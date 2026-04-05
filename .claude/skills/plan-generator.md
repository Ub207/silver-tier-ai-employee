# Skill: plan-generator
Creates a structured Plan.md with checkboxes for the complete WA reply flow.

## Trigger
Called by `wa-message-processor` (Step 3) or directly: `/plan-generator [context]`

## Input
Receives (from caller or user):
- `sender`: contact name
- `message`: original message text
- `flags`: array of classification flags (URGENT, INVOICE, FINANCIAL_FLAG, etc.)
- `source_file`: original WA_*.md filename

---

## Instructions

### 1. Generate plan path
```
silver_tier/Plans/PLAN_wa_[sender_slug]_[YYYYMMDD_HHMMSS].md
```
Slug: lowercase sender name, spaces → underscores, max 20 chars.

### 2. Write the Plan.md

```markdown
# Plan: WhatsApp Reply — [Sender]
*Created: [TIMESTAMP]*
*Source: [source_file]*

## Message Summary
**From:** [sender]
**Received:** [datetime]
**Classification:** [URGENT / INVOICE / PAYMENT / REPLY_NEEDED / FINANCIAL_FLAG]
**Message:** "[message snippet]"

## Goal
Draft, approve, and send a context-appropriate WhatsApp reply to [sender].

## Steps
- [ ] 1. Analyze message content and classify (urgent? invoice? payment?)
- [ ] 2. Draft 3 reply options via /reply-drafter
- [ ] 3. Route draft to /Pending_Approval for human review
- [ ] 4. Human selects/customizes reply and marks approved
- [ ] 5. Call /whatsapp-sender-mcp to open WhatsApp Web and pre-fill reply
- [ ] 6. Human confirms and clicks Send
- [ ] 7. Move WA_*.md from /Needs_Action to /Done
- [ ] 8. Update Dashboard.md with resolved count

## Expected Output
`Pending_Approval/WA_reply_[source_file]` — approved reply ready to send via WhatsApp Web.

## Requires Approval
**Yes** — Step 4 requires human selection before any send action.

## Risks / Notes
[If FINANCIAL_FLAG]: ⚠️ Invoice/payment message — confirm amounts before sending. Flag if > PKR 10,000.
[If URGENT]: Response within 2 hours expected (10am–7pm IST window).
- Always greet by name
- Never auto-send — human must click Send in WhatsApp Web
```

### 3. Print the plan path so the calling skill can reference it.

### 4. Do NOT proceed with execution — only create the plan and return.

## Usage
- Called by `/wa-message-processor` automatically
- Direct call: `/plan-generator "WhatsApp reply to Rahul — invoice follow-up"`
