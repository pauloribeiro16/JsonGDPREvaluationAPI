# mini_doc_analyzer.py
import json
import os
import requests # Para call_ollama_generate (LLM Principal)
import time
import beaupy
import re
import traceback

# Importar módulos locais
import interaction_logger_mini
# REMOVER: import document_rag_services as doc_rag

# --- LlamaIndex Imports ---
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama # Para usar LLMs Ollama dentro do LlamaIndex
import chromadb # Cliente ChromaDB

# --- Configurações (Ollama e Diretórios como antes) ---
OLLAMA_API_BASE_URL = "http://localhost:11434/api"
OLLAMA_TAGS_ENDPOINT_SUFFIX = "/tags"
OLLAMA_GENERATE_ENDPOINT_SUFFIX = "/generate"
OLLAMA_REQUEST_TIMEOUT_SECONDS = 360
OLLAMA_KEEP_ALIVE_DURATION = "5m"
PROMPTS_DIR_NAME = "prompts_mini"
DEFAULT_SCHEMA_DIR = "test_schemas"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR_PATH = os.path.join(SCRIPT_DIR, PROMPTS_DIR_NAME)

# --- Configurações LlamaIndex ---
LLAMA_CHROMA_PERSIST_DIR = "./llamaindex_chroma_db_docs" # Deve corresponder ao do script de indexação
LLAMA_CHROMA_COLLECTION_NAME = "llamaindex_doc_embeddings_minilm"
LLAMA_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2" # Deve corresponder

# --- Funções de Interação com Ollama (LLM Principal - call_ollama_generate, list_ollama_models - como antes) ---
def list_ollama_models():
    # (Implementação como antes)
    try:
        response = requests.get(f"{OLLAMA_API_BASE_URL}{OLLAMA_TAGS_ENDPOINT_SUFFIX}", timeout=10)
        response.raise_for_status()
        models_data = response.json()
        available_models = [model["name"] for model in models_data.get("models", [])]
        if not available_models:
            print("[WARNING] No models found via Ollama API. Using a minimal default list.")
            return ["qwen2:0.5b"]
        print(f"[INFO] Successfully fetched {len(available_models)} models from Ollama.")
        return available_models
    except Exception as e:
        print(f"[WARNING] Could not fetch models from Ollama: {e}. Using a minimal default list.")
        return ["qwen2:0.5b"]

def call_ollama_generate(model_name, system_prompt, user_prompt_with_data, target_doc_name_for_info=""):
    # (Implementação como antes)
    payload = { "model": model_name, "system": system_prompt, "prompt": user_prompt_with_data, "stream": True, "keep_alive": OLLAMA_KEEP_ALIVE_DURATION }
    endpoint = f"{OLLAMA_API_BASE_URL}{OLLAMA_GENERATE_ENDPOINT_SUFFIX}"
    full_response_content = []; raw_done_chunk_for_debug = None; http_status = None
    try:
        with requests.post(endpoint, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS, stream=True) as response:
            http_status = response.status_code; response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8', errors='ignore')
                    try:
                        chunk = json.loads(decoded_line)
                        if "response" in chunk and chunk["response"]: full_response_content.append(chunk["response"])
                        if chunk.get("done", False): raw_done_chunk_for_debug = chunk; break
                        if "error" in chunk: return f"Error from Ollama API Stream: {chunk['error']}"
                    except json.JSONDecodeError: pass
                    except Exception as e_chunk: print(f"[ERROR] Proc stream chunk for '{target_doc_name_for_info}': {e_chunk}")
            final_assessment_text = "".join(full_response_content).strip()
            if "<think>" in final_assessment_text: final_assessment_text = re.sub(r"<think>.*?</think>\s*", "", final_assessment_text, flags=re.DOTALL).strip()
            if not final_assessment_text:
                if raw_done_chunk_for_debug and raw_done_chunk_for_debug.get("error"): return f"Error in LLM 'done' signal: {raw_done_chunk_for_debug.get('error')}"
                return "Warning: LLM produced an empty response."
            return final_assessment_text
    except requests.exceptions.HTTPError as http_err: return f"Error: Ollama HTTPError for '{target_doc_name_for_info}': {http_err}. Response: {http_err.response.text[:200] if http_err.response else 'N/A'}"
    except requests.exceptions.RequestException as e: return f"Error: Ollama RequestException for '{target_doc_name_for_info}': {e}"
    except Exception as e_call: return f"Error: Unexpected Ollama call error for '{target_doc_name_for_info}': {e_call}"

# --- Funções Auxiliares (load_prompt_template, get_json_files_from_dir - como antes) ---
def load_prompt_template(prompt_filename):
    # (Implementação como antes)
    filepath = os.path.join(PROMPTS_DIR_PATH, prompt_filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f: return f.read()
    except FileNotFoundError: print(f"[ERROR] Prompt file not found: {filepath}"); return None
    except Exception as e: print(f"[ERROR] Error loading prompt from {filepath}: {e}"); return None

def get_json_files_from_dir(directory_path):
    # (Implementação como antes)
    json_files = []
    if not os.path.isdir(directory_path): print(f"[WARNING] Directory not found: {directory_path}"); return []
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(".json"): json_files.append(os.path.join(directory_path, filename))
    return json_files

# --- Dummy Logger (como antes) ---
class DummyLogger:
    # (Implementação como antes)
    current_log_filepath = None
    def initialize_logger(self, *args, **kwargs): pass
    def log_interaction(self, *args, **kwargs): pass
    def log_error_interaction(self, *args, **kwargs): pass
    def log_run_summary(self, *args, **kwargs): print("[DUMMY LOGGER] Skipping run summary log.")
    def format_duration(self, seconds):
        if seconds is None or seconds < 0: return "N/A"
        if seconds < 60: return f"{seconds:.2f}s"
        minutes = int(seconds // 60); secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    def _clean_name_for_folder(self, name):
        if not name: return "unknown_dummy"
        return re.sub(r'[^\w\-]', '', name.replace(":", "_")) or "cleaned_empty_dummy"

# --- Função de Interação com Utilizador (prompt_user_for_run_mode - como antes) ---
def prompt_user_for_run_mode(all_available_ollama_models):
    # (Implementação como antes, mas adicionando novo tipo de RAG)
    run_choices = {"models_to_run": [], "use_rag": False, "rag_type": "none", "run_all_models_flag": False}
    print("\n--- Configuração da Execução ---")
    run_all_models_choice = beaupy.confirm("Deseja analisar com TODOS os modelos Ollama disponíveis?", default_is_yes=False, yes_text="Sim, todos", no_text="Não, escolher um")
    run_choices["run_all_models_flag"] = run_all_models_choice
    if run_all_models_choice:
        run_choices["models_to_run"] = all_available_ollama_models
        print(f"[INFO] Selecionado: Analisar com todos os {len(all_available_ollama_models)} modelos.")
    else: # Escolher um modelo
        if not all_available_ollama_models: print("[ERROR] Nenhum modelo Ollama disponível."); return None
        selected_single_model = beaupy.select(all_available_ollama_models, cursor="> ", cursor_style="cyan")
        if not selected_single_model: print("Nenhum modelo selecionado."); return None
        run_choices["models_to_run"].append(selected_single_model)
        print(f"[INFO] Selecionado: Analisar com o modelo '{selected_single_model}'.")

    use_rag_choice = beaupy.confirm("\nDeseja usar RAG (Retrieval Augmented Generation)?", default_is_yes=True, yes_text="Sim", no_text="Não")
    run_choices["use_rag"] = use_rag_choice
    print(f"[INFO] Usar RAG: {'Sim' if use_rag_choice else 'Não'}.")

    if use_rag_choice:
        rag_type_options = [
            "RAG Simples (Recuperação de Documentos)",
            "RAG Multi-Query (Decomposição e Respostas Intermédias)" # Novo nome
        ]
        print("\nSelecione o tipo de RAG a utilizar:")
        selected_rag_type_display = beaupy.select(rag_type_options, cursor="> ", cursor_style="green")
        if not selected_rag_type_display:
            print("Nenhum tipo de RAG selecionado. RAG será desativado.")
            run_choices["use_rag"] = False; run_choices["rag_type"] = "none"
        elif selected_rag_type_display == rag_type_options[0]: run_choices["rag_type"] = "simple_docs_llamaindex"
        elif selected_rag_type_display == rag_type_options[1]: run_choices["rag_type"] = "multi_step_qa_llamaindex" # Nova chave interna
        print(f"[INFO] Tipo de RAG selecionado: {run_choices['rag_type']}.")
    else:
        run_choices["rag_type"] = "none"
    return run_choices


# --- Novas Funções RAG com LlamaIndex ---
def load_llamaindex_index(persist_dir, collection_name, embed_model_name_for_query):
    """Carrega um VectorStoreIndex LlamaIndex persistido do ChromaDB."""
    if not os.path.exists(persist_dir):
        print(f"[LlamaIndex LOAD ERROR] Diretório de persistência '{persist_dir}' não encontrado.")
        print("  Execute o script 'index_documents_llamaindex.py' primeiro.")
        return None
    try:
        print(f"[LlamaIndex LOAD INFO] A carregar índice de '{persist_dir}', coleção '{collection_name}'...")
        chroma_client = chromadb.PersistentClient(path=persist_dir)
        chroma_collection = chroma_client.get_collection(collection_name) # get_collection, não get_or_create
        
        # Configurar o modelo de embedding para consulta (deve ser o mesmo da indexação)
        query_embed_model = HuggingFaceEmbedding(model_name=embed_model_name_for_query)
        
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(
            vector_store,
            embed_model=query_embed_model # Importante para queries
        )
        print(f"[LlamaIndex LOAD INFO] Índice carregado com sucesso. {chroma_collection.count()} itens na coleção.")
        return index
    except Exception as e:
        print(f"[LlamaIndex LOAD ERROR] Falha ao carregar índice LlamaIndex/Chroma: {e}")
        print("  Certifique-se que a coleção existe e o modelo de embedding é compatível.")
        return None

def generate_subqueries_with_llamaindex_llm(aux_llm_model: Ollama, # Tipo Ollama do LlamaIndex
                                            system_prompt_sq_gen, user_template_sq_gen,
                                            document_content_excerpt, document_name, project_context_summary,
                                            num_queries=3):
    """Usa um LLM (via LlamaIndex) para gerar sub-perguntas."""
    if not all([aux_llm_model, system_prompt_sq_gen, user_template_sq_gen]):
        print("[SQ GEN LLAMA WARNING] LLM ou prompts para geração de sub-perguntas em falta.")
        return []
    
    user_prompt_sq_formatted = user_template_sq_gen.format(
        document_name=document_name,
        document_excerpt=document_content_excerpt[:1000],
        num_queries=num_queries,
        project_context_summary=project_context_summary
    )
    
    # Formato de mensagem para o LLM do LlamaIndex
    from llama_index.core.llms import ChatMessage, MessageRole
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt_sq_gen),
        ChatMessage(role=MessageRole.USER, content=user_prompt_sq_formatted)
    ]
    
    print(f"[SQ GEN LLAMA] A gerar ~{num_queries} sub-perguntas para '{document_name}' usando {aux_llm_model.model}...")
    try:
        response = aux_llm_model.chat(messages)
        subqueries_raw_output = response.message.content
    except Exception as e:
        print(f"[SQ GEN LLAMA ERROR] Falha ao chamar LLM para sub-perguntas: {e}")
        return []

    if not subqueries_raw_output:
        print(f"[SQ GEN LLAMA WARNING] LLM ({aux_llm_model.model}) não retornou output para sub-perguntas.")
        return []

    subqueries_list = [sq.strip() for sq in subqueries_raw_output.splitlines() if sq.strip() and len(sq.strip()) > 5]
    if not subqueries_list:
        print("[SQ GEN LLAMA WARNING] LLM não retornou sub-perguntas válidas (depois da filtragem).")
        return []
    print(f"[SQ GEN LLAMA] {len(subqueries_list)} sub-perguntas geradas: {subqueries_list[:num_queries]}")
    return subqueries_list[:num_queries]


def answer_subquestions_with_llamaindex_rag(index: VectorStoreIndex, aux_llm_model: Ollama, 
                                           subqueries: list[str], prompt_answer_template: str, 
                                           k_per_query=2, max_chars_per_doc_in_sub_answer_ctx=500):
    """
    Para cada sub-pergunta, recupera contexto e usa um LLM para gerar uma resposta.
    Retorna uma lista de (sub_pergunta, resposta_llm_para_sub_pergunta).
    """
    if not index or not aux_llm_model or not subqueries or not prompt_answer_template:
        print("[SUB ANSWER WARNING] Parâmetros em falta para responder sub-perguntas.")
        return []

    qa_pairs = []
    retriever = index.as_retriever(similarity_top_k=k_per_query)
    print(f"[SUB ANSWER RAG] A processar {len(subqueries)} sub-perguntas...")

    for i, sub_q_text in enumerate(subqueries):
        print(f"  Processando Sub-pergunta {i+1}/{len(subqueries)}: \"{sub_q_text[:100]}...\"")
        try:
            retrieved_nodes = retriever.retrieve(sub_q_text)
            
            if not retrieved_nodes:
                print(f"    Nenhum documento encontrado para a sub-pergunta.")
                qa_pairs.append((sub_q_text, "Contexto RAG não encontrou documentos relevantes para esta sub-pergunta."))
                continue

            # Formatar contexto recuperado para esta sub-pergunta
            sub_q_retrieved_context_parts = []
            for node_with_score in retrieved_nodes:
                node_content = node_with_score.node.get_content()
                source = node_with_score.node.metadata.get('source_filename', f"Fonte Desconhecida")
                preview = node_content[:max_chars_per_doc_in_sub_answer_ctx] + ("..." if len(node_content) > max_chars_per_doc_in_sub_answer_ctx else "")
                sub_q_retrieved_context_parts.append(f"Fonte '{source}':\n{preview}")
            
            sub_q_final_retrieved_context = "\n\n---\n\n".join(sub_q_retrieved_context_parts)

            # Construir prompt para responder à sub-pergunta
            user_prompt_for_sub_answer = prompt_answer_template.format(
                retrieved_context_for_subquestion=sub_q_final_retrieved_context,
                sub_question_text=sub_q_text
            )
            
            # Usar o LLM auxiliar para responder
            from llama_index.core.llms import ChatMessage, MessageRole # Reimportar aqui para clareza
            messages_for_sub_answer = [
                # Poderia ter um system prompt aqui se necessário para o LLM que responde
                ChatMessage(role=MessageRole.USER, content=user_prompt_for_sub_answer)
            ]
            response = aux_llm_model.chat(messages_for_sub_answer)
            answer_text = response.message.content.strip()
            
            print(f"    Resposta LLM à sub-pergunta: \"{answer_text[:100]}...\"")
            qa_pairs.append((sub_q_text, answer_text))

        except Exception as e_sub_ans:
            print(f"    [SUB ANSWER ERROR] Erro ao processar sub-pergunta '{sub_q_text}': {e_sub_ans}")
            qa_pairs.append((sub_q_text, f"Erro ao gerar resposta para esta sub-pergunta: {e_sub_ans}"))
            
    return qa_pairs


def format_qa_pairs(qa_pairs_list: list[tuple[str, str]]):
    """Formata uma lista de tuplos (pergunta, resposta) numa string."""
    if not qa_pairs_list:
        return "Nenhum par de Pergunta-Resposta gerado a partir das sub-perguntas."
    
    formatted_string = "Contexto Gerado a partir de Sub-Perguntas e Respostas Intermédias:\n\n"
    for i, (question, answer) in enumerate(qa_pairs_list, start=1):
        formatted_string += f"Sub-Pergunta {i}: {question}\nResposta Intermédia {i}: {answer}\n\n"
    return formatted_string.strip()


def get_context_with_llamaindex(use_rag_flag, rag_type,
                                llamaindex_index: VectorStoreIndex, # O índice LlamaIndex carregado
                                aux_llm_model_llamaindex: Ollama, # LLM LlamaIndex para tarefas RAG
                                system_subquery_gen_prompt, user_subquery_gen_template, # Para gerar SQs
                                prompt_answer_subquestion_text, # Template para responder SQs
                                raw_json_str, doc_name, project_context_summary,
                                num_subqueries=3, k_per_subquery=2):
    """Orquestra a obtenção de contexto RAG usando LlamaIndex."""
    if not use_rag_flag or rag_type == "none":
        return "RAG não solicitado para esta análise."
    if not llamaindex_index:
        return "Contexto RAG: Índice LlamaIndex não disponível."

    if rag_type == "simple_docs_llamaindex":
        print(f"[RAG SIMPLE LLAMA] A obter contexto para '{doc_name}'...")
        try:
            retriever = llamaindex_index.as_retriever(similarity_top_k=k_per_subquery + 1)
            json_excerpt = raw_json_str[:250]
            simple_query = f"Informação PII e de proteção de dados relevante para o documento '{doc_name}'. Excerto do conteúdo: {json_excerpt}"
            retrieved_nodes = retriever.retrieve(simple_query) # Retorna lista de NodeWithScore
            
            if not retrieved_nodes:
                return "Contexto RAG Simples (LlamaIndex): Nenhum documento relevante encontrado."

            # Formatar os nós recuperados manualmente para contexto bruto
            context_parts = []
            for i, node_ws in enumerate(retrieved_nodes):
                source = node_ws.node.metadata.get('source_filename', f"Documento {i+1}")
                content_preview = node_ws.node.get_content()[:700] # Usar get_content()
                if len(node_ws.node.get_content()) > 700: content_preview += "..."
                context_parts.append(f"Contexto do Documento '{source}':\n{content_preview}")
            return "\n\n---\n\n".join(context_parts)
        except Exception as e:
            return f"Contexto RAG Simples (LlamaIndex): Erro durante a recuperação - {str(e)[:150]}"

    elif rag_type == "multi_step_qa_llamaindex":
        print(f"[RAG MULTI-STEP QA LLAMA] Iniciando para '{doc_name}'...")
        if not aux_llm_model_llamaindex:
            return "Contexto RAG Multi-Step Q&A: LLM auxiliar (LlamaIndex) não configurado."

        # 1. Gerar Sub-Perguntas
        document_content_excerpt_for_sq = raw_json_str[:500]
        subqueries = generate_subqueries_with_llamaindex_llm(
            aux_llm_model_llamaindex, system_subquery_gen_prompt, user_subquery_gen_template,
            document_content_excerpt_for_sq, doc_name, project_context_summary,
            num_queries=num_subqueries
        )
        if not subqueries:
            return "Contexto RAG Multi-Step Q&A: Falha ao gerar sub-perguntas."

        # 2. Responder a cada sub-pergunta usando RAG
        qa_pairs = answer_subquestions_with_llamaindex_rag(
            llamaindex_index, aux_llm_model_llamaindex,
            subqueries, prompt_answer_subquestion_text,
            k_per_query=k_per_subquery
        )
        if not qa_pairs:
            return "Contexto RAG Multi-Step Q&A: Falha ao gerar respostas para sub-perguntas."

        # 3. Formatar os pares Q+A para o LLM principal
        formatted_qa_context = format_qa_pairs(qa_pairs)
        return formatted_qa_context
    else:
        return f"Tipo de RAG (LlamaIndex) desconhecido: {rag_type}."


# --- Função de Análise por Modelo (Atualizada para LlamaIndex) ---
def run_analysis_for_model(model_to_use_main_llm, # Nome do LLM principal (Ollama API direta)
                           json_files_to_analyze,
                           system_prompt_base, user_template_base, project_context,
                           use_rag_flag, rag_type,
                           llamaindex_index: VectorStoreIndex, # Índice LlamaIndex
                           aux_llm_llamaindex: Ollama, # Modelo LlamaIndex.Ollama para tarefas RAG
                           system_subquery_gen_prompt, user_subquery_gen_template, # Para gerar SQs
                           prompt_answer_subquestion_text, # Para responder SQs
                           logger_module, analysis_mode_key_for_log, current_analysis_description):
    # (Início da função como antes, inicializando logger e métricas)
    model_specific_pipeline_start_time = time.perf_counter()
    logger_module.initialize_logger(model_to_use_main_llm, analysis_mode_key_for_log, SCRIPT_DIR)
    print(f"\n--- Iniciando análise com: {current_analysis_description} para o modelo principal {model_to_use_main_llm} ---")
    model_successful_analyses = 0; model_total_llm_processing_time = 0.0
    if not json_files_to_analyze: # ... (retorno como antes)
        model_pipeline_end_time = time.perf_counter()
        logger_module.log_run_summary(0, 0, model_pipeline_end_time - model_specific_pipeline_start_time, None)
        return 0, 0.0

    for i, json_filepath in enumerate(json_files_to_analyze):
        doc_name = os.path.basename(json_filepath)
        print(f"\n--- Analisando ficheiro {i+1}/{len(json_files_to_analyze)}: {doc_name} ---")
        raw_json_str = ""
        # ... (leitura do ficheiro como antes) ...
        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                MAX_JSON_SIZE_PROMPT = 2 * 1024 * 1024; raw_json_str = f.read(MAX_JSON_SIZE_PROMPT)
                if len(raw_json_str) == MAX_JSON_SIZE_PROMPT and f.tell() < os.path.getsize(json_filepath): print(f"[WARNING] Raw JSON for '{doc_name}' was truncated.")
        except Exception as e: print(f"[ERROR] Could not read JSON '{json_filepath}': {e}"); logger_module.log_error_interaction(doc_name, current_analysis_description, "N/A", "File read error", f"File reading error: {e}"); continue

        # Obter contexto RAG usando LlamaIndex
        actual_rag_context = get_context_with_llamaindex(
            use_rag_flag, rag_type,
            llamaindex_index,
            aux_llm_llamaindex, # Passar o modelo LlamaIndex.Ollama
            system_subquery_gen_prompt, user_subquery_gen_template,
            prompt_answer_subquestion_text, # Novo prompt para responder sub-perguntas
            raw_json_str, doc_name, project_context
        )
        
        # Formatar prompts principais (como antes)
        prompt_format_args = {"document_name": doc_name, "raw_json_content": raw_json_str, "project_context_summary": project_context}
        if "{additional_rag_context}" in user_template_base: prompt_format_args["additional_rag_context"] = actual_rag_context
        try:
            final_user_prompt_for_llm = user_template_base.format(**prompt_format_args)
        except KeyError as e_key: print(f"[ERROR] Placeholder user_template: {e_key}"); logger_module.log_error_interaction(doc_name, current_analysis_description, "N/A", "Template error", f"UK{e_key}"); continue
        
        system_prompt_format_args = {
            "document_name": doc_name, "raw_json_content": raw_json_str,
            "project_context_summary": project_context,
            "additional_rag_context": actual_rag_context if use_rag_flag and "{additional_rag_context}" in system_prompt_base else "RAG context not used/applicable in system prompt."
        }
        try:
            final_system_prompt_for_llm = system_prompt_base.format(**system_prompt_format_args)
        except KeyError as e_key_sys:
            print(f"[WARNING] Placeholder system_prompt: {e_key_sys}. Usando parcialmente formatado.")
            temp_sys = system_prompt_base
            for k_s, v_s in system_prompt_format_args.items(): temp_sys = temp_sys.replace("{" + k_s + "}", str(v_s))
            final_system_prompt_for_llm = temp_sys
        except Exception as e_fmt_sys: print(f"[ERROR] Format system_prompt: {e_fmt_sys}"); final_system_prompt_for_llm = system_prompt_base
        
        # Chamada ao LLM Principal (Ollama API direta)
        print(f"[INFO] Submetendo para LLM principal '{model_to_use_main_llm}' para '{doc_name}'.")
        start_time_file_llm = time.perf_counter()
        llm_assessment_text = call_ollama_generate( # Sua função de chamada direta
            model_to_use_main_llm,
            final_system_prompt_for_llm,
            final_user_prompt_for_llm,
            target_doc_name_for_info=f"MainAnalysisFor_{doc_name}"
        )
        # ... (resto da função: logging, cálculo de tempos, sumário do modelo - como antes) ...
        end_time_file_llm = time.perf_counter(); file_llm_duration = end_time_file_llm - start_time_file_llm
        print(f"\n[RESULT] Assessment by '{model_to_use_main_llm}' for '{doc_name}':")
        print(llm_assessment_text[:1000] + ('...' if len(llm_assessment_text) > 1000 else ''))
        print(f"(Time for LLM analysis: {logger_module.format_duration(file_llm_duration)})")
        if llm_assessment_text.startswith("Error:"): logger_module.log_error_interaction(doc_name, current_analysis_description, final_system_prompt_for_llm, final_user_prompt_for_llm, llm_assessment_text)
        else:
            logger_module.log_interaction(doc_name, current_analysis_description, final_system_prompt_for_llm, final_user_prompt_for_llm, llm_assessment_text)
            if not llm_assessment_text.startswith("Warning:"): model_successful_analyses += 1; model_total_llm_processing_time += file_llm_duration
    
    model_pipeline_end_time = time.perf_counter()
    model_total_pipeline_duration_seconds = model_pipeline_end_time - model_specific_pipeline_start_time
    model_avg_time_per_file_seconds = model_total_llm_processing_time / model_successful_analyses if model_successful_analyses > 0 else None
    print(f"\n--- Sumário para Modelo: {model_to_use_main_llm} (RAG: {rag_type if use_rag_flag else 'Nenhum'}) ---")
    # ... (prints do sumário do modelo)
    print(f"Ficheiros processados: {len(json_files_to_analyze)}, Sucessos: {model_successful_analyses}")
    print(f"Tempo médio (LLM): {logger_module.format_duration(model_avg_time_per_file_seconds)}")
    print(f"Tempo total pipeline modelo: {logger_module.format_duration(model_total_pipeline_duration_seconds)}")
    logger_module.log_run_summary(len(json_files_to_analyze), model_successful_analyses, model_total_pipeline_duration_seconds, model_avg_time_per_file_seconds)
    if logger_module.current_log_filepath: print(f"Log: {logger_module.current_log_filepath}")
    print(f"--- Fim da análise com: {model_to_use_main_llm} ---\n")
    return model_successful_analyses, model_total_llm_processing_time


# --- Função Principal (Atualizada para LlamaIndex) ---
def main():
    overall_pipeline_start_time = time.perf_counter()
    print("--- Mini Document PII Analyzer v5 (LlamaIndex RAG) ---")

    logger_module = interaction_logger_mini
    # ... (verificação do logger como antes) ...

    # --- Inicializar LlamaIndex ---
    # Configurar o modelo de embedding globalmente para LlamaIndex (opcional, mas pode simplificar)
    # try:
    #     Settings.embed_model = HuggingFaceEmbedding(model_name=LLAMA_EMBED_MODEL_NAME)
    # except Exception as e_embed_settings:
    #     print(f"[LLAMAINDEX ERROR] Falha ao definir embed_model global: {e_embed_settings}")
    #     print("  RAG com LlamaIndex pode não funcionar. Verifique a instalação de sentence-transformers.")
    #     # Poderia abortar aqui ou tentar continuar sem RAG LlamaIndex
    
    llamaindex_loaded_index = load_llamaindex_index(
        LLAMA_CHROMA_PERSIST_DIR, 
        LLAMA_CHROMA_COLLECTION_NAME,
        LLAMA_EMBED_MODEL_NAME # Passar o nome do modelo para ser usado na consulta
    )
    if not llamaindex_loaded_index:
        print("[WARNING] Índice LlamaIndex não carregado. RAG com LlamaIndex não estará disponível.")
        # Não precisa de rag_factory aqui, LlamaIndex lida com isso internamente

    all_available_ollama_models = list_ollama_models()
    # ... (verificação de all_available_ollama_models como antes) ...

    run_configuration = prompt_user_for_run_mode(all_available_ollama_models)
    # ... (verificação de run_configuration como antes) ...

    models_to_run_list = run_configuration["models_to_run"]
    use_rag = run_configuration["use_rag"]
    rag_type = run_configuration["rag_type"] # ex: "simple_docs_llamaindex", "multi_step_qa_llamaindex"
    run_all_models_flag = run_configuration["run_all_models_flag"]

    print(f"\n[INFO FINAL CONFIG] Modelos: {models_to_run_list}, Usar RAG: {use_rag}, Tipo RAG: {rag_type}")

    project_summary_text = load_prompt_template("project_context_summary.txt")
    # ... (fallback para project_summary_text como antes) ...
    if not project_summary_text: project_summary_text = "Project context: Not available."

    json_files_to_analyze = get_json_files_from_dir(os.path.join(SCRIPT_DIR, DEFAULT_SCHEMA_DIR))
    # ... (verificação de json_files_to_analyze como antes) ...

    user_template_filename = "user_doc_holistic_task_template_WITHRAG_raw.txt" if use_rag else "user_doc_holistic_task_template_NORAG_raw.txt"
    user_template_base_text = load_prompt_template(user_template_filename)
    system_prompt_base_text = load_prompt_template("system_doc_holistic_assessor_raw.txt")

    # Prompts para RAG LlamaIndex
    system_subquery_gen_prompt, user_subquery_gen_template = None, None
    prompt_answer_subquestion_text = None # Novo prompt para responder sub-perguntas
    aux_ollama_llm_for_rag = None # Modelo LlamaIndex.Ollama para tarefas RAG

    if use_rag and (rag_type == "multi_step_qa_llamaindex" or rag_type == "simple_docs_llamaindex"): # Verificar se RAG está ativo
        if not llamaindex_loaded_index:
            print("[ERROR] RAG solicitado mas índice LlamaIndex não carregado. Desativando RAG.")
            use_rag = False
            rag_type = "none"
        else:
            # Configurar LLM auxiliar para LlamaIndex
            PREFERRED_AUX_LLM_NAME = "qwen2:0.5b" # Nome exato do Ollama
            # ... (lógica para encontrar actual_preferred_aux_llm_name como antes) ...
            actual_preferred_aux_llm_name = PREFERRED_AUX_LLM_NAME # Simplificação, assumindo que existe
            # Criar instância do LLM LlamaIndex
            try:
                aux_ollama_llm_for_rag = Ollama(model=actual_preferred_aux_llm_name, request_timeout=120.0)
                print(f"[INFO] LLM auxiliar LlamaIndex ({actual_preferred_aux_llm_name}) configurado para tarefas RAG.")
            except Exception as e_llm_llama:
                print(f"[ERROR] Falha ao configurar LLM LlamaIndex ({actual_preferred_aux_llm_name}): {e_llm_llama}")
                print("        RAG Multi-Step Q&A pode não funcionar. Tentando fallback se possível.")
                aux_ollama_llm_for_rag = None # Anular para que a lógica de fallback seja acionada

            if rag_type == "multi_step_qa_llamaindex":
                if not aux_ollama_llm_for_rag: # Se o LLM auxiliar falhou ao configurar
                    print("[WARNING] LLM Auxiliar para RAG Multi-Step Q&A não disponível. Fazendo fallback para RAG Simples.")
                    rag_type = "simple_docs_llamaindex" # Fallback
                else:
                    system_subquery_gen_prompt = load_prompt_template("system_subquery_generator.txt")
                    user_subquery_gen_template = load_prompt_template("user_subquery_generator_template.txt")
                    prompt_answer_subquestion_text = load_prompt_template("prompt_answer_subquestion_template.txt")
                    if not all([system_subquery_gen_prompt, user_subquery_gen_template, prompt_answer_subquestion_text]):
                        print("[ERROR] Prompts para RAG Multi-Step Q&A em falta. Fazendo fallback para RAG Simples.")
                        rag_type = "simple_docs_llamaindex" # Fallback

    if not system_prompt_base_text or not user_template_base_text:
        # ... (abortar como antes) ...
        print("[ERROR] Ficheiros de prompt base críticos em falta. Abortando.")
        return

    overall_successful_analyses = 0; overall_llm_time = 0.0; models_processed_count = 0

    for model_idx, current_model_to_run_main_llm in enumerate(models_to_run_list):
        # Determinar modo RAG para esta iteração
        current_use_rag = use_rag
        current_rag_type = rag_type

        # Fallbacks se os pré-requisitos RAG não estiverem satisfeitos
        if current_use_rag and not llamaindex_loaded_index:
            print(f"[WARNING] Índice LlamaIndex não disponível. Desativando RAG para {current_model_to_run_main_llm}.")
            current_use_rag = False; current_rag_type = "none"
        
        if current_use_rag and current_rag_type == "multi_step_qa_llamaindex":
            if not aux_ollama_llm_for_rag:
                print(f"[WARNING] LLM auxiliar para RAG Multi-Step não disponível. Fallback para RAG Simples para {current_model_to_run_main_llm}.")
                current_rag_type = "simple_docs_llamaindex"
            elif not all([system_subquery_gen_prompt, user_subquery_gen_template, prompt_answer_subquestion_text]):
                print(f"[WARNING] Prompts para RAG Multi-Step em falta. Fallback para RAG Simples para {current_model_to_run_main_llm}.")
                current_rag_type = "simple_docs_llamaindex"
        
        # Se mesmo RAG Simples não for possível (índice em falta), desativar RAG
        if current_use_rag and current_rag_type == "simple_docs_llamaindex" and not llamaindex_loaded_index:
             print(f"[WARNING] Índice LlamaIndex não disponível para RAG Simples. Desativando RAG para {current_model_to_run_main_llm}.")
             current_use_rag = False; current_rag_type = "none"


        log_rag_suffix = "raw_llamaindex" # Novo default
        if current_use_rag:
            if current_rag_type == "simple_docs_llamaindex": log_rag_suffix = "rag_simple_llama"
            elif current_rag_type == "multi_step_qa_llamaindex": log_rag_suffix = "rag_multistepqa_llama"
        
        analysis_mode_key_for_log = f"{logger_module._clean_name_for_folder(current_model_to_run_main_llm)}_{log_rag_suffix}"
        current_analysis_description = f"Análise com {current_model_to_run_main_llm} (LlamaIndex RAG: {current_rag_type if current_use_rag else 'Nenhum'})"

        print(f"\n======================\nProcessando Modelo {model_idx + 1}/{len(models_to_run_list)}: {current_model_to_run_main_llm}\n{current_analysis_description}\n======================")

        try:
            successful_count, llm_time_for_model = run_analysis_for_model(
                model_to_use_main_llm=current_model_to_run_main_llm,
                json_files_to_analyze=json_files_to_analyze,
                system_prompt_base=system_prompt_base_text,
                user_template_base=user_template_base_text,
                project_context=project_summary_text,
                use_rag_flag=current_use_rag,
                rag_type=current_rag_type,
                llamaindex_index=llamaindex_loaded_index, # Passar o índice
                aux_llm_llamaindex=aux_ollama_llm_for_rag, # Passar o LLM LlamaIndex
                system_subquery_gen_prompt=system_subquery_gen_prompt,
                user_subquery_gen_template=user_subquery_gen_template,
                prompt_answer_subquestion_text=prompt_answer_subquestion_text, # Novo prompt
                logger_module=logger_module,
                analysis_mode_key_for_log=analysis_mode_key_for_log,
                current_analysis_description=current_analysis_description
            )
            overall_successful_analyses += successful_count
            overall_llm_time += llm_time_for_model
            models_processed_count +=1
        except Exception as e_model_loop:
            print(f"[ERROR FATAL] Erro no loop do modelo '{current_model_to_run_main_llm}': {e_model_loop}")
            traceback.print_exc()
            print(f"  A continuar para o próximo modelo, se houver.")

    # Sumário Global Final (como antes)
    # ... (lógica do sumário global)
    overall_pipeline_end_time = time.perf_counter()
    overall_total_pipeline_duration_seconds = overall_pipeline_end_time - overall_pipeline_start_time
    # ... (prints do sumário global)
    if len(models_to_run_list) > 1 or run_all_models_flag:
        print("\n\n--- Sumário Global da Execução (LlamaIndex RAG) ---")
        # ...
    elif models_processed_count == 1:
         print(f"\nTempo total de pipeline (modelo único): {logger_module.format_duration(overall_total_pipeline_duration_seconds)}")
    else:
        print("\nNenhum modelo foi processado.")
        print(f"Tempo total de pipeline: {logger_module.format_duration(overall_total_pipeline_duration_seconds)}")

    # LlamaIndex não tem um .close() explícito para o índice carregado desta forma.
    # O cliente ChromaDB dentro do VectorStore pode precisar ser fechado se fosse gerido manualmente,
    # mas LlamaIndex trata disso.
    print(f"\n--- Mini Analyzer v5 (LlamaIndex RAG) Completo ---")

if __name__ == "__main__":
    main()