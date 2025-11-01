from shellstate import CommandResult , ShellState
from regex import RegexAgent
from builtin import BuiltinHandler
import subprocess
from typing import Dict, Any


class ExecutorAgent:
    """
    ExecutorAgent - Safe Shell Command Executor
    ============================================
    
    Safely executes shell commands by checking safety first, then integrating
    RegexAgent and BuiltinHandler. ALL commands (including builtins) are checked
    for safety before execution.
    
    Public Method:
    --------------
    execute(cmd: str) -> CommandResult
        Executes a shell command with safety checks and user approval flow.
    """
    
    # Builtin commands that should be handled by BuiltinHandler
    BUILTIN_COMMANDS = {
        'cd', 'pwd', 'alias', 'unalias', 'export', 'unset', 'env'
    }
    
    def __init__(self, regex_agent: RegexAgent, builtin_handler: BuiltinHandler):
        """
        Initialize ExecutorAgent.
        
        Args:
            regex_agent: Instance of RegexAgent for command classification
            builtin_handler: Instance of BuiltinHandler for builtin commands
        """
        self.regex_agent = regex_agent
        self.builtin_handler = builtin_handler
    
    def execute(self, cmd: str , capture_output : True) -> CommandResult:
        """
        Execute a shell command with safety checks.
        
        Args:
            cmd: Shell command to execute
            
        Returns:
            CommandResult object with stdout, stderr, and exit_code
        """
        # Handle empty commands
        if not cmd or not cmd.strip():
            return CommandResult(stdout="", stderr="", exit_code=0)
        
        cmd = cmd.strip()
        
        # CRITICAL: Check safety FIRST before doing anything else
        classification_result = self.regex_agent.check(cmd)
        print(classification_result)
        status = classification_result.get("status", "unknown")
        is_safe = classification_result.get("is_safe", False)
        
        
        # Determine if this is a builtin command
        first_word = cmd.split()[0] if cmd.split() else ""
        is_builtin = first_word in self.BUILTIN_COMMANDS
        
        # Decision flow based on safety and classification
        if is_safe and status == "approved":
            # Safe and approved - execute directly
            if is_builtin:
                return self._execute_builtin(cmd)
            else:
        
                return self._execute_approved(cmd ,capture_output)
        
        elif status == "dangerous":
            # Dangerous command - ask for confirmation (never approve)
            return self._handle_dangerous(cmd, is_builtin , capture_output)
        
        else:  # unknown or not safe
            # Unknown command - ask for approval
            return self._handle_unknown(cmd, is_builtin , capture_output)
    
    def _execute_builtin(self, cmd: str) -> CommandResult:
        """Execute builtin command via BuiltinHandler."""
        return self.builtin_handler.handle(cmd)
    
    def _execute_approved(self, cmd: str , capture_output) -> CommandResult:
        """Execute approved command directly."""
        return self._run_subprocess(cmd , capture_output)
    
    def _handle_dangerous(self, cmd: str, is_builtin: bool ,capture_output : bool) -> CommandResult:
        """Handle dangerous command with confirmation prompt."""
        print("⚠️ Dangerous command detected. Run anyway? [y/n]: ", end="")
        response = input().strip().lower()
        
        if response == 'y':
            print("Executing...")
            if is_builtin:
                return self._execute_builtin(cmd)
            else:
                return self._run_subprocess(cmd , capture_output)
        else:
            print("Command blocked")
            return CommandResult(
                stdout="",
                stderr="Command blocked by user",
                exit_code=1
            )
    
    def _handle_unknown(self, cmd: str, is_builtin: bool , capture_output) -> CommandResult:
        """Handle unknown command with approval prompt."""
        print("Command not approved. Approve? [y/n/a/p]: ", end="")
        response = input().strip().lower()
        
        if response == 'y':
            # Execute once without approving
            
            if is_builtin:
                return self._execute_builtin(cmd)
            else:
                return self._run_subprocess(cmd ,capture_output)
        
        elif response == 'n':
            # Skip execution
            print("Command blocked")
            return CommandResult(
                stdout="",
                stderr="Command blocked by user",
                exit_code=1
            )
        
        elif response == 'a':
            # Approve exact command and execute
            self._approve_exact(cmd)
            
            if is_builtin:
                return self._execute_builtin(cmd)
            else:
                return self._run_subprocess(cmd , capture_output)
        
        elif response == 'p':
            # Approve prefix and execute
            self._approve_prefix(cmd)
            
            if is_builtin:
                return self._execute_builtin(cmd)
            else:
                return self._run_subprocess(cmd,capture_output)
        
        else:
            # Invalid response - treat as 'n'
            print("Command blocked")
            return CommandResult(
                stdout="",
                stderr="Invalid response - command blocked",
                exit_code=1
            )
    
    def _approve_exact(self, cmd: str) -> None:
        """Approve exact command and persist."""
        result = self.regex_agent.modify(
            operation="add",
            category="approved",
            value=cmd,
            match_type="exact",
            persist=True
        )
        if result.get("status") == "success":
            print(f"Exact command approved: '{cmd}'")
    
    def _approve_prefix(self, cmd: str) -> None:
        """Approve command prefix and persist."""
        prefix = cmd.split()[0] if cmd.split() else cmd
        result = self.regex_agent.modify(
            operation="add",
            category="approved",
            value=prefix,
            match_type="prefix",
            persist=True
        )
        if result.get("status") == "success":
            print(f"Prefix approved: '{prefix}'")
    
    def _run_subprocess(self, cmd: str , capture_output : bool) -> CommandResult:
        """
        Execute command via subprocess.
        
        Args:
            cmd: Command to execute
            
        Returns:
            CommandResult with execution output
        """
        try:
            print("Hi : DEBUG 5")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=capture_output,
                text=True,
                
            )
            return CommandResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                stdout="",
                stderr="Command timed out after 30 seconds",
                exit_code=124
            )
        except Exception as e:
            return CommandResult(
                stdout="",
                stderr=f"Execution error: {str(e)}",
                exit_code=1
            )


