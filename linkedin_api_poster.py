"""
linkedin_api_poster.py — LinkedIn Official API se post karo

OAuth 2.0 use karta hai — email/password ki zaroorat NAHI.
Sirf ek baar browser mein authorize karo, phir hamesha API se post.

Setup (ek baar):
    python linkedin_api_poster.py --auth

Post karo:
    python linkedin_api_poster.py --post "Tumhari post text yahan"
    python linkedin_api_poster.py --file silver_tier/Approved/LI_*.md

Check karo:
    python linkedin_api_poster.py --check
"""

import os, sys, io, json, argparse, logging, webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
import urllib.request

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LinkedInAPI")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT        = Path("silver_tier")
TOKEN_FILE   = Path(".linkedin_token.json")
POST_LOG     = Path(".linkedin_api_post_log.json")
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES       = "openid profile w_member_social"

MAX_POSTS_PER_WEEK = 2


# ── Env loader ─────────────────────────────────────────────────────────────────

def _load_env():
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get_creds():
    client_id     = os.environ.get("linkeidin-client-id", "").strip()
    client_secret = os.environ.get("linkeid-client-secret", "").strip()
    if not client_id or not client_secret:
        print("\n[ERROR] LinkedIn credentials .env mein nahi hain.")
        print("  linkeidin-client-id=YOUR_ID")
        print("  linkeid-client-secret=YOUR_SECRET")
        sys.exit(1)
    return client_id, client_secret


# ── Token management ───────────────────────────────────────────────────────────

def _save_token(token_data: dict):
    token_data["saved_at"] = datetime.now().isoformat()
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
    logger.info("Token saved: %s", TOKEN_FILE)


def _load_token() -> dict | None:
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _get_access_token() -> str:
    token = _load_token()
    if not token:
        print("\n[ERROR] LinkedIn token nahi mila. Pehle auth karo:")
        print("  python linkedin_api_poster.py --auth")
        sys.exit(1)
    return token["access_token"]


# ── OAuth flow ─────────────────────────────────────────────────────────────────

