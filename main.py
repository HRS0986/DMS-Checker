import time
from webdav3.client import Client
from webdav3.exceptions import WebDavException
from dotenv import load_dotenv
import os
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
    
    try:
        if client.check(REMOTE_TARGET_DIR):
            all_entries = client.list(REMOTE_TARGET_DIR)
            
            valid_files = []
            for entry in all_entries:
                if not entry or entry == REMOTE_TARGET_DIR or entry == "/":
                    continue
                if entry.endswith('/'):
                    continue
                # Ignore dat.txt to prevent processing the output file
                if entry == "dat.txt" or entry.endswith("/dat.txt"):
                    continue
                    
                remote_path = os.path.join(REMOTE_TARGET_DIR, entry).replace("\\", "/")
                if client.is_dir(remote_path):
                    continue
                valid_files.append((entry, remote_path))
            
            if not valid_files:
                return False
            
            print(f"\n[+] Remote folder '{REMOTE_TARGET_DIR}' found. Scanning entries...")
            print("--- Files found on WebDAV Server ---")
            for idx, (file_name, _) in enumerate(valid_files, start=1):
                print(f" {idx}. {file_name}")
            print("-------------------------------------")
            
            print(f"[+] Cleaning local folder: '{LOCAL_DOWNLOAD_DIR}/' before new downloads...")
            for f in os.listdir(LOCAL_DOWNLOAD_DIR):
                file_path = os.path.join(LOCAL_DOWNLOAD_DIR, f)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"[-] Failed to delete local file {file_path}: {e}")
            
            print(f"[+] Starting download pipeline for {len(valid_files)} file(s)...")
            for file_name, remote_file_path in valid_files:
                local_file_path = os.path.join(LOCAL_DOWNLOAD_DIR, file_name)
                print(f" -> Downloading '{file_name}'...")
                client.download_file(remote_file_path, local_file_path)
                
                # Delete from remote WebDAV so we don't process it again
                print(f" -> Deleting remote file '{file_name}' from Nextcloud...")
                client.clean(remote_file_path)
            
            print(f"[+] All files successfully saved to local folder and cleared from Nextcloud.")
            return True
            
    except WebDavException as e:
        print(f"\n[-] WebDAV Error encountered: {e}")
    except Exception as e:
        print(f"\n[-] An unexpected error occurred: {e}")
        
    return False

def upload_answer():
    if not os.path.exists("dat.txt"):
        print(f"[-] Upload aborted: 'dat.txt' file wasn't found.")
        return

    print(f"[*] Initializing connection to upload target to Nextcloud...")
    client = Client(WEBDAV_OPTIONS)

    try:
        # remote_answers_path = os.path.join(REMOTE_TARGET_DIR, "dat.txt").replace("\\", "/")
        client.upload_sync(local_path="dat.txt", remote_path="dat.txt")
        print(f"[+] Success! 'dat.txt' uploaded to Nextcloud at dat.txt.")
    except WebDavException as e:
        print(f"[-] WebDAV upload failed: {e}")
    except Exception as e:
        print(f"[-] Unexpected error during upload step: {e}")


if __name__ == "__main__":
    if not os.path.exists(LOCAL_DOWNLOAD_DIR):
        os.makedirs(LOCAL_DOWNLOAD_DIR)
        print(f"[+] Created local folder: '{LOCAL_DOWNLOAD_DIR}'")

    print(f"Connecting to Nextcloud WebDAV and watching folder '{REMOTE_TARGET_DIR}'...")
    
    while True:
        try:
            if check_and_download():
                # Remove old local dat.txt if it exists
                if os.path.exists("dat.txt"):
                    try:
                        os.remove("dat.txt")
                    except Exception as e:
                        print(f"[-] Failed to delete old dat.txt: {e}")

                process_images_to_text(LOCAL_DOWNLOAD_DIR, SUPPORTED_IMAGE_EXTS)   # OCR step
                if get_answer_from_llm():
                    upload_answer()
            else:
                print(".", end="", flush=True)
        except Exception as e:
            print(f"\n[-] Error in main loop: {e}")
            
        time.sleep(CHECK_INTERVAL)