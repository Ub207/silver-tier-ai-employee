# Skill: wa-message-processor
Orchestrates the full WhatsApp message → reply → approval → send pipeline.

## Trigger
Call when a new `WA_*.md` appears in `silver_tier/Needs_Action/` or user runs `/wa-message-processor`.

## Ralph Wiggum Loop
Iterate through every step below until ALL items in Needs_Action are processed. Do not stop early.

---

## Step 1 — Scan Needs_Action
Read all `WA_*.md` files in `silver_tier/Needs_Action/`.
For each file, extract:
- `from:` (sender name)
- `received:` (timestamp)
- `priority:` (high / normal)
- `status:` (skip if already `awaiting_approval`, `approved`, or `done`)
- Full message body / snippet

Print a summary table:
```
| File | From | Priority | Status | Message snippet |
```

---

## Step 2 — Analyze Each Message
For each unprocessed file, classify:

| Check | Flag if... |
|-------|-----------|
| URGENT | message contains: urgent, asap, emergency, kal tak, today |
| INVOICE/PAYMENT | message contains: invoice, payment, bill, amount, PKR, rupees, money |
| REPLY_NEEDED | any question, request, or complaint |
| FINANCIAL_FLAG | invoice/payment AND cannot confirm amount < PKR 10,000 |
| DEFER_OK | message is informational only |

Print analysis result per file.

---

## Step 3 — Call /plan-generator
Invoke `plan-generator` skill for each message, passing:
- sender name
- message content
- classification flags from Step 2

---

## Step 4 — Call /reply-drafter
Invoke `reply-drafter` skill to generate 3 reply options tailored to the message context.

---

## Step 5 — Route to Pending_Approval
Create `silver_tier/Pending_Approval/WA_reply_[original_filename]` with:
- Frontmatter (type, from, priority, status: awaiting_approval, plan reference)
- Original message quoted
- Classification analysis
- 3 reply options (A/B/C) from reply-drafter
- Financial flag warning if applicable
- Approval checkbox

Update `status:` in original Needs_Action file to `awaiting_approval`.

---

## Step 6 — Update Dashboard
Call `update_dashboard` logic: rewrite Pending WhatsApp Messages table with current Needs_Action counts and Pending Approvals section.

---

## Step 7 — Report
Print final status:
```
=== WA Processing Complete ===
Files processed: N
Routed to Pending_Approval: N
Financial flags raised: N
Pending human approval: N
==============================
```

## Notes
- NEVER send any reply — only draft and route
- Always re-read the original file before generating reply (do not hallucinate content)
- If financial flag is raised, add bold warning in the Pending_Approval file
- Skip files with status: awaiting_approval, approved, or done
