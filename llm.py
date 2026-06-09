def get_answer_from_llm():
    from google import genai

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

    combined_query_content = []

    for file_name in os.listdir(LOCAL_DOWNLOAD_DIR):
        file_path = os.path.join(LOCAL_DOWNLOAD_DIR, file_name)
        if not os.path.isfile(file_path):
            continue

        ext = os.path.splitext(file_name)[1].lower()

        if ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if content.strip():
                    combined_query_content.append(f"--- From: {file_name} ---\n{content}")
            except Exception as e:
                print(f"[-] Could not read file {file_name}: {e}")

        elif ext == '.pdf':
            content = extract_text_from_pdf(file_path)
            if content.strip():
                combined_query_content.append(f"--- From: {file_name} ---\n{content}")

        elif ext in SUPPORTED_IMAGE_EXTS:
            # Images should already be handled by process_images_to_text()
            # Skip here to avoid double processing
            continue

        else:
            print(f"[*] Skipping unsupported file: {file_name}")

    if not combined_query_content:
        print("[-] No readable content found to send to LLM.")
        return None

    query = "\n\n".join(combined_query_content)

    if not os.path.exists("PP.txt"):
        print("[-] Error: 'PP.txt' context document was not found.")
        return None

    with open("PP.txt", 'r', encoding='utf-8') as file:
        data = file.read()

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{template_str.format(context_str=data, query_str=query)}"
    )

    with open("answers.txt", "w", encoding='utf-8') as file:
        file.write(response.text)

    print(response.text)
    return True