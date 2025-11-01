import re
import json
import os
from typing import List, Dict, Any, Literal, Union
from dataclasses import dataclass, asdict


# --- Data Classes ---

@dataclass
class SubcommandResult:
    """Result of classifying a single subcommand"""
    command: str
    category: Literal["builtin", "dangerous", "approved", "external"]
    matched: str
    match_type: Literal["prefix", "exact"]
    is_safe: bool
    reason: str


@dataclass
class ModifyResult:
    """Result of modifying the policy"""
    status: str
    category: str
    operation: str
    value: str
    match_type: str
    generated_pattern: str
    message: str


# --- Core Agent Class ---

class RegexCommandAgent:
    """
    Agent that classifies shell commands and maintains policy persistence via a JSON file.
    """
    
    # Configuration
    POLICY_FILE = "policy.json"
    
    # Immutable builtin commands
    BUILTIN_COMMANDS = frozenset([
        "cd", "pwd", "alias", "unalias", "env", "export", "unset"
    ])
    
    # Shell command delimiters
    DELIMITERS = [r'\&\&', r'\|\|', r';', r'\|']
    
    def __init__(self):
        """
        Initialize the agent by loading policy from file, or setting defaults and saving if file doesn't exist.
        """
        self.dangerous_patterns: Dict[str, Dict[str, Any]] = {}
        self.approved_patterns: Dict[str, Dict[str, Any]] = {}
        
        self._load_policy()
        
        # If the policy file was empty or didn't exist, set and save defaults
        if not self.dangerous_patterns and not self.approved_patterns:
            self._set_default_patterns()
            self._save_policy()

    def _set_default_patterns(self):
        """Sets the initial dangerous and approved commands."""
        # Default dangerous commands
        default_dangerous = [
            ("rm", "prefix"),
            ("shutdown", "prefix"),
            ("reboot", "prefix"),
            ("kill", "prefix"),
            ("chmod 777", "prefix"),
            ("chown", "prefix"),
            ("mkfs", "prefix"),
        ]
        
        # Default approved commands
        default_approved = [
            ("python", "prefix"),
            ("manim", "prefix"),
            ("git", "prefix"),
            ("node", "prefix"),
        ]
        
        for value, match_type in default_dangerous:
            self._add_pattern("dangerous", value, match_type)
        
        for value, match_type in default_approved:
            self._add_pattern("approved", value, match_type)

    def _load_policy(self):
        """
        Loads policy lists from the JSON file and compiles regex patterns.
        """
        if not os.path.exists(self.POLICY_FILE):
            print(f"Policy file '{self.POLICY_FILE}' not found. Will use defaults.")
            return

        try:
            with open(self.POLICY_FILE, 'r') as f:
                policy_data = json.load(f)
            
            self.dangerous_patterns.clear()
            self.approved_patterns.clear()

            # Load dangerous patterns
            for item in policy_data.get("dangerous", []):
                self._add_pattern_from_load("dangerous", item["value"], item["match_type"])

            # Load approved patterns
            for item in policy_data.get("approved", []):
                self._add_pattern_from_load("approved", item["value"], item["match_type"])
            
            print(f"Policy loaded successfully from '{self.POLICY_FILE}'.")
            
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading policy from '{self.POLICY_FILE}': {e}. Using in-memory defaults.")
            # Critical error: fall back to an empty state or defaults
            self.dangerous_patterns.clear()
            self.approved_patterns.clear()

    def _save_policy(self):
        """
        Writes the current in-memory policy lists to the JSON file.
        Only saves the value and match_type, not the compiled regex object.
        """
        serializable_policy = {
            "dangerous": [
                {"value": data["value"], "match_type": data["match_type"]}
                for data in self.dangerous_patterns.values()
            ],
            "approved": [
                {"value": data["value"], "match_type": data["match_type"]}
                for data in self.approved_patterns.values()
            ]
        }
        
        try:
            with open(self.POLICY_FILE, 'w') as f:
                json.dump(serializable_policy, f, indent=4)
            print(f"Policy saved successfully to '{self.POLICY_FILE}'.")
            return True
        except IOError as e:
            print(f"Error saving policy to '{self.POLICY_FILE}': {e}")
            return False

    def _generate_pattern(self, value: str, match_type: str) -> str:
        """
        Generate a regex pattern from a value and match type.
        """
        escaped_value = re.escape(value)
        
        if match_type == "prefix":
            # Match command at start, followed by space or end of string
            return f"^{escaped_value}(\\s|$)"
        elif match_type == "exact":
            # Match entire command exactly
            return f"^{escaped_value}$"
        else:
            raise ValueError(f"Invalid match_type: {match_type}. Must be 'prefix' or 'exact'")
    
    def _add_pattern_from_load(self, category: str, value: str, match_type: str) -> str:
        """Helper to add pattern without saving, used only during loading."""
        pattern_str = self._generate_pattern(value, match_type)
        pattern = re.compile(pattern_str)
        
        target = self.dangerous_patterns if category == "dangerous" else self.approved_patterns
        
        # Store both the pattern and metadata
        target[value] = {
            "pattern": pattern,
            "pattern_str": pattern_str,
            "match_type": match_type,
            "value": value
        }
        return pattern_str

    def _add_pattern(self, category: str, value: str, match_type: str) -> str:
        """
        Add a pattern to the specified category.
        
        Returns:
            The generated pattern string
        """
        return self._add_pattern_from_load(category, value, match_type)
    
    def _remove_pattern(self, category: str, value: str) -> bool:
        """
        Remove a pattern from the specified category.
        
        Returns:
            True if removed, False if not found
        """
        target = self.dangerous_patterns if category == "dangerous" else self.approved_patterns
        
        if value in target:
            del target[value]
            return True
        return False
    
    def _clear_patterns(self, category: str):
        """Clear all patterns from the specified category"""
        if category == "dangerous":
            self.dangerous_patterns.clear()
        else:
            self.approved_patterns.clear()
    
    def _split_compound_command(self, command: str) -> List[str]:
        """
        Split a compound shell command into atomic subcommands. (Original implementation kept)
        """
        delimiter_pattern = '|'.join(self.DELIMITERS)
        subcommands = re.split(f'({delimiter_pattern})', command)
        
        result = []
        for part in subcommands:
            stripped = part.strip()
            if stripped and not re.fullmatch(delimiter_pattern, stripped):
                result.append(stripped)
        
        return result if result else [command.strip()]
    
    def _classify_single_command(self, command: str) -> SubcommandResult:
        """
        Classify a single atomic command. (Original implementation kept)
        """
        command = command.strip()
        base_command = command.split()[0] if command else ""
        
        # 1. Check dangerous
        for value, data in self.dangerous_patterns.items():
            if data["pattern"].match(command):
                return SubcommandResult(
                    command=command, category="dangerous", matched=value, match_type=data["match_type"],
                    is_safe=False, reason=f"Dangerous {data['match_type']} '{value}' detected"
                )
        
        # 2. Check builtin
        if base_command in self.BUILTIN_COMMANDS:
            return SubcommandResult(
                command=command, category="builtin", matched=base_command, match_type="prefix",
                is_safe=True, reason="Builtin command detected"
            )
        
        # 3. Check approved
        for value, data in self.approved_patterns.items():
            if data["pattern"].match(command):
                return SubcommandResult(
                    command=command, category="approved", matched=value, match_type=data["match_type"],
                    is_safe=True, reason=f"Approved {data['match_type']} '{value}' detected"
                )
        
        # 4. Default to external
        return SubcommandResult(
            command=command, category="external", matched=base_command, match_type="prefix",
            is_safe=False, reason=f"External command '{base_command}' not in approved list"
        )
    
    def check(self, command: str) -> Dict[str, Any]:
        """
        Classify a command (handles compound expressions). (Original implementation kept)
        """
        subcommands = self._split_compound_command(command)
        results = [self._classify_single_command(cmd) for cmd in subcommands]
        
        is_safe = all(r.is_safe for r in results)
        
        reason = "All commands are safe"
        if not is_safe:
            for r in results:
                if not r.is_safe:
                    reason = f"Contains {r.category} command '{r.command}'"
                    break
        
        return {
            "summary": {"is_safe": is_safe, "reason": reason},
            "subcommands": [asdict(r) for r in results]
        }
    
    def modify(
        self,
        operation: Literal["add", "remove", "clear"],
        category: Literal["approved", "dangerous"],
        value: str = "",
        match_type: Literal["prefix", "exact"] = "prefix",
        persist: bool = True # Defaulting to True for convenience, but False is better for safety (as previously discussed)
    ) -> Dict[str, Any]:
        """
        Modify the security policy.

        Args:
            operation: The operation to perform (add, remove, clear)
            category: The category to modify (approved or dangerous)
            value: The command value (required for add/remove)
            match_type: The match type (prefix or exact)
            persist: Whether to persist changes to the JSON file immediately (Default: True).
        """
        # ... (Validation remains the same)
        if category not in ["approved", "dangerous"]:
             return {"status": "error", "message": f"Invalid category: {category}. Must be 'approved' or 'dangerous'"}
        
        result_message = ""
        success = False
        generated_pattern = ""
        
        if operation == "clear":
            self._clear_patterns(category)
            success = True
            result_message = f"All {category} patterns cleared."
        
        elif operation == "add":
            if not value:
                 return {"status": "error", "message": "Value is required for 'add' operation"}
            generated_pattern = self._add_pattern(category, value, match_type)
            success = True
            result_message = f"{category.capitalize()} {match_type} '{value}' added."
        
        elif operation == "remove":
            if not value:
                 return {"status": "error", "message": "Value is required for 'remove' operation"}
            
            if self._remove_pattern(category, value):
                success = True
                result_message = f"{category.capitalize()} pattern '{value}' removed."
            else:
                success = False
                result_message = f"Pattern '{value}' not found in {category} list."
        
        else:
            return {"status": "error", "message": f"Invalid operation: {operation}. Must be 'add', 'remove', or 'clear'"}
        
        # --- Persistence Logic ---
        if success and persist:
            if not self._save_policy():
                 return {"status": "error", "message": f"{result_message} BUT failed to persist changes to file."}

        # --- Return Result ---
        return {
            "status": "success" if success else "error",
            "category": category,
            "operation": operation,
            "value": value,
            "match_type": match_type if operation == "add" else "",
            "generated_pattern": generated_pattern,
            "message": result_message
        }
    
    def get_policy(self) -> Dict[str, Any]:
        """
        Get the current security policy.
        
        Returns:
            Dictionary containing all current patterns
        """
        # NOTE: This only saves the necessary fields for persistence (value, match_type)
        # The 'pattern' field here is generated for display/audit, showing the full regex string.
        return {
            "builtin": list(self.BUILTIN_COMMANDS),
            "dangerous": [
                {
                    "value": data["value"],
                    "match_type": data["match_type"],
                    "pattern": data["pattern_str"]
                }
                for data in self.dangerous_patterns.values()
            ],
            "approved": [
                {
                    "value": data["value"],
                    "match_type": data["match_type"],
                    "pattern": data["pattern_str"]
                }
                for data in self.approved_patterns.values()
            ]
        }


