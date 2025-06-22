# index_rgpd_llamaindex.py
import os
import re
import logging
import sys
from typing import List, Dict, Optional

from llama_index.core.schema import TextNode
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb
from pypdf import PdfReader # Usaremos pypdf em vez de PyPDF2

# Configurar logging básico
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configurações ---
RGPD_DOCUMENT_PATH = "./document/GDPR/"  # Pasta onde o PDF do RGPD estará
# Assume que haverá apenas um PDF principal do RGPD nesta pasta
# ou que podemos identificar o ficheiro correto.
# Para simplificar, vamos assumir que se chama "GDPR_PT.pdf" ou similar.
# Poderíamos adicionar lógica para encontrar o PDF automaticamente.

RGPD_CHROMA_PERSIST_DIR = "./llamaindex_chroma_db_rgpd" # NOVO diretório para o DB do RGPD
RGPD_CHROMA_COLLECTION_NAME = "rgpd_structured_minilm"

# Modelo de Embedding (mesmo que o outro script para consistência)
LLAMA_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Configurações de Chunking Estrutural para o RGPD
# MAX_CHUNK_SIZE em caracteres. Ajuste conforme necessário.
# O objetivo é que cada chunk caiba no modelo de embedding e seja semanticamente útil.
RGPD_MAX_CHUNK_SIZE = 1800  # Sugestão baseada na nossa discussão
RGPD_CHUNK_OVERLAP = 150 # Pequena sobreposição para sub-chunks do mesmo Artigo/Considerando

# Regex para identificar estruturas no RGPD (Português)
# Estes podem precisar de ajuste fino dependendo do formato exato do PDF.
RE_CONSIDERANDO = re.compile(r"\((\d+)\)\s+([\s\S]+?)(?=(?:\(\d+\)\s)|(?:Artigo\s\d+)|(?:CAPÍTULO)|(?:SECÇÃO)|(?:TÍTULO\s+[IVXLCDM]+))", re.IGNORECASE)
RE_ARTIGO = re.compile(r"Artigo\s*(\d+[A-Za-z]?º?\.?)\s*(?:-|–)?\s*([^\n\r]+)([\s\S]+?)(?=(?:Artigo\s*\d+)|(?:CAPÍTULO)|(?:SECÇÃO)|(?:TÍTULO\s+[IVXLCDM]+)|(?:FIM DO DOCUMENTO))", re.IGNORECASE)
# Regex para parágrafos (ex: "1.", "2. ") e alíneas (ex: "a)", "b) ")
RE_PARAGRAFO = re.compile(r"^\s*(\d+)\.\s+([\s\S]+?)(?=(?:\s*\d+\.\s)|(?:^\s*[a-z]\)\s)|(?:Artigo)|$)", re.MULTILINE)
RE_ALINEA = re.compile(r"^\s*([a-z])\)\s+([\s\S]+?)(?=(?:\s*[a-z]\)\s)|(?:^\s*\d+\.\s)|(?:Artigo)|$)", re.MULTILINE)

def extract_text_from_pdf(pdf_filepath: str) -> str:
    """Extrai texto de um ficheiro PDF."""
    logger.info(f"A extrair texto de: {pdf_filepath}")
    if not os.path.exists(pdf_filepath):
        logger.error(f"Ficheiro PDF não encontrado: {pdf_filepath}")
        return ""
    
    reader = PdfReader(pdf_filepath)
    text = ""
    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n" # Adicionar nova linha entre páginas
            else:
                logger.warning(f"Nenhum texto extraído da página {page_num + 1} de {pdf_filepath}")
        except Exception as e:
            logger.error(f"Erro ao extrair texto da página {page_num + 1} de {pdf_filepath}: {e}")
    logger.info(f"Texto extraído com {len(text)} caracteres.")
    return text

