import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:latest"

def calculate_score(analysis: dict, strategy: dict) -> tuple[int, list, list]:
    """Rule-based ICP scoring — deterministic, no LLM needed."""
    score = 0
    matches = []
    misses = []

    prospect_industry = analysis.get("industry", "").lower()
    prospect_size = analysis.get("company_size", "").lower()
    prospect_signals = [s.lower() for s in analysis.get("icp_signals", [])]
    prospect_pains = [p.lower() for p in analysis.get("pain_points", [])]
    prospect_summary = analysis.get("company_summary", "").lower()

    target_industries = [i.lower() for i in strategy.get("target_industries", [])]
    target_sizes = [s.lower() for s in strategy.get("company_sizes", [])]
    target_geos = [g.lower() for g in strategy.get("geographies", [])]
    target_pains = [p.lower() for p in strategy.get("pain_points", [])]
    target_triggers = [t.lower() for t in strategy.get("buying_triggers", [])]

    # 1. Industry match (30 pts)
    industry_match = any(
        ind in prospect_industry or prospect_industry in ind
        for ind in target_industries
    )
    if industry_match:
        score += 30
        matches.append(f"Industry match: {analysis.get('industry', '')}")
    else:
        misses.append(f"Industry '{analysis.get('industry', '')}' not in target industries")

    # 2. Company size match (20 pts)
    size_match = any(
        sz in prospect_size or prospect_size in sz
        for sz in target_sizes
    )
    if size_match:
        score += 20
        matches.append(f"Company size match: {analysis.get('company_size', '')}")
    else:
        misses.append(f"Size '{analysis.get('company_size', '')}' not in target sizes")

    # 3. Pain point overlap (25 pts)
    pain_keywords = []
    for tp in target_pains:
        for word in tp.split():
            if len(word) > 4:
                pain_keywords.append(word)

    pain_hits = 0
    for kw in pain_keywords:
        if any(kw in p for p in prospect_pains) or kw in prospect_summary:
            pain_hits += 1

    pain_score = min(25, int((pain_hits / max(len(pain_keywords), 1)) * 25))
    score += pain_score
    if pain_score >= 15:
        matches.append(f"Strong pain point alignment ({pain_hits} signals detected)")
    elif pain_score > 0:
        matches.append(f"Partial pain point overlap ({pain_hits} signals)")
    else:
        misses.append("No matching pain points detected")

    # 4. Buying trigger signals (15 pts)
    trigger_keywords = []
    for t in target_triggers:
        for word in t.split():
            if len(word) > 4:
                trigger_keywords.append(word)

    trigger_hit = any(
        kw in prospect_summary or any(kw in s for s in prospect_signals)
        for kw in trigger_keywords
    )
    if trigger_hit:
        score += 15
        matches.append("Buying trigger signals present")
    else:
        misses.append("No buying trigger signals detected")

    # 5. Geography bonus (10 pts)
    geo_keywords = []
    for g in target_geos:
        geo_keywords.extend(g.lower().split())

    geo_hit = any(kw in prospect_summary for kw in geo_keywords)
    if geo_hit:
        score += 10
        matches.append(f"Geography match detected")

    return min(score, 100), matches, misses


def get_grade(score: int) -> str:
    if score >= 80: return "A"
    if score >= 60: return "B"
    if score >= 40: return "C"
    return "D"


def get_qualitative_fields(analysis: dict, strategy: dict) -> dict:
    """Use Ollama only for text fields, not for the score."""
    prompt = f"""You are a B2B sales expert. Based on this prospect analysis, provide brief qualitative insights.

Prospect: {analysis.get('company_summary', '')}
Industry: {analysis.get('industry', '')}
Our product solves: {', '.join(strategy.get('pain_points', [])[:3])}

Return ONLY this JSON (keep responses SHORT - 1-2 sentences each):
{{
  "why_fit": "one sentence why they need our product",
  "suggested_service": "most relevant service for them (5 words max)",
  "potential_pain_points": ["pain 1", "pain 2", "pain 3"],
  "confidence": "High",
  "confidence_reason": "one short reason",
  "bd_notes": "one actionable tip for outreach"
}}

No markdown, no backticks, just JSON.
"""
    try:
        res = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 512}
        }, timeout=60)
        raw = res.json()["response"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        if not raw.endswith("}"):
            raw = raw + "}" if raw.endswith('"') else raw + '"}'
        return json.loads(raw)
    except:
        return {
            "why_fit": "Prospect operates in a target industry with relevant compliance needs.",
            "suggested_service": "Compliance audit",
            "potential_pain_points": ["Data security", "Regulatory compliance", "Security audits"],
            "confidence": "Medium",
            "confidence_reason": "Based on industry and size match.",
            "bd_notes": "Reference their industry's compliance requirements when reaching out."
        }


def score_prospect(analysis: dict, strategy: dict) -> dict:
    # Rule-based score — always accurate
    score, matches, misses = calculate_score(analysis, strategy)
    grade = get_grade(score)

    # LLM only for qualitative text
    qual = get_qualitative_fields(analysis, strategy)

    verdict_map = {
        "A": "Strong ICP match — high priority prospect.",
        "B": "Good fit — worth pursuing with tailored outreach.",
        "C": "Partial fit — proceed with caution.",
        "D": "Weak fit — consider deprioritizing."
    }

    return {
        "score": score,
        "grade": grade,
        "matches": matches,
        "misses": misses,
        "verdict": verdict_map[grade],
        "why_fit": qual.get("why_fit", ""),
        "suggested_service": qual.get("suggested_service", ""),
        "potential_pain_points": qual.get("potential_pain_points", []),
        "confidence": qual.get("confidence", "Medium"),
        "confidence_reason": qual.get("confidence_reason", ""),
        "bd_notes": qual.get("bd_notes", "")
    }