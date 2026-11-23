import os
import re
import json
import uuid
import base64
from datetime import datetime
import streamlit as st
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.prompts import ChatPromptTemplate
from gerenciador_llm import obter_chave_gemini, gerar_resposta_com_fallback
from metricas_cache import (
    ARQUIVO_TELEMETRIA,
    buscar_no_cache,
    salvar_no_cache,
    registrar_telemetria,
    obter_resumo_telemetria
)

# ==============================================================================
# CONFIGURAÇÕES GERAIS E CONSTANTES
# ==============================================================================
ARQUIVO_BANCO = "banco_vetorial.json"
MODELO_OLLAMA_EMBEDDING = "nomic-embed-text"
MODELO_GEMINI_EMBEDDING = "models/gemini-embedding-001"
PASTA_ASSETS = "assets"

SUGESTOES_RAPIDAS = [
    "Como acompanho meu processo seletivo pelo SISU?",
    "Como acessar o SIGAA?",
    "Sou veterano. Como me matriculo?",
    "Quais cursos de graduação a UFCA oferece?",
    "Como trancar disciplinas?",
    "Sou calouro. O que preciso saber?"
]

# ==============================================================================
# CARREGAMENTO DE IMAGENS E ÍCONES DA PASTA ASSETS
# ==============================================================================
def carregar_asset_base64(nome_arquivo):
    caminho = os.path.join(PASTA_ASSETS, nome_arquivo)
    if os.path.exists(caminho):
        with open(caminho, "rb") as f:
            ext = nome_arquivo.split(".")[-1].lower()
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    return ""

CAMINHO_FAVICON = os.path.join(PASTA_ASSETS, "logo_chatbot_ufca_beta.png")
CAMINHO_AVATAR_CHAT = os.path.join(PASTA_ASSETS, "icone_sms_chatbot_ufca_beta.png")

st.set_page_config(
    page_title="Chatbot UFCA - Assistente Virtual",
    page_icon=CAMINHO_FAVICON if os.path.exists(CAMINHO_FAVICON) else None,
    layout="wide",
    initial_sidebar_state="expanded"
)

LOGO_CHATBOT_URI = carregar_asset_base64("logo_chatbot_ufca_beta.png")
ICONE_SMS_URI = carregar_asset_base64("icone_sms_chatbot_ufca_beta.png")
BRASAO_UFCA_URI = carregar_asset_base64("brasao_ufca.png")
GITHUB_ICONE_URI = carregar_asset_base64("github_icone.png")
VERSION_ICONE_URI = carregar_asset_base64("version_icone.jpg")

AVATAR_ASSISTENTE = CAMINHO_AVATAR_CHAT if os.path.exists(CAMINHO_AVATAR_CHAT) else None

