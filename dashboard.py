import gradio as gr
import os
import subprocess
import requests
from ruamel.yaml import YAML

# Initialize ruamel.yaml for strict round-trip formatting
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# --- File Paths ---
NLU_PATH = "data/nlu.yml"
DOMAIN_PATH = "domain.yml"
RASA_API_URL = "http://localhost:5005/webhooks/rest/webhook"

def load_yaml(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.load(f) or {}

def save_yaml(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

def get_current_intents():
    domain = load_yaml(DOMAIN_PATH)
    return domain.get("intents", []) if domain else []

def add_new_intent(intent_name, examples_text):
    if not intent_name:
        return "⚠️ Please enter an intent name.", gr.update()
    
    intent_name = intent_name.strip()
    
    # 1. Update NLU File safely
    nlu_data = load_yaml(NLU_PATH)
    if not nlu_data or "nlu" not in nlu_data:
        nlu_data = {"version": "3.1", "nlu": []}
    if nlu_data["nlu"] is None:
        nlu_data["nlu"] = []
        
    # Standardize the user's new inputs into a clean Python list
    new_examples = []
    for line in examples_text.split("\n"):
        line = line.strip()
        if line:
            if line.startswith("-"):
                line = line.lstrip("-").strip()
            new_examples.append(line)
            
    # Look through existing intents
    intent_found = False
    for item in nlu_data["nlu"]:
        if item.get("intent") == intent_name:
            intent_found = True
            current_examples = item.get("examples", "")
            
            # If the current examples are a string block, parse it into a list first
            if isinstance(current_examples, str):
                existing_list = [
                    line.lstrip("-").strip() 
                    for line in current_examples.split("\n") 
                    if line.strip()
                ]
            elif isinstance(current_examples, list):
                existing_list = [str(x).strip() for x in current_examples]
            else:
                existing_list = []
                
            # Merge lists while removing duplicates
            for ex in new_examples:
                if ex not in existing_list:
                    existing_list.append(ex)
                    
            # Build the clean block string back for Rasa
            block_str = "\n".join([f"- {x}" for x in existing_list]) + "\n"
            from ruamel.yaml.scalarstring import LiteralScalarString
            item["examples"] = LiteralScalarString(block_str)
            break
            
    # If the intent is completely new, just make a new block string
    if not intent_found:
        block_str = "\n".join([f"- {x}" for x in new_examples]) + "\n"
        from ruamel.yaml.scalarstring import LiteralScalarString
        nlu_data["nlu"].append({"intent": intent_name, "examples": LiteralScalarString(block_str)})
        
    save_yaml(NLU_PATH, nlu_data)
    
    # 2. Update Domain File safely
    domain_data = load_yaml(DOMAIN_PATH)
    if not domain_data or "intents" not in domain_data:
        domain_data = {"version": "3.1", "intents": []}
    if domain_data["intents"] is None:
        domain_data["intents"] = []
        
    if intent_name not in domain_data["intents"]:
        domain_data["intents"].append(intent_name)
        
    save_yaml(DOMAIN_PATH, domain_data)
    
    updated_intents = get_current_intents()
    return f"✅ Intent '{intent_name}' updated (new examples appended safely!)", gr.update(choices=updated_intents)


def delete_intent(intent_name):
    if not intent_name:
        return "⚠️ Please select an intent to delete.", gr.update()
        
    # 1. Remove from NLU
    nlu_data = load_yaml(NLU_PATH)
    if nlu_data and "nlu" in nlu_data and nlu_data["nlu"]:
        nlu_data["nlu"] = [item for item in nlu_data["nlu"] if item.get("intent") != intent_name]
    save_yaml(NLU_PATH, nlu_data)
    
    # 2. Remove from Domain
    domain_data = load_yaml(DOMAIN_PATH)
    if domain_data and "intents" in domain_data and domain_data["intents"]:
        domain_data["intents"] = [i for i in domain_data["intents"] if i != intent_name]
    save_yaml(DOMAIN_PATH, domain_data)
    
    updated_intents = get_current_intents()
    return f"❌ Intent '{intent_name}' deleted.", gr.update(choices=updated_intents, value=None)

def trigger_rasa_train():
    yield "🏗️ Training started... Check terminal for real-time logs."
    try:
        process = subprocess.run(["rasa", "train"], capture_output=True, text=True, check=True)
        yield "🎉 Training Complete! Your new model is ready to test."
    except subprocess.CalledProcessError as e:
        yield f"❌ Training Failed!\n\nError Log:\n{e.stderr}"

def predict_rasa_response(message, history):
    """Sends user chat message to the live running Rasa REST API server."""
    payload = {
        "sender": "gradio_user",
        "message": message
    }
    try:
        response = requests.post(RASA_API_URL, json=payload, timeout=5)
        if response.status_code == 200:
            rasa_responses = response.json()
            if not rasa_responses:
                return "The bot processed the text but sent no message back (check rules/stories context)."
            
            # Combine multiple text outputs if Rasa replies with more than one message bubble
            text_replies = [reply.get("text") for reply in rasa_responses if "text" in reply]
            return "\n".join(text_replies)
        else:
            return f"❌ Error: Rasa server responded with status code {response.status_code}."
    except requests.exceptions.ConnectionError:
        return "⚠️ Connection Failed! Is your background Rasa server running via 'rasa run --enable-api --cors \"*\"'?"
# --- Gradio UI Layout ---
with gr.Blocks(title="Rasa Workspace") as demo:
    gr.Markdown("# 🍕 Rasa Bot Custom Manager Dashboard")
    
    with gr.Tab("Manage Intents"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("### ➕ Add / Update Intent")
                intent_input = gr.Textbox(label="Intent Name", placeholder="e.g., greet")
                examples_input = gr.TextArea(label="Training Examples (One per line)", placeholder="hello\nhi")
                add_btn = gr.Button("Add/Update Intent", variant="primary")
                
            with gr.Column():
                gr.Markdown("### 🗑️ Delete Intent")
                current_intents = get_current_intents()
                delete_dropdown = gr.Dropdown(label="Select Intent to Remove", choices=current_intents)
                delete_btn = gr.Button("Delete Intent", variant="stop")
                
        status_output = gr.Markdown("")

    with gr.Tab("🚂 Automation & Training"):
        train_btn = gr.Button("Train Model Now", variant="primary", size="lg")
        train_output = gr.Textbox(label="Console Status", interactive=False)

    # --- NEW TAB: LIVE CHAT CLIENT ---
    with gr.Tab("💬 Live Chat Client"):
        gr.Markdown("### Talk to Your Model Live")
        gr.Markdown("*Note: Make sure your API server is actively running in the background via `rasa run --enable-api --cors '*'`*")
        gr.ChatInterface(fn=predict_rasa_response)

    # Wire up Event Listeners
    add_btn.click(fn=add_new_intent, inputs=[intent_input, examples_input], outputs=[status_output, delete_dropdown])
    delete_btn.click(fn=delete_intent, inputs=[delete_dropdown], outputs=[status_output, delete_dropdown])
    train_btn.click(fn=trigger_rasa_train, inputs=[], outputs=[train_output])

if __name__ == "__main__":
    demo.queue().launch(server_port=7860)