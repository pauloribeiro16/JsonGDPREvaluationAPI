# rgpd_rag_advanced.py

import os
import re
import nest_asyncio
import traceback
from typing import List, Dict, Optional, Any

# --- LlamaIndex Core Imports ---
from llama_index.core import Settings, Document, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter 
# from llama_index.core.tools import QueryEngineTool # Não mais necessário para retrieval simples
from llama_index.core.query_engine import RetrieverQueryEngine # Usaremos este diretamente
# from llama_index.core.selectors import LLMSingleSelector # Não mais necessário

# --- LlamaIndex Integration Imports ---
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore

# --- LlamaParse ---
from llama_parse import LlamaParse

# --- Qdrant Client (não do LlamaIndex) ---
from qdrant_client import QdrantClient

# Importar configurações e prompts
import config # Nosso config.py

nest_asyncio.apply()

# --- 1. Configuração Inicial ---
# ... (igual à versão anterior, até ao final da configuração de QDRANT_COLLECTION_NAME)
print("[Advanced RAG INFO] Iniciando configuração...")
if not os.environ.get("LLAMA_CLOUD_API_KEY"):
    print("*"*50); print("ATENÇÃO: LLAMA_CLOUD_API_KEY não está definida."); print("LlamaParse não funcionará. Tentando fallback."); print("*"*50)
try:
    Settings.llm = Ollama(model=config.PREFERRED_RAG_AUX_LLM_NAME, request_timeout=120.0)
    print(f"[Advanced RAG INFO] LlamaIndex LLM: {config.PREFERRED_RAG_AUX_LLM_NAME}")
except Exception as e: print(f"[Advanced RAG ERROR] LLM LlamaIndex: {e}"); Settings.llm = None 
try:
    Settings.embed_model = HuggingFaceEmbedding(model_name=config.LLAMA_EMBED_MODEL_NAME)
    print(f"[Advanced RAG INFO] LlamaIndex Embedding: {config.LLAMA_EMBED_MODEL_NAME}")
except Exception as e: print(f"[Advanced RAG ERROR] Embedding LlamaIndex: {e}"); Settings.embed_model = None
RE_ARTIGO_TITLE_NUM = re.compile(r"Artigo\s*(\d+[A-Za-z]?º?\.?)\s*(?:-|–)?\s*([^\n\r]+)", re.IGNORECASE)
RE_CONSIDERANDO_NUM = re.compile(r"^\s*\((\d+)\)", re.MULTILINE)
SCRIPT_DIR_ADVANCED = os.path.dirname(os.path.abspath(__file__))
RGPD_PDF_FILENAME = "GDPR.pdf" 
RGPD_PDF_PATH = os.path.join(SCRIPT_DIR_ADVANCED, config.RGPD_DOCS_SUBDIR.strip("./"), RGPD_PDF_FILENAME)
QDRANT_PERSIST_PATH = os.path.join(SCRIPT_DIR_ADVANCED, "qdrant_storage_rgpd_advanced")
QDRANT_COLLECTION_NAME = "rgpd_adv_llamaparse_local_v3" # Nome novo para forçar recriação se necessário


def extract_potential_metadata_from_text(text_chunk: str) -> Dict[str, Any]:
    # ... (igual à versão anterior) ...
    metadata: Dict[str, Any] = {}; artigo_match = RE_ARTIGO_TITLE_NUM.search(text_chunk[:300]) 
    if artigo_match: metadata["article_number"] = artigo_match.group(1).replace("º", "").replace(".","").strip(); metadata["article_title"] = artigo_match.group(2).strip(); metadata["type"] = "Artigo"; return metadata 
    considerando_match = RE_CONSIDERANDO_NUM.search(text_chunk[:50]) 
    if considerando_match: metadata["considerando_number"] = considerando_match.group(1); metadata["type"] = "Considerando"; return metadata
    return metadata

