# 📏 SPRINT GOVERNANCE & HARD LIMITS

> **AI-SD-OS Sprint Korlátok Specifikációja**

| Paraméter | Hard Limit | Akció a korlát túllépésekor |
| :--- | :--- | :--- |
| **Max Runtime** | 8 óra (480 perc) | `SPRINT_ABORTED` -> Checkpoint mentés -> L4 eszkaláció |
| **Max Output Tokens** | 250,000 token / Sprint | `SPRINT_ABORTED` -> L4 eszkaláció |
| **Max Modified Files** | 50 fájl / Work Package | `WORK_PACKAGE_REJECTED` -> Rollback |
| **Max LOC Delta** | +4000 / -2000 sormódosítás | `WORK_PACKAGE_REJECTED` -> Refactor kérés |
| **Max Consecutive Failures** | 5 sikertelen tesztfutás egymás után | `L3_ESCALATION` (AI Review Board összehívása) |

---

## Működési Diagram

```
                                  +-----------------------+
                                  |   Sprint Indítása     |
                                  +-----------+-----------+
                                              |
                                              v
                                  +-----------------------+
                                  |  Keretek Ellenőrzése  |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     |                        |                        |
                     v                        v                        v
            [LOC / Fájl Korlát]     [Futásidő / Token Korlát]     [Hibatűrési Korlát]
            Max 4000 LOC            Max 8 Óra                     Max 10 Hiba
            Max 50 Fájl             Max $15 Token                 Consecutive < 5
                     |                        |                        |
                     +------------------------+------------------------+
                                              |
                                     (Bármelyik TÚLLÉPVE?)
                                              |
                                     +--------+--------+
                                     |                 |
                                    IGEN              NEM
                                     |                 |
                                     v                 v
                         +-----------------------+  +-----------------------+
                         |    SPRINT_ABORTED     |  |   Sprint Folytatás    |
                         | (Escalation to Human) |  +-----------------------+
                         +-----------------------+
```
