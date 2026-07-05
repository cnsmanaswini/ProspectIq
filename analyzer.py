import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:latest"

def analyze_prospect(scraped_text: str) -> dict:
    prompt = f"""You are a B2B business development analyst. Analyze the following company website content and return a JSON object with this exact structure:

{{
  "company_summary": "2-3 sentence summary of what the company does",
  "industry": "the industry they operate in",
  "company_size": "startup / smb / mid-market / enterprise (best guess)",
  "icp_signals": ["signal 1", "signal 2", "signal 3"],
  "pain_points": ["pain point 1", "pain point 2"],
  "decision_maker_titles": ["title 1", "title 2"],
  "qualification_score": 7,
  "qualification_reason": "one sentence explaining the score out of 10"
}}

Return ONLY valid JSON. No explanation, no markdown, no backticks.

Website content:
{scraped_text[:1500]}
"""

    try:
        res = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=60)
        res.raise_for_status()

        raw = res.json()["response"].strip()

        # Strip markdown code fences if model adds them
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