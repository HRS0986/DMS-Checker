import time
from webdav3.client import Client
from webdav3.exceptions import WebDavException
from dotenv import load_dotenv
import os
import easyocr
from pypdf import PdfReader
from llm import get_answer_from_llm
from extractors import extract_text_from_image, extract_text_from_pdf, process_images_to_text

load_dotenv()

# --- Configuration ---
WEBDAV_OPTIONS = {
    'webdav_hostname': os.getenv('WEBDAV_URL'),
    'webdav_login': os.getenv('WEBDAV_USERNAME'),
    'webdav_password': os.getenv('WEBDAV_PASSWORD'),
}

REMOTE_TARGET_DIR = os.getenv('REMOTE_TARGET_DIR', '/') 
LOCAL_DOWNLOAD_DIR = os.getenv('LOCAL_DOWNLOAD_DIR', 'quiz')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 5))

SUPPORTED_IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
SUPPORTED_TEXT_EXTS = ['.txt', '.pdf']
# ---------------------

def check_and_download():
    client = Client(WEBDAV_OPTIONS)
    
    if not os.path.exists(LOCAL_DOWNLOAD_DIR):
        os.makedirs(LOCAL_DOWNLOAD_DIR)
        print(f"[+] Created local folder: '{LOCAL_DOWNLOAD_DIR}'")
    
    print(f"Connecting to Nextcloud WebDAV and watching folder '{REMOTE_TARGET_DIR}'...")
    
    while True:
        try:
            if client.check(REMOTE_TARGET_DIR):
                print(f"\n[+] Remote folder '{REMOTE_TARGET_DIR}' found. Scanning entries...")
                
                all_entries = client.list(REMOTE_TARGET_DIR)
                
                valid_files = []
                for entry in all_entries:
                    if not entry or entry == REMOTE_TARGET_DIR or entry == "/":
                        continue
                    if entry.endswith('/'):
                        continue
                    remote_path = os.path.join(REMOTE_TARGET_DIR, entry).replace("\\", "/")
                    if client.is_dir(remote_path):
                        continue
                    valid_files.append(entry)
                
                print("--- Files found on WebDAV Server ---")
                if not valid_files:
                    print(" No files detected in this directory. Retrying...")
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                for idx, file_name in enumerate(valid_files, start=1):
                    print(f" {idx}. {file_name}")
                print("-------------------------------------")
                
                print(f"[+] Starting download pipeline for {len(valid_files)} file(s)...")
                for file_name in valid_files:
                    remote_file_path = os.path.join(REMOTE_TARGET_DIR, file_name).replace("\\", "/")
                    local_file_path = os.path.join(LOCAL_DOWNLOAD_DIR, file_name)
                    print(f" -> Downloading '{file_name}'...")
                    client.download_file(remote_file_path, local_file_path)
                
                print(f"[+] All files successfully saved to local folder: '{LOCAL_DOWNLOAD_DIR}/'")
                break
            else:
                print(".", end="", flush=True)
                
        except WebDavException as e:
            print(f"\n[-] WebDAV Error encountered: {e}")
            print("Retrying in the next cycle...")
        except Exception as e:
            print(f"\n[-] An unexpected error occurred: {e}")
            
        time.sleep(CHECK_INTERVAL)

def upload_answer():
    if not os.path.exists("answers.txt"):
        print(f"[-] Upload aborted: 'answers.txt' file wasn't found.")
        return

    print(f"[*] Initializing connection to upload target to Nextcloud...")
    client = Client(WEBDAV_OPTIONS)

    try:
        client.upload_sync(local_path="answers.txt", remote_path="answers.txt")
        print(f"[+] Success! 'answers.txt' uploaded to Nextcloud.")
    except WebDavException as e:
        print(f"[-] WebDAV upload failed: {e}")
    except Exception as e:
        print(f"[-] Unexpected error during upload step: {e}")


if __name__ == "__main__":
    check_and_download()
    process_images_to_text(LOCAL_DOWNLOAD_DIR, SUPPORTED_IMAGE_EXTS)   # OCR step — runs before LLM, adds ocr_extracted.txt to quiz/
    if get_answer_from_llm():
        upload_answer()