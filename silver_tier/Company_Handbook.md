# Company Handbook
*Last updated: 2026-03-04 — Silver Tier*

---

## Communication Protocols

### WhatsApp — Primary Real-Time Channel
**Rule: Polite, quick replies. Always respond within 2 hours during business hours.**

- WhatsApp is the #1 channel for urgent client communication
- Keywords that trigger auto-detection: `urgent`, `asap`, `invoice`, `payment`, `help`, `bhai`, `due`, `pending`, `follow up`
- Watcher polls every 3 minutes — action files appear in `/Needs_Action` automatically
- **Tone rules:**
  - Always greet by name if known
  - Be warm but concise — no long paragraphs on WhatsApp
  - Acknowledge the urgency before giving a timeline: "Got it, Rahul — I'll check and get back by 5pm"
  - Never leave a client on read for >2 hours between 10am–7pm IST
  - For payment/invoice messages: confirm receipt immediately, provide timeline for resolution
  - **Always polite and quick — acknowledge before acting**
  - **Confirm before sending any money-related replies**
  - **Flag any invoice or payment discussion where amount is unknown or exceeds PKR 10,000 — secondary approval required**
- **All replies are drafted by AI and require human approval before sending**
- Draft approval process: `/Needs_Action` → `/Pending_Approval` → human approves → `/whatsapp-sender-mcp` pre-fills → human sends manually
- **PKR Rule:** Any WhatsApp message referencing payments, invoices, or transfers where the amount cannot be confirmed as < PKR 10,000 must be escalated for secondary human approval before any reply is sent.

### Email — Formal Channel
- Use for contracts, project briefs, invoices (full PDF), and formal proposals
- Check every 3 hours
- Reply within 24 hours for non-urgent, 4 hours for flagged important

### LinkedIn — Thought Leadership Channel

> **Primary:** Always post on the **Company Page** first. Personal profile posts are secondary/supplementary.
> **Tool:** Playwright-based automation. Human always clicks "Post" — never auto-posted.

#### Company Page Rules
**Rule: Max 2 posts per week on Company Page. Value-first only. Never too salesy. Always get human approval before posting.**

- Posts published under the company brand ("we", "our clients", "our work")
- **Company page slug** must be set in `.env`: `LINKEDIN_COMPANY_SLUG=your-slug`
- **Post frequency:** Max 2 per week (Mon–Sun). Tracked in `.linkedin_company_post_log.json`.
- **Content pillars** (rotate in order, never repeat back-to-back):
  1. AI Automation — practical results, system walkthroughs, before/after
  2. Founder Productivity — delegation, SOPs, time-saving frameworks
  3. Client Success — anonymised wins, lessons, transformations
- **Post structure:** Hook → Insight (3–5 paragraphs) → CTA
- **Character limit:** 1300 recommended, 3000 hard max
- **Optional image:** Set `image: path/to/file.png` in post frontmatter
- **No:**
  - "We're thrilled to announce..." or "Excited to share..." openers
  - More than 3 hashtags
  - Pure promotional content without a useful insight
  - Auto-posting — human **always** clicks "Post" in browser
  - Fabricated client data, metrics, or names
  - Tagging individuals without permission
- **Draft workflow:** `/linkedin-company-poster` → `LinkedIn_Drafts/LI_CO_*.md` → `Pending_Approval/` → human reviews → moves to `Approved/` → `python linkedin_company_mcp.py --post [filename]` → browser opens → human clicks Post

#### Personal Profile Rules (Secondary)
**Rule: Max 2 posts per week. Always educational/value-add. Draft → Pending_Approval → Approved → then only post.**

> Personal profile posts supplement the company page. Write in first person ("I", "my clients").

- Every post must teach the reader something useful — even if they never hire you
- **Post frequency:** Maximum **2 posts per week** (Mon–Sun). Consistency over volume.
- **Content pillars** (rotate in order, never repeat back-to-back):
  1. AI Automation — practical how-tos, before/after results
  2. Founder Productivity — systems, SOPs, delegation tips
  3. Client Stories — anonymised wins and lessons learned
- **Post structure:** Hook (1 line) → Insight (3–5 short paragraphs) → CTA
- **Character limit:** 1300 recommended, 3000 hard max
- **No:**
  - "I'm excited to announce..." or "Proud to share..." openers
  - More than 3 hashtags
  - Pure self-promotion without value first
  - Auto-posting — human **always** clicks "Post" in browser
  - Fabricated stats, names, or results
- **Draft workflow:** `/linkedin-personal-poster` → `LinkedIn_Drafts/` → `Pending_Approval/` → human reviews → human moves to `Approved/` → `python linkedin_personal_mcp.py --post [filename]` → browser pre-filled → human clicks Post
- **Personal profile rules:**
  - Write in first person ("I", "my clients", "we built")
  - Reflect real experience — no hypotheticals presented as facts
  - Comments and DMs must be handled manually (AI does not respond to LinkedIn messages)
  - Never tag people or companies without permission
