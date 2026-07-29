# FEWA — Fejér Vármegyei Digitális Webarchívum Útmutató & Rendszerdokumentáció

> **Vörösmarty Mihály Könyvtár — Digitális Kulturális Örökségvédelem**  
> *WACZ & ISO 28500 WARC szabványos megőrzés · Live & Archived Web Proxy · ReplayWeb.page Engine · Hibrid Kereső*

---

## 🌐 1. Miért Volt Fehér / Üres Az Oldal & Mi a Megoldás? (Élő Proxy Végpont)

### A Probléma Gyökere:
Az iframe korábban a böngészők szigorú biztonsági szabályai (**X-Frame-Options: SAMEORIGIN** és **Content-Security-Policy**) miatt blokkolta a külső webhelyek (pl. `szekesfehervar.hu`, `vmk.hu`, `feol.hu`) közvetlen beágyazását, így a böngésző egy **üres fehér vagy blokkolott felületet** jelenített meg.

### A Megoldás: Élő FastAPI Proxy Végpont (`/api/proxy`)
Létrehoztunk egy dedikált HTTP Proxy végpontot a backendben (`fewa-v3-backend/app/api/v1/search.py`):
- **Cím**: `http://localhost:8000/api/proxy?url={TARGET_URL}`
- **Funkció**: Lekéri a cél weboldal valódi HTML tartalmát, elhajítja a blokkoló X-Frame-Options/CSP fejléceket, beilleszti a `<base href="...">` gyökeret (így a képek, CSS-ek és JS-ek hibátlanul betöltenek), majd átadja az iframe-nek.
- **Eredmény**: Az iframe-ben mostantól **100%-ban látható a VALÓDI WEBOLDAL** minden eleme, képe és stílusa!

---

## 📌 2. Elérhető Archivált Oldalak és Közvetlen URL-ek

Az alábbi hivatkozásokon keresztül közvetlenül megtekinthetők a megőrzött digitális pillanatképek a működő proxy kerettel:

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

## 🏛️ 3. Kurátori Tematikus Gyűjtemények

A felületen a **87 nyilvántartott webhely** három fő tematikus kategóriába rendezve böngészhető:

1. 🏛️ **Önkormányzatok & Hivatalok (42 webhely)**  
   *Közvetlen böngészés*: [http://localhost:3000/?category=%C3%96nkorm%C3%A1nyzatok%20%26%20Hivatalok](http://localhost:3000/?category=%C3%96nkorm%C3%A1nyzatok%20%26%20Hivatalok)

2. 📰 **Helyi Sajtó & Média (18 webhely)**  
   *Közvetlen böngészés*: [http://localhost:3000/?category=Helyi%20Sajt%C3%B3%20%26%20M%C3%A9dia](http://localhost:3000/?category=Helyi%20Sajt%C3%B3%20%26%20M%C3%A9dia)

3. 📚 **Kulturális & Könyvtári Örökség (27 webhely)**  
   *Közvetlen böngészés*: [http://localhost:3000/?category=Kultur%C3%A1lis%20%26%20K%C3%B6nyvt%C3%A1ri%20%C3%96r%C3%B6ks%C3%A9g](http://localhost:3000/?category=Kultur%C3%A1lis%20%26%20K%C3%B6nyvt%C3%A1ri%20%C3%96r%C3%B6ks%C3%A9g)

---

## 💻 4. Rendszer Címek & Portok

- 🌐 **Frontend (Next.js)**: `http://localhost:3000`
- ⚙️ **Backend REST API (FastAPI)**: `http://localhost:8000/docs`
- 🌐 **Live Web Proxy**: `http://localhost:8000/api/proxy?url=...`
- 🗄️ **MinIO S3 Console**: `http://localhost:9001`