def process_documents_from_llamaparse(parsed_documents: List[Document]) -> List[Document]:
    # ... (igual à versão anterior, com sub-chunking) ...
    final_processed_nodes: List[Document] = []; page_offset = 0 
    for i, doc_from_parser in enumerate(parsed_documents):
        print(f"[Advanced RAG INFO] Processando Documento {i+1}/{len(parsed_documents)} do LlamaParse...")
        current_page_number_str = doc_from_parser.metadata.get("page_label", str(page_offset + i + 1))
        try: current_page_number = int(re.search(r'\d+', current_page_number_str).group()) if re.search(r'\d+', current_page_number_str) else page_offset + i + 1
        except: current_page_number = page_offset + i + 1
        base_metadata = {"source_document": "RGPD_LlamaParse", "original_parser_doc_index": i, "page_number": current_page_number}
        structural_metadata_doc = extract_potential_metadata_from_text(doc_from_parser.text); base_metadata.update(structural_metadata_doc)
        doc_from_parser.metadata = base_metadata.copy()
        if len(doc_from_parser.text) > config.RGPD_MAX_CHUNK_SIZE_CHARS * 1.5:
            print(f"  Doc {i+1} (página {current_page_number}) grande ({len(doc_from_parser.text)} chars), sub-chunking...")
            node_parser = SentenceSplitter(chunk_size=config.LLAMA_CHUNK_SIZE, chunk_overlap=config.LLAMA_CHUNK_OVERLAP)
            sub_nodes_text = node_parser.split_text(doc_from_parser.text)
            for sub_idx, text_chunk in enumerate(sub_nodes_text):
                sub_node_metadata = base_metadata.copy(); sub_node_metadata["sub_chunk_index_in_page"] = sub_idx
                specific_sub_chunk_meta = extract_potential_metadata_from_text(text_chunk)
                if specific_sub_chunk_meta.get("type"): sub_node_metadata.update(specific_sub_chunk_meta)
                new_node = Document(text=text_chunk, metadata=sub_node_metadata)
                if new_node.text.strip(): final_processed_nodes.append(new_node)
            print(f"  Criados {len(sub_nodes_text)} sub-nós para a página {current_page_number}.")
        else:
            if doc_from_parser.text.strip(): final_processed_nodes.append(doc_from_parser) 
            else: print(f"  Doc {i+1} (página {current_page_number}) vazio. Ignorando.")
    print(f"[Advanced RAG INFO] Total de nós finais processados: {len(final_processed_nodes)}")
    return final_processed_nodes


