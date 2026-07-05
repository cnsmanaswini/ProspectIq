import requests
import json
from bs4 import BeautifulSoup

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:latest"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

EXCLUDE_DOMAINS = [
    "linkedin.com", "twitter.com", "facebook.com", "youtube.com",
    "wikipedia.org", "reddit.com", "medium.com", "techcrunch.com",
    "crunchbase.com", "inc42.com", "yourstory.com", "f6s.com"
]

def get_company_suggestions(strategy: dict) -> list[dict]:
    """Use Ollama to suggest real companies matching the ICP."""
    prompt = f"""You are a B2B market research expert. Based on this ICP strategy, suggest 10 real companies that would be ideal prospects.

ICP Strategy:
- Target Industries: {', '.join(strategy.get('target_industries', []))}
- Company Sizes: {', '.join(strategy.get('company_sizes', []))}
- Geographies: {', '.join(strategy.get('geographies', []))}
- Pain Points: {', '.join(strategy.get('pain_points', []))}
- Buying Triggers: {', '.join(strategy.get('buying_triggers', []))}

Return ONLY a JSON array of 10 real companies:
[
  {{"name": "Razorpay", "website": "https://razorpay.com", "reason": "Fast-growing fintech handling payments"}},
  {{"name": "Zepto", "website": "https://www.zeptonow.com", "reason": "Quick commerce startup with customer data"}},
  ...
]

Use REAL companies with their ACTUAL website URLs. Focus on companies in the target geographies and industries.
No markdown, no backticks, just the JSON array.
"""

    try:
        res = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=90)
        res.raise_for_status()

        raw = res.json()["response"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        companies = json.loads(raw)
        return companies if isinstance(companies, list) else []

    except Exception as e:
        print(f"Ollama suggestion error: {e}")
        return []

def verify_url(url: str) -> bool:
    """Check if URL is reachable."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        return r.status_code < 400
    except:
        return False

def search_prospects(strategy: dict, max_results: int = 8) -> list[str]:
    """Get prospect URLs using Ollama suggestions."""
    print("Asking Ollama to suggest prospect companies...")
    companies = get_company_suggestions(strategy)
    print(f"Ollama suggested {len(companies)} companies")

    urls = []
    for company in companies:
        url = company.get("website", "").strip()
        name = company.get("name", "")
        reason = company.get("reason", "")

        if not url or not url.startswith("http"):
            continue

        # Skip excluded domains
        skip = False
        for domain in EXCLUDE_DOMAINS:
            if domain in url:
                skip = True
                break
        if skip:
            continue

        print(f"  Checking {name} ({url}) — {reason}")
        if verify_url(url):
            print(f"    ✓ Reachable")
            if url not in urls:
                urls.append(url)
        else:
            print(f"    ✗ Not reachable")

        if len(urls) >= max_results:
            break

    print(f"Total valid prospects: {len(urls)}")
    return urls