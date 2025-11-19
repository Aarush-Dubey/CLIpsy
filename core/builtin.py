
"""
BuiltinHandler Module
---------------------

This module defines the BuiltinHandler class, which implements built-in shell commands 
(like `cd`, `pwd`, `alias`, `export`, etc.) for a custom CLI or shell simulation.

Each command updates or retrieves information from a ShellState object, which maintains 
environment variables, aliases, working directory, and shell variables.

Public Functions:
-----------------
- handle(cmd: str) -> CommandResult        : Entry point that dispatches a command to its handler.

Private Function (should not be called)
- _handle_cd(cmd: str) -> CommandResult    : Change current working directory.
- _handle_pwd(cmd: str) -> CommandResult   : Print current working directory.
- _handle_alias(cmd: str) -> CommandResult : Create, list, or update command aliases.
- _handle_unalias(cmd: str) -> CommandResult : Remove alias(es).
- _handle_export(cmd: str) -> CommandResult : Set or export environment variables.
- _handle_unset(cmd: str) -> CommandResult  : Remove environment or shell variables.
- _handle_env(cmd: str) -> CommandResult    : Display all environment variables.

Example Usage:
--------------
If you give this input:
    handler.handle("alias greet='echo Hello'")
    handler.handle("alias")

You will get this output:
    alias greet='echo Hello'
"""

import os
from core.shellstate import ShellState, CommandResult


