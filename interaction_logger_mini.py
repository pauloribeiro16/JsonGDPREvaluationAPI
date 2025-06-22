# interaction_logger_mini.py
import os
import datetime
import re
import platform 
import psutil   
import subprocess 
from typing import List, Any, Dict, Optional
import wmi 

LOG_DIR_NAME = "llm_interaction_logs"
current_log_filepath: Optional[str] = None
is_consolidated_mode: bool = False # Novo estado para o logger
consolidated_log_overall_analysis_key: Optional[str] = None # Para nomear o ficheiro consolidado

# ... (format_duration, _clean_name_for_folder, _get_system_info_windows permanecem iguais) ...
def format_duration(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0: return "N/A"
    if seconds < 60: return f"{seconds:.2f}s"
    minutes = int(seconds // 60); secs = int(seconds % 60)
    return f"{minutes}m {secs}s"

def _clean_name_for_folder(name: Optional[str]) -> str:
    if not name: return "unknown"
    name = name.replace(":", "_").replace("/", "_").replace("\\", "_").replace(".", "_")
    name = re.sub(r'[^\w\-]', '', name); return name if name else "cleaned_empty_name"

def _get_system_info_windows() -> str:
    info: List[str] = []
    info.append("--- System Information (Windows Snapshot) ---")
    try: info.append(f"Operating System: {platform.system()} {platform.release()} ({platform.version()})"); info.append(f"Architecture: {platform.machine()}")
    except Exception as e: info.append(f"OS/Architecture Info: Error - {e}")
    try:
        info.append(f"Processor (generic): {platform.processor()}"); cpu_cores_physical = psutil.cpu_count(logical=False); cpu_cores_logical = psutil.cpu_count(logical=True); info.append(f"CPU Cores: {cpu_cores_physical} physical, {cpu_cores_logical} logical")
        try:
            cpu_name_process = subprocess.run(['wmic', 'cpu', 'get', 'name'], capture_output=True, text=True, check=False, shell=True)
            if cpu_name_process.returncode == 0:
                cpu_names = cpu_name_process.stdout.strip().split('\n')
                if len(cpu_names) > 1 and cpu_names[1].strip(): info.append(f"CPU Model (from WMIC): {cpu_names[1].strip()}")
                else: info.append(f"CPU Model (from WMIC): Not found in WMIC output.")
            else: info.append(f"CPU Model (from WMIC): WMIC command failed (ret: {cpu_name_process.returncode})")
        except Exception as e_wmic_cpu: info.append(f"CPU Model (from WMIC): Not available ({e_wmic_cpu})")
    except Exception as e: info.append(f"CPU Info: Error - {e}")
    try:
        ram = psutil.virtual_memory(); info.append(f"Total RAM: {ram.total / (1024**3):.2f} GB"); info.append(f"Available RAM (at collection): {ram.available / (1024**3):.2f} GB")
    except Exception as e: info.append(f"RAM Info: Error - {e}")
    info.append("GPU(s):")
    if wmi:
        try:
            c = wmi.WMI(); gpu_count = 0
            for controller in c.Win32_VideoController():
                gpu_count += 1; gpu_name = controller.Name if controller.Name else "N/A"; vram_bytes = controller.AdapterRAM; vram_gb = f"{vram_bytes / (1024**3):.2f} GB" if vram_bytes else "N/A"; info.append(f"  - GPU {gpu_count} (WMI): {gpu_name}, VRAM: {vram_gb}")
            if gpu_count == 0: info.append("  No WMI Video Controllers found.")
        except Exception as e_wmi_gpu: info.append(f"  Could not retrieve GPU info via WMI: {e_wmi_gpu}")
    else: info.append("  Python WMI module not installed. GPU details via WMI not available.")
    try:
        gpu_name_process_wmic = subprocess.run(['wmic', 'path', 'win32_videocontroller', 'get', 'name'], capture_output=True, text=True, check=False, shell=True)
        if gpu_name_process_wmic.returncode == 0:
            gpu_names_wmic = gpu_name_process_wmic.stdout.strip().split('\n'); wmic_gpu_found = False
            for i, name_line in enumerate(gpu_names_wmic):
                if i > 0 and name_line.strip(): info.append(f"  - GPU (from WMIC): {name_line.strip()}"); wmic_gpu_found = True
            if not wmic_gpu_found and len(gpu_names_wmic) <=1 : info.append(f"  - GPU (from WMIC): No GPU names found in WMIC output.")
        else: info.append(f"  - GPU (from WMIC): WMIC command failed (ret: {gpu_name_process_wmic.returncode})")
    except Exception as e_wmic_gpu_fallback: info.append(f"  - GPU (from WMIC): Not available ({e_wmic_gpu_fallback})")
    info.append("Disk(s):")
    try:
        physical_disks_info = []
        if wmi:
            try:
                c_wmi = wmi.WMI()
                for disk_drive in c_wmi.Win32_DiskDrive():
                    name = disk_drive.Caption if disk_drive.Caption else "N/A"; media_type_val = disk_drive.MediaType if disk_drive.MediaType else "Unknown Type"; model = disk_drive.Model if disk_drive.Model else "N/A"; physical_disk_type = "Unknown"
                    if "SSD" in model.upper() or "SOLID STATE" in model.upper() or (isinstance(media_type_val, str) and ("SSD" in media_type_val.upper() or "SOLID STATE" in media_type_val.upper())): physical_disk_type = "SSD"
                    elif "HDD" in model.upper() or "HARD DISK" in model.upper() or (isinstance(media_type_val, str) and ("HDD" in media_type_val.upper() or "HARD DISK" in media_type_val.upper())): physical_disk_type = "HDD"
                    elif isinstance(media_type_val, str) and "Fixed hard disk media" in media_type_val: physical_disk_type = "Fixed Disk (likely SSD/NVMe)"
                    else:
                        if isinstance(media_type_val, str): physical_disk_type = f"Other ({media_type_val})"
                        else: media_type_map = {0: "Unknown", 3: "HDD", 4: "SSD", 5: "SCM", 12: "Fixed Disk (likely SSD/NVMe)"}; physical_disk_type = media_type_map.get(media_type_val, f"Other (Code: {media_type_val})")
                    size_bytes = int(disk_drive.Size) if disk_drive.Size else 0; size_gb = f"{size_bytes / (1024**3):.2f} GB" if size_bytes > 0 else "N/A"; physical_disks_info.append(f"  - Physical Disk: {name} (Model: {model}, Type: {physical_disk_type}, Size: {size_gb})")
            except Exception as e_wmi_disk: physical_disks_info.append(f"  Could not retrieve physical disk info via WMI: {e_wmi_disk}")
        else: physical_disks_info.append("  Python WMI module not installed. Physical disk details via WMI not available.")
        if not physical_disks_info or (len(physical_disks_info) == 1 and "Could not retrieve" in physical_disks_info[0]): info.append("  No detailed physical disk information available via WMI.")
        else: info.extend(physical_disks_info)
        info.append("  Partitions (from psutil):")
        partitions = psutil.disk_partitions()
        if not partitions: info.append("    No partitions found by psutil.")
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint); info.append(f"    - Mountpoint: {p.mountpoint} (Filesystem: {p.fstype})"); info.append(f"      Total Size: {usage.total / (1024**3):.2f} GB, Used: {usage.used / (1024**3):.2f} GB ({usage.percent}%), Free: {usage.free / (1024**3):.2f} GB")
            except Exception as e_part: info.append(f"    - Mountpoint: {p.mountpoint} - Error getting usage details: {e_part}")
    except Exception as e: info.append(f"Disk Info: Error - {e}")
    info.append("="*50)
    return "\n".join(info) + "\n\n"


def initialize_logger(model_name: str, analysis_mode_key: str, base_script_dir: str):
    """Initializes logger for a single model run (individual log file)."""
    global current_log_filepath, is_consolidated_mode
    
    if is_consolidated_mode:
        # No new file is created if in consolidated mode by this function.
        # current_log_filepath is already set by initialize_consolidated_log.
        print(f"[LOGGER INFO] Consolidated mode active. Using: {current_log_filepath}")
        return

    current_log_filepath = None # Reset for individual log
    # ... (lógica de criação de pasta e nome de ficheiro como antes) ...
    if ":" in model_name: parts = model_name.split(":", 1); family_name_raw = parts[0]; variant_name_raw = parts[1]
    else: family_name_raw = model_name; variant_name_raw = "default"
    family_folder_name = _clean_name_for_folder(family_name_raw); variant_folder_name = _clean_name_for_folder(variant_name_raw)
    base_log_dir_for_all_models = os.path.join(base_script_dir, LOG_DIR_NAME); family_specific_log_dir = os.path.join(base_log_dir_for_all_models, family_folder_name); final_variant_specific_log_dir = os.path.join(family_specific_log_dir, variant_folder_name)
    try: os.makedirs(final_variant_specific_log_dir, exist_ok=True)
    except OSError as e: print(f"[LOGGER ERROR] Could not create log directory {final_variant_specific_log_dir}: {e}"); return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); model_name_cleaned_for_file = _clean_name_for_folder(model_name)
    log_filename = f"doc_analysis_log_{model_name_cleaned_for_file}_{analysis_mode_key}_{timestamp}.txt"
    temp_log_filepath = os.path.join(final_variant_specific_log_dir, log_filename)

    try:
        with open(temp_log_filepath, 'w', encoding='utf-8') as f:
            f.write(f"Individual Model LLM Interaction Log (Mode: {analysis_mode_key.upper()})\n") # Alterado
            f.write(f"Model Full Name: {model_name}\n")
            f.write(f"Log Folder Structure: {family_folder_name}/{variant_folder_name}\n")
            f.write(f"Initialized: {datetime.datetime.now().isoformat()}\n")
            f.write("="*50 + "\n\n")
            # ... (escrita de system info como antes) ...
            if platform.system() == "Windows":
                try: system_info_str = _get_system_info_windows(); f.write(system_info_str)
                except Exception as e_sysinfo_main: f.write("--- System Information ---\n"); f.write(f"Error collecting system information: {e_sysinfo_main}\n"); f.write("="*50 + "\n\n")
            else:
                f.write("--- System Information ---\n"); f.write("System information collection is currently focused on Windows.\n"); f.write(f"OS Detected: {platform.system()} {platform.release()}\n")
                try:
                    info_non_win = []; info_non_win.append(f"Processor: {platform.processor()}"); info_non_win.append(f"CPU Cores: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical"); ram = psutil.virtual_memory(); info_non_win.append(f"Total RAM: {ram.total / (1024**3):.2f} GB"); f.write("\n".join(info_non_win) + "\n")
                except Exception as e_psutil_nonwin: f.write(f"Could not get basic psutil info: {e_psutil_nonwin}\n")
                f.write("="*50 + "\n\n")

        current_log_filepath = temp_log_filepath
        print(f"[LOGGER INFO] Individual model log initialized at: {current_log_filepath}")
    except Exception as e_init:
        print(f"[LOGGER ERROR] Error during individual logger initialization: {e_init}")