def create_rgpd_nodes(full_text: str) -> List[TextNode]:
    """
    Cria TextNodes estruturados a partir do texto completo do RGPD.
    Implementa a lógica de chunking: Considerando, Artigo -> Parágrafo -> Alínea.
    """
    nodes: List[TextNode] = []
    
    # Adicionar um marcador de fim para ajudar os regex a capturar o último elemento
    safe_full_text = full_text + "\nFIM DO DOCUMENTO"

    # 1. Processar Considerandos
    logger.info("A processar Considerandos...")
    last_considerando_end = 0
    for match_c in RE_CONSIDERANDO.finditer(safe_full_text):
        num_considerando = match_c.group(1)
        content_considerando = match_c.group(2).strip()
        last_considerando_end = match_c.end()

        if not content_considerando:
            logger.warning(f"Considerando {num_considerando} sem conteúdo.")
            continue

        metadata_base = {
            "source_document": "RGPD",
            "type": "Considerando",
            "considerando_number": num_considerando,
        }
        
        if len(content_considerando) <= RGPD_MAX_CHUNK_SIZE:
            nodes.append(TextNode(text=content_considerando, metadata=metadata_base.copy()))
        else:
            # Subdividir Considerandos longos (raro, mas possível) por frases ou parágrafos simples
            # Para simplificar, vamos usar uma divisão mais básica aqui ou apenas avisar
            # Poderíamos usar SentenceSplitter aqui se necessário
            logger.warning(f"Considerando {num_considerando} é muito longo ({len(content_considerando)} chars). "
                           f"Será dividido de forma simples ou pode precisar de melhor chunking.")
            # Exemplo de subdivisão simples (pode ser melhorado com SentenceSplitter)
            start = 0
            part_num = 1
            while start < len(content_considerando):
                end = start + RGPD_MAX_CHUNK_SIZE
                chunk_text = content_considerando[start:end]
                meta_part = metadata_base.copy()
                meta_part["part_number"] = part_num
                nodes.append(TextNode(text=chunk_text, metadata=meta_part))
                start = end - RGPD_CHUNK_OVERLAP # Aplicar overlap
                if start < 0: start = 0 # Evitar start negativo
                part_num +=1

    logger.info(f"Processados {len(nodes)} nós de Considerandos.")

    # Encontrar o início dos Artigos (após os considerandos)
    # Heurística: procurar "Artigo 1" ou "CAPÍTULO I" após o último considerando.
    # Isto pode precisar de ajuste se a estrutura do PDF for diferente.
    start_of_articles_text = safe_full_text[last_considerando_end:]
    
    # 2. Processar Artigos
    logger.info("A processar Artigos...")
    initial_node_count = len(nodes)
    for match_a in RE_ARTIGO.finditer(start_of_articles_text):
        num_artigo = match_a.group(1).replace("º", "").replace(".","").strip() # Limpar "1º." para "1"
        titulo_artigo = match_a.group(2).strip()
        content_artigo_full = match_a.group(3).strip()

        if not content_artigo_full:
            logger.warning(f"Artigo {num_artigo} sem conteúdo principal.")
            continue

        metadata_artigo_base = {
            "source_document": "RGPD",
            "type": "Artigo",
            "article_number": num_artigo,
            "article_title": titulo_artigo,
        }

        if len(content_artigo_full) <= RGPD_MAX_CHUNK_SIZE:
            nodes.append(TextNode(text=content_artigo_full, metadata=metadata_artigo_base.copy()))
        else:
            # Subdividir Artigo por Parágrafos
            par_num = 0
            for match_p in RE_PARAGRAFO.finditer(content_artigo_full):
                par_num_text = match_p.group(1) # Este é o número do parágrafo, ex: "1"
                content_paragrafo = match_p.group(2).strip()
                
                metadata_par = metadata_artigo_base.copy()
                metadata_par["paragraph_number"] = par_num_text
                
                if len(content_paragrafo) <= RGPD_MAX_CHUNK_SIZE:
                    nodes.append(TextNode(text=content_paragrafo, metadata=metadata_par))
                else:
                    # Subdividir Parágrafo por Alíneas
                    alinea_char_code = ord('a') # para iterar a, b, c...
                    for match_al in RE_ALINEA.finditer(content_paragrafo):
                        alinea_letra = match_al.group(1)
                        content_alinea = match_al.group(2).strip()
                        
                        metadata_al = metadata_par.copy()
                        metadata_al["alinea_letter"] = alinea_letra
                        
                        # Mesmo que a alínea seja muito longa, por agora criamos um nó.
                        # Poderia ser adicionado um SentenceSplitter aqui para maior granularidade.
                        if len(content_alinea) > RGPD_MAX_CHUNK_SIZE:
                             logger.warning(f"Artigo {num_artigo}, Par. {par_num_text}, Alínea {alinea_letra} "
                                           f"é longa ({len(content_alinea)} chars).")
                        
                        nodes.append(TextNode(text=content_alinea, metadata=metadata_al))
                        alinea_char_code +=1
                    
                    # Se não houve match de alíneas mas o parágrafo era longo, tratar o parágrafo como um todo (ou dividir por frases)
                    if not list(RE_ALINEA.finditer(content_paragrafo)) and len(content_paragrafo) > RGPD_MAX_CHUNK_SIZE:
                        logger.warning(f"Artigo {num_artigo}, Par. {par_num_text} é longo ({len(content_paragrafo)} chars) "
                                       f"e não foi dividido por alíneas. Será um nó único grande.")
                        nodes.append(TextNode(text=content_paragrafo, metadata=metadata_par))


            # Se não houve match de parágrafos mas o artigo era longo, tratar o artigo como um todo (ou dividir por frases)
            if not list(RE_PARAGRAFO.finditer(content_artigo_full)) and len(content_artigo_full) > RGPD_MAX_CHUNK_SIZE:
                logger.warning(f"Artigo {num_artigo} ({titulo_artigo}) é longo ({len(content_artigo_full)} chars) "
                               f"e não foi dividido por parágrafos. Será um nó único grande.")
                nodes.append(TextNode(text=content_artigo_full, metadata=metadata_artigo_base.copy()))

    logger.info(f"Processados {len(nodes) - initial_node_count} nós de Artigos.")
    logger.info(f"Total de nós criados para o RGPD: {len(nodes)}")
    return nodes


