import gradio as gr
import os
import subprocess
import requests
import re
from ruamel.yaml import YAML
from pyvis.network import Network
from ruamel.yaml.scalarstring import LiteralScalarString

# Initialize ruamel.yaml for strict round-trip formatting
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# --- File Paths ---
NLU_PATH = "data/nlu.yml"
STORIES_PATH = "data/stories.yml"
DOMAIN_PATH = "domain.yml"
RASA_API_URL = "http://localhost:5005/webhooks/rest/webhook"
GRAPH_HTML_PATH = "model_graph.html"
RULES_PATH = "data/rules.yml"

def load_yaml(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.load(f) or {}

def validate_domain_asset(asset_type, name, text_template=None):
    """Pre-flight validator checking naming standards and value safety."""
    if not name or not name.strip():
        return False, "❌ Error: Asset name cannot be blank."
    
    name = name.strip()
    
    # 1. Alphanumeric and underscore formatting check
    if not re.match(r"^[a-zA-Z0-9_]+$", name):
        return False, f"❌ Error: Name '{name}' contains illegal characters. Use only letters, numbers, and underscores (_)."
        
    # 2. Rasa prefix structural check
    if asset_type == "Response Template" and not name.startswith("utter_"):
        return False, f"⚠️ Notice: Action responses should typically begin with the 'utter_' prefix (e.g., 'utter_{name}')."

    if asset_type == "Response Template" and (not text_template or not text_template.strip()):
        return False, "❌ Error: Response templates require actual text utterances for the bot to speak."

    return True, "✅ Pre-flight validation checks passed successfully."


def register_domain_asset(asset_type, asset_name, response_text):
    """Safely updates domain.yml data structure without breaking comments or formatting."""
    asset_name = asset_name.strip()
    
    # Run gate verification first
    is_valid, message = validate_domain_asset(asset_type, asset_name, response_text)
    if not is_valid:
        return message, gr.update(), gr.update()
        
    domain_data = load_yaml(DOMAIN_PATH)
    if not domain_data:
        domain_data = {"version": "3.1", "intents": [], "responses": {}, "actions": []}

    # Ensure sections exist safely inside dictionary layers
    if "intents" not in domain_data or domain_data["intents"] is None: domain_data["intents"] = []
    if "actions" not in domain_data or domain_data["actions"] is None: domain_data["actions"] = []
    if "responses" not in domain_data or domain_data["responses"] is None: domain_data["responses"] = {}

    # --- HANDLE INTENT STORAGE UPDATE ---
    if asset_type == "Intent":
        if asset_name in domain_data["intents"]:
            return f"ℹ️ Intent '{asset_name}' is already registered in the domain.", gr.update(), gr.update()
        domain_data["intents"].append(asset_name)
        log_msg = f"🎉 Successfully added intent '{asset_name}' to Domain configuration rules."

    # --- HANDLE UTTERANCE RESPONSE STORAGE UPDATE ---
    elif asset_type == "Response Template":
        # In Rasa, responses auto-register as actions, but custom ones need tracking
        if asset_name in domain_data["responses"]:
            action_type_word = "Updated existing"
        else:
            action_type_word = "Added new"
            
        # Structure the response layout cleanly using Rasa list elements format
        domain_data["responses"][asset_name] = [{"text": response_text.strip()}]
        log_msg = f"🎉 {action_type_word} action response rule template '{asset_name}' successfully."

    # Execute isolated write-back block execution
    save_yaml(DOMAIN_PATH, domain_data)
    
    # Refresh selections dynamically across dashboard elements
    updated_intents = domain_data.get("intents", [])
    updated_responses = list(domain_data.get("responses", {}).keys())
    
    return log_msg, gr.update(choices=updated_intents), gr.update(choices=updated_responses)


def read_asset_details(asset_type, asset_name):
    """Reads details of an existing asset for inspection or quick viewing."""
    if not asset_name:
        return ""
    domain_data = load_yaml(DOMAIN_PATH)
    if asset_type == "Intent":
        return f"🔒 Intent verified inside active domain layout."
    elif asset_type == "Response Template":
        resp_block = domain_data.get("responses", {}).get(asset_name, [])
        if resp_block and isinstance(resp_block, list) and "text" in resp_block[0]:
            return f"💬 Current Text Utterance:\n\"{resp_block[0]['text']}\""
    return "No additional parameters found."

def save_yaml(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

def get_current_intents():
    domain = load_yaml(DOMAIN_PATH)
    return domain.get("intents", []) if domain else []

def generate_model_graph():
    """Parses local Rasa configuration files into an interactive visual graph map."""
    nlu_data = load_yaml(NLU_PATH)
    stories_data = load_yaml(STORIES_PATH)
    rules_data = load_yaml(RULES_PATH)  # <-- Load the rules file!
    
    # Initialize PyVis network graph engine
    net = Network(height="550px", width="100%", bgcolor="#222222", font_color="white", directed=True)
    net.set_options("""
    var options = {
      "physics": {
        "barnesHut": { "gravitationalConstant": -4000, "centralGravity": 0.3, "springLength": 120, "springConstant": 0.04 }
      },
      "edges": { "smooth": { "type": "cubicBezier", "roundness": 0.4 } }
    }
    """)
    
    # Extract known intents and sample count sizes from NLU file
    intents = set()
    intent_counts = {}
    if nlu_data and "nlu" in nlu_data and nlu_data["nlu"]:
        for item in nlu_data["nlu"]:
            if "intent" in item:
                name = item["intent"]
                intents.add(name)
                ex = item.get("examples", "")
                count = len([line for line in ex.split("\n") if line.strip()]) if isinstance(ex, str) else len(ex)
                intent_counts[name] = count

    tracked_actions = set()
    edges_to_add = set()

    # 1. Process Stories
    if stories_data and "stories" in stories_data and stories_data["stories"]:
        for story_block in stories_data["stories"]:
            steps = story_block.get("steps", [])
            story_name = story_block.get("story", "Unnamed Story")
            
            for i in range(len(steps) - 1):
                curr_name = steps[i].get("intent") or steps[i].get("action")
                next_name = steps[i+1].get("intent") or steps[i+1].get("action")
                
                if curr_name and next_name:
                    if steps[i].get("action"): tracked_actions.add(curr_name)
                    if steps[i+1].get("action"): tracked_actions.add(next_name)
                    edges_to_add.add((curr_name, next_name, f"Story: {story_name}", "#f1c40f")) # Yellow for stories

    # 2. Process Rules (NEW LOGIC)
    if rules_data and "rules" in rules_data and rules_data["rules"]:
        for rule_block in rules_data["rules"]:
            steps = rule_block.get("steps", [])
            rule_name = rule_block.get("rule", "Unnamed Rule")
            
            for i in range(len(steps) - 1):
                curr_name = steps[i].get("intent") or steps[i].get("action")
                next_name = steps[i+1].get("intent") or steps[i+1].get("action")
                
                if curr_name and next_name:
                    if steps[i].get("action"): tracked_actions.add(curr_name)
                    if steps[i+1].get("action"): tracked_actions.add(next_name)
                    # We give rules a striking RED color so you can visually distinguish them from stories!
                    edges_to_add.add((curr_name, next_name, f"Rule: {rule_name}", "#e74c3c")) 

    # Add Intent Nodes
    for intent in intents:
        count = intent_counts.get(intent, 0)
        net.add_node(intent, label=f"💬 {intent}", color="#4a90e2", shape="ellipse", title=f"Intent: {intent}\nExamples: {count}")
        
    # Add Action Nodes
    for action in tracked_actions:
        net.add_node(action, label=f"⚙️ {action}", color="#2ecc71", shape="box", title=f"Action: {action}")

    # Inject the relationship arrow paths with their distinct color traits
    for source, target, path_title, edge_color in edges_to_add:
        net.add_edge(source, target, title=path_title, color=edge_color, width=2)
        
    # Save and bundle to base64 inline string format
    net.save_graph(GRAPH_HTML_PATH)
    with open(GRAPH_HTML_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    import base64
    b64_content = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")
    
    return f"""
    <iframe src="data:text/html;base64,{b64_content}" width="100%" height="600px" style="border:none; background-color: #222222; border-radius: 8px;"></iframe>
    """

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
with gr.Blocks(title="Rasa Workspace V2") as demo:
    gr.Markdown("# 🍕 Rasa Bot Custom Manager Dashboard (v2.0)")
    
    # with gr.Tab("Manage Intents"):
    #     with gr.Row():
    #         with gr.Column():
    #             gr.Markdown("### ➕ Add / Update Intent")
    #             intent_input = gr.Textbox(label="Intent Name", placeholder="e.g., greet")
    #             examples_input = gr.TextArea(label="Training Examples (One per line)", placeholder="hello\nhi")
    #             add_btn = gr.Button("Add/Update Intent", variant="primary")
                
    #         with gr.Column():
    #             gr.Markdown("### 🗑️ Delete Intent")
    #             current_intents = get_current_intents()
    #             delete_dropdown = gr.Dropdown(label="Select Intent to Remove", choices=current_intents)
    #             delete_btn = gr.Button("Delete Intent", variant="stop")
                
    #     status_output = gr.Markdown("")
    with gr.Tab("🛡️ Domain Registry Manager"):
        gr.Markdown("### Core Domain Asset Configuration")
        gr.Markdown("*Safely manage assets registered inside `domain.yml` with strict validation guardrails.*")
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("#### ➕ Register New Domain Asset")
                asset_type_selector = gr.Radio(
                    choices=["Intent", "Response Template"], 
                    label="Asset Type", 
                    value="Intent"
                )
                
                asset_name_input = gr.Textbox(
                    label="Asset Variable Name", 
                    placeholder="e.g., ask_payment_status or utter_greet"
                )
                
                # Dynamic context block visibility handled pythonically
                response_text_input = gr.TextArea(
                    label="Response Utterance Text (Required for templates)", 
                    placeholder="Hello! How can I assist you today?",
                    visible=False
                )
                
                # Toggle template field display based on selector value
                def toggle_response_visibility(choice):
                    return gr.update(visible=(choice == "Response Template"))
                
                asset_type_selector.change(
                    fn=toggle_response_visibility, 
                    inputs=[asset_type_selector], 
                    outputs=[response_text_input]
                )
                
                register_btn = gr.Button("Validate & Commit Asset", variant="primary")
                
            with gr.Column(scale=1):
                gr.Markdown("#### 🔍 Active Domain Inspector")
                
                domain_data_current = load_yaml(DOMAIN_PATH)
                init_intents = domain_data_current.get("intents", [])
                init_responses = list(domain_data_current.get("responses", {}).keys())
                
                inspector_intent_dropdown = gr.Dropdown(
                    label="Registered Core Intents", 
                    choices=init_intents
                )
                inspector_response_dropdown = gr.Dropdown(
                    label="Registered Response Templates (`utter_`)", 
                    choices=init_responses
                )
                
                inspect_output = gr.Code(
                    label="Asset Metadata Readout", 
                    language="markdown", 
                    interactive=False
                )
                
                # Wire up inspection readouts instantly on click event changes
                inspector_intent_dropdown.change(
                    fn=lambda name: read_asset_details("Intent", name),
                    inputs=[inspector_intent_dropdown],
                    outputs=[inspect_output]
                )
                inspector_response_dropdown.change(
                    fn=lambda name: read_asset_details("Response Template", name),
                    inputs=[inspector_response_dropdown],
                    outputs=[inspect_output]
                )

        domain_status_feed = gr.Markdown("### Application State Status: Standing By...")
        
        # Connect main activation listener click action paths
        register_btn.click(
            fn=register_domain_asset,
            inputs=[asset_type_selector, asset_name_input, response_text_input],
            outputs=[domain_status_feed, inspector_intent_dropdown, inspector_response_dropdown]
        )

    with gr.Tab("🚂 Automation & Training"):
        train_btn = gr.Button("Train Model Now", variant="primary", size="lg")
        train_output = gr.Textbox(label="Console Status", interactive=False)

    with gr.Tab("💬 Live Chat Client"):
        gr.Markdown("### Talk to Your Model Live")
        gr.ChatInterface(fn=predict_rasa_response)

    # --- NEW V2 TAB: INTERACTIVE GRAPH MAP VISUALIZATION ---
    with gr.Tab("🕸️ Model Semantic Graph"):
        gr.Markdown("### Interactive Conversational Flow Mapping")
        gr.Markdown("*Visualizes how your intents (blue circles) and action choices (green rectangles) route structurally through conversation workflows.*")
        
        refresh_graph_btn = gr.Button("🔄 Render / Refresh Network Architecture", variant="secondary")
        graph_html_display = gr.HTML(value="<div style='padding:20px; color:#aaa; text-align:center;'>Click the button above to compile and scan your filesystem.</div>")

    # Wire up Event Listeners
    # add_btn.click(fn=add_new_intent, inputs=[intent_input, examples_input], outputs=[status_output, delete_dropdown])
    # delete_btn.click(fn=delete_intent, inputs=[delete_dropdown], outputs=[status_output, delete_dropdown])
    train_btn.click(fn=trigger_rasa_train, inputs=[], outputs=[train_output])
    
    # Connect graph compiler activation actions
    refresh_graph_btn.click(fn=generate_model_graph, inputs=[], outputs=[graph_html_display])

if __name__ == "__main__":
    demo.queue().launch(server_port=7860)