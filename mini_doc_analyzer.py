# mini_doc_analyzer_v2.py
import json
import os
import requests
import time
import beaupy # pip install beaupy
import interaction_logger_mini

# --- Configurações ---
OLLAMA_API_BASE_URL = "http://localhost:11434/api"
OLLAMA_TAGS_ENDPOINT_SUFFIX = "/tags"
OLLAMA_GENERATE_ENDPOINT_SUFFIX = "/generate"
OLLAMA_REQUEST_TIMEOUT_SECONDS = 1660 
OLLAMA_KEEP_ALIVE_DURATION = "5m"
PROMPTS_DIR_NAME = "prompts_mini"
DEFAULT_SCHEMA_DIR = "test_schemas" # Continua a ser a pasta para os JSONs brutos

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR_PATH = os.path.join(SCRIPT_DIR, PROMPTS_DIR_NAME)

# --- Funções de Interação com Ollama ---
def list_ollama_models():
    # (Como antes)
    try:
        response = requests.get(f"{OLLAMA_API_BASE_URL}{OLLAMA_TAGS_ENDPOINT_SUFFIX}", timeout=10)
        response.raise_for_status()
        models_data = response.json()
        available_models = [model["name"] for model in models_data.get("models", [])]
        if not available_models:
            print("[WARNING] No models found via Ollama API. Using a minimal default list.")
            return ["gemma:2b"] 
        print(f"[INFO] Successfully fetched {len(available_models)} models from Ollama.")
        return available_models
    except Exception as e:
        print(f"[WARNING] Could not fetch models from Ollama: {e}. Using a minimal default list.")
        return ["gemma:2b"] 

# MODIFICADO: analysis_mode não é mais um parâmetro variável aqui, é sempre "Raw JSON Analysis"
def call_ollama_generate(model_name, system_prompt, user_prompt_with_data, target_doc_name):
    payload = {
        "model": model_name, "system": system_prompt, "prompt": user_prompt_with_data,
        "template": "{{ .System }}\n\n{{ .Prompt }}", "stream": True, 
        "keep_alive": OLLAMA_KEEP_ALIVE_DURATION
    }
    endpoint = f"{OLLAMA_API_BASE_URL}{OLLAMA_GENERATE_ENDPOINT_SUFFIX}"
    
    analysis_mode_description_fixed = "Raw JSON Analysis" # Já que o modo é fixo
    print(f"\n[INFO] Analyzing '{target_doc_name}' ({analysis_mode_description_fixed}) with Ollama ({model_name}). Streaming response...")
    
    full_response_content = []
    final_response_metrics = {} 
    http_status = None
    raw_error_output_for_log = "Error: LLM Call did not produce parsable stream."

    try:
        with requests.post(endpoint, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS, stream=True) as response:
            http_status = response.status_code
            response.raise_for_status() 
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        if "response" in chunk and chunk["response"]:
                            token = chunk["response"]
                            full_response_content.append(token)
                        if chunk.get("done", False):
                            final_response_metrics = chunk 
                            break 
                        if "error" in chunk:
                            error_msg = f"Ollama API Stream Error: {chunk['error']}"
                            print(f"\n[ERROR] {error_msg}")
                            raw_error_output_for_log = json.dumps(chunk)
                            interaction_logger_mini.log_error_interaction(
                                target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data, 
                                error_msg, http_status
                            )
                            return f"Error from Ollama API Stream: {chunk['error']}"
                    except json.JSONDecodeError:
                        print(f"\n[WARNING] Non-JSON line in stream: {line}")
                        raw_error_output_for_log += f"\nNon-JSON line: {line.decode('utf-8', errors='ignore')}"
                    except Exception as e_chunk:
                        print(f"\n[ERROR] Error processing stream chunk: {e_chunk} - Chunk: {line}")
                        raw_error_output_for_log += f"\nError processing chunk: {e_chunk} - Chunk: {line.decode('utf-8', errors='ignore')}"
            
            # DEBUG: Para ver o que foi realmente coletado ANTES do strip()
            # print(f"[DEBUG STREAM CONTENT] Raw collected content for '{target_doc_name}': {full_response_content}")

            final_assessment_text = "".join(full_response_content).strip()

            if not final_assessment_text and not final_response_metrics.get("error"):
                # Se não houve conteúdo mas também não houve erro explícito no stream "done"
                if not final_response_metrics: 
                     error_msg = "Empty response from LLM and no 'done' signal or metrics received from stream."
                     print(f"\n[ERROR] {error_msg}")
                     interaction_logger_mini.log_error_interaction(
                        target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data, 
                        error_msg, http_status
                     )
                     return "Error: Empty response and no metrics from LLM stream."
                # Se houve "done" mas sem "response", e o eval_count for baixo (como 1)
                eval_count = final_response_metrics.get("eval_count", 0)
                if eval_count <= 1: # Ajuste este limiar se necessário
                    final_assessment_text = f"Warning: LLM produced a minimal response (eval_count: {eval_count}). Possible empty or whitespace-only output."
                else:
                    final_assessment_text = "Warning: LLM produced an empty response despite no explicit error."


            # MODIFICADO: Remover Stream Metrics do log
            interaction_logger_mini.log_interaction(
                target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data, 
                final_assessment_text 
            )
            return final_assessment_text
            
    # ... (blocos except como antes) ...
    except requests.exceptions.HTTPError as http_err:
        error_msg = f"Ollama request failed with HTTPError: {http_err}. Response: {response.text[:500] if response else 'No response object'}"
        print(f"\n[ERROR] {error_msg}")
        raw_error_output_for_log = response.text[:500] if response else "No response object"
        interaction_logger_mini.log_error_interaction(
            target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data, 
            error_msg, http_status
        )
        return f"Error: Ollama request failed - {http_err}"
    except requests.exceptions.RequestException as e:
        error_msg = f"Ollama request failed: {e}"
        print(f"\n[ERROR] {error_msg}")
        raw_error_output_for_log = str(e)
        interaction_logger_mini.log_error_interaction(
            target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data, 
            error_msg, getattr(e.response, 'status_code', None)
        )
        return f"Error: Ollama request failed - {e}"
    except Exception as e_call:
        error_msg = f"An unexpected error occurred during Ollama stream call: {e_call}"
        print(f"\n[ERROR] {error_msg}")
        raw_error_output_for_log = str(e_call)
        interaction_logger_mini.log_error_interaction(
            target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data, 
            error_msg
        )
        return f"Error: An unexpected error occurred - {e_call}"

