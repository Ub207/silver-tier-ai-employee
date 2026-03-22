Process WhatsApp action files from /Needs_Action and create reply plans.

## Instructions

### Step 1 — Call /plan-creator first
Before processing anything, invoke plan-creator with context "WhatsApp Processing Run $DATE".

### Step 2 — Scan for WA files
Read all `.md` files in `silver_tier/Needs_Action/` where `type: whatsapp` in frontmatter.
List each file with: filename, `from`, `received`, `priority`.

### Step 3 — For each WA file, generate 3 reply options

Analyse the message snippet and suggest:
- **Option A — Professional**: Formal, brief, confirms receipt + timeline
- **Option B — Friendly**: Warm, conversational, matches the tone of the message
- **Option C — Defer**: Politely delays, gives a specific time to follow up

Format:
```
### [filename]
**From:** [contact]
**Message:** [snippet]

**Option A (Professional):**
> [reply text]

**Option B (Friendly):**
> [reply text]

**Option C (Defer):**
> [reply text]
```

### Step 4 — Route to Pending_Approval
For every file with `priority: high`:
1. Create `silver_tier/Pending_Approval/WA_REPLY_[original_filename]` with:
   - Original message details
   - All 3 reply options
   - Checkbox: `- [ ] Approved reply: ` (human fills in which option)
2. Update the original file's frontmatter: `status: awaiting_approval`

### Step 5 — Update Dashboard.md
Rewrite the **Pending WhatsApp Messages** table in `silver_tier/Dashboard.md` with current items.

## Notes
- Never send any reply — only draft and route to approval
- If `status: approved` already exists in a file, skip it
- Call this skill: `/whatsapp-processor`
