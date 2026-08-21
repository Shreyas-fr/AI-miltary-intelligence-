import os
# Fix for PyArrow mimalloc memory crashes on Apple Silicon (M-series Macs)
os.environ["ARROW_DEFAULT_MEMORY_POOL"] = "system"

try:
    from utils.dns_interceptor import init_dns_interceptor
    init_dns_interceptor()
except ImportError:
    pass

import streamlit as st

st.set_page_config(
    page_title="AI Military Intelligence",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded"
)

import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# Load CSS
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css("assets/style.css")

# --- Authentication Setup ---
# --- Authentication Setup ---
import logging

render_secret_path = '/etc/secrets/credentials.yaml'
local_path = 'credentials.yaml'

credentials_path = None
if os.path.exists(render_secret_path):
    credentials_path = render_secret_path
elif os.path.exists(local_path):
    credentials_path = local_path

if not credentials_path:
    st.error("🔒 **Configuration Error:** `credentials.yaml` not found in `/etc/secrets/` or local directory.")
    st.warning("Ensure credentials are provided via Render Secret Files or local file.")
    st.stop()

print(f"✅ Successfully loaded credentials from: {credentials_path}")

try:
    with open(credentials_path) as file:
        config = yaml.load(file, Loader=SafeLoader)
except Exception as e:
    st.error(f"🔒 **Failed to parse credentials file:** {str(e)}")
    st.stop()

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# ---------------------------------------------------------------------------
# Brute-force lockout — check BEFORE rendering the login widget
# ---------------------------------------------------------------------------
import streamlit.components.v1 as components

def _get_failed_attempts(username: str) -> int:
    try:
        return config['credentials']['usernames'].get(username, {}).get('failed_login_attempts', 0)
    except Exception:
        return 0

# Check all known users — if the currently-attempted username is locked, block early
_attempted_username = st.session_state.get("username")
if _attempted_username:
    _fails = _get_failed_attempts(_attempted_username)
    if _fails >= 5:
        st.error("🔒 **Account Locked:** Too many failed login attempts. Contact your administrator.")
        st.stop()

# Render login widget
authenticator.login(location="main")

auth_status = st.session_state.get("authentication_status")

if auth_status:
    authenticator.logout(location="sidebar")
    st.sidebar.markdown(f"**User:** {st.session_state.get('name', 'Unknown')}")
    
    roles = st.session_state.get("roles")
    role_display = roles[0] if roles and isinstance(roles, list) else "Viewer"
    st.sidebar.markdown(f"**Role:** {role_display}")
    
elif auth_status is False:
    st.error('Username/password is incorrect')
    st.stop()
elif auth_status is None:
    st.warning('Please enter your username and password')
    st.stop()

import pyotp
import qrcode
import io

if auth_status:
    username = st.session_state["username"]
    user_cred = config['credentials']['usernames'][username]
    
    if not st.session_state.get("mfa_verified", False):
        st.markdown("## 🔐 Multi-Factor Authentication")
        
        if "mfa_secret" not in user_cred:
            st.info("First-time setup: Enroll your device for MFA.")
            if "temp_mfa_secret" not in st.session_state:
                st.session_state["temp_mfa_secret"] = pyotp.random_base32()
                
            secret = st.session_state["temp_mfa_secret"]
            totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_cred['email'], issuer_name="AI Military Intelligence")
            
            img = qrcode.make(totp_uri)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption="Scan with Authenticator", width=200)
            
            st.code(secret, language=None)
            
            code = st.text_input("Enter 6-digit code to verify:", key="enroll_code")
            if st.button("Verify & Enroll"):
                totp = pyotp.TOTP(secret)
                if totp.verify(code):
                    user_cred["mfa_secret"] = secret
                    with open(credentials_path, 'w') as file:
                        yaml.dump(config, file, default_flow_style=False)
                    st.session_state["mfa_verified"] = True
                    st.success("MFA Setup Complete!")
                    st.rerun()
                else:
                    st.error("Invalid code.")
            st.stop()
        else:
            secret = user_cred["mfa_secret"]
            code = st.text_input("Enter 6-digit MFA code:", key="login_code")
            if st.button("Verify"):
                totp = pyotp.TOTP(secret)
                if totp.verify(code):
                    st.session_state["mfa_verified"] = True
                    st.rerun()
                else:
                    st.error("Invalid code.")
            st.stop()

    # Check for DNS Threat Filter Blocks (Global UI Notification)
    if "dns_blocks" in st.session_state and st.session_state["dns_blocks"]:
        for domain in st.session_state["dns_blocks"]:
            st.toast(f"Threat Filter Blocked: {domain}", icon="🛑")
        st.session_state["dns_blocks"].clear()

    # -----------------------------------------------------------------------
    # Security JS — injected once per authenticated session
    # Watermark, blur on focus loss, disable right-click and print shortcuts
    # -----------------------------------------------------------------------
    _username = st.session_state.get("username", "Unknown")
    _roles = st.session_state.get("roles", [])
    _role_display = _roles[0] if _roles and isinstance(_roles, list) else "Viewer"
    _wm_text = f"{_username} \u2022 {_role_display} \u2022 CLASSIFIED"

    components.html(f"""
    <script>
    (function() {{
      // --- Watermark overlay ---
      var existing = document.getElementById('mil-watermark');
      if (!existing) {{
        var wm = document.createElement('div');
        wm.id = 'mil-watermark';
        wm.setAttribute('style', [
          'position:fixed', 'top:0', 'left:0', 'width:100vw', 'height:100vh',
          'pointer-events:none', 'z-index:99999', 'overflow:hidden',
          'opacity:0.07', 'font-size:18px', 'color:#00E5FF',
          'font-family:monospace', 'font-weight:600', 'white-space:nowrap',
          'display:flex', 'flex-wrap:wrap', 'align-items:flex-start',
          'transform:rotate(-25deg) scale(1.6)', 'transform-origin:center center',
        ].join(';'));
        var count = 80;
        for (var i = 0; i < count; i++) {{
          var span = document.createElement('span');
          span.textContent = '{_wm_text}   ';
          span.style.marginRight = '4rem';
          wm.appendChild(span);
          if (i % 5 === 4) {{ var br = document.createElement('br'); wm.appendChild(br); }}
        }}
        document.body.appendChild(wm);
      }}

      // --- Blur on window focus loss ---
      var appEl = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
      function applyBlur() {{
        if (appEl) appEl.style.filter = 'blur(12px)';
      }}
      function removeBlur() {{
        if (appEl) appEl.style.filter = '';
      }}
      window.parent.addEventListener('blur', applyBlur);
      window.parent.document.addEventListener('visibilitychange', function() {{
        if (window.parent.document.hidden) applyBlur(); else removeBlur();
      }});

      // --- Disable right-click ---
      window.parent.document.addEventListener('contextmenu', function(e) {{
        e.preventDefault();
      }}, true);

      // --- Disable print and save shortcuts ---
      window.parent.document.addEventListener('keydown', function(e) {{
        var key = e.key.toLowerCase();
        if ((e.ctrlKey || e.metaKey) && (key === 'p' || key === 's')) {{
          e.preventDefault();
        }}
        if (key === 'printscreen') {{
          e.preventDefault();
        }}
      }}, true);
    }})();
    </script>
    """, height=0)