- **Weekly tracking:** Post count tracked in `.linkedin_post_log.json`. Run `python linkedin_personal_mcp.py --check` to see slots remaining.

---

## Workflow Rules

### Plan First — No Exceptions
Every action (reply, post, invoice follow-up) starts with a `Plan.md`.
No execution without a plan on record in `/Plans`.

### Human-in-the-Loop — Mandatory Approval For:
| Action | Approval Required |
|--------|------------------|
| WhatsApp reply (any) | Yes |
| LinkedIn post | Yes |
| Email reply to client | Yes |
| Invoice follow-up message | Yes |
| Creating/editing files in vault | No |
| Generating drafts | No |
| Updating Dashboard | No |

### Approval Flow
```
/Needs_Action  →  workflow_runner.py  →  /Pending_Approval
                                               ↓
                                       /approval-handler skill
                                               ↓
                              /Approved (send manually) or /Rejected
```

### File & Folder Conventions
| Prefix/Folder | Meaning |
|---------------|---------|
| `WA_` | WhatsApp message action |
| `EMAIL_` | Email action |
| `DROP_` | Manually dropped task |
| `PLAN_` | Execution plan |
| `LI_` | LinkedIn draft |
| `/Needs_Action` | Incoming items to process |
| `/Pending_Approval` | Awaiting human decision |
| `/Approved` | Approved — ready to send manually |
| `/Rejected` | Rejected with reason |
| `/Done` | Processed and sent — archived |
| `/Plans` | All plan documents |
| `/LinkedIn_Drafts` | LinkedIn post drafts |

---

## Tools & Stack

| Tool | Purpose |
|------|---------|
| Playwright | WhatsApp Web monitoring, LinkedIn draft assist |
| Watchdog | Filesystem change detection |
| Claude Code | AI skill execution (skills in `.claude/skills/`) |
| Obsidian | Vault, knowledge base, daily notes |
| PM2 / run_all.py | Process management for watchers |

---

## Agent Skills Reference

| Skill | Command | What it does |
|-------|---------|-------------|
| Plan Creator | `/plan-creator` | Creates Plan.md before any action (legacy) |
| WhatsApp Processor | `/whatsapp-processor` | Analyses WA files, generates 3 reply options (legacy) |
| LinkedIn Poster | `/linkedin-poster` | Generates value-first post from Business_Goals.md (legacy) |
| Approval Handler | `/approval-handler` | Moves items to /Approved or /Rejected, logs decision |
| **WA Message Processor** | `/wa-message-processor` | Full WA pipeline: analyze → plan → draft → route to approval |
| **Plan Generator** | `/plan-generator` | Creates structured Plan.md with full WA flow checkboxes |
| **Reply Drafter** | `/reply-drafter` | Generates 3–4 context-aware reply options per message |
| **Approval Checker** | `/approval-checker` | Checks /Pending_Approval, triggers send flow, moves to /Done |
| **WhatsApp Sender MCP** | `/whatsapp-sender-mcp` | Generates Playwright snippet to pre-fill WhatsApp Web reply |
| **LinkedIn Personal Poster** | `/linkedin-personal-poster` | Personal profile posts, max 2/week, full approval flow |
| **LinkedIn Company Poster** | `/linkedin-company-poster` | Company page posts, max 2/week, Playwright composer, optional image support |

---

## Silver Tier — What's Automated vs Manual

| Task | Automated | Manual |
|------|-----------|--------|
| Detect urgent WhatsApp | Yes (watcher) | — |
| Analyze & classify message | Yes (/wa-message-processor) | — |
| Create Plan.md with flow | Yes (/plan-generator) | — |
| Draft 3–4 reply options | Yes (/reply-drafter) | — |
| Route to Pending_Approval | Yes (workflow) | — |
| Approve / reject items | No | Human reviews + decides |
| Pre-fill WhatsApp Web reply | Yes (/whatsapp-sender-mcp) | — |
| Send reply | No | Human clicks Send |
| Move to /Done | Yes (approval-checker) | — |
| Generate LinkedIn post (company) | Yes (/linkedin-company-poster) | — |
| Generate LinkedIn post (personal) | Yes (/linkedin-personal-poster) | — |
| Enforce 2-post/week limit | Yes (both MCP scripts) | — |
| Open company page composer | Yes (linkedin_company_mcp.py) | — |
| Post to LinkedIn | No | Human clicks Post in browser |
| Create Plan.md | Yes (workflow) | — |
| Update Dashboard | Yes (workflow) | — |
| Financial flag (>PKR 10k) | Yes (auto-detect) | Human gives secondary approval |
