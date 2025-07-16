import os
import requests
import utils # Assuming utils.py exists and handles config reading
import json
import re
from collections import defaultdict
import sys # Import sys to access command-line arguments

# --- Configuration (can reuse or extend from code_documentation's config) ---

# These will be set based on command-line arguments, but we'll keep them
# as global variables for consistency with how they're used throughout the script.
# They will be overwritten by the main_analysis function's arguments.
CONFIG = utils.read_config("config.json") # Ensure config.json has these keys
OLLAMA_API_URL = CONFIG["OLLAMA_API_URL"]
OLLAMA_MODEL = CONFIG["OLLAMA_MODEL"]
CHUNK_SIZE_CHARACTERS = CONFIG["CHUNK_SIZE_CHARACTERS"] # Keep for large files
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
EXCLUDE_DIRS = CONFIG["EXCLUDE_DIRS"]

# Global variables to be set by main_analysis
SOURCE_CODE_DIR = None
DOC_OUTPUT_DIR = None


# --- Helper Functions (reused or slightly modified from code_documentation.py) ---

def get_file_type(extension):
    return SUPPORTED_EXTENSIONS.get(extension.lower(), 'unknown')

def scan_directory(root_dir):
    file_paths = []
    print(f"Starting scan of directory: {root_dir}")
    for dirpath, _, filenames in os.walk(root_dir):
        # Exclude specified directories
        if any(excluded_dir in dirpath for excluded_dir in EXCLUDE_DIRS):
            print(f"Skipping excluded directory: {dirpath}")
            continue

        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext.lower() in SUPPORTED_EXTENSIONS:
                file_paths.append(os.path.join(dirpath, filename))
    print(f"Found {len(file_paths)} supported files for analysis.")
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

def call_ollama_api(prompt):
    headers = {'Content-Type': 'application/json'}
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 2048
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
        return "**Error: Could not connect to Ollama.** Please ensure it's running."
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err} - Response: {response.text}")
        return f"**Error from Ollama API:** {response.text}. Check Ollama logs."
    except Exception as e:
        print(f"An unexpected error occurred during Ollama request: {e}")
        return f"**Error:** An unexpected error occurred while communicating with Ollama: {e}"

def save_analysis_report(output_path, report_content):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"Analysis report saved to: {output_path}")
        return True
    except Exception as e:
        print(f"Error: Could not save analysis report to '{output_path}'. Details: {e}")
        return False

# --- Core Analysis Functions ---

def analyze_code_for_refactoring_and_reuse(file_content, file_name, file_type, project_context=""):
    prompt = f"""You are an expert software architect and refactoring specialist.
Analyze the following {file_type} code snippet from the file '{file_name}'.
Consider the overall '{project_context}' if provided, to infer design patterns or common practices.

Provide detailed recommendations for:

1.  **Code Reuse/Refactoring:**
    * Identify duplicated code blocks or logic.
    * Suggest opportunities to extract common functionalities into reusable functions, classes, or modules.
    * Propose design pattern applications (e.g., Strategy, Factory, Singleton if appropriate) to improve maintainability and extensibility.
    * Recommend breaking down large functions/classes into smaller, more focused units.
    * Suggest improving code organization, modularity, and separation of concerns.
    * Highlight any "code smells" (e.g., long methods, large classes, primitive obsession, feature envy) and suggest specific refactoring techniques to address them.

2.  **Code Comments/IntelliSense Recommendations:**
    * Identify areas where inline comments or block comments would significantly improve code clarity, especially for complex logic, tricky algorithms, or non-obvious design choices.
    * Suggest appropriate docstrings/XML comments (e.g., for Python functions, C# methods, Java methods) detailing parameters, return values, exceptions, and overall purpose.
    * Recommend type hints or interface definitions where missing to improve static analysis and IntelliSense support.
    * Point out any unclear variable names, function names, or class names and suggest more descriptive alternatives.

3.  **Potential Dead Code Audit:**
    * Identify code blocks, functions, or variables that appear to be unused or unreachable based *solely on this snippet's context*.
    * Note: Acknowledge that a complete dead code audit requires whole-project static analysis, but provide initial suspicions.
    * Look for commented-out code that could potentially be removed.

Present your findings clearly, using Markdown for formatting (e.g., bullet points, code blocks).
Be specific in your recommendations, referencing line numbers or code patterns where possible.

Code snippet:
    {file_content}

Analysis and Recommendations:
"""
    return call_ollama_api(prompt)

# --- Main Execution Logic for Analysis ---

