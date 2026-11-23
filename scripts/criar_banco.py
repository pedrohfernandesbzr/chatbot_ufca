import os
import sys
import tomllib
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore

from config import (
    DOCUMENTOS_DIR,
    ARQUIVO_BANCO_GEMINI,
    ARQUIVO_BANCO_OLLAMA,
    ARQUIVO_CACHE,
    ARQUIVO_SECRETS,
)

MODELO_OLLAMA_EMBEDDING = "nomic-embed-text"
MODELO_GEMINI_EMBEDDING = "models/gemini-embedding-001"


def obter_chave_gemini():
    chave = os.environ.get("GOOGLE_API_KEY")
    if chave and chave.strip():
        return chave.strip()

    if ARQUIVO_SECRETS.exists():
        with open(ARQUIVO_SECRETS, "rb") as f:
            secrets = tomllib.load(f)
            return secrets.get("GOOGLE_API_KEY")

    return None


def carregar_e_dividir_documentos():
    if not DOCUMENTOS_DIR.exists():
        raise FileNotFoundError(f"A pasta '{DOCUMENTOS_DIR}' não existe.")

    arquivos_md = sorted([f for f in DOCUMENTOS_DIR.iterdir() if f.suffix == ".md"])
    if not arquivos_md:
        raise FileNotFoundError(f"Nenhum arquivo .md encontrado em '{DOCUMENTOS_DIR}'.")

    headers_to_split_on = [
        ("#", "Titulo_Principal"),
        ("##", "Secao"),
        ("###", "Subsecao"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False
    )
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    todos_chunks = []
    for caminho_arquivo in arquivos_md:
        conteudo = caminho_arquivo.read_text(encoding="utf-8")
        chunks_md = markdown_splitter.split_text(conteudo)
        for chunk in chunks_md:
            chunk.metadata["fonte"] = caminho_arquivo.name
        todos_chunks.extend(text_splitter.split_documents(chunks_md))

    return todos_chunks


def criar_base_conhecimento(modo_forcado=None):
    """
    modo_forcado: 'gemini', 'ollama' ou None (detecta pela presença da chave API).
    """
    todos_chunks = carregar_e_dividir_documentos()
    print(f"Total de blocos de conhecimento gerados: {len(todos_chunks)}")

    chave_gemini = obter_chave_gemini()
    usar_gemini = (modo_forcado == "gemini") or (modo_forcado is None and bool(chave_gemini))

    if usar_gemini:
        if not chave_gemini:
            raise ValueError("Chave GOOGLE_API_KEY necessária para gerar o banco Gemini.")
        print("Gerando vetores na nuvem (Google Embeddings - 3072d)...")
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model=MODELO_GEMINI_EMBEDDING,
            google_api_key=chave_gemini
        )
        arquivo_destino = ARQUIVO_BANCO_GEMINI
    else:
        print(f"Gerando vetores localmente com Ollama ({MODELO_OLLAMA_EMBEDDING} - 768d)...")
        embeddings = OllamaEmbeddings(model=MODELO_OLLAMA_EMBEDDING)
        arquivo_destino = ARQUIVO_BANCO_OLLAMA

    vector_store = InMemoryVectorStore.from_documents(
        documents=todos_chunks,
        embedding=embeddings
    )
    arquivo_destino.parent.mkdir(parents=True, exist_ok=True)
    vector_store.dump(str(arquivo_destino))

    if ARQUIVO_CACHE.exists():
        ARQUIVO_CACHE.unlink()
        print("Cache de respostas antigo removido para sincronizar com a nova base.")

    print(f"Sucesso! Banco vetorial salvo em: '{arquivo_destino}'.")
    return str(arquivo_destino)


if __name__ == "__main__":
    modo_arg = sys.argv[1].lower() if len(sys.argv) > 1 else None
    criar_base_conhecimento(modo_forcado=modo_arg)