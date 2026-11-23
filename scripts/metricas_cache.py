import re
import csv
import json
import unicodedata
from datetime import datetime
from filelock import FileLock

from config import (
    TELEMETRY_DIR,
    ARQUIVO_CACHE,
    ARQUIVO_TELEMETRIA,
    ARQUIVO_BANCO_GEMINI,
    ARQUIVO_BANCO_OLLAMA,
)

LOCK_CACHE = FileLock(f"{ARQUIVO_CACHE}.lock", timeout=5)
LOCK_TELEMETRIA = FileLock(f"{ARQUIVO_TELEMETRIA}.lock", timeout=5)


def normalizar_texto(texto: str) -> str:
    """Remove acentos, pontuação e espaços extras, convertendo para minúsculas."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _obter_versao_bancos() -> str:
    """Combina os timestamps dos bancos vetoriais ativos para invalidar cache desatualizado."""
    ts_gemini = int(ARQUIVO_BANCO_GEMINI.stat().st_mtime) if ARQUIVO_BANCO_GEMINI.exists() else 0
    ts_ollama = int(ARQUIVO_BANCO_OLLAMA.stat().st_mtime) if ARQUIVO_BANCO_OLLAMA.exists() else 0
    return f"{ts_gemini}_{ts_ollama}"


def buscar_no_cache(pergunta: str):
    """Retorna a resposta em cache se a pergunta já existir para a versão atual dos bancos."""
    if not ARQUIVO_CACHE.exists():
        return None

    try:
        with LOCK_CACHE:
            with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
                dados = json.load(f)

        versao_atual = _obter_versao_bancos()
        if dados.get("versao_banco") != versao_atual:
            return None

        chave = normalizar_texto(pergunta)
        return dados.get("respostas", {}).get(chave)
    except Exception:
        return None


def salvar_no_cache(pergunta: str, resposta: str):
    """Salva uma resposta válida no cache local (ignora respostas de erro ou lacunas)."""
    if not resposta or len(resposta.strip()) < 15:
        return

    termos_ignorar = [
        "servidores de atendimento estão temporariamente",
        "não possui essa informação no momento",
        "não possuo essa informação no momento",
        "a conexão oscilou",
        "ocorreu uma falha inesperada",
        "não foi possível consultar a base"
    ]
    if any(t in resposta.lower() for t in termos_ignorar):
        return

    versao_atual = _obter_versao_bancos()
    chave = normalizar_texto(pergunta)

    try:
        ARQUIVO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with LOCK_CACHE:
            dados = {"versao_banco": versao_atual, "respostas": {}}
            if ARQUIVO_CACHE.exists():
                try:
                    with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
                        existente = json.load(f)
                        if existente.get("versao_banco") == versao_atual:
                            dados = existente
                except Exception:
                    pass

            dados["respostas"][chave] = resposta
            with open(ARQUIVO_CACHE, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Aviso Cache] Não foi possível salvar cache: {e}")


def registrar_telemetria(pergunta: str, origem: str, resposta: str):
    """
    Registra métricas anônimas em CSV dentro de telemetry/ para identificar
    dúvidas frequentes, encaminhamentos e lacunas na base (conformidade LGPD).
    """
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    resp_lower = resposta.lower()

    indicadores_lacuna = [
        "não possui essa informação",
        "não possuo essa informação",
        "não consta no contexto",
        "não encontrei essa informação"
    ]
    indicadores_erro = [
        "temporariamente indisponíveis",
        "temporariamente sobrecarregados",
        "a conexão oscilou",
        "ocorreu uma falha inesperada",
        "não foi possível consultar a base"
    ]
    indicadores_encaminhamento = [
        "secretaria do curso",
        "pró-reitoria",
        "prograd",
        "prae",
        "coordenação do curso"
    ]

    if any(ind in resp_lower for ind in indicadores_erro) or origem in ("Indisponivel", "Erro_Busca", "Falha_Stream"):
        status = "Erro_Servidor"
    elif any(ind in resp_lower for ind in indicadores_lacuna):
        status = "Lacuna_Conhecimento"
    elif any(ind in resp_lower for ind in indicadores_encaminhamento):
        status = "Encaminhamento_Setor"
    else:
        status = "Respondida"

    try:
        with LOCK_TELEMETRIA:
            arquivo_novo = not ARQUIVO_TELEMETRIA.exists()
            with open(ARQUIVO_TELEMETRIA, "a", newline="", encoding="utf-8-sig") as f:
                escritor = csv.writer(f, delimiter=";")
                if arquivo_novo:
                    escritor.writerow(["Data_Hora", "Pergunta", "Origem_Resposta", "Status"])

                escritor.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    pergunta.replace("\n", " ").strip(),
                    origem,
                    status
                ])
    except Exception as e:
        print(f"[Aviso Telemetria] Não foi possível gravar log: {e}")


def obter_resumo_telemetria():
    """Lê o CSV de telemetria para exibir métricas rápidas no painel lateral."""
    if not ARQUIVO_TELEMETRIA.exists():
        return None

    try:
        total = 0
        lacunas = 0
        via_cache = 0
        with LOCK_TELEMETRIA:
            with open(ARQUIVO_TELEMETRIA, "r", encoding="utf-8-sig") as f:
                leitor = csv.DictReader(f, delimiter=";")
                for linha in leitor:
                    total += 1
                    if linha.get("Status") == "Lacuna_Conhecimento":
                        lacunas += 1
                    if linha.get("Origem_Resposta") == "Cache":
                        via_cache += 1

        return {"total": total, "lacunas": lacunas, "via_cache": via_cache}
    except Exception:
        return None