# Modified to accept source_code_path and doc_output_path as arguments
def main_analysis(source_code_path, doc_output_path):
    global SOURCE_CODE_DIR, DOC_OUTPUT_DIR
    SOURCE_CODE_DIR = source_code_path
    DOC_OUTPUT_DIR = doc_output_path

    if not os.path.isdir(SOURCE_CODE_DIR):
        print(f"Error: The provided source path '{SOURCE_CODE_DIR}' is not a valid directory or does not exist.")
        # Exit with an error code to signal failure to the calling script (Gradio UI)
        sys.exit(1)

    os.makedirs(DOC_OUTPUT_DIR, exist_ok=True)
    print(f"Analysis reports will be saved in: {os.path.abspath(DOC_OUTPUT_DIR)}")

    all_file_contents = {}
    file_paths = scan_directory(SOURCE_CODE_DIR)

    if not file_paths:
        print("No supported files found in the specified directory for analysis. Exiting.")
        # Exit with a success code if no files, as it's not an error, just no work to do
        sys.exit(0)

    # Phase 1: Read all file contents
    print("\nPhase 1: Reading file contents...")
    for file_path in file_paths:
        relative_path = os.path.relpath(file_path, SOURCE_CODE_DIR)
        content = read_file_content(file_path)
        if content is not None:
            all_file_contents[relative_path] = content
        else:
            print(f"Skipping analysis for {relative_path} due to read error.")

    # Phase 2: Analyze each file
    print("\nPhase 2: Analyzing individual files...")
    analyzed_files_info = []

    for relative_path, content in all_file_contents.items():
        base_name = os.path.basename(relative_path)
        file_name_without_ext, ext = os.path.splitext(base_name)
        file_type = get_file_type(ext)

        # Create output path for this file's analysis
        output_sub_dir = os.path.join(DOC_OUTPUT_DIR, os.path.dirname(relative_path))
        output_file_name = f"{file_name_without_ext}_analysis.md"
        output_full_path = os.path.join(output_sub_dir, output_file_name)

        print(f"\nAnalyzing file: {relative_path} (Type: {file_type.capitalize()})")

        chunks = chunk_content(content, CHUNK_SIZE_CHARACTERS)

        full_analysis_report = f"# Code Analysis Report for `{relative_path}`\n\n"
        full_analysis_report += f"**Original File Type:** {file_type.capitalize()}\n\n"
        full_analysis_report += f"--- \n\n"

        if len(chunks) > 1:
            print(f"File is large, splitting into {len(chunks)} chunks for analysis.")
            for i, chunk in enumerate(chunks):
                print(f"  Analyzing chunk {i+1}/{len(chunks)}...")
                # The LLM will have less context per chunk. This is a limitation.
                # A more advanced approach would be to summarize previous chunks or provide a higher-level prompt.
                chunk_analysis = analyze_code_for_refactoring_and_reuse(
                    chunk, base_name, file_type,
                    project_context=f"This is part {i+1} of {len(chunks)} of the file. Consider previous parts if they were processed, though this model only sees this chunk."
                )
                full_analysis_report += f"## Part {i+1} Analysis\n\n{chunk_analysis}\n\n---\n\n"
        else:
            print(f"  Analyzing as a single chunk.")
            single_analysis = analyze_code_for_refactoring_and_reuse(content, base_name, file_type)
            full_analysis_report += single_analysis

        if save_analysis_report(output_full_path, full_analysis_report):
            analyzed_files_info.append((relative_path, output_full_path))

    # Phase 3: Generate an overall summary (optional, but highly recommended)
    print("\nPhase 3: Generating overall project summary (if applicable)...")
    generate_overall_summary(all_file_contents, analyzed_files_info, SOURCE_CODE_DIR, DOC_OUTPUT_DIR)

    print("\nCode analysis complete!")
    print(f"Check the '{DOC_OUTPUT_DIR}' directory for your generated Markdown analysis reports.")

# No change needed here, it uses the global DOC_OUTPUT_DIR and SOURCE_CODE_DIR
def generate_overall_summary(all_file_contents, analyzed_files_info, root_dir, output_dir):
    summary_file_path = os.path.join(output_dir, "PROJECT_ANALYSIS_SUMMARY.md")
    summary_content = "# Project Code Analysis Summary\n\n"
    summary_content += "This report provides an overall summary of potential code reuse/refactoring opportunities, comment recommendations, and dead code suspicions across the analyzed codebase.\n\n"
    summary_content += "---\n\n"

    if not analyzed_files_info:
        summary_content += "No supported files were analyzed.\n"
        save_analysis_report(summary_file_path, summary_content)
        return

    # Create a simple table of contents for the analysis reports
    summary_content += "## Individual File Analysis Reports\n\n"
    analyzed_files_info.sort(key=lambda x: x[0].lower())
    for original_relative_path, md_full_path in analyzed_files_info:
        md_relative_to_summary = os.path.relpath(md_full_path, output_dir)
        summary_content += f"* [`{original_relative_path}`]({md_relative_to_summary})\n"
    summary_content += "\n---\n\n"

    file_list_str = "\n".join([f"- {path} ({get_file_type(os.path.splitext(path)[1])})" for path, _ in analyzed_files_info])
    overall_prompt = f"""You are an expert software architect tasked with providing a high-level summary of a codebase.
I have analyzed the following files in a project:

{file_list_str}

Based on typical code analysis patterns, what are common themes or areas that might show:
-   **Cross-file code reuse opportunities?** (e.g., similar utility functions across different files)
-   **Major refactoring areas that might span multiple files?** (e.g., inconsistencies in error handling, data structures, or common design patterns not being consistently applied)
-   **Overall documentation gaps or style inconsistencies?**
-   **General indications of potential dead code across the project (e.g., unused libraries, deprecated features)?**

Do not provide specific code examples, but rather high-level observations and recommendations for further investigation.

Overall Codebase Analysis Summary:
"""
    print("Requesting overall project analysis summary from Ollama...")
    overall_analysis = call_ollama_api(overall_prompt)
    summary_content += "## Overall Codebase Observations and Cross-File Recommendations\n\n"
    summary_content += overall_analysis
    summary_content += "\n\n---\n\n"
    summary_content += "### Important Note:\n"
    summary_content += "This summary is generated by an AI and provides high-level observations. Detailed investigation of individual file reports is crucial for accurate assessment and implementation of recommendations.\n"
    summary_content += "For comprehensive dead code auditing, consider using specialized static analysis tools."

    save_analysis_report(summary_file_path, summary_content)
    print(f"Overall project analysis summary generated at: {summary_file_path}")

# --- Command Line Argument Parsing ---
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python code_analysis.py <source_code_path> <doc_output_path>")
        sys.exit(1) # Exit with an error code

    source_path = sys.argv[1]
    output_path = sys.argv[2]

    main_analysis(source_path, output_path)
