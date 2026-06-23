"""
Public-facing tracking server — open pixels, click redirects, unsubscribe, landing pages.
Run alongside Streamlit:  uvicorn tracker:app --host 0.0.0.0 --port 8502
Nginx then routes:
  /track/*      -> :8502
  /unsubscribe/* -> :8502
  /l/*          -> :8502
  everything else -> :8501 (Streamlit)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from fastapi.responses import Response, RedirectResponse, HTMLResponse
import urllib.parse
import database as db

app = FastAPI(title="Tungaloy Tracker", docs_url=None, redoc_url=None)

BRAND_RED   = "#c0392b"
BRAND_DARK  = "#1a1a2e"

# ── 1×1 transparent PNG pixel ─────────────────────────────────────────────────
PIXEL = bytes([
    0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,0x00,0x00,0x00,0x0d,0x49,0x48,0x44,0x52,
    0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01,0x08,0x06,0x00,0x00,0x00,0x1f,0x15,0xc4,
    0x89,0x00,0x00,0x00,0x0a,0x49,0x44,0x41,0x54,0x78,0x9c,0x62,0x00,0x01,0x00,0x00,
    0x05,0x00,0x01,0x0d,0x0a,0x2d,0xb4,0x00,0x00,0x00,0x00,0x49,0x45,0x4e,0x44,0xae,
    0x42,0x60,0x82,
])

# ── Open tracking ──────────────────────────────────────────────────────────────

@app.get("/track/o/{send_id}")
async def track_open(send_id: int):
    try:
        db.email_record_open(send_id)
    except Exception:
        pass
    return Response(content=PIXEL, media_type="image/png",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


# ── Click tracking ─────────────────────────────────────────────────────────────

@app.get("/track/c/{send_id}/{url:path}")
async def track_click(send_id: int, url: str):
    try:
        decoded = urllib.parse.unquote(url)
        db.email_record_click(send_id, decoded)
    except Exception:
        decoded = "/"
    return RedirectResponse(url=decoded, status_code=302)


# ── Unsubscribe ────────────────────────────────────────────────────────────────

@app.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_page(token: str):
    send = db.email_get_send_by_token(token)
    if not send:
        return _page("Invalid Link", "<p>This unsubscribe link is not valid or has already been used.</p>")

    if send['unsubscribed']:
        return _page("Already Unsubscribed",
                     f"<p><strong>{send['contact_email']}</strong> is already removed from our mailing list.</p>")

    return _page("Unsubscribe", f"""
        <p>Click the button below to remove <strong>{send['contact_email']}</strong>
        from all Tungaloy UK marketing emails.</p>
        <form method="post" action="/unsubscribe/{token}">
            <button type="submit" style="background:{BRAND_RED};color:#fff;border:none;
                padding:12px 28px;border-radius:6px;font-size:16px;cursor:pointer;font-weight:700;">
                ✓ Unsubscribe Me
            </button>
        </form>
        <p style="color:#888;font-size:13px;margin-top:20px;">
            You can always contact us at
            <a href="mailto:rob.werhun@tungaloyuk.co.uk">rob.werhun@tungaloyuk.co.uk</a>
            to re-subscribe at any time.
        </p>""")


@app.post("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_confirm(token: str):
    success = db.email_record_unsubscribe(token)
    if success:
        return _page("Unsubscribed ✓", """
            <div style="text-align:center;padding:20px;">
                <div style="font-size:48px;margin-bottom:16px;">✅</div>
                <h3>You've been unsubscribed</h3>
                <p>You will no longer receive marketing emails from Tungaloy UK.</p>
                <p>Thank you for being a customer — we hope to hear from you again.</p>
                <p style="margin-top:30px;">
                    <a href="https://tungaloy.com/uk/" style="color:{BRAND_RED};">
                        Visit Tungaloy UK →
                    </a>
                </p>
            </div>""")
    return _page("Error", "<p>Something went wrong. Please contact us directly.</p>")


# ── Landing pages ──────────────────────────────────────────────────────────────

@app.get("/l/{slug}", response_class=HTMLResponse)
async def landing_page(slug: str):
    page = db.lp_get_page(slug)
    if not page:
        return _page("Page Not Found", """
            <div style="text-align:center;padding:40px 20px;">
                <h2>404 — Page Not Found</h2>
                <p>This page doesn't exist or has been removed.</p>
                <a href="https://tungaloy.com/uk/" style="color:{BRAND_RED};">
                    Visit Tungaloy UK →
                </a>
            </div>""")
    try:
        db.lp_record_view(page['id'])
    except Exception:
        pass
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page['title']} | Tungaloy UK</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:0; background:#f4f4f4; font-family:Arial,sans-serif; color:#333; }}
  .hero {{ background:{BRAND_DARK}; color:#fff; padding:24px 32px; text-align:center; }}
  .hero h1 {{ margin:0; font-size:20px; }}
  .hero p  {{ margin:6px 0 0; opacity:.75; font-size:13px; }}
  .content {{ max-width:700px; margin:30px auto; background:#fff; border-radius:8px;
              padding:40px; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
  a.cta {{ display:inline-block; background:{BRAND_RED}; color:#fff !important;
           text-decoration:none; padding:12px 28px; border-radius:6px;
           font-weight:700; margin:16px 0; }}
  .footer {{ text-align:center; padding:20px; font-size:12px; color:#aaa; }}
  .footer a {{ color:#aaa; }}
</style>
</head>
<body>
  <div class="hero">
    <h1>Tungaloy UK</h1>
    <p>Cutting Tools &amp; Carbide Specialists</p>
  </div>
  <div class="content">
    <h2 style="color:{BRAND_DARK};margin-top:0;">{page['title']}</h2>
    {page['body_html']}
  </div>
  <div class="footer">
    <p>© Tungaloy UK &nbsp;|&nbsp;
       <a href="https://tungaloy.com/uk/">tungaloy.com/uk</a> &nbsp;|&nbsp;
       <a href="mailto:rob.werhun@tungaloyuk.co.uk">Contact Us</a>
    </p>
  </div>
</body>
</html>"""


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "tungaloy-tracker"}


# ── HTML page helper ───────────────────────────────────────────────────────────

def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Tungaloy UK</title>
<style>
  body {{ margin:0; padding:0; background:#f4f4f4; font-family:Arial,sans-serif; }}
  .hero {{ background:{BRAND_DARK}; color:#fff; padding:20px 32px; text-align:center; }}
  .hero h1 {{ margin:0; font-size:18px; }}
  .box {{ max-width:540px; margin:40px auto; background:#fff; border-radius:8px;
          padding:36px; box-shadow:0 2px 8px rgba(0,0,0,.08); text-align:center; }}
  .box h2 {{ color:{BRAND_DARK}; }}
  a {{ color:{BRAND_RED}; }}
  .footer {{ text-align:center; padding:20px; font-size:12px; color:#aaa; }}
</style>
</head>
<body>
  <div class="hero"><h1>Tungaloy UK</h1></div>
  <div class="box">
    <h2>{title}</h2>
    {body}
  </div>
  <div class="footer">
    <a href="https://tungaloy.com/uk/">tungaloy.com/uk</a>
  </div>
</body>
</html>"""
