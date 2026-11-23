import os
import base64
import streamlit as st
import streamlit.components.v1 as components

PASTA_ASSETS = "assets"
PASTA_TEMPLATES = "templates"


def carregar_asset_base64(nome_arquivo):
    caminho = os.path.join(PASTA_ASSETS, nome_arquivo)
    if os.path.exists(caminho):
        with open(caminho, "rb") as f:
            ext = nome_arquivo.split(".")[-1].lower()
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    return ""


def _ler_template(nome_arquivo):
    caminho = os.path.join(PASTA_TEMPLATES, nome_arquivo)
    with open(caminho, "r", encoding="utf-8") as f:
        return f.read()


def obter_caminhos_icones():
    favicon = os.path.join(PASTA_ASSETS, "logo_chatbot_ufca_beta.png")
    avatar = os.path.join(PASTA_ASSETS, "icone_sms_chatbot_ufca_beta.png")
    return {
        "favicon": favicon if os.path.exists(favicon) else None,
        "avatar_assistente": avatar if os.path.exists(avatar) else None,
    }


def injetar_estilos():
    css = _ler_template("estilo.css")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def renderizar_topbar():
    brasao_uri = carregar_asset_base64("brasao_ufca.png")
    img_brasao = f'<img src="{brasao_uri}" alt="Brasão UFCA">' if brasao_uri else ""
    html = _ler_template("topbar.html").format(img_brasao=img_brasao)
    st.markdown(html, unsafe_allow_html=True)


def renderizar_rodape():
    github_uri = carregar_asset_base64("github_icone.png")
    version_uri = carregar_asset_base64("version_icone.jpg")

    img_github = f'<img src="{github_uri}" alt="GitHub">' if github_uri else ""
    img_version = f'<img src="{version_uri}" alt="Versão">' if version_uri else ""

    html = _ler_template("footer.html").format(
        img_github=img_github,
        img_version=img_version
    )
    st.markdown(html, unsafe_allow_html=True)

    components.html("""
    <script>
    (function() {
        const doc = window.parent.document;
        function alinharRodape() {
            const footer = doc.getElementById('ufca-footer');
            const mainArea = doc.querySelector('section[data-testid="stMain"]') || doc.querySelector('.main');
            if (footer && mainArea) {
                const rect = mainArea.getBoundingClientRect();
                footer.style.left = rect.left + 'px';
                footer.style.width = rect.width + 'px';
            }
        }
        alinharRodape();
        window.parent.addEventListener('resize', alinharRodape);
        const observer = new MutationObserver(alinharRodape);
        observer.observe(doc.body, { attributes: true, subtree: true, attributeFilter: ['aria-expanded', 'style', 'class'] });
        setInterval(alinharRodape, 250);
    })();
    </script>
    """, height=0, width=0)


def renderizar_sidebar_brand():
    logo_uri = carregar_asset_base64("logo_chatbot_ufca_beta.png")
    img_sidebar = f'<img src="{logo_uri}" alt="Logo Chatbot UFCA">' if logo_uri else ""
    html = _ler_template("sidebar_brand.html").format(img_sidebar=img_sidebar)
    st.markdown(html, unsafe_allow_html=True)


def renderizar_sidebar_participe():
    html = _ler_template("sidebar_participe.html")
    st.markdown(html, unsafe_allow_html=True)


def renderizar_hero():
    icone_uri = carregar_asset_base64("icone_sms_chatbot_ufca_beta.png") or carregar_asset_base64("logo_chatbot_ufca_beta.png")
    img_hero = (
        f'<div class="hero-avatar-circle"><img src="{icone_uri}" alt="Assistente Virtual UFCA"></div>'
        if icone_uri else ""
    )
    html = _ler_template("hero.html").format(img_hero=img_hero)
    st.markdown(html, unsafe_allow_html=True)