# --- Main Application (Only visible if authenticated) ---

# Hero Section
st.markdown("<h1>🛡️ AI Military Intelligence Command Center</h1>", unsafe_allow_html=True)
st.markdown("##### Advanced tactical risk scoring, spatial hotspot forecasting, and AI situation reporting")

st.markdown("""
<div class="module-card">
    <div style="font-size: 1.1rem; color: #E2E8F0; line-height: 1.6;">
        Welcome to the <strong>Predictive Tactical Intelligence Platform</strong>.
        This system combines historical incident analytics (GTD), spatial DBSCAN clustering,
        SARIMA time-series forecasting, live public-source intelligence monitoring (GDELT),
        and non-linear Threat Severity Index (TSI) scoring for assisted command decisions.
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)

# Module Grid
st.markdown("### Platform modules")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🌍</div>
        <div class="module-title">Global Threat & Hotspots</div>
        <div class="module-desc">Geospatial incident maps and DBSCAN clustering with Haversine distance and migration vectors.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🤖</div>
        <div class="module-title">Predictive ML Models</div>
        <div class="module-desc">Random Forest classifiers to predict tactical attack types and classify threat levels.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🔔</div>
        <div class="module-title">Intelligence Alerts</div>
        <div class="module-desc">Threshold-based surveillance rules for real-time risk score and activity surge spikes.</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="module-card">
        <div class="module-icon">📈</div>
        <div class="module-title">Time-Series Forecasting</div>
        <div class="module-desc">AIC-optimized SARIMA forecasting with held-out validation against linear baseline models.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🛰️</div>
        <div class="module-title">Live Public Signals</div>
        <div class="module-desc">Real-time GDELT news metadata integration for event detection and risk trend tracking.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">📋</div>
        <div class="module-title">Resource Recommendation</div>
        <div class="module-desc">AI-driven operational response suggestions and tactical force posture guidelines.</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🧠</div>
        <div class="module-title">AI Situation Briefings</div>
        <div class="module-desc">Composite 0–100 risk breakdowns, risk driver metrics, and executive situation reports.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">📊</div>
        <div class="module-title">Data Explorer</div>
        <div class="module-desc">Interactive DuckDB SQL query engine over multi-year incident data with instant CSV export.</div>
    </div>
    """, unsafe_allow_html=True)



    st.markdown("""
    <div class="module-card">
        <div class="module-icon">⛅</div>
        <div class="module-title">Weather Intelligence</div>
        <div class="module-desc">OpenWeather conditions and operational impact assessment for reconnaissance and flight planning.</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🌎</div>
        <div class="module-title">Country Intelligence</div>
        <div class="module-desc">Deep-dive country profiles combining GTD statistics, live news, and risk breakdown.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🚨</div>
        <div class="module-title">AI Threat Scoring</div>
        <div class="module-desc">Non-linear Threat Severity Index (TSI) scoring for real-time incident severity estimation.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🎖️</div>
        <div class="module-title">Mission Planning</div>
        <div class="module-desc">Location-based threat radius simulator for tactical operational preparation.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🏗️</div>
        <div class="module-title">Military Asset Layer</div>
        <div class="module-desc">Simulated airbase, naval, and radar installation overlays with threat proximity buffers.</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)
st.caption("👈 Use the left sidebar navigation menu to select a module and begin analysis.")
