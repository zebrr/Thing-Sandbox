# Thing' Sandbox

Experimental LLM-powered text simulation inspired by D&D/MUD games where AI-controlled characters autonomously interact in a persistent world.

## Setup

### Prerequisites

- Python 3.11 or higher
- pip

### Installation

1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

### Development

Run quality checks:
```bash
ruff check src/
ruff format src/
mypy src/
```

Run tests:
```bash
pytest -v
```
