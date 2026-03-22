# Skill: Human Approval

## Metadata

| Field          | Value                                               |
|----------------|-----------------------------------------------------|
| Skill Name     | Human Approval                                      |
| Invoked As     | `/human-approval`                                   |
| Category       | Workflow / HITL (Human-in-the-Loop)                 |
| Script         | `scripts/approval_handler.py`                       |
| Requires Env   | None                                                |

---

## Description

Manages the human approval gate in the Silver Tier workflow.
Routes tasks to `Pending_Approval/`, reads a human decision from the task file,
and then routes the file to `Approved/` or `Rejected/` accordingly.
All decisions are recorded in `AI_Employee_Vault/Approval_Log.md`.

This is the mandatory checkpoint between AI planning and real-world execution.
No external action (email, WhatsApp, LinkedIn post) should be taken without
passing through this gate first.

---

## Inputs

| Argument       | Flag           | Required | Description                                              |
|----------------|----------------|----------|----------------------------------------------------------|
| Action         | `--action`     | Yes      | `submit`, `check`, `approve`, `reject`, or `list`        |
| File name      | `--file`       | Yes*     | The task file to act on                                  |
| Reason         | `--reason`     | No       | Optional reason (for reject) or note (for approve)       |
| Dry run        | `--dry`        | No       | Preview without writing                                  |

*Required for all actions except `list`.

---

## Actions

### `submit` — Send a task to Pending_Approval

Moves a file from any vault folder into `Pending_Approval/` and sets
`status: awaiting_approval` in its frontmatter. Use this after a plan has been
created and is ready for human review.

```bash
python scripts/approval_handler.py --action submit --file Plan_20260307.md
```

---

### `check` — Read the current approval status of a file

Reads the file's frontmatter and reports its current status.
Tells you if it is still awaiting approval or already decided.

```bash
python scripts/approval_handler.py --action check --file Plan_20260307.md
```

---

### `approve` — Mark a task as approved

Moves the file from `Pending_Approval/` to `Approved/`, sets
`status: approved`, and logs the decision. After approval, the task is
safe to execute.

```bash
python scripts/approval_handler.py --action approve --file Plan_20260307.md --reason "Confirmed correct"
```

---

### `reject` — Mark a task as rejected

Moves the file from `Pending_Approval/` to `Rejected/`, sets
`status: rejected`, appends the rejection reason to the file, and logs it.

```bash
python scripts/approval_handler.py --action reject --file Plan_20260307.md --reason "Amount incorrect"
```

---

### `list` — Show all files currently awaiting approval

Lists every file in `Pending_Approval/` with its type, from-field, and age.

```bash
python scripts/approval_handler.py --action list
```

---

## Workflow Integration

```
AI creates plan
    |
    v
/human-approval --action submit --file <plan>
    |
    v
Human reviews file in Pending_Approval/
    |
    +-- Approve --> /human-approval --action approve --file <plan>
    |                   |
    |                   v
    |               Approved/ --> Execute task
    |
    +-- Reject  --> /human-approval --action reject --file <plan> --reason "..."
                        |
                        v
                    Rejected/ --> No action taken
```

---

## Output

Submit:
```
[OK] Submitted for approval: Plan_20260307.md
     Location : Pending_Approval/Plan_20260307.md
     Status   : awaiting_approval
     Time     : 2026-03-07 10:15:00
```

Check:
```
[INFO] Plan_20260307.md
       Status   : awaiting_approval
       Location : Pending_Approval/
       Age      : 12 minutes
```

Approve:
```
[OK] Approved: Plan_20260307.md
     Moved to : Approved/Plan_20260307.md
     Note     : Confirmed correct
     Time     : 2026-03-07 10:27:00
```

Reject:
```
[OK] Rejected: Plan_20260307.md
     Moved to : Rejected/Plan_20260307.md
     Reason   : Amount incorrect
     Time     : 2026-03-07 10:27:00
```

List:
```
Pending Approval — 2 file(s) awaiting review
  1. WA_REPLY_Ali_Khan.md     | type: whatsapp_reply | 25 min ago
  2. Plan_20260307_email.md   | type: plan           |  8 min ago
```

---

## Rules and Constraints

- Never auto-approve — a human must explicitly call `--action approve`
- Never skip this gate for tasks involving external communication or finances
- Always log every decision (approve or reject) to `Approval_Log.md`
- If the file is not found in `Pending_Approval/` during approve/reject, search all folders and report its actual location
- Rejection reason is required for financial tasks (files with `financial_flag: true`)
