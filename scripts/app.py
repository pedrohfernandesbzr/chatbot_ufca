import os
import re
import json
import uuid
from datetime import datetime
import streamlit as st
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.prompts import ChatPromptTemplate

from config import (
    ARQUIVO_BANCO_GEMINI,
    ARQUIVO_BANCO_OLLAMA,
    ARQUIVO_RESPOSTAS_RAPIDAS,
)
from criar_banco import criar_base_conhecimento
from gerenciador_llm import (
    obter_chave_gemini,
    obter_modo_execucao,
    gerar_resposta_com_fallback,
    StreamInterrompidoError,
)
from metricas_cache import (
    ARQUIVO_TELEMETRIA,
    normalizar_texto,
    buscar_no_cache,
    salvar_no_cache,
    registrar_telemetria,
    obter_resumo_telemetria
)
from interface_ui import (
    obter_caminhos_icones,
    injetar_estilos,
    renderizar_topbar,
    renderizar_rodape,
    renderizar_sidebar_brand,
    renderizar_sidebar_participe,
    renderizar_hero
)

# ==============================================================================
# CONFIGURAÇÕES GERAIS E CONSTANTES
# ==============================================================================
MODELO_OLLAMA_EMBEDDING = "nomic-embed-text"
MODELO_GEMINI_EMBEDDING = "models/gemini-embedding-001"

SUGESTOES_RAPIDAS = [
    "Como acompanho meu processo seletivo pelo SISU?",
    "Como acessar o SIGAA?",
    "Sou veterano. Como me matriculo?",
    "Quais cursos de graduação a UFCA oferece?",
    "Como trancar disciplinas?",
    "Sou calouro. O que preciso saber?"
]

icones = obter_caminhos_icones()
AVATAR_ASSISTENTE = icones["avatar_assistente"]

st.set_page_config(
    page_title="Chatbot UFCA - Assistente Virtual",
    page_icon=icones["favicon"],
    layout="wide",
    initial_sidebar_state="expanded"
)

injetar_estilos()
renderizar_topbar()
renderizar_rodape()

# ==============================================================================
# CARREGAMENTO DO BANCO VETORIAL E RESPOSTAS RÁPIDAS
# ==============================================================================
@st.cache_resource
def carregar_banco(usar_nuvem: bool):
    if usar_nuvem:
        chave_gemini = obter_chave_gemini()
        if not ARQUIVO_BANCO_GEMINI.exists():
            criar_base_conhecimento(modo_forcado="gemini")
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model=MODELO_GEMINI_EMBEDDING,
            google_api_key=chave_gemini
        )
        return InMemoryVectorStore.load(str(ARQUIVO_BANCO_GEMINI), embedding=embeddings)
    else:
        if not ARQUIVO_BANCO_OLLAMA.exists():
            criar_base_conhecimento(modo_forcado="ollama")
        embeddings = OllamaEmbeddings(model=MODELO_OLLAMA_EMBEDDING)
        return InMemoryVectorStore.load(str(ARQUIVO_BANCO_OLLAMA), embedding=embeddings)


@st.cache_data
def carregar_respostas_rapidas():
    if not ARQUIVO_RESPOSTAS_RAPIDAS.exists():
        print(f"[Aviso] Arquivo não encontrado: {ARQUIVO_RESPOSTAS_RAPIDAS}")
        return {}
    try:
        with open(ARQUIVO_RESPOSTAS_RAPIDAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Aviso] Erro ao ler '{ARQUIVO_RESPOSTAS_RAPIDAS}': {e}")
        return {}


chave_atual = obter_chave_gemini()
modo_atual = obter_modo_execucao()
usar_banco_nuvem = bool(chave_atual) and modo_atual in ("nuvem", "auto")

try:
    with st.spinner("Preparando base de conhecimento..."):
        vector_store = carregar_banco(usar_banco_nuvem)
