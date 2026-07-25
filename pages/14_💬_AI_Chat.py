import os
import streamlit as st
from utils.chat_engine import build_context, chat_with_gemini
from utils.data_loader import query_data

# Page configuration
st.set_page_config(
    page_title="AI Chat Assistant",
    page_icon="💬",
    layout="wide"
)

# Load CSS
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

# Title & Subtitle
st.title("💬 AI Intelligence Assistant")
st.markdown("##### Ask questions about global threats, country risks, and intelligence data")

st.markdown('<div style="margin-top:0.75rem"></div>', unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration")
api_key = st.sidebar.text_input(
    "Gemini API Key",
    value=os.environ.get("GEMINI_API_KEY", ""),
    type="password",
    help="Enter your Google Gemini API Key. If left empty, template response mode will be used."
)

st.sidebar.markdown("---")
st.sidebar.header("ℹ️ Model Info")
if api_key:
    st.sidebar.success("Status: Gemini API Active")
    st.sidebar.markdown("- **Engine:** Google Gemini")
    st.sidebar.markdown("- **Model:** `gemini-2.5-flash`")
else:
    st.sidebar.info("Status: Template Engine Active")
    st.sidebar.markdown("- **Engine:** Keyword Template Fallback")
    st.sidebar.markdown("- **Model:** Internal Rule Assistant")

st.sidebar.markdown("- **Context:** GTD Threat Intelligence Stats")

# Initialize Chat History
st.session_state.setdefault("chat_history", [])

# Clear Chat History Button
st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Clear Chat History", width="stretch"):
    st.session_state.chat_history = []
    st.rerun()

# Build GTD Statistics Context
stats = query_data(
    "SELECT COUNT(*) as total, COUNT(DISTINCT country_txt) as countries, SUM(nkill) as fatalities FROM 'data/globalterrorism.csv'"
).iloc[0]

context = build_context(
    country_stats={
        "Total Incidents": f"{int(stats['total']):,}",
        "Countries": int(stats["countries"]),
        "Total Fatalities": f"{int(stats['fatalities'] or 0):,}",
    }
)

# Display Existing Chat History
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            source = message.get("source", "template")
            if source == "gemini":
                st.caption("🟢 **Source:** Gemini AI (`gemini-2.5-flash`)")
            else:
                st.caption("🟡 **Source:** Template Engine")

# Sample Prompts if Chat History is empty
if not st.session_state.chat_history:
    st.info("💡 **Sample Questions You Can Ask:**\n"
            "- *Which countries have the highest threat level based on GTD data?*\n"
            "- *Compare historical terrorism trends in Iraq vs Afghanistan.*\n"
            "- *Where are current regional conflict hotspots?*\n"
            "- *What forecasting capabilities are available in this system?*")

# Chat Input & Interaction Handling
if user_input := st.chat_input("Ask about global threats, country risks, or intelligence data..."):
    # Append user message
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    # Get AI / Template response
    response = chat_with_gemini(
        user_message=user_input,
        history=st.session_state.chat_history,
        context=context,
        api_key=api_key
    )
    
    # Append assistant response
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": response.content,
        "source": response.source
    })
    
    # Rerun to refresh chat display
    st.rerun()
