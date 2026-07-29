# FEWA — Fejér Vármegyei Digitális Webarchívum Útmutató & Rendszerdokumentáció

> **Vörösmarty Mihály Könyvtár — Digitális Kulturális Örökségvédelem**  
> *WACZ & ISO 28500 WARC szabványos megőrzés · Live & Archived Web Proxy · ReplayWeb.page Engine · Hibrid Kereső*

---

## ⚡ 1. Miért Nem Változott a Böngészőben & Mi Történt?

### A Probléma Gyökere:
A háttérben futó **Next.js szerver** (PID 554346) korábbi statikus memóriája és a `.next` gyorsítótára elraktározta a régi oldalváltozatokat. Amikor a forráskód frissült, a beragadt Next.js folyamat a régi felületet adta vissza a böngészőnek.

### Az Elvégzett Beavatkozás:
1. **Folyamatok Leállítása**: Leállítottuk a beragadt Next.js folyamatokat (`kill -9 554346`).
2. **Gyorsítótár Ürítése**: Teljesen töröltük a `.next` gyorsítótár könyvtárat.
3. **Friss Szerver Indítás**: Elindítottuk a friss Next.js felületet a `http://localhost:3000` címen (`✓ Ready in 1647ms`).

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
- 🗄️ **MinIO S3 Console**: `http://localhost:9001`