def initialize_consolidated_log(
    base_script_dir: str, 
    overall_analysis_key: str, # Ex: "norag", "rag_simple_dual"
    main_system_prompt: str,
    main_user_template: str,
    #project_context_summary: str,
    rag_prompts: Optional[Dict[str, Optional[str]]] = None # Dict com chaves como "system_subquery_gen", "user_subquery_gen_template", etc.
):
    """Initializes a single consolidated log file for a multi-model run."""
    global current_log_filepath, is_consolidated_mode, consolidated_log_overall_analysis_key
    
    is_consolidated_mode = True
    consolidated_log_overall_analysis_key = overall_analysis_key # Guardar para sumário global
    current_log_filepath = None 

    base_log_dir = os.path.join(base_script_dir, LOG_DIR_NAME)
    try:
        os.makedirs(base_log_dir, exist_ok=True)
    except OSError as e:
        print(f"[LOGGER ERROR] Could not create base log directory {base_log_dir}: {e}")
        is_consolidated_mode = False # Fallback para não tentar escrever
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Remover parte do nome do modelo do overall_analysis_key, se houver (não deve haver aqui)
    log_filename = f"all_models_run_{overall_analysis_key}_{timestamp}.txt"
    temp_log_filepath = os.path.join(base_log_dir, log_filename)

    try:
        with open(temp_log_filepath, 'w', encoding='utf-8') as f:
            f.write(f"Consolidated LLM Interaction Log for All Models (Overall Mode: {overall_analysis_key.upper()})\n")
            f.write(f"Initialized: {datetime.datetime.now().isoformat()}\n")
            f.write("="*50 + "\n\n")

            # 1. System Information (uma vez)
            if platform.system() == "Windows":
                try: system_info_str = _get_system_info_windows(); f.write(system_info_str)
                except Exception as e_sysinfo_main: f.write("--- System Information ---\nError: {e_sysinfo_main}\n\n")
            else: # Basic non-Windows info
                f.write("--- System Information ---\n")
                f.write(f"OS Detected: {platform.system()} {platform.release()}\n")
                try:
                    info_non_win = [f"Processor: {platform.processor()}", f"CPU Cores: {psutil.cpu_count(logical=False)}p, {psutil.cpu_count(logical=True)}l"]
                    ram = psutil.virtual_memory(); info_non_win.append(f"Total RAM: {ram.total / (1024**3):.2f} GB")
                    f.write("\n".join(info_non_win) + "\n\n")
                except Exception as e_psutil_nonwin: f.write(f"Could not get basic psutil info: {e_psutil_nonwin}\n\n")
            
            # 2. Base Prompts (uma vez)
            f.write("--- Base Prompts for Main LLM ---\n")
            f.write("System Prompt (Template):\n" + str(main_system_prompt) + "\n\n")
            f.write("User Prompt (Template - RAG placeholders will be filled per document):\n" + str(main_user_template) + "\n\n")
            #f.write("Project Context Summary (Used in Prompts):\n" + str(project_context_summary) + "\n")
            f.write("="*50 + "\n\n")

            if rag_prompts:
                f.write("--- Base Prompts for RAG Auxiliary LLMs ---\n")
                for key, prompt_text in rag_prompts.items():
                    if prompt_text: # Só escreve se o prompt existir
                        f.write(f"{key.replace('_', ' ').title()} (Template):\n" + str(prompt_text) + "\n\n")
                f.write("="*50 + "\n\n")

        current_log_filepath = temp_log_filepath
        print(f"[LOGGER INFO] Consolidated log initialized at: {current_log_filepath}")
    except Exception as e_init:
        print(f"[LOGGER ERROR] Error during consolidated logger initialization: {e_init}")
        is_consolidated_mode = False # Fallback


