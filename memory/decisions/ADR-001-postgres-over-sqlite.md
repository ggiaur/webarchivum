# ADR-001 DB választás PostgreSQL mellett

- **Típus**: Decision
- **Dátum**: 2026-07-29
- **Kulcsszavak**: `database`, `postgres`, `schema`

## Kontextus
A webarchívum nagy mennyiségű WACZ metaadatot és vektoros beágyazást (embeddings) kezel 10k req/s elvárás mellett.

## Döntés
SQLite helyett PostgreSQL 16 adatbázist választunk `pgvector` bővítménnyel a hibrid és vektoros keresések kiszolgálására.
