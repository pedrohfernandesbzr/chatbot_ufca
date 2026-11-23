import os
import time
import streamlit as st
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI

MODELOS_NUVEM_PREFERIDOS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]

TIMEOUT_TENTATIVA_SEGUNDOS = 20.0
CB_FALHAS_MAXIMAS = 3
CB_COOLDOWN_SEGUNDOS = 120


class StreamInterrompidoError(Exception):
    """Sinaliza que o streaming foi cortado antes da conclusão."""


def obter_chave_gemini():
    try:
        chave = st.secrets["GOOGLE_API_KEY"]
        if chave and chave.strip():
            return chave.strip()
    except Exception:
        pass
    chave = os.environ.get("GOOGLE_API_KEY")
    return chave.strip() if chave and chave.strip() else None


def obter_modo_execucao():
    return os.environ.get("MODO_EXECUCAO", "auto")


def obter_modelo_local():
    return os.environ.get("MODELO_OLLAMA_ESCOLHIDO", "llama3.2:3b")


def _modelo_em_cooldown(nome_modelo):
    estado_cb = st.session_state.setdefault("cb_modelos", {})
    info = estado_cb.get(nome_modelo)
    if not info:
        return False
    if info["falhas"] >= CB_FALHAS_MAXIMAS:
        if time.time() - info["ultimo_erro"] < CB_COOLDOWN_SEGUNDOS:
            return True
        # Cooldown expirado: reseta contador para nova tentativa
        estado_cb[nome_modelo] = {"falhas": 0, "ultimo_erro": 0.0}
    return False


def _registrar_falha_modelo(nome_modelo):
    estado_cb = st.session_state.setdefault("cb_modelos", {})
    info = estado_cb.get(nome_modelo, {"falhas": 0, "ultimo_erro": 0.0})
    info["falhas"] += 1
    info["ultimo_erro"] = time.time()
    estado_cb[nome_modelo] = info


def _registrar_sucesso_modelo(nome_modelo):
    estado_cb = st.session_state.setdefault("cb_modelos", {})
    if nome_modelo in estado_cb:
        estado_cb[nome_modelo] = {"falhas": 0, "ultimo_erro": 0.0}


def _listar_modelos_ativos_na_conta(chave_api):
    """Consulta a API do Google e filtra apenas modelos ativos."""
    try:
        from google import genai
        cliente = genai.Client(api_key=chave_api)
        ativos = []
        for m in cliente.models.list():
            nome = m.name.replace("models/", "")
            acoes = getattr(m, "supported_actions", []) or []
            if "generateContent" in acoes and ("flash" in nome or "gemma" in nome):
                if any(x in nome for x in ["1.0", "1.5", "2.0", "2.5", "omni", "embedding", "image", "audio", "tts"]):
                    continue
                ativos.append(nome)
        return ativos
    except Exception as e:
        print(f"[Aviso] Nao foi possivel listar modelos dinamicos: {e}")
        return []


def _extrair_texto_limpo(pedaco):
    """Extrai estritamente texto visível (string pura), descartando raciocínio e assinaturas."""
    conteudo = getattr(pedaco, "content", None)

    if isinstance(conteudo, str):
        return conteudo

    if isinstance(conteudo, list):
        partes = []
        for bloco in conteudo:
            if isinstance(bloco, dict):
                if bloco.get("type") == "thought" or "signature" in bloco.get("extras", {}):
                    continue
                if bloco.get("type") == "text" and isinstance(bloco.get("text"), str):
                    partes.append(bloco["text"])
            elif isinstance(bloco, str):
                partes.append(bloco)
        return "".join(partes)

    return ""


