import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
APP_SCRIPT = SCRIPTS_DIR / "app.py"
CRIAR_BANCO_SCRIPT = SCRIPTS_DIR / "criar_banco.py"
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"

# ==============================================================================
# EDITE AQUI AS INFORMAÇÕES SOBRE O PROJETO (EXIBIDAS NA OPÇÃO 7 DO MENU)
# ==============================================================================
INFORMACOES_PROJETO = """
Projeto: Assistente Virtual Institucional - UFCA
Instituição: Universidade Federal do Cariri (UFCA)
Autor(es): [Insira seu nome aqui]
Orientação / Setor: [Insira o nome do orientador ou setor aqui]
Ano: 2026

Descrição:
Protótipo de assistente virtual baseado em Inteligência Artificial com arquitetura
RAG (Retrieval-Augmented Generation), suporte híbrido (Google Gemini na nuvem e
Ollama local), cache inteligente de respostas frequentes e telemetria anônima
em conformidade com a LGPD.
"""
# ==============================================================================


def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def listar_modelos_ollama():
    """Consulta o terminal do Ollama para listar apenas os modelos de chat instalados."""
    try:
        resultado = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        linhas = resultado.stdout.strip().splitlines()
        modelos = []
        for linha in linhas[1:]:
            partes = linha.split()
            if partes:
                nome = partes[0]
                if "embed" not in nome.lower():
                    modelos.append(nome)
        return modelos
    except Exception:
        return []


def instalar_requerimentos():
    """Instala ou atualiza as bibliotecas listadas no requirements.txt."""
    limpar_tela()
    print("=======================================================")
    print("         INSTALAÇÃO DE DEPENDÊNCIAS DO PROJETO         ")
    print("=======================================================\n")

    if not REQUIREMENTS_FILE.exists():
        print(f"[Erro] Arquivo '{REQUIREMENTS_FILE}' não encontrado.")
        input("\nPressione Enter para voltar ao menu...")
        return

    print("Instalando pacotes via pip (aguarde)...\n")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
            check=True
        )
        print("\n[Sucesso] Todas as dependências foram instaladas/atualizadas!")
    except subprocess.CalledProcessError as e:
        print(f"\n[Erro] Ocorreu uma falha durante a instalação (código {e.returncode}).")

    input("\nPressione Enter para voltar ao menu...")


def exibir_informacoes_projeto():
    """Exibe as informações institucionais e técnicas definidas no topo do script."""
    limpar_tela()
    print("=======================================================")
    print("                 INFORMAÇÕES DO PROJETO                ")
    print("=======================================================")
    print(INFORMACOES_PROJETO.strip())
    print("=======================================================")
    input("\nPressione Enter para voltar ao menu...")


def executar_streamlit(ambiente_customizado):
    if not APP_SCRIPT.exists():
        print(f"\n[Erro] Arquivo principal não encontrado em: {APP_SCRIPT}")
        input("Pressione Enter para voltar ao menu...")
        return

    print("\n" + "=" * 55)
    print("Servidor do Assistente UFCA iniciado!")
    print("Para encerrar o servidor e voltar a este menu,")
    print("clique nesta janela e pressione:  Ctrl + C")
    print("=" * 55 + "\n")

    processo = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(APP_SCRIPT)],
        cwd=str(BASE_DIR),
        env=ambiente_customizado
    )

    try:
        processo.wait()
    except KeyboardInterrupt:
        print("\nEncerrando o servidor Streamlit e retornando ao menu...")
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()