def start_model_block_in_consolidated_log(model_name: str):
    """Writes a header for a new model's section in the consolidated log."""
    global current_log_filepath, is_consolidated_mode
    if not current_log_filepath or not is_consolidated_mode:
        return

    try:
        with open(current_log_filepath, 'a', encoding='utf-8') as f:
            f.write("\n" + "*"*20 + f" STARTING ANALYSIS FOR MODEL: {model_name} " + "*"*20 + "\n\n")
    except IOError as e:
        print(f"[LOGGER ERROR] Could not write model block header to consolidated log: {e}")

# ... (_log_llm_interaction_content, log_main_llm_interaction, log_main_llm_error,
#      log_aux_llm_interaction, log_retrieval_query_and_results permanecem os mesmos)
# (Estas funções já usam current_log_filepath, que será o consolidado se is_consolidated_mode=True)
def _log_llm_interaction_content(
    llm_type_description: str, llm_model_name: str, target_document_name: str, 
    analysis_mode_description: str, system_prompt: Optional[str], user_prompt: str, 
    output_content: str, is_error: bool = False, http_status_code: Optional[int] = None
):
    global current_log_filepath;
    if not current_log_filepath: return
    entry_type = "ERROR LLM Interaction" if is_error else "LLM Interaction"
    input_type = f"INPUT TO {llm_type_description.upper()} ({llm_model_name})"
    output_section_header = "ERROR DETAILS" if is_error else f"OUTPUT FROM {llm_type_description.upper()} ({llm_model_name}) (Raw)"
    log_entry_parts = [
        f"--- {entry_type} Start (Document: {target_document_name}, LLM: {llm_type_description}) ---",
        f"Timestamp: {datetime.datetime.now().isoformat()}", f"LLM Model Logged: {llm_model_name}",
        f"Analysis Stage: {analysis_mode_description}",
    ]
    if is_error and http_status_code: log_entry_parts.append(f"HTTP Status Code: {http_status_code}")
    log_entry_parts.extend([
        f"\n{input_type}:", "-" * 15 + " System Prompt " + "-"*15 + "\n" + str(system_prompt if system_prompt else "N/A"),
        "-" * 15 + " User Prompt " + "-"*15 + "\n" + str(user_prompt), "---"*10 + "\n",
        f"{output_section_header}:\n" + str(output_content), "--- LLM Interaction End ---\n", "="*50 + "\n"
    ])
    try:
        with open(current_log_filepath, 'a', encoding='utf-8') as f: f.write("\n".join(log_entry_parts) + "\n")
    except IOError as e: print(f"[LOGGER ERROR] Could not write LLM interaction to log file {current_log_filepath}: {e}")
    except Exception as e_log: print(f"[LOGGER ERROR] Unexpected error during LLM interaction logging: {e_log}")

