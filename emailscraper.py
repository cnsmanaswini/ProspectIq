import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

def scrape_emails(url: str) -> list[str]:
    emails = set()
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # Find mailto links
        for a in soup.select("a[href^='mailto:']"):
            email = a["href"].replace("mailto:", "").split("?")[0].strip()
            if email and "@" in email:
                emails.add(email.lower())

        # Find emails in text
        text = soup.get_text()
        found = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
        for e in found:
            emails.add(e.lower())

        # Also try /contact page
        base = url.rstrip("/")
        for path in ["/contact", "/contact-us", "/about"]:
            try:
                r2 = requests.get(base + path, headers=HEADERS, timeout=8)
                soup2 = BeautifulSoup(r2.text, "html.parser")
                for a in soup2.select("a[href^='mailto:']"):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip()
                    if email and "@" in email:
                        emails.add(email.lower())
                text2 = soup2.get_text()
                found2 = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text2)
                for e in found2:
                    emails.add(e.lower())
            except:
                pass

    except Exception as e:
        print(f"Email scrape error: {e}")

    # Filter out image/file extensions and common noise
    filtered = [
        e for e in emails
        if not any(e.endswith(x) for x in [".png", ".jpg", ".gif", ".svg", ".css", ".js"])
        and "example" not in e
        and "sentry" not in e
        and "wix" not in e
    ]

    # Sort — prioritize contact/info/hello emails
    priority = ["contact", "info", "hello", "hi", "support", "sales", "bd", "business"]
    def sort_key(e):
        for i, p in enumerate(priority):
            if p in e:
                return i
        return 99

    return sorted(filtered, key=sort_key)[:8]