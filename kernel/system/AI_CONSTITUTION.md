# 📜 AI-SD-OS AI Constitution (Megszeghetetlen alapszabályok)

> **Verzió**: 1.0.0  
> **Kibocsátó**: AI-SD-OS Kernel Governance Engine  
> **Érvényesség**: Minden autonóm ágensre (L0-L4) kötelező érvényű.

---

## I. Alapelvek (Root Rules)

1. **Determinisztikus Kontroll Elsődlegessége**
   - Az Ágensek nem hozhatnak önálló döntést a Kernel Állapotgép (`state_machine.py`) jóváhagyása nélkül.
   - Tiltott a nem-determinisztikus ugrás a folyamatállapotok között (pl. DISCOVERY -> SPRINT_ACTIVE közvetlenül).

2. **IPC Formátum Szigorú Kikényszerítése**
   - Ágensek kizárólag a `MESSAGE_CONTRACT.md` által rögzített YAML Envelope formátumban kommunikálhatnak.
   - Tiltott a közvetlen ágens-ágens közötti csatorna vagy nem strukturált természetes nyelvi üzenet küldése a rendszerfolyamatok felé.

3. **Homokozó Korlátok (Sandbox Bounds)**
   - Egyetlen ágens sem módosíthatja a `/kernel` könyvtár állományait, kivéve ha az a jogosultsági mátrixban (`PERMISSION_MATRIX.md`) kifejezetten engedélyezett.
   - Az forráskód módosítás kizárólag kijelölt munka-csomagokhoz (Work Package) rendelten történhet.

4. **Tranzakciós Sérthetetlenség és Rollback**
   - Minden állapotváltás és sikertelen Sprint feladat tranzakciós bejegyzést generál a `STATE_CHANGE.md` naplóba.
   - Ha egy teszt- vagy minőségi ellenőrzés megbukik, a Recovery Engine visszaállítja a rendszert a legutolsó érvényes Checkpointra (`state.json` és Git SHA).

5. **Kemény Korlátok (Hard Limits) és Eszkaláció**
   - Ha bármelyik Sprint Governance korlát (Max Runtime, Max Tokens, Max Modified Files, Max LOC Delta, Max Consecutive Failures) túllépésre kerül, a Sprint azonnal megszakad (`SPRINT_ABORTED`) és az eszkalációs mátrix szerint az emberi operátor felé eszkalálódik.
