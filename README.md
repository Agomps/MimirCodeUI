# MimirCodeUI
GradioUI frontend for MimirCode: A Smart Code Analyzer and Documentation Utility

MimirCode is a Python-based tool that simplifies code analysis, documentation, and usage. It takes existing code projects or folders, breaks them into smaller parts, and sends them to a local instance of Ollama for a thorough analysis. 

MimirCode allows a local LLM to dive into code, determining its structure, function, and purpose. The resulting documentation is clear and easy-to-understand, explaining each component's role, interaction with other parts of the project, and usage examples. This makes it easier for developers to navigate through complex projects, learn new concepts quickly, and utilize the code effectively.

# Setting Up
To get started with this project on your local machine, follow these steps:

1. First, clone the repository containing the project files to your local computer using a command line tool like Git Bash or Terminal. For example:
   ```
   git clone https://github.com/Agomps/MimirCode.git
   ```

2. Navigate to the project directory:
   ```
   cd MimirCode
   ```
   
3. Create a new Python virtual environment using the venv module:
   ```
   python3 -m venv venv
   ```
   This command creates a folder called `venv` in your current directory, which will contain all the necessary files for the isolated Python environment.

4. Activate the virtual environment by running:
   ```
   source venv/bin/activate
   ```
   This step puts the virtual environment into effect, so that any packages installed or modifications made to Python during this session are local to the project and don't affect other projects on your machine.

5. With the virtual environment active, you can now install the required dependencies using pip:
   ```
   pip install -r requirements.txt
   ```

After completing these steps, your local environment should be set up and ready for developing or running the project.

## To Run the MimirCodeUI

```bash
python3 app.py
```
