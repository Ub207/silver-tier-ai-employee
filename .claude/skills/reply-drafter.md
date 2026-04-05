# Skill: reply-drafter
Generates 3 context-aware WhatsApp reply options based on message analysis.

## Trigger
Called by `wa-message-processor` (Step 4) or directly: `/reply-drafter [filename]`

## Input
- Original message content
- Sender name
- Classification flags (URGENT, INVOICE, FINANCIAL_FLAG, etc.)
- Company_Handbook.md tone rules

---

## Instructions

### 1. Read tone rules from Company_Handbook.md
Key rules to apply:
- Always greet by name
- Warm but concise — no long paragraphs
- Acknowledge urgency before giving a timeline
- Invoice/payment: confirm receipt + give resolution timeline
- Flag amounts > PKR 10,000 for human attention

### 2. Analyze the message context
- What is the sender asking/reporting?
- What's the urgency level?
- Is there a financial element?
- What information is the sender expecting in the reply?

### 3. Generate 3 reply options

**Option A — Professional / Formal:**
- Formal greeting, acknowledges the specific issue, commits to a timeline
- Best for: first-time clients, formal relationships, high-stakes issues
- Format: "Hi [Name], [acknowledgement]. [Action commitment]. [Timeline]."

**Option B — Friendly / Warm (Recommended for repeat clients):**
- Casual greeting matching sender's tone (e.g., "Bhai" if they used it), empathetic, action-oriented
- Best for: established relationships, repeat clients
- Format: "[Bhai/Name], [acknowledgement]. [Action]. [Timeline or reassurance]."

**Option C — Defer / Buy Time:**
- Politely acknowledges, explains you're busy/checking, gives specific callback time
- Best for: when you need time to verify before committing
- Format: "Hi [Name], got your message. [Reason for delay]. Will [action] by [specific time]."

### 4. For FINANCIAL_FLAG messages
Add a 4th option:
**Option D — Escalation / Confirmation Request:**
- Ask for invoice number/amount to pull records before committing to resolution
- Format: "Hi [Name], on it! Can you send the invoice number so I can pull it up quickly? Will sort this today."

### 5. Output format
Return the options in this block (used by wa-message-processor to embed in Pending_Approval file):

```
### Reply Options for [filename]

**Option A — Professional:**
> [reply text]

**Option B — Friendly (Recommended):**
> [reply text]

**Option C — Defer:**
> [reply text]

**Option D — Escalation (for invoice/payment):**  ← only if FINANCIAL_FLAG
> [reply text]

---
💡 Recommendation: Option [B/D] — [one sentence reason]
```

## Notes
- NEVER fabricate specifics (amounts, dates, names) the sender didn't provide
- Use [TIME] or [TODAY 5PM] as placeholders for human to fill before sending
- Match the sender's language register (if they write informally, B/D options should too)
- Always keep replies under 300 characters when possible (WhatsApp readability)
