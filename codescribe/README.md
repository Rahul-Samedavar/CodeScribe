# Directory: codescribe

This directory contains the core logic for CodeScribe AI, a tool built for the Roo code hackathon, automating the generation of project documentation using Large Language Models (LLMs).  It leverages several key modules to achieve this:

* **`cli.py`**: Provides the command-line interface for interacting with CodeScribe.
* **`config.py`**: Manages API keys for different LLMs from environment variables.
* **`llm_handler.py`**:  Handles interaction with various LLMs (e.g., Groq, Gemini), managing API keys, rate limits, and errors.  It generates both structured JSON and plain text outputs.
* **`orchestrator.py`**: Orchestrates the entire documentation generation process, including project scanning, dependency analysis, docstring generation, and optionally pushing changes to a GitHub repository.  Handles both local paths and URLs as project sources.
* **`parser.py`**: Parses Python files to construct a project's dependency graph.
* **`readme_generator.py`**: Generates comprehensive README.md files for projects and subdirectories, utilizing LLMs and incorporating code analysis and user descriptions.
* **`scanner.py`**: Scans project directories and clones repositories from URLs.
* **`updater.py`**: Updates Python files with newly generated docstrings.
* **`__init__.py`**: Initialization file for the package.


There are no subdirectories with accompanying READMEs.