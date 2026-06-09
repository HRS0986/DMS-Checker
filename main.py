import time
from webdav3.client import Client
from webdav3.exceptions import WebDavException
from dotenv import load_dotenv
import os
import markdown2
from weasyprint import HTML
from google import genai

load_dotenv()

# --- Configuration ---
WEBDAV_OPTIONS = {
    'webdav_hostname': os.getenv('WEBDAV_URL'),
    'webdav_login': os.getenv('WEBDAV_USERNAME'),
    'webdav_password': os.getenv('WEBDAV_PASSWORD'),
}

# The remote folder in Nextcloud containing the files (ends with a slash)
REMOTE_TARGET_DIR = os.getenv('REMOTE_TARGET_DIR', '/') 
# Local folder where you want to save downloaded files
LOCAL_DOWNLOAD_DIR = os.getenv('LOCAL_DOWNLOAD_DIR', 'quiz')

# Time to wait (in seconds) between checks
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 5))
# ---------------------

def check_and_download():
    client = Client(WEBDAV_OPTIONS)
    
    # Ensure the local quiz directory exists
    if not os.path.exists(LOCAL_DOWNLOAD_DIR):
        os.makedirs(LOCAL_DOWNLOAD_DIR)
        print(f"[+] Created local folder: '{LOCAL_DOWNLOAD_DIR}'")
    
    print(f"Connecting to Nextcloud WebDAV and watching folder '{REMOTE_TARGET_DIR}'...")
    
    while True:
        try:
            # Check if the folder exists on the server
            if client.check(REMOTE_TARGET_DIR):
                print(f"\n[+] Remote folder '{REMOTE_TARGET_DIR}' found. Scanning entries...")
                
                # --- STAGE 1: List all items in the remote directory ---
                all_entries = client.list(REMOTE_TARGET_DIR)
                
                valid_files = []
                for entry in all_entries:
                    # Clean up entry string and filter out empty items or root path repetitions
                    if not entry or entry == REMOTE_TARGET_DIR or entry == "/":
                        continue
                    
                    # webdav3 lists directories usually with a trailing slash
                    if entry.endswith('/'):
                        continue
                        
                    # Construct full path to inspect if it is an accidental directory entry
                    remote_path = os.path.join(REMOTE_TARGET_DIR, entry).replace("\\", "/")
                    if client.is_dir(remote_path):
                        continue
                        
                    valid_files.append(entry)
                
                # Print the complete list of files found first
                print("--- Files found on WebDAV Server ---")
                if not valid_files:
                    print(" No files detected in this directory. Retrying...")
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                for idx, file_name in enumerate(valid_files, start=1):
                    print(f" {idx}. {file_name}")
                print("-------------------------------------")
                
                # --- STAGE 2: Download the listed files ---
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

def get_answer_from_llm():
    template_str = (
        "SYSTEM INSTRUCTION:\n"
        "You are a helpful question and answering assistant. "
        "You must answer the user's query based strictly on the context provided below. "
        "First determine the question type. If it is a MCQ, then answer with the correct option and no explanation needed. "
        "If it is a descriptive question, then answer in a concise manner. Just use simple text format since this is a text-based interface and saved in a txt file.\n\n"
        "CONTEXT FROM DOCUMENTS:\n"
        "---------------------\n"
        "{context_str}\n"
        "---------------------\n\n"
        "USER QUERY: {query_str}\n\n"
        "YOUR ANALYSIS: "
    )

    if not os.path.exists(LOCAL_DOWNLOAD_DIR) or not os.listdir(LOCAL_DOWNLOAD_DIR):
        print(f"[-] Error: The folder '{LOCAL_DOWNLOAD_DIR}' is empty or does not exist.")
        return None

    # Aggregate text content from all files inside the downloaded folder
    combined_query_content = []
    for file_name in os.listdir(LOCAL_DOWNLOAD_DIR):
        file_path = os.path.join(LOCAL_DOWNLOAD_DIR, file_name)
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    combined_query_content.append(file.read())
            except Exception as e:
                print(f"[-] Could not read file {file_name}: {e}")

    query = "\n\n".join(combined_query_content)

    if not os.path.exists("PP.txt"):
        print("[-] Error: 'PP.txt' context document was not found.")
        return None

    with open("PP.txt", 'r', encoding='utf-8') as file:
        data = file.read()

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=f"{template_str.format(context_str=data, query_str=query)}"
    )

    with open("answers.txt", "w", encoding='utf-8') as file:
        file.write(response.text)

    print(response.text)
    return True

def upload_answer_pdf():
    if not os.path.exists("answers.txt"):
        print(f"[-] Upload aborted: 'answers.txt' file wasn't found.")
        return

    print(f"[*] Initializing connection to upload target to Nextcloud...")
    client = Client(WEBDAV_OPTIONS)

    try:
        client.upload_sync(local_path="answers.txt", remote_path="answers.txt")
        print(f"[+] Success! Local file 'answers.txt' has been uploaded to Nextcloud storage as 'answers.txt'")
    except WebDavException as e:
        print(f"[-] WebDAV upload failed: {e}")
    except Exception as e:
        print(f"[-] Unexpected error during upload step: {e}")


if __name__ == "__main__":
    check_and_download()
    if get_answer_from_llm():
        upload_answer_pdf()