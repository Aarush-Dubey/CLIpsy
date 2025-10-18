#!/usr/bin/env python3
import subprocess
import json
import os
import warnings
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'
from dotenv import load_dotenv
load_dotenv()
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

CONFIG_FILE = "config.json"
HISTORY_FILE = "history.json"


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
    if config["llm_provider"] == "openai":
        return ChatOpenAI(model=config["model"])
    else:
        return ChatGoogleGenerativeAI(model=config["model"])

def is_blacklisted(cmd, blacklist):
    return any(b in cmd for b in blacklist)

def execute_command(cmd, capture=False):
    try:
        # Handle cd specially to change actual working directory
        if cmd.strip().startswith('cd '):
            path = cmd.strip()[3:].strip()
            if not path:
                path = os.path.expanduser('~')
            else:
                path = os.path.expanduser(path)
            os.chdir(path)
            msg = f"Changed directory to: {os.getcwd()}"
            return ""
        
        # Use subprocess for capturing (agent mode), os.system for direct execution
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout + result.stderr
        else:
            exit_code = os.system(cmd)
            return f"\n[Exit code: {exit_code}]" if exit_code != 0 else ""
    except Exception as e:
        return f"Error: {str(e)}"

def simple_mode(query, config, history, conversation):
    llm = get_llm(config)
    system_prompt = "You are a helpful AI that translates natural language into safe, concise bash commands. Only output the raw bash command which can be directly copy pasted into the terminal without any errors, nothing else."
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation)
    messages.append({"role": "user", "content": query})
    
    response = llm.invoke(messages)
    
    cmd = response.content.strip()
    print(f"\nCommand: {cmd}")
    
    if is_blacklisted(cmd, config["blacklist"]):
        print("❌ Command is blacklisted!")
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

def agent_mode(query, config, history, conversation):
    llm = get_llm(config)
    system_prompt = """You are a CLI Assistant that interacts with the shell safely. You must follow this structured loop:

1. START → Represent the user's original request.
2. PLAN → Think step by step about what is needed.
3. ACTION → Suggest **one safe shell command at a time**.
4. OBSERVATION → Wait for the system to return the command's output.
5. OUTPUT → After gathering enough observations, provide the final safe command(s) for user approval.

Important Rules:
- Always PLAN before taking ACTION.
- Never suggest destructive commands (like `rm -rf`) without safety checks.
- Only return **one JSON object per response**.
- Do not include markdown code blocks or any text outside the JSON object.
- If unsure, PLAN additional observations (e.g., run `ls`, `pwd`, `git status`) before final OUTPUT.

You MUST respond with ONLY a valid JSON object in one of these formats:
- PLAN: {"type": "PLAN", "thought": "Your reasoning here"}
- ACTION: {"type": "ACTION", "command": "Your safe shell command here"}
- OBSERVATION: {"type": "OBSERVATION", "result": "Output of previous command"}
- OUTPUT: {"type": "OUTPUT", "command": "Final safe command(s)"}

Return ONLY the JSON object, nothing else. No markdown, no explanations, just the JSON."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]
    
    conversation = []
    
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
            print(f"💭 PLAN: {step['thought']}")
            conversation.append(step)
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "Continue"})
        
        elif step_type == "ACTION":
            cmd = step["command"]
            print(f"⚡ ACTION: {cmd}")
            
            if is_blacklisted(cmd, config["blacklist"]):
                print("❌ Blacklisted command detected!")
                break
            
            # Checkpoint: Ask for approval before executing
            approval = input("Execute this command? (y/n): ").lower()
            
            if approval != 'y':
                print("⏭️  Skipped. Asking agent to reconsider...")
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "User declined. Please suggest an alternative approach."})
                continue
            
            output = execute_command(cmd)
            print(f"📤 Output: {output[:200]}...")
            
            obs = {"type": "OBSERVATION", "result": output}
            conversation.append(step)
            conversation.append(obs)
            
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": json.dumps(obs)})
        
        elif step_type == "OUTPUT":
            cmd = step["command"]
            print(f"\n✅ Final Command: {cmd}")
            
            if is_blacklisted(cmd, config["blacklist"]):
                print("❌ Command is blacklisted!")
                break
            
            approval = input("Approve? (y/n): ").lower()
            
            if approval == 'y':
                output = execute_command(cmd)
                print(output)
                history.append({"query": query, "conversation": conversation, "final_command": cmd, "output": output})
            break
        
        else:
            print(f"Unknown step type: {step_type}")
            break

def main():
    config = load_config()
    history = load_history()
    conversation = []
    
    print("CLI Agent Ready. Type 'exit' to quit.")
    print(f"Current directory: {os.getcwd()}\n")
    
    while True:
        try:
            query = input(f"\n{os.getcwd()}> ").strip()
            
            if query.lower() == 'exit':
                break
            
            if not query:
                continue
            
            # Direct execution mode
            if query.startswith("!") or query.endswith("!"):
                cmd = query.strip("!")
                print(f"Executing: {cmd}")
                output = execute_command(cmd)
                print(output)
                history.append({"query": query, "command": cmd, "output": output})
                continue
            
            # Agent mode
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