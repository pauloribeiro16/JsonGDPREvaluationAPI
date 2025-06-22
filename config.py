# config.py

# --- Ollama Configurations ---
OLLAMA_API_BASE_URL = "http://localhost:11434/api"
OLLAMA_TAGS_ENDPOINT_SUFFIX = "/tags"
OLLAMA_GENERATE_ENDPOINT_SUFFIX = "/generate"
OLLAMA_REQUEST_TIMEOUT_SECONDS = 360
OLLAMA_KEEP_ALIVE_DURATION = "5m"
# Nome de um modelo Ollama pequeno e rápido para tarefas auxiliares RAG
# Certifique-se que este modelo está disponível no seu Ollama
PREFERRED_RAG_AUX_LLM_NAME = "qwen2.5:0.5b" 

# --- Directory Configurations ---
# PROMPTS_DIR_NAME = "prompts_mini" # Não será mais necessário se os prompts estiverem no código
DEFAULT_SCHEMA_DIR_NAME = "test_schemas" # Apenas o nome da pasta, o caminho completo será construído
LOG_DIR_NAME = "llm_interaction_logs"

RGPD_DOCS_SUBDIR = "document/GDPR/"
# Project Documents Path (relativo ao script principal)
PROJECT_DOCS_SUBDIR = "document/project/"

# --- LlamaIndex & ChromaDB Configurations ---
# RGPD Index
RGPD_CHROMA_PERSIST_DIR_NAME = "llamaindex_chroma_db_rgpd" # Apenas o nome, caminho completo será construído
RGPD_CHROMA_COLLECTION_NAME = "rgpd_structured_minilm"

# Project Documents Index
PROJECT_DOCS_CHROMA_PERSIST_DIR_NAME = "llamaindex_chroma_db_project_docs" # Apenas o nome
PROJECT_DOCS_CHROMA_COLLECTION_NAME = "project_docs_minilm"

# Embedding Model
LLAMA_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# LlamaIndex NodeParser (Chunking) Settings for General Project Docs
LLAMA_CHUNK_SIZE = 1000
LLAMA_CHUNK_OVERLAP = 150

# RGPD Structural Chunking Settings
RGPD_MAX_CHUNK_SIZE_CHARS = 1800
RGPD_CHUNK_OVERLAP_CHARS = 150

# --- RAG Task Configurations ---
RAG_NUM_SUBQUERIES = 3
RAG_K_PER_RETRIEVER_SIMPLE = 2    # Para RAG Simples, quantos nós de cada índice
RAG_K_PER_RETRIEVER_MULTISTEP = 1 # Para RAG Multi-Query, quantos nós de cada índice por sub-pergunta

# --- JSON Analysis Configuration ---
MAX_JSON_SIZE_FOR_PROMPT_MB = 2 # Em Megabytes, para limitar o tamanho do JSON enviado ao LLM