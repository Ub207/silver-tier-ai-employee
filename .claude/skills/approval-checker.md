# Skill: approval-checker
Checks /Pending_Approval for approved WA items and triggers the send flow.

## Trigger
- `/approval-checker` — scan all pending items and report
- `/approval-checker send WA_reply_WA_TEST_1.md` — process a specific approval

---

## Step 1 — Scan Pending_Approval
Read all `WA_reply_*.md` files in `silver_tier/Pending_Approval/`.
Show status table:

| # | File | From | Priority | Status | Approved Option |
|---|------|------|----------|--------|----------------|

Determine approval state:
- `status: awaiting_approval` → WAITING
- `status: approved` → READY TO SEND (call /whatsapp-sender-mcp)
- `status: rejected` → REJECTED (move to /Rejected)

---

## Step 2 — Process APPROVED items

For each file with `status: approved`:

1. **Extract the approved reply text:**
   - Look for `- [x] Approved reply: [A / B / C / D / Custom]` checkbox
   - If Custom, extract the text below `> ` in the Custom reply section
   - If A/B/C/D, extract that option's text from the Reply Options section

2. **Financial safety check:**
   - If original message had FINANCIAL_FLAG and no human has confirmed amount → print warning:
     ```
     ⚠️  FINANCIAL FLAG: This message involves an invoice/payment.
         Confirm the amount does NOT exceed PKR 10,000 before sending.
         If > PKR 10,000, this reply needs secondary approval.
     ```
   - Pause and ask human to confirm: "Confirmed amount is under PKR 10,000? (yes/no)"

3. **Print the approved reply clearly:**
   ```
   === READY TO SEND ===
   To: [sender name] on WhatsApp
   Reply:
   "[approved reply text]"
   ====================
   ```

4. **Call /whatsapp-sender-mcp** with the approved reply text and sender name.

5. **Move files:**
   - Move `Pending_Approval/WA_reply_*.md` → `Approved/WA_reply_*.md`
   - Move `Needs_Action/WA_*.md` → `Done/WA_*.md`
   - Update frontmatter `status: done` in both files

6. **Tick off Plan.md checkboxes:**
   - Read the referenced `Plans/PLAN_*.md`
   - Mark steps 3, 4, 5 as `[x]` (routed → approved → sent)

7. **Log to Approval_Log.md:**
   ```
   | [datetime] | [filename] | approved | whatsapp_reply | [sender] |
   ```

---

## Step 3 — Process REJECTED items

For each file with `status: rejected`:
1. Move to `Rejected/WA_reply_*.md`
2. Ask user: "Reason for rejection? (optional)" — append as note
3. Update original Needs_Action file: `status: rejected`
4. Log to Approval_Log.md

---

## Step 4 — Update Dashboard
Rewrite Pending Approvals table and Pending WhatsApp Messages table to reflect current state.

---

## Usage
- `/approval-checker` → list all pending WA items and their status
- `/approval-checker send WA_reply_WA_TEST_1.md` → process that specific approval
- `/approval-checker reject WA_reply_WA_TEST_1.md` → reject and move to /Rejected

## Notes
- Never auto-send — always print reply text and wait for human confirmation via /whatsapp-sender-mcp
- Always verify financial flag before triggering send
- Always log every decision in Approval_Log.md
