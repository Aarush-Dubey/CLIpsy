"""

Things to add 
->Streaming 
->HITL
->ProvacticeErrorAgent

"""


from requests import api
from core.builtin import BuiltinHandler
from core.shellstate import ShellState
from core.regex import RegexAgent
from core.executor import ExecutorAgent

state = ShellState()
buildin_handler = BuiltinHandler(state)
regex_agent = RegexAgent()
EXECUTOR = ExecutorAgent(regex_agent , buildin_handler)
from langchain_google_genai import ChatGoogleGenerativeAI
# class Brain:
#     def __init__(self) -> None:
#         self.client

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

from langchain.agents import create_agent 
from dotenv import load_dotenv
import os
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")



def execute(cmd:str ):
    """Execute a shell command and return stdout , stderr and exit code"""
    return EXECUTOR.execute(cmd, True)


tools = [execute] 
model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.4,
    api_key = api_key
)

# 2. Create agent with the single tool
agent = create_agent(
    model=model,
    tools=[execute],
    system_prompt=system_prompt
)


print("⚡ Agent REPL started. Type 'exit' to quit.\n")

while True:
    user = input("User > ")

    if user.lower() in ["exit", "quit"]:
        break

    result = agent.invoke({
        "messages": [
            {"role": "user", "content": user}
        ]
    })

    # The final result is in messages[-1]
    final_msg = result["messages"][-1]
    print("Agent >", final_msg.content)