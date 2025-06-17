# index_documents.py
import os
import json
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader, JSONLoader, UnstructuredHTMLLoader # , UnstructuredFileLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()

# Configurações
DOCUMENTS_PATH = "./document"  # <<< CRIE ESTA PASTA E COLOQUE SEUS PDFS, TXTS, JSONS LÁ
CHROMA_PERSIST_DIRECTORY = "./chroma_db_docs"
CHROMA_COLLECTION_NAME = "document_embeddings_minilm"

# Modelo de Embedding
MODEL_NAME = "all-MiniLM-L6-v2"
embedding_function = HuggingFaceEmbeddings(model_name=MODEL_NAME, model_kwargs={'device': 'cpu'})
print(f"Usando Sentence Transformer: {MODEL_NAME}")

# Text Splitter
# Ajuste chunk_size e chunk_overlap conforme necessário para os seus documentos
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

def load_and_split_documents(docs_path):
    all_docs_chunks = []
    supported_extensions = {
        ".pdf": PyPDFLoader,
        ".txt": TextLoader,
        ".json": JSONLoader,
        ".html": UnstructuredHTMLLoader, # <<< LOADER PARA HTML
        ".htm": UnstructuredHTMLLoader, 
    }
    print(f"A carregar documentos de: {docs_path}")
    if not os.path.exists(docs_path):
        print(f"ERRO: Diretório de documentos '{docs_path}' não encontrado.")
        return []

    for filename in os.listdir(docs_path):
        filepath = os.path.join(docs_path, filename)
        if os.path.isfile(filepath):
            ext = os.path.splitext(filename)[1].lower()
            if ext in supported_extensions:
                print(f"  A processar: {filename}")
                try:
                    if ext == ".json":
                        # JSONLoader requer um jq_schema. Para um carregamento genérico de todo o texto:
                        # Pode ser mais simples tratar JSON como texto ou usar uma estratégia específica
                        # Aqui, vamos tentar carregar o conteúdo principal como texto.
                        # Exemplo de jq_schema para extrair todo o conteúdo textual: '.[] | select(type=="string")'
                        # Ou, para extrair tudo: '.' que retorna o JSON inteiro como string (pode precisar de split depois)
                        # A abordagem mais simples para JSON é lê-lo e convertê-lo para string, depois passar para TextSplitter
                        # loader = JSONLoader(file_path=filepath, jq_schema='.', text_content=False) # Carrega metadados
                        # documents = loader.load()
                        # Se quiser todo o conteúdo do JSON como texto para embedding:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            try:
                                data = json.load(f)
                                text_content = json.dumps(data, ensure_ascii=False, indent=2) # Converte todo o JSON em string formatada
                                # Criar um Documento LangChain manualmente
                                from langchain_core.documents import Document
                                documents = [Document(page_content=text_content, metadata={"source": filename, "type": "json"})]
                            except json.JSONDecodeError:
                                print(f"    Aviso: Falha ao fazer parse do JSON {filename}. A tentar como TXT.")
                                loader = TextLoader(filepath, encoding='utf-8')
                                documents = loader.load()

                    else: # PDF, TXT
                        loader_class = supported_extensions[ext]
                        loader = loader_class(filepath)
                        documents = loader.load()

                    if documents:
                        chunks = text_splitter.split_documents(documents)
                        # Adicionar metadados úteis a cada chunk
                        for i, chunk in enumerate(chunks):
                            chunk.metadata["source_filename"] = filename
                            chunk.metadata["chunk_index"] = i
                            chunk.metadata["document_type"] = ext.replace('.', '')
                        all_docs_chunks.extend(chunks)
                        print(f"    {len(documents)} documento(s) carregados, divididos em {len(chunks)} chunks.")
                except Exception as e:
                    print(f"    ERRO ao processar {filename}: {e}")
            else:
                print(f"  A ignorar ficheiro com extensão não suportada: {filename}")

    print(f"\nTotal de chunks gerados de todos os documentos: {len(all_docs_chunks)}")
    return all_docs_chunks


def build_vector_store(documents_chunks):
    if not documents_chunks:
        print("Nenhum chunk de documento para indexar. Abortando a criação da base vetorial.")
        return None

    print(f"\nA construir/atualizar base de dados vetorial Chroma em: {CHROMA_PERSIST_DIRECTORY}")
    print(f"Usando coleção: {CHROMA_COLLECTION_NAME}")

    # Criar ou carregar a coleção ChromaDB
    # O embedding_function é passado aqui para que o Chroma saiba como embutir queries
    # e para verificar a compatibilidade se a coleção já existir.
    vector_db = Chroma.from_documents(
        documents=documents_chunks,
        embedding=embedding_function,
        collection_name=CHROMA_COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIRECTORY
    )
    vector_db.persist() # Garantir que os dados são escritos em disco
    print("Base de dados vetorial Chroma construída e persistida com sucesso.")
    print(f"Total de itens na coleção '{CHROMA_COLLECTION_NAME}': {vector_db._collection.count()}")
    return vector_db

if __name__ == "__main__":
    # 1. Criar a pasta DOCUMENTS_PATH se não existir
    if not os.path.exists(DOCUMENTS_PATH):
        os.makedirs(DOCUMENTS_PATH)
        print(f"Pasta '{DOCUMENTS_PATH}' criada. Adicione os seus ficheiros PDF, TXT, JSON lá.")
        print("Execute este script novamente após adicionar os ficheiros.")
    else:
        # 2. Carregar e dividir os documentos
        chunks = load_and_split_documents(DOCUMENTS_PATH)

        if chunks:
            # 3. Construir a base de dados vetorial
            db = build_vector_store(chunks)
            if db:
                print("\nIndexação concluída.")
                print("Para testar a busca (exemplo):")
                # test_query = "qual é o princípio da limitação das finalidades?"
                # results = db.similarity_search(test_query, k=2)
                # print(f"\nResultados para a query de teste '{test_query}':")
                # for res in results:
                #     print(f"  Fonte: {res.metadata.get('source_filename', 'N/A')}")
                #     print(f"  Conteúdo (preview): {res.page_content[:200]}...")
                #     print("  ---")
        else:
            print("Nenhum documento foi processado para indexação.")