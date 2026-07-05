import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

def scrape(url: str) -> dict:
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else "No title"
        
        # Meta description
        meta = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta["content"].strip() if meta and meta.get("content") else ""

        # Main body text — limit to 2000 chars to keep LLM prompt tight
        body = soup.get_text(separator=" ", strip=True)
        body = " ".join(body.split())[:2000]

        return {
            "title": title,
            "scraped_text": f"{meta_desc}\n\n{body}".strip(),
            "error": None
        }

    except Exception as e:
        return {"title": "", "scraped_text": "", "error": str(e)}