# ✉️ MESSAGE CONTRACT (Agent IPC Envelope Specification)

> **Zárt Üzenet-Szerződés az Ágensek és a Kernel között**

```yaml
---
MESSAGE_ID: "MSG-20260729-1089"
CORRELATION_ID: "WP-SPRINT-001-TASK-03"
SENDER: "DeveloperAgent"
RECIPIENT: "TestAgent"
TIMESTAMP: "2026-07-29T15:30:00Z"
STATE_AT_SEND: "SPRINT_ACTIVE"

STATUS_CODE: "READY_FOR_TEST" # Lehetséges kódok: TASK_COMPLETE, TASK_BLOCKED, TEST_PASSED, TEST_FAILED, ROLLBACK_REQUESTED

ARTIFACTS:
  COMMITS:
    - "a74bc91d8f"
  MODIFIED_FILES:
    - "src/auth/jwt.py"
    - "tests/auth/test_jwt.py"

PAYLOAD:
  SUMMARY: "JWT token validáció és refresh token logika implementálva."
  BLOCKERS: []
---
```

## Érvényes STATUS_CODE Értékek

- `TASK_COMPLETE`: A munka-csomag feladatai elvégzésre kerültek.
- `READY_FOR_TEST`: A kód átadásra kész a TestAgent számára.
- `TEST_PASSED`: A teszt szvit sikeresen lefutott.
- `TEST_FAILED`: A teszt szvit hibával zárult.
- `TASK_BLOCKED`: Technikai vagy specifikációs akadály merült fel.
- `ROLLBACK_REQUESTED`: Az ágens állapota visszaállításra szorul.
