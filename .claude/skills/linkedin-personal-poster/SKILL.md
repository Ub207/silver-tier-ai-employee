# Skill: linkedin-personal-poster

Generates value-first LinkedIn posts for your **personal profile**, routes to
Pending_Approval first, and opens the composer only after human moves the file to Approved/.

## Trigger
- `/linkedin-personal-poster` — generate a new post draft
- `/linkedin-personal-poster post [filename]` — open composer for an approved file
- `/linkedin-personal-poster check` — show this week's post count

---

## Hard Rules (Never Break)
- Max **2 posts per week** (Mon–Sun). Stop if limit reached.
- Draft ALWAYS goes to Pending_Approval first.
- Human moves file to Approved/ — only then call `--post`.
- Human clicks "Post" in browser — AI never auto-posts.
- Every post must teach something useful (value-first, not promotion).

---

## Step 1 — Check Weekly Limit

Run:
```
python linkedin_personal_mcp.py --check
```

If 2 posts already made this week, print:
```
WEEKLY LIMIT REACHED (2/2).
Next slot opens Monday. Review approved drafts for next week.
```
And STOP.

---

## Step 2 — Read Context

Read these files before generating:
- `silver_tier/Business_Goals.md` — pillars, tone, audience, active offers
- `silver_tier/Company_Handbook.md` — LinkedIn rules
- Last 2 files in `silver_tier/LinkedIn_Drafts/` — avoid repeating topics

**Content pillar rotation** (cycle in order):
1. AI Automation — practical how-tos, before/after results
2. Founder Productivity — systems, SOPs, time-saving
3. Client Case Studies — anonymised wins and lessons

Check the last draft's frontmatter `pillar:` field to pick the next one.

---

## Step 3 — Generate Post

Write ONE LinkedIn post following these rules:

| Element | Rule |
|---------|------|
| Hook (line 1) | Bold claim, surprising stat, or direct question — max 12 words |
| Body | 3–5 short paragraphs, 1–3 sentences each, teach ONE insight |
| CTA (last line) | Comment / share / DM ask — never "I'm excited to share" |
| Length | Max 1300 characters |
| Hashtags | Max 3, at the very end |
| Tone | Direct, no fluff, honest, no hype |
| Format | Short paragraphs with blank lines between (LinkedIn readability) |

**DO NOT:**
- Fabricate client names, numbers, or results
- Use more than 3 hashtags
- Start with "I'm excited..." or "Proud to share..."
- Self-promote without giving value first

---

## Step 4 — Save Draft

Write to `silver_tier/LinkedIn_Drafts/LI_PERSONAL_[YYYYMMDD_HHMM]_[slug].md`:

```markdown
---
type: linkedin_post_personal
created: [YYYY-MM-DD HH:MM:SS]
status: draft
pillar: [AI Automation | Founder Productivity | Client Case Study]
characters: [N]
week: [YYYY-WNN]
---

[post content here — plain text, exactly as it will appear on LinkedIn]

---

## Approval Checklist
- [ ] Hook grabs attention in the first line
- [ ] Teaches something useful (value-first)
- [ ] CTA is clear and not salesy
- [ ] Under 1300 characters ([N]/1300)
- [ ] Not a repeat topic from last post
- [ ] Approved to post on personal profile

## To Post
1. Move this file to `silver_tier/Approved/`
2. Run: `python linkedin_personal_mcp.py --post [filename]`
3. Review in browser, then click 'Post'
```

---

## Step 5 — Route to Pending_Approval

Copy the same file to `silver_tier/Pending_Approval/` with `status: awaiting_approval`.

Print confirmation:
```
=== LinkedIn Personal Draft Ready ===
Draft:   silver_tier/LinkedIn_Drafts/[filename]
Pending: silver_tier/Pending_Approval/[filename]
Chars:   [N]/1300
Pillar:  [content pillar]
Week:    [YYYY-WNN]

Next steps:
  1. Review in Obsidian (Pending_Approval/)
  2. Move to Approved/ if happy
  3. Run: python linkedin_personal_mcp.py --post [filename]
=====================================
```

---

## Step 6 — Posting Flow (after human approval)

Human has moved file to `Approved/`. Now run:
```
python linkedin_personal_mcp.py --post [filename]
```

What happens:
- Weekly limit re-checked (blocks if 2/2 already posted)
- Browser opens with saved LinkedIn session
- Post pre-filled in composer
- Human reviews, edits if needed, clicks 'Post'
- On browser close: file moves to Done/, entry logged in Approval_Log.md

---

## First-Time Setup

If `silver_tier/linkedin_session/` doesn't exist or is empty:
```
python linkedin_personal_mcp.py --setup
```
Opens browser → user logs in manually → session saved → close browser.

---

## Notes
- Session stored at `silver_tier/linkedin_session/`
- Weekly post count tracked in `.linkedin_post_log.json` (project root)
- After posting, file moves: `Approved/` → `Done/`
- All posts logged in `Approval_Log.md`
