Create a Plan.md before taking any action.

## Instructions

1. Read the context provided (file path, task description, or item details)
2. Create a new file at `silver_tier/Plans/PLAN_$CONTEXT_$TIMESTAMP.md` using this template:

```markdown
# Plan: $CONTEXT
*Created: $TIMESTAMP*

## Goal
[One sentence: what outcome are we achieving?]

## Steps
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
...

## Expected Output
[What file/action/result will exist when done?]

## Requires Approval
[Yes/No — if Yes, which step needs human sign-off?]

## Risks / Notes
- [Any edge cases or things to watch]
```

3. Print the plan path so the calling skill can reference it
4. **Do not proceed with execution** — only create the plan and return

## Usage
Called by whatsapp-processor and linkedin-poster before they take any action.
Also call directly: `/plan-creator [context description]`