# Example usage
if __name__ == "__main__":
    # Remove old policy file to start fresh for demo
    if os.path.exists(RegexCommandAgent.POLICY_FILE):
        os.remove(RegexCommandAgent.POLICY_FILE)
        print(f"Removed old '{RegexCommandAgent.POLICY_FILE}' for fresh start.")
    
    print("\n--- Initializing Agent (Loads or Creates Policy) ---")
    agent = RegexCommandAgent()
    
    # Test 1: Add new approved pattern and persist (persist=True is default)
    print("\n" + "=" * 60)
    print("Test 1: Add and Persist 'kubectl'")
    print("=" * 60)
    result = agent.modify(
        operation="add",
        category="approved",
        value="kubectl",
        match_type="prefix",
        persist=True # Explicitly setting, though it's the new default
    )
    print(json.dumps(result, indent=2))
    
    # Check the policy after modification
    print("\n" + "=" * 60)
    print("Test 2: View current policy after ADD")
    print("=" * 60)
    policy = agent.get_policy()
    print(f"Policy file size: {os.path.getsize(RegexCommandAgent.POLICY_FILE)} bytes")
    print("Approved commands:", [d['value'] for d in policy['approved']])
    
    # Test 3: Create a NEW agent to check persistence
    print("\n" + "=" * 60)
    print("Test 3: Re-initialize Agent to Check Persistence")
    print("=" * 60)
    agent_reloaded = RegexCommandAgent()
    
    # Check if the added command is present
    result = agent_reloaded.check("kubectl apply -f config.yaml")
    print(f"Checking 'kubectl apply...' in reloaded agent:")
    print(json.dumps(result, indent=2))
    
    # Test 4: Remove a command without persisting
    print("\n" + "=" * 60)
    print("Test 4: Remove 'kubectl' WITHOUT Persist")
    print("=" * 60)
    agent_reloaded.modify(
        operation="remove",
        category="approved",
        value="kubectl",
        persist=False # Should only change in memory
    )
    
    # Check policy on disk (should still have kubectl)
    print(f"Approved list in memory BEFORE re-load:", [d['value'] for d in agent_reloaded.get_policy()['approved']])

    agent_reloaded_again = RegexCommandAgent() # Forces reload from disk
    print(f"Approved list on disk AFTER NO-PERSIST REMOVE:", [d['value'] for d in agent_reloaded_again.get_policy()['approved']])