from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from database import init_db, get_db, get_strategy
from scraper import scrape
from analyzer import analyze_prospect
from scorer import score_prospect
from drafter import generate_draft
from strategy import generate_strategy
from finder import search_prospects
import json

app = FastAPI()

import json as _json
templates_env_ready = False
templates = Jinja2Templates(directory="templates")
templates.env.filters["fromjson"] = lambda s: _json.loads(s) if s else {}

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def index(request: Request):
    conn = get_db()
    prospects = conn.execute(
        "SELECT * FROM prospects ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    strat = get_strategy()

    # Parse score for each prospect to show in table
    prospects_data = []
    for p in prospects:
        p_dict = dict(p)
        if p_dict.get("score_json"):
            try:
                p_dict["score"] = json.loads(p_dict["score_json"])
            except:
                p_dict["score"] = None
        else:
            p_dict["score"] = None
        prospects_data.append(p_dict)

    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"prospects": prospects_data, "has_strategy": strat is not None}
    )

@app.post("/add")
def add_prospect(url: str = Form(...)):
    result = scrape(url)
    conn = get_db()
    if result["error"]:
        conn.execute(
            "INSERT INTO prospects (url, title, scraped_text, status) VALUES (?, ?, ?, ?)",
            (url, "Error", result["error"], "error")
        )
    else:
        conn.execute(
            "INSERT INTO prospects (url, title, scraped_text, status) VALUES (?, ?, ?, ?)",
            (url, result["title"], result["scraped_text"], "scraped")
        )
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)

@app.post("/discover")
def discover(request: Request):
    strat_row = get_strategy()
    if not strat_row:
        return RedirectResponse("/strategy", status_code=303)

    strategy = json.loads(strat_row["strategy_json"])
    urls = search_prospects(strategy, max_results=5)

    conn = get_db()
    for url in urls:
        existing = conn.execute(
            "SELECT id FROM prospects WHERE url = ?", (url,)
        ).fetchone()
        if existing:
            continue
        result = scrape(url)
        if result["error"]:
            conn.execute(
                "INSERT INTO prospects (url, title, scraped_text, status) VALUES (?, ?, ?, ?)",
                (url, "Error", result["error"], "error")
            )
        else:
            conn.execute(
                "INSERT INTO prospects (url, title, scraped_text, status) VALUES (?, ?, ?, ?)",
                (url, result["title"], result["scraped_text"], "scraped")
            )
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)

@app.get("/prospect/{id}")
def view_prospect(request: Request, id: int):
    conn = get_db()
    prospect = conn.execute("SELECT * FROM prospects WHERE id = ?", (id,)).fetchone()
    conn.close()

    analysis = None
    score = None
    draft = None

    if prospect["analysis_json"]:
        try:
            analysis = json.loads(prospect["analysis_json"])
        except:
            pass

    if prospect["score_json"]:
        try:
            score = json.loads(prospect["score_json"])
        except:
            pass

    if prospect["draft_json"]:
        try:
            draft = json.loads(prospect["draft_json"])
        except:
            pass

    return templates.TemplateResponse(
        request=request, name="prospect.html",
        context={"prospect": prospect, "analysis": analysis, "score": score, "draft": draft}
    )

@app.post("/analyze/{id}")
def run_analysis(id: int):
    conn = get_db()
    prospect = conn.execute("SELECT * FROM prospects WHERE id = ?", (id,)).fetchone()
    if not prospect or not prospect["scraped_text"]:
        conn.close()
        return RedirectResponse(f"/prospect/{id}", status_code=303)

    result = analyze_prospect(prospect["scraped_text"])
    conn.execute(
        "UPDATE prospects SET analysis_json = ?, status = ? WHERE id = ?",
        (json.dumps(result), "analyzed", id)
    )

    # Auto-score if strategy exists
    strat_row = get_strategy()
    if strat_row and not result.get("error"):
        strategy = json.loads(strat_row["strategy_json"])
        score_result = score_prospect(result, strategy)
        conn.execute(
            "UPDATE prospects SET score_json = ?, status = ? WHERE id = ?",
            (json.dumps(score_result), "scored", id)
        )

    conn.commit()
    conn.close()
    return RedirectResponse(f"/prospect/{id}", status_code=303)

