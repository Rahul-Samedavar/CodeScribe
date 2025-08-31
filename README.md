# CodeScribe AI

CodeScribe AI is an AI-assisted tool that intelligently and automatically generates documentation (docstrings) for a given software project. It analyzes the project's dependency graph to document files in a logical order, providing context from already-documented dependencies to generate high-quality, consistent documentation.

## Features

- **Dependency-Aware:** Documents files with no dependencies first, then uses their new docstrings as context for documenting files that depend on them.
- **Flexible Input:** Works with both local directories and remote Git repositories.
- **Smart Filtering:** Exclude non-essential directories like `venv`, `tests`, or `node_modules`.
- **Resilient LLM Handler:**
  - Supports multiple API keys for Groq and Gemini.
  - Prioritizes faster/cheaper models (Groq) and fails over to others (Gemini).
  - Implements a smart rate-limiter with a 30-second cooldown to handle API limits gracefully.
- **In-place Updates:** Modifies your source files directly to add the generated docstrings.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <this-repo-url>
    cd codescribe-ai
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up API Keys:**
    - Rename `.env.example` to `.env`.
    - Open the `.env` file and add your API keys from Groq and/or Google Gemini. You can add multiple keys for each provider.

    ```
    # .env
    GROQ_API_KEY_1="gsk_YourGroqKeyHere"
    GEMINI_API_KEY_1="YourGeminiKeyHere"
    ```

## Usage

The tool is run from the command line.

```bash
python -m src.cli --path <path_or_url> --desc "<project_description>" [--exclude <pattern>]