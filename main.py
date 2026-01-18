#!/usr/bin/env python3
"""
CLI Wrapper for the Brain Module
Provides a terminal-like interface with AI assistance.
"""

import os
import sys
import argparse
from typing import Optional
import readline
import atexit
from rich.console import Console
from rich.markdown import Markdown

# Initialize Rich Console
console = Console()
# Import your existing components
from core.builtin import BuiltinHandler
from core.executor import ExecutorAgent
from core.regex import RegexAgent
from core.shellstate import ShellState

# Import Brain - choose your implementation

from brain.brain import Brain, AgentMode
AI_PROVIDER = "Groq"


class CLIAgent:
    """Main CLI Agent class wrapping the Brain"""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, verbose: bool = False):
        """
        Initialize the CLI Agent.
        
        Args:
            api_key: API key (if None, reads from environment)
            model: Model name to use
            verbose: Enable verbose output
        """
        self.verbose = verbose
        
        # Setup history
        self.hist_file = os.path.join(os.path.expanduser("~"), ".clipsy_history")
        try:
            readline.read_history_file(self.hist_file)
            readline.set_history_length(1000)
        except FileNotFoundError:
            pass
        atexit.register(readline.write_history_file, self.hist_file)
        
        # Get API key from environment if not provided
        if api_key is None:
            if AI_PROVIDER == "Gemini":
                api_key = os.getenv("GOOGLE_API_KEY")
            elif AI_PROVIDER == "Groq":
                api_key = os.getenv("GROQ_API_KEY")
            else:
                api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            print(f"Error: API key not found.")
            print(f"Set {AI_PROVIDER.upper()}_API_KEY environment variable or pass --api-key")
            sys.exit(1)
        
        # Initialize core components
        self.state = ShellState()
        self.builtin_handler = BuiltinHandler(self.state)
        self.regex_agent = RegexAgent()
        self.executor = ExecutorAgent(self.regex_agent, self.builtin_handler)
        
        # Initialize Brain
        kwargs = {"executor": self.executor, "state": self.state, "api_key": api_key}
        if model:
            kwargs["model"] = model
        
        self.brain = Brain(**kwargs)
        
        if self.verbose:
            print(f"✓ Brain initialized with {AI_PROVIDER}")
            if model:
                print(f"  Using model: {model}")
    
    def get_user_input(self, prompt: str) -> str:
        """Get user input"""
        return input(prompt)
    
    def get_prompt(self) -> str:
        """Get shell-like prompt"""
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        return f"{cwd} $ "
    
    def run_direct_command(self, command: str) -> None:
        """Execute command directly using executor without Brain"""
        try:
            result = self.executor.execute(command)
            
            # Print stdout
            if result.get("stdout"):
                print(result["stdout"], end='')
            
            # Print stderr
            if result.get("stderr"):
                print(result["stderr"], end='', file=sys.stderr)
            
            # Update exit code (if needed by your shell state)
            exit_code = result.get("exit_code", 0)
            if exit_code != 0 and self.verbose:
                print(f"[Exit code: {exit_code}]", file=sys.stderr)
                
        except Exception as e:
            print(f"Error: {str(e)}", file=sys.stderr)
    
    def run_brain_command(self, command: str) -> None:
        """Execute command through Brain with error recovery"""
        result = self.brain.process(
            command,
            AgentMode.COMMAND,
            get_user_input_callback=self.get_user_input
        )
        
        status = result.get("status")
        
        if status == "success":
            # Print output
            if "result" in result:
                res = result["result"]
                if res.get("stdout"):
                    # Use rich markdown for formatting
                    console.print(Markdown(res["stdout"]))
                if res.get("stderr"):
                    console.print(res["stderr"], style="bold red")
            
            # Show recovery message if applied
            if result.get("recovery_applied") and self.verbose:
                print("[Brain: Error recovery applied]")
        
        elif status == "error":
            # Print error output
            if "result" in result:
                res = result["result"]
                if res.get("stderr"):
                    print(res["stderr"], end='', file=sys.stderr)
            
            # Show error analysis if available
            if "error_analysis" in result and self.verbose:
                analysis = result["error_analysis"]
                print(f"\n[Brain: {analysis.get('explanation', 'Command failed')}]", file=sys.stderr)
        
        elif status == "aborted":
            if self.verbose:
                print(f"[Brain: {result.get('message', 'Operation cancelled')}]")
    
    def run_chat_mode(self, query: str) -> None:
        """Run query in chat mode"""
        result = self.brain.process(query, AgentMode.CHAT)
        
        if result["status"] == "success":
            console.print(Markdown(result["response"]))
        else:
            print(f"Error: {result.get('message', 'Chat failed')}", file=sys.stderr)
    
    def run_agentic_mode(self, task: str) -> None:
        """Run task in agentic mode"""
        result = self.brain.process(
            task,
            AgentMode.AGENTIC,
            get_user_input_callback=self.get_user_input
        )
        
        status = result.get("status")
        
        if status == "success":
            if self.verbose:
                print(f"[Brain: Completed {len(result.get('completed_steps', []))} steps]")
            # Show output from final step
            if result.get("completed_steps"):
                last_step = result["completed_steps"][-1]
                if "result" in last_step:
                    res = last_step["result"]
                    if res.get("stdout"):
                        console.print(Markdown(res["stdout"]))
        
        elif status == "partial_failure":
            print(f"Error: Task partially completed ({len(result.get('completed_steps', []))} steps)", file=sys.stderr)
            if self.verbose and "failed_at" in result:
                print(f"[Brain: Failed at step - {result['failed_at'].get('description', 'unknown')}]", file=sys.stderr)
        
        elif status == "error":
            print("Error: Task failed", file=sys.stderr)
    
    def run_shell(self):
        """Run in interactive shell mode"""
        if self.verbose:
            print("CLI-Agent Shell")
            print("Commands starting or ending with '!' are executed directly")
            print("Commands ending with '-c' use Chat mode")
            print("Commands ending with '-a' use Agentic mode")
            print("Other commands use Brain command mode with error recovery")
            print("Type 'exit' or press Ctrl+D to quit\n")
        
        while True:
            try:
                # Get user input with shell-like prompt
                user_input = input(self.get_prompt()).strip()
                
                # Skip empty input
                if not user_input:
                    continue
                
                # Check for exit commands
                if user_input.lower() in ['exit', 'quit']:
                    break
                
                # Check for clear command
                if user_input.lower() == 'clear':
                    os.system('clear')
                    continue
                
                # Check if command should be executed directly (starts or ends with !)
                if user_input.startswith('!') or user_input.endswith('!'):
                    # Remove the ! marker
                    clean_command = user_input.strip('!')
                    self.run_direct_command(clean_command)
                
                # Check for chat mode (ends with -c)
                elif user_input.endswith(' -c'):
                    # Remove the -c marker
                    query = user_input[:-3].strip()
                    if query:
                        self.run_chat_mode(query)
                
                # Check for agentic mode (ends with -a)
                elif user_input.endswith(' -a'):
                    # Remove the -a marker
                    task = user_input[:-3].strip()
                    if task:
                        self.run_agentic_mode(task)
                
                else:
                    # Use Brain for intelligent command execution
                    self.run_brain_command(user_input)
                
            except KeyboardInterrupt:
                print()  # New line after ^C
                continue
            except EOFError:
                print()  # New line after ^D
                break
            except Exception as e:
                print(f"Error: {str(e)}", file=sys.stderr)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="CLI-Agent Brain Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Examples:
    # Run interactive shell
    %(prog)s
    
    # Run with verbose mode
    %(prog)s --verbose
    
    # Specify model
    %(prog)s --model gpt-4o
  
    Shell Usage:
    # Direct execution (bypass Brain, instant)
    $ !ls -la
    $ cd /tmp!
    
    # Chat mode (conversational questions)
    $ what is the difference between pip and conda -c
    $ explain docker containers -c
    
    # Agentic mode (complex multi-step tasks)
    $ create a python project with venv and install pandas -a
    $ setup a flask app with authentication -a
    
    # Command mode (default, with error recovery and safety)
    $ ls -la
    $ pip install pandas
    $ rm important_file.txt
    
    # Exit
    $ exit
            """
    )
    
    parser.add_argument(
        "--api-key",
        help="API key (or set GOOGLE_API_KEY/OPENAI_API_KEY env var)"
    )
    
    parser.add_argument(
        "--model",
        help="Model to use (e.g., gpt-4o, gemini-2.0-flash-exp)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"CLI-Agent Brain 1.0 (using {AI_PROVIDER})"
    )
    
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    # Initialize agent
    try:
        agent = CLIAgent(api_key=api_key, model=args.model, verbose=args.verbose)
    except Exception as e:
        print(f"Failed to initialize: {str(e)}", file=sys.stderr)
        sys.exit(1)
    
    # Run shell
    try:
        agent.run_shell()
    except Exception as e:
        print(f"\nFatal error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()