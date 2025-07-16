import os
import requests
import utils
import json
import re
import sys

# --- Configuration ---

CONFIG = utils.read_config("config.json")
OUTPUT_DIR = CONFIG["OUTPUT_DIR"]
OLLAMA_API_URL = CONFIG["OLLAMA_API_URL"]
OLLAMA_MODEL = CONFIG["OLLAMA_MODEL"]
CHUNK_SIZE_CHARACTERS = CONFIG["CHUNK_SIZE_CHARACTERS"]
SUPPORTED_EXTENSIONS = {
    '.cs': 'csharp',
    '.ts': 'typescript',
    '.java': 'java',
    '.py': 'python',
    '.js': 'javascript',
    '.json': 'json',
    '.config': 'config',
    '.xml': 'xml',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.env': 'environment configuration',
    '.txt': 'text',
    '.sql': 'sql',
    '.go': 'golang',
    '.php': 'php',
}

SOURCE_CODE_DIR = None
DOC_OUTPUT_DIR = None

# --- Helper Functions ---

def get_file_type(extension):
    return SUPPORTED_EXTENSIONS.get(extension.lower(), 'unknown')

def scan_directory(root_dir):
    file_paths = []
    print(f"Starting scan of directory: {root_dir}")
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext.lower() in SUPPORTED_EXTENSIONS:
                file_paths.append(os.path.join(dirpath, filename))
    print(f"Found {len(file_paths)} supported files for documentation.")
    return file_paths

def read_file_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception as e:
            print(f"Error: Could not read file '{file_path}' with UTF-8 or Latin-1 encoding. Details: {e}")
            return None
    except Exception as e:
        print(f"Error: An unexpected error occurred while reading file '{file_path}'. Details: {e}")
        return None

def chunk_content(content, chunk_size):
    if not content:
        return []

    chunks = []
    current_chunk_lines = []
    current_length = 0
    lines = content.splitlines(keepends=True)

    for line in lines:
        if current_length + len(line) > chunk_size and current_chunk_lines:
            chunks.append("".join(current_chunk_lines))
            current_chunk_lines = [line]
            current_length = len(line)
        else:
            current_chunk_lines.append(line)
            current_length += len(line)

    if current_chunk_lines:
        chunks.append("".join(current_chunk_lines))
    return chunks

def document_with_ollama(chunk_text, file_name, file_type, part_info=""):
    prompt = f"""You are an expert software engineer and technical writer.
Your task is to analyze the following {file_type} code or configuration snippet from the file '{file_name}'.
{part_info} # This will be like "(Part 1 of 3)" or empty for single chunks.

Provide a detailed, human-readable explanation of what this code/config snippet does, its purpose, and its inner workings.
Focus on clarity and conciseness, making it easy for non-experts to understand.

**Key Requirements:**
1.  **For Code:** Identify any classes, functions, methods, or significant variables/enums within this snippet.
    **Bold their names** using Markdown (e.g., **ClassName**, **function_name()**, **CONSTANT_NAME**).
    Explain their roles and how they contribute to the overall functionality.
2.  **For Configuration Files:** Explain the structure, purpose of different sections/keys, and what values they typically hold.
3.  **Overall Context:** If this is part of a larger file, try to infer its context or contribution to the whole.

Code/Configuration snippet:
{chunk_text}
Documentation:
"""

    headers = {'Content-Type': 'application/json'}
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 1024
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        result = response.json()
        return result['response'].strip()
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Ollama at {OLLAMA_API_URL}.")
        print("Please ensure Ollama is running and the specified model is downloaded.")
        return f"**Error: Could not connect to Ollama.** Please ensure it's running at {OLLAMA_API_URL} and the model '{OLLAMA_MODEL}' is downloaded."
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err} - Response: {response.text}")
        return f"**Error from Ollama API:** {response.text}. Check Ollama logs for details."
    except Exception as e:
        print(f"An unexpected error occurred during Ollama request: {e}")
        return f"**Error:** An unexpected error occurred while communicating with Ollama: {e}"

def save_markdown(output_path, markdown_content):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"Documentation saved to: {output_path}")
        return True
    except Exception as e:
        print(f"Error: Could not save markdown to '{output_path}'. Details: {e}")
        return False

