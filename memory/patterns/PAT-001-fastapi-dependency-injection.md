# PAT-001 Dependency Injection minta

- **Típus**: Pattern
- **Dátum**: 2026-07-29
- **Kulcsszavak**: `fastapi`, `pattern`, `auth`

## Kontextus
A szerepkör-alapú hozzáférés-vezérlés (RBAC) egységes érvényesítése az API végpontokon.

## Minta leírása
A FastAPI `Depends(require_role("role_name"))` mintáját használjuk a végpontok védelmére és a JWT token szerepkör ellenőrzésére.
