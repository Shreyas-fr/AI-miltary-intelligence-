import streamlit as st

def st_custom_kpi_card(title: str, value: str, subtitle: str = "", icon: str = "") -> None:
    """
    Renders a custom HTML/CSS glassmorphism KPI card.
    """
    icon_html = f'<span style="font-size: 1.1rem; margin-right: 4px;">{icon}</span>' if icon else ''
    subtitle_html = f'<div class="custom-kpi-subtitle">{subtitle}</div>' if subtitle else ''
    html = (
        f'<div class="custom-kpi-card">'
        f'<div class="custom-kpi-title">{icon_html} {title}</div>'
        f'<div class="custom-kpi-value">{value}</div>'
        f'{subtitle_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def st_custom_threat_banner(level: str, score: str) -> None:
    """
    Renders a specialized threat banner with dynamic color styling based on the level.
    Expects level to be one of: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'.
    """
    level_class_map = {
        "CRITICAL": "threat-critical",
        "HIGH": "threat-high",
        "MEDIUM": "threat-medium",
        "LOW": "threat-low",
        "ELEVATED": "threat-high", 
        "SEVERE": "threat-critical"
    }
    
    css_class = level_class_map.get(str(level).upper(), "threat-medium")
    
    html = (
        f'<div class="custom-threat-banner {css_class}">'
        f'<div>'
        f'<div class="threat-banner-label">Current Threat Level</div>'
        f'<div class="threat-banner-value" style="font-size: 2rem;">{level.upper()}</div>'
        f'</div>'
        f'<div style="text-align: right;">'
        f'<div class="threat-banner-label">Threat Score</div>'
        f'<div class="threat-banner-value">{score}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