# --- Funções de Schema REMOVIDAS ---
# load_and_resolve_schema
# _extract_properties_recursive
# get_all_properties_with_descriptions

# --- Funções Auxiliares (como antes, mas load_prompt_template será simplificado) ---
def load_prompt_template(prompt_filename): # Simplificado, pois só carregamos os prompts 'raw'
    filepath = os.path.join(PROMPTS_DIR_PATH, prompt_filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"[ERROR] Prompt file not found: {filepath}")
        return None
    except Exception as e:
        print(f"[ERROR] Error loading prompt from {filepath}: {e}")
        return None

def get_json_files_from_dir(directory_path):
    # (Como antes)
    json_files = []
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(".json"):
            json_files.append(os.path.join(directory_path, filename))
    return json_files

def format_duration(seconds):
    # (Como antes)
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"

# --- Dummy Logger para Fallback (como antes) ---
class DummyLogger:
    current_log_filepath = None
    def initialize_logger(self, *args, **kwargs): pass
    def log_interaction(self, *args, **kwargs): pass
    def log_error_interaction(self, *args, **kwargs): pass

# --- Função Principal MODIFICADA ---
def main():
    print("--- Mini Document PII Analyzer v2 (Raw JSON Mode Only) ---") # Título atualizado
    
    logger_module = interaction_logger_mini
    try:
        if not hasattr(interaction_logger_mini, 'initialize_logger'):
            raise NameError 
    except NameError:
        print("[CRITICAL ERROR] Logger module not loaded correctly. Logging will be disabled.")
        logger_module = DummyLogger()

    # 1. Selecionar Modelo Ollama (como antes)
    available_models = list_ollama_models()
    if not available_models:
        print("[ERROR] No Ollama models available. Aborting.")
        return
        
    print("\nSelect an Ollama model to use:")
    selected_model = beaupy.select(available_models, cursor="> ") 
    
    if not selected_model:
        print("No model selected. Aborting.")
        return
    print(f"[INFO] Using Ollama model: {selected_model}")

    # 2. Modo de Análise é FIXO como "raw"
    analysis_mode_key = "raw"
    # analysis_mode_description_fixed usado para logs e output
    analysis_mode_description_fixed = "Raw JSON Analysis" 
    print(f"[INFO] Analysis mode: {analysis_mode_description_fixed}")

    # Inicializar Logger com analysis_mode_key fixo
    logger_module.initialize_logger(selected_model, analysis_mode_key, SCRIPT_DIR)

    # 3. Definir e Verificar a Pasta dos Schemas (JSONs brutos)
    predefined_schema_dir_path = os.path.join(SCRIPT_DIR, DEFAULT_SCHEMA_DIR)
    print(f"\n[INFO] Using predefined JSON directory: {predefined_schema_dir_path}")

    if not os.path.isdir(predefined_schema_dir_path):
        print(f"[ERROR] Predefined JSON directory not found: {predefined_schema_dir_path}")
        # ... (lógica de criação de diretório como antes) ...
        create_dir_choice = beaupy.confirm(f"Directory '{DEFAULT_SCHEMA_DIR}' not found. Attempt to create it?", default_is_yes=True)
        if create_dir_choice:
            try:
                os.makedirs(predefined_schema_dir_path)
                print(f"[INFO] Directory '{predefined_schema_dir_path}' created. Please add your JSON files there and re-run.")
            except OSError as e:
                print(f"[ERROR] Could not create directory {predefined_schema_dir_path}: {e}")
        else: 
            print("[INFO] Directory creation aborted by user.")
        return 

    json_files_to_analyze = get_json_files_from_dir(predefined_schema_dir_path)
    print(f"[DEBUG] Files found by get_json_files_from_dir in '{predefined_schema_dir_path}': {json_files_to_analyze}") 
    if not json_files_to_analyze:
        print(f"[INFO] No .json files found in the predefined directory: {predefined_schema_dir_path}.")
        print(f"Please add your JSON files to '{DEFAULT_SCHEMA_DIR}' and re-run.")
        return 
    
    print(f"[INFO] Found {len(json_files_to_analyze)} JSON files to analyze.") 

    # 4. Carregar Prompts para Raw JSON
    system_prompt_text = load_prompt_template("system_doc_holistic_assessor_raw.txt")
    user_task_template_text = load_prompt_template("user_doc_holistic_task_template_raw.txt")

    if not system_prompt_text or not user_task_template_text:
        print("[ERROR] Critical prompt files for Raw JSON mode missing. Aborting.")
        return

    total_processing_time = 0
    successful_analyses = 0

    # 5. Processar cada ficheiro JSON
    for i, json_filepath in enumerate(json_files_to_analyze):
        doc_name = os.path.basename(json_filepath)
        print(f"\n--- Analyzing file {i+1}/{len(json_files_to_analyze)}: {doc_name} ---")
        
        user_prompt_input_data = ""
        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                raw_json_str = f.read(1024 * 1024) 
                if len(raw_json_str) == (1024*1024) and f.tell() < os.path.getsize(json_filepath): 
                    print(f"[WARNING] Raw JSON for {doc_name} was truncated to 1MB for the prompt.")
                user_prompt_input_data = raw_json_str
        except Exception as e:
            print(f"[ERROR] Could not read raw JSON file {json_filepath}: {e}")
            logger_module.log_error_interaction( # Usa analysis_mode_description_fixed
                doc_name, analysis_mode_description_fixed, system_prompt_text, 
                f"Error: Could not read raw JSON - {e}", "File reading error"
            )
            continue
        
        final_user_prompt = user_task_template_text.format(
            document_name=doc_name,
            raw_json_content=user_prompt_input_data
        )

        start_time_file = time.perf_counter()
        llm_assessment = call_ollama_generate( # Passa apenas os argumentos necessários
            selected_model, system_prompt_text, final_user_prompt, doc_name
        )
        end_time_file = time.perf_counter()
        
        file_duration = end_time_file - start_time_file
        total_processing_time += file_duration
        
        print(f"\n[RESULT] Assessment for '{doc_name}':")
        print(llm_assessment)
        print(f"(Time taken for this file: {format_duration(file_duration)})")

        if not llm_assessment.startswith("Error:"): 
            successful_analyses += 1
            
    # 6. Sumário Final (como antes)
    print("\n\n--- Analysis Summary ---")
    print(f"Processed {len(json_files_to_analyze)} JSON files.")
    print(f"Successful LLM analyses: {successful_analyses}")
    if successful_analyses > 0:
        avg_time_per_file = total_processing_time / successful_analyses
        print(f"Average processing time per successfully analyzed file: {format_duration(avg_time_per_file)}")
    elif len(json_files_to_analyze) > 0 : 
        print("No files were successfully analyzed by the LLM.")
    else: 
        print("No JSON files were processed.")
        
    print(f"Total processing time for all attempted files: {format_duration(total_processing_time)}")
    if logger_module.current_log_filepath: 
        print(f"Detailed LLM interactions logged to: {logger_module.current_log_filepath}")
    elif isinstance(logger_module, DummyLogger):
        print("Logging was disabled due to logger module loading issues.")
    else:
        print("Logging was not initialized or failed for other reasons.")

    print("--- Mini Analyzer V2 (Raw JSON Mode Only) Complete ---")

if __name__ == "__main__":
    try:
        import interaction_logger_mini
    except ImportError:
        print("[DEBUG] Direct import of `interaction_logger_mini` failed during __main__.")
        pass
    main()