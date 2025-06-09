Entendido! Aqui está o guia de instalação focado exclusivamente no Windows, utilizando o link específico para o Python 3.11.12, e formatado em Markdown.

```markdown
# Guia de Instalação (Windows): Mini Document PII Analyzer

Este guia detalha os passos para configurar o ambiente necessário no Windows para executar o script `mini_doc_analyzer.py`.

## Sumário

1.  [Instalar Python 3.11.12 e Pip](#1-instalar-python-31112-e-pip)
2.  [Instalar Bibliotecas Python](#2-instalar-bibliotecas-python)
3.  [Instalar Ollama](#3-instalar-ollama)
4.  [Descarregar Modelos Ollama para Teste](#4-descarregar-modelos-ollama-para-teste)
5.  [Estrutura de Pastas do Projeto](#5-estrutura-de-pastas-do-projeto)
6.  [Executar o Script](#6-executar-o-script)

---

## 1. Instalar Python 3.11.12 e Pip

`pip` (o gestor de pacotes do Python) vem incluído com esta instalação do Python.

1.  **Descarregar Python 3.11.12:**
    *   Vá para a página de download específica do Python 3.11.12: [https://www.python.org/downloads/release/python-31112/](https://www.python.org/downloads/release/python-31112/)
    *   Navegue até à secção "Files" no final da página.
    *   Procure e descarregue o **"Windows installer (64-bit)"**. (Se tiver um sistema Windows de 32 bits, que é raro hoje em dia, escolha a versão de 32 bits).

2.  **Executar o Instalador:**
    *   Abra o ficheiro `.exe` que descarregou.
    *   **Muito Importante:** No primeiro ecrã do instalador, marque a caixa que diz **"Add Python 3.11 to PATH"**. Isto é crucial para poder executar `python` e `pip` facilmente a partir da Linha de Comandos.
    *   Clique em "Install Now" para a instalação padrão. Se preferir, pode escolher "Customize installation" para alterar o local de instalação, mas a opção padrão é geralmente adequada.
    *   Aguarde a conclusão da instalação. Poderá ser necessário fornecer permissões de administrador.

3.  **Verificar Instalação:**
    *   Após a instalação, abra uma **nova** Linha de Comandos (CMD) ou PowerShell. (É importante que seja uma nova janela para que as alterações ao PATH sejam reconhecidas).
    *   Digite o seguinte comando e pressione Enter:
        ```cmd
        python --version
        ```
        Deverá ver algo como `Python 3.11.12`.
    *   De seguida, digite este comando e pressione Enter:
        ```cmd
        pip --version
        ```
        Deverá ver a versão do pip associada ao Python 3.11.12.

---

## 2. Instalar Bibliotecas Python

Com o Python e `pip` configurados, instale as bibliotecas Python necessárias para o projeto. Na Linha de Comandos (CMD ou PowerShell), execute o seguinte comando:

```cmd
pip install requests beaupy psutil wmi
```

Detalhes das bibliotecas:
*   **`requests`**: Para fazer pedidos HTTP à API do Ollama.
*   **`beaupy`**: Para criar interfaces de seleção interativas na linha de comandos.
*   **`psutil`**: Para obter informações do sistema (CPU, RAM, disco, SO).
*   **`wmi`**: Para obter informações mais detalhadas do sistema no Windows (GPU, tipo de disco).

*Dica: Se planeia trabalhar em vários projetos Python, considere usar ambientes virtuais para gerir as dependências de cada projeto separadamente. Se estiver a usar um ambiente virtual, ative-o antes de executar o comando `pip install`.*

---

## 3. Instalar Ollama

Ollama permite executar modelos de linguagem grandes localmente.

1.  **Visite o Site Oficial:**
    *   [ollama.com](https://ollama.com/)
2.  **Descarregar e Instalar para Windows:**
    *   Na página inicial do Ollama, clique no botão de download para Windows.
    *   Execute o ficheiro `.exe` do instalador do Ollama.
    *   Siga as instruções de instalação. O Ollama será configurado para iniciar automaticamente com o Windows e correr em segundo plano.
3.  **Verificar Instalação (após Ollama estar a correr):**
    *   O ícone do Ollama deverá aparecer na bandeja do sistema (perto do relógio).
    *   Abra uma nova Linha de Comandos/PowerShell e digite:
        ```cmd
        ollama list
        ```
    *   Se for a primeira vez que executa este comando e não tem modelos descarregados, a lista estará vazia. Isto confirma que o cliente de linha de comandos (CLI) do Ollama está a funcionar e a comunicar com o serviço Ollama.

---

## 4. Descarregar Modelos Ollama para Teste

Para testar o script, precisa de descarregar alguns modelos através do Ollama. Abra a Linha de Comandos/PowerShell.

Modelos recomendados para começar (são relativamente pequenos e versáteis):

1.  **`phi3:mini`**
    *   Um modelo recente da Microsoft, com bom equilíbrio entre tamanho e capacidade.
    *   Execute:
        ```cmd
        ollama pull phi3:mini
        ```

2.  **`gemma:2b`**
    *   Modelo da Google, também relativamente leve.
    *   Execute:
        ```cmd
        ollama pull gemma:2b
        ```

3.  **(Opcional) `llama3:8b`**
    *   Um modelo maior e mais capaz da Meta, mas requer mais recursos (RAM e VRAM).
    *   Execute:
        ```cmd
        ollama pull llama3:8b
        ```
    *   *Verifique os requisitos de sistema para este modelo no site do Ollama ou na página do modelo na biblioteca Ollama.*

Pode encontrar mais modelos e as suas etiquetas específicas (tags) na biblioteca oficial do Ollama: [ollama.com/library](https://ollama.com/library)

Após descarregar, pode verificar os modelos instalados com `ollama list`.

---

## 5. Estrutura de Pastas do Projeto

Certifique-se de que o seu projeto tem a seguinte estrutura de pastas e ficheiros no seu computador:

```
FileEvaluationAPIgenerateSimple/   <-- Pasta raiz do seu projeto (o nome pode ser diferente)
├── mini_doc_analyzer_v2.py        <-- O script Python principal
├── interaction_logger_mini.py     <-- O módulo de logging
├── prompts_mini/                  <-- Pasta para os templates de prompt
│   ├── system_doc_holistic_assessor_raw.txt
│   └── user_doc_holistic_task_template_raw.txt
├── test_schemas/                  <-- Pasta para os ficheiros JSON que quer analisar
│   └── GtfsAccessPoint.json       <-- Exemplo de ficheiro JSON (adicione os seus aqui)
│   └── outro_exemplo.json
└── llm_interaction_logs/          <-- Esta pasta será criada automaticamente pelo logger para guardar os logs
```

*   Coloque os seus ficheiros `.py` (`mini_doc_analyzer_v2.py`, `interaction_logger_mini.py`) na pasta raiz do projeto.
*   Crie a pasta `prompts_mini` e coloque os ficheiros de template de prompt (`system_doc_holistic_assessor_raw.txt`, `user_doc_holistic_task_template_raw.txt`) lá dentro.
*   Crie a pasta `test_schemas` e coloque os ficheiros `.json` que pretende analisar lá.

---

## 6. Executar o Script

1.  **Certifique-se de que o Ollama está a correr** em segundo plano. Verifique o ícone na bandeja do sistema.
2.  Abra a Linha de Comandos (CMD) ou PowerShell.
3.  Navegue até à pasta raiz do seu projeto usando o comando `cd`. Por exemplo:
    ```cmd
    cd C:\Caminho\Para\O\Seu\Projeto\FileEvaluationAPIgenerateSimple
    ```
    (Substitua pelo caminho real da sua pasta).
4.  Execute o script Python:
    ```cmd
    python mini_doc_analyzer_v2.py
    ```

5.  O script irá:
    *   Listar os modelos Ollama que descarregou.
    *   Pedir-lhe para selecionar um modelo da lista.
    *   Começar a analisar os ficheiros `.json` encontrados na pasta `test_schemas`.
    *   Guardar os logs detalhados das interações e informações do sistema na pasta `llm_interaction_logs`.

---

Se encontrar algum problema durante a execução:
*   Verifique as mensagens de erro no terminal. Elas geralmente dão pistas sobre o que correu mal.
*   Confirme que todas as bibliotecas Python (`requests`, `beaupy`, `psutil`, `wmi`) foram instaladas corretamente.
*   Certifique-se de que o serviço Ollama está realmente a correr.
*   Verifique se os caminhos para as pastas `prompts_mini` e `test_schemas` estão corretos em relação à localização do script.
```

Este guia focado no Windows deverá ser mais direto para a sua configuração.
