# ollama_utils.py
import requests
import json
import re
from typing import List, Tuple, Optional

# Importar configurações
import config

def list_ollama_models() -> List[str]:
    """Fetches the list of available models from the Ollama API."""
    try:
        print(f"[OLLAMA UTIL INFO] Tentando contactar: {config.OLLAMA_API_BASE_URL}{config.OLLAMA_TAGS_ENDPOINT_SUFFIX}")
        response = requests.get(
            f"{config.OLLAMA_API_BASE_URL}{config.OLLAMA_TAGS_ENDPOINT_SUFFIX}", 
            timeout=10
        )
        response.raise_for_status() # Lança uma exceção para códigos de erro HTTP
        models_data = response.json()
        
        # Extrair nomes de modelos. models_data.get("models", []) retorna uma lista vazia se "models" não existir.
        available_models = [model["name"] for model in models_data.get("models", []) if model.get("name")] # Garantir que 'name' existe

        if not available_models:
            # Este caso acontece se a API responder com sucesso (200 OK) mas a lista de modelos estiver vazia.
            print("[OLLAMA UTIL WARNING] API Ollama respondeu com sucesso, mas não retornou modelos. Usando lista padrão.")
            return [config.PREFERRED_RAG_AUX_LLM_NAME] # <<< ADICIONAR RETURN AQUI
        else:
            print(f"[OLLAMA UTIL INFO] Successfully fetched {len(available_models)} models from Ollama: {available_models}")
            return available_models

    except requests.exceptions.RequestException as e_req: # Erros de rede, DNS, timeout, etc.
        print(f"[OLLAMA UTIL ERROR] Erro de requisição ao contactar Ollama: {e_req}. Usando lista padrão.")
        return [config.PREFERRED_RAG_AUX_LLM_NAME]
    except json.JSONDecodeError as e_json: # Se a resposta não for JSON válido
        print(f"[OLLAMA UTIL ERROR] Erro ao descodificar resposta JSON do Ollama: {e_json}. Usando lista padrão.")
        return [config.PREFERRED_RAG_AUX_LLM_NAME]
    except Exception as e: # Outras exceções inesperadas
        print(f"[OLLAMA UTIL ERROR] Erro inesperado ao obter modelos do Ollama: {e}. Usando lista padrão.")
        return [config.PREFERRED_RAG_AUX_LLM_NAME]

def call_ollama_generate(
    model_name: str, 
    system_prompt: Optional[str], 
    user_prompt_with_data: str, 
    target_doc_name_for_info: str = ""
) -> Tuple[str, Optional[int]]:
    """
    Calls the Ollama /api/generate endpoint.
    Returns a tuple: (response_text, http_status_code).
    """
    payload = {
        "model": model_name,
        "system": system_prompt if system_prompt else "", 
        "prompt": user_prompt_with_data,
        "stream": True, 
        "keep_alive": config.OLLAMA_KEEP_ALIVE_DURATION 
    }
    endpoint = f"{config.OLLAMA_API_BASE_URL}{config.OLLAMA_GENERATE_ENDPOINT_SUFFIX}"
    
    full_response_content: List[str] = []
    raw_done_chunk_for_debug: Optional[dict] = None
    http_status: Optional[int] = None

    try:
        with requests.post(
            endpoint, 
            json=payload, 
            timeout=config.OLLAMA_REQUEST_TIMEOUT_SECONDS, 
            stream=True
        ) as response:
            http_status = response.status_code
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8', errors='ignore')
                    try:
                        chunk = json.loads(decoded_line)
                        if "response" in chunk and chunk["response"]:
                            full_response_content.append(chunk["response"])
                        if chunk.get("done", False):
                            raw_done_chunk_for_debug = chunk
                            if chunk.get("error"):
                                error_msg = f"Error in LLM 'done' signal from Ollama: {chunk.get('error')}"
                                print(f"[OLLAMA UTIL ERROR] {error_msg} for '{target_doc_name_for_info}'")
                                return error_msg, http_status
                            break 
                        if "error" in chunk:
                            error_msg = f"Error from Ollama API Stream: {chunk['error']}"
                            print(f"[OLLAMA UTIL ERROR] {error_msg} for '{target_doc_name_for_info}'")
                            return error_msg, http_status
                    except json.JSONDecodeError:
                        pass
                    except Exception as e_chunk:
                        print(f"[OLLAMA UTIL ERROR] Processing stream chunk for '{target_doc_name_for_info}': {e_chunk}")
            
            final_assessment_text = "".join(full_response_content).strip()
            
            # <think> tag removal logic REMOVED from here
            
            if not final_assessment_text and not (raw_done_chunk_for_debug and raw_done_chunk_for_debug.get("error")):
                warning_msg = "Warning: LLM produced an empty response."
                print(f"[OLLAMA UTIL WARNING] {warning_msg} for '{target_doc_name_for_info}'")
                return warning_msg, http_status
                
            return final_assessment_text, http_status

    # ... (except blocks como antes) ...
    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code if http_err.response else None
        error_text = http_err.response.text[:200] if http_err.response else "N/A"
        err_msg = f"Error: Ollama HTTPError for '{target_doc_name_for_info}': {http_err}. Response: {error_text}"
        print(f"[OLLAMA UTIL ERROR] {err_msg}")
        return err_msg, status_code
    except requests.exceptions.RequestException as req_err:
        err_msg = f"Error: Ollama RequestException for '{target_doc_name_for_info}': {req_err}"
        print(f"[OLLAMA UTIL ERROR] {err_msg}")
        return err_msg, None 
    except Exception as e_call:
        err_msg = f"Error: Unexpected Ollama call error for '{target_doc_name_for_info}': {e_call}"
        print(f"[OLLAMA UTIL ERROR] {err_msg}")
        return err_msg, None