def log_main_llm_interaction(target_document_name, main_llm_model_name, analysis_mode_description, system_prompt, user_prompt, raw_llm_output):
    if not current_log_filepath: print(f"[LOGGER WARNING] Logger not initialized. Skipping MAIN LLM log entry for {target_document_name}."); return
    _log_llm_interaction_content("LLM Principal", main_llm_model_name, target_document_name, analysis_mode_description, system_prompt, user_prompt, raw_llm_output)

def log_main_llm_error(target_document_name, main_llm_model_name, analysis_mode_description, system_prompt, user_prompt, error_message, status_code=None):
    if not current_log_filepath: print(f"[LOGGER WARNING] Logger not initialized. Skipping MAIN LLM error log entry for {target_document_name}."); return
    _log_llm_interaction_content("LLM Principal", main_llm_model_name, target_document_name, analysis_mode_description, system_prompt, user_prompt, error_message, True, status_code)

def log_aux_llm_interaction(aux_llm_type_description: str, aux_llm_model_name: str, target_document_name: str, related_sub_task: str, system_prompt: Optional[str], user_prompt: str, raw_llm_output: str):
    if not current_log_filepath: print(f"[LOGGER WARNING] Logger not initialized. Skipping AUX LLM log entry for {target_document_name}."); return
    _log_llm_interaction_content(f"LLM Auxiliar ({aux_llm_type_description})", aux_llm_model_name, target_document_name, related_sub_task, system_prompt, user_prompt, raw_llm_output)
    
