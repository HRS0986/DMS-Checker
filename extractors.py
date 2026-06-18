import os
import easyocr
from pypdf import PdfReader

def extract_text_from_image(file_path, reader):
    """Extract text from an image file using EasyOCR."""
    print(f"   [OCR] Running EasyOCR on '{os.path.basename(file_path)}'...")
    results = reader.readtext(file_path, detail=0, paragraph=True)
    extracted = "\n".join(results)
    print(f"   [OCR] Extracted {len(extracted)} characters.")
    return extracted


def extract_text_from_pdf(file_path):
    """Extract text from a PDF file using pypdf."""
    try:
        reader = PdfReader(file_path)
        pages_text = [page.extract_text() for page in reader.pages if page.extract_text()]
        return "\n".join(pages_text)
    except Exception as e:
        print(f"[-] Failed to read PDF {file_path}: {e}")
        return ""

def process_images_to_text(filepath_to_check, supported_image_types):
    """
    Scan the download folder for image files, run OCR on each,
    and save all extracted text into a single 'ocr_extracted.txt' file.
    Returns the output path if any images were processed, else None.
    """
    image_files = [
        f for f in os.listdir(filepath_to_check)
        if os.path.splitext(f)[1].lower() in supported_image_types
    ]

    if not image_files:
        print("[*] No image files found in download folder. Skipping OCR step.")
        return None

    print(f"\n[+] Found {len(image_files)} image file(s). Initializing EasyOCR reader...")
    # Initialize once — loading the model is expensive
    reader = easyocr.Reader(['en'], gpu=False)  # set gpu=True if CUDA is available

    all_extracted_text = []

    for file_name in image_files:
        file_path = os.path.join(filepath_to_check, file_name)
        print(f" -> Processing image: '{file_name}'")

        text = extract_text_from_image(file_path, reader)

        if text.strip():
            all_extracted_text.append(f"--- Extracted from: {file_name} ---\n{text}")
        else:
            print(f"   [!] No text detected in '{file_name}'. Skipping.")

    if not all_extracted_text:
        print("[-] OCR produced no usable text from any image.")
        return None

    output_path = os.path.join(filepath_to_check, "ocr_extracted.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_extracted_text))

    print(f"[+] OCR complete. Extracted text saved to '{output_path}'")
    return output_path