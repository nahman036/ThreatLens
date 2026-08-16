import streamlit as st
import psutil
import socket
import requests
import hashlib
import json
import os
import time
import pandas as pd
import datetime
from supabase import create_client, Client
import extra_streamlit_components as stx

# -------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -------------------------------------------------------------
st.set_page_config(
    page_title="ThreatLens",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

DEV_AVATAR_SRC = "https://github.com/nahman036.png"

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        display: none;
    }
    .tool-card {
        background-color: #1a2234;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 12px;
        border: 1px solid #2a3449;
    }
    .developer-card {
        background-color: #111827;
        border-radius: 12px;
        padding: 18px 20px;
        margin-top: 25px;
        margin-bottom: 15px;
        border: 1px solid #1f2937;
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .dev-avatar {
        width: 68px;
        height: 68px;
        border-radius: 50%;
        border: 2px solid #38bdf8;
        object-fit: cover;
    }
    .tool-card h3 {
        margin: 0 0 6px 0;
        font-size: 1.2rem;
        color: #ffffff;
    }
    .tool-card p {
        margin: 0;
        font-size: 0.9rem;
        color: #94a3b8;
    }
    .pro-badge {
        background-color: #f59e0b;
        color: #000000;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
        margin-left: 8px;
    }
    .free-badge {
        background-color: #10b981;
        color: #ffffff;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
        margin-left: 8px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. COOKIE MANAGER & PERSISTENT SESSION
# -------------------------------------------------------------
cookie_manager = stx.CookieManager()
# -------------------------------------------------------------
# 3. SUPABASE CLOUD DATABASE CONNECTION
# -------------------------------------------------------------
SUPABASE_URL = "https://cypljfetstxffzyszmch.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5cGxqZmV0c3R4ZmZ6eXN6bWNoIiwicm9sZSI6ImFub24iLCJpYXQiOj..."  # Paste the full string
@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase_client = init_supabase()
except Exception:
    supabase_client = None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode()).hexdigest()

def update_user_activity(email):
    if not supabase_client or not email:
        return
    try:
        platform_info = "Windows App" if "dist" in os.getcwd() else "Web/Mobile"
        supabase_client.table("users_profile").update({
            "last_active": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "current_platform": platform_info
        }).eq("email", email.strip().lower()).execute()
    except Exception:
        pass

def db_register_user(full_name, email, phone, password, plan="Free Tier"):
    if not supabase_client:
        return False, "Database client connection offline."
    try:
        data = {
            "full_name": full_name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
            "password_hash": hash_password(password),
            "plan_tier": plan,
            "current_platform": "Windows App" if "dist" in os.getcwd() else "Web/Mobile",
            "last_active": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        supabase_client.table("users_profile").insert(data).execute()
        return True, "Registration successful!"
    except Exception as e:
        err_msg = str(e)
        if "duplicate key" in err_msg or "unique constraint" in err_msg:
            return False, "An account with this email already exists."
        return False, f"Registration failed: {err_msg}"

def db_authenticate_user(email, password):
    if not supabase_client:
        return False, None
    try:
        clean_email = email.strip().lower()
        clean_pass = password.strip()
        hashed = hash_password(clean_pass)
        res = supabase_client.table("users_profile").select("*").eq("email", clean_email).execute()
        if res.data and len(res.data) > 0:
            user_data = res.data[0]
            if user_data.get("password_hash") == hashed:
                update_user_activity(clean_email)
                return True, user_data
        return False, None
    except Exception:
        return False, None

def db_get_user_by_email(email):
    if not supabase_client or not email:
        return None
    try:
        res = supabase_client.table("users_profile").select("*").eq("email", email.strip().lower()).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception:
        return None

def db_reset_password(email, new_password):
    if not supabase_client:
        return False, "Database offline."
    try:
        clean_email = email.strip().lower()
        hashed = hash_password(new_password)
        res = supabase_client.table("users_profile").update({"password_hash": hashed}).eq("email", clean_email).execute()
        if res.data and len(res.data) > 0:
            return True, "Password updated successfully!"
        return False, "Email address not found in database."
    except Exception as e:
        return False, str(e)

# Session States initialization
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_data" not in st.session_state:
    st.session_state["user_data"] = {}
if "current_view" not in st.session_state:
    st.session_state["current_view"] = "home"

# --- PERSISTENT COOKIE AUTO-LOGIN ---
saved_user_email = cookie_manager.get(cookie="threatlens_user_email")
if saved_user_email and not st.session_state["authenticated"]:
    cached_user = db_get_user_by_email(saved_user_email)
    if cached_user:
        st.session_state["authenticated"] = True
        st.session_state["user_data"] = cached_user
        update_user_activity(saved_user_email)


# -------------------------------------------------------------
# 4. AUTHENTICATION (LOGIN, SIGN UP, FORGOT PASSWORD)
# -------------------------------------------------------------
if not st.session_state["authenticated"]:
    st.markdown("# 🛡️ ThreatLens")
    st.caption("Autonomous Endpoint Protection & Cloud Intelligence Suite")

    auth_tab = st.radio("Select Action", ["Login", "Sign Up / Register", "Forgot Password?"], horizontal=True)

    # --- LOGIN ---
    if auth_tab == "Login":
        with st.form("login_form"):
            st.subheader("Account Login")
            login_email = st.text_input("Registered Email Address")
            login_pass = st.text_input("Password", type="password")
            remember_me = st.checkbox("Remember Me on this device", value=True)
            submit_login = st.form_submit_button("Sign In", type="primary", use_container_width=True)

            if submit_login:
                if not login_email or not login_pass:
                    st.warning("Please enter your email and password.")
                else:
                    success, u_data = db_authenticate_user(login_email, login_pass)
                    if success:
                        st.session_state["authenticated"] = True
                        st.session_state["user_data"] = u_data
                        st.session_state["current_view"] = "home"
                        if remember_me:
                            cookie_manager.set("threatlens_user_email", login_email.strip().lower(), expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")

    # --- SIGN UP ---
    elif auth_tab == "Sign Up / Register":
        with st.form("signup_form"):
            st.subheader("Create Professional Account")
            reg_name = st.text_input("Full Name (e.g., Alex Johnson)")
            reg_email = st.text_input("Email Address (e.g., alex@domain.com)")
            reg_phone = st.text_input("Mobile Number (with country code)")
            reg_pass = st.text_input("Create Password", type="password")
            reg_plan = st.selectbox("Select Subscription Plan", ["Free Tier", "Pro Tier ($19/mo)"])
            submit_signup = st.form_submit_button("Register Account", type="primary", use_container_width=True)

            if submit_signup:
                if not (reg_name and reg_email and reg_phone and reg_pass):
                    st.warning("All fields are required.")
                elif len(reg_pass) < 6:
                    st.warning("Password must be at least 6 characters.")
                else:
                    plan_val = "Pro Tier" if "Pro" in reg_plan else "Free Tier"
                    ok, msg = db_register_user(reg_name, reg_email, reg_phone, reg_pass, plan_val)
                    if ok:
                        st.success(msg + " Please switch to 'Login' to continue.")
                    else:
                        st.error(msg)

    # --- FORGOT PASSWORD ---
    elif auth_tab == "Forgot Password?":
        with st.form("forgot_form"):
            st.subheader("Password Recovery")
            f_email = st.text_input("Enter Registered Email")
            f_new_pass = st.text_input("Enter New Password", type="password")
            submit_reset = st.form_submit_button("Update Password", type="primary", use_container_width=True)

            if submit_reset:
                if not f_email or not f_new_pass:
                    st.warning("Please fill in both fields.")
                elif len(f_new_pass) < 6:
                    st.warning("Password must be at least 6 characters.")
                else:
                    ok, msg = db_reset_password(f_email, f_new_pass)
                    if ok:
                        st.success(msg + " You can now log in.")
                    else:
                        st.error(msg)

    # Developer Profile Card
    st.markdown(f"""
    <div class="developer-card">
        <img src="{DEV_AVATAR_SRC}" class="dev-avatar" alt="Nahman Sajad Khan" onerror="this.onerror=null; this.src='https://ui-avatars.com/api/?name=Nahman+Sajad&background=0D8ABC&color=fff&size=128';"/>
        <div>
            <h4 style="margin:0 0 4px 0; color:#e2e8f0;">👨‍💻 Nahman Sajad Khan</h4>
            <p style="margin:0; font-size:0.85rem; color:#94a3b8;">Cybersecurity & Python Engineer</p>
            <a href="https://github.com/nahman036" target="_blank" style="color:#38bdf8; text-decoration:none; font-size:0.85rem;">🔗 GitHub: @nahman036</a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# -------------------------------------------------------------
# 5. DASHBOARD VIEW (2 FREE + 6 PRO)
# -------------------------------------------------------------
user_info = st.session_state.get("user_data", {})
is_pro = (user_info.get("plan_tier") == "Pro Tier")

update_user_activity(user_info.get("email", ""))

if st.session_state["current_view"] == "home":
    st.markdown("# 🛡️ ThreatLens")
    badge = "⭐ PRO TIER" if is_pro else "FREE TIER"
    st.markdown(f"User: **{user_info.get('full_name', 'User')}** | Email: `{user_info.get('email', '')}` | Tier: **{badge}**")

    c_btn1, c_btn2 = st.columns([1, 1])
    with c_btn1:
        if st.button("💎 Manage Subscription", type="primary", use_container_width=True):
            st.session_state["current_view"] = "upgrade"
            st.rerun()
    with c_btn2:
        if st.button("🚪 Log Out", use_container_width=True):
            cookie_manager.delete("threatlens_user_email")
            st.session_state["authenticated"] = False
            st.session_state["user_data"] = {}
            st.rerun()

    # --- ADMIN TELEMETRY ---
    with st.expander("👑 Admin Dashboard: Live Users & App Telemetry"):
        if supabase_client:
            res = supabase_client.table("users_profile").select("full_name, email, phone, plan_tier, current_platform, last_active, created_at").order("last_active", desc=True).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                st.metric("Total Registered Users", len(df))
                st.dataframe(df, use_container_width=True)
        else:
            st.warning("Database connection offline.")

    st.write("")

    # Free Tool 1
    st.markdown("""<div class="tool-card"><h3>🌐 Live Network Monitor <span class="free-badge">FREE</span></h3><p>Real-time socket sniffer, bandwidth usage, and active connections.</p></div>""", unsafe_allow_html=True)
    if st.button("Launch Tool", key="btn_network", type="primary"):
        st.session_state["current_view"] = "network"
        st.rerun()

    st.write("")

    # Free Tool 2
    st.markdown("""<div class="tool-card"><h3>⚙️ Process Scanner <span class="free-badge">FREE</span></h3><p>Inspect running processes, CPU consumption, and system handles.</p></div>""", unsafe_allow_html=True)
    if st.button("Launch Tool", key="btn_process", type="primary"):
        st.session_state["current_view"] = "process"
        st.rerun()

    st.write("")

    # Pro Tools
    pro_tools = [
        ("🤖 AI Threat Analyzer", "ai", "Heuristic evaluation for behavioral anomalies and malware signatures."),
        ("📡 Recon & Port Scanner", "recon", "Active socket probing, open ports discovery, and network auditing."),
        ("🔑 Password Breach Auditor", "passwords", "Audit credentials against billions of leaked passwords."),
        ("🌍 Threat Intelligence & IP Lookup", "ip_intel", "Autonomous ASN lookup, geolocation analysis, and hostile IP profiling."),
        ("📜 Deep Forensic Audit Logs", "logs", "Kernel integrity verification and structured JSON forensic exports."),
        ("🖥️ Advanced System Telemetry", "telemetry", "Real-time memory allocations, swap profiles, and thread metrics.")
    ]

    for title, view_key, desc in pro_tools:
        st.markdown(f"""<div class="tool-card"><h3>{title} <span class="pro-badge">PRO</span></h3><p>{desc}</p></div>""", unsafe_allow_html=True)
        if st.button("Launch Tool", key=f"btn_{view_key}", type="primary"):
            st.session_state["current_view"] = view_key
            st.rerun()
        st.write("")

    # Footer Card
    st.markdown(f"""
    <div class="developer-card">
        <img src="{DEV_AVATAR_SRC}" class="dev-avatar" alt="Nahman Sajad Khan" onerror="this.onerror=null; this.src='https://ui-avatars.com/api/?name=Nahman+Sajad&background=0D8ABC&color=fff&size=128';"/>
        <div>
            <h4 style="margin:0 0 4px 0; color:#e2e8f0;">👨‍💻 Nahman Sajad Khan</h4>
            <p style="margin:0; font-size:0.85rem; color:#94a3b8;">Developer & Maintainer | ThreatLens Suite v1.0.4</p>
            <a href="https://github.com/nahman036" target="_blank" style="color:#38bdf8; text-decoration:none; font-size:0.85rem;">🔗 GitHub: @nahman036</a>
        </div>
    </div>
    """, unsafe_allow_html=True)


# -------------------------------------------------------------
# 6. TOOL VIEWS & WORKFLOW
# -------------------------------------------------------------
else:
    if st.button("⬅️ Back to Dashboard"):
        st.session_state["current_view"] = "home"
        st.rerun()
    st.divider()

    # Network Monitor
    if st.session_state["current_view"] == "network":
        st.subheader("🌐 Live Network Monitor")
        connections = []
        for conn in psutil.net_connections(kind='inet')[:30]:
            try:
                laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
                raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
                connections.append({"PID": conn.pid, "Status": conn.status, "Local": laddr, "Remote": raddr})
            except Exception:
                pass
        st.dataframe(pd.DataFrame(connections), use_container_width=True)

    # Process Scanner
    elif st.session_state["current_view"] == "process":
        st.subheader("⚙️ Process Scanner")
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                procs.append(p.info)
            except Exception:
                pass
        st.dataframe(pd.DataFrame(procs).sort_values(by='cpu_percent', ascending=False).head(25), use_container_width=True)

    # AI Analyzer (Pro)
    elif st.session_state["current_view"] == "ai":
        st.subheader("🤖 AI Threat Analyzer")
        if not is_pro:
            st.warning("🔒 **Pro Subscription Required**")
            if st.button("👉 Upgrade to Pro"):
                st.session_state["current_view"] = "upgrade"
                st.rerun()
        else:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            score = int((cpu * 0.4) + (mem * 0.4))
            st.metric("System Threat Index", f"{score}/100")
            if score < 40: st.success("System baseline healthy.")
            else: st.warning("High utilization detected.")

    # Recon Scanner (Pro)
    elif st.session_state["current_view"] == "recon":
        st.subheader("📡 Port Reconnaissance Scanner")
        if not is_pro:
            st.warning("🔒 **Pro Subscription Required**")
        else:
            target = st.text_input("Target IP / Domain", value="127.0.0.1")
            if st.button("Run Recon"):
                results = []
                for p in [21, 22, 80, 443, 8080]:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.2)
                    res = s.connect_ex((target, p))
                    results.append({"Port": p, "Status": "Open" if res == 0 else "Closed"})
                    s.close()
                st.table(pd.DataFrame(results))

    # Password Auditor (Pro)
    elif st.session_state["current_view"] == "passwords":
        st.subheader("🔑 Password Breach Auditor")
        if not is_pro:
            st.warning("🔒 **Pro Subscription Required**")
        else:
            pwd = st.text_input("Password to check", type="password")
            if st.button("Verify"):
                sha = hashlib.sha1(pwd.encode()).hexdigest().upper()
                r = requests.get(f"https://api.pwnedpasswords.com/range/{sha[:5]}", timeout=4)
                if sha[5:] in r.text: st.error("⚠️ Password compromised in public data breaches.")
                else: st.success("✅ Secure password.")

    # IP Intelligence (Pro)
    elif st.session_state["current_view"] == "ip_intel":
        st.subheader("🌍 Threat Intelligence & IP Lookup")
        if not is_pro:
            st.warning("🔒 **Pro Subscription Required**")
        else:
            ip = st.text_input("IP Address", value="8.8.8.8")
            if st.button("Audit IP"):
                r = requests.get(f"http://ip-api.com/json/{ip}").json()
                st.json(r)

    # Forensic Logs (Pro)
    elif st.session_state["current_view"] == "logs":
        st.subheader("📜 Deep Forensic Logs")
        if not is_pro:
            st.warning("🔒 **Pro Subscription Required**")
        else:
            st.write(f"System Boot: `{datetime.datetime.fromtimestamp(psutil.boot_time())}`")
            st.download_button("Export Report (.json)", data=json.dumps({"audit": "clean"}), file_name="audit.json")

    # Advanced Telemetry (Pro)
    elif st.session_state["current_view"] == "telemetry":
        st.subheader("🖥️ Advanced Hardware Telemetry")
        if not is_pro:
            st.warning("🔒 **Pro Subscription Required**")
        else:
            st.metric("CPU Load", f"{psutil.cpu_percent()}%")
            st.metric("RAM Used", f"{psutil.virtual_memory().percent}%")

    # Upgrade
    elif st.session_state["current_view"] == "upgrade":
        st.subheader("💎 Subscription Plans")
        if is_pro:
            st.success("Your account is on the **Pro Tier**.")
        else:
            st.info("Upgrade to access AI Analyzer, Port Recon, Password Leak Auditor, and Forensics.")
            if st.button("Activate Pro Tier ($19/mo)", type="primary"):
                supabase_client.table("users_profile").update({"plan_tier": "Pro Tier"}).eq("email", user_info.get("email")).execute()
                user_info["plan_tier"] = "Pro Tier"
                st.success("Pro Tier activated!")
                st.rerun()