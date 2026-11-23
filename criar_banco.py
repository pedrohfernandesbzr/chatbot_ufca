import os
import tomllib
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore

# Configurações de caminhos e modelos
PASTA_DOCUMENTOS = "documentos"
ARQUIVO_BANCO = "banco_vetorial.json"
ARQUIVO_CACHE = "cache_respostas.json"
MODELO_OLLAMA_EMBEDDING = "nomic-embed-text"
MODELO_GEMINI_EMBEDDING = "models/gemini-embedding-001"


def obter_chave_gemini():
    # 1. Tenta ler da variável de ambiente do terminal
    chave = os.environ.get("GOOGLE_API_KEY")
    if chave and chave.strip() != "":
        return chave.strip()

    # 2. Tenta ler do arquivo .streamlit/secrets.toml (se existir localmente)
    caminho_secrets = os.path.join(".streamlit", "secrets.toml")
    if os.path.exists(caminho_secrets):
        with open(caminho_secrets, "rb") as f:
            secrets = tomllib.load(f)
            return secrets.get("GOOGLE_API_KEY")

    return None


def criar_base_conhecimento():
    if not os.path.exists(PASTA_DOCUMENTOS):
        print(f"Erro: A pasta '{PASTA_DOCUMENTOS}' não existe.")
        return

    arquivos_md = [f for f in os.listdir(PASTA_DOCUMENTOS) if f.endswith(".md")]
    if not arquivos_md:
        print(f"Nenhum arquivo .md encontrado na pasta '{PASTA_DOCUMENTOS}'. Adicione seus arquivos lá primeiro.")
        return

    print(f"Encontrados {len(arquivos_md)} arquivo(s) Markdown: {arquivos_md}")

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

    for nome_arquivo in arquivos_md:
        caminho_completo = os.path.join(PASTA_DOCUMENTOS, nome_arquivo)
        with open(caminho_completo, "r", encoding="utf-8") as f:
            conteudo = f.read()

        chunks_md = markdown_splitter.split_text(conteudo)
        
        for chunk in chunks_md:
            chunk.metadata["fonte"] = nome_arquivo

        chunks_finais = text_splitter.split_documents(chunks_md)
        todos_chunks.extend(chunks_finais)

    print(f"Total de blocos de conhecimento gerados: {len(todos_chunks)}")

    # Decide qual motor de embeddings usar
    chave_gemini = obter_chave_gemini()

    if chave_gemini:
        print("Chave do Gemini detectada. Gerando vetores na nuvem (Google Embeddings)...")
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model=MODELO_GEMINI_EMBEDDING,
            google_api_key=chave_gemini
        )
    else:
        print("Nenhuma chave do Gemini detectada. Gerando vetores localmente com o Ollama...")
        embeddings = OllamaEmbeddings(model=MODELO_OLLAMA_EMBEDDING)
    
    vector_store = InMemoryVectorStore.from_documents(
        documents=todos_chunks,
        embedding=embeddings
    )
    vector_store.dump(ARQUIVO_BANCO)

    # Remove o cache antigo para evitar respostas desatualizadas após atualizar os documentos
    if os.path.exists(ARQUIVO_CACHE):
        os.remove(ARQUIVO_CACHE)
        print("Cache de respostas antigo removido para sincronizar com a nova base.")

    print(f"Sucesso! Banco vetorial salvo no arquivo '{ARQUIVO_BANCO}'.")


if __name__ == "__main__":
    criar_base_conhecimento()