def cmd_auth():
    """One-time OAuth authorization — opens browser, saves token."""
    client_id, client_secret = _get_creds()

    auth_code_holder = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if "code" in params:
                auth_code_holder["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                <html><body style='font-family:sans-serif;text-align:center;padding:50px'>
                <h2 style='color:green'>LinkedIn Authorization Complete!</h2>
                <p>Terminal mein wapas jao. Ye tab band kar sakte ho.</p>
                </body></html>""")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Error: No code received")
        def log_message(self, *args):
            pass  # suppress server logs

    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    }
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params)

    print("\n" + "=" * 60)
    print("  LinkedIn Authorization")
    print("=" * 60)
    print("\nBrowser mein LinkedIn khul raha hai...")
    print("Apne LinkedIn account se ALLOW karo.")
    print("\nAgar browser na khule to ye URL copy karo:")
    print(f"  {auth_url}\n")

    webbrowser.open(auth_url)

    # Start local server to catch callback
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    logger.info("Callback server start hua (localhost:8080)...")
    server.handle_request()  # waits for one request

    if "code" not in auth_code_holder:
        print("[ERROR] Authorization code nahi mila.")
        sys.exit(1)

    auth_code = auth_code_holder["code"]
    logger.info("Authorization code mila. Token exchange ho raha hai...")

    # Exchange code for token
    token_data = urlencode({
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.loads(resp.read())

    _save_token(token)

    print("\n[OK] Authorization complete! Token saved.")
    print(f"     Expires in: {token.get('expires_in', '?')} seconds (~60 days)")
    print("\nAb post karo:")
    print("  python linkedin_api_poster.py --post 'Tumhari post text'")


# ── Get LinkedIn member ID ──────────────────────────────────────────────────────

def _get_member_id(access_token: str) -> str:
    token_data = _load_token()
    if token_data and "member_id" in token_data:
        return token_data["member_id"]

    req = urllib.request.Request(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    member_id = data.get("sub", "")
    if not member_id:
        raise RuntimeError("Member ID nahi mila LinkedIn API se.")

    # Cache it
    token_data = _load_token() or {}
    token_data["member_id"] = member_id
    token_data["name"] = data.get("name", "")
    _save_token(token_data)
    return member_id


# ── Post to LinkedIn ───────────────────────────────────────────────────────────

def _post_to_linkedin(text: str, access_token: str, member_id: str) -> dict:
    """Post text to LinkedIn via API."""
    payload = json.dumps({
        "author": f"urn:li:person:{member_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.linkedin.com/v2/ugcPosts",
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        post_id = resp.headers.get("X-RestLi-Id", "unknown")
        return {"post_id": post_id, "status": resp.status}


# ── Post log ───────────────────────────────────────────────────────────────────

def _load_log() -> list:
    if POST_LOG.exists():
        try:
            return json.loads(POST_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_log(log: list):
    POST_LOG.write_text(json.dumps(log[-100:], indent=2), encoding="utf-8")


def _posts_this_week(log: list) -> list:
    from datetime import timedelta
    today  = datetime.now().date()
    monday = today - __import__('datetime').timedelta(days=today.weekday())
    result = []
    for entry in log:
        try:
            d = datetime.fromisoformat(entry["posted_at"]).date()
            if d >= monday:
                result.append(entry)
        except Exception:
            pass
    return result


# ── Read post from file ────────────────────────────────────────────────────────

def _read_post_file(filepath: str) -> str:
    path = Path(filepath)
    if not path.exists():
        # Try in Approved/
        path = VAULT / "Approved" / filepath
    if not path.exists():
        print(f"[ERROR] File nahi mili: {filepath}")
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()

    for marker in ("## Approval Checklist", "## To Post", "\n---\n##"):
        if marker in text:
            text = text[:text.index(marker)]

    return text.strip()


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_check():
    log        = _load_log()
    week_posts = _posts_this_week(log)
    token      = _load_token()

    print("\nLinkedIn API Status")
    print("-" * 35)
    print(f"Token saved : {'Yes' if token else 'No — run --auth'}")
    if token:
        print(f"Account     : {token.get('name', 'unknown')}")
    print(f"This week   : {len(week_posts)}/{MAX_POSTS_PER_WEEK} posts")

    if week_posts:
        print("\nPosted this week:")
        for e in week_posts:
            print(f"  {e['posted_at'][:16]}  |  {e.get('chars','?')} chars  |  {e.get('post_id','?')}")
    print()


def cmd_post(text: str = None, filepath: str = None):
    if filepath:
        text = _read_post_file(filepath)
    if not text or not text.strip():
        print("[ERROR] Post text empty hai.")
        sys.exit(1)

    char_count = len(text)

    # Weekly limit
    log        = _load_log()
    week_posts = _posts_this_week(log)
    if len(week_posts) >= MAX_POSTS_PER_WEEK:
        print(f"\n[LIMIT] Is hafte {MAX_POSTS_PER_WEEK} posts ho chuki hain. Agli Monday ke baad karo.")
        sys.exit(1)

    print(f"\n=== POST PREVIEW ({char_count}/1300 chars) ===")
    print("-" * 50)
    print(text[:600] + ("..." if char_count > 600 else ""))
    print("-" * 50)

    confirm = input("\nPost karo? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancel.")
        return

    access_token = _get_access_token()
    member_id    = _get_member_id(access_token)

    print("LinkedIn API pe post ho rahi hai...")
    result = _post_to_linkedin(text, access_token, member_id)

    print(f"\n[OK] Post published! ID: {result['post_id']}")
    print("LinkedIn feed mein check karo.")

    log.append({
        "posted_at": datetime.now().isoformat(),
        "chars":     char_count,
        "post_id":   result["post_id"],
        "text_preview": text[:100],
    })
    _save_log(log)

    slots_left = MAX_POSTS_PER_WEEK - len(week_posts) - 1
    print(f"Is hafte {slots_left} slot(s) remaining.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    _load_env()

    parser = argparse.ArgumentParser(description="LinkedIn API Poster")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--auth",  action="store_true", help="One-time OAuth setup")
    group.add_argument("--post",  metavar="TEXT",      help="Post text directly")
    group.add_argument("--file",  metavar="FILE",      help="Post from .md file")
    group.add_argument("--check", action="store_true", help="Status check")
    args = parser.parse_args()

    if args.auth:
        cmd_auth()
    elif args.check:
        cmd_check()
    elif args.post:
        cmd_post(text=args.post)
    elif args.file:
        cmd_post(filepath=args.file)


if __name__ == "__main__":
    main()