def _instanciar_modelo_nuvem(nome_modelo, chave_api):
    # Modelos que usam defaults fixos de sampling e não aceitam temperature/thinking_budget
    if any(x in nome_modelo for x in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemma"]):
        return ChatGoogleGenerativeAI(
            model=nome_modelo,
            google_api_key=chave_api,
            max_output_tokens=800,
            timeout=TIMEOUT_TENTATIVA_SEGUNDOS,
            max_retries=0
        )

    return ChatGoogleGenerativeAI(
        model=nome_modelo,
        google_api_key=chave_api,
        temperature=0.3,
        max_output_tokens=800,
        timeout=TIMEOUT_TENTATIVA_SEGUNDOS,
        max_retries=0,
        thinking_budget=0,
        include_thoughts=False
    )


def gerar_resposta_com_fallback(prompt_template, variaveis_prompt):
    chave_gemini = obter_chave_gemini()
    modo = obter_modo_execucao()
    st.session_state["ultima_resposta_valida"] = False

    # 1. MODO NUVEM (Executado quando modo == 'nuvem' ou 'auto' com chave presente)
    if chave_gemini and modo in ("nuvem", "auto"):
        if "lista_modelos_nuvem" not in st.session_state:
            descobertos = _listar_modelos_ativos_na_conta(chave_gemini)
            fila = list(MODELOS_NUVEM_PREFERIDOS)
            for mod in descobertos:
                if mod not in fila:
                    fila.append(mod)
            st.session_state["lista_modelos_nuvem"] = fila

        lista_ordenada = list(st.session_state["lista_modelos_nuvem"])

        modelo_preferido = st.session_state.get("modelo_nuvem_ativo")
        if modelo_preferido and modelo_preferido in lista_ordenada:
            lista_ordenada.remove(modelo_preferido)
            lista_ordenada.insert(0, modelo_preferido)

        for nome_modelo in lista_ordenada:
            if _modelo_em_cooldown(nome_modelo):
                print(f"[Circuit Breaker] '{nome_modelo}' em cooldown. Pulando...")
                continue

            try:
                llm = _instanciar_modelo_nuvem(nome_modelo, chave_gemini)
                cadeia = prompt_template | llm
                fluxo = cadeia.stream(variaveis_prompt)

                primeiro_texto = ""
                for pedaco in fluxo:
                    texto = _extrair_texto_limpo(pedaco)
                    if texto:
                        primeiro_texto = texto
                        break

                if not primeiro_texto:
                    _registrar_falha_modelo(nome_modelo)
                    continue

                _registrar_sucesso_modelo(nome_modelo)
                st.session_state["modelo_nuvem_ativo"] = nome_modelo

                def gerador_valido():
                    yield primeiro_texto
                    try:
                        for pedaco in fluxo:
                            texto = _extrair_texto_limpo(pedaco)
                            if texto:
                                yield texto
                        st.session_state["ultima_resposta_valida"] = True
                    except Exception as erro_stream:
                        _registrar_falha_modelo(nome_modelo)
                        st.session_state["ultima_resposta_valida"] = False
                        raise StreamInterrompidoError(str(erro_stream)) from erro_stream

                return gerador_valido(), f"Nuvem ({nome_modelo})"

            except Exception as erro:
                _registrar_falha_modelo(nome_modelo)
                print(f"[Fallback LLM] '{nome_modelo}' pulado ({type(erro).__name__}: {erro}).")
                continue

        if modo == "nuvem":
            print("[Erro Nuvem] Nenhum modelo da API Gemini respondeu.")
            return None, None

    # 2. MODO LOCAL (Executado quando modo == 'local' ou 'auto' sem chave)
    modelo_local = obter_modelo_local()
    try:
        llm_local = ChatOllama(
            model=modelo_local,
            temperature=0.2,
            num_predict=800,
            repeat_penalty=1.2
        )
        cadeia_local = prompt_template | llm_local
        fluxo_local = cadeia_local.stream(variaveis_prompt)

        primeiro_texto_local = ""
        for pedaco in fluxo_local:
            texto = _extrair_texto_limpo(pedaco)
            if texto:
                primeiro_texto_local = texto
                break

        if not primeiro_texto_local:
            return None, None

        def gerador_local_valido():
            yield primeiro_texto_local
            try:
                for pedaco in fluxo_local:
                    texto = _extrair_texto_limpo(pedaco)
                    if texto:
                        yield texto
                st.session_state["ultima_resposta_valida"] = True
            except Exception as erro_stream_local:
                st.session_state["ultima_resposta_valida"] = False
                raise StreamInterrompidoError(str(erro_stream_local)) from erro_stream_local

        return gerador_local_valido(), f"Local Ollama ({modelo_local})"

    except Exception as erro_local:
        print(f"[Erro Local] Ollama nao respondeu: {erro_local}")
        return None, None