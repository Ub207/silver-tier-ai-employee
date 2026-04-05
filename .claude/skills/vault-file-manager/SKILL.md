# Skill: Vault File Manager

## Metadata

| Field          | Value                                              |
|----------------|----------------------------------------------------|
| Skill Name     | Vault File Manager                                 |
| Invoked As     | `/vault-file-manager`                              |
| Category       | Workflow / Task Management                         |
| Script         | `scripts/move_task.py`                             |
| Requires Env   | None (uses relative paths)                         |

---

## Description

Moves task files between vault workflow folders and updates their frontmatter
status in a single atomic operation. Supports single-file moves, batch moves by
pattern, and a status report of all vault folders. The audit trail is appended
to `AI_Employee_Vault/Approval_Log.md` on every move.

---

## Vault Folder Map

```
AI_Employee_Vault/
  Inbox/           — new tasks (entry point)
  Needs_Action/    — tasks with plans, awaiting execution
  Pending_Approval/ — tasks awaiting human approval
  Approved/        — approved, ready to execute
  Rejected/        — rejected tasks
  Done/            — completed and archived
```

---

## Inputs

| Argument      | Flag            | Required | Description                                    |
|---------------|-----------------|----------|------------------------------------------------|
| File name     | `--file`        | Yes*     | File to move (name only, or relative path)     |
| Destination   | `--to`          | Yes*     | Target folder name (see folder map above)      |
| Pattern move  | `--pattern`     | No       | Glob pattern, e.g. `WA_*.md` (moves all matches) |
| Source folder | `--from`        | No       | Source folder (default: searches all folders)  |
| Note          | `--note`        | No       | Optional note appended to Approval_Log.md      |
| Status report | `--status`      | No       | Print a count of files in each folder and exit |
| Dry run       | `--dry`         | No       | Preview the move without writing anything      |

*Required unless `--status` is used.

---

## Workflow

1. Resolve the source file path (search all folders if `--from` not specified)
2. Validate the destination folder name
3. Check for filename conflicts in the destination (rename with `_1`, `_2` if needed)
4. Move the file using `shutil.move`
5. Update the `status:` field in the file's YAML frontmatter to match the destination
6. Append an entry to `AI_Employee_Vault/Approval_Log.md`
7. Print a confirmation line

---

## Usage

```bash
# Move a single file to Done
python scripts/move_task.py --file WA_20260307_Ali_Khan.md --to Done

# Move from a specific folder
python scripts/move_task.py --file PLAN_20260307.md --from Needs_Action --to Pending_Approval

# Move all WA reply files to Done
python scripts/move_task.py --pattern "WA_REPLY_*.md" --from Pending_Approval --to Done

# Check how many files are in each folder
python scripts/move_task.py --status

# Preview without writing
python scripts/move_task.py --file task.md --to Done --dry
```

---

## Output

Move success:
```
[OK] Moved: Needs_Action/WA_20260307_Ali_Khan.md
         -> Done/WA_20260307_Ali_Khan.md
     Status updated : done
     Logged at      : 2026-03-07 10:05:33
```

Status report:
```
Vault Status — 2026-03-07 10:05:33
  Inbox             :  2 file(s)
  Needs_Action      :  5 file(s)
  Pending_Approval  :  3 file(s)
  Approved          :  1 file(s)
  Rejected          :  0 file(s)
  Done              : 14 file(s)
```

---

## Folder-to-Status Mapping

| Destination Folder | Status Written to Frontmatter |
|--------------------|-------------------------------|
| Inbox              | `new`                         |
| Needs_Action       | `pending`                     |
| Pending_Approval   | `awaiting_approval`           |
| Approved           | `approved`                    |
| Rejected           | `rejected`                    |
| Done               | `done`                        |

---

## Rules and Constraints

- Never delete files — only move them
- Never overwrite an existing file silently — rename with suffix instead
- Always update frontmatter status after moving
- Always append to Approval_Log.md (never overwrite it)
- If the source file cannot be found in any vault folder, exit with code 1
