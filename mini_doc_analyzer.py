# mini_doc_analyzer_v2.py
import json
import os
import requests
import time
import beaupy # pip install beaupy
import re     # Para limpeza de <think> block, se necessário
import interaction_logger_mini

# --- Configurações ---
OLLAMA_API_BASE_URL = "http://localhost:11434/api"
OLLAMA_TAGS_ENDPOINT_SUFFIX = "/tags"
OLLAMA_GENERATE_ENDPOINT_SUFFIX = "/generate"
OLLAMA_REQUEST_TIMEOUT_SECONDS = 360
OLLAMA_KEEP_ALIVE_DURATION = "5m" # ou "0s" se suspeitar de problemas
PROMPTS_DIR_NAME = "prompts_mini"
DEFAULT_SCHEMA_DIR = "test_schemas"
MAX_JSON_SIZE_PROMPT_MB = 2 # Limite em MB para o conteúdo JSON no prompt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR_PATH = os.path.join(SCRIPT_DIR, PROMPTS_DIR_NAME)

# --- Funções de Interação com Ollama ---
def list_ollama_models():
    try:
        response = requests.get(f"{OLLAMA_API_BASE_URL}{OLLAMA_TAGS_ENDPOINT_SUFFIX}", timeout=10)
        response.raise_for_status()
        models_data = response.json()
        available_models = [model["name"] for model in models_data.get("models", [])]
        if not available_models:
            print("[WARNING] No models found via Ollama API. Using a minimal default list.")
            return ["phi3:mini"] # Default mais genérico
        print(f"[INFO] Successfully fetched {len(available_models)} models from Ollama.")
        return available_models
    except Exception as e:
        print(f"[WARNING] Could not fetch models from Ollama: {e}. Using a minimal default list.")
        return ["phi3:mini"]

