# officebuddy_simple.py
import streamlit as st
from dataclasses import dataclass
from typing import List, Dict
import datetime as dt

# =========================
# Page config
st.set_page_config(page_title="OfficeBuddy • Office Helper", layout="centered")

st.title("OfficeBuddy • Office Helper Chatbot")
st.write("I can help with tickets, leave requests, and email drafts. Type /help for examples.")

# =========================
# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "active_flow" not in st.session_state:
    st.session_state.active_flow = None

if "flow_data" not in st.session_state:
    st.session_state.flow_data = {}

# =========================
# Flow definitions
@dataclass
class Step:
    field: str
    prompt: str
    required: bool = True

@dataclass
class Flow:
    name: str
    steps: List[Step]

FLOWS = {
    "ticket": Flow(
        "Raise a Ticket",
        [
            Step("category", "Ticket category? (IT/HR/Facilities/Payroll/Other)"),
            Step("summary", "Short summary (one line)"),
            Step("business_impact", "Business impact (what is blocked?)"),
            Step("urgency", "Urgency (Low/Medium/High/Critical)")
        ]
    ),
    "leave": Flow(
        "Leave Request",
        [
            Step("leave_type", "Leave type? (PTO/Sick/Personal/Other)"),
            Step("dates", "Leave dates (start - end)"),
            Step("coverage_plan", "Who will cover your work?"),
            Step("manager", "Manager name")
        ]
    ),
    "email": Flow(
        "Email Draft",
        [
            Step("subject", "Email subject"),
            Step("recipient", "Recipient name or email"),
            Step("body", "Email body / request details")
        ]
    )
}

# =========================
# Flow helpers
def start_flow(flow_name):
    st.session_state.active_flow = flow_name
    st.session_state.flow_data = {}

def get_next_step(flow: Flow):
    for step in flow.steps:
        if step.field not in st.session_state.flow_data:
            return step
    return None

# =========================
# Chat input
user_input = st.text_input("You:", key="input_text")

if user_input:
    ts = dt.datetime.now().strftime("%H:%M")
    
    # Commands
    if user_input.lower() in ["/help", "help"]:
        reply = (
            "Try these:\n"
            "- raise ticket\n"
            "- leave request\n"
            "- draft email\n"
            "Type /cancel to stop any active flow."
        )
    elif user_input.lower() == "/cancel":
        st.session_state.active_flow = None
        st.session_state.flow_data = {}
        reply = "Active task cancelled."
    
    # Flow active
    elif st.session_state.active_flow:
        flow = FLOWS[st.session_state.active_flow]
        step = get_next_step(flow)
        if step:
            st.session_state.flow_data[step.field] = user_input
            next_step = get_next_step(flow)
            if next_step:
                reply = f"{next_step.prompt} {'(required)' if next_step.required else '(optional)'}"
            else:
                # Flow completed
                data = st.session_state.flow_data
                result_lines = [f"{k}: {v}" for k,v in data.items()]
                reply = f"✅ {flow.name} completed:\n" + "\n".join(result_lines)
                st.session_state.active_flow = None
                st.session_state.flow_data = {}
        else:
            reply = "Unexpected input. Type /cancel to restart."
    
    # Start flow
    elif "raise ticket" in user_input.lower():
        start_flow("ticket")
        first_step = get_next_step(FLOWS["ticket"])
        reply = f"Let’s raise a ticket.\n{first_step.prompt} (required)"
    
    elif "leave request" in user_input.lower():
        start_flow("leave")
        first_step = get_next_step(FLOWS["leave"])
        reply = f"Let’s submit a leave request.\n{first_step.prompt} (required)"
    
    elif "draft email" in user_input.lower() or "write email" in user_input.lower():
        start_flow("email")
        first_step = get_next_step(FLOWS["email"])
        reply = f"Let’s draft an email.\n{first_step.prompt} (required)"
    
    else:
        reply = "I can help with tickets, leave requests, and emails. Type /help for commands."
    
    # Store chat
    st.session_state.chat_history.append({"role":"user", "text": user_input, "ts":ts})
    st.session_state.chat_history.append({"role":"assistant", "text": reply, "ts":ts})

# =========================
# Display chat
for chat in st.session_state.chat_history:
    if chat["role"]=="user":
        st.markdown(f"**You ({chat['ts']}):** {chat['text']}")
    else:
        st.markdown(f"**OfficeBuddy ({chat['ts']}):** {chat['text']}")