except Exception as erro_banco:
    st.error(
        f"Não foi possível inicializar o banco vetorial ({'Nuvem 3072d' if usar_banco_nuvem else 'Local Ollama 768d'}). "
        f"Detalhe técnico: {erro_banco}"
    )
    st.stop()

# ==============================================================================
# GERENCIAMENTO DE MÚLTIPLAS CONVERSAS
# ==============================================================================
def criar_nova_conversa():
    novo_id = str(uuid.uuid4())
    st.session_state.conversas[novo_id] = {
        "titulo": "Nova conversa",
        "data": datetime.now().strftime("%d/%m %H:%M"),
        "mensagens": []
    }
    st.session_state.conversa_atual = novo_id


if "conversas" not in st.session_state:
    st.session_state.conversas = {}
    criar_nova_conversa()

conversa_ativa = st.session_state.conversas[st.session_state.conversa_atual]
mensagens_atuais = conversa_ativa["mensagens"]


def gerar_markdown_exportacao(conversa):
    linhas = [
        "# Histórico de Atendimento - Chatbot UFCA",
        f"**Assunto:** {conversa['titulo']}",
        f"**Data/Hora de início:** {conversa['data']}",
        "---\n"
    ]
    for msg in conversa["mensagens"]:
        autor = "**Usuário**" if msg["role"] == "user" else "**Chatbot UFCA**"
        linhas.append(f"### {autor}\n{msg['content']}\n")
    return "\n".join(linhas)