# ==============================================================================
# ESTILIZAÇÃO CSS COMPLETA
# ==============================================================================
def injetar_css_customizado():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #1F1F1F;
        }

        /* Cabeçalho nativo do Streamlit posicionado abaixo da barra institucional */
        header[data-testid="stHeader"] {
            background: transparent !important;
            top: 48px !important;
            height: 44px !important;
            z-index: 998 !important;
        }

        /* Barra Superior Institucional Fixa (#3A332D) */
        .ufca-topbar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 48px;
            background-color: #3A332D;
            color: #EAE4DC;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 28px;
            z-index: 1000001;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.18);
            font-size: 13px;
        }

        .ufca-topbar-left, .ufca-topbar-right {
            display: flex;
            align-items: center;
            gap: 32px;
        }

        .ufca-topbar a {
            color: #EAE4DC !important;
            text-decoration: none !important;
            font-weight: 500;
            letter-spacing: 0.3px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: color 0.2s ease;
        }

        .ufca-topbar a:hover {
            color: #F2C94C !important;
        }

        .ufca-topbar img {
            height: 24px;
            width: auto;
            object-fit: contain;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            top: 48px !important;
            height: calc(100vh - 48px) !important;
            background-color: #F4F5F6 !important;
            border-right: 1px solid #D8DCE0 !important;
        }

        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 0.8rem !important;
            padding-bottom: 1.5rem !important;
        }

        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 2px 4px 12px 4px;
        }

        .sidebar-brand img {
            width: 44px;
            height: 44px;
            object-fit: contain;
        }

        .sidebar-brand-title {
            font-size: 18px;
            font-weight: 700;
            color: #1A1A1A;
            line-height: 1.2;
        }

        .sidebar-section-label {
            font-size: 12.5px;
            font-weight: 700;
            color: #1A1A1A;
            margin: 12px 0 6px 2px;
        }

        .sidebar-divider {
            height: 1px;
            background-color: #C7CCD1;
            margin: 12px 0;
        }

        /* Botões da Sidebar - Primários (#3B6E75) */
        section[data-testid="stSidebar"] button[kind="primary"],
        section[data-testid="stSidebar"] .stDownloadButton > button {
            background-color: #3B6E75 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            padding: 0.48rem 0.75rem !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.08) !important;
            transition: background-color 0.2s ease !important;
        }

        section[data-testid="stSidebar"] button[kind="primary"]:hover,
        section[data-testid="stSidebar"] .stDownloadButton > button:hover {
            background-color: #2E585E !important;
            color: #FFFFFF !important;
        }

        /* Botões da Sidebar - Lista de Conversas Abertas */
        section[data-testid="stSidebar"] button[kind="secondary"] {
            background-color: #FFFFFF !important;
            color: #222222 !important;
            border: 1px solid #C8CDD2 !important;
            border-radius: 7px !important;
            font-weight: 600 !important;
            font-size: 12px !important;
            padding: 0.35rem 0.6rem !important;
            text-align: left !important;
            justify-content: flex-start !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }

        section[data-testid="stSidebar"] button[kind="secondary"]:hover {
            border-color: #3B6E75 !important;
            background-color: #EEF5F6 !important;
        }

        .sidebar-action-link {
            display: block;
            width: 100%;
            background-color: #3B6E75;
            color: #FFFFFF !important;
            text-align: center;
            text-decoration: none !important;
            font-weight: 600;
            font-size: 12.5px;
            padding: 8px 10px;
            border-radius: 8px;
            margin-bottom: 7px;
            transition: background-color 0.2s ease;
        }

        .sidebar-action-link:hover {
            background-color: #2E585E;
            color: #FFFFFF !important;
        }

        /* Container Principal */
        .main .block-container {
            padding-top: 64px !important;
            padding-bottom: 165px !important;
            max-width: 920px !important;
        }

        /* Tela de Boas-vindas (Hero) */
        .hero-wrapper {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-top: 16px;
            margin-bottom: 18px;
        }

        .hero-header {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            margin-bottom: 14px;
        }

        .hero-avatar-circle {
            width: 84px;
            height: 84px;
            border-radius: 50%;
            border: 1.5px solid #4A4A4A;
            background-color: #FFFFFF;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 8px;
            flex-shrink: 0;
        }

        .hero-avatar-circle img {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

        .hero-title {
            font-size: 27px;
            font-weight: 700;
            color: #111111;
            line-height: 1.25;
            margin: 0;
        }

        .hero-divider {
            width: 100%;
            height: 1px;
            background-color: #9E9E9E;
            margin: 6px 0 10px 0;
        }

        .hero-subtitle {
            font-size: 14px;
            color: #333333;
            text-align: center;
            margin: 0;
        }

        /* Cabeçalho de Conversa Ativa */
        .chat-active-header {
            text-align: center;
            padding-bottom: 12px;
            margin-bottom: 18px;
            border-bottom: 1px solid #B5B5B5;
        }

        .chat-active-header h2 {
            font-size: 23px;
            font-weight: 700;
            color: #111111;
            margin: 0;
        }

        /* Botões de Sugestão Rápida */
        .sugestoes-titulo {
            font-size: 14.5px;
            font-weight: 700;
            color: #1A1A1A;
            margin-bottom: 10px;
        }

        div[data-testid="stMainBlockContainer"] button[kind="secondary"] {
            background-color: #FFFFFF !important;
            color: #2B2B2B !important;
            border: 1px solid #BDBDBD !important;
            border-radius: 9px !important;
            font-size: 13.5px !important;
            font-weight: 400 !important;
            padding: 0.55rem 0.9rem !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
            transition: all 0.15s ease !important;
            min-height: 44px !important;
        }

        div[data-testid="stMainBlockContainer"] button[kind="secondary"]:hover {
            border-color: #3B6E75 !important;
            background-color: #F4F9FA !important;
            color: #111111 !important;
        }

        /* Mensagens do Chat */
        div[data-testid="stChatMessage"] {
            background-color: transparent !important;
            padding: 0.75rem 0.25rem !important;
            gap: 14px !important;
        }

        div[data-testid="stChatMessageAvatarUser"] {
            background-color: #D9DDE2 !important;
            color: #6B7280 !important;
            width: 38px !important;
            height: 38px !important;
        }

        div[data-testid="stChatMessageAvatarAssistant"] {
            background-color: #FFFFFF !important;
            border: 1.2px solid #555555 !important;
            width: 38px !important;
            height: 38px !important;
            padding: 3px !important;
        }

        /* ======================================================================
           CAIXA DE PERGUNTA (stBottom) E RODAPÉ LEGAL ALINHADOS E RESPONSIVOS
           ====================================================================== */
        div[data-testid="stBottom"] {
            background-color: #FFFFFF !important;
            padding-top: 6px !important;
            padding-bottom: 78px !important;
        }

        div[data-testid="stBottom"] > div {
            max-width: 920px !important;
            width: 100% !important;
            margin: 0 auto !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        /* Remove a borda interna dupla do Streamlit e encorpa a borda externa */
        div[data-testid="stChatInput"] {
            border: 2px solid #8E959C !important;
            border-radius: 14px !important;
            background-color: #FFFFFF !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05) !important;
            overflow: hidden !important;
            transition: border-color 0.2s ease !important;
        }

        div[data-testid="stChatInput"]:focus-within {
            border-color: #3B6E75 !important;
        }

        div[data-testid="stChatInput"] > div {
            border: none !important;
            box-shadow: none !important;
            background-color: transparent !important;
        }

        div[data-testid="stChatInput"] [data-baseweb="textarea"],
        div[data-testid="stChatInput"] [data-baseweb="base-input"] {
            border: none !important;
            box-shadow: none !important;
            background-color: transparent !important;
        }

        div[data-testid="stChatInput"] textarea {
            font-size: 14.5px !important;
            padding: 12px 14px !important;
            background-color: transparent !important;
        }

        /* Botão de Enviar */
        div[data-testid="stChatInput"] button {
            background-color: #3B6E75 !important;
            color: #FFFFFF !important;
            border-radius: 50% !important;
            width: 36px !important;
            height: 36px !important;
            margin: 5px !important;
            border: none !important;
        }

        div[data-testid="stChatInput"] button:hover {
            background-color: #2E585E !important;
        }

        /* Rodapé Fixo (alinhado exatamente à largura do container principal e responsivo ao recuo da sidebar) */
        .ufca-footer-wrapper {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #FFFFFF;
            padding: 4px 0 8px 0;
            z-index: 999;
            display: flex;
            justify-content: center;
            transition: padding-left 0.2s ease;
        }

        @media (min-width: 769px) {
            body:has(section[data-testid="stSidebar"][aria-expanded="true"]) .ufca-footer-wrapper {
                padding-left: 21rem;
            }
            body:has(section[data-testid="stSidebar"][aria-expanded="false"]) .ufca-footer-wrapper {
                padding-left: 0;
            }
        }

        .ufca-footer-inner {
            width: 100%;
            max-width: 920px;
            padding: 0 1rem;
            display: grid;
            grid-template-columns: 1.85fr 1fr;
            gap: 16px;
            align-items: center;
        }

        .ufca-disclaimer-box {
            background-color: #FFF7C2;
            border-radius: 6px;
            padding: 7px 12px;
            font-size: 10.5px;
            line-height: 1.32;
            color: #2C2A1E;
            width: 100%;
        }

        .ufca-credits-box {
            font-size: 11px;
            line-height: 1.4;
            color: #1F1F1F;
        }

        .ufca-credits-box strong {
            font-size: 11.5px;
            display: block;
            margin-bottom: 2px;
        }

        .ufca-credits-box a {
            color: #1F1F1F !important;
            text-decoration: underline !important;
            word-break: break-all;
        }

        .ufca-credit-row {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-top: 2px;
        }

        .ufca-credit-row img {
            width: 15px;
            height: 15px;
            object-fit: contain;
            flex-shrink: 0;
        }

        /* Botão Deploy */
        div[data-testid="stDeployButton"] button {
            background-color: #3B6E75 !important;
            color: #FFFFFF !important;
            border-radius: 6px !important;
        }
    </style>
    """, unsafe_allow_html=True)

def renderizar_barra_superior():
    img_brasao = f'<img src="{BRASAO_UFCA_URI}" alt="Brasão UFCA">' if BRASAO_UFCA_URI else ""
    st.markdown(f"""
    <div class="ufca-topbar">
        <div class="ufca-topbar-left">
            <a href="https://github.com/pedrohfernandesbzr/chatbot_ufca#readme" target="_blank">MAIS INFORMAÇÕES</a>
            <a href="https://github.com/pedrohfernandesbzr/chatbot_ufca" target="_blank">CONTRIBUA COM O PROJETO</a>
        </div>
        <div class="ufca-topbar-right">
            <a href="https://www.ufca.edu.br/" target="_blank">
                {img_brasao}
                <span>Site oficial da UFCA</span>
            </a>
            <a href="https://www.ufca.edu.br/instituicao/administrativo/acesso-a-informacao/institucional/quem-e-quem/" target="_blank">
                <span>Contatos</span>
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)

def renderizar_rodape_fixo():
    img_github = f'<img src="{GITHUB_ICONE_URI}" alt="GitHub">' if GITHUB_ICONE_URI else ""
    img_version = f'<img src="{VERSION_ICONE_URI}" alt="Versão">' if VERSION_ICONE_URI else ""

    st.markdown(f"""
    <div class="ufca-footer-wrapper">
        <div class="ufca-footer-inner">
            <div class="ufca-disclaimer-box">
                <strong>Chatbot UFCA (Beta) - v0.1.0:</strong> Este projeto é desenvolvido por estudantes e não possui qualquer vínculo institucional com a universidade. Ele é de um sistema de IA ainda incompleto, em desenvolvimento, e está sujeito a erros. NÃO considere as respostas como verdade absoluta e NUNCA tome decisões baseadas nelas. Verifique informações importantes nos canais e repositórios oficiais da UFCA.
            </div>
            <div class="ufca-credits-box">
                <strong>Chatbot UFCA - v0.1.0</strong>
                <div class="ufca-credit-row">
                    {img_github}
                    <a href="https://github.com/pedrohfernandesbzr/chatbot_ufca" target="_blank">https://github.com/pedrohfernandesbzr/chatbot_ufca</a>
                </div>
                <div class="ufca-credit-row">
                    {img_version}
                    <span>Protótipo, Versão Beta, v0.1.0</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

injetar_css_customizado()
renderizar_barra_superior()
renderizar_rodape_fixo()

# ==============================================================================
# CARREGAMENTO DO BANCO VETORIAL
# ==============================================================================
def detectar_tipo_banco(caminho_arquivo):
    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)
        primeiro_item = next(iter(dados.values()))
        tamanho_vetor = len(primeiro_item["vector"])
        return "ollama" if tamanho_vetor == 768 else "gemini"
    except Exception:
        return "gemini" if obter_chave_gemini() else "ollama"

@st.cache_resource
def carregar_banco():
    if not os.path.exists(ARQUIVO_BANCO):
        return None

    tipo_banco = detectar_tipo_banco(ARQUIVO_BANCO)
    chave_gemini = obter_chave_gemini()

    if tipo_banco == "gemini" and chave_gemini:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model=MODELO_GEMINI_EMBEDDING,
            google_api_key=chave_gemini
        )
    else:
        embeddings = OllamaEmbeddings(model=MODELO_OLLAMA_EMBEDDING)

    return InMemoryVectorStore.load(ARQUIVO_BANCO, embedding=embeddings)

vector_store = carregar_banco()

if vector_store is None:
    st.error("Arquivo 'banco_vetorial.json' não encontrado! Rode a opção 3 no painel para criá-lo.")
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
    img_sidebar = f'<img src="{LOGO_CHATBOT_URI}" alt="Logo Chatbot UFCA">' if LOGO_CHATBOT_URI else ""
    st.markdown(f"""
    <div class="sidebar-brand">
        {img_sidebar}
        <span class="sidebar-brand-title">Chatbot UFCA</span>
    </div>
    """, unsafe_allow_html=True)

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
    st.markdown("""
        <a class="sidebar-action-link" href="https://github.com/pedrohfernandesbzr/chatbot_ufca/discussions" target="_blank">
            Compartilhe sua experiência
        </a>
        <a class="sidebar-action-link" href="https://github.com/pedrohfernandesbzr/chatbot_ufca/issues" target="_blank">
            Reporte problemas e dê ideias
        </a>
    """, unsafe_allow_html=True)

# ==============================================================================
# FUNÇÕES DE TRIAGEM, MEMÓRIA E PROMPT
# ==============================================================================
ARQUIVO_RESPOSTAS_RAPIDAS = "respostas_rapidas.json"

@st.cache_data
def carregar_respostas_rapidas():
    if not os.path.exists(ARQUIVO_RESPOSTAS_RAPIDAS):
        return {}
    try:
        with open(ARQUIVO_RESPOSTAS_RAPIDAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Aviso] Erro ao ler '{ARQUIVO_RESPOSTAS_RAPIDAS}': {e}")
        return {}

def verificar_mensagem(texto):
    texto_limpo = re.sub(r'[^\w\s]', '', texto.lower()).strip()
    categorias = carregar_respostas_rapidas()

    for dados in categorias.values():
        gatilhos = {p.lower().strip() for p in dados.get("perguntas", [])}
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
4. Se a resposta não estiver no contexto, diga educadamente que não possui essa informação no momento e oriente o usuário a procurar a secretaria do curso ou a pró-reitoria correspondente.
5. TRIAGEM: Sempre que a dúvida exigir um procedimento administrativo, explique o passo a passo básico (se constar no contexto) e forneça os dados de contato do setor responsável.
6. Seja conciso e direto ao ponto: responda em no máximo 2 parágrafos curtos ou até 4 tópicos objetivos.
7. Não utilize emojis nas suas respostas.

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
    # --- ESTADO 1: TELA INICIAL DE BOAS-VINDAS ---
    img_hero = f'<div class="hero-avatar-circle"><img src="{ICONE_SMS_URI or LOGO_CHATBOT_URI}" alt="Assistente Virtual UFCA"></div>' if (ICONE_SMS_URI or LOGO_CHATBOT_URI) else ""
    st.markdown(f"""
    <div class="hero-wrapper">
        <div class="hero-header">
            {img_hero}
            <h1 class="hero-title">Sou o assistente virtual da UFCA!<br>Como posso te ajudar?</h1>
        </div>
        <div class="hero-divider"></div>
        <p class="hero-subtitle">Tire dúvidas sobre cursos, setores, auxílios, editais, eventos, prazos e atendimento antes de falar com a secretaria.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sugestoes-titulo">Sugestões de perguntas:</div>', unsafe_allow_html=True)

    for linha_idx in range(0, len(SUGESTOES_RAPIDAS), 3):
        cols = st.columns([1.35, 1, 1.25], gap="small")
        for col_idx, texto_sug in enumerate(SUGESTOES_RAPIDAS[linha_idx:linha_idx + 3]):
            with cols[col_idx]:
                if st.button(texto_sug, key=f"sug_{linha_idx + col_idx}", use_container_width=True, type="secondary"):
                    sugestao_clicada = texto_sug
else:
    # --- ESTADO 2: CONVERSA ATIVA ---
    st.markdown(f"""
    <div class="chat-active-header">
        <h2>{conversa_ativa['titulo']}</h2>
    </div>
    """, unsafe_allow_html=True)

    for msg in mensagens_atuais:
        avatar = AVATAR_ASSISTENTE if msg["role"] == "assistant" else None
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

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

    with st.chat_message("assistant", avatar=AVATAR_ASSISTENTE):
        resposta_rapida = verificar_mensagem(pergunta)
        resposta_cache = buscar_no_cache(pergunta) if not resposta_rapida else None

        # 1. Resposta imediata por saudação
        if resposta_rapida:
            st.markdown(resposta_rapida)
            resposta_completa = resposta_rapida
            registrar_telemetria(pergunta, "Saudacao", resposta_completa)

        # 2. Resposta imediata via Cache
        elif resposta_cache and len(mensagens_atuais) <= 1:
            st.markdown(resposta_cache)
            resposta_completa = resposta_cache
            registrar_telemetria(pergunta, "Cache", resposta_completa)
            with st.expander("Ver detalhes técnicos (Modo Debug)"):
                st.caption("Origem: Cache local instantâneo (0 tokens consumidos)")

        # 3. Fluxo completo RAG + LLM
        else:
            consulta_busca = pergunta
            if len(mensagens_atuais) >= 3:
                pergunta_anterior = mensagens_atuais[-3]["content"]
                consulta_busca = f"{pergunta_anterior} - {pergunta}"

            docs_encontrados = None
            for tentativa in range(2):
                try:
                    docs_encontrados = vector_store.similarity_search(consulta_busca, k=3)
                    break
                except Exception:
                    if tentativa == 0:
                        continue
                    st.warning("A conexão com o servidor de busca oscilou. Por favor, envie sua pergunta novamente.")
                    st.stop()

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
                except Exception:
                    resposta_completa = "A conexão com o servidor oscilou durante a resposta. Por favor, tente novamente."
                    st.warning(resposta_completa)

                if len(mensagens_atuais) <= 1:
                    salvar_no_cache(pergunta, resposta_completa)

                registrar_telemetria(pergunta, modelo_utilizado, resposta_completa)

                with st.expander("Ver trechos consultados (Modo Debug)"):
                    st.caption(f"Modelo utilizado nesta resposta: {modelo_utilizado}")
                    for i, doc in enumerate(docs_encontrados, 1):
                        st.markdown(f"**Trecho {i} ({doc.metadata.get('fonte')}):**")
                        st.text(doc.page_content)
            else:
                resposta_completa = "Desculpe, todos os servidores de atendimento estão temporariamente sobrecarregados. Por favor, tente novamente em alguns instantes."
                st.warning(resposta_completa)
                registrar_telemetria(pergunta, "Indisponivel", resposta_completa)

    mensagens_atuais.append({"role": "assistant", "content": resposta_completa})
    st.rerun()