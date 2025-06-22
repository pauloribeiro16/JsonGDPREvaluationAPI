# rag_utils.py
import os
import traceback
from typing import Optional, List, Tuple, Any, Dict

# LlamaIndex Imports
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.schema import NodeWithScore
from llama_index.core.retrievers import BaseRetriever
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage, MessageRole # Para interações com LLM LlamaIndex
import chromadb

# Importar configurações e prompts
import config
import prompts_library as prompts

def load_llamaindex_vector_index(
    persist_dir_name: str, 
    collection_name: str, 
    index_name_for_log: str,
    base_script_dir: str
) -> Optional[VectorStoreIndex]:
    """Carrega um VectorStoreIndex LlamaIndex persistido do ChromaDB."""
    persist_dir_path = os.path.join(base_script_dir, persist_dir_name)

    if not os.path.exists(persist_dir_path):
        print(f"[RAG UTIL CHROMA LOAD ERROR] Diretório '{persist_dir_path}' para '{index_name_for_log}' não encontrado.")
        print(f"  Execute o script de indexação apropriado primeiro.")
        return None
    try:
        print(f"[RAG UTIL CHROMA LOAD INFO] Carregando índice '{index_name_for_log}' de '{persist_dir_path}', coleção '{collection_name}'...")
        chroma_client = chromadb.PersistentClient(path=persist_dir_path)
        try:
            chroma_collection = chroma_client.get_collection(collection_name)
        except Exception as e_get_coll:
            print(f"[RAG UTIL CHROMA LOAD ERROR] Coleção '{collection_name}' não encontrada em '{persist_dir_path}' para '{index_name_for_log}'. {e_get_coll}")
            return None

        if chroma_collection.count() == 0:
            print(f"[RAG UTIL CHROMA LOAD WARNING] Coleção '{collection_name}' em '{persist_dir_path}' para '{index_name_for_log}' está vazia.")
        
        query_embed_model = HuggingFaceEmbedding(model_name=config.LLAMA_EMBED_MODEL_NAME)
        
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(
            vector_store,
            embed_model=query_embed_model
        )
        print(f"[RAG UTIL CHROMA LOAD INFO] Índice '{index_name_for_log}' carregado. {chroma_collection.count()} itens.")
        return index
    except Exception as e:
        print(f"[RAG UTIL CHROMA LOAD ERROR] Falha ao carregar índice LlamaIndex (Chroma) '{index_name_for_log}': {e}")
        traceback.print_exc()
        return None

def generate_privacy_concerns_summary(
    logger_module,
    llm_for_summary: Ollama,
    raw_json_sample: str,
    doc_name: str
) -> str:
    if not llm_for_summary:
        print("[RAG UTIL PRIVACY SUMMARY WARNING] LLM para resumo não disponível.")
        return f"Análise genérica de PII e proteção de dados para o documento '{doc_name}'."

    user_prompt_summary = prompts.USER_PRIVACY_SUMMARY_GENERATOR_TEMPLATE.format(
        #project_context_for_summary=config.PROJECT_CONTEXT_SUMMARY, 
        doc_name=doc_name,
        raw_json_sample=raw_json_sample
    )
    
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=prompts.SYSTEM_PRIVACY_SUMMARY_GENERATOR),
        ChatMessage(role=MessageRole.USER, content=user_prompt_summary)
    ]
    
    print(f"[RAG UTIL PRIVACY SUMMARY] Gerando resumo para '{doc_name}' usando {llm_for_summary.model}...")
    summary = f"Análise de PII para o documento '{doc_name}'." # Fallback
    try:
        response = llm_for_summary.chat(messages)
        summary_content = response.message.content.strip()
        if not summary_content:
            print(f"[RAG UTIL PRIVACY SUMMARY WARNING] LLM ({llm_for_summary.model}) não retornou resumo.")
            summary = f"Falha ao gerar resumo, usando fallback para '{doc_name}'."
        else:
            summary = summary_content
        
        logger_module.log_aux_llm_interaction(
            aux_llm_type_description="RAG - Privacy Summary Gen",
            aux_llm_model_name=llm_for_summary.model,
            target_document_name=doc_name,
            related_sub_task=f"Geração de Resumo de Privacidade para '{doc_name}'",
            system_prompt=prompts.SYSTEM_PRIVACY_SUMMARY_GENERATOR,
            user_prompt=user_prompt_summary,
            raw_llm_output=summary
        )
        print(f"[RAG UTIL PRIVACY SUMMARY] Resumo: {summary}")
        return summary
    except Exception as e:
        print(f"[RAG UTIL PRIVACY SUMMARY ERROR] Falha LLM para resumo: {e}")
        return f"Avaliação de privacidade para '{doc_name}'." # Fallback

