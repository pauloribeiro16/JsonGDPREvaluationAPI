# interaction_logger_mini.py
import os
import datetime
import re
import platform # Para informações do SO
import psutil   # Para CPU, RAM, Disco (pip install psutil)
import subprocess # Para executar comandos como wmic se necessário

# Tentar importar wmi, mas não tornar uma dependência rígida se não for encontrado
try:
    import wmi # (pip install wmi)
except ImportError:
    wmi = None

LOG_DIR_NAME = "llm_interaction_logs"
current_log_filepath = None

def format_duration(seconds):
    if seconds is None or seconds < 0: # Adicionado 'seconds is None'
        return "N/A"
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"

def _clean_name_for_folder(name):
    if not name:
        return "unknown"
    name = name.replace(":", "_").replace("/", "_").replace("\\", "_").replace(".", "_")
    name = re.sub(r'[^\w\-]', '', name) # Mantém letras, números, underscore e hífen
    return name if name else "cleaned_empty_name"

def _get_system_info_windows():
    info = []
    info.append("--- System Information (Windows Snapshot) ---")

    try:
        info.append(f"Operating System: {platform.system()} {platform.release()} ({platform.version()})")
        info.append(f"Architecture: {platform.machine()}")
    except Exception as e:
        info.append(f"OS/Architecture Info: Error - {e}")

    try:
        info.append(f"Processor (generic): {platform.processor()}")
        cpu_cores_physical = psutil.cpu_count(logical=False)
        cpu_cores_logical = psutil.cpu_count(logical=True)
        info.append(f"CPU Cores: {cpu_cores_physical} physical, {cpu_cores_logical} logical")
        try:
            # Tentar obter nome mais detalhado da CPU via wmic (Windows específico)
            # Usar shell=True com cuidado e apenas com comandos controlados.
            cpu_name_process = subprocess.run(['wmic', 'cpu', 'get', 'name'], capture_output=True, text=True, check=False, shell=True)
            if cpu_name_process.returncode == 0:
                cpu_names = cpu_name_process.stdout.strip().split('\n')
                if len(cpu_names) > 1 and cpu_names[1].strip():
                    info.append(f"CPU Model (from WMIC): {cpu_names[1].strip()}")
                else:
                    info.append(f"CPU Model (from WMIC): Not found in WMIC output.")
            else:
                info.append(f"CPU Model (from WMIC): WMIC command failed (ret: {cpu_name_process.returncode})")
        except Exception as e_wmic_cpu:
            info.append(f"CPU Model (from WMIC): Not available ({e_wmic_cpu})")
    except Exception as e:
        info.append(f"CPU Info: Error - {e}")


    try:
        ram = psutil.virtual_memory()
        info.append(f"Total RAM: {ram.total / (1024**3):.2f} GB")
        info.append(f"Available RAM (at collection): {ram.available / (1024**3):.2f} GB")
    except Exception as e:
        info.append(f"RAM Info: Error - {e}")

    info.append("GPU(s):")
    if wmi:
        try:
            c = wmi.WMI()
            gpu_count = 0
            for controller in c.Win32_VideoController():
                gpu_count += 1
                gpu_name = controller.Name if controller.Name else "N/A"
                vram_bytes = controller.AdapterRAM
                vram_gb = f"{vram_bytes / (1024**3):.2f} GB" if vram_bytes else "N/A"
                info.append(f"  - GPU {gpu_count} (WMI): {gpu_name}, VRAM: {vram_gb}")
            if gpu_count == 0:
                 info.append("  No WMI Video Controllers found.")
        except Exception as e_wmi_gpu:
            info.append(f"  Could not retrieve GPU info via WMI: {e_wmi_gpu}")
    else:
        info.append("  Python WMI module not installed. GPU details via WMI not available.")

    # Fallback/complemento com WMIC para nome da GPU se WMI não estiver disponível ou para ter outra fonte
    try:
        gpu_name_process_wmic = subprocess.run(['wmic', 'path', 'win32_videocontroller', 'get', 'name'], capture_output=True, text=True, check=False, shell=True)
        if gpu_name_process_wmic.returncode == 0:
            gpu_names_wmic = gpu_name_process_wmic.stdout.strip().split('\n')
            wmic_gpu_found = False
            for i, name_line in enumerate(gpu_names_wmic):
                if i > 0 and name_line.strip(): # Ignora cabeçalho "Name" e linhas vazias
                    info.append(f"  - GPU (from WMIC): {name_line.strip()}")
                    wmic_gpu_found = True
            if not wmic_gpu_found and len(gpu_names_wmic) <=1 : # Se só veio o header "Name"
                 info.append(f"  - GPU (from WMIC): No GPU names found in WMIC output.")

        else:
            info.append(f"  - GPU (from WMIC): WMIC command failed (ret: {gpu_name_process_wmic.returncode})")
    except Exception as e_wmic_gpu_fallback:
        info.append(f"  - GPU (from WMIC): Not available ({e_wmic_gpu_fallback})")


    info.append("Disk(s):")
    try:
        # Listar discos físicos e seus tipos primeiro
        physical_disks_info = []
        if wmi:
            try:
                c_wmi = wmi.WMI()
                for disk_drive in c_wmi.Win32_DiskDrive():
                    name = disk_drive.Caption if disk_drive.Caption else "N/A"
                    media_type_val = disk_drive.MediaType if disk_drive.MediaType else "Unknown Type"
                    model = disk_drive.Model if disk_drive.Model else "N/A"
                    physical_disk_type = "Unknown"

                    # Tentar inferir SSD/HDD a partir do MediaType ou Model
                    if "SSD" in model.upper() or "SOLID STATE" in model.upper() or \
                       (isinstance(media_type_val, str) and ("SSD" in media_type_val.upper() or "SOLID STATE" in media_type_val.upper())):
                        physical_disk_type = "SSD"
                    elif "HDD" in model.upper() or "HARD DISK" in model.upper() or \
                         (isinstance(media_type_val, str) and ("HDD" in media_type_val.upper() or "HARD DISK" in media_type_val.upper())):
                        physical_disk_type = "HDD"
                    elif isinstance(media_type_val, str) and "Fixed hard disk media" in media_type_val: # Comum para NVMe/SSD
                         physical_disk_type = "Fixed Disk (likely SSD/NVMe)"
                    else: # Se não for string ou não contiver as palavras chave
                        if isinstance(media_type_val, str):
                            physical_disk_type = f"Other ({media_type_val})"
                        else: # Se media_type_val não for string (pode ser int)
                            # Common MediaType values: 0 (Unknown), 3 (HDD), 4 (SSD), 5 (SCM)
                            # 12 (Fixed hard disk) - Often NVMe/SSD
                            media_type_map = {0: "Unknown", 3: "HDD", 4: "SSD", 5: "SCM", 12: "Fixed Disk (likely SSD/NVMe)"}
                            physical_disk_type = media_type_map.get(media_type_val, f"Other (Code: {media_type_val})")

                    size_bytes = int(disk_drive.Size) if disk_drive.Size else 0
                    size_gb = f"{size_bytes / (1024**3):.2f} GB" if size_bytes > 0 else "N/A"
                    physical_disks_info.append(f"  - Physical Disk: {name} (Model: {model}, Type: {physical_disk_type}, Size: {size_gb})")
            except Exception as e_wmi_disk:
                physical_disks_info.append(f"  Could not retrieve physical disk info via WMI: {e_wmi_disk}")
        else:
            physical_disks_info.append("  Python WMI module not installed. Physical disk details via WMI not available.")
        
        if not physical_disks_info or (len(physical_disks_info) == 1 and "Could not retrieve" in physical_disks_info[0]):
             info.append("  No detailed physical disk information available via WMI.")
        else:
            info.extend(physical_disks_info)

        info.append("  Partitions (from psutil):")
        partitions = psutil.disk_partitions()
        if not partitions:
            info.append("    No partitions found by psutil.")
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                info.append(f"    - Mountpoint: {p.mountpoint} (Filesystem: {p.fstype})")
                info.append(f"      Total Size: {usage.total / (1024**3):.2f} GB, Used: {usage.used / (1024**3):.2f} GB ({usage.percent}%), Free: {usage.free / (1024**3):.2f} GB")
            except Exception as e_part:
                info.append(f"    - Mountpoint: {p.mountpoint} - Error getting usage details: {e_part}")
    except Exception as e:
        info.append(f"Disk Info: Error - {e}")

    info.append("="*50)
    return "\n".join(info) + "\n\n"