def call_ollama_generate(model_name, system_prompt, user_prompt_with_data, target_doc_name):
    payload = {
        "model": model_name,
        "system": system_prompt,
        "prompt": user_prompt_with_data,
        "stream": True,
        # "template": "{{ .System }}\n\n{{ .Prompt }}", # Deixe comentado se a remoção resolveu problemas
        "keep_alive": OLLAMA_KEEP_ALIVE_DURATION,
        "options": { # Opções adicionais podem ser úteis
            # "temperature": 0.7, # Exemplo
        }
    }
    endpoint = f"{OLLAMA_API_BASE_URL}{OLLAMA_GENERATE_ENDPOINT_SUFFIX}"
    analysis_mode_description_fixed = "Raw JSON Analysis"
    print(f"\n[INFO] Analyzing '{target_doc_name}' ({analysis_mode_description_fixed}) with Ollama ({model_name}). Streaming response...")

    full_response_content = []
    final_response_metrics = {} # Ainda guardamos métricas, mesmo que não as loguemos todas
    http_status = None

    try:
        with requests.post(endpoint, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS, stream=True) as response:
            http_status = response.status_code
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8', errors='ignore')
                    try:
                        chunk = json.loads(decoded_line)
                        if "response" in chunk and chunk["response"]:
                            token = chunk["response"]
                            full_response_content.append(token)
                        if chunk.get("done", False):
                            final_response_metrics = chunk
                            break # Parar após o sinal de "done"
                        if "error" in chunk:
                            error_msg = f"Ollama API Stream Error: {chunk['error']}"
                            print(f"\n[ERROR] {error_msg}")
                            interaction_logger_mini.log_error_interaction(
                                target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data,
                                error_msg, http_status
                            )
                            return f"Error from Ollama API Stream: {chunk['error']}"
                    except json.JSONDecodeError:
                        print(f"\n[WARNING] Non-JSON line in stream (ignoring): {decoded_line[:100]}...")
                    except Exception as e_chunk:
                        print(f"\n[ERROR] Error processing stream chunk: {e_chunk} - Chunk: {decoded_line[:100]}...")
                        # Não retornar aqui, tentar continuar processando a stream

            final_assessment_text = "".join(full_response_content).strip()

            # Opcional: Remover blocos <think> se um modelo os produzir e não os quiser
            if "<think>" in final_assessment_text: # Verificação simples antes de usar regex
                cleaned_assessment_text = re.sub(r"<think>.*?</think>\s*", "", final_assessment_text, flags=re.DOTALL).strip()
                if cleaned_assessment_text or not re.search(r"<think>", final_assessment_text, re.DOTALL): # Lógica para usar o texto limpo
                    final_assessment_text = cleaned_assessment_text

            if not final_assessment_text and not final_response_metrics.get("error"):
                # Se não houve erro explícito no stream, mas o texto está vazio
                if not final_response_metrics: # Se nem o "done" foi recebido
                     error_msg = "Empty response from LLM and no 'done' signal or metrics received from stream."
                     print(f"\n[ERROR] {error_msg}")
                     interaction_logger_mini.log_error_interaction(
                        target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data,
                        error_msg, http_status
                     )
                     return "Error: Empty response and no metrics from LLM stream."
                # Se "done" foi recebido mas o texto está vazio
                final_assessment_text = "Warning: LLM produced an empty response (after joining response tokens)."

            # Passar APENAS o texto da avaliação para o log de interação
            interaction_logger_mini.log_interaction(
                target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data,
                final_assessment_text
            )
            return final_assessment_text

    except requests.exceptions.HTTPError as http_err:
        error_msg = f"Ollama request failed with HTTPError: {http_err}. Response: {http_err.response.text[:500] if http_err.response else 'No response object'}"
        print(f"\n[ERROR] {error_msg}")
        interaction_logger_mini.log_error_interaction(
            target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data,
            error_msg, http_status if http_status else getattr(http_err.response, 'status_code', None)
        )
        return f"Error: Ollama request failed - {http_err}"
    except requests.exceptions.RequestException as e: # Outros erros de request (timeout, connection error)
        error_msg = f"Ollama request failed: {e}"
        print(f"\n[ERROR] {error_msg}")
        interaction_logger_mini.log_error_interaction(
            target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data,
            error_msg, getattr(e.response, 'status_code', None)
        )
        return f"Error: Ollama request failed - {e}"
    except Exception as e_call: # Qualquer outra excepção inesperada
        error_msg = f"An unexpected error occurred during Ollama stream call: {e_call}"
        print(f"\n[ERROR] {error_msg}")
        interaction_logger_mini.log_error_interaction(
            target_doc_name, analysis_mode_description_fixed, system_prompt, user_prompt_with_data,
            error_msg
        )
        return f"Error: An unexpected error occurred - {e_call}"


# --- Funções Auxiliares ---
def load_prompt_template(prompt_filename):
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
    json_files = []
    if not os.path.isdir(directory_path):
        print(f"[WARNING] Directory not found: {directory_path}")
        return []
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(".json"):
            json_files.append(os.path.join(directory_path, filename))
    return json_files

# --- Dummy Logger para Fallback ---
class DummyLogger:
    current_log_filepath = None
    def initialize_logger(self, *args, **kwargs):
        print("[DUMMY LOGGER] Initialization skipped.")
    def log_interaction(self, *args, **kwargs):
        print("[DUMMY LOGGER] Interaction log skipped.")
    def log_error_interaction(self, *args, **kwargs):
        print("[DUMMY LOGGER] Error interaction log skipped.")
    def log_run_summary(self, *args, **kwargs):
        print("[DUMMY LOGGER] Run summary log skipped.")
    def format_duration(self, seconds): # Adicionar ao DummyLogger
        if seconds is None or seconds < 0: return "N/A"
        if seconds < 60: return f"{seconds:.2f}s"
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"