class BuiltinHandler:
    def __init__(self, state: ShellState):
        self.state = state
        self.builtins = {
            'cd': self._handle_cd,
            'pwd': self._handle_pwd,
            'alias': self._handle_alias,
            'unalias': self._handle_unalias,
            'export': self._handle_export,
            'unset': self._handle_unset,
            'env': self._handle_env
        }

    def _handle_cd(self, cmd: str) -> CommandResult:
        arg = cmd.strip().split(maxsplit=1)

        if len(arg) == 1 or arg[1].strip() == "":
            target = self.state.env_vars.get("HOME", os.path.expanduser("~"))
        else:
            target = arg[1].strip()

        if target == "-":
            target = self.state.old_cwd

        target = os.path.expandvars(os.path.expanduser(target))
        if not os.path.isabs(target):
            target = os.path.join(self.state.cwd, target)
        target = os.path.abspath(target)

        if not os.path.isdir(target):
            err = f"cd: no such file or directory: {target}\n"
            self.state.last_exit_code = 1
            return CommandResult(stderr=err, exit_code=1)

        try:
            os.chdir(target)
            self.state.old_cwd = self.state.cwd
            self.state.cwd = target
            self.state.last_exit_code = 0
            return CommandResult(stdout="", exit_code=0)
        except Exception as e:
            err = f"cd: {e}\n"
            self.state.last_exit_code = 1
            return CommandResult(stderr=err, exit_code=1)

    def _handle_pwd(self, cmd: str) -> CommandResult:
        arg = cmd.strip().split()
        use_physical = "-P" in arg
        
        cwd = os.getcwd()
        if use_physical:
            cwd = os.path.realpath(cwd)
            
        print(cwd);

        return CommandResult(stdout=cwd + "\n", exit_code=0)

    def _handle_alias(self, cmd: str) -> CommandResult:
        arg = cmd.strip().split(maxsplit=1)
        
        # List all aliases
        if len(arg) == 1:
            if not self.state.aliases:
                return CommandResult(stdout="", exit_code=0)
            
            output = []
            for k, v in self.state.aliases.items():
                output.append(f"alias {k}='{v}'")
            return CommandResult(stdout="\n".join(output) + "\n", exit_code=0)
        
        # Create/update alias
        try:
            # Handle different formats: alias name=value, alias name='value', alias name="value"
            alias_def = arg[1]
            
            if "=" not in alias_def:
                return CommandResult(stderr="alias: invalid format. Use alias name='value'\n", exit_code=1)
            
            name, value = alias_def.split("=", 1)
            name = name.strip()
            value = value.strip()
            
            # Remove quotes if present
            if (value.startswith("'") and value.endswith("'")) or \
               (value.startswith('"') and value.endswith('"')):
                value = value[1:-1]
            
            self.state.aliases[name] = value
            return CommandResult(exit_code=0)
        except ValueError:
            return CommandResult(stderr="alias: invalid format. Use alias name='value'\n", exit_code=1)

    def _handle_unalias(self, cmd: str) -> CommandResult:
        tokens = cmd.strip().split()
        
        # If only "unalias" is given → error
        if len(tokens) == 1:
            return CommandResult(stderr="unalias: missing operand\n", exit_code=1)
        
        # Handle "unalias -a" → remove all
        if len(tokens) == 2 and tokens[1] == "-a":
            self.state.aliases.clear()
            return CommandResult(exit_code=0)
        
        # Otherwise → remove specific aliases
        errors = []
        for name in tokens[1:]:
            if name in self.state.aliases:
                del self.state.aliases[name]
            else:
                errors.append(f"unalias: {name}: not found")
        
        # Build result
        if errors:
            return CommandResult(stderr="\n".join(errors) + "\n", exit_code=1)
        return CommandResult(exit_code=0)

    def _handle_export(self, cmd: str) -> CommandResult:
        tokens = cmd.strip().split(maxsplit=1)

        # Case 1: only "export" → list all env vars
        if len(tokens) == 1:
            output = "\n".join(f"{k}={v}" for k, v in self.state.env_vars.items())
            if output:
                output += "\n"
            return CommandResult(stdout=output, exit_code=0)

        # Case 2: "export VAR=value" or multiple separated by space
        # We need to be careful with quoted values containing spaces
        rest = tokens[1]
        assignments = []
        current = []
        in_quotes = None
        
        for char in rest:
            if char in ('"', "'") and in_quotes is None:
                in_quotes = char
                current.append(char)
            elif char == in_quotes:
                in_quotes = None
                current.append(char)
            elif char == ' ' and in_quotes is None:
                if current:
                    assignments.append(''.join(current))
                    current = []
            else:
                current.append(char)
        
        if current:
            assignments.append(''.join(current))

        for assignment in assignments:
            if "=" in assignment:
                name, value = assignment.split("=", 1)
                name = name.strip()
                value = value.strip()
                
                # Remove quotes
                if (value.startswith("'") and value.endswith("'")) or \
                   (value.startswith('"') and value.endswith('"')):
                    value = value[1:-1]
                
                self.state.env_vars[name] = value
                os.environ[name] = value
            else:
                # Case: "export VAR" → mark existing var as exported if present
                name = assignment.strip()
                if name in self.state.shell_vars:
                    val = self.state.shell_vars[name]
                    self.state.env_vars[name] = val
                    os.environ[name] = val
                else:
                    # If variable doesn't exist, create empty
                    self.state.env_vars[name] = ""
                    os.environ[name] = ""

        return CommandResult(exit_code=0)

    def _handle_unset(self, cmd: str) -> CommandResult:
        tokens = cmd.strip().split()
        
        if len(tokens) == 1:
            return CommandResult(stderr="unset: missing operand\n", exit_code=1)
        
        errors = []
        for name in tokens[1:]:
            removed = False
            if name in self.state.env_vars:
                del self.state.env_vars[name]
                if name in os.environ:
                    del os.environ[name]
                removed = True
            if name in self.state.shell_vars:
                del self.state.shell_vars[name]
                removed = True
            if not removed:
                errors.append(f"unset: {name}: not found")

        if errors:
            return CommandResult(stderr="\n".join(errors) + "\n", exit_code=1)
        return CommandResult(exit_code=0)

    def _handle_env(self, cmd: str) -> CommandResult:
        tokens = cmd.strip().split()
        
        # Just "env" → list all environment variables
        if len(tokens) == 1:
            output = "\n".join(f"{k}={v}" for k, v in self.state.env_vars.items())
            if output:
                output += "\n"
            return CommandResult(stdout=output, exit_code=0)
        
        return CommandResult(stderr="env: command execution not implemented\n", exit_code=1)
    
    def handle(self, cmd: str) -> CommandResult:
        if not cmd.strip():
            return CommandResult(exit_code=0, stdout="", stderr="")

        name = cmd.split()[0]
        
        func = self.builtins.get(name)

        if func:
            return func(cmd)
        else:
            return CommandResult(exit_code=1, stdout="", stderr=f"{name}: command not found\n")