if __name__ == "__main__":
    # Mock classes for testing (since we can't import the real ones)
    
    
    
    
    # Test Suite
    print("="*70)
    print("ExecutorAgent Comprehensive Test Suite")
    print("Safety checks ALWAYS performed before execution")
    print("="*70)
    
    # Initialize mocks and agent
    state = ShellState()
    regex_agent = RegexAgent()
    builtin_handler = BuiltinHandler(state)
    executor = ExecutorAgent(regex_agent, builtin_handler)
    
    test_count = 0
    passed_count = 0
    
    def test_case(description, test_func):
        """Run a test case."""
        global test_count, passed_count
        test_count += 1
        print(f"\n[Test {test_count}] {description}")
        try:
            test_func()
            passed_count += 1
            print("✓ PASSED")
        except AssertionError as e:
            passed_count += 0
            print(f"✗ FAILED: {e}")
        except Exception as e:
            print(f"✗ ERROR: {e}")
    
    # Test 1: Empty command
    def test_empty_command():
        result = executor.execute("")
        assert result.exit_code == 0, "Empty command should succeed"
        assert result.stdout == "", "Empty command should have no output"
    
    test_case("Empty command handling", test_empty_command)
    
    # Test 2: Approved external command (echo)
    def test_approved_command():
        result = executor.execute("echo 'Hello World'")
        assert result.exit_code == 0, "echo should succeed"
        assert "Hello World" in result.stdout, "echo should output text"
    
    test_case("Approved external command: echo", test_approved_command)
    
    # Test 3: Approved external command (ls)
    def test_approved_ls():
        result = executor.execute("ls")
        assert result.exit_code == 0, "ls should succeed"
    
    test_case("Approved external command: ls", test_approved_ls)
    
    # Test 4: Pre-approved builtin (after manual approval)
    def test_pre_approved_builtin():
        # Manually approve pwd prefix
        regex_agent.builtin_approved.add("pwd")
        result = executor.execute("pwd")
        assert result.exit_code == 0, "Pre-approved pwd should succeed"
        assert "/home/user" in result.stdout, "pwd should return current directory"
    
    test_case("Pre-approved builtin command: pwd", test_pre_approved_builtin)
    
    # Test 5: Check that unapproved builtin requires approval
    def test_unapproved_builtin_needs_approval():
        # cd is NOT in approved list initially
        # This test verifies the flow would ask for approval
        result = regex_agent.check("cd /tmp")
        assert result["is_safe"] == False, "Unapproved builtin should not be safe"
        assert result["status"] == "unknown", "Unapproved builtin should be unknown"
    
    test_case("Unapproved builtin requires approval check", test_unapproved_builtin_needs_approval)
    
    # Test 6: Approved builtin prefix works
    def test_approved_builtin_prefix():
        # Approve the cd prefix
        regex_agent.approved_prefix.add("cd")
        regex_agent.builtin_approved.add("cd")
        result = executor.execute("cd /tmp")
        assert result.exit_code == 0, "Approved cd should succeed"
        result = executor.execute("pwd")
        # pwd still needs approval
        regex_agent.builtin_approved.add("pwd")
        result = executor.execute("pwd")
        assert "/tmp" in result.stdout, "Directory should have changed"
    
    test_case("Approved builtin prefix execution", test_approved_builtin_prefix)
    
    # Test 7: Multiple approved commands
    def test_multiple_approved():
        result1 = executor.execute("echo 'test1'")
        result2 = executor.execute("echo 'test2'")
        assert result1.exit_code == 0, "First echo should succeed"
        assert result2.exit_code == 0, "Second echo should succeed"
        assert "test1" in result1.stdout, "First echo output correct"
        assert "test2" in result2.stdout, "Second echo output correct"
    
    test_case("Multiple approved commands", test_multiple_approved)
    
    # Test 8: Safety check catches dangerous command
    def test_dangerous_detection():
        result = regex_agent.check("rm -rf /")
        assert result["is_safe"] == False, "Dangerous command should not be safe"
        assert result["status"] == "dangerous", "rm -rf should be dangerous"
    
    test_case("Dangerous command detection", test_dangerous_detection)
    
    # Test 9: Complex approved command
    def test_complex_command():
        result = executor.execute("echo 'test' | grep test")
        assert result.exit_code == 0, "Piped command should succeed"
    
    test_case("Complex piped command", test_complex_command)
    
    # Test 10: Whitespace handling
    def test_whitespace():
        regex_agent.builtin_approved.add("env")
        result = executor.execute("  env  ")
        assert result.exit_code == 0, "Command with whitespace should succeed"
    
    test_case("Whitespace handling", test_whitespace)
    
    # Test 11: Exact approval mechanism
    def test_exact_approval():
        regex_agent.approved_exact.add("ls -la")
        result = executor.execute("ls -la")
        assert result.exit_code == 0, "Exact approved command should succeed"
    
    test_case("Exact approval mechanism", test_exact_approval)
    
    # Test 12: Verify all builtins go through safety check
    def test_all_builtins_checked():
        builtins = ['cd', 'pwd', 'alias', 'unalias', 'export', 'unset', 'env']
        for builtin in builtins:
            if builtin not in regex_agent.builtin_approved:
                result = regex_agent.check(builtin)
                # Unapproved builtins should require approval
                assert result["is_safe"] == False or result["status"] == "unknown", \
                    f"{builtin} should require approval when not in approved list"
    
    test_case("All builtins go through safety check", test_all_builtins_checked)
    
    # Test 13: Safety check before builtin execution
    def test_safety_before_builtin():
        # Test that even builtins are checked
        # env is not approved yet
        result = regex_agent.check("env")
        is_safe = result.get("is_safe", False)
        # Should not be safe if not approved
        if "env" not in regex_agent.builtin_approved:
            assert is_safe == False, "Unapproved env should not be safe"
    
    test_case("Safety check before builtin execution", test_safety_before_builtin)
    
    # Test 14: Approved prefix for git commands
    def test_git_prefix():
        result = executor.execute("git status")
        assert result.exit_code == 0, "git command should be approved by default"
    
    test_case("Git command prefix approval", test_git_prefix)
    
    # Test 15: Command with arguments safety check
    def test_command_with_args():
        regex_agent.builtin_approved.add("alias")
        result = executor.execute("alias ll='ls -la'")
        assert result.exit_code == 0, "Alias with arguments should work"
    
    test_case("Command with arguments", test_command_with_args)
    
    # Summary
    print("\n" + "="*70)
    print(f"Test Summary: {passed_count}/{test_count} tests passed")
    if passed_count == test_count:
        print("✓ All tests passed!")
    else:
        print(f"✗ {test_count - passed_count} test(s) failed")
    print("="*70)
    
    # Safety demonstration
    print("\n" + "="*70)
    print("Safety Check Demonstration")
    print("="*70)
    
    print("\n1. Checking approved command (echo):")
    result = regex_agent.check("echo hello")
    print(f"   is_safe: {result['is_safe']}, status: {result['status']}")
    
    print("\n2. Checking unapproved builtin (cd):")  # Ensure it's not approved
    result = regex_agent.check("cd /tmp")
    print(f"   is_safe: {result['is_safe']}, status: {result['status']}")
    
    print("\n3. Checking dangerous command (rm -rf):")
    result = regex_agent.check("rm -rf /")
    print(f"   is_safe: {result['is_safe']}, status: {result['status']}")
    
    print("\n4. Checking unknown command (malicious):")
    result = regex_agent.check("malicious-binary --hack")
    print(f"   is_safe: {result['is_safe']}, status: {result['status']}")
    
    print("\n" + "="*70)
    print("Key Feature: ALL commands (including builtins) are checked")
    print("for safety BEFORE execution!")
    print("="*70)