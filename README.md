Estrutura do projeto:

chatbot_ufca/
├── index.html                  <-- Homepage do GitHub Pages + Widget do Chat
├── app.py                      <-- Seu código Streamlit
├── interface_ui.py             <-- Módulo visual
├── gerenciador_llm.py          <-- Gerenciador Gemini/Ollama
├── metricas_cache.py           <-- Cache e telemetria
├── banco_vetorial.json         <-- Base vetorial gerada
├── respostas_rapidas.json      <-- Saudações e agradecimentos
├── requirements.txt            <-- Dependências Python
├── assets/                     <-- Imagens (brasao_ufca.png, logo_chatbot_ufca_beta.png, etc.)
└── templates/
    ├── topbar.html             <-- Barra superior do chat
    ├── estilo.css
    ├── footer.html
    ├── hero.html
    ├── sidebar_brand.html
    └── sidebar_participe.html