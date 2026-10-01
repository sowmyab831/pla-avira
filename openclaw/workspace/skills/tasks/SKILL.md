---
name: pla-tasks
description: Task and habit management — create, update, list, and delete tasks synced to the PLA backend.
metadata: { "openclaw": { "emoji": "\u2705", "requires": { "bins": ["pla"] } } }
---

# Tasks Skill

Use `pla tasks` to manage your to-do list, chores, and habits.

## Commands

```bash
pla tasks add "Buy groceries" --category task --due 2026-06-08
pla tasks add "Walk 30 min" --category habit --due 2026-06-07
pla tasks list               # All tasks
pla tasks list --pending     # Pending only
pla tasks done TASK_ID       # Mark complete
pla tasks delete TASK_ID     # Delete a task
```

## Usage Examples

- "Add a task to call the plumber" → `pla tasks add "Call plumber"`
- "What are my pending tasks?" → `pla tasks list --pending`
- "Mark the dentist task done" → `pla tasks done TASK-001`
- "Add a daily habit to read 20 pages" → `pla tasks add "Read 20 pages" --category habit`
