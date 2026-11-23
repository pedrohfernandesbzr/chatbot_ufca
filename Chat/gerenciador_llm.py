import os
import streamlit as st
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI

MODELOS_NUVEM_PREFERIDOS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]


def obter_chave_gemini():
    try:
        return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        chave = os.environ.get("GOOGLE_API_KEY")
        return chave if chave and chave.strip() != "" else None


def obter_modo_execucao():
    return os.environ.get("MODO_EXECUCAO", "auto")


def obter_modelo_local():
    return os.environ.get("MODELO_OLLAMA_ESCOLHIDO", "llama3.2:3b")


def _listar_modelos_ativos_na_conta(chave_api):
    """Consulta a API do Google e filtra apenas modelos ativos (ignorando 2.0 e 2.5 descontinuados)."""
    try:
        from google import genai
        cliente = genai.Client(api_key=chave_api)
        ativos = []
        for m in cliente.models.list():
            nome = m.name.replace("models/", "")
            acoes = getattr(m, "supported_actions", []) or []
            if "generateContent" in acoes and ("flash" in nome or "gemma" in nome):
                if any(x in nome for x in ["2.0", "2.5", "embedding", "image", "audio", "tts"]):
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
    # Modelos '3.5-flash-lite' e 'gemma' não aceitam thinking_budget ou temperature customizada
    if "3.5-flash-lite" in nome_modelo or "gemma" in nome_modelo:
        return ChatGoogleGenerativeAI(
            model=nome_modelo,
            google_api_key=chave_api,
            max_output_tokens=600,
            timeout=20.0,
            max_retries=0
        )

    return ChatGoogleGenerativeAI(
        model=nome_modelo,
        google_api_key=chave_api,
        temperature=0.1,
        max_output_tokens=600,
        timeout=20.0,
        max_retries=0,
        thinking_budget=0,
        include_thoughts=False
    )


def gerar_resposta_com_fallback(prompt_template, variaveis_prompt):
    chave_gemini = obter_chave_gemini()
    modo = obter_modo_execucao()


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
                    continue

                st.session_state["modelo_nuvem_ativo"] = nome_modelo

                def gerador_valido():
                    yield primeiro_texto
                    try:
                        for pedaco in fluxo:
                            texto = _extrair_texto_limpo(pedaco)
                            if texto:
                                yield texto
                    except Exception as erro_stream:
                        print(f"[Aviso Stream] Interrompido no meio ({type(erro_stream).__name__}): {erro_stream}")
                        yield "\n\n*(A conexão oscilou antes de concluir toda a resposta. Se precisar de mais detalhes, pergunte novamente.)*"

                return gerador_valido(), f"Nuvem ({nome_modelo})"

            except Exception as erro:
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
            temperature=0.0,
            num_predict=350,
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
            for pedaco in fluxo_local:
                texto = _extrair_texto_limpo(pedaco)
                if texto:
                    yield texto

        return gerador_local_valido(), f"Local Ollama ({modelo_local})"

    except Exception as erro_local:
        print(f"[Erro Local] Ollama nao respondeu: {erro_local}")
        return None, None