def initialize_logger(model_name, analysis_mode_key, base_script_dir):
    global current_log_filepath
    current_log_filepath = None

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
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name_cleaned_for_file = _clean_name_for_folder(model_name)
    log_filename = f"doc_analysis_log_{model_name_cleaned_for_file}_{analysis_mode_key}_{timestamp}.txt"
    temp_log_filepath = os.path.join(final_variant_specific_log_dir, log_filename)

    try:
        with open(temp_log_filepath, 'w', encoding='utf-8') as f:
            f.write(f"Holistic Document Analysis LLM Interaction Log (Mode: {analysis_mode_key.upper()})\n")
            f.write(f"Model Full Name: {model_name}\n")
            f.write(f"Log Folder Structure: {family_folder_name}/{variant_folder_name}\n")
            f.write(f"Initialized: {datetime.datetime.now().isoformat()}\n")
            f.write("="*50 + "\n\n")

            if platform.system() == "Windows":
                try:
                    system_info_str = _get_system_info_windows()
                    f.write(system_info_str)
                except Exception as e_sysinfo_main:
                    f.write("--- System Information ---\n")
                    f.write(f"Error collecting system information: {e_sysinfo_main}\n")
                    f.write("="*50 + "\n\n")
            else:
                f.write("--- System Information ---\n")
                f.write("System information collection is currently focused on Windows.\n")
                f.write(f"OS Detected: {platform.system()} {platform.release()}\n")
                try: # Basic psutil info for non-Windows
                    info_non_win = []
                    info_non_win.append(f"Processor: {platform.processor()}")
                    info_non_win.append(f"CPU Cores: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")
                    ram = psutil.virtual_memory()
                    info_non_win.append(f"Total RAM: {ram.total / (1024**3):.2f} GB")
                    f.write("\n".join(info_non_win) + "\n")
                except Exception as e_psutil_nonwin:
                     f.write(f"Could not get basic psutil info: {e_psutil_nonwin}\n")
                f.write("="*50 + "\n\n")

        current_log_filepath = temp_log_filepath
        print(f"[LOGGER INFO] Interaction log initialized at: {current_log_filepath}")
    except IOError as e:
        print(f"[LOGGER ERROR] Could not initialize log file {temp_log_filepath}: {e}")
    except Exception as e_init:
        print(f"[LOGGER ERROR] Unexpected error during logger initialization or system info: {e_init}")


