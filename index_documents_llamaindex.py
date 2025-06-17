# index_documents_llamaindex.py
import os
import json
import logging
import sys

# Configurar logging básico para LlamaIndex (opcional, mas útil)
# logging.basicConfig(stream=sys.stdout, level=logging.INFO) # INFO ou DEBUG
# logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb # Necessário para criar o cliente Chroma

# Configurações
DOCUMENTS_PATH_LLAMA = "./document"  # Use a mesma pasta de documentos
LLAMA_CHROMA_PERSIST_DIR = "./llamaindex_chroma_db_docs" # NOVO diretório
LLAMA_CHROMA_COLLECTION_NAME = "llamaindex_doc_embeddings_minilm" # NOVA coleção

# Modelo de Embedding (mesmo que antes para consistência, se desejado)
LLAMA_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2" # Nome completo para HuggingFace

# Text Splitter (NodeParser em LlamaIndex)
LLAMA_CHUNK_SIZE = 1000
LLAMA_CHUNK_OVERLAP = 150

def create_llamaindex_vector_store():
    print(f"[LlamaIndex INFO] Iniciando processo de indexação de documentos de: {DOCUMENTS_PATH_LLAMA}")

    if not os.path.exists(DOCUMENTS_PATH_LLAMA):
        os.makedirs(DOCUMENTS_PATH_LLAMA)
        print(f"[LlamaIndex WARNING] Diretório de documentos '{DOCUMENTS_PATH_LLAMA}' não existia e foi criado.")
        print("  Adicione os seus ficheiros PDF, TXT, JSON, HTML lá e execute este script novamente.")
        return None

    # 1. Carregar Documentos
    # SimpleDirectoryReader pode precisar de dependências extras para certos tipos de ficheiros (ex: pypdf para PDFs)
    # Verifique a documentação do LlamaIndex para 'file_extractor' se tiver tipos de ficheiros complexos
    # ou quiser um parsing de JSON mais específico.
    # Para JSON, o SimpleDirectoryReader por defeito trata-o como texto.
    # Para HTML, ele também deve extrair o texto principal.
    try:
        print(f"[LlamaIndex INFO] A carregar documentos de '{DOCUMENTS_PATH_LLAMA}'...")
        # Configurar file_metadata para obter o nome do ficheiro
        def filename_fn(filename_path):
            return {"source_filename": os.path.basename(filename_path),
                    "document_type": os.path.splitext(filename_path)[1].lower()}

        reader = SimpleDirectoryReader(
            input_dir=DOCUMENTS_PATH_LLAMA,
            required_exts=[".pdf", ".txt", ".json", ".html", ".htm", ".md"], # Adicione as extensões que tem
            recursive=True, # Ler subdiretórios também, se houver
            file_metadata=filename_fn
        )
        documents = reader.load_data()
        if not documents:
            print("[LlamaIndex WARNING] Nenhum documento carregado. Verifique o diretório e as extensões.")
            return None
        print(f"[LlamaIndex INFO] {len(documents)} documentos carregados com sucesso.")
    except Exception as e:
        print(f"[LlamaIndex ERROR] Erro ao carregar documentos: {e}")
        return None

    # 2. Configurar Modelo de Embedding
    print(f"[LlamaIndex INFO] A configurar modelo de embedding: {LLAMA_EMBED_MODEL_NAME}")
    try:
        # LlamaIndex espera o nome como é usado pela biblioteca sentence-transformers
        embed_model = HuggingFaceEmbedding(model_name=LLAMA_EMBED_MODEL_NAME, device="cpu")
    except Exception as e:
        print(f"[LlamaIndex ERROR] Erro ao inicializar modelo de embedding: {e}")
        print("  Certifique-se que sentence-transformers está instalado e o nome do modelo é válido.")
        return None

    # 3. Configurar ChromaDB como VectorStore
    print(f"[LlamaIndex INFO] A configurar ChromaDB em: {LLAMA_CHROMA_PERSIST_DIR}, coleção: {LLAMA_CHROMA_COLLECTION_NAME}")
    if not os.path.exists(LLAMA_CHROMA_PERSIST_DIR):
        os.makedirs(LLAMA_CHROMA_PERSIST_DIR)

    try:
        chroma_client = chromadb.PersistentClient(path=LLAMA_CHROMA_PERSIST_DIR)
        chroma_collection = chroma_client.get_or_create_collection(LLAMA_CHROMA_COLLECTION_NAME)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    except Exception as e:
        print(f"[LlamaIndex ERROR] Erro ao configurar ChromaVectorStore: {e}")
        return None

    # 4. Configurar NodeParser (Text Splitter)
    node_parser = SentenceSplitter(chunk_size=LLAMA_CHUNK_SIZE, chunk_overlap=LLAMA_CHUNK_OVERLAP)

    # 5. Criar o StorageContext e o ServiceContext (ou usar global)
    # O ServiceContext foi depreciado, agora os componentes são passados diretamente ou via Settings global
    # LlamaIndex.Settings.llm = ... (se precisar de um LLM global)
    # LlamaIndex.Settings.embed_model = embed_model (pode definir globalmente)
    # LlamaIndex.Settings.node_parser = node_parser

    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # 6. Criar o Índice
    # Passar `embed_model` e `transformations` (que inclui o node_parser) diretamente para VectorStoreIndex
    # se não foram definidos globalmente em `Settings`.
    print(f"[LlamaIndex INFO] A criar ou atualizar o VectorStoreIndex...")
    try:
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            embed_model=embed_model, # Passar explicitamente
            transformations=[node_parser], # Passar explicitamente
            show_progress=True
        )
        # A persistência com ChromaVectorStore e PersistentClient já deve acontecer,
        # mas uma chamada explícita ao `persist` do índice pode ser feita se necessário para outros stores.
        # Com ChromaVectorStore configurado com um cliente persistente, a persistência é gerida pelo cliente.
        print(f"[LlamaIndex INFO] Indexação concluída. Índice com {len(index.docstore.docs)} nós base (documentos originais).")
        print(f"  Coleção Chroma '{LLAMA_CHROMA_COLLECTION_NAME}' agora tem {chroma_collection.count()} embeddings.")
        # index.storage_context.persist(persist_dir=LLAMA_CHROMA_PERSIST_DIR) # Redundante se Chroma já é persistente
        print(f"[LlamaIndex INFO] Índice LlamaIndex com ChromaDB persistido/atualizado em '{LLAMA_CHROMA_PERSIST_DIR}'.")
        return index
    except Exception as e:
        print(f"[LlamaIndex ERROR] Erro ao criar o VectorStoreIndex: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Configurar logging para ver mais detalhes do LlamaIndex durante a indexação
    logging.basicConfig(stream=sys.stdout, level=logging.INFO) # Mudar para DEBUG para mais verbosidade
    # Descomentar a linha abaixo pode causar duplicação de logs se o root logger já tiver handlers.
    # logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))
    
    # Definir o embed_model globalmente para LlamaIndex usar (alternativa a passar em cada chamada)
    # from llama_index.core import Settings
    # Settings.embed_model = HuggingFaceEmbedding(model_name=LLAMA_EMBED_MODEL_NAME, device="cpu")
    # Settings.chunk_size = LLAMA_CHUNK_SIZE # Outra forma de definir globalmente
    # Settings.chunk_overlap = LLAMA_CHUNK_OVERLAP
    
    index = create_llamaindex_vector_store()

    if index:
        print("\n[LlamaIndex SUCCESS] Indexação com LlamaIndex e ChromaDB concluída.")
        # Exemplo de como testar (opcional)
        # try:
        #     print("\n[LlamaIndex TEST] A testar uma query de similaridade...")
        #     retriever = index.as_retriever(similarity_top_k=2)
        #     test_query_text = "Quais são os direitos dos titulares de dados?"
        #     nodes = retriever.retrieve(test_query_text)
        #     if nodes:
        #         print(f"  Resultados para a query de teste '{test_query_text}':")
        #         for i, node_with_score in enumerate(nodes):
        #             node = node_with_score.node
        #             print(f"  Resultado {i+1} (Score: {node_with_score.score:.4f}):")
        #             print(f"    Fonte: {node.metadata.get('source_filename', 'N/A')}")
        #             print(f"    Conteúdo (preview): {node.get_content()[:250]}...")
        #     else:
        #         print("  Nenhum resultado encontrado para a query de teste.")
        # except Exception as e_query:
        #     print(f"[LlamaIndex TEST ERROR] Erro ao testar query: {e_query}")
    else:
        print("\n[LlamaIndex FAIL] Processo de indexação falhou.")