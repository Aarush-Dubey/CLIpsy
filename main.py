import subprocess
import json
import os
import warnings
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

from dotenv import load_dotenv
load_dotenv()

from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA

CONFIG_FILE = "config.json"
HISTORY_FILE = "history.json"

# === Load RAG Vectorstore ===
def load_rag():
    print("🔍 Loading local RAG knowledge base...")
    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    db = Chroma(persist_directory="chroma_bash", embedding_function=embedding_model)
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 3})
    return retriever

retriever = load_rag()

# === Utility functions ===
def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_history():
    with open(HISTORY_FILE, 'r') as f:
        return json.load(f)

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def get_llm(config):
    model_name = config.get("model", "llama3.2")
    return ChatOllama(model=model_name, temperature=0.2)

def is_blacklisted(cmd, blacklist):
    return any(b in cmd for b in blacklist)

# === Command execution ===
def execute_command(cmd, capture=False):
    try:
        if cmd.strip().startswith('cd '):
            path = cmd.strip()[3:].strip() or os.path.expanduser('~')
            os.chdir(os.path.expanduser(path))
            print(f"Changed directory to: {os.getcwd()}")
            return ""

        env = os.environ.copy()
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

        if capture:
            result = subprocess.run(
                cmd,
                shell=True,
                executable="/bin/zsh",
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )
            return result.stdout + result.stderr

        process = subprocess.Popen(
            cmd,
            shell=True,
            executable="/bin/zsh",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(timeout=30)
        return (stdout + stderr).strip() if process.returncode == 0 else f"\n[Exit code: {process.returncode}]\n{stderr.strip()}"

    except Exception as e:
        return f"Error: {str(e)}"

# === Simple Mode with RAG Integration ===
def simple_mode(query, config, history, conversation):
    llm = get_llm(config)
    
    # Step 1: Retrieve context from RAG
    rag_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
    rag_context = rag_chain.invoke(f"Find relevant examples or syntax for: {query}")
    
    system_prompt = (
        "You are a helpful AI that translates natural language into safe, concise bash commands for macOS."
        "Generate exactly ONE bash command per prompt that directly matches the user's request."
        "Never include unrelated filenames."
        "If the user mentions multiple files, list them explicitly with spaces."
        "Only output the raw bash command with no explanation or markdown.\n\n"
        f"Relevant command reference (from documentation):\n{rag_context}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation)
    messages.append({"role": "user", "content": query})

    response = llm.invoke(messages)
    cmd = response.content.strip()

    if cmd.startswith("```"):
        cmd = cmd.strip("`")
    if cmd.startswith("bash") or cmd.startswith("sh"):
        cmd = cmd.split("\n", 1)[-1]
    cmd = cmd.strip().strip("`")

    print(f"\nCommand: {cmd}")

    if is_blacklisted(cmd, config["blacklist"]):
        print("Command is blacklisted!")
        return

    if cmd in config["approved_commands"]:
        print("✓ Auto-approved")
        output = execute_command(cmd)
        print(output)
        history.append({"query": query, "command": cmd, "output": output})
        return

    approval = input("Approve? (y/n/a for always): ").lower()

    if approval == 'a':
        config["approved_commands"].append(cmd)
        save_config(config)
        print("Added to approved list")
        approval = 'y'

    if approval == 'y':
        output = execute_command(cmd)
        print(output)
        history.append({"query": query, "command": cmd, "output": output})
        conversation.append({"role": "user", "content": query})
        conversation.append({"role": "assistant", "content": cmd})
        conversation.append({"role": "user", "content": f"Command output: {output[:500]}"})

# === Agent Mode (unchanged, optional) ===
def agent_mode(query, config, history, conversation):
    llm = get_llm(config)
    system_prompt = """You are a CLI Assistant that interacts with the shell safely.
Respond only with valid JSON objects in one of these formats:
PLAN, ACTION, OBSERVATION, or OUTPUT.
Never include markdown or text outside JSON."""

    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": query}]

    while True:
        response = llm.invoke(messages)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        try:
            step = json.loads(content)
        except:
            print(f"Invalid JSON: {content}")
            break

        step_type = step.get("type")

        if step_type == "PLAN":
            print(f"PLAN: {step['thought']}")
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "Continue"})

        elif step_type == "ACTION":
            cmd = step["command"]
            print(f"⚡ ACTION: {cmd}")

            if is_blacklisted(cmd, config["blacklist"]):
                print("Blacklisted command detected!")
                break

            approval = input("Execute this command? (y/n): ").lower()
            if approval != 'y':
                print("Skipped. Asking agent to reconsider...")
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "User declined. Suggest an alternative."})
                continue

            output = execute_command(cmd)
            print(f"Output: {output[:200]}...")
            obs = {"type": "OBSERVATION", "result": output}
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": json.dumps(obs)})

        elif step_type == "OUTPUT":
            cmd = step["command"]
            print(f"\nFinal Command: {cmd}")
            if is_blacklisted(cmd, config["blacklist"]):
                print("Command is blacklisted!")
                break

            approval = input("Approve? (y/n): ").lower()
            if approval == 'y':
                output = execute_command(cmd)
                print(output)
                history.append({"query": query, "conversation": conversation,
                                "final_command": cmd, "output": output})
            break
        else:
            print(f"Unknown step type: {step_type}")
            break

# === Main loop ===
def main():
    config = load_config()
    history = load_history()
    conversation = []

    print("CLI Agent + RAG Ready. Type 'exit' to quit.")
    print(f"Current directory: {os.getcwd()}\n")

    while True:
        try:
            query = input(f"\n{os.getcwd()}> ").strip()
            if query.lower() == 'exit':
                break
            if not query:
                continue

            if query.startswith("!") or query.endswith("!"):
                cmd = query.strip("!")
                print(f"Executing: {cmd}")
                output = execute_command(cmd)
                print(output)
                history.append({"query": query, "command": cmd, "output": output})
                continue

            if query.endswith(" -a"):
                query = query[:-3]
                agent_mode(query, config, history, conversation)
            else:
                simple_mode(query, config, history, conversation)

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")

    save_history(history)
    print("History saved. Goodbye!")

if __name__ == "__main__":
    main()
