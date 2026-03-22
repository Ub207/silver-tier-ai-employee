Generate a value-first LinkedIn post from Business_Goals.md and route for approval.

## Instructions

### Step 1 — Call /plan-creator first
Invoke plan-creator with context "LinkedIn Post - $DATE".

### Step 2 — Read Business_Goals.md
Read `silver_tier/Business_Goals.md`. Extract:
- Current quarter focus areas
- Content pillars
- Target audience
- Tone of voice

### Step 3 — Generate the post

Write a LinkedIn post using this structure:
1. **Hook** (line 1): Bold statement, surprising fact, or direct question — max 12 words
2. **Body** (3–5 short paragraphs): Teach one useful insight, use whitespace liberally
3. **CTA** (last line): One clear ask — comment, share, or DM

Rules:
- Max 1300 characters
- No hashtag spam (max 3 relevant hashtags at end)
- No "I'm excited to share..." openers
- Value-first: reader learns something even if they never contact you
- Match the tone from Business_Goals.md

### Step 4 — Save draft
Save to `silver_tier/LinkedIn_Drafts/LI_$DATE_$SLUG.md`:

```markdown
---
type: linkedin_post
created: $TIMESTAMP
status: draft
topic: [one-line topic]
---

[Full post text here]

---
## Approval Checklist
- [ ] Hook is compelling
- [ ] Teaches something useful
- [ ] CTA is clear
- [ ] Under 1300 characters
- [ ] Approved to post
```

### Step 5 — Route to Pending_Approval
Copy the draft to `silver_tier/Pending_Approval/LI_$DATE_$SLUG.md` with a note:
> "Awaiting human approval before posting to LinkedIn."

### Step 6 — Update Dashboard.md
Add entry to the **LinkedIn Drafts / Posts Today** table.

## After Approval (Manual Step)
Once human marks `- [x] Approved to post` in Pending_Approval:
- Use Playwright to open LinkedIn, navigate to create post, paste content
- **Do not click Post automatically** — leave it for human to review and submit

## Notes
- NEVER auto-post — always require explicit approval
- Call this skill: `/linkedin-poster`
- Optionally pass a topic hint: `/linkedin-poster AI automation for founders`