def log_retrieval_query_and_results(retriever_name: str, target_document_name: str, retrieval_query: str, retrieved_nodes_info: List[Dict[str, Any]], notes: Optional[str] = None):
    global current_log_filepath;
    if not current_log_filepath: print(f"[LOGGER WARNING] Logger not initialized. Skipping retrieval log for {target_document_name}."); return
    log_entry_parts = [f"--- Retrieval Interaction Start (Document: {target_document_name}, Retriever: {retriever_name}) ---", f"Timestamp: {datetime.datetime.now().isoformat()}"]
    if notes: log_entry_parts.append(f"Context/Notes: {notes}")
    log_entry_parts.extend([f"\nRETRIEVAL QUERY to '{retriever_name}':", str(retrieval_query), "\nRETRIEVED NODES (" + (f"{len(retrieved_nodes_info)} nodes):" if retrieved_nodes_info else "No nodes found):")])
    if retrieved_nodes_info:
        for i, node_info in enumerate(retrieved_nodes_info):
            log_entry_parts.append(f"  --- Node {i+1} ---"); log_entry_parts.append(f"    Metadata: {str(node_info.get('metadata', {}))}")
            log_entry_parts.append(f"    Score: {node_info.get('score', 'N/A'):.4f}" if isinstance(node_info.get('score'), float) else f"    Score: {node_info.get('score', 'N/A')}")
            log_entry_parts.append(f"    Content Preview: {str(node_info.get('content_preview', ''))[:500]}...") 
    else: log_entry_parts.append("  (No relevant nodes found by this retriever for this query)")
    log_entry_parts.extend(["--- Retrieval Interaction End ---", "="*50 + "\n"])
    try:
        with open(current_log_filepath, 'a', encoding='utf-8') as f: f.write("\n".join(log_entry_parts) + "\n")
    except IOError as e: print(f"[LOGGER ERROR] Could not write retrieval interaction to log file {current_log_filepath}: {e}")
    except Exception as e_log: print(f"[LOGGER ERROR] Unexpected error during retrieval interaction logging: {e_log}")


