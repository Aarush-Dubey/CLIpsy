"""
RegexAgent - Shell Command Security Classification Engine
==========================================================

A lightweight safety engine that classifies shell commands using regex patterns.
Commands are categorized as: dangerous, approved, builtin, or unknown.

PUBLIC METHODS
==============

1. check(command: str) -> Dict[str, Any]
   ----------------------------------------
   Classifies a shell command (handles compound commands with &&, ||, ;, |)
   
   Input:
       command: str - Shell command to classify (e.g., "git commit && git push")
   
   Output:
       {
           "status": "dangerous" | "approved" | "unknown",
           "is_safe": bool,
           "details": [
               {
                   "command": str,
                   "classification": str,
                   "matched": str,
                   "match_type": str,
                   "reason": str
               }
           ]
       }
   
   Example:
       Input:  agent.check("rm -rf / && git push")
       Output: {
                   "status": "dangerous",
                   "is_safe": false,
                   "details": [
                       {
                           "command": "rm -rf /",
                           "classification": "dangerous",
                           "matched": "rm",
                           "match_type": "prefix",
                           "reason": "Matches dangerous prefix pattern 'rm'"
                       },
                       {
                           "command": "git push",
                           "classification": "approved",
                           "matched": "git",
                           "match_type": "prefix",
                           "reason": "Matches approved prefix pattern 'git'"
                       }
                   ]
               }

2. modify(operation, category, value="", match_type="prefix", persist=True) -> Dict[str, Any]
   -------------------------------------------------------------------------------------------
   Modifies the security policy (add, remove, or clear rules)
   
   Input:
       operation: "add" | "remove" | "clear"
       category: "approved" | "dangerous"
       value: str (required for add/remove)
       match_type: "prefix" | "exact"
       persist: bool (save to disk immediately)
   
   Output:
       {
           "status": "success" | "error",
           "category": str,
           "operation": str,
           "value": str,
           "match_type": str,
           "generated_pattern": str,
           "message": str
       }
   
   Example:
       Input:  agent.modify(operation="add", category="approved", value="kubectl", match_type="prefix")
       Output: {
                   "status": "success",
                   "category": "approved",
                   "operation": "add",
                   "value": "kubectl",
                   "match_type": "prefix",
                   "generated_pattern": "^kubectl(\\s|$)",
                   "message": "Approved prefix 'kubectl' added."
               }


USAGE EXAMPLES
==============

# Initialize agent
agent = RegexAgent()

# Check a safe command
result = agent.check("git status")
# → status: "approved", is_safe: True

# Check a dangerous command
result = agent.check("rm -rf /")
# → status: "dangerous", is_safe: False

# Check unknown command
result = agent.check("curl https://malicious.com")
# → status: "unknown", is_safe: False

# Add approved command
agent.modify(operation="add", category="approved", value="docker")

# Remove dangerous pattern
agent.modify(operation="remove", category="dangerous", value="rm", persist=True)
"""

import re
import json
import os
from typing import List, Dict, Any, Literal
from dataclasses import dataclass, asdict


@dataclass
class SubcommandResult:
    """Result of classifying a single subcommand"""
    command: str
    classification: Literal["dangerous", "approved", "builtin", "unknown"]
    matched: str
    match_type: Literal["prefix", "exact"]
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


