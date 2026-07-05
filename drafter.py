import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:latest"

def generate_draft(analysis: dict, sender_context: str = "", score: dict = None) -> dict:
    pain_points = ', '.join(analysis.get('pain_points', []))
    icp_signals = ', '.join(analysis.get('icp_signals', []))
    suggested_service = score.get('suggested_service', '') if score else ''
    why_fit = score.get('why_fit', '') if score else ''
    decision_makers = ', '.join(analysis.get('decision_maker_titles', []))

    prompt = f"""You are an expert B2B cold outreach copywriter.

SENDER (our company):
{sender_context}

PROSPECT (who we're reaching out to):
- Company: {analysis.get('company_summary', '')}
- Industry: {analysis.get('industry', '')}
- Pain Points: {pain_points}
- ICP Signals: {icp_signals}
- Decision Makers: {decision_makers}
- Why they're a fit: {why_fit}
- Suggested Service for them: {suggested_service}

Generate TWO outreach messages:

1. COLD EMAIL — professional, 4-5 lines, specific subject line, ends with soft CTA (15 min call)
2. LINKEDIN DM — casual, max 280 characters, one specific hook, one CTA

Return ONLY this JSON:
{{
  "email_subject": "specific subject line here",
  "email_body": "full email body with \\n for line breaks",
  "linkedin_dm": "short linkedin message under 280 chars"
}}

The email is FROM our company TO the prospect. Sound human, not templated.
No markdown, no backticks, just JSON.
"""

    try:
        res = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=60)
        res.raise_for_status()

        raw = res.json()["response"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError:
        return {"error": "LLM returned invalid JSON", "raw": raw}
    except Exception as e:
        return {"error": str(e)}