# RENOMEADA: para sumário de modelo individual (usada em ambos os modos)
def log_model_run_summary(
    model_name: str, # Adicionado nome do modelo
    total_files_processed: int, 
    successful_analyses: int, 
    total_model_pipeline_time_seconds: float, 
    avg_time_per_file_seconds: Optional[float]
):
    global current_log_filepath, is_consolidated_mode
    if not current_log_filepath:
        return

    summary_header = f"--- Model Run Summary for: {model_name} ---" if is_consolidated_mode else "--- Run Summary ---"
    
    try:
        with open(current_log_filepath, 'a', encoding='utf-8') as f:
            f.write(f"{summary_header}\n")
            f.write(f"Model Analyzed: {model_name}\n")
            f.write(f"Total JSON files processed with this model: {total_files_processed}\n")
            f.write(f"Successful LLM analyses by this model: {successful_analyses}\n")
            avg_time_str = format_duration(avg_time_per_file_seconds)
            f.write(f"Average processing time per successfully analyzed file (main LLM): {avg_time_str}\n")
            total_time_str = format_duration(total_model_pipeline_time_seconds)
            f.write(f"Total pipeline time for this model's run: {total_time_str}\n")
            if is_consolidated_mode:
                 f.write(f"--- End of Summary for Model: {model_name} ---\n")
            else: # Log individual
                f.write("="*50 + "\n")
                f.write("--- End of Log ---\n")
            f.write("\n") # Linha extra
    except Exception as e:
        print(f"[LOGGER ERROR] Could not write model run summary to log file: {e}")


# NOVA FUNÇÃO: para sumário global no ficheiro consolidado
def log_overall_consolidated_run_summary(
    total_models_processed: int,
    total_json_files_configured: int, # Quantos ficheiros JSON estavam na pasta de input
    overall_successful_analyses: int, # Soma de sucessos de todos os modelos
    overall_total_llm_processing_time: float, # Soma dos tempos de LLM de todos os modelos
    overall_total_pipeline_duration_seconds: float # Tempo total da execução de todos os modelos
):
    global current_log_filepath, is_consolidated_mode, consolidated_log_overall_analysis_key
    if not current_log_filepath or not is_consolidated_mode:
        print("[LOGGER WARNING] Not in consolidated mode or log file not set. Skipping overall summary.")
        return

    avg_llm_time_overall = overall_total_llm_processing_time / overall_successful_analyses if overall_successful_analyses > 0 else None
    
    try:
        with open(current_log_filepath, 'a', encoding='utf-8') as f:
            f.write("\n" + "#"*20 + " OVERALL CONSOLIDATED RUN SUMMARY " + "#"*20 + "\n")
            f.write(f"Overall Analysis Mode Key: {consolidated_log_overall_analysis_key}\n")
            f.write(f"Total distinct models processed in this run: {total_models_processed}\n")
            f.write(f"Total JSON files configured for analysis in this run: {total_json_files_configured}\n")
            f.write(f"Total successful main LLM analyses across all models: {overall_successful_analyses}\n")
            avg_time_str = format_duration(avg_llm_time_overall)
            f.write(f"Average main LLM processing time per successfully analyzed file (across all models): {avg_time_str}\n")
            total_time_str = format_duration(overall_total_pipeline_duration_seconds)
            f.write(f"Total pipeline time for this entire multi-model run: {total_time_str}\n")
            f.write("#"*60 + "\n")
            f.write("--- End of Consolidated Log ---\n")
    except Exception as e:
        print(f"[LOGGER ERROR] Could not write overall consolidated run summary: {e}")