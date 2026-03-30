---
phase: quick
plan: 260330-dz6
subsystem: session
tags: [scheduling, invite, security, session-lifecycle]
dependency_graph:
  requires: []
  provides: [scheduled_at enforcement in can_start/start, 30-min invite expiration]
  affects: [session/models.py, session/serializers.py, docs/api.md]
tech_stack:
  added: []
  patterns: [timezone.now() >= scheduled_at guard in state machine]
key_files:
  created: []
  modified:
    - session/models.py
    - session/serializers.py
    - docs/api.md
decisions:
  - Guard placed in both can_start() (return False) and start() (explicit error message) to give a specific 400 for the too-early case rather than falling through to the generic status error
  - Invite expiration changed to flat 30 minutes from creation, removing the min(7days, scheduled_at) logic entirely
metrics:
  duration: ~5 minutes
  completed: "2026-03-30"
  tasks_completed: 2
  files_modified: 3
---

# Quick 260330-dz6: Rework Session Scheduling — Enforce Scheduled Time + 30-min Invite Expiry

**One-liner:** Scheduling guard in `can_start()`/`start()` blocks premature session starts; invite token now expires 30 minutes after creation (replaced 7-day/scheduled_at min logic).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Enforce scheduled_at guard + 30-min invite expiration | 1432b1d | session/models.py, session/serializers.py |
| 2 | Update API docs with new scheduling and invite rules | 656fa37 | docs/api.md |

## Changes Made

### session/models.py

`can_start()` now includes a third condition:
```python
and timezone.now() >= self.scheduled_at
```

`start()` now raises a specific error before falling through to the generic status error:
```python
if self.scheduled_at and timezone.now() < self.scheduled_at:
    raise ValidationError("Cannot start session before the scheduled time.")
```

### session/serializers.py

`SessionCreateSerializer.create()` invite expiration changed from:
```python
expires = min(timezone.now() + timedelta(days=7), validated_data["scheduled_at"])
```
to:
```python
expires = timezone.now() + timedelta(minutes=30)
```

### docs/api.md

- `POST /api/sessions/`: Added note that `invite_expires_at` = now + 30 minutes
- `POST /api/sessions/accept-invite/`: Added note that token expires 30 minutes after session creation
- `POST /api/sessions/<id>/start/`: Added `scheduled_at` requirement to description; added `"Cannot start session before the scheduled time."` to 400 errors

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

Files confirmed modified:
- FOUND: session/models.py
- FOUND: session/serializers.py
- FOUND: docs/api.md

Commits confirmed:
- FOUND: 1432b1d
- FOUND: 656fa37
