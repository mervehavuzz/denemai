import streamlit as st
import google.generativeai as genai
import json
import os
from datetime import datetime

# ─────────────────────────────────────────
# SAYFA AYARI
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Siber Hukuk Asistanı",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────
# VERİTABANI FONKSİYONLARI
# ─────────────────────────────────────────
DB_FILE = "chat_history.json"

def load_db() -> dict:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_db(data: dict) -> None:
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_current() -> None:
    db = load_db()
    db[st.session_state.chat_id] = st.session_state.messages
    save_db(db)

# ─────────────────────────────────────────
# API & MODEL YAPILANDIRMASI
# ─────────────────────────────────────────
SYSTEM_PROMPT = (
    "Sen uzman bir Siber Hukuk Asistanısın. Yanıtlarını resmi, maddeli ve "
    "Türkiye yasalarına (TCK, KVKK, 5651 sayılı Kanun vb.) dayandırarak ver. "
    "Gerektiğinde ilgili kanun maddelerini belirt. Yanıtların net ve anlaşılır olsun."
)

try:
    # API Anahtarını Streamlit Secrets'tan al
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # Modeli system_instruction ile başlatıyoruz (en verimli yöntem)
    _model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT
    )
except Exception as e:
    st.error(f"API Yapılandırma Hatası: {e}")
    st.stop()

# ─────────────────────────────────────────
# SESSION STATE (OTURUM YÖNETİMİ)
# ─────────────────────────────────────────
if "chat_id" not in st.session_state:
    st.session_state.chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
if "messages" not in st.session_state:
    db0 = load_db()
    st.session_state.messages = db0.get(st.session_state.chat_id, [])
if "gem_session" not in st.session_state:
    # Mevcut geçmişi model formatına çevir
    history = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
        for m in st.session_state.messages
    ]
    st.session_state.gem_session = _model.start_chat(history=history)
if "queued" not in st.session_state:
    st.session_state.queued = ""

# ─────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────
def stream_response(prompt: str, placeholder) -> str:
    # System prompt model tanımında olduğu için burada tekrar eklemeye gerek yok
    response = st.session_state.gem_session.send_message(prompt, stream=True)
    text = ""
    for chunk in response:
        if chunk.text:
            text += chunk.text
            placeholder.markdown(text + "▌")
    placeholder.markdown(text)
    return text

def process_message(user_text: str) -> None:
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_text)
    
    st.session_state.messages.append({"role": "user", "content": user_text})
    
    with st.chat_message("assistant", avatar="⚖️"):
        ph = st.empty()
        try:
            answer = stream_response(user_text, ph)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # İlk mesajda başlık oluştur
            if len(st.session_state.messages) <= 2:
                st.session_state.messages[0]["title"] = user_text[:30]
            
            save_current()
        except Exception as err:
            ph.error(f"⚠️ Yanıt oluşturulurken bir hata oluştu: {err}")

def load_chat(cid: str) -> None:
    db = load_db()
    msgs = db.get(cid, [])
    st.session_state.chat_id = cid
    st.session_state.messages = msgs
    st.session_state.gem_session = _model.start_chat(history=[
        {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
        for m in msgs
    ])
    st.session_state.queued = ""

def new_chat() -> None:
    st.session_state.chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.messages = []
    st.session_state.gem_session = _model.start_chat(history=[])
    st.session_state.queued = ""

def group_by_date(db: dict) -> dict:
    today = datetime.now().date()
    groups = {"Bugün": [], "Bu Hafta": [], "Geçen Hafta": [], "Eskiler": []}
    for cid in sorted(db.keys(), reverse=True):
        try:
            diff = (today - datetime.strptime(cid, "%Y%m%d_%H%M%S").date()).days
            if   diff == 0:  groups["Bugün"].append(cid)
            elif diff <= 7:  groups["Bu Hafta"].append(cid)
            elif diff <= 14: groups["Geçen Hafta"].append(cid)
            else:            groups["Eskiler"].append(cid)
        except Exception:
            groups["Eskiler"].append(cid)
    return groups

# ─────────────────────────────────────────
# URL PARAMETRELERİ VE AKSİYONLAR
# ─────────────────────────────────────────
params = st.query_params
sb_action = params.get("sb_action")
sb_cid = params.get("sb_cid")

if sb_action == "new":
    new_chat()
    st.query_params.clear()
    st.rerun()
elif sb_action == "load" and sb_cid:
    load_chat(sb_cid)
    st.query_params.clear()
    st.rerun()

# ─────────────────────────────────────────
# CSS TASARIMI (Arayüz Güzelleştirme)
# ─────────────────────────────────────────
SB_WIDTH = 260
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {{
    font-family: 'DM Sans', sans-serif !important;
    background-color: #F8F7FF !important;
}}

/* Sidebar'ı gizle (Custom sidebar kullanıyoruz) */
[data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="collapsedControl"] {{
    display: none !important;
}}

/* Ana içerik genişliği */
.main .block-container {{
    max-width: 800px !important;
    padding-left: {SB_WIDTH + 40}px !important;
    padding-bottom: 150px !important;
}}

/* Custom Sidebar Stili */
#custom-sidebar {{
    position: fixed; top: 0; left: 0; width: {SB_WIDTH}px; height: 100vh;
    background: linear-gradient(180deg, #5B2FD9 0%, #7C3FFC 100%);
    color: white; z-index: 1000; padding: 20px;
}}

