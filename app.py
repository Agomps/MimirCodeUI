import gradio as gr
import zipfile
import os
import shutil
import subprocess
import uuid
import datetime

# --- Configuration ---
TEMP_BASE_DIR = "temp"
DOC_OUTPUT_BASE_DIR = "generated_docs"
CODE_DOC_SCRIPT = "python code_documentation.py"
DEEP_DOC_SCRIPT = "python deep_documentation.py"
CODE_ANALYSIS_SCRIPT = "python code_analyzer.py"

# --- Helper Functions ---

def create_and_get_session_paths(session_id):
    session_temp_dir = os.path.join(TEMP_BASE_DIR, session_id)
    extracted_path = os.path.join(session_temp_dir, "extracted_code")
    os.makedirs(extracted_path, exist_ok=True)
    return session_temp_dir, extracted_path

def create_and_get_doc_output_path(session_id):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_doc_session_dir_name = f"{timestamp}_{session_id}"
    doc_output_path = os.path.join(DOC_OUTPUT_BASE_DIR, unique_doc_session_dir_name)
    os.makedirs(doc_output_path, exist_ok=True)
    print(f"Documentation output path created: {doc_output_path}")
    return doc_output_path

def extract_zip(zip_filepath, extract_to_path):
    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_to_path)
        return True
    except Exception as e:
        print(f"Error extracting zip file: {e}")
        return False

def run_external_script(script_command, extracted_code_path, doc_temp_path):
    try:
        command = f"{script_command} {extracted_code_path} {doc_temp_path}"
        print(f"Executing command: {command}")
        process = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        print(f"Script output (stdout):\n{process.stdout}")
        print(f"Script output (stderr):\n{process.stderr}")
        return True, process.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running script: {e}")
        print(f"Script stdout on error:\n{e.stdout}")
        print(f"Script stderr on error:\n{e.stderr}")
        return False, f"Error: {e.stderr if e.stderr else e.stdout}"
    except FileNotFoundError:
        return False, f"Error: Script not found or not executable: {script_command}"
    except Exception as e:
        return False, f"An unexpected error occurred: {e}"

def zip_documentation_output(doc_output_path):
    zip_basename = os.path.basename(doc_output_path)
    output_zip_filepath_no_ext = os.path.join(os.path.dirname(doc_output_path), zip_basename)

    print(f"Zipping contents of {doc_output_path} to {output_zip_filepath_no_ext}.zip")
    shutil.make_archive(output_zip_filepath_no_ext, 'zip', doc_output_path)

    final_zip_path = output_zip_filepath_no_ext + ".zip"
    print(f"Zip created at: {final_zip_path}")
    return final_zip_path if os.path.exists(final_zip_path) else None


def process_code(zip_file, action):
    if zip_file is None:
        return "Please upload a zip file.", None

    session_id = str(uuid.uuid4())
    session_temp_dir, extracted_code_path = create_and_get_session_paths(session_id)
    doc_output_path = create_and_get_doc_output_path(session_id) # New separate path for docs

    output_message = ""
    download_file = None

    try:
        if not extract_zip(zip_file.name, extracted_code_path):
            output_message = "Failed to extract zip file."
            if os.path.exists(session_temp_dir):
                shutil.rmtree(session_temp_dir)
            if os.path.exists(doc_output_path):
                shutil.rmtree(doc_output_path)
            return output_message, None

        script_to_run = ""
        if action == "Code Documentation":
            script_to_run = CODE_DOC_SCRIPT
        elif action == "Deep Code Documentation":
            script_to_run = DEEP_DOC_SCRIPT
        elif action == "Code Analysis":
            script_to_run = CODE_ANALYSIS_SCRIPT
        else:
            output_message = "Invalid action selected."
            if os.path.exists(session_temp_dir):
                shutil.rmtree(session_temp_dir)
            if os.path.exists(doc_output_path):
                shutil.rmtree(doc_output_path)
            return output_message, None

        # Run the external script
        success, script_output = run_external_script(script_to_run, extracted_code_path, doc_output_path)

        if success:
            output_message = f"Operation '{action}' completed successfully.\n\nScript Output:\n{script_output}"
            zipped_docs_filepath = zip_documentation_output(doc_output_path)
            if zipped_docs_filepath:
                download_file = gr.File(value=zipped_docs_filepath, label="Download Documentation Zip", visible=True)
                output_message += f"\n\nGenerated documentation available at: {os.path.abspath(doc_output_path)}"
            else:
                output_message += "\n\nFailed to create documentation zip file."
                download_file = None
        else:
            output_message = f"Operation '{action}' failed.\n\nError: {script_output}"
            download_file = None

    except Exception as e:
        output_message = f"An unexpected error occurred during processing: {e}"
        download_file = None
    finally:
        if os.path.exists(session_temp_dir):
            try:
                shutil.rmtree(session_temp_dir)
                print(f"Cleaned up session temporary directory: {session_temp_dir}")
            except Exception as e:
                print(f"Warning: Could not clean up {session_temp_dir}: {e}")

    return output_message, download_file

# --- Gradio UI ---
with gr.Blocks() as mimir_code_ui:
    gr.Markdown(
    """
    # MimirCode UI
    Upload a zip file containing your project's source code and choose an action to perform.
    """
    )

    with gr.Row():
        zip_file_input = gr.File(type="filepath", label="Upload Project Zip File")

    with gr.Row():
        doc_button = gr.Button("Code Documentation")
        deep_doc_button = gr.Button("Deep Code Documentation")
        analysis_button = gr.Button("Code Analysis")

    output_text = gr.Textbox(label="Status/Output", lines=10)
    download_output = gr.File(label="Download Generated Documents", visible=False)

    doc_button.click(
        process_code,
        inputs=[zip_file_input, gr.State("Code Documentation")],
        outputs=[output_text, download_output]
    )
    deep_doc_button.click(
        process_code,
        inputs=[zip_file_input, gr.State("Deep Code Documentation")],
        outputs=[output_text, download_output]
    )
    analysis_button.click(
        process_code,
        inputs=[zip_file_input, gr.State("Code Analysis")],
        outputs=[output_text, download_output]
    )

if __name__ == "__main__":
    os.makedirs(TEMP_BASE_DIR, exist_ok=True)
    os.makedirs(DOC_OUTPUT_BASE_DIR, exist_ok=True)
    mimir_code_ui.launch()