def create_and_query_rgpd_simple_retrieval_pipeline(user_query: str, pdf_filepath: str): # Nome da função alterado
    if not Settings.llm or not Settings.embed_model:
        print("[Advanced RAG ERROR] LLM ou Embedding Model não configurado. Abortando.")
        return None

    llama_parsed_documents: Optional[List[Document]] = None
    # ... (Lógica de LlamaParse e fallback para SimpleDirectoryReader igual à anterior) ...
    if os.environ.get("LLAMA_CLOUD_API_KEY"):
        print(f"[Advanced RAG INFO] Iniciando parsing do PDF: {pdf_filepath} com LlamaParse...")
        try:
            parser = LlamaParse(result_type="markdown", verbose=True, language="pt")
            llama_parsed_documents = parser.load_data(pdf_filepath)
            if not llama_parsed_documents: print("[Advanced RAG ERROR] LlamaParse não retornou documentos."); return None
            print(f"[Advanced RAG INFO] LlamaParse retornou {len(llama_parsed_documents)} documentos base.")
        except Exception as e_parse: print(f"[Advanced RAG ERROR] Erro LlamaParse: {e_parse}. Tentando fallback."); llama_parsed_documents = None
    if not llama_parsed_documents:
        print("[Advanced RAG WARNING] LlamaParse não usado/falhou. Usando SimpleDirectoryReader fallback.")
        from llama_index.core import SimpleDirectoryReader
        try:
            fallback_parser = SimpleDirectoryReader(input_files=[pdf_filepath]); llama_parsed_documents = fallback_parser.load_data()
            if not llama_parsed_documents: print("[Advanced RAG ERROR] Fallback SimpleDirectoryReader falhou."); return None
            print(f"[Advanced RAG INFO] Fallback SimpleDirectoryReader carregou {len(llama_parsed_documents)} documento(s) base.")
        except Exception as e_fallback: print(f"[Advanced RAG ERROR] Erro fallback SimpleDirectoryReader: {e_fallback}"); return None

    processed_nodes = process_documents_from_llamaparse(llama_parsed_documents)
    if not processed_nodes: print("[Advanced RAG ERROR] Nenhum nó processado."); return None

    qdrant_client: Optional[QdrantClient] = None
    index: Optional[VectorStoreIndex] = None
    try:
        print(f"[Advanced RAG INFO] Configurando Qdrant Vector Store LOCAL em: {QDRANT_PERSIST_PATH} para coleção: {QDRANT_COLLECTION_NAME}")
        qdrant_client = QdrantClient(path=QDRANT_PERSIST_PATH)
        
        try: # Apagar coleção
            print(f"  Verificando coleção Qdrant '{QDRANT_COLLECTION_NAME}'..."); collections_response = qdrant_client.get_collections()
            collection_exists = any(col.name == QDRANT_COLLECTION_NAME for col in collections_response.collections)
            if collection_exists: print(f"  Apagando coleção Qdrant existente '{QDRANT_COLLECTION_NAME}'..."); qdrant_client.delete_collection(collection_name=QDRANT_COLLECTION_NAME); print(f"  Coleção Qdrant '{QDRANT_COLLECTION_NAME}' apagada.")
            else: print(f"  Coleção Qdrant '{QDRANT_COLLECTION_NAME}' não encontrada. Será criada.")
        except Exception as e_delete_coll: print(f"  Aviso: Não foi possível apagar/verificar coleção Qdrant: {e_delete_coll}")

        vector_store = QdrantVectorStore(client=qdrant_client, collection_name=QDRANT_COLLECTION_NAME)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        print(f"[Advanced RAG INFO] Indexando {len(processed_nodes)} nós no Qdrant (local)...")
        index = VectorStoreIndex(nodes=processed_nodes, storage_context=storage_context, show_progress=True)
        print(f"[Advanced RAG INFO] Indexação no Qdrant (local) concluída.")
    except Exception as e_qdrant:
        print(f"[Advanced RAG ERROR] Erro Qdrant (local): {e_qdrant}"); traceback.print_exc()
        if qdrant_client: qdrant_client.close()
        return None

    if not index: print("[Advanced RAG ERROR] Falha criação índice Qdrant.") 
    if qdrant_client: qdrant_client.close(); return None

    # Criar o retriever
    # Exemplo de filtro: podemos adicionar um filtro aqui se quisermos
    # metadata_filter = {"page_number": 5} # Exemplo: buscar apenas na página 5
    # base_retriever = index.as_retriever(similarity_top_k=5, vector_store_kwargs={"filter": metadata_filter})
    base_retriever = index.as_retriever(similarity_top_k=3) # Ajustar k conforme necessário
    print(f"[Advanced RAG INFO] Base retriever criado com similarity_top_k=3.")

    # Criar o Query Engine diretamente com o retriever
    query_engine = RetrieverQueryEngine(
        retriever=base_retriever,
        # Se quisermos usar o LLM para sintetizar a resposta a partir dos nós recuperados:
        # response_synthesizer = get_response_synthesizer(llm=Settings.llm) # Precisaria de get_response_synthesizer
    )
    print(f"[Advanced RAG INFO] RetrieverQueryEngine criado.")

    print(f"\n[Advanced RAG INFO] Executando query: '{user_query}'")
    response_final = None
    try:
        response_final = query_engine.query(user_query) # Usar o query_engine diretamente
        
        print("\n--- Resposta do Query Engine ---")
        print(str(response_final))
        
        print("\n--- Metadados da Resposta ---") # Não haverá 'selector_result'
        if response_final and response_final.metadata:
            for key, value in response_final.metadata.items():
                print(f"  {key}: {value}")
        else: print("  Sem metadados na resposta.")

        print("\n--- Nós Fonte Recuperados ---")
        if response_final and response_final.source_nodes:
            for i, source_node in enumerate(response_final.source_nodes):
                print(f"  Fonte {i+1} (Score: {source_node.score:.4f}):")
                print(f"    Metadados: {source_node.node.metadata}")
                print(f"    Texto (preview): {source_node.node.text[:350]}...") # Aumentar preview
        else: print("  Nenhum nó fonte na resposta.")
            
    except Exception as e_query:
        print(f"[Advanced RAG ERROR] Erro durante a execução da query: {e_query}")
        traceback.print_exc()
    finally:
        if qdrant_client:
            print("[Advanced RAG INFO] Fechando cliente Qdrant.")
            qdrant_client.close()
        return response_final


if __name__ == "__main__":
    print("[Advanced RAG SCRIPT INFO] Iniciando script de teste do pipeline RAG (Simples Retrieval) para RGPD.")

    if not os.path.exists(RGPD_PDF_PATH):
        print(f"[Advanced RAG ERROR] Ficheiro PDF do RGPD não encontrado em: {RGPD_PDF_PATH}")
    else:
        test_query = "Quais são os princípios relativos ao tratamento de dados pessoais?"
        
        response_object = create_and_query_rgpd_simple_retrieval_pipeline(test_query, RGPD_PDF_PATH) # Nome da função atualizado

        if response_object:
            print("\n[Advanced RAG SCRIPT INFO] Pipeline (Simples Retrieval) executado com sucesso.")
        else:
            print("\n[Advanced RAG SCRIPT INFO] Pipeline (Simples Retrieval) executado com erros ou sem resposta.")