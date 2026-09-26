import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from core.database import get_database
from core.settings import settings
from core.whatsapp_utils import send_whatsapp_message

logger = logging.getLogger(__name__)

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.3,
    groq_api_key=settings.GROQ_API_KEY
)


async def draft_personalized_pitch(
    lead: Dict[str, Any],
    founder_name: str = "Seyaff"
) -> Dict[str, str]:
    """Generates a hyper-personalized multi-channel pitch for a targeted lead."""
    company = lead.get("company_name", "your business")
    fit_reason = lead.get("fit_reason", "increasing customer response speed and orders")
    pitch_angle = lead.get("recommended_pitch_angle", "autonomous 24/7 WhatsApp ordering")

    system_prompt = (
        "You are an elite B2B sales copywriter specializing in high-converting cold outreach. "
        "Your pitches are punchy, respectful, authentic, and zero-fluff. "
        "Product: An Autonomous 24/7 WhatsApp AI Customer Support & Order Management Agent with live dashboard sync."
    )

    human_prompt = f"""Target Business: {company}
Identified Bottleneck/Opportunity: {fit_reason}
Recommended Pitch Hook: {pitch_angle}
Founder Name: {founder_name}

Generate two outreach variations:
1. Cold Email (Subject line under 6 words + body under 90 words with single low-friction CTA: asking if open to a 2-min demo video).
2. Cold WhatsApp Message (Friendly, casual, under 60 words, referencing their business directly).

Output strictly valid JSON with keys:
- "email_subject": string
- "email_body": string
- "whatsapp_message": string
"""

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])

    clean = response.content.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]

    try:
        return json.loads(clean)
    except Exception as e:
        logger.error(f"Error parsing pitch JSON: {e}")
        return {
            "email_subject": f"Quick question regarding {company}",
            "email_body": f"Hi {company} team,\n\nNoticed your high customer volume. We built an autonomous WhatsApp AI agent that handles orders, inquiries, and menus 24/7 on autopilot.\n\nOpen to a 2-minute video showing how it works?\n\nBest,\n{founder_name}",
            "whatsapp_message": f"Hey {company} team! Came across your work and loved what you're doing. We built an AI WhatsApp agent that manages customer orders and inquiries 24/7 without manual staff. Would love to send a quick 60-second preview if you're open to it!"
        }


async def process_inbound_lead_reply(
    sender_identifier: str,
    reply_message: str,
    founder_whatsapp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Autonomous Reply Listener & Objection Handler:
    1. Analyzes the lead's reply for sentiment, interest, and intent.
    2. Generates an intelligent, tailored follow-up or calendar booking response.
    3. Proactively alerts the founder if a high-priority opportunity or demo request is detected.
    """
    db = get_database()

    system_prompt = (
        "You are an autonomous B2B sales development AI. Analyze an inbound reply from a prospective client "
        "who received our cold pitch about the WhatsApp Customer Support & Ordering Agent."
    )

    human_prompt = f"""Inbound Reply from Lead: "{reply_message}"

Analyze the intent and categorize into ONE of:
- "DEMO_REQUEST": Lead wants a call, demo, pricing, or meeting.
- "INTERESTED": Positive interest or asking questions about features.
- "OBJECTION": Expressed hesitation (e.g. "is it expensive?", "we have a person already").
- "NOT_INTERESTED": Explicit rejection or opt-out.

Provide:
1. Intent category.
2. Suggested automated response handling their objection or offering calendar link (calendly.com/founder/15min).
3. Founder Alert flag: true if DEMO_REQUEST or INTERESTED, else false.
4. Short explanation for founder (e.g. "Lead wants a 15-min call on Wednesday").

Output strictly valid JSON:
{{
  "intent": "DEMO_REQUEST" | "INTERESTED" | "OBJECTION" | "NOT_INTERESTED",
  "suggested_response": string,
  "notify_founder": boolean,
  "founder_summary": string
}}
"""

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])

    clean = response.content.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]

    try:
        analysis = json.loads(clean)
    except Exception as e:
        logger.error(f"Error parsing reply analysis JSON: {e}")
        analysis = {
            "intent": "INTERESTED",
            "suggested_response": "Thank you for getting back! Would you be open to a quick 10-minute walkthrough this week?",
            "notify_founder": True,
            "founder_summary": "Lead replied to our outreach."
        }

    # Record reply log in database
    reply_doc = {
        "sender": sender_identifier,
        "message": reply_message,
        "intent": analysis.get("intent"),
        "suggested_response": analysis.get("suggested_response"),
        "founder_summary": analysis.get("founder_summary"),
        "created_at": datetime.now(timezone.utc),
    }
    await db["lead_replies"].insert_one(reply_doc)

    # Autonomous Founder Alert
    if analysis.get("notify_founder"):
        alert_text = (
            f"🚀 *FOUNDER ALERT: HOT LEAD REPLY!*\n\n"
            f"👤 *From:* {sender_identifier}\n"
            f"💬 *Reply:* \"{reply_message}\"\n"
            f"🎯 *Intent:* {analysis.get('intent')}\n"
            f"📌 *Analysis:* {analysis.get('founder_summary')}\n\n"
            f"✨ *Recommended Response:* {analysis.get('suggested_response')}"
        )

        logger.info(f"HIGH-PRIORITY FOUNDER ALERT: {alert_text}")

        # Send alert to founder's WhatsApp if configured
        target_phone = founder_whatsapp or settings.WHATSAPP_PHONE_NUMBER_ID
        if target_phone:
            try:
                await send_whatsapp_message(
                    to_phone=target_phone,
                    text=alert_text
                )
            except Exception as e:
                logger.warning(f"Could not dispatch founder WhatsApp alert: {e}")

    return analysis
