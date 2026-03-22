"""
gmail_auth.py — One-time OAuth flow to generate token.json
Run this ONCE after placing credentials.json in vault root.
After success, token.json will be created here — keep it safe!
"""

import os
import sys
from pathlib import Path

# ── Dependency check ─────────────────────────────────────────────────────────
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("ERROR: Missing Google auth libraries.")
    print("Run:  pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']  # read + archive

VAULT_ROOT    = Path(__file__).parent          # same folder as this script
CREDS_FILE    = VAULT_ROOT / 'credentials.json'
TOKEN_FILE    = VAULT_ROOT / 'token.json'

# ── Guards ────────────────────────────────────────────────────────────────────
if not CREDS_FILE.exists():
    print(f"\nERROR: credentials.json not found at:\n  {CREDS_FILE}")
    print("\nSteps:")
    print("  1. Go to https://console.cloud.google.com/apis/credentials")
    print("  2. Download your OAuth 2.0 Client ID JSON")
    print("  3. Save it as  credentials.json  in this folder")
    sys.exit(1)

# ── Auth flow ─────────────────────────────────────────────────────────────────
creds = None

if TOKEN_FILE.exists():
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        print("Refreshing expired token...")
        creds.refresh(Request())
    else:
        print("Opening browser for Google sign-in...")
        print("(A local server on a random port will handle the callback)\n")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    print(f"\ntoken.json saved to: {TOKEN_FILE}")

# ── Verify ────────────────────────────────────────────────────────────────────
print("\n--- Verification ---")
print(f"  Scopes granted : {creds.scopes}")
print(f"  Token valid    : {creds.valid}")
print(f"  Has refresh    : {bool(creds.refresh_token)}")
print("\nGmail credentials setup COMPLETE — gmail_watcher.py is ready to run.")
