from shellstate import ShellState
from regex import RegexAgent
from builtin import BuiltinHandler
from executor import ExecutorAgent

agent = RegexAgent()
state = ShellState()
handler = BuiltinHandler(state)
executor = ExecutorAgent(agent , handler)

print(executor.execute("python main.py" , False))

