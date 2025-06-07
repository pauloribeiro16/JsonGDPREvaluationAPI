# interaction_logger_mini.py
import os
import datetime
import re 

LOG_DIR_NAME = "llm_interaction_logs" 
current_log_filepath = None

def _clean_name_for_folder(name):
    if not name:
        return "unknown"
    name = name.replace(":", "_")
    name = name.replace("/", "_")
    name = name.replace("\\", "_")
    name = name.replace(".", "_")
    name = re.sub(r'[^\w\-]', '', name)
    return name if name else "cleaned_empty_name"

def initialize_logger(model_name, analysis_mode_key, base_script_dir):
    global current_log_filepath
    
    if ":" in model_name:
        parts = model_name.split(":", 1)
        family_name_raw = parts[0]
        variant_name_raw = parts[1]
    else:
        family_name_raw = model_name
        variant_name_raw = "default"

    family_folder_name = _clean_name_for_folder(family_name_raw)
    variant_folder_name = _clean_name_for_folder(variant_name_raw)

    base_log_dir_for_all_models = os.path.join(base_script_dir, LOG_DIR_NAME)
    family_specific_log_dir = os.path.join(base_log_dir_for_all_models, family_folder_name)
    final_variant_specific_log_dir = os.path.join(family_specific_log_dir, variant_folder_name)

    try:
        os.makedirs(final_variant_specific_log_dir, exist_ok=True)
    except OSError as e:
        print(f"[LOGGER ERROR] Could not create log directory {final_variant_specific_log_dir}: {e}")
        current_log_filepath = None
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name_cleaned_for_file = _clean_name_for_folder(model_name)
    
    log_filename = f"doc_analysis_log_{model_name_cleaned_for_file}_{analysis_mode_key}_{timestamp}.txt"
    current_log_filepath = os.path.join(final_variant_specific_log_dir, log_filename)
    
    try:
        with open(current_log_filepath, 'w', encoding='utf-8') as f:
            f.write(f"Holistic Document Analysis LLM Interaction Log (Mode: {analysis_mode_key.upper()})\n")
            f.write(f"Model Full Name: {model_name}\n")
            f.write(f"Log Folder Structure: {family_folder_name}/{variant_folder_name}\n")
            f.write(f"Initialized: {datetime.datetime.now().isoformat()}\n")
            f.write("="*50 + "\n\n")
        print(f"[LOGGER INFO] Interaction log initialized at: {current_log_filepath}")
    except IOError as e:
        print(f"[LOGGER ERROR] Could not initialize log file {current_log_filepath}: {e}")
        current_log_filepath = None

def _log_entry_content(target_document_name, mode_for_log, system_prompt, user_prompt, output_content, is_error=False):
    global current_log_filepath
    if not current_log_filepath:
        print(f"[LOGGER WARNING] Logger not initialized or failed. Skipping log entry for {target_document_name}.")
        return
    
    entry_type = "ERROR Interaction" if is_error else "Interaction"
    input_type = "INPUT TO LLM (Attempted)" if is_error else "INPUT TO LLM"
    output_section_header = "ERROR DETAILS" if is_error else "OUTPUT FROM LLM (Raw)"

    try:
        with open(current_log_filepath, 'a', encoding='utf-8') as f:
            f.write(f"--- {entry_type} Start (Document: {target_document_name}) ---\n")
            f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Analysis Mode Logged As: {mode_for_log}\n\n") 
            
            f.write(f"{input_type}:\n")
            f.write("-" * 15 + " System Prompt " + "-"*15 + "\n")
            f.write(system_prompt + "\n")
            f.write("-" * 15 + " User Prompt " + "-"*15 + "\n")
            f.write(user_prompt + "\n") 
            f.write("---"*10 + "\n\n")
            
            f.write(f"{output_section_header}:\n")
            f.write(output_content + "\n") 
            f.write("--- Interaction End ---\n\n")
            f.write("="*50 + "\n\n")
            
    except IOError as e:
        print(f"[LOGGER ERROR] Could not write to log file {current_log_filepath}: {e}")
    except Exception as e:
        print(f"[LOGGER ERROR] Unexpected error during logging: {e}")

def log_interaction(target_document_name, analysis_mode_description, system_prompt, user_prompt, raw_llm_output):
    _log_entry_content(target_document_name, analysis_mode_description, system_prompt, user_prompt, raw_llm_output)

def log_error_interaction(target_document_name, analysis_mode_description, system_prompt, user_prompt, error_message, status_code=None):
    error_output_content = (
        (f"HTTP Status Code: {status_code}\n" if status_code else "")
        + f"Error Message: {error_message}"
    )
    _log_entry_content(target_document_name, analysis_mode_description, system_prompt, user_prompt, 
                       error_output_content, is_error=True)