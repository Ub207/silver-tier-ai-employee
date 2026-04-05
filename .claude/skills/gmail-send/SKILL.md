# Skill: Gmail Send

## Metadata

| Field          | Value                                    |
|----------------|------------------------------------------|
| Skill Name     | Gmail Send                               |
| Invoked As     | `/gmail-send`                            |
| Category       | Communication / Email                    |
| Script         | `scripts/send_email.py`                  |
| Requires Env   | `EMAIL_ADDRESS`, `EMAIL_PASSWORD`        |

---

## Description

Sends a real email via Gmail SMTP (TLS on port 587).
Reads credentials from environment variables — never hardcoded.
Supports plain-text and HTML bodies. Returns a clear success or error message.

---

## Required Environment Variables

Set these in your `.env` file before invoking:

```
EMAIL_ADDRESS=you@gmail.com
EMAIL_PASSWORD=your_app_password
```

> Use a Gmail App Password (not your account password).
> Enable 2FA on your Google account, then generate an App Password at
> myaccount.google.com/apppasswords.

---

## Inputs

| Argument    | Flag          | Required | Description                        |
|-------------|---------------|----------|------------------------------------|
| Recipient   | `--to`        | Yes      | Email address to send to           |
| Subject     | `--subject`   | Yes      | Email subject line                 |
| Body        | `--body`      | Yes      | Email body (plain text or HTML)    |
| CC          | `--cc`        | No       | CC recipient(s), comma-separated   |
| HTML mode   | `--html`      | No       | Flag: treat body as HTML           |

---

## Workflow

1. Load `EMAIL_ADDRESS` and `EMAIL_PASSWORD` from environment / `.env`
2. Validate all required inputs are present
3. Build the MIME email message
4. Connect to `smtp.gmail.com:587` with STARTTLS
5. Authenticate and send
6. Print success confirmation with timestamp
7. On any error, print a clear error message and exit with code 1

---

## Usage

```bash
python scripts/send_email.py \
  --to client@example.com \
  --subject "Invoice #1042 Follow-up" \
  --body "Hi, just following up on the invoice sent last week."
```

```bash
python scripts/send_email.py \
  --to client@example.com \
  --cc manager@example.com \
  --subject "Meeting Confirmation" \
  --body "<h2>Confirmed</h2><p>See you Thursday at 3PM.</p>" \
  --html
```

---

## Output

Success:
```
[OK] Email sent to client@example.com
     Subject : Invoice #1042 Follow-up
     From    : you@gmail.com
     Sent at : 2026-03-07 09:15:42
```

Failure:
```
[ERROR] Authentication failed — check EMAIL_ADDRESS and EMAIL_PASSWORD
Exit code: 1
```

---

## Rules and Constraints

- Never hardcode credentials in the script
- Always use TLS — do not fall back to plain SMTP
- Validate the `--to` address format before attempting to send
- If `EMAIL_ADDRESS` or `EMAIL_PASSWORD` is missing, exit with code 1 and a clear message
- Do not retry on failure — report the error and stop
