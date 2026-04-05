# Skill: linkedin-company-poster

Generates professional, value-first LinkedIn posts for the **Company Page**,
routes to Pending_Approval for human review, then uses Playwright to open the
company page composer with text pre-filled. Human always clicks "Post".

## Trigger
- `/linkedin-company-poster` — generate a new company post draft
- `/linkedin-company-poster post [filename]` — open composer for an approved file
- `/linkedin-company-poster check` — show weekly count + approved queue

---

## Hard Rules (Never Break)
- Always post on the **Company Page**, not the personal profile.
- Max **2 posts per week** (Mon–Sun) — enforced by `linkedin_company_mcp.py`.
- Draft always goes to `Pending_Approval/` first — never skip.
- Human moves to `Approved/` — only then call `--post`.
- Human clicks "Post" in browser — AI **never** auto-posts.
- Value-first only. No promotional content without an insight.
- Never tag individuals without permission.

---

## Step 1 — Check Weekly Limit

Run:
```
python linkedin_company_mcp.py --check
```

If 2 posts already made this week, print:
```
WEEKLY LIMIT REACHED (2/2).
Next slot opens Monday. Save this draft for next week.
```
And STOP.

---

## Step 2 — Read Context

Read these files before generating:
- `silver_tier/Business_Goals.md` — content pillars, value proposition, audience, tone
- `silver_tier/Company_Handbook.md` — LinkedIn company rules
- Last 2 files in `silver_tier/LinkedIn_Drafts/` matching `LI_CO_*.md` — avoid repeating topics

**Content pillar rotation** (cycle in this exact order):
1. AI Automation — practical results, before/after, system walkthroughs
2. Founder Productivity — delegation, SOPs, time-saving frameworks
3. Client Success — anonymised case studies, wins, lessons

Check the last `LI_CO_*.md` draft's `pillar:` frontmatter field to pick the next pillar.

---

## Step 3 — Generate Post

Write ONE company-voice LinkedIn post:

| Element | Rule |
|---------|------|
| Voice | "We", "Our clients", "Here's what we do" — company, not personal |
| Hook (line 1) | Bold claim, surprising stat, or problem statement — max 12 words |
| Body | 3–5 short paragraphs, 1–3 sentences each, ONE core insight |
| CTA | Comment / DM / share ask — not "Check out our services" |
| Length | Max 1300 characters (hard limit 3000) |
| Hashtags | Max 3 at the very end |
| Tone | Professional but approachable — direct, no hype, no jargon |

**DO NOT:**
- Use "We're thrilled to announce..." or "Excited to share..."
- Add more than 3 hashtags
- Write pure product promotion without a useful insight
- Fabricate client data, metrics, or names
- Start post body paragraphs with "I" (this is a company page)

---

## Step 4 — Save Draft

Write to `silver_tier/LinkedIn_Drafts/LI_CO_[YYYYMMDD_HHMM]_[slug].md`:

```markdown
---
type: linkedin_company_post
created: [YYYY-MM-DD HH:MM:SS]
status: draft
pillar: [AI Automation | Founder Productivity | Client Success]
characters: [N]
week: [YYYY-WNN]
image: none
---

[post content — plain text exactly as it will appear on LinkedIn]

---

## Approval Checklist
- [ ] Company voice ("we", not "I")
- [ ] Hook grabs attention in the first line
- [ ] Teaches something useful — value before promotion
- [ ] CTA is clear, not salesy
- [ ] Under 1300 characters ([N]/1300)
- [ ] Not a repeat topic from last company post
- [ ] Image needed? If yes, add path to `image:` frontmatter field
- [ ] Approved to post on Company Page

## To Post
1. Move this file to `silver_tier/Approved/`
2. Run: `python linkedin_company_mcp.py --post [filename]`
   (Optional with image): `python linkedin_company_mcp.py --post [filename] --image path/to/image.png`
3. Review in browser, then click 'Post'
```

---

## Step 5 — Route to Pending_Approval

Copy file to `silver_tier/Pending_Approval/` with `status: awaiting_approval`.

Print:
```
=== LinkedIn Company Draft Ready ===
Draft:   silver_tier/LinkedIn_Drafts/[filename]
Pending: silver_tier/Pending_Approval/[filename]
Chars:   [N]/1300
Pillar:  [content pillar]
Week:    [YYYY-WNN]

Next steps:
  1. Review in Obsidian (Pending_Approval/)
  2. Move to Approved/ when ready
  3. Run: python linkedin_company_mcp.py --post [filename]
=====================================
```

---

## Step 6 — Posting Flow (after human approval)

Human has moved file to `Approved/`. Now run:
```
python linkedin_company_mcp.py --post [filename]
```
With optional image:
```
python linkedin_company_mcp.py --post [filename] --image silver_tier/assets/image.png
```

What happens:
1. Weekly limit re-checked (blocks if 2/2)
2. Browser opens with saved company session
3. Navigates to Company Page admin → Create a post
4. Falls back to Feed → Start a post → switches identity to company page
5. Text (and image if provided) pre-filled in composer
6. Human reviews, edits if needed, clicks 'Post'
7. On browser close: file moves to `Done/`, entry logged in `Approval_Log.md`

---

## First-Time Setup

If `silver_tier/linkedin_company_session/` doesn't exist or is empty:
```
python linkedin_company_mcp.py --setup
```
Also set in `.env`:
```
LINKEDIN_COMPANY_SLUG=your-company-url-slug
LINKEDIN_COMPANY_NAME=Your Company Name
```

---

## Notes
- Session: `silver_tier/linkedin_company_session/`
- Weekly count: `.linkedin_company_post_log.json`
- Company slug is the part after `/company/` in your LinkedIn URL
- If identity switcher is not available, navigate to company admin page manually
- All posts logged in `Approval_Log.md`
- File prefix: `LI_CO_` (distinct from personal `LI_PERSONAL_`)
