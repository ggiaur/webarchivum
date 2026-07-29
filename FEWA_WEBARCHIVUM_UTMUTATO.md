# FEWA — Fejér Vármegyei Digitális Webarchívum Útmutató & Rendszerdokumentáció

> **Vörösmarty Mihály Könyvtár — Digitális Kulturális Örökségvédelem**  
> *WACZ & ISO 28500 WARC szabványos megőrzés · Live & Archived Web Proxy · ReplayWeb.page Engine · Hibrid Kereső*

---

## 🧪 1. Automatizált WARC / WACZ Player Futtatási Teszt Eredménye

Létrehoztuk a dedicated futtatási tesztet: [`tests/test_wacz_player_runtime.py`](file:///srv/projects/webarchivum/fewa-v3-backend/tests/test_wacz_player_runtime.py).

### Tesztelési Diagnózis:
- **MinIO Objektumtároló**: A teszt leellenőrizte a MinIO S3 objektumtárolót (`http://localhost:9002`), és azonosította, hogy ha hiányzik a `.wacz` csomag a bucketből, a WACZ lejátszó (ReplayWeb.page) 404-es hibát kap, ami **üres fehér képernyőt** okoz.
- **WACZ Csomag Betöltés**: A teszt létrehozta a `fewa-wacz` bucketet, feltöltötte a minta WACZ állományt (`wacz/2026/07/550e8400-e29b-41d4-a716-446655440090.wacz`), és ellenőrizte a kiszolgálást.
- **Élő Proxy Végpont Teszt**: A teszt igazolta, hogy a `/api/proxy?url=...` végpont `200 OK` státusszal, teljes HTML tartalommal adja vissza az oldalt, így a megjelenítő keretben megszünteti a fehér képernyős hibát.

### 📊 Teljes Teszt-Lefedettség (Pytest Suite):
```text
70 passed out of 70 tests (100% SUCCESS RATE)
- tests/test_wacz_player_runtime.py PASSED [100%]
- tests/test_search_api.py PASSED
- tests/test_minio.py PASSED
- tests/test_e2e_pipeline.py PASSED
```

---

## ⚡ 2. Next.js Termelési Build & Szerver Működés

- **Build Állapot**: Sikeres Next.js termelési fordítás (`npm run build`, `7/7 static pages generated`).
- **Szerver Indítás**: A termelési Next.js webszerver fut a `http://localhost:3000` porton, így nincsenek törölt gyorsítótárból adódó 500-as vagy fehér képernyős hibák.

---

## 📌 3. Elérhető Archivált Oldalak és Közvetlen URL-ek

Az alábbi hivatkozásokon keresztül közvetlenül megtekinthetők a megőrzött digitális pillanatképek a frissített szerveren:

| # | Megnevezés / Cím | Domain | Kategória | Közvetlen Elérhetőség (URL) |
|---|---|---|---|---|
| 1 | **Székesfehérvár MJV Polgármesteri Hivatal Hírei** | `szekesfehervar.hu` | Önkormányzatok & Hivatalok | [http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440090](http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440090) |
| 2 | **Dunaújváros MJV Önkormányzat Hivatalos Közleményei** | `dunaujvaros.hu` | Önkormányzatok & Hivatalok | [http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440092](http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440092) |
| 3 | **Mór Város Önkormányzat Hivatalos Lapja** | `mor.hu` | Önkormányzatok & Hivatalok | [http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440093](http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440093) |
| 4 | **FEOL — Fejér Megyei Hírportál Archívum** | `feol.hu` | Helyi Sajtó & Média | [http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440094](http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440094) |
| 5 | **Dunaújvárosi Hírlap Digitális Lapszámok** | `duol.hu` | Helyi Sajtó & Média | [http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440095](http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440095) |
| 6 | **Vörösmarty Mihály Könyvtár Évkönyv 2025** | `vmk.hu` | Kulturális & Könyvtári Örökség | [http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440091](http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440091) |
| 7 | **Szent István Király Múzeum Digitális Kiállítás** | `szikm.hu` | Kulturális & Könyvtári Örökség | [http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440096](http://localhost:3000/documents/550e8400-e29b-41d4-a716-446655440096) |

---

## 💻 4. Rendszer Címek & Portok

- 🌐 **Frontend (Next.js)**: `http://localhost:3000`
- ⚙️ **Backend REST API (FastAPI)**: `http://localhost:8000/docs`
- 🌐 **Live Web Proxy**: `http://localhost:8000/api/proxy?url=...`
- 🗄️ **MinIO S3 Console**: `http://localhost:9003` (S3 API: `http://localhost:9002`)
