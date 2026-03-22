Move items from /Pending_Approval to /Approved or /Rejected and update tracking.

## When to Call
Call this skill when the user says "approve", "reject", "done", or after reviewing
a file in `silver_tier/Pending_Approval/`.

## Instructions

### Step 1 — List pending items
Read all `.md` files in `silver_tier/Pending_Approval/`.
Show a table:

| # | File | Type | From/Topic | Created | Action Needed |
|---|------|------|------------|---------|---------------|

If empty: report "No items pending approval."

### Step 2 — Process the decision

**On APPROVE:**
1. Read the approval file to extract the approved reply/post/action
2. Move file to `silver_tier/Approved/[filename]`
3. Update frontmatter: `status: approved`
4. Update the original source file in `Needs_Action/` (if it exists): `status: approved`
5. If type is `whatsapp_reply`:
   - Extract the chosen option text
   - Print it clearly: "READY TO SEND via WhatsApp:"
   - Remind: "Copy this and send manually in WhatsApp Web"
6. If type is `linkedin_post`:
   - Print the post text clearly
   - Remind: "Paste into LinkedIn — do not auto-post"
7. Update `silver_tier/Plans/` — tick off the approval step in the relevant Plan.md

**On REJECT:**
1. Move file to `silver_tier/Rejected/[filename]`
2. Update frontmatter: `status: rejected`
3. Ask user: "Reason for rejection? (optional)" — add as a note to the file
4. Update original source file: `status: rejected`

### Step 3 — Update Dashboard.md
Rewrite the **Pending Approvals** section to reflect the new state.

### Step 4 — Log the decision
Append a one-line entry to `silver_tier/Approval_Log.md`:
```
| {datetime} | {filename} | {approved/rejected} | {type} |
```
Create the file with header if it doesn't exist.

## Usage
- `/approval-handler` → list all pending items
- `/approval-handler approve WA_REPLY_WA_TEST_1.md` → approve specific file
- `/approval-handler reject LI_20260303_post.md` → reject specific file

## Notes
- Never auto-send messages — always print for manual sending
- Always log every decision in Approval_Log.md
- If approving a LinkedIn post, also offer to open LinkedIn in browser (ask first)