def generate_table_of_contents(documented_files_info, output_dir):
    toc_file_path = os.path.join(output_dir, "TABLE_OF_CONTENTS.md")
    toc_content = "# Project Documentation - Table of Contents\n\n"
    toc_content += "This file lists all documentation for project files.\n\n"
    toc_content += "---\n\n"

    if not documented_files_info:
        toc_content += "No supported files were documented.\n"
    else:
        documented_files_info.sort(key=lambda x: x[0].lower())

        for original_relative_path, md_full_path in documented_files_info:
            md_relative_to_toc = os.path.relpath(md_full_path, output_dir)
            toc_content += f"* [`{original_relative_path}`]({md_relative_to_toc})\n"

    save_markdown(toc_file_path, toc_content)
    print(f"\nTable of Contents generated at: {toc_file_path}")

# --- Main Execution Logic ---

def main_documentation(source_code_path, doc_output_path):
    global SOURCE_CODE_DIR, DOC_OUTPUT_DIR
    SOURCE_CODE_DIR = source_code_path
    DOC_OUTPUT_DIR = doc_output_path

    if not os.path.isdir(SOURCE_CODE_DIR):
        print(f"Error: The provided source path '{SOURCE_CODE_DIR}' is not a valid directory or does not exist.")
        sys.exit(1) # Exit with an error code to signal failure to the calling script (Gradio UI)

    os.makedirs(DOC_OUTPUT_DIR, exist_ok=True)
    print(f"Output documentation will be saved in: {os.path.abspath(DOC_OUTPUT_DIR)}")

    documented_files_info = []

    file_paths = scan_directory(SOURCE_CODE_DIR)

    if not file_paths:
        print("No supported files found in the specified directory. Exiting.")
        sys.exit(0)

    for file_path in file_paths:
        relative_path_of_code_file = os.path.relpath(file_path, SOURCE_CODE_DIR)
        base_name = os.path.basename(file_path)
        file_name_without_ext, ext = os.path.splitext(base_name)
        file_type = get_file_type(ext)

        output_sub_dir = os.path.join(DOC_OUTPUT_DIR, os.path.dirname(relative_path_of_code_file))
        output_file_name = f"{file_name_without_ext}_doc.md" # Distinct name for basic doc
        output_full_path_of_markdown_doc = os.path.join(output_sub_dir, output_file_name)

        print(f"\nProcessing file: {relative_path_of_code_file} (Type: {file_type.capitalize()})")
        content = read_file_content(file_path)

        if content is None:
            continue

        chunks = chunk_content(content, CHUNK_SIZE_CHARACTERS)

        full_markdown_doc = f"# Documentation for `{relative_path_of_code_file}`\n\n"
        full_markdown_doc += f"**Original File Type:** {file_type.capitalize()}\n\n"
        full_markdown_doc += f"--- \n\n"

        if len(chunks) > 1:
            print(f"File is large, splitting into {len(chunks)} chunks for processing.")
            for i, chunk in enumerate(chunks):
                part_info = f"(Part {i+1} of {len(chunks)})"
                print(f"  Documenting chunk {i+1}/{len(chunks)}...")
                chunk_doc = document_with_ollama(chunk, base_name, file_type, part_info)
                full_markdown_doc += f"## Part {i+1}\n\n{chunk_doc}\n\n---\n\n"
        else:
            print(f"  Documenting as a single chunk.")
            single_doc = document_with_ollama(content, base_name, file_type)
            full_markdown_doc += single_doc

        if save_markdown(output_full_path_of_markdown_doc, full_markdown_doc):
            documented_files_info.append((relative_path_of_code_file, output_full_path_of_markdown_doc))

    generate_table_of_contents(documented_files_info, DOC_OUTPUT_DIR)

    print("\nDocumentation generation complete!")
    print(f"Check the '{DOC_OUTPUT_DIR}' directory for your generated Markdown files and the TABLE_OF_CONTENTS.md.")

# --- Command Line Argument Parsing ---
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python code_documentation.py <source_code_path> <doc_output_path>")
        sys.exit(1)

    source_path = sys.argv[1]
    output_path = sys.argv[2]

    main_documentation(source_path, output_path)
