# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- **Run the application**: `python main.py`
- **Setup**:
  - Linux: `./setup.sh` (installs Tesseract and dependencies)
  - Windows: `setup.bat` (install Tesseract manually from link provided)
- **Install Python dependencies**: `pip install -r requirements.txt`
- **Run with VPN check**: Use `run.bat` on Windows
- **Development mode**: Use `python dev.py` or `./dev.sh` (disables VPN check)
- **Environment variables**:
  - `ENABLE_VPN_CHECK=False`: Disable VPN check
  - `HEADLESS_BROWSER=True/False`: Set browser mode
  - `TESSERACT_PATH=/path/to/tesseract`: Override Tesseract binary path
  - `OBJECT_DETECTION_ENABLED=True/False`: Enable/disable object detection
  - `PRODUCT_SEARCH_ENABLED=True/False`: Enable/disable product identification
  - `CLOUD_VISION_ENABLED=True/False`: Enable/disable Google Cloud Vision API
  - `NETWORK_TIMEOUT=60000`: Network timeout in milliseconds
  - `USE_GOOGLE_API=True/False`: Use Google Custom Search API (requires API key)
  - `ENABLE_AMAZON_SEARCH=True/False`: Enable Amazon product search
  - `OPENROUTER_ENABLED=True/False`: Enable LLM-based search query generation
  - `OPENROUTER_API_KEY=yourapikey`: Your OpenRouter API key
  - `OPENROUTER_MODEL=anthropic/claude-3-opus-20240229`: LLM model to use (default is Claude Opus)
- **Tests**: Currently no test framework implemented

## Code Style Guidelines

- **Imports**: Group standard library, third-party, and local imports with a blank line between each group
- **Formatting**: Follow PEP 8 guidelines with 4 spaces for indentation
- **Types**: Use docstrings to document parameter and return types
- **Naming**:
  - Classes: `CamelCase`
  - Functions/variables: `snake_case`
  - Constants: `UPPER_CASE`
- **Error Handling**: Use try/except blocks with specific exception types and proper logging
- **Logging**: Use the `setup_logger` function from `utils.logger` for new components
- **Documentation**: Use docstrings for all functions and classes
- **File Organization**: Follow the existing module structure (scraper, analyzer, utils)