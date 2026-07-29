# 🔐 PERMISSION MATRIX

> **AI-SD-OS Agent I/O & Execution Access Control**

| Agent Role | Read Paths | Write Paths | Allowed Commands | Allowed Transitions |
| :--- | :--- | :--- | :--- | :--- |
| **DiscoveryAgent** | `/spec`, `/docs`, `/memory` | `/spec/discovery/`, `/kernel/ipc/outbox/` | `git status`, `git log` | `DISCOVERY -> VISION` |
| **ArchitectAgent** | `/spec`, `/docs`, `/memory` | `/spec/`, `/docs/ADR/`, `/kernel/ipc/outbox/` | `git status`, `git diff` | `VISION -> SPEC`, `SPEC -> ARCHITECTURE`, `ARCHITECTURE -> ROADMAP` |
| **DeveloperAgent** | `/spec`, `/fewa-v3-backend`, `/fewa-v3-frontend`, `/memory` | `/fewa-v3-backend/`, `/fewa-v3-frontend/`, `/kernel/ipc/outbox/` | `pytest`, `npm test`, `git add`, `git commit` | `BOOTSTRAP -> SPRINT_ACTIVE`, `SPRINT_ACTIVE -> REVIEW` |
| **TestAgent** | `/fewa-v3-backend`, `/fewa-v3-frontend`, `/tests` | `/docs/test-reports/`, `/kernel/ipc/outbox/` | `pytest`, `npm run test`, `docker compose` | `REVIEW -> RELEASE`, `REVIEW -> SPRINT_ACTIVE` |
| **DevOpsAgent** | `/docker-compose.yml`, `/docker-compose.test.yml`, `/spec` | `/docker-compose*`, `/kernel/ipc/outbox/` | `docker`, `docker compose`, `git` | `RELEASE -> SPRINT_ACTIVE` |
| **ReviewerAgent** | `/fewa-v3-backend`, `/fewa-v3-frontend`, `/spec` | `/docs/reviews/`, `/kernel/ipc/outbox/` | `git diff`, `pytest` | `REVIEW -> SPRINT_ACTIVE`, `REVIEW -> RELEASE` |
| **KernelDaemon** | `/` (Full system read) | `/kernel/ipc/`, `/checkpoint/`, `STATE_CHANGE.md`, `/memory/` | `git reset`, `git checkout`, POSIX process signals | All transitions |
