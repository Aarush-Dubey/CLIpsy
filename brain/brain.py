from enum import Enum
from requests import api
from core.builtin import BuiltinHandler
from core.shellstate import ShellState
from core.regex import RegexAgent
from core.executor import ExecutorAgent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

class AgentMode(Enum):
    COMMAND = "command"
    CHAT = "chat"
    AGENTIC = "agentic"

class Brain:
    def __init__(self, executor: ExecutorAgent, state: ShellState, api_key: str, model: str = "openai/gpt-oss-120b"):
        self.executor = executor
        self.state = state
        self.api_key = api_key
        
        # Define your custom tool for execution
        def execute(cmd: str):
            """Execute a shell command and return stdout, stderr, and exit code."""
            return self.executor.execute(cmd, True)

        # System prompt for agent instructions
        self.system_prompt = """
You are an intelligent CLI agent running in a terminal environment of macos. Your goal is to answer user queries by executing tools and synthesizing the raw output into concise, natural language summaries.

**YOUR CORE PROTOCOLS:**
1. **Interpret, Don't Regurgitate:**
* Never dump raw standard output (stdout) unless explicitly asked.
* Instead of pasting the output of `git status`, say: *"You have 3 modified files in `src/` and 2 new files ready to be staged."*
* Instead of pasting `ls -la`, say: *"The directory contains 5 text files and a python script. The latest modification was today."*
* CLI users value speed. Use bullet points for lists.
* Avoid conversational filler like "I have checked the system and found..." -> Just state the finding.

2. **Formatting:**
* Use **Markdown** for readability.
* Use **Bold** for critical statuses (e.g., **Error**, **Clean**, **Modified**).
* Use `code spans` for file names, paths, and specific command flags.

3. **Context Awareness:**
* If a tool fails (stderr is not empty), analyze the error message and explain *why* it failed in plain English, then suggest a fix.

**TONE GUIDE:**
* **Correct:** "The server is down (Port 8080 busy)."
* **Incorrect:** "It looks like I tried to connect to the server but unfortunately it appears to be down because port 8080 is currently being used by another process."

**INSTRUCTIONS FOR TOOL OUTPUTS:**
When you receive the output from a tool (e.g., the result of a `git` command or file read):
1. Scan the output for key metrics (errors, file counts, statuses).
2. Summarize the state clearly.
3. If the output indicates a clean/successful state, confirm it briefly (e.g., "Working tree is clean.").
4. If the output is too long (over 20 lines), summarize the patterns (e.g., "There are 50+ log files created today").
"""
        
        # List of tools
        self.tools = [execute]
        self.memory = InMemorySaver() 
        
        self.model = ChatGroq(
            model=model,
            temperature=0.4,
            api_key=self.api_key
        )
        
        # Create agent with the tool and memory
        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            system_prompt=self.system_prompt,
            checkpointer=self.memory
        )
        
        self.thread_id = "default"

    def process(self, input_text: str, mode: AgentMode, get_user_input_callback=None):
        """
        Process the input based on the mode.
        Returns a dictionary with status and result.
        """
        # For now, we map all modes to the same agent or adjust system prompt if needed.
        # But keeping it simple as per original script logic which was generic.
        
        try:
            result = self.agent.invoke(
                {
                    "messages": [
                        {"role": "user", "content": input_text}
                    ]
                },
                {
                    "configurable": {
                        "thread_id": self.thread_id
                    }
                }
            )
            
            final_msg = result["messages"][-1]
            response_content = final_msg.content
            
            # Construct a result object compatible with main.py expectations
            # main.py expects result["result"]["stdout"] etc for command mode
            # or result["response"] for chat mode
            
            if mode == AgentMode.CHAT:
                return {
                    "status": "success",
                    "response": response_content
                }
            elif mode == AgentMode.COMMAND:
                # In command mode, main.py expects:
                # if status == "success": result["result"] = {"stdout": ..., "stderr": ...}
                # But our agent executes internally and returns a text summary.
                # However, if the agent called the tool, the tool execution happened.
                # We might want to capture the last tool execution output if possible?
                # The generic agent from `create_agent` (prebuilt) usually returns the final message.
                
                # For compatibility, we'll return success and put the text in stdout if it looks like output
                # or just return the text response.
                
                return {
                    "status": "success",
                    "result": {
                        "stdout": response_content + "\n",
                        "stderr": ""
                    },
                    "recovery_applied": False
                }
            elif mode == AgentMode.AGENTIC:
                 # main.py expects 'completed_steps'
                 return {
                     "status": "success",
                     "completed_steps": [
                         {
                             "result": {
                                 "stdout": response_content
                             }
                         }
                     ]
                 }
                 
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "result": {"stderr": str(e)}
            }


if __name__ == "__main__":
    # Test block
    print("⚡ Brain Module Test.")
