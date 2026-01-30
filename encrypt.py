import ujson
import os

'''
    Простенький шифрувальник, потрібно створити файл variables.env в якому визначити значення для secret_key, наприклад "MySecretKey123"
    Зміни назву на свій CONFIG_FILE
'''
ENV_FILE = "variables.env"
CONFIG_FILE = "config.json"
ENV_VAR_NAME = "secret_key"

def _get_key():
    """
    Function for search secret_key in file variables.env.
    """
    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                # Pass comments
                if not line or line.startswith("#"):
                    continue
                
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() == ENV_VAR_NAME:
                        return value.strip().strip('"').strip("'")
    except OSError:
        print(f"[Error]: file {ENV_FILE} does not founded!")
    
    print(f"[Error]: key {ENV_VAR_NAME} does not founded!")
    return None

def _xor_cipher(data_bytes, key_str):
    """XOR encrypting/decrypting"""
    if not key_str:
        return data_bytes
        
    key_bytes = key_str.encode('utf-8')
    key_len = len(key_bytes)
    result = bytearray(len(data_bytes))
    
    for i in range(len(data_bytes)):
        result[i] = data_bytes[i] ^ key_bytes[i % key_len]
        
    return result

def save_config(data_dict):
    """Save current config in ecrypted version"""
    key = _get_key()
    if not key:
        return False

    try:
        json_str = ujson.dumps(data_dict)
        encrypted_data = _xor_cipher(json_str.encode('utf-8'), key)
        
        with open(CONFIG_FILE, "wb") as f:
            f.write(encrypted_data)
            
        print(f"[OK] Saved and encrypted {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"[ERROR] Can't save config: {e}")
        return False

def load_config():
    """Load encrypted file and decrypt him"""
    key = _get_key()
    if not key:
        return None

    try:
        with open(CONFIG_FILE, "rb") as f:
            file_data = f.read()
        try:
            return ujson.loads(file_data)
        except ValueError:
            pass

        decrypted_data = _xor_cipher(file_data, key)
        
        json_str = decrypted_data.decode('utf-8')
        return ujson.loads(json_str)

    except OSError:
        print(f"[INFO] File {CONFIG_FILE} still exist.")
        return None
    except Exception as e:
        print(f"[ERROR] Reading/encrypting error: {e}")
        return None

def encrypt_existing_file():
    """
    Utillity to encrypt existing non-crypted config.json file
    """
    print("encrypt_existing_file() begin")
    try:
        with open(CONFIG_FILE, "r") as f:
            data = ujson.load(f)
        if save_config(data):
            print("File saved in encrypted fromat")
    except ValueError:
        print("File encrypted or invalid")
    except OSError:
        print("No file")