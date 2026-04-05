# Skill: LinkedIn Post

## Metadata

| Field          | Value                                          |
|----------------|------------------------------------------------|
| Skill Name     | LinkedIn Post                                  |
| Invoked As     | `/linkedin-post`                               |
| Category       | Social Media / Content                         |
| Script         | `scripts/post_linkedin.py`                     |
| Requires Env   | `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`          |
| Requires Pkg   | `playwright` (`python -m playwright install chromium`) |

---

## Description

Creates a real LinkedIn text post using Playwright browser automation.
Logs in with your LinkedIn credentials, navigates to the feed, opens the post
composer, types the content, and submits it. Supports session reuse to avoid
repeated logins. Returns a success message or a clear error.

---

## Required Environment Variables

```
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=your_linkedin_password
```

---

## Inputs

| Argument      | Flag          | Required | Description                                      |
|---------------|---------------|----------|--------------------------------------------------|
| Post text     | `--text`      | Yes*     | The post content (plain text)                    |
| Post file     | `--file`      | Yes*     | Path to a .md or .txt file containing post text  |
| Headless      | `--headless`  | No       | Run browser headlessly (default: True)           |
| Setup/login   | `--setup`     | No       | Open browser for manual login + session save     |

*Provide either `--text` or `--file`, not both.

---

## Session Management

On first run, use `--setup` to log in manually and save the session:

```bash
python scripts/post_linkedin.py --setup
```

This opens a visible browser. Log in manually, then press Enter in the terminal.
The session is saved to `AI_Employee_Vault/linkedin_session/` and reused on future runs.

---

## Workflow

1. Load credentials and session from environment / `.env`
2. If `--setup`: open browser for manual login, save session, exit
3. Launch Playwright (headless by default, uses saved session if available)
4. Navigate to `linkedin.com/feed`
5. If not logged in: authenticate with `LINKEDIN_EMAIL` / `LINKEDIN_PASSWORD`
6. Click "Start a post" to open the composer
7. Type the post content character by character
8. Click the "Post" button to submit
9. Wait for confirmation that the post is live
10. Print success with timestamp and exit

---

## Usage

```bash
# Post from text
python scripts/post_linkedin.py --text "Excited to share our latest project update!"

# Post from file
python scripts/post_linkedin.py --file AI_Employee_Vault/LinkedIn_Drafts/LI_20260307.md

# First-time setup (save session)
python scripts/post_linkedin.py --setup
```

---

## Output

Success:
```
[OK] LinkedIn post published successfully
     Characters : 58
     Posted at  : 2026-03-07 09:30:15
```

Failure:
```
[ERROR] Could not locate post composer on LinkedIn feed
        LinkedIn may have updated their UI. Check selector in post_linkedin.py.
Exit code: 1
```

---

## Rules and Constraints

- Never hardcode credentials
- Use saved session when available — only fall back to password login if session is invalid
- Do not post if `--text` and `--file` are both provided — exit with error
- If post content exceeds 3000 characters, truncate and warn
- Always wait for the post confirmation element before reporting success
- On any unhandled error, take a screenshot to `logs/linkedin_error_<timestamp>.png`
