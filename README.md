# CLIpsy

CLIpsy is a Python-based CLI wrapper that provides a terminal-like interface with AI assistance and conversation history. It simulates a shell, supports built-in commands, and integrates AI for command execution and safety.

## Features
- Simulates a shell with custom state (working directory, aliases, shell/environment variables).
- Supports AI-assisted command execution and conversation history.
- Classifies and checks commands for safety before execution using regex and policy rules.
- Built-in command handling (e.g., `cd`, `pwd`, `alias`, `export`, etc.).
- Alias management and extensible shell state.
- Extensible for integration with LLMs (OpenAI, Google, etc.).

## Project Structure
```
main.py           # Entry point; sets up CLI and imports core modules
core/
  builtin.py      # Implements built-in shell commands
  executor.py     # Safe shell command execution with safety checks
  regex.py        # Command classification and safety engine
  shellstate.py   # Maintains shell state (cwd, aliases, etc.)
  test.py         # Basic test script for command execution
brain/
  brain.py        # AI integration and agent management
policy.json       # Defines dangerous command patterns for safety
requirements.txt  # Python dependencies
README.md         # Project documentation
```

## Getting Started
1. Clone the repository and install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2. Run the CLI:
    ```bash
    python main.py
    ```

## Safety
- Commands are classified as `dangerous`, `approved`, `builtin`, or `unknown` before execution.
- Dangerous commands (e.g., `rm`, `shutdown`, `kill`) are blocked or require explicit approval.
- Safety policies are defined in `policy.json` and regex patterns in `core/regex.py`.

## Extending
- Add new built-in commands in `core/builtin.py`.
- Update safety rules in `policy.json` and `core/regex.py`.
- Integrate new LLMs or AI agents in `brain/brain.py`.

## License
MIT License