@app.post("/draft/{id}")
def run_draft(id: int):
    conn = get_db()
    prospect = conn.execute("SELECT * FROM prospects WHERE id = ?", (id,)).fetchone()
    if not prospect or not prospect["analysis_json"]:
        conn.close()
        return RedirectResponse(f"/prospect/{id}", status_code=303)

    analysis = json.loads(prospect["analysis_json"])
    strat_row = get_strategy()
    sender_context = strat_row["product_description"] if strat_row else ""

    score_data = json.loads(prospect["score_json"]) if prospect["score_json"] else None
    result = generate_draft(analysis, sender_context=sender_context, score=score_data)
    conn.execute(
        "UPDATE prospects SET draft_json = ?, status = ? WHERE id = ?",
        (json.dumps(result), "drafted", id)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(f"/prospect/{id}", status_code=303)

@app.get("/strategy")
def strategy_page(request: Request):
    row = get_strategy()
    strategy = None
    product_description = ""
    if row:
        product_description = row["product_description"]
        try:
            strategy = json.loads(row["strategy_json"])
        except:
            pass
    return templates.TemplateResponse(
        request=request, name="strategy.html",
        context={"strategy": strategy, "product_description": product_description}
    )

@app.post("/strategy")
def save_strategy(product_description: str = Form(...)):
    result = generate_strategy(product_description)
    conn = get_db()
    conn.execute("DELETE FROM strategy")
    conn.execute(
        "INSERT INTO strategy (product_description, strategy_json) VALUES (?, ?)",
        (product_description, json.dumps(result))
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/strategy", status_code=303)

@app.get("/debug/strategy")
def debug_strategy():
    row = get_strategy()
    if not row:
        return {"error": "no strategy saved"}
    return {"product_description": row["product_description"], "strategy_json": row["strategy_json"]}

@app.get("/prospect/{id}/report")
def view_report(request: Request, id: int):
    conn = get_db()
    prospect = conn.execute("SELECT * FROM prospects WHERE id = ?", (id,)).fetchone()
    conn.close()

    analysis = None
    score = None

    if prospect["analysis_json"]:
        try:
            analysis = json.loads(prospect["analysis_json"])
        except:
            pass

    if prospect["score_json"]:
        try:
            score = json.loads(prospect["score_json"])
        except:
            pass

    return templates.TemplateResponse(
        request=request, name="report.html",
        context={"prospect": prospect, "analysis": analysis, "score": score}
    )

# ── APPROVAL WORKFLOW ─────────────────────────────────────────────────────

@app.post("/prospect/{id}/approve")
def approve_prospect(
    id: int,
    email_subject: str = Form(default=""),
    email_body: str = Form(default=""),
    linkedin_dm: str = Form(default="")
):
    conn = get_db()
    conn.execute("""
        UPDATE prospects SET
            approval_status = 'approved',
            approved_email_subject = ?,
            approved_email_body = ?,
            approved_linkedin_dm = ?,
            status = 'approved'
        WHERE id = ?
    """, (email_subject, email_body, linkedin_dm, id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/prospect/{id}", status_code=303)

@app.post("/prospect/{id}/reject")
def reject_prospect(id: int):
    conn = get_db()
    conn.execute("""
        UPDATE prospects SET approval_status = 'rejected', status = 'rejected'
        WHERE id = ?
    """, (id,))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/prospect/{id}", status_code=303)

@app.post("/prospect/{id}/reset")
def reset_approval(id: int):
    conn = get_db()
    conn.execute("""
        UPDATE prospects SET approval_status = 'pending', status = 'drafted'
        WHERE id = ?
    """, (id,))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/prospect/{id}", status_code=303)

@app.get("/review")
def review_queue(request: Request):
    conn = get_db()
    pending = conn.execute("""
        SELECT * FROM prospects WHERE draft_json IS NOT NULL
        AND (approval_status = 'pending' OR approval_status IS NULL)
        ORDER BY created_at DESC
    """).fetchall()
    approved = conn.execute("""
        SELECT * FROM prospects WHERE approval_status = 'approved'
        ORDER BY created_at DESC
    """).fetchall()
    rejected = conn.execute("""
        SELECT * FROM prospects WHERE approval_status = 'rejected'
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()

    def parse_score(p):
        d = dict(p)
        if d.get("score_json"):
            try:
                d["score"] = json.loads(d["score_json"])
            except:
                d["score"] = None
        else:
            d["score"] = None
        return d

    return templates.TemplateResponse(
        request=request, name="review.html",
        context={
            "pending": [parse_score(p) for p in pending],
            "approved": [parse_score(p) for p in approved],
            "rejected": [parse_score(p) for p in rejected],
        }
    )

# ── EMAIL SENDING ─────────────────────────────────────────────────────────

from emailscraper import scrape_emails
from emailsender import send_email

@app.get("/prospect/{id}/send")
def send_page(request: Request, id: int):
    conn = get_db()
    prospect = conn.execute("SELECT * FROM prospects WHERE id = ?", (id,)).fetchone()
    conn.close()

    if not prospect or prospect["approval_status"] != "approved":
        return RedirectResponse(f"/prospect/{id}", status_code=303)

    # Scrape emails from prospect website
    emails = scrape_emails(prospect["url"])

    return templates.TemplateResponse(
        request=request, name="send.html",
        context={"prospect": prospect, "emails": emails}
    )

@app.post("/prospect/{id}/send")
def do_send(id: int, recipient_email: str = Form(...)):
    conn = get_db()
    prospect = conn.execute("SELECT * FROM prospects WHERE id = ?", (id,)).fetchone()

    if not prospect:
        conn.close()
        return RedirectResponse("/", status_code=303)

    subject = prospect["approved_email_subject"] or "Introduction"
    body = prospect["approved_email_body"] or ""

    result = send_email(recipient_email, subject, body)

    if result["success"]:
        conn.execute(
            "UPDATE prospects SET status = 'sent', approval_status = 'sent' WHERE id = ?",
            (id,)
        )
    else:
        conn.execute(
            "UPDATE prospects SET status = 'failed' WHERE id = ?",
            (id,)
        )

    conn.commit()
    conn.close()
    return RedirectResponse(f"/prospect/{id}", status_code=303)