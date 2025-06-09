# Guia de Instalação: Mini Document PII Analyzer

Este guia detalha os passos para configurar o ambiente necessário para executar o script `mini_doc_analyzer.py`.

## Sumário

1.  [Instalar Python e Pip](#1-instalar-python-e-pip)
2.  [Instalar Bibliotecas Python](#2-instalar-bibliotecas-python)
3.  [Instalar Ollama](#3-instalar-ollama)
4.  [Descarregar Modelos Ollama para Teste](#4-descarregar-modelos-ollama-para-teste)
5.  [Estrutura de Pastas do Projeto](#5-estrutura-de-pastas-do-projeto)
6.  [Executar o Script](#6-executar-o-script)

---

## 1. Instalar Python e Pip

Se ainda não tem Python instalado, siga estes passos. `pip` (o gestor de pacotes do Python) geralmente vem incluído nas instalações modernas do Python.

### Windows:

1.  **Descarregar Python:**
    *   Vá ao site oficial do Python: [python.org/downloads/windows/](https://www.python.org/downloads/windows/)
    *   Descarregue o instalador executável mais recente para Windows (ex: "Windows installer (64-bit)").
2.  **Executar o Instalador:**
    *   Execute o ficheiro `.exe` descarregado.
    *   **Importante:** No primeiro ecrã do instalador, marque a caixa que diz **"Add Python X.X to PATH"** (onde X.X é a versão). Isto é crucial para poder executar `python` e `pip` a partir da linha de comandos.
    *   Pode escolher "Install Now" (instalação padrão) ou "Customize installation" se souber o que está a fazer.
3.  **Verificar Instalação:**
    *   Abra uma nova Linha de Comandos (CMD) ou PowerShell.
    *   Digite `python --version` e pressione Enter. Deverá ver a versão do Python instalada.
    *   Digite `pip --version` e pressione Enter. Deverá ver a versão do pip instalada.

### macOS:

O macOS geralmente já vem com uma versão do Python, mas pode ser uma versão mais antiga (Python 2). É recomendado instalar o Python 3.

1.  **Usando Homebrew (Recomendado):**
    *   Se não tem o Homebrew, instale-o a partir de [brew.sh](https://brew.sh/).
    *   Abra o Terminal e execute:
        ```bash
        brew install python
        ```
2.  **Usando o Instalador Oficial:**
    *   Vá ao site oficial do Python: [python.org/downloads/macos/](https://www.python.org/downloads/macos/)
    *   Descarregue o instalador de pacote macOS.
    *   Execute o ficheiro `.pkg` e siga as instruções.
3.  **Verificar Instalação:**
    *   Abra um novo Terminal.
    *   Digite `python3 --version` e pressione Enter.
    *   Digite `pip3 --version` e pressione Enter.
    *   (Pode precisar de usar `python3` e `pip3` em vez de `python` e `pip` para garantir que está a usar a versão 3).

### Linux:

A maioria das distribuições Linux já vem com Python 3 instalado.

1.  **Verificar Instalação:**
    *   Abra o Terminal.
    *   Digite `python3 --version` e pressione Enter.
    *   Digite `pip3 --version` e pressione Enter.
2.  **Instalar (se necessário):**
    *   Em sistemas baseados em Debian/Ubuntu:
        ```bash
        sudo apt update
        sudo apt install python3 python3-pip
        ```
    *   Em sistemas baseados em Fedora:
        ```bash
        sudo dnf install python3 python3-pip
        ```

---

## 2. Instalar Bibliotecas Python

Com o Python e `pip` configurados, instale as bibliotecas Python necessárias para o projeto. Abra a Linha de Comandos (CMD/PowerShell no Windows) ou Terminal (macOS/Linux) e execute:

```bash
pip install requests beaupy psutil wmi


requests: Para fazer pedidos HTTP à API do Ollama.

beaupy: Para criar interfaces de seleção interativas na linha de comandos.

psutil: Para obter informações do sistema (CPU, RAM, disco, SO).

wmi: Para obter informações mais detalhadas do sistema no Windows (GPU, tipo de disco). Nota: Esta biblioteca é específica para Windows.

Se estiver num ambiente virtual (recomendado para isolar dependências de projetos), ative-o antes de executar o comando pip install.

3. Instalar Ollama

Ollama permite executar modelos de linguagem grandes localmente.

Visite o Site Oficial:

ollama.com

Descarregar e Instalar:

Windows: Descarregue o instalador para Windows a partir da secção "Download" e execute-o.

macOS: Descarregue a aplicação para macOS.

Linux: Siga as instruções de instalação fornecidas (geralmente um script curl).

Verificar Instalação (após Ollama estar a correr):

Após a instalação, o Ollama deverá estar a correr em segundo plano.

Abra uma nova Linha de Comandos/Terminal e digite:

ollama list
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

Se for a primeira vez, a lista estará vazia. Isto confirma que o CLI do Ollama está a funcionar.

4. Descarregar Modelos Ollama para Teste

Para testar o script, precisará de alguns modelos descarregados através do Ollama. Abra a Linha de Comandos/Terminal.

Modelos recomendados para começar (são relativamente pequenos e versáteis):

phi3:mini (ou uma variante mais recente de Phi-3 se disponível)

Bom equilíbrio entre tamanho e capacidade.

Execute:

ollama pull phi3:mini
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

gemma:2b

Modelo da Google, também relativamente leve.

Execute:

ollama pull gemma:2b
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

(Opcional) llama3:8b (ou uma variante mais recente de Llama-3 se disponível)

Um modelo maior e mais capaz, mas requer mais recursos (RAM/VRAM).

Execute:

ollama pull llama3:8b
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

Verifique os requisitos de sistema para este modelo no site do Ollama ou na página do modelo no ollama.com/library.

Pode encontrar mais modelos na biblioteca oficial do Ollama: ollama.com/library

Após descarregar, pode verificar os modelos instalados com ollama list.

5. Estrutura de Pastas do Projeto

Certifique-se de que o seu projeto tem a seguinte estrutura de pastas e ficheiros:

FileEvaluationAPIgenerateSimple/   <-- Pasta raiz do seu projeto
├── mini_doc_analyzer_v2.py        <-- O script Python principal (ou o nome que lhe deu)
├── interaction_logger_mini.py     <-- O módulo de logging
├── prompts_mini/                  <-- Pasta para os templates de prompt
│   ├── system_doc_holistic_assessor_raw.txt
│   └── user_doc_holistic_task_template_raw.txt
├── test_schemas/                  <-- Pasta para os ficheiros JSON que quer analisar
│   └── GtfsAccessPoint.json       <-- Exemplo de ficheiro JSON
│   └── outro_exemplo.json
└── llm_interaction_logs/          <-- Esta pasta será criada automaticamente pelo logger
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
IGNORE_WHEN_COPYING_END

Coloque os seus ficheiros .py na raiz do projeto.

Crie a pasta prompts_mini e coloque os ficheiros de template de prompt lá dentro.

Crie a pasta test_schemas e coloque os ficheiros .json que pretende analisar lá.

6. Executar o Script

Certifique-se de que o Ollama está a correr em segundo plano.

Navegue até à pasta raiz do seu projeto na Linha de Comandos/Terminal:

