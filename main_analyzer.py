# main_analyzer.py
import os
import time
import beaupy 
import traceback
from typing import Optional, List, Dict, Any, Tuple

# Importar módulos modularizados
import config
import prompts_library as prompts
import ollama_utils
import file_utils
import rag_utils # Apenas o RAG original com ChromaDB
# import rgpd_rag_advanced # <<< REMOVIDO
import interaction_logger_mini

# LlamaIndex Imports (configurados no início do main)
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama 
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
# from qdrant_client import QdrantClient # <<< REMOVIDO (não necessário se Qdrant RAG for removido)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def prompt_user_for_run_mode(all_available_ollama_models: List[str]) -> Optional[Dict[str, Any]]:
    run_choices: Dict[str, Any] = {"models_to_run": [], "use_rag": False, "rag_type": "none", "run_all_models_flag": False}
    print("\n--- Configuração da Execução ---")
    run_all_models_choice = beaupy.confirm("Deseja analisar com TODOS os modelos Ollama disponíveis?", default_is_yes=False, yes_text="Sim, todos", no_text="Não, escolher um")
    run_choices["run_all_models_flag"] = run_all_models_choice
    if run_all_models_choice: run_choices["models_to_run"] = all_available_ollama_models
    else:
        if not all_available_ollama_models: print("[ERROR] Nenhum modelo Ollama disponível."); return None
        selected_single_model = beaupy.select(all_available_ollama_models, cursor="> ", cursor_style="cyan")
        if not selected_single_model: print("Nenhum modelo selecionado."); return None
        run_choices["models_to_run"].append(selected_single_model)

    use_rag_choice = beaupy.confirm("\nDeseja usar RAG (Retrieval Augmented Generation)?", default_is_yes=True, yes_text="Sim", no_text="Não")
    run_choices["use_rag"] = use_rag_choice
    
    if use_rag_choice:
        rag_type_options = [
            "RAG Simples (RGPD ChromaDB + Projeto ChromaDB)",
            "RAG Multi-Query (RGPD ChromaDB + Projeto ChromaDB)",
            # "RAG RGPD (Texto Qdrant - Avançado)" # <<< OPÇÃO REMOVIDA
        ]
        print("\nSelecione o tipo de RAG a utilizar:")
        selected_rag_type_display = beaupy.select(rag_type_options, cursor="> ", cursor_style="green")
        
        if not selected_rag_type_display:
            print("Nenhum tipo de RAG selecionado. RAG será desativado.")
            run_choices["use_rag"] = False; run_choices["rag_type"] = "none"
        elif selected_rag_type_display == rag_type_options[0]: 
            run_choices["rag_type"] = "simple_docs_llamaindex" 
        elif selected_rag_type_display == rag_type_options[1]: 
            run_choices["rag_type"] = "multi_step_qa_llamaindex"
        # elif selected_rag_type_display == rag_type_options[2]: # <<< LÓGICA REMOVIDA
            # run_choices["rag_type"] = "advanced_rgpd_text_qdrant" 
        
        print(f"[INFO] Tipo de RAG selecionado: {run_choices['rag_type']}.")
    else:
        run_choices["rag_type"] = "none"
    return run_choices

def get_context_for_analysis(
    logger_module,
    use_rag_flag: bool, 
    rag_type: str,
    rgpd_index_chroma: Optional[Any], 
    project_docs_index_chroma: Optional[Any], 
    aux_llm_for_chroma_rag: Optional[Ollama],
    # query_engine_advanced_rgpd: Optional[Any], # <<< PARÂMETRO REMOVIDO
    raw_json_str: str, 
    doc_name: str,
) -> str:
    if not use_rag_flag or rag_type == "none":
        return "RAG não solicitado para esta análise."

    if rag_type == "simple_docs_llamaindex" or rag_type == "multi_step_qa_llamaindex":
        if not (rgpd_index_chroma or project_docs_index_chroma):
            return f"Contexto RAG ({rag_type}): Nenhum índice ChromaDB disponível."
        return rag_utils.get_context_with_llamaindex(
            logger_module, True, rag_type,
            rgpd_index_chroma, project_docs_index_chroma,
            aux_llm_for_chroma_rag,
            raw_json_str, doc_name
        )
    # elif rag_type == "advanced_rgpd_text_qdrant": # <<< BLOCO INTEIRO REMOVIDO
        # ...
    else:
        return f"Tipo de RAG desconhecido: {rag_type}."


def run_analysis_for_model(
    model_to_use_main_llm: str, 
    json_files_to_analyze: List[str],
    use_rag_flag: bool, 
    rag_type: str,
    rgpd_index_chroma: Optional[Any], 
    project_docs_index_chroma: Optional[Any], 
    aux_llm_for_chroma_rag: Optional[Ollama],
    # query_engine_advanced_rgpd: Optional[Any], # <<< PARÂMETRO REMOVIDO
    logger_module, 
    analysis_mode_key_for_log: str, 
    current_analysis_description: str
) -> Tuple[int, float, float]:
    model_specific_pipeline_start_time = time.perf_counter()
    print(f"\n--- Iniciando análise com: {current_analysis_description} para o modelo principal {model_to_use_main_llm} ---")
    model_successful_analyses = 0; model_total_llm_processing_time = 0.0
    max_json_bytes = config.MAX_JSON_SIZE_FOR_PROMPT_MB * 1024 * 1024

    if not json_files_to_analyze: 
        model_pipeline_end_time = time.perf_counter(); total_duration = model_pipeline_end_time - model_specific_pipeline_start_time
        logger_module.log_model_run_summary(model_to_use_main_llm, 0,0,total_duration,None); return 0,0.0,total_duration

    for i, json_filepath in enumerate(json_files_to_analyze):
        doc_name = os.path.basename(json_filepath); print(f"\n--- Analisando ficheiro {i+1}/{len(json_files_to_analyze)}: {doc_name} ---"); raw_json_str = ""
        try:
            with open(json_filepath, 'r', encoding='utf-8') as f: raw_json_str = f.read(max_json_bytes)
            if len(raw_json_str) == max_json_bytes and f.tell() < os.path.getsize(json_filepath): print(f"[ANALYSIS WARNING] JSON '{doc_name}' truncado.")
        except Exception as e: print(f"[ANALYSIS ERROR] Ler JSON '{json_filepath}': {e}"); logger_module.log_main_llm_error(doc_name, model_to_use_main_llm, current_analysis_description, "N/A", "File read error", f"File reading error: {e}", None); continue

        actual_rag_context = get_context_for_analysis(
            logger_module, use_rag_flag, rag_type,
            rgpd_index_chroma, project_docs_index_chroma, aux_llm_for_chroma_rag,
            # query_engine_advanced_rgpd, # <<< ARGUMENTO REMOVIDO
            raw_json_str, doc_name
        )
        
        user_template_to_use = prompts.USER_DOC_HOLISTIC_TASK_WITHRAG if use_rag_flag else prompts.USER_DOC_HOLISTIC_TASK_NORAG
        prompt_format_args = {"document_name": doc_name, "raw_json_content": raw_json_str}
        if use_rag_flag and "{additional_rag_context}" in user_template_to_use: prompt_format_args["additional_rag_context"] = actual_rag_context
        try: final_user_prompt_for_llm = user_template_to_use.format(**prompt_format_args)
        except KeyError as e_key: print(f"[ANALYSIS ERROR] Placeholder user_template: {e_key}"); logger_module.log_main_llm_error(doc_name, model_to_use_main_llm, current_analysis_description, "N/A", "Template error", f"UK{e_key}", None); continue
        final_system_prompt_for_llm = prompts.SYSTEM_DOC_HOLISTIC_ASSESSOR
        print(f"[ANALYSIS INFO] Submetendo para LLM principal '{model_to_use_main_llm}' para '{doc_name}'."); start_time_file_llm = time.perf_counter()
        llm_assessment_text, http_status = ollama_utils.call_ollama_generate(model_to_use_main_llm, final_system_prompt_for_llm, final_user_prompt_for_llm, target_doc_name_for_info=f"MainAnalysisFor_{doc_name}")
        end_time_file_llm = time.perf_counter(); file_llm_duration = end_time_file_llm - start_time_file_llm
        print(f"\n[ANALYSIS RESULT] Assessment por '{model_to_use_main_llm}' para '{doc_name}':\n{llm_assessment_text[:1000] + ('...' if len(llm_assessment_text) > 1000 else '')}\n(Time: {logger_module.format_duration(file_llm_duration)})")
        if llm_assessment_text.startswith("Error:"): logger_module.log_main_llm_error(doc_name,model_to_use_main_llm,current_analysis_description,final_system_prompt_for_llm,final_user_prompt_for_llm,llm_assessment_text,http_status)
        else:
            logger_module.log_main_llm_interaction(doc_name,model_to_use_main_llm,current_analysis_description,final_system_prompt_for_llm,final_user_prompt_for_llm,llm_assessment_text)
            if not llm_assessment_text.startswith("Warning:"): model_successful_analyses += 1; model_total_llm_processing_time += file_llm_duration
    
    model_pipeline_end_time = time.perf_counter(); model_total_pipeline_duration_seconds = model_pipeline_end_time - model_specific_pipeline_start_time
    model_avg_time_per_file_seconds = model_total_llm_processing_time / model_successful_analyses if model_successful_analyses > 0 else None
    print(f"\n--- Sumário Modelo: {model_to_use_main_llm} (RAG: {rag_type if use_rag_flag else 'Nenhum'}) ---"); print(f"Ficheiros: {len(json_files_to_analyze)}, Sucessos: {model_successful_analyses}"); print(f"Tempo médio (LLM): {logger_module.format_duration(model_avg_time_per_file_seconds)}"); print(f"Tempo total pipeline: {logger_module.format_duration(model_total_pipeline_duration_seconds)}")
    logger_module.log_model_run_summary(model_to_use_main_llm,len(json_files_to_analyze),model_successful_analyses,model_total_pipeline_duration_seconds,model_avg_time_per_file_seconds)
    if logger_module.current_log_filepath: print(f"Log: {logger_module.current_log_filepath}")
    print(f"--- Fim análise {model_to_use_main_llm} ---\n")
    return model_successful_analyses, model_total_llm_processing_time, model_total_pipeline_duration_seconds

def main():
    overall_pipeline_start_time_global = time.perf_counter()
    print(f"--- Modular PII Analyzer v1.3 (RAG Avançado Removido do Main) ---")
    logger_module = interaction_logger_mini 

    print("\n--- Configurando LlamaIndex Settings Globais ---")
    try:
        Settings.llm = Ollama(model=config.PREFERRED_RAG_AUX_LLM_NAME, request_timeout=120.0)
        print(f"[MAIN INFO] LlamaIndex LLM (Settings.llm) globalmente configurado para: {config.PREFERRED_RAG_AUX_LLM_NAME}")
    except Exception as e_settings_llm:
        print(f"[MAIN CRITICAL ERROR] Falha ao configurar Settings.llm global: {e_settings_llm}"); return 
    try:
        Settings.embed_model = HuggingFaceEmbedding(model_name=config.LLAMA_EMBED_MODEL_NAME)
        print(f"[MAIN INFO] LlamaIndex Embedding Model (Settings.embed_model) globalmente configurado para: {config.LLAMA_EMBED_MODEL_NAME}")
    except Exception as e_settings_embed:
        print(f"[MAIN CRITICAL ERROR] Falha ao configurar Settings.embed_model global: {e_settings_embed}"); return 

    all_available_ollama_models = ollama_utils.list_ollama_models()
    if not all_available_ollama_models: print("[MAIN ERROR] Nenhum modelo Ollama."); return
    all_available_ollama_models.sort()
    run_configuration = prompt_user_for_run_mode(all_available_ollama_models)
    if not run_configuration or not run_configuration["models_to_run"]: print("[MAIN ERROR] Config inválida."); return

    models_to_run_list = run_configuration["models_to_run"]
    use_rag_initial_choice = run_configuration["use_rag"]
    rag_type_initial_choice = run_configuration["rag_type"] # Será 'simple' ou 'multi_step' ou 'none'
    run_all_models_flag = run_configuration["run_all_models_flag"]
    
    json_files_to_analyze = file_utils.get_json_files_from_dir(SCRIPT_DIR, config.DEFAULT_SCHEMA_DIR_NAME)
    if not json_files_to_analyze: print(f"[MAIN ERROR] Nenhum JSON em '{config.DEFAULT_SCHEMA_DIR_NAME}'."); return

    rgpd_index_chroma: Optional[Any] = None
    project_docs_index_chroma: Optional[Any] = None
    aux_llm_for_rag_tasks: Optional[Ollama] = Settings.llm # Usar o LLM global de Settings para tarefas RAG
    
    available_rag_type_active = "none"

    if use_rag_initial_choice and (rag_type_initial_choice == "simple_docs_llamaindex" or rag_type_initial_choice == "multi_step_qa_llamaindex"):
        print("\n--- Inicializando Recursos RAG (ChromaDB) ---")
        print("  Carregando índices ChromaDB...")
        rgpd_index_chroma = rag_utils.load_llamaindex_vector_index(config.RGPD_CHROMA_PERSIST_DIR_NAME, config.RGPD_CHROMA_COLLECTION_NAME, "RGPD ChromaDB Index", SCRIPT_DIR)
        project_docs_index_chroma = rag_utils.load_llamaindex_vector_index(config.PROJECT_DOCS_CHROMA_PERSIST_DIR_NAME, config.PROJECT_DOCS_CHROMA_COLLECTION_NAME, "Project Docs ChromaDB Index", SCRIPT_DIR)
        if rgpd_index_chroma or project_docs_index_chroma:
            available_rag_type_active = rag_type_initial_choice
            if rag_type_initial_choice == "multi_step_qa_llamaindex" and not aux_llm_for_rag_tasks:
                print("[MAIN WARNING] RAG Multi-Query (Chroma) precisa de LLM aux, mas não disponível. Fallback para Simples.")
                available_rag_type_active = "simple_docs_llamaindex"
                if not (rgpd_index_chroma or project_docs_index_chroma): available_rag_type_active = "none"
        else:
            print("[MAIN WARNING] Nenhum índice ChromaDB carregado. RAG ChromaDB não disponível.")
    
    current_use_rag = available_rag_type_active != "none"
    current_rag_type = available_rag_type_active
    
    overall_log_rag_suffix = "norag"
    if current_use_rag:
        if current_rag_type == "simple_docs_llamaindex": overall_log_rag_suffix = "rag_simple_chroma"
        elif current_rag_type == "multi_step_qa_llamaindex": overall_log_rag_suffix = "rag_multistep_chroma"
    
    print(f"\n[MAIN INFO FINAL CONFIG] Modelos: {models_to_run_list}, Usar RAG: {current_use_rag}, Tipo RAG: {current_rag_type}")

    main_user_template = prompts.USER_DOC_HOLISTIC_TASK_WITHRAG if current_use_rag else prompts.USER_DOC_HOLISTIC_TASK_NORAG
    main_system_prompt = prompts.SYSTEM_DOC_HOLISTIC_ASSESSOR

    if run_all_models_flag:
        rag_prompts_header: Dict[str, Optional[str]] = {}
        if current_use_rag and current_rag_type == "multi_step_qa_llamaindex":
            rag_prompts_header["system_subquery_generator"] = prompts.SYSTEM_SUBQUERY_GENERATOR
            rag_prompts_header["user_subquery_generator_template"] = prompts.USER_SUBQUERY_GENERATOR_TEMPLATE
            rag_prompts_header["prompt_answer_subquestion_template"] = prompts.PROMPT_ANSWER_SUBQUESTION_TEMPLATE
        logger_module.initialize_consolidated_log(SCRIPT_DIR, overall_log_rag_suffix, main_system_prompt, 
                                                  main_user_template,  
                                                  rag_prompts_header if rag_prompts_header else None)

    overall_successful_analyses_GLOBAL = 0; overall_llm_time_GLOBAL = 0.0; 
    overall_pipeline_time_GLOBAL_agg = 0.0; models_processed_count_GLOBAL = 0

    # try: # O bloco try/finally para o cliente qdrant não é mais necessário aqui
    for model_idx, current_model_to_run_main_llm in enumerate(models_to_run_list):
        analysis_key_model_log = f"{logger_module._clean_name_for_folder(current_model_to_run_main_llm)}_{overall_log_rag_suffix}"
        analysis_desc_log = f"Análise com {current_model_to_run_main_llm} (RAG: {current_rag_type if current_use_rag else 'Nenhum'})"
        if run_all_models_flag: logger_module.start_model_block_in_consolidated_log(current_model_to_run_main_llm)
        else: logger_module.initialize_logger(current_model_to_run_main_llm, analysis_key_model_log, SCRIPT_DIR)
        print(f"\n======================\nProcessando Modelo {model_idx + 1}/{len(models_to_run_list)}: {current_model_to_run_main_llm}\n{analysis_desc_log}\n======================")
        try:
            successful_count, llm_time_for_model, pipeline_time_for_model = run_analysis_for_model(
                current_model_to_run_main_llm, json_files_to_analyze, 
                current_use_rag, current_rag_type,
                rgpd_index_chroma, project_docs_index_chroma, aux_llm_for_rag_tasks, 
                # query_engine_advanced_rgpd, # <<< ARGUMENTO REMOVIDO
                logger_module, analysis_key_model_log, analysis_desc_log
            )
            overall_successful_analyses_GLOBAL += successful_count; overall_llm_time_GLOBAL += llm_time_for_model
            overall_pipeline_time_GLOBAL_agg += pipeline_time_for_model; models_processed_count_GLOBAL +=1
        except Exception as e_model_loop: print(f"[MAIN ERROR FATAL] Loop modelo '{current_model_to_run_main_llm}': {e_model_loop}"); traceback.print_exc()

    actual_total_pipeline_duration = time.perf_counter() - overall_pipeline_start_time_global
    if run_all_models_flag and models_processed_count_GLOBAL > 0 :
        logger_module.log_overall_consolidated_run_summary(models_processed_count_GLOBAL,len(json_files_to_analyze),overall_successful_analyses_GLOBAL,overall_llm_time_GLOBAL,actual_total_pipeline_duration)
        if logger_module.current_log_filepath: print(f"\nLog consolidado: {logger_module.current_log_filepath}")
    
    # ... (Impressão do sumário global no console como antes)
    if models_processed_count_GLOBAL > 1 or run_all_models_flag : 
        avg_llm_time_str_global = logger_module.format_duration(overall_llm_time_GLOBAL / overall_successful_analyses_GLOBAL if overall_successful_analyses_GLOBAL > 0 else None)
        print("\n\n--- Sumário Global da Execução (Console) ---"); print(f"Modelos processados: {models_processed_count_GLOBAL}"); print(f"Ficheiros JSON configurados: {len(json_files_to_analyze)}"); print(f"Análises LLM bem-sucedidas (total): {overall_successful_analyses_GLOBAL}"); print(f"Tempo médio LLM por ficheiro (global): {avg_llm_time_str_global}"); print(f"Tempo total pipeline (global): {logger_module.format_duration(actual_total_pipeline_duration)}")
    elif models_processed_count_GLOBAL == 1 and not run_all_models_flag: print(f"\nTempo total pipeline (modelo único): {logger_module.format_duration(actual_total_pipeline_duration)}")
    elif models_processed_count_GLOBAL == 0 : print("\nNenhum modelo processado com sucesso."); print(f"Tempo total pipeline: {logger_module.format_duration(actual_total_pipeline_duration)}")
    
    # finally: # <<< BLOCO FINALLY REMOVIDO
        # if qdrant_client_advanced:
            # ... (lógica de fecho do cliente qdrant removida)

    print(f"\n--- Modular PII Analyzer Completo ---")

if __name__ == "__main__":
    main()