import os
import re
import csv
import json
import unicodedata
from datetime import datetime

PASTA_LOGS = "logs"
ARQUIVO_CACHE = "cache_respostas.json"
ARQUIVO_TELEMETRIA = os.path.join(PASTA_LOGS, "telemetria_ufca.csv")
ARQUIVO_BANCO = "banco_vetorial.json"


def _normalizar_pergunta(texto):
    """Remove acentos, pontuacao e converte para minusculas para encontrar perguntas equivalentes."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _obter_versao_banco():
    """Retorna o timestamp de modificacao do banco vetorial para invalidar o cache se o banco mudar."""
    if os.path.exists(ARQUIVO_BANCO):
        return str(int(os.path.getmtime(ARQUIVO_BANCO)))
    return "0"


def buscar_no_cache(pergunta):
    """Retorna a resposta em cache se a pergunta ja existir para a versao atual do banco."""
    if not os.path.exists(ARQUIVO_CACHE):
        return None

    try:
        with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
            dados = json.load(f)

        versao_atual = _obter_versao_banco()
        if dados.get("versao_banco") != versao_atual:
            return None

        chave = _normalizar_pergunta(pergunta)
        return dados.get("respostas", {}).get(chave)
    except Exception:
        return None


def salvar_no_cache(pergunta, resposta):
    """Salva uma resposta valida no cache local (ignora respostas de erro ou lacunas)."""
    if not resposta or len(resposta.strip()) < 15:
        return

    termos_ignorar = [
        "servidores de atendimento estão temporariamente",
        "não possui essa informação no momento",
        "não possuo essa informação no momento"
    ]
    if any(t in resposta.lower() for t in termos_ignorar):
        return

    versao_atual = _obter_versao_banco()
    dados = {"versao_banco": versao_atual, "respostas": {}}

    if os.path.exists(ARQUIVO_CACHE):
        try:
            with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
                existente = json.load(f)
                if existente.get("versao_banco") == versao_atual:
                    dados = existente
        except Exception:
            pass

    chave = _normalizar_pergunta(pergunta)
    dados["respostas"][chave] = resposta

    try:
        with open(ARQUIVO_CACHE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Aviso Cache] Nao foi possivel salvar cache: {e}")


def registrar_telemetria(pergunta, origem, resposta):
    """
    Registra metricas anonimas em CSV dentro da pasta logs/ para identificar
    duvidas frequentes e lacunas na base (conformidade LGPD).
    """
    os.makedirs(PASTA_LOGS, exist_ok=True)
    arquivo_novo = not os.path.exists(ARQUIVO_TELEMETRIA)

    indicadores_lacuna = [
        "não possui essa informação",
        "não possuo essa informação",
        "não consta no contexto",
        "procurar a secretaria do curso"
    ]
    if any(ind in resposta.lower() for ind in indicadores_lacuna):
        status = "Lacuna_Conhecimento"
    elif "temporariamente sobrecarregados" in resposta.lower():
        status = "Erro_Servidor"
    else:
        status = "Respondida"

    try:
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
        print(f"[Aviso Telemetria] Nao foi possivel gravar log: {e}")


def obter_resumo_telemetria():
    """Le o CSV de telemetria para exibir metricas rapidas no painel administrativo."""
    if not os.path.exists(ARQUIVO_TELEMETRIA):
        return None

    try:
        total = 0
        lacunas = 0
        via_cache = 0
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