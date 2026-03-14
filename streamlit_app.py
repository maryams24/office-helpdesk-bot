# officebuddy_simple.py
import streamlit as st
import datetime as dt

st.set_page_config(page_title="OfficeBuddy • Simple Bot", layout="centered")

st.markdown("""
<style>
div.stButton > button { background-color: #4CAF50; color: white; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# Initialize session
if "flow" not in st.session_state:
    st.session_state.flow = None
    st.session_state.step_idx = 0
    st.session_state.data = {}
    st.session_state.messages = []
    st.session_state.last_output = ""

# ----------------------
# Flows
EMAIL_FLOW = [
    ("subject", "Enter the subject line: (e.g., Request new laptop)"),
    ("recipient", "Who is this email to?"),
    ("body_context", "Briefly describe the context or reason for this email"),
    ("what_needed", "What do you need? (Owner | Date)"),
    ("approval", "Decision/approval needed (optional)"),
    ("sender", "Your name")
]

LEAVE_FLOW = [
    ("type", "Leave type? (PTO/Sick/Personal/Other)"),
    ("dates", "Dates of leave (e.g., 2026-03-20 to 2026-03-25)"),
    ("coverage", "Who will cover your work?"),
    ("manager", "Manager name"),
    ("notes", "Any additional notes (optional)")
]

TICKET_FLOW = [
    ("category", "Ticket category? (IT/HR/Facilities/Payroll/Other)"),
    ("summary", "Short summary (one line)"),
    ("impact", "Business impact"),
    ("urgency", "Urgency (Low/Medium/High/Critical)")
]

# ----------------------
# Helper to format outputs
def format_email(data):
    return f"""Subject: {data['subject']}

Hi {data['recipient']}, I’m reaching out to request {data['body_context']}.

Context:
What I need (Owner | Date): {data['what_needed']}
Decision/approval needed: {data.get('approval','N/A')}

Thanks, {data['sender']}
"""

def format_leave(data):
    return f"""Leave Request

Type: {data['type']}
Dates: {data['dates']}
Coverage plan: {data['coverage']}
Manager: {data['manager']}
Notes: {data.get('notes','N/A')}
"""

def format_ticket(data):
    return f"""Ticket

Category: {data['category']}
Summary: {data['summary']}
Business impact: {data['impact']}
Urgency: {data['urgency']}
"""

# ----------------------
# Flow handler
def start_flow(flow_name):
    st.session_state.flow = flow_name
    st.session_state.step_idx = 0
    st.session_state.data = {}

def current_prompt():
    flow_name = st.session_state.flow
    idx = st.session_state.step_idx
    if flow_name=="email":
        field, prompt = EMAIL_FLOW[idx]
    elif flow_name=="leave":
        field, prompt = LEAVE_FLOW[idx]
    elif flow_name=="ticket":
        field, prompt = TICKET_FLOW[idx]
    return field, prompt

def next_step(user_input):
    field, prompt = current_prompt()
    st.session_state.data[field] = user_input
    # move to next
    st.session_state.step_idx += 1
    # check done
    flow_name = st.session_state.flow
    if flow_name=="email" and st.session_state.step_idx >= len(EMAIL_FLOW):
        st.session_state.last_output = format_email(st.session_state.data)
        st.session_state.flow = None
    elif flow_name=="leave" and st.session_state.step_idx >= len(LEAVE_FLOW):
        st.session_state.last_output = format_leave(st.session_state.data)
        st.session_state.flow = None
    elif flow_name=="ticket" and st.session_state.step_idx >= len(TICKET_FLOW):
        st.session_state.last_output = format_ticket(st.session_state.data)
        st.session_state.flow = None

# ----------------------
# Sidebar: upload policies/texts
st.sidebar.header("Policy Uploads for Q&A")
uploaded_files = st.sidebar.file_uploader("Upload .txt or .md", type=["txt","md"], accept_multiple_files=True)
kb_texts = []
if uploaded_files:
    for f in uploaded_files:
        kb_texts.append(f.read().decode("utf-8", errors="ignore"))
    st.sidebar.success(f"Loaded {len(uploaded_files)} files")

# ----------------------
# Chat UI
st.title("OfficeBuddy • Simple Office Helper")

user_input = st.text_input("Ask me (e.g., draft email, raise ticket, leave request)")

if user_input:
    # Intent detection
    text = user_input.lower()
    if "email" in text:
        start_flow("email")
    elif "leave" in text:
        start_flow("leave")
    elif "ticket" in text:
        start_flow("ticket")
    else:
        st.session_state.messages.append(("assistant","I can help with email, leave requests, or tickets."))

# Flow step input
if st.session_state.flow:
    field, prompt = current_prompt()
    user_step_input = st.text_input(prompt, key="flow_input")
    if user_step_input:
        next_step(user_step_input)
        st.experimental_rerun()

# Show last output
if st.session_state.last_output:
    st.subheader("Generated Output")
    st.text_area("Preview", st.session_state.last_output, height=250)
    st.download_button("Download Output", st.session_state.last_output, file_name="officebuddy_output.txt")
