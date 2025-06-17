# document_rag_services.py
import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

load_dotenv()

# Configurações (devem ser as mesmas do script de indexação)
CHROMA_PERSIST_DIRECTORY_SVC = "./chroma_db_docs"
CHROMA_COLLECTION_NAME_SVC = "document_embeddings_minilm"

# Modelo de Embedding (deve ser o mesmo da indexação)
MODEL_NAME_SVC = "all-MiniLM-L6-v2"
embedding_function_svc = HuggingFaceEmbeddings(model_name=MODEL_NAME_SVC, model_kwargs={'device': 'cpu'})

class DocumentRAGRetrieverFactory:
    def __init__(self):
        self.embedding_model = embedding_function_svc
        self.vector_store = None
        self.is_initialized = False

        if not os.path.exists(CHROMA_PERSIST_DIRECTORY_SVC):
            print(f"[DOC RAG FACTORY WARNING] Diretório da base vetorial Chroma não encontrado: {CHROMA_PERSIST_DIRECTORY_SVC}")
            print("  Execute o script 'index_documents.py' primeiro para criar a base de dados.")
            return

        try:
            print(f"[DOC RAG FACTORY INFO] A carregar base vetorial Chroma de: {CHROMA_PERSIST_DIRECTORY_SVC}")
            self.vector_store = Chroma(
                collection_name=CHROMA_COLLECTION_NAME_SVC,
                persist_directory=CHROMA_PERSIST_DIRECTORY_SVC,
                embedding_function=self.embedding_model # Importante para queries
            )
            # Testar se a coleção tem itens
            if self.vector_store._collection.count() == 0:
                 print(f"[DOC RAG FACTORY WARNING] A coleção Chroma '{CHROMA_COLLECTION_NAME_SVC}' está vazia ou não foi encontrada corretamente.")
                 print("  Certifique-se de que o script 'index_documents.py' foi executado com sucesso e populou a coleção.")
                 self.is_initialized = False # Marcar como não inicializado se estiver vazio
            else:
                print(f"[DOC RAG FACTORY INFO] Base vetorial Chroma carregada. Coleção '{CHROMA_COLLECTION_NAME_SVC}' com {self.vector_store._collection.count()} itens.")
                self.is_initialized = True
        except Exception as e:
            print(f"[DOC RAG FACTORY ERROR] Falha ao carregar/inicializar ChromaDB: {e}")
            self.vector_store = None

    def get_document_retriever(self, search_type="similarity", k=3):
        """Retorna um retriever baseado na pesquisa vetorial nos documentos."""
        if not self.is_initialized or not self.vector_store:
            print("[DOC RAG FACTORY WARNING] VectorStore (ChromaDB) não disponível. Não é possível criar retriever.")
            return None
        return self.vector_store.as_retriever(search_type=search_type, search_kwargs={'k': k})

    def format_retrieved_documents_for_context(self, documents, max_chars_per_doc=800):
        """Formata os documentos recuperados como uma string de contexto para o LLM."""
        if not documents:
            return "Nenhuma informação relevante encontrada nos documentos indexados para esta query."

        context_parts = []
        for i, doc in enumerate(documents):
            source = doc.metadata.get('source_filename', f"Documento {i+1}")
            content_preview = doc.page_content[:max_chars_per_doc]
            if len(doc.page_content) > max_chars_per_doc:
                content_preview += "..."
            context_parts.append(f"Contexto do Documento '{source}':\n{content_preview}")
        return "\n\n---\n\n".join(context_parts)

    def close(self):
        # ChromaDB não requer um close explícito quando carregado de um diretório persistente
        # A persistência ocorre durante a escrita (from_documents com persist_directory, ou chamando .persist())
        print("[DOC RAG FACTORY INFO] ChromaDB (persistente) não requer close explícito.")