def menu_principal():
    chave_api_sessao = os.environ.get("GOOGLE_API_KEY", "")

    while True:
        limpar_tela()
        status_chave = f"Configurada (termina em ...{chave_api_sessao[-4:]})" if len(chave_api_sessao) >= 4 else "Nao configurada"

        print("=======================================================")
        print("      PAINEL DE CONTROLE - ASSISTENTE VIRTUAL UFCA     ")
        print("=======================================================")
        print(f"Chave API Gemini na sessao: {status_chave}")
        print("-------------------------------------------------------")
        print("1. Iniciar Chat - Modo Nuvem (Google Gemini)")
        print("2. Iniciar Chat - Modo Local (Escolher modelo Ollama)")
        print("3. Atualizar Banco Vetorial (criar_banco.py)")
        print("4. Definir / Alterar Chave API do Gemini nesta sessao")
        print("5. Remover Chave API desta sessao")
        print("6. Instalar / Atualizar Requerimentos (requirements.txt)")
        print("7. Informacoes sobre o Projeto")
        print("0. Sair")
        print("-------------------------------------------------------")

        opcao = input("Escolha uma opcao: ").strip()

        if opcao == "1":
            if not chave_api_sessao:
                print("\n[Aviso] Nenhuma chave do Gemini foi definida nesta sessao.")
                nova_chave = input("Cole sua GOOGLE_API_KEY agora (ou Enter para voltar): ").strip()
                if not nova_chave:
                    continue
                chave_api_sessao = nova_chave

            env = os.environ.copy()
            env["GOOGLE_API_KEY"] = chave_api_sessao
            env["MODO_EXECUCAO"] = "nuvem"
            executar_streamlit(env)

        elif opcao == "2":
            modelos = listar_modelos_ollama()
            print("\nModelos locais disponiveis no seu Ollama:")
            if modelos:
                for idx, mod in enumerate(modelos, 1):
                    print(f"  {idx}. {mod}")
                escolha = input(f"\nEscolha o numero do modelo (ou Enter para '{modelos[0]}'): ").strip()
                if escolha.isdigit() and 1 <= int(escolha) <= len(modelos):
                    modelo_escolhido = modelos[int(escolha) - 1]
                elif escolha == "":
                    modelo_escolhido = modelos[0]
                else:
                    modelo_escolhido = escolha
            else:
                print("  Nao foi possivel listar automaticamente os modelos do Ollama.")
                modelo_escolhido = input("Digite o nome do modelo (ex: llama3.2:3b): ").strip() or "llama3.2:3b"

            print(f"\nIniciando com modelo local: {modelo_escolhido}...")
            env = os.environ.copy()
            env.pop("GOOGLE_API_KEY", None)
            env["MODO_EXECUCAO"] = "local"
            env["MODELO_OLLAMA_ESCOLHIDO"] = modelo_escolhido
            executar_streamlit(env)

        elif opcao == "3":
            print("\nQual indice vetorial deseja gerar?")
            print("  1. Nuvem Gemini (3072 dimensoes)")
            print("  2. Local Ollama (768 dimensoes - nomic-embed-text)")
            sub = input("Escolha (1 ou 2): ").strip()

            env = os.environ.copy()
            modo_arg = "ollama"
            if sub == "1":
                if not chave_api_sessao:
                    print("\n[Erro] Defina a GOOGLE_API_KEY na opcao 4 primeiro.")
                    input("\nPressione Enter para voltar ao menu...")
                    continue
                env["GOOGLE_API_KEY"] = chave_api_sessao
                modo_arg = "gemini"
            else:
                env.pop("GOOGLE_API_KEY", None)

            print("\nExecutando criar_banco.py...")
            subprocess.run(
                [sys.executable, str(CRIAR_BANCO_SCRIPT), modo_arg],
                cwd=str(BASE_DIR),
                env=env
            )
            input("\nPressione Enter para voltar ao menu...")

        elif opcao == "4":
            nova = input("\nCole sua GOOGLE_API_KEY: ").strip()
            if nova:
                chave_api_sessao = nova
                print("Chave salva na memoria desta janela!")
            input("Pressione Enter para continuar...")

        elif opcao == "5":
            chave_api_sessao = ""
            os.environ.pop("GOOGLE_API_KEY", None)
            print("\nChave removida da sessao.")
            input("Pressione Enter para continuar...")

        elif opcao == "6":
            instalar_requerimentos()

        elif opcao == "7":
            exibir_informacoes_projeto()

        elif opcao == "0":
            print("\nEncerrando painel...")
            break


if __name__ == "__main__":
    menu_principal()