def _log_entry_content(target_document_name, mode_for_log, system_prompt, user_prompt, output_content, is_error=False):
    global current_log_filepath
    if not current_log_filepath:
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
            f.write(str(system_prompt) + "\n") # Ensure prompts are strings
            f.write("-" * 15 + " User Prompt " + "-"*15 + "\n")
            f.write(str(user_prompt) + "\n")
            f.write("---"*10 + "\n\n")
            f.write(f"{output_section_header}:\n")
            f.write(str(output_content) + "\n") # Ensure output is string
            f.write("--- Interaction End ---\n\n")
            f.write("="*50 + "\n\n")
    except IOError as e:
        print(f"[LOGGER ERROR] Could not write to log file {current_log_filepath}: {e}")
    except Exception as e:
        print(f"[LOGGER ERROR] Unexpected error during logging: {e}")

def log_interaction(target_document_name, analysis_mode_description, system_prompt, user_prompt, raw_llm_output):
    if not current_log_filepath:
        print(f"[LOGGER WARNING] Logger not initialized or failed. Skipping log entry for {target_document_name}.")
        return
    _log_entry_content(target_document_name, analysis_mode_description, system_prompt, user_prompt, raw_llm_output)

def log_error_interaction(target_document_name, analysis_mode_description, system_prompt, user_prompt, error_message, status_code=None):
    if not current_log_filepath:
        print(f"[LOGGER WARNING] Logger not initialized or failed. Skipping error log entry for {target_document_name}.")
        return
    error_output_content = (
        (f"HTTP Status Code: {status_code}\n" if status_code else "")
        + f"Error Message: {error_message}"
    )
    _log_entry_content(target_document_name, analysis_mode_description, system_prompt, user_prompt,
                       error_output_content, is_error=True)

def log_run_summary(total_files_processed_in_run, successful_analyses_in_run, total_pipeline_time_seconds, avg_time_per_file_seconds):
    global current_log_filepath
    if not current_log_filepath:
        return

    try:
        with open(current_log_filepath, 'a', encoding='utf-8') as f:
            f.write("--- Run Summary ---\n")
            f.write(f"Total JSON files processed in this run: {total_files_processed_in_run}\n")
            f.write(f"Successful LLM analyses in this run: {successful_analyses_in_run}\n")
            avg_time_str = format_duration(avg_time_per_file_seconds)
            f.write(f"Average processing time per successfully analyzed file: {avg_time_str}\n")
            total_time_str = format_duration(total_pipeline_time_seconds)
            f.write(f"Total pipeline time for this run: {total_time_str}\n")
            f.write("="*50 + "\n")
            f.write("--- End of Log ---\n")
    except IOError as e:
        print(f"[LOGGER ERROR] Could not write run summary to log file {current_log_filepath}: {e}")
    except Exception as e:
        print(f"[LOGGER ERROR] Unexpected error during run summary logging: {e}")