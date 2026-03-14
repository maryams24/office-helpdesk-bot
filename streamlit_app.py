# officebuddy_bot_full.py
import streamlit as st
from dataclasses import dataclass
from typing import List, Callable, Optional
import datetime as dt
import re

# =========================
# Page config and styles
st.set_page_config(page_title="OfficeBuddy • Helpdesk Bot", layout="centered")
st.markdown("""
<style>
.block-container { max-width: 900px; padding-top:1rem;}
.badge { display:inline-block; padding:4px 10px; border-radius:999px; background:#A0E7E5; margin-right:6px; font-weight:bold;}
.stButton>button { background-color:#FFAEBC; color:white; font-weight:bold; border-radius:8px; height:40px;}
.stButton>button:hover { background-color:#FF8FA3; }
hr { border:none; border-top:1px solid #E5E7EB; margin:0.6rem 0;}
</style>
""", unsafe_allow_html=True)

# =========================
# Utilities
def _val(v: Optional[str]) -> str: return (v or "").strip() or "N/A"

def chunk_text(text: str, max_chars: int = 1000) -> List[str]:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    for p in parts:
        if len(p) <= max_chars:
            chunks.append(p)
        else:
            for i in range(0,len(p),max_chars):
                chunks.append(p[i:i+max_chars].strip())
    return chunks

# =========================
# Knowledge Base Item
@dataclass
class KBItem:
    title: str
    body: str
    tags: set
    category: str

BUILTIN_KB: List[KBItem] = [
    KBItem("Meeting Agenda Guide","Prepare agenda with outcomes, blockers, actions.","meeting agenda ticket","Productivity"),
    KBItem("Password Reset","Steps to reset locked accounts/MFA.","password reset account login","IT"),
]

def tokenize(text: str) -> set:
    words = set(re.findall(r'\b\w+\b', text.lower()))
    stopwords = {"the","a","an","and","or","to","for","of","in","on","at","is","are","am","with","by","from","this","that","it","as","be","we","you","i","our","your","please","pls","plz","can","could","would","need","want","help","me","my","hi","hello","hey","thanks","thank"}
    return {w for w in words if w not in stopwords and len(w)>=3}

def build_kb(uploaded_texts: List[str]) -> List[KBItem]:
    kb = list(BUILTIN_KB)
    for idx, text in enumerate(uploaded_texts,start=1):
        for cidx, chunk in enumerate(chunk_text(text),start=1):
            kb.append(KBItem(f"UploadedDoc{idx}.{cidx}", chunk, tokenize(chunk), "Uploaded"))
    return kb

def retrieve(kb: List[KBItem], query: str, top_k: int = 3):
    q = tokenize(query)
    scored = []
    for item in kb:
        overlap = len(q & item.tags)
        if overlap>0: scored.append((overlap, item))
    scored.sort(key=lambda x:x[0], reverse=True)
    return scored[:top_k]

# =========================
# Flow for Ticket
@dataclass
class Step:
    field: str
    prompt: str
    required: bool = True

@dataclass
class Flow:
    name: str
    intro: str
    steps: List[Step]
    formatter: Callable[[dict], str]

def format_ticket(data: dict) -> str:
    return "\n".join([f"{k}: {_val(v)}" for k,v in data.items()])

def format_leave(data: dict) -> str:
    return f"""Subject: Leave Request - {_val(data.get('Leave Type'))}

Dear {_val(data.get('Manager'))},

I would like to request {_val(data.get('Leave Type'))} from {_val(data.get('Start Date'))} to {_val(data.get('End Date'))} due to {_val(data.get('Reason'))}.

Kindly approve.

Thank you,
{_val(data.get('Employee Name'))}
"""

def format_email(data: dict) -> str:
    return f"""Subject: {_val(data.get('Subject'))}

Dear {_val(data.get('Recipient'))},

{_val(data.get('Body'))}

Best regards,
{_val(data.get('Sender'))}
"""

FLOWS = {
    "ticket": Flow("ticket","Let's raise a helpdesk ticket.",[
        Step("Category","Type of ticket? (IT/HR/Facilities/Other)"),
        Step("Summary","Brief summary of issue"),
        Step("Business impact","Impact/blocked areas"),
        Step("Urgency","Urgency (Low/Medium/High/Critical)"),
    ], format_ticket),
    "leave": Flow("leave","Let's draft a leave request email.",[
        Step("Employee Name","Your full name"),
        Step("Manager","Manager/Approver name"),
        Step("Leave Type","Type of leave (Casual/Sick/Annual)"),
        Step("Start Date","Leave start date"),
        Step("End Date","Leave end date"),
        Step("Reason","Reason for leave"),
    ], format_leave),
    "email": Flow("email","Let's draft a professional email.",[
        Step("Sender","Your name"),
        Step("Recipient","Recipient name"),
        Step("Subject","Email subject"),
        Step("Body","Email body"),
    ], format_email)
}

