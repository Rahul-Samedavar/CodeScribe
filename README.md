# Project: Rahul-Samedavar/CodeScribe

**Overview:**

CodeScribe is a powerful AI-driven tool built for the Roo code hackathon, designed to automate the generation of comprehensive project documentation.  Leveraging the capabilities of Large Language Models (LLMs), CodeScribe analyzes Python projects, generates docstrings, and constructs detailed README files.  The application consists of a core documentation generation engine (`codescribe` directory) and a server component (`server` directory) that handles user requests and manages interactions with GitHub repositories.  Static assets for a potential web interface are located in the `static` directory.  The project's primary entry point is `run.py`.

**Project Structure:**

The project is structured into three main directories:

* **`codescribe`:** This directory houses the core logic for generating documentation.  It includes modules for command-line interaction (`cli.py`), LLM management (`llm_handler.py`), project scanning (`scanner.py`), dependency parsing (`parser.py`), README generation (`readme_generator.py`), docstring updating (`updater.py`), configuration (`config.py`), and the overall orchestration of the documentation process (`orchestrator.py`).

* **`server`:** This directory contains the server-side components of the application. The `main.py` file serves as the application's entry point, managing GitHub authentication and the processing pipeline.  `tasks.py` contains the business logic for processing documentation generation tasks for GitHub repositories.

* **`static`:** This directory is reserved for static assets (e.g., images, CSS, JavaScript) that would be used by a web interface. Currently, it's empty but will be populated with assets as needed.


**Key Features:**

* **AI-Powered Documentation Generation:**  Utilizes LLMs to automatically generate high-quality documentation, including docstrings and README files.
* **Multi-LLM Support:**  The system is designed to interact with various LLMs (e.g., Groq, Gemini), offering flexibility and potentially improved performance.
* **Comprehensive Project Analysis:**  Performs in-depth analysis of Python projects, including dependency parsing, to create accurate and insightful documentation.
* **GitHub Integration:**  Supports interaction with GitHub repositories, enabling the automated generation and potential updating of documentation directly within GitHub projects. Both local paths and URLs as project sources are supported.
* **Command-Line Interface:**  Provides a user-friendly command-line interface for easy interaction with the tool.
* **Modular Design:**  The project is built using a modular approach, making it extensible and maintainable.
* **Automated Docstring Updates:**  Can automatically update Python source code with newly generated docstrings.


**Getting Started:**

(Further instructions on setting up and running the application would be added here, including installation dependencies, environment variables, and usage examples.)

**Contributing:**

(Instructions for contributing to the project would be added here, including guidelines for code style, testing, and submission of pull requests.)

**License:**

(The project's license would be specified here.)