# --- Função Principal ---
def main():
    pipeline_start_time = time.perf_counter()

    print("--- Mini Document PII Analyzer v2 (Raw JSON Mode Only) ---")

    logger_module = interaction_logger_mini
    try:
        # Verificar se as funções necessárias existem no logger_module
        required_funcs = ['initialize_logger', 'log_interaction', 'log_error_interaction', 'log_run_summary', 'format_duration']
        for func_name in required_funcs:
            if not hasattr(logger_module, func_name):
                raise AttributeError(f"Logger module is missing function: {func_name}")
    except Exception as e_logger_check: # Captura AttributeError ou outros problemas
        print(f"[CRITICAL ERROR] Logger module not loaded correctly or incomplete: {e_logger_check}. Logging will be disabled.")
        logger_module = DummyLogger()

    available_models = list_ollama_models()
    if not available_models:
        print("[ERROR] No Ollama models available. Aborting.")
        return
    available_models.sort()
    
    print("\nSelect an Ollama model to use:")
    selected_model = beaupy.select(available_models, cursor="> ")


    if not selected_model:
        print("No model selected. Aborting.")
        return
    print(f"[INFO] Using Ollama model: {selected_model}")

    analysis_mode_key = "raw"
    analysis_mode_description_fixed = "Raw JSON Analysis"
    print(f"[INFO] Analysis mode: {analysis_mode_description_fixed}")

    logger_module.initialize_logger(selected_model, analysis_mode_key, SCRIPT_DIR)

    predefined_schema_dir_path = os.path.join(SCRIPT_DIR, DEFAULT_SCHEMA_DIR)
    print(f"\n[INFO] Using predefined JSON directory: {predefined_schema_dir_path}")

    if not os.path.isdir(predefined_schema_dir_path):
        print(f"[ERROR] Predefined JSON directory not found: {predefined_schema_dir_path}")
        create_dir_choice = beaupy.confirm(f"Directory '{DEFAULT_SCHEMA_DIR}' not found. Attempt to create it?", default_is_yes=True)
        if create_dir_choice:
            try:
                os.makedirs(predefined_schema_dir_path)
                print(f"[INFO] Directory '{predefined_schema_dir_path}' created. Please add your JSON files there and re-run.")
            except OSError as e:
                print(f"[ERROR] Could not create directory {predefined_schema_dir_path}: {e}")
        else:
            print("[INFO] Directory creation aborted by user.")
        return # Abortar se o diretório não existir e não for criado

    json_files_to_analyze = get_json_files_from_dir(predefined_schema_dir_path)
    if not json_files_to_analyze:
        print(f"[INFO] No .json files found in the predefined directory: {predefined_schema_dir_path}.")
        pipeline_end_time = time.perf_counter()
        total_pipeline_duration_seconds = pipeline_end_time - pipeline_start_time
        logger_module.log_run_summary(0, 0, total_pipeline_duration_seconds, None)
        print("--- Mini Analyzer V2 (Raw JSON Mode Only) Complete ---")
        return

    print(f"[INFO] Found {len(json_files_to_analyze)} JSON files to analyze.")

    system_prompt_text = load_prompt_template("system_doc_holistic_assessor_raw.txt")
    user_task_template_text = load_prompt_template("user_doc_holistic_task_template_raw.txt")

    if not system_prompt_text or not user_task_template_text:
        print("[ERROR] Critical prompt files for Raw JSON mode missing. Aborting.")
        pipeline_end_time = time.perf_counter()
        total_pipeline_duration_seconds = pipeline_end_time - pipeline_start_time
        logger_module.log_run_summary(len(json_files_to_analyze), 0, total_pipeline_duration_seconds, None)
        print("--- Mini Analyzer V2 (Raw JSON Mode Only) Complete ---")
        return

    total_llm_processing_time_successful = 0
    successful_analyses = 0

    for i, json_filepath in enumerate(json_files_to_analyze):
        doc_name = os.path.basename(json_filepath)
        print(f"\n--- Analyzing file {i+1}/{len(json_files_to_analyze)}: {doc_name} ---")

        user_prompt_input_data = ""
        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                max_bytes = MAX_JSON_SIZE_PROMPT_MB * 1024 * 1024
                raw_json_str = f.read(max_bytes)
                if len(raw_json_str) == max_bytes and f.tell() < os.path.getsize(json_filepath):
                    print(f"[WARNING] Raw JSON for {doc_name} was truncated to {MAX_JSON_SIZE_PROMPT_MB}MB for the prompt.")
                user_prompt_input_data = raw_json_str
        except Exception as e:
            print(f"[ERROR] Could not read raw JSON file {json_filepath}: {e}")
            logger_module.log_error_interaction(
                doc_name, analysis_mode_description_fixed,
                system_prompt_text if system_prompt_text else "System prompt not loaded",
                f"User prompt could not be fully constructed due to file read error for: {doc_name}", # User prompt pode não estar formado
                f"Error reading JSON file: {e}", # Mensagem de erro
            )
            continue # Pular para o próximo ficheiro

        final_user_prompt = user_task_template_text.format(
            document_name=doc_name,
            raw_json_content=user_prompt_input_data
        )

        start_time_file_llm = time.perf_counter()
        llm_assessment = call_ollama_generate(
            selected_model, system_prompt_text, final_user_prompt, doc_name
        )
        end_time_file_llm = time.perf_counter()
        file_llm_duration = end_time_file_llm - start_time_file_llm

        # Imprimir uma indicação do resultado no terminal, mas não a avaliação completa
        print(f"\n[RESULT] Status for '{doc_name}':")
        if llm_assessment and not llm_assessment.startswith("Error:") and not llm_assessment.startswith("Warning:"):
            print(f"  Assessment successfully generated and logged.")
            successful_analyses += 1
            total_llm_processing_time_successful += file_llm_duration
        elif llm_assessment: # Se for um erro ou aviso do LLM
            print(f"  {llm_assessment.splitlines()[0]}") # Imprimir a primeira linha do erro/aviso
        else: # Se llm_assessment for None ou string vazia (improvável com a lógica atual, mas defensivo)
            print(f"  No assessment content returned from LLM call.")

        print(f"(Time taken for this file's LLM analysis: {logger_module.format_duration(file_llm_duration)})")

    pipeline_end_time = time.perf_counter()
    total_pipeline_duration_seconds = pipeline_end_time - pipeline_start_time
    avg_time_per_successful_file_seconds = None
    if successful_analyses > 0:
        avg_time_per_successful_file_seconds = total_llm_processing_time_successful / successful_analyses

    # Sumário na Consola
    print("\n\n--- Analysis Summary (Console) ---")
    print(f"Total JSON files attempted: {len(json_files_to_analyze)}")
    print(f"Successful LLM analyses: {successful_analyses}")
    if successful_analyses > 0:
        print(f"Average LLM processing time per successfully analyzed file: {logger_module.format_duration(avg_time_per_successful_file_seconds)}")
    print(f"Total LLM processing time for successful analyses: {logger_module.format_duration(total_llm_processing_time_successful)}")
    print(f"Total pipeline time for this run: {logger_module.format_duration(total_pipeline_duration_seconds)}")

    # Logar sumário no ficheiro
    logger_module.log_run_summary(
        len(json_files_to_analyze),
        successful_analyses,
        total_pipeline_duration_seconds,
        avg_time_per_successful_file_seconds
    )

    if logger_module.current_log_filepath:
        print(f"Detailed LLM interactions and run summary logged to: {logger_module.current_log_filepath}")
    elif isinstance(logger_module, DummyLogger):
        print("Logging was disabled due to logger module loading issues (using DummyLogger).")
    else: # Caso logger_module não seja nem o real nem o Dummy (improvável)
        print("Logging status uncertain.")

    print("--- Mini Analyzer V2 (Raw JSON Mode Only) Complete ---")

if __name__ == "__main__":
    main()