# =========================
# Session state init
for key, default in [("messages",[]),("active_flow",None),("flow_step_idx",0),("flow_data",{}),("last_output",""),("uploaded_texts",[])]:
    if key not in st.session_state: st.session_state[key] = default

def start_flow(flow_key: str):
    st.session_state.active_flow = flow_key
    st.session_state.flow_step_idx = 0
    st.session_state.flow_data = {s.field:"" for s in FLOWS[flow_key].steps}

def current_step(flow_key: str) -> Step:
    return FLOWS[flow_key].steps[st.session_state.flow_step_idx]

def flow_done(flow_key: str) -> bool:
    return all((_val(st.session_state.flow_data.get(s.field)) != "N/A") for s in FLOWS[flow_key].steps if s.required)

def next_step(flow_key: str) -> int:
    for idx, s in enumerate(FLOWS[flow_key].steps):
        if not st.session_state.flow_data.get(s.field): return idx
    return len(FLOWS[flow_key].steps)-1

# =========================
# Assistant reply
def assistant_reply(user_text: str) -> str:
    t = user_text.strip()
    if t.lower() in ["/help","help"]:
        return "Commands: /help, /cancel, /clear. Ask: 'raise ticket', 'leave request', 'draft email'."
    if t.lower() == "/cancel":
        st.session_state.active_flow = None
        st.session_state.flow_step_idx = 0
        st.session_state.flow_data = {}
        return "Flow cancelled."
    if t.lower() == "/clear":
        st.session_state.messages=[]
        return "Chat cleared."
    
    # Active flow
    if st.session_state.active_flow:
        fk = st.session_state.active_flow
        step = current_step(fk)
        st.session_state.flow_data[step.field] = t
        if flow_done(fk):
            out = FLOWS[fk].formatter(st.session_state.flow_data)
            st.session_state.last_output = out
            st.session_state.active_flow = None
            return "✅ Completed! Review below:\n\n" + out
        st.session_state.flow_step_idx = next_step(fk)
        nxt = current_step(fk)
        return f"{nxt.prompt} (required)"
    
    # Start flows
    if "raise ticket" in t.lower(): start_flow("ticket")
    elif "leave request" in t.lower(): start_flow("leave")
    elif "draft email" in t.lower(): start_flow("email")
    
    if st.session_state.active_flow:
        s0 = current_step(st.session_state.active_flow)
        return f"{FLOWS[st.session_state.active_flow].intro}\n\n{s0.prompt} (required)"
    
    # KB search
    hits = retrieve(build_kb(st.session_state.uploaded_texts), t)
    if hits:
        blocks = [f"**[{item.category}] {item.title}**\n{item.body}" for _, item in hits]
        return "\n\n---\n\n".join(blocks)
    
    return "I can help with tickets, leave requests, email drafts, or uploaded knowledge files. Type /help."

# =========================
# Sidebar: file upload
with st.sidebar:
    st.subheader("Upload documents for KB search")
    ups = st.file_uploader("Upload .txt or .md", type=["txt","md"], accept_multiple_files=True)
    if ups:
        st.session_state.uploaded_texts = []
        for f in ups: st.session_state.uploaded_texts.append(f.read().decode("utf-8", errors="ignore"))
        st.success(f"Loaded {len(ups)} file(s)")

# =========================
# Chat UI
st.title("OfficeBuddy • Office Helpdesk Bot 💼")
st.markdown('<span class="badge">Tickets</span> <span class="badge">Leave Request</span> <span class="badge">Email Draft</span>', unsafe_allow_html=True)

user_text = st.chat_input("Type your question, e.g., 'raise ticket' or 'leave request'")
if user_text:
    ts = dt.datetime.now().strftime("%H:%M")
    reply = assistant_reply(user_text)
    st.session_state.messages.append({"role":"user","content":user_text,"ts":ts})
    st.session_state.messages.append({"role":"assistant","content":reply,"ts":ts})

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("ts"): st.caption(m["ts"])

# =========================
# Download last output
if st.session_state.last_output.strip():
    st.download_button(
        "Download last output",
        data=st.session_state.last_output,
        file_name="officebuddy_output.txt",
    )