def generate_subqueries_with_llamaindex_llm(
    logger_module,
    aux_llm_model: Ollama,
    document_content_excerpt: str,
    document_name: str,
    # project_context_summary é agora de config
    # optional_privacy_concerns_summary: Optional[str] = None, # Se quisermos passar isto
    num_queries: int = config.RAG_NUM_SUBQUERIES
) -> List[str]:
    if not aux_llm_model:
        print("[RAG UTIL SQ GEN WARNING] LLM para sub-perguntas em falta.")
        return []
        
    user_prompt_sq_formatted = prompts.USER_SUBQUERY_GENERATOR_TEMPLATE.format(
        document_name=document_name,
        document_excerpt=document_content_excerpt[:1000],
        num_queries=num_queries,
        #project_context_for_subquery_generation=config.PROJECT_CONTEXT_SUMMARY,
        optional_privacy_concerns_summary_line="" # Omitir por agora, ou passar o resumo
    )
    
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=prompts.SYSTEM_SUBQUERY_GENERATOR),
        ChatMessage(role=MessageRole.USER, content=user_prompt_sq_formatted)
    ]
    print(f"[RAG UTIL SQ GEN] Gerando ~{num_queries} sub-perguntas para '{document_name}' com {aux_llm_model.model}...")
    subqueries_list: List[str] = []
    try:
        response = aux_llm_model.chat(messages)
        subqueries_raw_output = response.message.content

        logger_module.log_aux_llm_interaction(
            aux_llm_type_description="RAG - Sub-Query Generation",
            aux_llm_model_name=aux_llm_model.model,
            target_document_name=document_name,
            related_sub_task=f"Geração de Sub-Perguntas para '{document_name}'",
            system_prompt=prompts.SYSTEM_SUBQUERY_GENERATOR,
            user_prompt=user_prompt_sq_formatted,
            raw_llm_output=subqueries_raw_output if subqueries_raw_output else "N/A"
        )

        if not subqueries_raw_output:
            print(f"[RAG UTIL SQ GEN WARNING] LLM ({aux_llm_model.model}) não retornou output.")
            return []
        subqueries_list = [sq.strip() for sq in subqueries_raw_output.splitlines() if sq.strip() and len(sq.strip()) > 5]
        if not subqueries_list:
            print("[RAG UTIL SQ GEN WARNING] LLM não retornou sub-perguntas válidas.")
            return []
        print(f"[RAG UTIL SQ GEN] {len(subqueries_list)} sub-perguntas: {subqueries_list[:num_queries]}")
        return subqueries_list[:num_queries]
    except Exception as e:
        print(f"[RAG UTIL SQ GEN ERROR] Falha LLM para sub-perguntas: {e}")
        return []