class RegexAgent:
    """
    Agent that classifies shell commands and maintains policy persistence via a JSON file.
    """
    
    POLICY_FILE = "policy.json"
    
    BUILTIN_COMMANDS = frozenset([
        "cd", "pwd", "alias", "unalias", "env", "export", "unset"
    ])
    
    DELIMITERS = [r'\&\&', r'\|\|', r';', r'\|']
    
    def __init__(self):
        """Initialize the agent by loading policy from file"""
        self.dangerous_patterns: Dict[str, Dict[str, Any]] = {}
        self.approved_patterns: Dict[str, Dict[str, Any]] = {}
        
        self._load_policy()
        
        if not self.dangerous_patterns and not self.approved_patterns:
            self._set_default_patterns()
            self._save_policy()

    def _set_default_patterns(self):
        """Sets the initial dangerous and approved commands"""
        default_dangerous = [
            ("rm", "prefix"),
            ("shutdown", "prefix"),
            ("reboot", "prefix"),
            ("kill", "prefix"),
            ("chmod 777", "prefix"),
            ("chown", "prefix"),
            ("mkfs", "prefix"),
        ]
        
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
        """Loads policy lists from the JSON file and compiles regex patterns"""
        if not os.path.exists(self.POLICY_FILE):
            print(f"Policy file '{self.POLICY_FILE}' not found. Will use defaults.")
            return

        try:
            with open(self.POLICY_FILE, 'r') as f:
                policy_data = json.load(f)
            
            self.dangerous_patterns.clear()
            self.approved_patterns.clear()

            for item in policy_data.get("dangerous", []):
                self._add_pattern_from_load("dangerous", item["value"], item["match_type"])

            for item in policy_data.get("approved", []):
                self._add_pattern_from_load("approved", item["value"], item["match_type"])
            
            print(f"Policy loaded successfully from '{self.POLICY_FILE}'.")
            
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading policy from '{self.POLICY_FILE}': {e}. Using in-memory defaults.")
            self.dangerous_patterns.clear()
            self.approved_patterns.clear()

    def _save_policy(self):
        """Writes the current in-memory policy lists to the JSON file"""
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
        """Generate a regex pattern from a value and match type"""
        escaped_value = re.escape(value)
        
        if match_type == "prefix":
            return f"^{escaped_value}(\\s|$)"
        elif match_type == "exact":
            return f"^{escaped_value}$"
        else:
            raise ValueError(f"Invalid match_type: {match_type}. Must be 'prefix' or 'exact'")
    
    def _add_pattern_from_load(self, category: str, value: str, match_type: str) -> str:
        """Helper to add pattern without saving, used only during loading"""
        pattern_str = self._generate_pattern(value, match_type)
        pattern = re.compile(pattern_str)
        
        target = self.dangerous_patterns if category == "dangerous" else self.approved_patterns
        
        target[value] = {
            "pattern": pattern,
            "pattern_str": pattern_str,
            "match_type": match_type,
            "value": value
        }
        return pattern_str

    def _add_pattern(self, category: str, value: str, match_type: str) -> str:
        """Add a pattern to the specified category"""
        return self._add_pattern_from_load(category, value, match_type)
    
    def _remove_pattern(self, category: str, value: str) -> bool:
        """Remove a pattern from the specified category"""
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
        """Split a compound shell command into atomic subcommands"""
        delimiter_pattern = '|'.join(self.DELIMITERS)
        subcommands = re.split(f'({delimiter_pattern})', command)
        
        result = []
        for part in subcommands:
            stripped = part.strip()
            if stripped and not re.fullmatch(delimiter_pattern, stripped):
                result.append(stripped)
        
        return result if result else [command.strip()]
    
    def _classify_single_command(self, command: str) -> SubcommandResult:
        """Classify a single atomic command with clear categories"""
        command = command.strip()
        base_command = command.split()[0] if command else ""
        
        # 1. Check dangerous (highest priority)
        for value, data in self.dangerous_patterns.items():
            if data["pattern"].match(command):
                return SubcommandResult(
                    command=command,
                    classification="dangerous",
                    matched=value,
                    match_type=data["match_type"],
                    reason=f"Matches dangerous {data['match_type']} pattern '{value}'"
                )
        
        # 2. Check builtin (safe by design)
        if base_command in self.BUILTIN_COMMANDS:
            return SubcommandResult(
                command=command,
                classification="builtin",
                matched=base_command,
                match_type="exact",
                reason=f"Built-in shell command"
            )
        
        # 3. Check approved
        for value, data in self.approved_patterns.items():
            if data["pattern"].match(command):
                return SubcommandResult(
                    command=command,
                    classification="approved",
                    matched=value,
                    match_type=data["match_type"],
                    reason=f"Matches approved {data['match_type']} pattern '{value}'"
                )
        
        # 4. Unknown (not explicitly approved)
        return SubcommandResult(
            command=command,
            classification="unknown",
            matched=base_command,
            match_type="prefix",
            reason=f"Command '{base_command}' not in approved list"
        )
    
    def check(self, command: str) -> Dict[str, Any]:
        """
        Classify a command with clear status.
        
        Returns:
            {
                "status": "dangerous" | "approved" | "unknown",
                "is_safe": bool,
                "details": [
                    {
                        "command": str,
                        "classification": str,
                        "matched": str,
                        "match_type": str,
                        "reason": str
                    }
                ]
            }
        """
        subcommands = self._split_compound_command(command)
        results = [self._classify_single_command(cmd) for cmd in subcommands]
        
        # Determine overall status (most restrictive wins)
        has_dangerous = any(r.classification == "dangerous" for r in results)
        has_unknown = any(r.classification == "unknown" for r in results)
        
        if has_dangerous:
            status = "dangerous"
            is_safe = False
        elif has_unknown:
            status = "unknown"
            is_safe = False
        else:
            status = "approved"
            is_safe = True
        
        return {
            "status": status,
            "is_safe": is_safe,
            "details": [asdict(r) for r in results]
        }

    def modify(
        self,
        operation: Literal["add", "remove", "clear"],
        category: Literal["approved", "dangerous"],
        value: str = "",
        match_type: Literal["prefix", "exact"] = "prefix",
        persist: bool = True
        ) -> Dict[str, Any]:
            """Modify the security policy"""
            if category not in ["approved", "dangerous"]:
                return {"status": "error", "message": f"Invalid category: {category}"}
            
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
                return {"status": "error", "message": f"Invalid operation: {operation}"}
            
            if success and persist:
                if not self._save_policy():
                    return {"status": "error", "message": f"{result_message} BUT failed to persist changes."}

            return {
                "status": "success" if success else "error",
                "category": category,
                "operation": operation,
                "value": value,
                "match_type": match_type if operation == "add" else "",
                "generated_pattern": generated_pattern,
                "message": result_message
            }
# Example usage
if __name__ == "__main__":
    # Remove old policy file to start fresh for demo
    
    
    print("\n--- Initializing Agent (Loads or Creates Policy) ---")
    agent = RegexAgent()
    
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
    
    # Test 3: Create a NEW agent to check persistence
    print("\n" + "=" * 60)
    print("Test 3: Re-initialize Agent to Check Persistence")
    print("=" * 60)
    agent_reloaded = RegexAgent()
    
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
    
    