.sb-new-btn {{
    width: 100%; background: #fff; color: #5B2FD9; border: none;
    padding: 10px; border-radius: 8px; font-weight: bold; cursor: pointer;
    margin-bottom: 20px;
}}

.sb-chat-btn {{
    width: 100%; background: rgba(255,255,255,0.1); color: white;
    border: none; padding: 8px; border-radius: 5px; text-align: left;
    margin-bottom: 5px; font-size: 0.8rem; cursor: pointer;
}}

.sb-chat-btn:hover {{ background: rgba(255,255,255,0.2); }}

/* Chat Balonları */
[data-testid="stChatMessage"] {{ border-radius: 15px; margin-bottom: 10px; }}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# CUSTOM SIDEBAR HTML
# ─────────────────────────────────────────
db_sb = load_db()
grouped = group_by_date(db_sb)
history_html = ""

for grp, cids in grouped.items():
    if cids:
        history_html += f"<p style='font-size:0.7rem; opacity:0.6; margin-top:15px;'>{grp}</p>"
        for cid in cids:
            msgs_s = db_sb.get(cid, [])
            lbl = (msgs_s[0].get("title") or msgs_s[0]["content"][:20] + "...") if msgs_s else "Yeni Analiz"
            history_html += f"<button class='sb-chat-btn' onclick=\"goLoad('{cid}')\">💬 {lbl}</button>"

st.markdown(f"""
<div id="custom-sidebar">
    <h3 style="margin-bottom:5px;">⚖️ Siber Hukuk</h3>
    <p style="font-size:0.7rem; opacity:0.8; margin-bottom:20px;">Mezuniyet Projesi - 2026</p>
    <button class="sb-new-btn" onclick="goNew()">＋ Yeni Analiz</button>
    <hr style="opacity:0.2">
    <div style="overflow-y:auto; height:70vh;">{history_html}</div>
</div>

<script>
function goNew() {{ window.location.href = "?sb_action=new"; }}
function goLoad(cid) {{ window.location.href = "?sb_action=load&sb_cid=" + cid; }}
</script>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# ANA İÇERİK
# ─────────────────────────────────────────
pending = st.session_state.queued
if pending:
    st.session_state.queued = ""

if not st.session_state.messages and not pending:
    st.markdown("<h1 style='text-align:center;'>⚖️ Siber Hukuk Portalı</h1>", unsafe_allow_html=True)
    st.info("Dijital haklarınız veya siber suçlarla ilgili hukuki sorularınızı sorabilirsiniz.")
    
    # Örnek kartlar
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔒 KVKK İhlali Durumu"): st.session_state.queued = "Kişisel veri ihlali durumunda ne yapmalıyım?"; st.rerun()
    with c2:
        if st.button("💻 Siber Saldırı Analizi"): st.session_state.queued = "Sisteme izinsiz erişimin hukuki yaptırımları nelerdir?"; st.rerun()

# Geçmiş mesajları göster
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "⚖️"):
        st.markdown(msg["content"])

# Bekleyen (karttan gelen) mesajı işle
if pending:
    process_message(pending)

# ─────────────────────────────────────────
# CHAT INPUT
# ─────────────────────────────────────────
if user_input := st.chat_input("Hukuki sorunuzu yazın..."):
    process_message(user_input)
