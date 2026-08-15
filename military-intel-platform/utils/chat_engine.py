"""
utils/chat_engine.py — AI Chat Assistant Engine
=================================================
Provides a conversational intelligence assistant powered by Google Gemini.
Falls back to template-based responses when the API key is unavailable.

Architecture
------------
1. System prompt establishes the AI as a senior intelligence analyst.
2. Context injection: current risk scores, live event summaries, and GTD
   statistics are prepended to each user query for grounded responses.
3. Conversation history is maintained in Streamlit session state.
4. Fallback mode uses keyword matching to provide useful template responses
   without requiring an API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

try:
    from google import genai
except ImportError:
    genai = None


SYSTEM_PROMPT = """You are a senior military intelligence analyst assistant.
You have access to the Global Terrorism Database (GTD) and live GDELT conflict
monitoring data. Your role is to help defense analysts understand threats,
compare countries, identify trends, and make informed decisions.

Guidelines:
- Be concise, professional, and data-driven.
- Use bullet points for clarity.
- Always cite whether information comes from historical GTD data or live feeds.
- Never provide operational targeting guidance.
- Include risk levels (Low/Medium/High/Critical) when relevant.
- If you don't have enough data, say so clearly.
"""


@dataclass
class ChatResponse:
    """A response from the chat engine."""
    content: str
    source: str  # "gemini" or "template"


def get_gemini_client(api_key: str | None = None):
    """Get a Gemini client if available."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key or genai is None:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None


def build_context(
    country_stats: dict | None = None,
    live_summary: str | None = None,
    risk_data: dict | None = None,
) -> str:
    """Build context string to inject into the conversation."""
    parts = []

    if country_stats:
        parts.append("=== GTD Historical Statistics ===")
        for key, value in country_stats.items():
            parts.append(f"- {key}: {value}")

    if risk_data:
        parts.append("\n=== Current Risk Assessment ===")
        for key, value in risk_data.items():
            parts.append(f"- {key}: {value}")

    if live_summary:
        parts.append(f"\n=== Live Intelligence Summary ===\n{live_summary}")

    return "\n".join(parts) if parts else ""


def chat_with_gemini(
    user_message: str,
    history: list[dict],
    context: str = "",
    api_key: str | None = None,
) -> ChatResponse:
    """Send a message to Gemini and return the response."""
    client = get_gemini_client(api_key)
    if client is None:
        return _template_response(user_message)

    # Build conversation contents
    contents = []

    # System instruction + context
    system_text = SYSTEM_PROMPT
    if context:
        system_text += f"\n\nCurrent Intelligence Context:\n{context}"

    # Add history
    for msg in history[-10:]:  # Keep last 10 messages for context window
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    # Add current message
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config={"system_instruction": system_text},
        )
        return ChatResponse(content=response.text, source="gemini")
    except Exception as exc:
        return ChatResponse(
            content=f"⚠️ Gemini API error: {exc}\n\nFalling back to template response.\n\n"
                    + _template_response(user_message).content,
            source="template",
        )


def _template_response(user_message: str) -> ChatResponse:
    """Provide keyword-based template responses when Gemini is unavailable."""
    msg_lower = user_message.lower()

    if any(w in msg_lower for w in ["highest risk", "most dangerous", "riskiest"]):
        return ChatResponse(
            content="Based on GTD historical data, the countries with the highest "
                    "incident counts include **Iraq**, **Afghanistan**, **Pakistan**, "
                    "**India**, and **Colombia**. Visit the **Country Analysis** page "
                    "to see detailed risk scores and the **AI Situation Report** page "
                    "for a comprehensive threat assessment of any country.",
            source="template",
        )

    if any(w in msg_lower for w in ["compare", "versus", "vs"]):
        return ChatResponse(
            content="To compare countries, visit the **Country Analysis** page and "
                    "select each country individually to view side-by-side statistics. "
                    "The **AI Situation Report** page can generate detailed briefs for "
                    "each country. For a Gemini-powered comparison, please provide an "
                    "API key in the sidebar.",
            source="template",
        )

    if any(w in msg_lower for w in ["today", "latest", "recent", "live"]):
        return ChatResponse(
            content="For the latest events, visit the **Live Intelligence Feed** page "
                    "which pulls real-time conflict data from GDELT. You can filter by "
                    "severity and time window. The **AI Situation Report** page also "
                    "integrates live intelligence with historical analysis.",
            source="template",
        )

    if any(w in msg_lower for w in ["forecast", "predict", "future"]):
        return ChatResponse(
            content="The **Hotspot Forecasting** page provides SARIMA-based predictions "
                    "for threat severity trends. The **Attack Prediction** page uses a "
                    "Random Forest classifier to predict likely attack types given "
                    "incident parameters. Visit these pages for detailed forecasts.",
            source="template",
        )

    if any(w in msg_lower for w in ["hotspot", "cluster", "concentration"]):
        return ChatResponse(
            content="The **Hotspot Detection** page uses DBSCAN clustering with "
                    "haversine distance to identify geographic threat concentrations. "
                    "You can adjust the cluster radius and minimum incident thresholds "
                    "in the sidebar. The **Global Threat Map** provides an interactive "
                    "hexbin density view.",
            source="template",
        )

    if any(w in msg_lower for w in ["help", "what can you", "capabilities"]):
        return ChatResponse(
            content="I can help you with:\n\n"
                    "- **Threat assessment**: \"What's the risk level for India?\"\n"
                    "- **Country comparison**: \"Compare Iraq and Syria\"\n"
                    "- **Live events**: \"What happened today?\"\n"
                    "- **Forecasting**: \"What's the forecast for the Middle East?\"\n"
                    "- **Hotspots**: \"Where are the current hotspots?\"\n"
                    "- **Similar events**: \"Find events similar to a bombing in Kabul\"\n\n"
                    "💡 For AI-powered responses, provide a Gemini API key in the sidebar.",
            source="template",
        )

    return ChatResponse(
        content="I can help you analyze global threats, compare countries, review "
                "live events, and explore forecasts. Try asking about a specific "
                "country, region, or threat type.\n\n"
                "💡 For enhanced AI-powered analysis, provide a Gemini API key "
                "in the sidebar.",
        source="template",
    )
