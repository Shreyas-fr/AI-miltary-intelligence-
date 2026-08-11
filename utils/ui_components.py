import streamlit as st
import textwrap

def st_custom_kpi_card(title: str, value: str, subtitle: str = "", icon: str = "") -> None:
    """
    Renders a custom HTML/CSS glassmorphism KPI card.
    """
    html = textwrap.dedent(f"""
    <div class="custom-kpi-card">
        <div class="custom-kpi-title">
            {f'<span style="font-size: 1.1rem; margin-right: 4px;">{icon}</span>' if icon else ''} {title}
        </div>
        <div class="custom-kpi-value">{value}</div>
        {f'<div class="custom-kpi-subtitle">{subtitle}</div>' if subtitle else ''}
    </div>
    """)
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
    
    html = textwrap.dedent(f"""
    <div class="custom-threat-banner {css_class}">
        <div>
            <div class="threat-banner-label">Current Threat Level</div>
            <div class="threat-banner-value" style="font-size: 2rem;">{level.upper()}</div>
        </div>
        <div style="text-align: right;">
            <div class="threat-banner-label">Threat Score</div>
            <div class="threat-banner-value">{score}</div>
        </div>
    </div>
    """)
    st.markdown(html, unsafe_allow_html=True)