def answer_subquestions_with_llamaindex_rag(
    logger_module,
    retrievers: List[BaseRetriever],
    retriever_names: List[str], # Nomes para logging (ex: "RGPD ChromaDB", "Project Docs ChromaDB")
    aux_llm_model: Ollama,
    subqueries: List[str],
    target_doc_name_main_analysis: str,
    max_chars_per_doc_in_sub_answer_ctx: int = 500
) -> List[Tuple[str, str]]:
    if not retrievers or not aux_llm_model or not subqueries:
        print("[RAG UTIL SUB ANSWER WARNING] Parâmetros em falta.")
        return []

    qa_pairs: List[Tuple[str, str]] = []
    print(f"[RAG UTIL SUB ANSWER] Processando {len(subqueries)} sub-perguntas com {len(retrievers)} retrievers...")

    for i, sub_q_text in enumerate(subqueries):
        print(f"  Sub-pergunta {i+1}/{len(subqueries)}: \"{sub_q_text[:100]}...\"")
        all_retrieved_nodes_for_sub_q: List[NodeWithScore] = []
        
        for retriever_idx, retriever_instance in enumerate(retrievers):
            retriever_name = retriever_names[retriever_idx] if retriever_idx < len(retriever_names) else f"Retriever {retriever_idx+1}"
            retrieved_nodes_from_one: List[NodeWithScore] = []
            try:
                retrieved_nodes_from_one = retriever_instance.retrieve(sub_q_text)
            except Exception as e_retrieve_sub:
                 print(f"    [RAG UTIL SUB ANSWER ERROR] Erro ao recuperar de '{retriever_name}' para '{sub_q_text}': {e_retrieve_sub}")
            
            nodes_info_for_log: List[Dict[str, Any]] = []
            if retrieved_nodes_from_one:
                print(f"    '{retriever_name}' encontrou {len(retrieved_nodes_from_one)} nós.")
                all_retrieved_nodes_for_sub_q.extend(retrieved_nodes_from_one)
                for node_ws in retrieved_nodes_from_one:
                    nodes_info_for_log.append({
                        "metadata": node_ws.node.metadata, "score": node_ws.score,
                        "content_preview": node_ws.node.get_content()[:250]
                    })
            else:
                print(f"    '{retriever_name}' não encontrou nós.")

            logger_module.log_retrieval_query_and_results(
                retriever_name=retriever_name,
                target_document_name=target_doc_name_main_analysis,
                retrieval_query=sub_q_text,
                retrieved_nodes_info=nodes_info_for_log,
                notes=f"Para RAG Multi-Query (ChromaDB), Sub-Pergunta {i+1}/{len(subqueries)}"
            )

        if not all_retrieved_nodes_for_sub_q:
            qa_pairs.append((sub_q_text, "Contexto RAG não encontrou documentos para esta sub-pergunta."))
            continue

        sub_q_retrieved_context_parts = []
        for node_with_score in all_retrieved_nodes_for_sub_q:
            node_content = node_with_score.node.get_content()
            source = node_with_score.node.metadata.get('source_document', node_with_score.node.metadata.get('source_filename', "N/A")) 
            preview = node_content[:max_chars_per_doc_in_sub_answer_ctx] + ("..." if len(node_content) > max_chars_per_doc_in_sub_answer_ctx else "")
            sub_q_retrieved_context_parts.append(f"Fonte '{source}' (Score: {node_with_score.score:.3f}):\n{preview}")
        
        sub_q_final_retrieved_context = "\n\n---\n\n".join(sub_q_retrieved_context_parts)
        user_prompt_for_sub_answer = prompts.PROMPT_ANSWER_SUBQUESTION_TEMPLATE.format(
            retrieved_context_for_subquestion=sub_q_final_retrieved_context,
            sub_question_text=sub_q_text
        )
        
        messages_for_sub_answer = [ChatMessage(role=MessageRole.USER, content=user_prompt_for_sub_answer)]
        answer_text = f"Erro LLM para sub-pergunta." # Fallback
        try:
            response = aux_llm_model.chat(messages_for_sub_answer)
            answer_text_content = response.message.content.strip()
            
            logger_module.log_aux_llm_interaction(
                aux_llm_type_description="RAG - Sub-Question Answering (ChromaDB)",
                aux_llm_model_name=aux_llm_model.model,
                target_document_name=target_doc_name_main_analysis,
                related_sub_task=f"Resposta à Sub-Pergunta '{sub_q_text[:50]}...'",
                system_prompt=None, 
                user_prompt=user_prompt_for_sub_answer,
                raw_llm_output=answer_text_content
            )
            # print(f"    Resposta LLM: \"{answer_text_content[:100]}...\"")
            qa_pairs.append((sub_q_text, answer_text_content))
        except Exception as e_sub_llm:
            print(f"    [RAG UTIL SUB ANSWER LLM ERROR] Erro LLM para sub-pergunta '{sub_q_text}': {e_sub_llm}")
            qa_pairs.append((sub_q_text, answer_text + f" (Erro: {e_sub_llm})"))
            
    return qa_pairs

