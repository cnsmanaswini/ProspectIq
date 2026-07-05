import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:latest"

def generate_strategy(product_description: str) -> dict:
    prompt = f"""You are an expert B2B sales strategist. Based on this product description, think like a seasoned salesperson and generate a detailed target prospect strategy.

Product Description:
{product_description}

Return ONLY a JSON object with this exact structure:
{{
  "target_industries": ["industry1", "industry2", "industry3", "industry4"],
  "company_sizes": ["Startup", "SME"],
  "geographies": ["region1", "region2"],
  "pain_points": ["pain point 1", "pain point 2", "pain point 3", "pain point 4"],
  "buying_triggers": ["trigger 1", "trigger 2", "trigger 3"],
  "decision_makers": ["Title 1", "Title 2", "Title 3"],
  "icp_summary": "2 sentence summary of the ideal customer profile"
}}

No markdown, no backticks, no explanation. Just JSON.
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