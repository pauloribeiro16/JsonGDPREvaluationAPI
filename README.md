# Guia de Instalação (Windows): Mini Document PII Analyzer

Este guia detalha os passos para configurar o ambiente necessário no Windows para executar o projeto `FileEvaluationAPIgenerateSimple` clonado do GitHub.

## Sumário

1.  [Instalar Git](#1-instalar-git)
2.  [Clonar o Repositório do Projeto](#2-clonar-o-repositório-do-projeto)
3.  [Instalar Python 3.11.12 e Pip](#3-instalar-python-31112-e-pip)
4.  [Instalar Bibliotecas Python](#4-instalar-bibliotecas-python)
5.  [Instalar Ollama](#5-instalar-ollama)
6.  [Descarregar Modelos Ollama para Teste](#6-descarregar-modelos-ollama-para-teste)
7.  [Estrutura de Pastas do Projeto (Confirmar)](#7-estrutura-de-pastas-do-projeto-confirmar)
8.  [Executar o Script](#8-executar-o-script)

---

## 1. Instalar Git

Git é um sistema de controlo de versões necessário para clonar o repositório do projeto.

1.  **Descarregar Git para Windows:**
    *   Vá ao site oficial do Git: [git-scm.com/download/win](https://git-scm.com/download/win)
    *   O download do instalador apropriado (geralmente 64-bit) deverá começar automaticamente. Se não, clique no link de download.
2.  **Executar o Instalador do Git:**
    *   Abra o ficheiro `.exe` que descarregou.
    *   Siga as instruções do instalador. Na maioria dos casos, as opções padrão são adequadas. Algumas sugestões:
        *   **"Select Components"**: Pode deixar como está.
        *   **"Choosing the default editor used by Git"**: Pode escolher "Use Visual Studio Code as Git's default editor" (se o tiver instalado e preferir) ou "Use Vim (the ubiquitous text editor) as Git's default editor" (que é o padrão e funciona bem para commits). Para utilizadores menos experientes, Notepad++ ou outro editor gráfico pode ser mais fácil se estiver listado. Para este projeto, o editor padrão do Git não será muito usado.
        *   **"Adjusting the name of the initial branch in new repositories"**: "Let Git decide" ou "Override the default branch name..." (ex: `main`) são boas opções.
        *   **"Adjusting your PATH environment"**: A opção recomendada "Git from the command line and also from 3rd-party software" é geralmente a melhor.
        *   **"Choosing HTTPS transport backend"**: "Use the OpenSSL library" é o padrão e funciona bem.
        *   **"Configuring the line ending conversions"**: "Checkout Windows-style, commit Unix-style line endings" é uma boa opção padrão para Windows.
    *   Continue a clicar em "Next" e depois "Install".
3.  **Verificar Instalação do Git:**
    *   Após a instalação, abra uma **nova** Linha de Comandos (CMD) ou PowerShell.
    *   Digite o seguinte comando e pressione Enter:
        ```cmd
        git --version
        ```
        Deverá ver a versão do Git instalada (ex: `git version 2.xx.x.windows.x`).

---

## 2. Clonar o Repositório do Projeto

Com o Git instalado, pode clonar o repositório do projeto a partir do GitHub.

1.  **Abrir Git Bash, CMD ou PowerShell:**
    *   O Git Bash (que é instalado com o Git) é uma boa opção, mas CMD ou PowerShell também funcionam.
2.  **Navegar para a Pasta Desejada:**
    *   Use o comando `cd` para navegar até ao diretório onde quer guardar a pasta do projeto. Por exemplo, para criar na sua pasta "Documentos":
        ```cmd
        cd C:\Users\SeuUsuario\Documents
        ```
        (Substitua `SeuUsuario` pelo seu nome de utilizador no Windows).
3.  **Clonar o Repositório:**
    *   Execute o seguinte comando:
        ```cmd
        git clone https://github.com/pauloribeiro16/FileEvaluationAPIgenerateSimple.git
        ```
    *   Isto criará uma pasta chamada `FileEvaluationAPIgenerateSimple` no diretório atual, contendo todos os ficheiros do projeto.
4.  **Entrar na Pasta do Projeto:**
    ```cmd
    cd FileEvaluationAPIgenerateSimple
    ```

---

## 3. Instalar Python 3.11.12 e Pip

`pip` (o gestor de pacotes do Python) vem incluído com esta instalação do Python. *Se já tem uma versão compatível do Python 3 (ex: 3.9+) e o pip configurados e adicionados ao PATH, pode potencialmente saltar este passo.*

1.  **Descarregar Python 3.11.12:**
    *   Vá para a página de download específica do Python 3.11.12: [https://www.python.org/downloads/release/python-31112/](https://www.python.org/downloads/release/python-31112/)
    *   Navegue até à secção "Files" no final da página.
    *   Procure e descarregue o **"Windows installer (64-bit)"**.
2.  **Executar o Instalador:**
    *   Abra o ficheiro `.exe` que descarregou.
    *   **Muito Importante:** No primeiro ecrã do instalador, marque a caixa que diz **"Add Python 3.11 to PATH"**.
    *   Clique em "Install Now" para a instalação padrão.
    *   Aguarde a conclusão da instalação.
3.  **Verificar Instalação:**
    *   Abra uma **nova** Linha de Comandos (CMD) ou PowerShell.
    *   Digite `python --version` e pressione Enter. Deverá ver `Python 3.11.12`.
    *   Digite `pip --version` e pressione Enter. Deverá ver a versão do pip.

---

## 4. Instalar Bibliotecas Python

Com o Python e `pip` configurados, e já dentro da pasta do projeto `FileEvaluationAPIgenerateSimple` (do passo 2.4), instale as bibliotecas Python necessárias. Na Linha de Comandos (CMD ou PowerShell), execute:

```cmd
pip install requests beaupy psutil wmi
```

Detalhes das bibliotecas:
*   **`requests`**: Para fazer pedidos HTTP à API do Ollama.
*   **`beaupy`**: Para criar interfaces de seleção interativas na linha de comandos.
*   **`psutil`**: Para obter informações do sistema (CPU, RAM, disco, SO).
*   **`wmi`**: Para obter informações mais detalhadas do sistema no Windows (GPU, tipo de disco).

---

## 5. Instalar Ollama

Ollama permite executar modelos de linguagem grandes localmente.

1.  **Visite o Site Oficial:**
    *   [ollama.com](https://ollama.com/)
2.  **Descarregar e Instalar para Windows:**
    *   Na página inicial do Ollama, clique no botão de download para Windows.
    *   Execute o ficheiro `.exe` do instalador do Ollama.
    *   Siga as instruções de instalação. O Ollama será configurado para iniciar automaticamente com o Windows e correr em segundo plano.
3.  **Verificar Instalação (após Ollama estar a correr):**
    *   O ícone do Ollama deverá aparecer na bandeja do sistema.
    *   Abra uma nova Linha de Comandos/PowerShell e digite:
        ```cmd
        ollama list
        ```
    *   A lista estará vazia se ainda não tiver descarregado modelos.

---

## 6. Descarregar Modelos Ollama para Teste

Abra a Linha de Comandos/PowerShell para descarregar os modelos.

1.  **`phi3:mini` (ou `phi4-mini-reasoning` se for esse o nome exato que pretende usar e estiver disponível)**
    *   **Nota:** O nome `phi4-mini-reasoning` não é um modelo padrão na biblioteca Ollama. O modelo mais próximo seria da família `phi3`. Por favor, verifique o nome exato do modelo que pretende usar na [biblioteca Ollama](https://ollama.com/library). Se for um modelo personalizado ou uma tag específica, use essa tag. Para este guia, usarei `phi3:mini` como um exemplo comum e disponível. Se o seu modelo for `phi3:mini` com uma tag diferente, ajuste o comando.
    *   *Se `phi4-mini-reasoning` é o nome que tem funcionado para si, pode tentar:*
        ```cmd
        ollama pull phi3:mini 
        ```
        *Ou, se `phi4-mini-reasoning` for uma tag específica que funciona para si (verifique `ollama list` no seu sistema se já o tem):*
        ```cmd
        ollama pull phi4-mini-reasoning 
        ```
        *(Este último comando provavelmente falhará se `phi4-mini-reasoning` não for uma tag oficial ou um modelo que já construiu localmente).*
        **Para efeitos deste guia, vou assumir o modelo oficial `phi3:mini` como um exemplo robusto.**

    *   **Modelo Sugerido: `phi3:mini`**
        Um modelo recente da Microsoft, com bom equilíbrio entre tamanho e capacidade.
        Execute:
        ```cmd
        ollama pull phi3:mini
        ```

2.  **`gemma:2b` (ou `gemma3:1b` se for essa a tag específica)**
    *   **Nota:** `gemma3:1b` não é uma tag padrão comum para `gemma`. A tag mais comum para a versão de ~2B parâmetros é `gemma:2b`. Verifique a [biblioteca Ollama](https://ollama.com/library/gemma). Se `gemma3:1b` é uma tag que tem ou funciona para si, use-a.
    *   **Modelo Sugerido: `gemma:2b`**
        Modelo da Google, também relativamente leve.
        Execute:
        ```cmd
        ollama pull gemma:2b
        ```

3.  **`llama3:8b`**
    *   Um modelo maior e mais capaz da Meta, mas requer mais recursos (RAM e VRAM).
    *   Execute:
        ```cmd
        ollama pull llama3:8b
        ```

4.  **`qwen2:7b` (ou `qwen3:8b` se for essa a tag específica)**
    *   **Nota:** `qwen3:8b` não é uma tag padrão comum. A família `qwen` tem `qwen2:7b` como um modelo popular. Verifique a [biblioteca Ollama](https://ollama.com/library/qwen2). Se `qwen3:8b` é uma tag que tem ou funciona para si, use-a.
    *   **Modelo Sugerido: `qwen2:7b`**
        Um modelo capaz da Alibaba Cloud.
        Execute:
        ```cmd
        ollama pull qwen2:7b
        ```

Pode encontrar mais modelos e as suas etiquetas específicas (tags) na biblioteca oficial do Ollama: [ollama.com/library](https://ollama.com/library)

Após descarregar, pode verificar os modelos instalados com `ollama list`.

---

## 7. Estrutura de Pastas do Projeto (Confirmar)

Após clonar o repositório, a estrutura de pastas já deverá estar correta. Verifique se corresponde a isto dentro da pasta `FileEvaluationAPIgenerateSimple`:

```
FileEvaluationAPIgenerateSimple/
├── mini_doc_analyzer_v2.py
├── interaction_logger_mini.py
├── prompts_mini/
│   ├── system_doc_holistic_assessor_raw.txt
│   └── user_doc_holistic_task_template_raw.txt
├── test_schemas/
│   └── GtfsAccessPoint.json  <-- Adicione os seus ficheiros JSON de teste aqui
└── README.md
└── .gitignore
└── llm_interaction_logs/     <-- Será criada automaticamente
```
*   Confirme que a pasta `test_schemas` contém os ficheiros `.json` que pretende analisar. Se estiver vazia, adicione alguns.

---

## 8. Executar o Script

1.  **Certifique-se de que o Ollama está a correr** em segundo plano.
2.  Abra a Linha de Comandos (CMD) ou PowerShell.
3.  Se ainda não estiver, navegue até à pasta `FileEvaluationAPIgenerateSimple` que clonou:
    ```cmd
    cd caminho\para\FileEvaluationAPIgenerateSimple
    ```
4.  Execute o script Python:
    ```cmd
    python mini_doc_analyzer_v2.py
    ```

5.  O script irá:
    *   Listar os modelos Ollama que descarregou.
    *   Pedir-lhe para selecionar um modelo da lista.
    *   Analisar os ficheiros `.json` encontrados na pasta `test_schemas`.
    *   Guardar os logs detalhados das interações e informações do sistema na pasta `llm_interaction_logs`.

---