def create_rgpd_vector_store():
    logger.info(f"[RGPD Indexer INFO] Iniciando processo de indexação do RGPD.")
    logger.info(f"  Diretório do documento RGPD: {RGPD_DOCUMENT_PATH}")
    logger.info(f"  Diretório de persistência ChromaDB: {RGPD_CHROMA_PERSIST_DIR}")
    logger.info(f"  Nome da coleção ChromaDB: {RGPD_CHROMA_COLLECTION_NAME}")

    if not os.path.exists(RGPD_DOCUMENT_PATH):
        os.makedirs(RGPD_DOCUMENT_PATH)
        logger.warning(f"Diretório de documentos do RGPD '{RGPD_DOCUMENT_PATH}' não existia e foi criado.")
        logger.warning("  Adicione o ficheiro PDF do RGPD lá (ex: GDPR_PT.pdf) e execute este script novamente.")
        return None

    # Encontrar o ficheiro PDF do RGPD na pasta especificada
    pdf_files = [f for f in os.listdir(RGPD_DOCUMENT_PATH) if f.lower().endswith(".pdf")]
    if not pdf_files:
        logger.error(f"Nenhum ficheiro PDF encontrado em '{RGPD_DOCUMENT_PATH}'.")
        return None
    if len(pdf_files) > 1:
        logger.warning(f"Múltiplos ficheiros PDF encontrados em '{RGPD_DOCUMENT_PATH}'. A usar o primeiro: {pdf_files[0]}")
    
    rgpd_pdf_filepath = os.path.join(RGPD_DOCUMENT_PATH, pdf_files[0])

    # 1. Extrair Texto do PDF
    full_rgpd_text = extract_text_from_pdf(rgpd_pdf_filepath)
    if not full_rgpd_text:
        logger.error("Nenhum texto extraído do PDF do RGPD. Abortando.")
        return None

    # 2. Criar Nós Estruturados
    rgpd_nodes = create_rgpd_nodes(full_rgpd_text)
    if not rgpd_nodes:
        logger.warning("Nenhum nó criado a partir do texto do RGPD. Verifique os regex e o conteúdo do PDF.")
        return None
    logger.info(f"{len(rgpd_nodes)} nós estruturados criados para o RGPD.")

    # 3. Configurar Modelo de Embedding
    logger.info(f"A configurar modelo de embedding: {LLAMA_EMBED_MODEL_NAME}")
    try:
        embed_model = HuggingFaceEmbedding(model_name=LLAMA_EMBED_MODEL_NAME, device="cpu")
    except Exception as e:
        logger.error(f"Erro ao inicializar modelo de embedding: {e}")
        return None

    # 4. Configurar ChromaDB como VectorStore
    logger.info(f"A configurar ChromaDB em: {RGPD_CHROMA_PERSIST_DIR}, coleção: {RGPD_CHROMA_COLLECTION_NAME}")
    if not os.path.exists(RGPD_CHROMA_PERSIST_DIR):
        os.makedirs(RGPD_CHROMA_PERSIST_DIR)

    try:
        chroma_client = chromadb.PersistentClient(path=RGPD_CHROMA_PERSIST_DIR)
        # Apagar coleção antiga se existir, para garantir que estamos a indexar de novo.
        # Cuidado: isto apaga dados existentes! Comente se quiser adicionar incrementalmente (mais complexo).
        try:
            logger.info(f"A tentar apagar coleção existente '{RGPD_CHROMA_COLLECTION_NAME}' para reindexação...")
            chroma_client.delete_collection(RGPD_CHROMA_COLLECTION_NAME)
            logger.info(f"Coleção '{RGPD_CHROMA_COLLECTION_NAME}' apagada com sucesso.")
        except Exception: # chromadb.api.errors.CollectionNotFoundError ou similar
            logger.info(f"Coleção '{RGPD_CHROMA_COLLECTION_NAME}' não encontrada para apagar, será criada.")
            pass # Coleção não existe, o que é bom para get_or_create_collection

        chroma_collection = chroma_client.get_or_create_collection(RGPD_CHROMA_COLLECTION_NAME)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    except Exception as e:
        logger.error(f"Erro ao configurar ChromaVectorStore para RGPD: {e}")
        return None

    # 5. Criar o StorageContext
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # 6. Criar o Índice a partir dos Nós
    # Não precisamos de `transformations` aqui porque já fizemos o chunking manual.
    logger.info(f"A criar ou atualizar o VectorStoreIndex para o RGPD a partir de {len(rgpd_nodes)} nós...")
    try:
        index = VectorStoreIndex(
            nodes=rgpd_nodes, # Passamos os nós diretamente
            storage_context=storage_context,
            embed_model=embed_model,
            show_progress=True
        )
        logger.info(f"Indexação do RGPD concluída. Índice com {len(index.docstore.docs)} nós base.")
        logger.info(f"  Coleção Chroma '{RGPD_CHROMA_COLLECTION_NAME}' agora tem {chroma_collection.count()} embeddings.")
        logger.info(f"Índice LlamaIndex para RGPD com ChromaDB persistido/atualizado em '{RGPD_CHROMA_PERSIST_DIR}'.")
        return index
    except Exception as e:
        logger.error(f"Erro ao criar o VectorStoreIndex para o RGPD: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Configurar logging para ver mais detalhes do LlamaIndex durante a indexação
    # logging.getLogger('llama_index').setLevel(logging.DEBUG) # Para LlamaIndex
    
    index = create_rgpd_vector_store()

    if index:
        logger.info("\n[RGPD Indexer SUCCESS] Indexação do RGPD com LlamaIndex e ChromaDB concluída.")
        # Exemplo de como testar (opcional)
        try:
            logger.info("\n[RGPD Indexer TEST] A testar uma query de similaridade no índice do RGPD...")
            retriever = index.as_retriever(similarity_top_k=2)
            # Tente uma query que seja relevante para um Artigo ou Considerando específico
            test_query_text = "Quais são os princípios relativos ao tratamento de dados pessoais?"
            # Ou "O que diz o Artigo 5 sobre tratamento de dados?"
            retrieved_nodes = retriever.retrieve(test_query_text)
            if retrieved_nodes:
                logger.info(f"  Resultados para a query de teste '{test_query_text}':")
                for i, node_with_score in enumerate(retrieved_nodes):
                    node = node_with_score.node
                    logger.info(f"  Resultado {i+1} (Score: {node_with_score.score:.4f}):")
                    logger.info(f"    Metadados: {node.metadata}")
                    logger.info(f"    Conteúdo (preview): {node.get_content()[:250]}...")
            else:
                logger.info("  Nenhum resultado encontrado para a query de teste no índice do RGPD.")
        except Exception as e_query:
            logger.error(f"[RGPD Indexer TEST ERROR] Erro ao testar query: {e_query}")
    else:
        logger.error("\n[RGPD Indexer FAIL] Processo de indexação do RGPD falhou.")