# file_utils.py
import os
from typing import List

def get_json_files_from_dir(base_script_dir: str, dir_name: str) -> List[str]:
    """
    Gets a list of .json file paths from a specified directory.
    The directory is relative to the base_script_dir.
    """
    json_files: List[str] = []
    directory_path = os.path.join(base_script_dir, dir_name)

    if not os.path.isdir(directory_path):
        print(f"[FILE UTIL WARNING] Directory not found: {directory_path}")
        return []
    
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(".json"):
            json_files.append(os.path.join(directory_path, filename))
            
    if not json_files:
        print(f"[FILE UTIL INFO] No JSON files found in '{directory_path}'.")
    else:
        print(f"[FILE UTIL INFO] Found {len(json_files)} JSON files in '{directory_path}'.")
        
    return json_files