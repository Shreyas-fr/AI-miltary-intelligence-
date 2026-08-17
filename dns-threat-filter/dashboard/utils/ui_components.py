"""
ui_components.py — DNS Threat Filter dashboard UI components.

Adapted from military-intel-platform/utils/ui_components.py style reference.
Not imported from that project — standalone copy with DNS-specific additions.
"""
import streamlit as st


def inject_global_css() -> None:
    """Inject dark-theme glassmorphism CSS matching military-intel-platform style."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #0a0f1e;
        color: #e2e8f0;
    }
    .stApp { background-color: #0a0f1e; }

    .kpi-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        backdrop-filter: blur(12px);
        margin-bottom: 0.5rem;
    }
    .kpi-title  { font-size: 0.75rem; color: #94a3b8; letter-spacing: 0.08em; text-transform: uppercase; }
    .kpi-value  { font-size: 2rem;    font-weight: 700; color: #f1f5f9; margin: 0.2rem 0; }
    .kpi-sub    { font-size: 0.8rem;  color: #64748b; }

    .verdict-blocked { color: #f87171; font-weight: 600; }
    .verdict-allow   { color: #4ade80; font-weight: 600; }
    .verdict-uncertain { color: #facc15; font-weight: 600; }

    .feed-badge {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.05em;
    }
    .badge-ok          { background: rgba(74,222,128,0.15); color: #4ade80; border: 1px solid #4ade80; }
    .badge-unavailable { background: rgba(248,113,113,0.15); color: #f87171; border: 1px solid #f87171; }
    .badge-hardcoded   { background: rgba(250,204,21,0.15);  color: #facc15; border: 1px solid #facc15; }
    </style>
    """, unsafe_allow_html=True)


def kpi_card(title: str, value: str, subtitle: str = "", icon: str = "") -> None:
    icon_html = f'<span style="margin-right:6px">{icon}</span>' if icon else ""
    sub_html  = f'<div class="kpi-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="kpi-card">'
        f'  <div class="kpi-title">{icon_html}{title}</div>'
        f'  <div class="kpi-value">{value}</div>'
        f'  {sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def urlhaus_feed_badge(status: str) -> None:
    """Render a coloured badge showing the live feed state."""
    if status == "OK":
        cls, label = "badge-ok", "URLhaus Live"
    elif status == "UNAVAILABLE":
        cls, label = "badge-unavailable", "URLhaus UNAVAILABLE"
    else:
        cls, label = "badge-hardcoded", f"Feed: {status}"
    st.markdown(
        f'<span class="feed-badge {cls}">{label}</span>',
        unsafe_allow_html=True,
    )