def format_qa_pairs(qa_pairs_list: List[Tuple[str, str]]) -> str:
    # ... (como antes) ...
    if not qa_pairs_list: return "Nenhum par Pergunta-Resposta gerado."
    formatted_string = "Contexto de Sub-Perguntas e Respostas Intermédias:\n\n"
    for i, (q, a) in enumerate(qa_pairs_list, 1): formatted_string += f"Sub-P {i}: {q}\nResp {i}: {a}\n\n"
    return formatted_string.strip()

def get_context_with_llamaindex(
    logger_module,
    use_rag_flag: bool, # Deveria ser sempre True se esta função é chamada
    rag_type: str, # "simple_docs_llamaindex" ou "multi_step_qa_llamaindex"
    rgpd_index_chroma: Optional[VectorStoreIndex], 
    project_docs_index_chroma: Optional[VectorStoreIndex], 
    aux_llm_for_rag: Optional[Ollama], # LLM para tarefas RAG como resumo ou sub-perguntas
    raw_json_str: str, 
    doc_name: str
) -> str:
    # Esta função é para RAG com ChromaDB.
    # A lógica para RAG Qdrant está em main_analyzer.py -> get_context_for_analysis
    
    if not (rgpd_index_chroma or project_docs_index_chroma):
        return f"Contexto RAG (ChromaDB - {rag_type}): Nenhum índice disponível."

    final_context_parts: List[str] = []

    if rag_type == "simple_docs_llamaindex":
        print(f"[RAG UTIL CHROMA SIMPLE] Obtendo contexto para '{doc_name}'...")
        
        privacy_concerns_summary = f"Análise de PII para '{doc_name}'."
        if aux_llm_for_rag:
            privacy_concerns_summary = generate_privacy_concerns_summary(
                logger_module, aux_llm_for_rag, raw_json_str[:3000], doc_name
            )
        else:
            print("[RAG UTIL CHROMA SIMPLE WARNING] LLM aux não disponível para resumo de privacidade.")

        query_for_rgpd = f"Preocupações de privacidade: '{privacy_concerns_summary}'. Relevância RGPD?"
        query_for_project_docs = f"Documento '{doc_name}', preocupações: '{privacy_concerns_summary}'. Contexto relevante noutros docs do projeto?"
        
        if rgpd_index_chroma:
            retrieved_rgpd_nodes: List[NodeWithScore] = []
            try:
                retriever_rgpd = rgpd_index_chroma.as_retriever(similarity_top_k=config.RAG_K_PER_RETRIEVER_SIMPLE)
                retrieved_rgpd_nodes = retriever_rgpd.retrieve(query_for_rgpd)
            except Exception as e: final_context_parts.append(f"Erro RAG Chroma RGPD: {e}")
            # ... (lógica de formatação e logging para RGPD como em main_analyzer)
            nodes_log_rgpd: List[Dict[str, Any]] = []
            if retrieved_rgpd_nodes: final_context_parts.append("--- Contexto RGPD (ChromaDB) ---")
            for node_ws in retrieved_rgpd_nodes:
                # ... (formatação) ...
                source = node_ws.node.metadata.get('source_document','RGPD_Chroma') + (f" (Art: {node_ws.node.metadata.get('article_number')})" if node_ws.node.metadata.get('article_number') else "")
                final_context_parts.append(f"Fonte '{source}':\n{node_ws.node.get_content()[:700]}...")
                nodes_log_rgpd.append({"metadata":node_ws.node.metadata, "score":node_ws.score, "content_preview":node_ws.node.get_content()[:250]})
            logger_module.log_retrieval_query_and_results("RGPD ChromaDB", doc_name, query_for_rgpd, nodes_log_rgpd, "RAG Simples Chroma")

        if project_docs_index_chroma:
            # ... (lógica similar para project_docs_index_chroma) ...
            retrieved_proj_nodes: List[NodeWithScore] = []
            try:
                retriever_proj = project_docs_index_chroma.as_retriever(similarity_top_k=config.RAG_K_PER_RETRIEVER_SIMPLE)
                retrieved_proj_nodes = retriever_proj.retrieve(query_for_project_docs)
            except Exception as e: final_context_parts.append(f"Erro RAG Chroma Projeto: {e}")
            nodes_log_proj: List[Dict[str, Any]] = []
            if retrieved_proj_nodes: final_context_parts.append("\n--- Contexto Docs Projeto (ChromaDB) ---")
            for node_ws in retrieved_proj_nodes:
                final_context_parts.append(f"Fonte '{node_ws.node.metadata.get('source_filename','Proj_Chroma')}':\n{node_ws.node.get_content()[:700]}...")
                nodes_log_proj.append({"metadata":node_ws.node.metadata, "score":node_ws.score, "content_preview":node_ws.node.get_content()[:250]})
            logger_module.log_retrieval_query_and_results("Projeto ChromaDB", doc_name, query_for_project_docs, nodes_log_proj, "RAG Simples Chroma")
        
        return "\n\n".join(final_context_parts) if final_context_parts else "RAG Simples (ChromaDB): Nenhuma info recuperada."

    elif rag_type == "multi_step_qa_llamaindex":
        print(f"[RAG UTIL CHROMA MULTI-STEP] Iniciando para '{doc_name}'...")
        if not aux_llm_for_rag:
            return "RAG Multi-Step (ChromaDB): LLM auxiliar não configurado."

        active_retrievers: List[BaseRetriever] = []
        active_retriever_names: List[str] = []
        if rgpd_index_chroma:
            active_retrievers.append(rgpd_index_chroma.as_retriever(similarity_top_k=config.RAG_K_PER_RETRIEVER_MULTISTEP))
            active_retriever_names.append("RGPD ChromaDB")
        if project_docs_index_chroma:
            active_retrievers.append(project_docs_index_chroma.as_retriever(similarity_top_k=config.RAG_K_PER_RETRIEVER_MULTISTEP))
            active_retriever_names.append("Projeto ChromaDB")
        
        if not active_retrievers: return "RAG Multi-Step (ChromaDB): Nenhum retriever ativo."

        subqueries = generate_subqueries_with_llamaindex_llm(
            logger_module, aux_llm_for_rag, raw_json_str[:500], doc_name
        )
        if not subqueries: return "RAG Multi-Step (ChromaDB): Falha ao gerar sub-perguntas."

        qa_pairs = answer_subquestions_with_llamaindex_rag(
            logger_module, active_retrievers, active_retriever_names,
            aux_llm_for_rag, subqueries, target_doc_name_main_analysis=doc_name
        )
        if not qa_pairs: return "RAG Multi-Step (ChromaDB): Falha ao gerar respostas para sub-perguntas."
        return format_qa_pairs(qa_pairs)
    else:
        return f"Tipo de RAG (ChromaDB) desconhecido: {rag_type}."

# Para instalar a dependência do ChromaDB para LlamaIndex
# pip install llama-index-vector-stores-chroma