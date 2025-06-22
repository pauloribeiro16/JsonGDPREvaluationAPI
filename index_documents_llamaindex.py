# index_documents_llamaindex.py
import os
import json # Não usado diretamente para escrita, mas pode estar em documentos
import logging
import sys

# Configurar logging básico para LlamaIndex (opcional, mas útil)
# logging.basicConfig(stream=sys.stdout, level=logging.INFO) # INFO ou DEBUG
# logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))
logger = logging.getLogger(__name__) # Usar logger nomeado
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb # Necessário para criar o cliente Chroma

# --- Configurações Atualizadas ---
PROJECT_DOCUMENTS_PATH = "./document/project"  # Caminho para documentos do PROJETO
PROJECT_CHROMA_PERSIST_DIR = "./llamaindex_chroma_db_project_docs" # NOVO diretório para DB de docs do projeto
PROJECT_CHROMA_COLLECTION_NAME = "project_docs_minilm" # NOVA coleção para docs do projeto

# Modelo de Embedding (mesmo que antes para consistência)
LLAMA_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Text Splitter (NodeParser em LlamaIndex)
LLAMA_CHUNK_SIZE = 1000
LLAMA_CHUNK_OVERLAP = 150

def create_project_vector_store():
    logger.info(f"[Project Docs Indexer INFO] Iniciando processo de indexação de documentos de: {PROJECT_DOCUMENTS_PATH}")

    if not os.path.exists(PROJECT_DOCUMENTS_PATH):
        os.makedirs(PROJECT_DOCUMENTS_PATH)
        logger.warning(f"Diretório de documentos do projeto '{PROJECT_DOCUMENTS_PATH}' não existia e foi criado.")
        logger.warning("  Adicione os seus ficheiros PDF, TXT, JSON, HTML lá e execute este script novamente.")
        return None

    # 1. Carregar Documentos do Projeto
    try:
        logger.info(f"A carregar documentos de '{PROJECT_DOCUMENTS_PATH}'...")
        def filename_fn(filename_path):
            return {"source_filename": os.path.basename(filename_path),
                    "document_type": os.path.splitext(filename_path)[1].lower()}

        reader = SimpleDirectoryReader(
            input_dir=PROJECT_DOCUMENTS_PATH,
            required_exts=[".pdf", ".txt", ".json", ".html", ".htm", ".md"],
            recursive=True,
            file_metadata=filename_fn
        )
        documents = reader.load_data()
        if not documents:
            logger.warning("Nenhum documento do projeto carregado. Verifique o diretório e as extensões.")
            return None
        logger.info(f"{len(documents)} documentos do projeto carregados com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao carregar documentos do projeto: {e}")
        return None

    # 2. Configurar Modelo de Embedding
    logger.info(f"A configurar modelo de embedding: {LLAMA_EMBED_MODEL_NAME}")
    try:
        embed_model = HuggingFaceEmbedding(model_name=LLAMA_EMBED_MODEL_NAME, device="cpu")
    except Exception as e:
        logger.error(f"Erro ao inicializar modelo de embedding: {e}")
        logger.error("  Certifique-se que sentence-transformers está instalado e o nome do modelo é válido.")
        return None

    # 3. Configurar ChromaDB como VectorStore para o Projeto
    logger.info(f"A configurar ChromaDB para documentos do projeto em: {PROJECT_CHROMA_PERSIST_DIR}, coleção: {PROJECT_CHROMA_COLLECTION_NAME}")
    if not os.path.exists(PROJECT_CHROMA_PERSIST_DIR):
        os.makedirs(PROJECT_CHROMA_PERSIST_DIR)

    try:
        chroma_client = chromadb.PersistentClient(path=PROJECT_CHROMA_PERSIST_DIR)
        # Apagar coleção antiga se existir, para garantir que estamos a indexar de novo.
        try:
            logger.info(f"A tentar apagar coleção existente '{PROJECT_CHROMA_COLLECTION_NAME}' para reindexação...")
            chroma_client.delete_collection(PROJECT_CHROMA_COLLECTION_NAME)
            logger.info(f"Coleção '{PROJECT_CHROMA_COLLECTION_NAME}' apagada com sucesso.")
        except Exception:
            logger.info(f"Coleção '{PROJECT_CHROMA_COLLECTION_NAME}' não encontrada para apagar, será criada.")
            pass

        chroma_collection = chroma_client.get_or_create_collection(PROJECT_CHROMA_COLLECTION_NAME)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    except Exception as e:
        logger.error(f"Erro ao configurar ChromaVectorStore para documentos do projeto: {e}")
        return None

    # 4. Configurar NodeParser (Text Splitter)
    node_parser = SentenceSplitter(chunk_size=LLAMA_CHUNK_SIZE, chunk_overlap=LLAMA_CHUNK_OVERLAP)

    # 5. Criar o StorageContext
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # 6. Criar o Índice para Documentos do Projeto
    logger.info(f"A criar ou atualizar o VectorStoreIndex para documentos do projeto...")
    try:
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            embed_model=embed_model,
            transformations=[node_parser],
            show_progress=True
        )
        logger.info(f"Indexação de documentos do projeto concluída. Índice com {len(index.docstore.docs)} nós base.")
        logger.info(f"  Coleção Chroma '{PROJECT_CHROMA_COLLECTION_NAME}' agora tem {chroma_collection.count()} embeddings.")
        logger.info(f"Índice LlamaIndex para documentos do projeto com ChromaDB persistido/atualizado em '{PROJECT_CHROMA_PERSIST_DIR}'.")
        return index
    except Exception as e:
        logger.error(f"Erro ao criar o VectorStoreIndex para documentos do projeto: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Configurar logging para ver mais detalhes do LlamaIndex durante a indexação
    # logging.getLogger('llama_index').setLevel(logging.DEBUG) # Para LlamaIndex

    index = create_project_vector_store()

    if index:
        logger.info("\n[Project Docs Indexer SUCCESS] Indexação de documentos do projeto com LlamaIndex e ChromaDB concluída.")
        # Exemplo de como testar (opcional)
        try:
            logger.info("\n[Project Docs Indexer TEST] A testar uma query de similaridade...")
            retriever = index.as_retriever(similarity_top_k=2)
            # Adapte a query de teste para algo que possa estar nos seus documentos de projeto
            test_query_text = "Quais são os principais objetivos deste projeto?"
            nodes = retriever.retrieve(test_query_text)
            if nodes:
                logger.info(f"  Resultados para a query de teste '{test_query_text}':")
                for i, node_with_score in enumerate(nodes):
                    node = node_with_score.node
                    logger.info(f"  Resultado {i+1} (Score: {node_with_score.score:.4f}):")
                    logger.info(f"    Fonte: {node.metadata.get('source_filename', 'N/A')}")
                    logger.info(f"    Conteúdo (preview): {node.get_content()[:250]}...")
            else:
                logger.info("  Nenhum resultado encontrado para a query de teste nos documentos do projeto.")
        except Exception as e_query:
            logger.error(f"[Project Docs Indexer TEST ERROR] Erro ao testar query: {e_query}")
    else:
        logger.error("\n[Project Docs Indexer FAIL] Processo de indexação de documentos do projeto falhou.")