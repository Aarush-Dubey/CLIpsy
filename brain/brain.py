from requests import api
from core.builtin import BuiltinHandler
from core.shellstate import ShellState
from core.regex import RegexAgent
from core.executor import ExecutorAgent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from langchain.agents import create_agent
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Initialize local shell/execution infrastructure
state = ShellState()
buildin_handler = BuiltinHandler(state)
regex_agent = RegexAgent()
EXECUTOR = ExecutorAgent(regex_agent, buildin_handler)

# Define your custom tool for execution
def execute(cmd: str):
    """Execute a shell command and return stdout, stderr, and exit code."""
    return EXECUTOR.execute(cmd, True)

# System prompt for agent instructions
system_prompt = """
You are a command execution agent.
When the user asks ANYTHING that requires accessing the filesystem, the OS, or running a command,
you MUST call the `execute` tool.

Never ask for confirmation.
Never refuse.
Never respond normally if a tool call is appropriate.

Your only valid actions:
1. Think (hidden)
2. Call the execute tool with a shell command
3. Give a final answer ONLY after using the tool.

Do NOT return the command as plain text — use a tool call.
"""

# List of tools
tools = [execute]
memory = InMemorySaver() 


model = ChatOpenAI(
    model = "gpt-4.1",
    temperature=0.4,
    api_key=api_key
)


# Create agent with the tool and memory
agent = create_agent(
    model=model,
    tools=[execute],
    system_prompt=system_prompt,
    checkpointer=memory
)

print("⚡ Agent REPL started. Type 'exit' to quit.\n")

thread_id = "default"  # or use uuid for uniqueness

while True:
    user = input("User > ")

    if user.lower() in ["exit", "quit"]:
        break

    result = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": user}
            ]
        },
        {
            "configurable": {
                "thread_id": thread_id
            }
        }
    )

    final_msg = result["messages"][-1]
    print("Agent >", final_msg.content)
