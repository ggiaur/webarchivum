# INC-001 Memory leak async worker-ben

- **Típus**: Incident
- **Dátum**: 2026-07-29
- **Kulcsszavak**: `python`, `fastapi`, `worker`, `leak`

## Probléma leírása
Hosszú lefutású async crawl feladatoknál felhalmozódó memóriafogyasztás lépett fel, mert az asyncpg connection pool-t nem zárták le megfelelően a worker folyamat leállásakor.

## Megoldás és Tanulság
Minden async pool-hoz `lifespan` handler vagy explicit `await pool.close()` lezáró szükséges az worker és fastapi kontextusban.
