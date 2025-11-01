import os
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# --- Actual Classes Provided by the User ---

class ShellState:
    """
    Maintains the internal state for a Python-based shell.
    """
    def __init__(self):
        # We patch os.getcwd() in the fixture, but the class logic is here
        self.cwd: str = os.getcwd() 
        self.aliases: Dict[str, str] = {}
        self.last_exit_code: int = 0
        self.shell_vars: Dict[str, str] = {}
        self.env_vars: Dict[str,str] = {}
        self.old_cwd: str = self.cwd
    
    # Custom method to compare state for testing
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ShellState):
            return NotImplemented
        # Compare all relevant attributes for state mutation tests
        return (self.cwd == other.cwd and
                self.old_cwd == other.old_cwd and
                self.last_exit_code == other.last_exit_code and
                self.env_vars == other.env_vars and
                self.aliases == other.aliases and
                self.shell_vars == other.shell_vars)
    
    def __repr__(self):
        # A detailed repr helps pytest display comparison failures
        return (f"ShellState(cwd={self.cwd!r}, old_cwd={self.old_cwd!r}, "
                f"last_exit_code={self.last_exit_code}, env_vars={self.env_vars!r}, "
                f"aliases={self.aliases!r}, shell_vars={self.shell_vars!r})")


class CommandResult:
    """Represents the outcome of executing a shell command."""
    def __init__(self, stdout: str = "", stderr: str = "", exit_code: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code

    def __bool__(self):
        return self.exit_code == 0

    def __repr__(self):
        return f"CommandResult(code={self.exit_code}, stdout={self.stdout!r}, stderr={self.stderr!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CommandResult):
            return NotImplemented
        return (self.exit_code == other.exit_code and
                self.stdout == other.stdout and
                self.stderr == other.stderr)


