import streamlit as st
from google import genai
import sqlite3
import hashlib
import time
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(
    page_title="VidhiDesk | Legal Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. THEME: OBSIDIAN & LIQUID GOLD ---
st.markdown("""
<style>
    /* IMPORTS */
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Inter:wght@300;400;600&display=swap');

    /* ANIMATIONS */
    @keyframes fadeInUp {
        from {opacity: 0; transform: translate3d(0, 20px, 0);}
        to {opacity: 1; transform: translate3d(0, 0, 0);}
    }

    /* GLOBAL RESET */
    .stApp {
        background-color: #000000;
        background-image: radial-gradient(circle at 50% 50%, #111 0%, #000 100%);
        color: #E0E0E0;
        font-family: 'Inter', sans-serif;
    }

    /* SIDEBAR */
    section[data-testid="stSidebar"] {
        background-color: #050505;
        border-right: 1px solid #222;
    }
    
    /* TITLE FIX - GUARANTEED NO QUANTIZING */
    .vidhi-title-container {
        width: 100%;
        text-align: center;
        padding-top: 5vh;
        padding-bottom: 2rem;
    }
    .vidhi-title {
        font-family: 'Cinzel', serif;
        font-weight: 700;
        /* Scales fluidly with screen width, never exceeds container */
        font-size: clamp(2.5rem, 6vw, 4.5rem); 
        margin: 0 auto;
        background: linear-gradient(135deg, #BF953F 0%, #FCF6BA 40%, #B38728 60%, #AA771C 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
        text-shadow: 0px 4px 20px rgba(212, 175, 55, 0.3);
        letter-spacing: 0.2em; /* Reduced spacing to prevent overflow */
        white-space: nowrap !important; /* Forces single line */
    }
    .vidhi-subtitle {
        color: #888;
        font-size: clamp(0.7rem, 1.5vw, 0.9rem);
        letter-spacing: 4px;
        text-transform: uppercase;
        margin-top: 10px;
    }
    .gold-divider {
        height: 1px;
        width: 150px;
        background: linear-gradient(90deg, transparent, #D4AF37, transparent);
        margin: 15px auto;
    }
    
    h1, h2, h3 { color: #D4AF37 !important; font-family: 'Cinzel', serif; }
    p, label, span, div { color: #B0B0B0; }

    /* BUTTONS - GOLD FOIL STYLE */
    .stButton > button {
        background: linear-gradient(145deg, #B8860B, #8A6E0B);
        color: #FFFFFF;
        font-family: 'Cinzel', serif;
        font-weight: 600;
        border: 1px solid #D4AF37;
        border-radius: 4px;
        padding: 0.7rem 2rem;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 2px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        width: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        background: linear-gradient(145deg, #D4AF37, #AA771C);
        box-shadow: 0 0 20px rgba(212, 175, 55, 0.5);
        border-color: #FFF;
        color: #FFF;
    }
    
    /* SECONDARY BUTTONS */
    button[kind="secondary"] {
        background: transparent !important;
        border: 1px solid #555 !important;
        color: #888 !important;
    }
    button[kind="secondary"]:hover {
        border-color: #D4AF37 !important;
        color: #D4AF37 !important;
    }

    /* INPUTS */
    .stTextInput > div > div > input, .stChatInput textarea {
        background: #080808;
        border: 1px solid #333;
        color: #FFF;
        border-radius: 4px;
        padding: 10px;
    }
    .stTextInput > div > div > input:focus, .stChatInput textarea:focus {
        border-color: #D4AF37;
        box-shadow: 0 0 10px rgba(212, 175, 55, 0.2);
    }

    /* CHAT BUBBLES */
    .stChatMessage {
        background-color: rgba(255,255,255,0.03);
        border: 1px solid #222;
        border-radius: 8px;
        animation: fadeInUp 0.4s ease-out;
    }
    .stChatMessage[data-testid="stChatMessageAvatar"] {
        background-color: #D4AF37;
        color: #000;
        border-radius: 50%;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE INIT ---
if "user" not in st.session_state: st.session_state.user = None
if "api_key" not in st.session_state: st.session_state.api_key = ""

INSTITUTIONS = sorted([
    "National Law School of India University (NLSIU), Bangalore", "NALSAR University of Law, Hyderabad",
    "National Law University, Delhi (NLUD)", "The West Bengal National University of Juridical Sciences (WBNUJS)",
    "National Law University, Jodhpur (NLUJ)", "Hidayatullah National Law University (HNLU), Raipur",
    "Gujarat National Law University (GNLU), Gandhinagar", "Dr. Ram Manohar Lohiya National Law University (RMLNLU)",
    "Rajiv Gandhi National University of Law (RGNUL), Patiala", "Chanakya National Law University (CNLU), Patna",
    "National University of Advanced Legal Studies (NUALS), Kochi", "National Law University Odisha (NLUO)",
    "Tamil Nadu National Law University (TNNLU)", "Maharashtra National Law University (MNLU), Mumbai",
    "Faculty of Law, University of Delhi (DU)", "Government Law College (GLC), Mumbai", 
    "Symbiosis Law School (SLS), Pune", "School of Law, Christ University", "Jindal Global Law School"
]) # Shortened purely for code brevity, feel free to paste the long list back here.

# --- 4. DATABASE MANAGER ---
class DBHandler:
    def __init__(self, db_name="vidhidesk_users.db"):
        self.db_name = db_name
        self.verify_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name, check_same_thread=False)

    def verify_db(self):
        try:
            conn = self.get_connection()
            conn.execute("SELECT 1 FROM users LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            self.create_schema()

    def create_schema(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, name TEXT, institution TEXT, year TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, role TEXT, content TEXT, timestamp DATETIME)''')
        c.execute('''CREATE TABLE IF NOT EXISTS spaces (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, category TEXT, query TEXT, response TEXT, timestamp DATETIME)''')
        conn.commit()
        conn.close()

    def login(self, email, password):
        conn = self.get_connection()
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        cur = conn.execute("SELECT name, institution, year FROM users WHERE email=? AND password=?", (email, hashed_pw))
        user = cur.fetchone()
        conn.close()
        if user:
            return {"email": email, "name": user[0], "institution": user[1], "year": user[2]}
        return None

    def save_message(self, email, role, content):
        conn = self.get_connection()
        conn.execute("INSERT INTO chats (email, role, content, timestamp) VALUES (?, ?, ?, ?)", 
                     (email, role, content, datetime.now()))
        conn.commit()
        conn.close()

    def get_history(self, email):
        conn = self.get_connection()
        cur = conn.execute("SELECT role, content FROM chats WHERE email=? ORDER BY id ASC", (email,))
        data = [{"role": row[0], "content": row[1]} for row in cur.fetchall()]
        conn.close()
        return data

    def clear_history(self, email):
        conn = self.get_connection()
        conn.execute("DELETE FROM chats WHERE email=?", (email,))
        conn.commit()
        conn.close()

    def save_to_space(self, email, category, query, response):
        conn = self.get_connection()
        conn.execute("INSERT INTO spaces (email, category, query, response, timestamp) VALUES (?, ?, ?, ?, ?)", 
                     (email, category, query, response, datetime.now()))
        conn.commit()
        conn.close()

    def get_space_items(self, email, category):
        conn = self.get_connection()
        cur = conn.execute("SELECT id, query, response, timestamp FROM spaces WHERE email=? AND category=? ORDER BY id DESC", (email, category))
        data = [{"id": r[0], "query": r[1], "response": r[2], "timestamp": r[3]} for r in cur.fetchall()]
        conn.close()
        return data

    def delete_space_item(self, item_id):
        conn = self.get_connection()
        conn.execute("DELETE FROM spaces WHERE id=?", (item_id,))
        conn.commit()
        conn.close()

db = DBHandler()

# --- 5. AI ENGINE (NEW SDK & SECURE KEY USAGE) ---
def get_gemini_response(query, tone, difficulty, institution, api_key):
    if not api_key:
        return "⚠️ **Access Error:** No API Key found. Please paste your Gemini API Key into the sidebar to activate VidhiDesk."

    try:
        # Utilizing the new google-genai library specification
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return f"❌ **System Config Error:** {str(e)}"
    
    sys_instruction = f"""
    ROLE: You are VidhiDesk, an elite legal research assistant for {institution}.
    TONE: {tone} | DEPTH: {difficulty}
    
    MANDATE:
    1. PRIORITIZE Indian Statutes: BNS (Bharatiya Nyaya Sanhita), BNSS, BSA, and Constitution.
    2. COMPARE with old acts (IPC/CrPC/Evidence Act) where relevant.
    3. CITE relevant Case Laws (Supreme Court/High Court) with year.
    4. FORMAT using Markdown: Use '### Headers', '**Bold**' for emphasis, and '>' for blockquotes.
    """

    # Exact models your environment proved it supports
    models_to_try = [
        'gemini-2.5-flash',
        'gemini-2.0-flash'
    ]
    
    last_error = ""
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=sys_instruction + "\n\nUSER QUERY: " + query
            )
            return response.text 
        except Exception as e:
            last_error = str(e)
            # If the key is invalid, stop hunting and tell the user immediately
            if "API_KEY_INVALID" in last_error or "not found" in last_error.lower():
                return f"❌ **Authentication Failed:** The API key you provided is invalid, expired, or was deactivated due to a leak."
            continue 

    return f"❌ **System Unavailable:** AI servers failed to respond. (Diagnostics: {last_error})"

# --- 6. UI LOGIC ---

def login_page():
    # 1. FULL WIDTH TITLE (Moved completely out of columns to fix quantizing)
    st.markdown("""
        <div class='vidhi-title-container'>
            <h1 class='vidhi-title'>VIDHIDESK</h1>
            <div class='gold-divider'></div>
            <div class='vidhi-subtitle'>Intelligent Legal Infrastructure</div>
        </div>
    """, unsafe_allow_html=True)
    
    # 2. LOGIN FORM 
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.container(border=True):
            st.markdown("<div style='padding: 10px;'>", unsafe_allow_html=True)
            email = st.text_input("IDENTITY TOKEN (EMAIL)", placeholder="gkrosh.0712@gmail.com")
            password = st.text_input("SECURITY KEY (PASSWORD)", type="password")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("INITIATE SESSION", use_container_width=True):
                with st.spinner("Authenticating credentials..."):
                    time.sleep(0.5) 
                    user = db.login(email, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Authentication Failed: Invalid token or key.")

def main_app():
    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/924/924915.png", width=50)
        st.markdown(f"### {st.session_state.user['name'].upper()}")
        st.markdown(f"<span style='color: #D4AF37; font-size: 0.8rem;'>{st.session_state.user['institution']}</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        nav = st.radio("SYSTEM MODULES", ["Research Core", "Knowledge Vault"], label_visibility="collapsed")
        
        st.markdown("---")
        
        # SECURE API KEY INPUT
        st.markdown("#### 🔑 System Access Key")
        api_input = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key, help="Paste your active Gemini API key here")
        if api_input != st.session_state.api_key:
            st.session_state.api_key = api_input
            st.rerun()

        # Status Indicator
        status_color = "#4CAF50" if st.session_state.api_key else "#FF5252"
        status_text = "System Online" if st.session_state.api_key else "Key Required"
        
        st.markdown(f"""
        <div style='border: 1px solid #222; padding: 12px; border-radius: 6px; background: #080808; margin-top:10px;'>
            <div style='display:flex; align-items:center; margin-bottom:5px;'>
                <span style='color: {status_color}; font-size: 1.2rem; margin-right: 8px;'>●</span> 
                <span style='color: #EEE; font-weight:600;'>{status_text}</span>
            </div>
            <div style='font-size: 0.7rem; color: #666;'>Engine: GenAI 2.5 Node</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("TERMINATE UPLINK"):
            st.session_state.user = None
            st.rerun()

    # --- RESEARCH CORE ---
    if nav == "Research Core":
        st.markdown("# RESEARCH CORE")
        st.markdown("<div style='height: 1px; width: 60px; background: #D4AF37; margin-bottom: 30px;'></div>", unsafe_allow_html=True)

        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            tone = c1.select_slider("OUTPUT TONE", ["Casual", "Professional", "Academic"], value="Academic")
            diff = c2.select_slider("ANALYSIS DEPTH", ["Summary", "Detailed", "Bare Act"], value="Detailed")
            space = c3.selectbox("AUTO-ARCHIVE TO", ["None", "Research", "Paper", "Study"])

        history = db.get_history(st.session_state.user['email'])
        for msg in history:
            avatar = "🧑‍⚖️" if msg['role'] == "user" else "⚖️"
            with st.chat_message(msg['role'], avatar=avatar):
                st.markdown(msg['content'])

        if query := st.chat_input("Input legal query, section, or case citation..."):
            with st.chat_message("user", avatar="🧑‍⚖️"):
                st.markdown(query)
            db.save_message(st.session_state.user['email'], "user", query)

            with st.chat_message("assistant", avatar="⚖️"):
                spinner_ph = st.empty()
                spinner_ph.markdown("""
                    <div style='display: flex; align-items: center; color: #D4AF37; padding: 10px;'>
                        <span style='margin-right: 12px; font-size: 1.2rem;'>⚡</span> 
                        <span style='font-family: Cinzel; font-weight: 600; letter-spacing: 1px;'>ANALYZING LEGAL CORPUS...</span>
                    </div>
                """, unsafe_allow_html=True)
                
                response = get_gemini_response(
                    query, tone, diff, 
                    st.session_state.user['institution'],
                    st.session_state.api_key
                )
                
                spinner_ph.empty()
                st.markdown(response)
                db.save_message(st.session_state.user['email'], "assistant", response)

                if space != "None" and "❌" not in response and "⚠️" not in response:
                    db.save_to_space(st.session_state.user['email'], space, query, response)
                    st.toast(f"Archived to {space}", icon="📂")

        if history:
            c1, c2 = st.columns([0.85, 0.15])
            with c2:
                if st.button("CLEAR LOGS", type="secondary"):
                    db.clear_history(st.session_state.user['email'])
                    st.rerun()

    # --- KNOWLEDGE VAULT ---
    elif nav == "Knowledge Vault":
        st.markdown("# KNOWLEDGE VAULT")
        st.markdown("<div style='height: 1px; width: 60px; background: #D4AF37; margin-bottom: 30px;'></div>", unsafe_allow_html=True)
        
        t1, t2, t3 = st.tabs(["📚 RESEARCH", "📝 PAPERS", "🎓 STUDY"])
        for tab, cat in zip([t1, t2, t3], ["Research", "Paper", "Study"]):
            with tab:
                items = db.get_space_items(st.session_state.user['email'], cat)
                if not items:
                    st.info(f"Sector '{cat}' is empty.", icon="ℹ️")
                else:
                    for item in items:
                        with st.expander(f"📌 {item['timestamp'][:16]} | {item['query'][:60]}..."):
                            st.markdown(item['response'])
                            if st.button("DELETE RECORD", key=f"del_{item['id']}"):
                                db.delete_space_item(item['id'])
                                st.rerun()

if __name__ == "__main__":
    if st.session_state.user:
        main_app()
    else:
        login_page()
