# 🚨 ESCALATION POLICY (L1 - L4)

> **AI-SD-OS Hierarchikus Eszkalációs Stratégia**

```
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: SELF-HEALING (Aktiválódik: Első teszt/linter hiba esetén)      │
│ Akció: A DeveloperAgent megkapja a Stack Trace-t és újrapróbálja.      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 3 sikertelen L1 próbálkozás
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 2: PEER-REPAIR (Aktiválódik: L1 kudarc után)                      │
│ Akció: RefactorAgent / TestAgent bevonása a kód átnézésére.            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 2 sikertelen L2 próbálkozás
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 3: AI REVIEW BOARD (Aktiválódik: Architektúrális elakadásnál)     │
│ Akció: ArchitectAgent + ReviewerAgent + DeveloperAgent közös szimulá-  │
│ ciója, a probléma izolálása és alternative specifikáció javaslata.    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Nem hoz eredményt / Hard Limit sérülés
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 4: HUMAN INTERVENTION (Aktiválódik: Rendszer-szintű blokkolásnál)│
│ Akció: Állapot = HUMAN_REQUIRED. Értesítés küldése, leállás.           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Szintek Részletezése

### LEVEL 1: Self-Healing
- **Aktiválási feltétel**: Egyszeri szintaktikai, teszt vagy linter hiba a `SPRINT_ACTIVE` szakaszban.
- **Folyamat**: A DeveloperAgent megkapja a hiba kimenetét (Stack Trace / pytest log) és legfeljebb 3 egymást követő javítási kísérletet tehet.
- **Max próbálkozások**: 3

### LEVEL 2: Peer-Repair
- **Aktiválási feltétel**: 3 egymást követő L1 Self-Healing kudarc.
- **Folyamat**: A Kernel átadja a kontextust a TestAgent-nek vagy ReviewerAgent-nek, akik elvégzik a kód felülvizsgálatát és specifikus hibajavítási javaslatot küldenek.
- **Max próbálkozások**: 2

### LEVEL 3: AI Review Board
- **Aktiválási feltétel**: 2 egymást követő L2 Peer-Repair kudarc, vagy architektúrális elakadás (pl. nem kompatibilis adatmodell).
- **Folyamat**: Az ArchitectAgent, ReviewerAgent és DeveloperAgent közös elemzést futtat, incidenst jegyez fel a `memory/incidents/` mappába, és alternatív megközelítést dolgoz ki.
- **Max próbálkozások**: 1

### LEVEL 4: Human Intervention
- **Aktiválási feltétel**: L3 kudarc, vagy Sprint Governance Hard Limit sérülése (pl. Max Runtime > 8 óra, Token consumption > 250k, LOC Delta korlát túllépése).
- **Folyamat**: A Kernel felfüggeszti a futást, az állapotot `HUMAN_REQUIRED` / `SPRINT_ABORTED`-ra állítja, rögzíti az incidenst, és értesíti a humán operátort.
