from pathlib import Path

# Raiz do projeto (um nível acima de scripts/)
BASE_DIR = Path(__file__).resolve().parent.parent

SCRIPTS_DIR = BASE_DIR / "scripts"
TEMPLATES_DIR = SCRIPTS_DIR / "templates"
DATABASE_DIR = BASE_DIR / "database"
DOCUMENTOS_DIR = DATABASE_DIR / "internal_conheciments"
TELEMETRY_DIR = BASE_DIR / "telemetry"
ASSETS_DIR = BASE_DIR / "assets"

# Arquivos de dados, cache e telemetria
ARQUIVO_BANCO_GEMINI = DATABASE_DIR / "banco_vetorial.json"
ARQUIVO_BANCO_OLLAMA = DATABASE_DIR / "banco_vetorial_ollama.json"
ARQUIVO_RESPOSTAS_RAPIDAS = DATABASE_DIR / "respostas_rapidas.json"
ARQUIVO_CACHE = DATABASE_DIR / "cache_respostas.json"
ARQUIVO_TELEMETRIA = TELEMETRY_DIR / "telemetria_ufca.csv"
ARQUIVO_REQUIREMENTS = BASE_DIR / "requirements.txt"
ARQUIVO_SECRETS = BASE_DIR / ".streamlit" / "secrets.toml"