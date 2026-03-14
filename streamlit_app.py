# officebuddy_bot.py
import re, datetime as dt
from dataclasses import dataclass
from typing import Callable, Optional, List, Tuple
import streamlit as st

# =========================
# Page config
st.set_page_config(page_title="OfficeBuddy • Helpdesk Bot", layout="centered")

st.markdown("""
<style>
.block-container { max-width: 980px; padding-top:1rem;}
.small { color:#6B7280; font-size:0.9rem;}
.badge { display:inline-block; padding:2px 8px; border-radius:999px; background:#F9FAFB; margin-right:6px; }
hr { border:none; border-top:1px solid #E5E7EB; margin:0.6rem 0;}
</style>
""", unsafe_allow_html=True)

# =========================
# Text utils
STOPWORDS = {"the","a","an","and","or","to","for","of","in","on","at","is","are","am","with","by","from","this","that","it","as","be","we","you","i","our","your","please","pls","plz","can","could","would","need","want","help","me","my","hi","hello","hey","thanks","thank"}

def normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s\-/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def tokenize(text: str) -> set:
    words = set(normalize(text).split())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}

def chunk_text(text: str, max_chars: int = 1100) -> List[str]:
    text = (text or "").strip()
    if not text: return []
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
# Knowledge Base
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

def build_kb(uploaded_texts: List[str]) -> List[KBItem]:
    kb = list(BUILTIN_KB)
    for up_idx, text in enumerate(uploaded_texts,start=1):
        for ch_idx, chunk in enumerate(chunk_text(text),start=1):
            kb.append(KBItem(f"Uploaded Doc {up_idx}.{ch_idx}", chunk, tokenize(chunk), "Uploaded"))
    return kb

def retrieve(kb: List[KBItem], query: str, top_k: int = 3) -> List[Tuple[float, KBItem]]:
    q = tokenize(query)
    if not q: return []
    scored = []
    for item in kb:
        overlap = len(q & item.tags)
        if overlap > 0:
            score = float(overlap)
            scored.append((score, item))
    scored.sort(key=lambda x:x[0], reverse=True)
    return scored[:top_k]

# =========================
# Flows and Templates
@dataclass
class Step:
    field: str
    prompt: str
    required: bool = True
    hint: str = ""

@dataclass
class Flow:
    name: str
    intro: str
    steps: List[Step]
    formatter: Callable[[dict], str]

def _val(v: Optional[str]) -> str: return (v or "").strip() or "N/A"

def format_ticket(data: dict) -> str:
    return "\n".join([f"{k}: {_val(v)}" for k,v in data.items()])

FLOWS = {
    "ticket": Flow(
        "ticket",
        "Raise a ticket with required details.",
        [
            Step("Category","Type of ticket? (IT/HR/Facilities/Payroll/Other)"),
            Step("Summary","Short summary (one line)."),
            Step("Business impact","What is affected/blocked?"),
            Step("Urgency","Urgency level (Low/Medium/High/Critical)")
        ],
        format_ticket
    )
}

# =========================
# Session state init
def ss_init():
    for key in ["messages","uploaded_texts","active_flow","flow_step_idx","flow_data","last_export_text"]:
        if key not in st.session_state: st.session_state[key] = [] if "messages uploaded_texts".find(key)>=0 else None if key=="active_flow" else 0 if key=="flow_step_idx" else {} if key=="flow_data" else ""
ss_init()

# =========================
# Flow helpers
def start_flow(flow_key: str):
    flow = FLOWS[flow_key]
    st.session_state.active_flow = flow_key
    st.session_state.flow_step_idx = 0
    st.session_state.flow_data = {s.field:"" for s in flow.steps}

def current_step(flow_key: str) -> Step:
    return FLOWS[flow_key].steps[st.session_state.flow_step_idx]

def flow_done(flow_key: str) -> bool:
    data = st.session_state.flow_data
    return all((data.get(s.field) or "").strip() for s in FLOWS[flow_key].steps if s.required)

def next_missing_step_index(flow_key: str) -> int:
    data = st.session_state.flow_data
    for idx, s in enumerate(FLOWS[flow_key].steps):
        if s.required and not (data.get(s.field) or "").strip(): return idx
    return len(FLOWS[flow_key].steps)-1

# =========================
# Assistant reply
def assistant_reply(user_text: str, kb: List[KBItem]) -> str:
    t = (user_text or "").strip()
    # Commands
    if t.lower() in ["/help","help"]:
        return "Commands: /help, /cancel, /clear. Ask: raise ticket, prepare agenda, access request..."
    if t.lower() == "/cancel":
        st.session_state.active_flow = None
        st.session_state.flow_step_idx = 0
        st.session_state.flow_data = {}
        return "Flow cancelled."
    if t.lower() == "/clear":
        st.session_state.messages = []
        return "Chat cleared."
    
    # Flow active
    if st.session_state.active_flow:
        fk = st.session_state.active_flow
        step = current_step(fk)
        answer = t
        st.session_state.flow_data[step.field] = answer
        if flow_done(fk):
            out = FLOWS[fk].formatter(st.session_state.flow_data)
            st.session_state.last_export_text = out
            st.session_state.active_flow = None
            return "Done. Review below:\n\n"+out
        st.session_state.flow_step_idx = next_missing_step_index(fk)
        nxt = current_step(fk)
        req = " (required)" if nxt.required else " (optional)"
        return f"{nxt.prompt}{req}\nHint: {nxt.hint}"
    
    # Detect KB query
    hits = retrieve(kb, t)
    if hits:
        blocks = [f"**[{item.category}] {item.title}**\n{item.body}" for score,item in hits]
        return "\n\n---\n\n".join(blocks)
    
    # Detect flow start
    if any(k in t.lower() for k in ["raise ticket","open ticket","helpdesk"]):
        start_flow("ticket")
        s0 = current_step("ticket")
        return f"{FLOWS['ticket'].intro}\n\n{s0.prompt} (required)"
    
    return "I can help with tickets, templates, and policy queries. Type /help for commands."

# =========================
# Sidebar: upload files
with st.sidebar:
    st.subheader("Upload documents for KB search")
    ups = st.file_uploader("Upload .txt or .md", type=["txt","md"], accept_multiple_files=True)
    if ups:
        st.session_state.uploaded_texts = []
        for f in ups: st.session_state.uploaded_texts.append(f.read().decode("utf-8", errors="ignore"))
        st.success(f"Loaded {len(ups)} file(s)")

# =========================
# Build KB
kb = build_kb(st.session_state.uploaded_texts)

# =========================
# Chat UI
st.title("OfficeBuddy • Office Helpdesk Bot")
user_text = st.chat_input("Ask anything office-related")
if user_text:
    ts = dt.datetime.now().strftime("%H:%M")
    reply = assistant_reply(user_text, kb)
    st.session_state.messages.append({"role":"user","content":user_text,"ts":ts})
    st.session_state.messages.append({"role":"assistant","content":reply,"ts":ts})
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("ts"): st.caption(m["ts"])

# =========================
# Export last output
if st.session_state.last_export_text.strip():
    st.download_button("Download last output", data=st.session_state.last_export_text, file_name="officebuddy_output.txt")
