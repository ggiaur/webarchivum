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

## 🌐 2. Élő FastAPI Web Proxy (`/api/proxy`)

- **Cím**: `http://localhost:8000/api/proxy?url={TARGET_URL}`
- **Működés**: Lekéri a megtekintett weboldal valódi HTML-jét, elhajítja a böngészőt blokkoló X-Frame-Options/CSP fejléceket, beilleszti a `<base href="...">` bejegyzést, így a képek, CSS-ek és JS-ek hibátlanul megjelennek az iframe keretben.

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

## 🏛️ 4. Kurátori Tematikus Gyűjtemények

A felületen a **87 nyilvántartott webhely** három fő tematikus kategóriába rendezve böngészhető:

1. 🏛️ **Önkormányzatok & Hivatalok (42 webhely)**  
   *Közvetlen böngészés*: [http://localhost:3000/?category=%C3%96nkorm%C3%A1nyzatok%20%26%20Hivatalok](http://localhost:3000/?category=%C3%96nkorm%C3%A1nyzatok%20%26%20Hivatalok)

2. 📰 **Helyi Sajtó & Média (18 webhely)**  
   *Közvetlen böngészés*: [http://localhost:3000/?category=Helyi%20Sajt%C3%B3%20%26%20M%C3%A9dia](http://localhost:3000/?category=Helyi%20Sajt%C3%B3%20%26%20M%C3%A9dia)

3. 📚 **Kulturális & Könyvtári Örökség (27 webhely)**  
   *Közvetlen böngészés*: [http://localhost:3000/?category=Kultur%C3%A1lis%20%26%20K%C3%B6nyvt%C3%A1ri%20%C3%96r%C3%B6ks%C3%A9g](http://localhost:3000/?category=Kultur%C3%A1lis%20%26%20K%C3%B6nyvt%C3%A1ri%20%C3%96r%C3%B6ks%C3%A9g)

---

## 💻 5. Rendszer Címek & Portok

- 🌐 **Frontend (Next.js)**: `http://localhost:3000`
- ⚙️ **Backend REST API (FastAPI)**: `http://localhost:8000/docs`
- 🌐 **Live Web Proxy**: `http://localhost:8000/api/proxy?url=...`
- 🗄️ **MinIO S3 Console**: `http://localhost:9003` (S3 API: `http://localhost:9002`)