# ==============================================================================
# BARRA LATERAL (HISTÓRICO, EXPORTAÇÃO, MÉTRICAS E PARTICIPAÇÃO)
# ==============================================================================
with st.sidebar:
    renderizar_sidebar_brand()

    if st.button("+ Nova conversa", use_container_width=True, type="primary"):
        criar_nova_conversa()
        st.rerun()

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">Conversas Abertas</div>', unsafe_allow_html=True)

    for cid in reversed(list(st.session_state.conversas.keys())):
        conv = st.session_state.conversas[cid]
        if st.button(conv["titulo"], key=f"btn_{cid}", use_container_width=True, type="secondary"):
            st.session_state.conversa_atual = cid
            st.rerun()

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">Dados e desempenho</div>', unsafe_allow_html=True)

    conteudo_md = gerar_markdown_exportacao(conversa_ativa)
    nome_arquivo = f"conversa_ufca_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    st.download_button(
        label="Exportar conversa (.md)",
        data=conteudo_md,
        file_name=nome_arquivo,
        mime="text/markdown",
        use_container_width=True
    )

    if "mostrar_indicadores" not in st.session_state:
        st.session_state.mostrar_indicadores = False

    seta_ind = "v" if st.session_state.mostrar_indicadores else ">"
    if st.button(f"{seta_ind}  Indicadores de Uso", key="btn_toggle_ind", use_container_width=True, type="primary"):
        st.session_state.mostrar_indicadores = not st.session_state.mostrar_indicadores
        st.rerun()

    if st.session_state.mostrar_indicadores:
        resumo = obter_resumo_telemetria()
        if resumo and resumo["total"] > 0:
            col1, col2 = st.columns(2)
            col1.metric("Perguntas", resumo["total"])
            col2.metric("Lacunas", resumo["lacunas"])
            st.caption(f"Via cache: {resumo['via_cache']} respostas")
            if os.path.exists(ARQUIVO_TELEMETRIA):
                with open(ARQUIVO_TELEMETRIA, "rb") as f_csv:
                    st.download_button(
                        label="Baixar relatório (.csv)",
                        data=f_csv.read(),
                        file_name="telemetria_ufca.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        else:
            st.caption("Nenhuma métrica registrada ainda.")

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">PARTICIPE!</div>', unsafe_allow_html=True)
    renderizar_sidebar_participe()

# ==============================================================================
# FUNÇÕES DE TRIAGEM, MEMÓRIA E PROMPT
# ==============================================================================
def verificar_mensagem(texto):
    texto_limpo = normalizar_texto(texto)
    categorias = carregar_respostas_rapidas()

    for dados in categorias.values():
        gatilhos = {normalizar_texto(p) for p in dados.get("perguntas", [])}
        if texto_limpo in gatilhos:
            return dados.get("resposta")

    return None


def obter_historico_recente():
    historico = mensagens_atuais[-5:-1]
    if not historico:
        return "Nenhuma conversa anterior."
    linhas = []
    for msg in historico:
        papel = "Usuário" if msg["role"] == "user" else "Assistente"
        linhas.append(f"{papel}: {msg['content']}")
    return "\n".join(linhas)


TEMPLATE_PROMPT = """
Você é o Assistente Virtual oficial da Universidade Federal do Cariri (UFCA).
Seu objetivo é ajudar visitantes, calouros e estudantes com dúvidas gerais de forma acolhedora, clara e objetiva.

REGRAS ESTRITAS:
1. Responda APENAS com base nas informações fornecidas no CONTEXTO OFICIAL abaixo.
2. Use o HISTÓRICO DA CONVERSA apenas para entender a que o usuário está se referindo (ex: pronomes como "dela", "esse setor", "qual o e-mail?").
3. NUNCA invente prazos, regras, e-mails, telefones ou links que não estejam explicitamente no contexto.
4. Se a resposta não estiver no contexto, escreva [*] no inpicio da resposta e diga educadamente que não possui essa informação no momento e oriente o usuário a procurar a secretaria do curso ou a pró-reitoria correspondente.
5. TRIAGEM: Sempre que a dúvida exigir um procedimento administrativo, explique o passo a passo básico (se constar no contexto) e forneça os dados de contato do setor responsável.
6. Seja conciso e direto ao ponto.

HISTÓRICO RECENTE DA CONVERSA:
{historico}

CONTEXTO OFICIAL DA INSTITUIÇÃO:
{contexto}

PERGUNTA ATUAL DO USUÁRIO:
{pergunta}
"""

prompt = ChatPromptTemplate.from_template(TEMPLATE_PROMPT)

# ==============================================================================
# INTERFACE PRINCIPAL (TELA INICIAL vs. CONVERSA ATIVA)
# ==============================================================================
sugestao_clicada = None

if len(mensagens_atuais) == 0:
    renderizar_hero()
    st.markdown('<div class="sugestoes-titulo">Sugestões de perguntas:</div>', unsafe_allow_html=True)

    for linha_idx in range(0, len(SUGESTOES_RAPIDAS), 3):
        cols = st.columns([1.35, 1, 1.25], gap="small")
        for col_idx, texto_sug in enumerate(SUGESTOES_RAPIDAS[linha_idx:linha_idx + 3]):
            with cols[col_idx]:
                if st.button(texto_sug, key=f"sug_{linha_idx + col_idx}", use_container_width=True, type="secondary"):
                    sugestao_clicada = texto_sug
else:
    for msg in mensagens_atuais:
        avatar = AVATAR_ASSISTENTE if msg["role"] == "assistant" else None
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            debug_info = msg.get("debug_info")
            if debug_info:
                with st.expander(debug_info["titulo"]):
                    st.caption(debug_info["subtitulo"])
                    for i, trecho in enumerate(debug_info.get("trechos", []), 1):
                        st.markdown(f"**Trecho {i} ({trecho['fonte']}):**")
                        st.text(trecho["conteudo"])

# Input fixo inferior
entrada_usuario = st.chat_input("Digite sua dúvida aqui...")
pergunta = sugestao_clicada or entrada_usuario

if pergunta:
    if conversa_ativa["titulo"] == "Nova conversa":
        titulo_resumido = pergunta[:38] + "..." if len(pergunta) > 38 else pergunta
        conversa_ativa["titulo"] = titulo_resumido

    mensagens_atuais.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    debug_registrado = None

    with st.chat_message("assistant", avatar=AVATAR_ASSISTENTE):
        resposta_rapida = verificar_mensagem(pergunta)
        resposta_cache = buscar_no_cache(pergunta) if not resposta_rapida else None

        # 1. Resposta imediata por saudação ou agradecimento
        if resposta_rapida:
            st.markdown(resposta_rapida)
            resposta_completa = resposta_rapida
            registrar_telemetria(pergunta, "Saudacao", resposta_completa)

        # 2. Resposta imediata via Cache
        elif resposta_cache and len(mensagens_atuais) <= 1:
            st.markdown(resposta_cache)
            resposta_completa = resposta_cache
            registrar_telemetria(pergunta, "Cache", resposta_completa)
            debug_registrado = {
                "titulo": "Ver detalhes técnicos (Modo Debug)",
                "subtitulo": "Origem: Cache local instantâneo (0 tokens consumidos)",
                "trechos": []
            }

        # 3. Fluxo completo RAG + LLM
        else:
            consulta_busca = pergunta
            if len(mensagens_atuais) >= 3:
                pergunta_anterior = mensagens_atuais[-3]["content"]
                consulta_busca = f"{pergunta_anterior} - {pergunta}"

            docs_encontrados = None
            erro_busca = None
            for tentativa in range(2):
                try:
                    docs_encontrados = vector_store.similarity_search(consulta_busca, k=4)
                    break
                except Exception as e:
                    erro_busca = e

            if docs_encontrados is None:
                resposta_completa = (
                    "Não foi possível consultar a base de documentos neste momento "
                    f"(erro técnico: {type(erro_busca).__name__}). Tente novamente."
                )
                st.warning(resposta_completa)
                registrar_telemetria(pergunta, "Erro_Busca", resposta_completa)
            else:
                contexto_texto = "\n\n---\n\n".join(
                    [f"[Fonte: {doc.metadata.get('fonte', 'Documento')}]\n{doc.page_content}" for doc in docs_encontrados]
                )

                variaveis = {
                    "historico": obter_historico_recente(),
                    "contexto": contexto_texto,
                    "pergunta": pergunta
                }

                gerador_fluxo, modelo_utilizado = gerar_resposta_com_fallback(prompt, variaveis)

                if gerador_fluxo is not None:
                    try:
                        resposta_completa = st.write_stream(gerador_fluxo)
                    except StreamInterrompidoError:
                        resposta_completa = (
                            "A conexão oscilou antes de concluir toda a resposta. "
                            "Por favor, envie sua pergunta novamente."
                        )
                        st.warning(resposta_completa)
                    except Exception:
                        st.session_state["ultima_resposta_valida"] = False
                        resposta_completa = (
                            "Ocorreu uma falha inesperada durante a geração da resposta. "
                            "Por favor, tente novamente."
                        )
                        st.warning(resposta_completa)

                    resposta_eh_valida = st.session_state.get("ultima_resposta_valida", False)

                    if resposta_eh_valida and len(mensagens_atuais) <= 1 and resposta_completa.strip():
                        salvar_no_cache(pergunta, resposta_completa)

                    registrar_telemetria(
                        pergunta,
                        modelo_utilizado if resposta_eh_valida else "Falha_Stream",
                        resposta_completa
                    )

                    debug_registrado = {
                        "titulo": "Ver trechos consultados (Modo Debug)",
                        "subtitulo": f"Modelo utilizado nesta resposta: {modelo_utilizado}",
                        "trechos": [
                            {"fonte": doc.metadata.get("fonte", "Documento"), "conteudo": doc.page_content}
                            for doc in docs_encontrados
                        ]
                    }
                else:
                    resposta_completa = (
                        "Desculpe, todos os servidores de atendimento estão temporariamente indisponíveis. "
                        "Por favor, tente novamente em alguns instantes."
                    )
                    st.warning(resposta_completa)
                    registrar_telemetria(pergunta, "Indisponivel", resposta_completa)

    mensagens_atuais.append({
        "role": "assistant",
        "content": resposta_completa,
        "debug_info": debug_registrado
    })
    st.rerun()