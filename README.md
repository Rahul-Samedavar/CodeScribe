# CodeScribe AI

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

CodeScribe AI is a full-stack web application that automates the generation of comprehensive documentation for Python projects. It leverages multiple Large Language Models (LLMs) with built-in failover to create high-quality in-code docstrings and hierarchical `README.md` files, integrating seamlessly with GitHub or accepting direct ZIP uploads.


[![IMAGE ALT TEXT HERE](https://img.youtube.com/vi/t3y4ATQx33g/0.jpg)](https://www.youtube.com/watch?v=t3y4ATQx33g)


---

## ✨ Key Features

-   **Dual Input Methods**: Process projects directly from a GitHub repository or by uploading a `.zip` archive.
-   **Multi-LLM Backend**: Utilizes both Groq (Llama 3) and Google Gemini for fast and high-quality generation, ensuring robustness.
-   **Intelligent Failover**: Automatically cycles through available API keys and providers if rate limits are hit or errors occur.
-   **Dependency-Aware Processing**: Parses the project's import structure to build a dependency graph, ensuring that base modules are documented first to provide context for more complex ones.
-   **Comprehensive Docstring Generation**: Creates reStructuredText (reST) formatted docstrings for modules, classes, and functions, then surgically inserts them into your Python files.
-   **Hierarchical README Generation**: Generates a `README.md` for every directory, summarizing its contents, and uses them to build a comprehensive root-level README for the entire project.
-   **Seamless GitHub Integration**:
    -   Authenticates users via GitHub OAuth2.
    -   Fetches user repositories and branches.
    -   Pushes the documented code to a new branch.
    -   Provides a direct link to create a pull request with the changes.
-   **Real-Time Progress Streaming**: The web UI provides a live, detailed log of the entire documentation process, from file scanning to the final output.
-   **Customizable Exclusions**: Easily exclude files or directories using regex patterns or an interactive file-tree selector.

## ⚙️ How It Works

The application follows a sophisticated, multi-phase process to document a codebase:

1.  **Input & Setup**: A user provides a GitHub repository or a ZIP file. The project files are cloned or extracted into a temporary directory on the server.
2.  **Phase 1: Scanning & Dependency Analysis**
    -   The `scanner` module walks the project tree to identify all Python files, respecting exclusion rules.
    -   The `parser` module reads each file's content, uses Python's `ast` (Abstract Syntax Tree) library to find `import` statements, and builds a dependency graph using `networkx`.
3.  **Phase 2: Docstring Generation**
    -   The `DocstringOrchestrator` traverses the dependency graph in topological order (dependencies first).
    -   For each file, it constructs a detailed prompt containing the project description, the file's source code, and the docstrings of its dependencies for context.
    -   It sends this prompt to the `LLMHandler`, which selects an available API key (Groq or Gemini) to generate a JSON object containing all docstrings for that file (module, classes, functions).
    -   The `updater` module then uses the `ast` library to parse the original file, insert the newly generated docstrings, and overwrite the file with the updated code.
4.  **Phase 3: README Generation**
    -   The `ReadmeGenerator` performs a bottom-up traversal of the directory structure.
    -   For each directory, it summarizes the contained Python files (using their newly generated module docstrings) and the READMEs of its subdirectories.
    -   It uses the `LLMHandler` to generate a `README.md` for that directory.
    -   This process culminates in generating a final, comprehensive `README.md` for the project root.
5.  **Phase 4: Output**
    -   **For GitHub**: The application creates a new branch, commits all the changes, pushes the branch to the remote repository, and provides the user with a link to create a pull request.
    -   **For ZIP**: The application archives the modified project directory into a new ZIP file and provides the user with a download link.

## 🚀 Technology Stack

-   **Backend**: **FastAPI** on Python 3.9+
-   **Frontend**: Vanilla **JavaScript** (ES6+), HTML5, CSS3
-   **LLM Integration**:
    -   [Groq](https://groq.com/) API (`groq` library)
    -   [Google Gemini](https://ai.google.dev/) API (`google-generativeai` library)
-   **Code Analysis**: Python `ast`, `networkx`
-   **Git/GitHub**: `GitPython`, `PyGithub`
-   **Server**: `uvicorn`
-   **Dependencies**: `python-dotenv`, `requests`

## Project Structure

The project is organized into two main parts: the Python backend (`codescribe/` and server files) and the frontend (`static/`).

```
.
├── codescribe/              # Core documentation generation logic
│   ├── config.py            # Loads API keys and configuration from .env
│   ├── llm_handler.py       # Manages LLM API calls, failover, and rate limiting
│   ├── orchestrator.py      # Main controller for the docstring generation process
│   ├── parser.py            # Builds the dependency graph from source files
│   ├── readme_generator.py  # Generates README.md files for directories
│   ├── scanner.py           # Scans project files and handles Git cloning
│   └── updater.py           # Updates Python files with new docstrings
├── static/                  # Frontend assets
│   ├── script.js            # All client-side logic for the UI and API interaction
│   └── style.css            # Styles for the web interface
├── main.py                  # FastAPI application, defines all API endpoints
├── tasks.py                 # Asynchronous worker task for processing projects
├── index.html               # The main HTML file for the single-page application
└── .env.example             # Example environment file
```

## 🛠️ Setup and Running Locally

### 1. Prerequisites

-   Python 3.9 or newer
-   Git

### 2. Clone the Repository

```bash
git clone https://github.com/Rahul-Samedavar/CodeScribe.git
cd CodeScribe
```

### 3. Install Dependencies

It's recommended to use a virtual environment.

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
pip install -r requirements.txt
```

### 4. Configure Environment Variables

You need to set up API keys and GitHub OAuth credentials.

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    ```

2.  **Get LLM API Keys**:
    -   **Groq**: Create an account at [groq.com](https://groq.com/) and generate API keys.
    -   **Gemini**: Go to [Google AI Studio](https://aistudio.google.com/app/apikey) to get your API keys.

3.  **Set up a GitHub OAuth App**:
    -   Go to your GitHub Settings -> Developer settings -> OAuth Apps -> New OAuth App.
    -   **Application name**: CodeScribe AI (or anything you like)
    -   **Homepage URL**: `http://127.0.0.1:8000`
    -   **Authorization callback URL**: `http://127.0.0.1:8000/auth/github/callback`
    -   Generate a new client secret.

4.  **Edit the `.env` file** and fill in the values:

    ```env
    # LLM API Keys (you can add more by incrementing the number)
    GROQ_API_KEY_1="gsk_..."
    GROQ_API_KEY_2="gsk_..."
    GEMINI_API_KEY_1="AIzaSy..."
    GEMINI_API_KEY_2="AIzaSy..."

    # GitHub OAuth App Credentials
    GITHUB_CLIENT_ID="your_github_client_id"
    GITHUB_CLIENT_SECRET="your_github_client_secret"
    ```

### 5. Run the Application

```bash
uvicorn main:app --reload
```

The application will be available at **http://127.0.0.1:8000**.
