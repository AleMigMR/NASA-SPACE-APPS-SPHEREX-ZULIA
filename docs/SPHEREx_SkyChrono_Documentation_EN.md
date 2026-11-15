# Complete Documentation — SPHEREx SkyChrono (EN)

**Interactive 360° Full-Sky Explorer (Official DR1), Multi-Epoch Level-2b Blinking, LVF Infrared Spectroscopy (`0.75–5.0 µm`), Tractor Forced Photometry, Automated 3D Celestial Recognition, and Multimodal AstroAI Copilot · *"Planet X and SPHEREx"* Challenge (NASA Space Apps Challenge 2026 · Delegación Zuliana de Astronomía).**

> [!NOTE]
> This **single unified master guide** consolidates **Beginner's Astrophysics**, the **User Manual**, the **Technical & Mathematical Architecture for NASA/IPAC Judges**, and the **Deployment & Space Apps Submission Guide** with zero redundancy. Use the **🌐 View in Español** button above to read the complete Spanish edition.

## Quick Index

- [Chapter 1 · Astrophysics Basics and SPHEREx Mission](#chapter-1-astrophysics-basics-and-spherex-mission)
- [Chapter 2 · User Manual: 360° Universe and Discovery Tools](#chapter-2-user-manual-360-universe-and-discovery-tools)
- [Chapter 3 · Technical Architecture, L2b Mathematics and API](#chapter-3-technical-architecture-l2b-mathematics-and-api)
- [Chapter 4 · Security, Live Deployment and Submission](#chapter-4-security-live-deployment-and-submission)
- [Chapter 5 · Reference Targets, Citations and DOIs](#chapter-5-reference-targets-citations-and-dois)

---

## Chapter 1 · Astrophysics Basics and SPHEREx Mission

### 1.1 What is SPHEREx and Why Observe in Infrared?
**SPHEREx** (*Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer*) is a **NASA** space observatory mapping **100% of the entire sky (`360° × 180°`)** from a sun-synchronous polar orbit. Using **Linear Variable Filters (LVF)** mounted across **6 HgCdTe H2RG detector arrays (`D1–D6`)**, SPHEREx resolves light into **102 infrared spectral channels** spanning **0.753 µm** to **4.988 µm** (`100` active spectral bins excluding `2` dichroic transition bins at `2.42 µm`).

| Detector Array | Spectral Range ($\lambda$) | DR1 Channels | What It Reveals Best |
| :--- | :---: | :---: | :--- |
| **D1** | `0.753 – 1.102 µm` | `Ch 0 – 16` | Far-red continuum, bright main-sequence stars, and Hα / metallic features. |
| **D2** | `1.113 – 1.631 µm` | `Ch 17 – 33` | Nearby red dwarfs (*Barnard's Star*), **H₂O** (`1.4 µm`), and **CH₄** (`1.15–1.6 µm`) troughs. |
| **D3** | `1.656 – 2.345 µm` | `Ch 34 – 49` | **H₂O** vapor (`1.9 µm`), **CO** (`2.3 µm`), and dust-piercing circumstellar structure. |
| **Dichroic Split** | `~2.42 µm` | `Ch 50 – 51` | Internal beam-splitter dividing short-wave (`D1–D3`) and thermal mid-IR (`D4–D6`). |
| **D4** | `2.506 – 3.768 µm` | `Ch 52 – 67` | Cryogenic **H₂O ice** (`3.05 µm`), **CH₄** (`3.32 µm`), and PAH emission (`3.29 µm`). |
| **D5** | `3.833 – 4.405 µm` | `Ch 68 – 84` | **CO₂ ice** (`4.27 µm`) and transition into thermal mid-infrared continuum. |
| **D6** | `4.435 – 4.988 µm` | `Ch 85 – 101` | **CO** (`4.67 µm`), thermal glow of ultra-cold **Y brown dwarfs (~250 K)**, and **Planet X / KBOs**. |

- **Cold objects vs. visible light:** A ~`250 K` Y-type brown dwarf such as `WISE 0855−0714` is nearly invisible in optical and SWIR bands due to methane/water absorption, yet shines brightly in `D5–D6`.
- **Biogenic Ices (SPLICES Catalog):** Infrared spectroscopy directly quantifies absorption signatures of volatile habitability molecules (**H₂O**, **CH₄**, **CO₂**, **CO**).

### 1.2 Motion, Dipoles, `ZODI` & `FLAGS`
- **Blink vs. Diff ($E_n - E_1$):** Repeated observations yield distinct time epochs. **`Blink`** cycles epochs so eyes catch motion or pulsing; **`Diff`** numerically subtracts Epoch 1 from the active epoch so constant stars cancel out while:
  - **Moving bodies** (*Planet X*, *3I/ATLAS*, *WISE 0855*, *Barnard's Star*) stand out as **dipoles** (dark negative lobe at old coordinates + bright positive lobe at current coordinates).
  - **Variables** (*RW Aurigae*, *R Draconis*) shine as isolated bright positive peaks (brightening) or dark pits (dimming).
- **`ZODI` (Zodiacal Light):** Interplanetary dust in our Solar System scatters sunlight and radiates thermal infrared across the sky. SkyChrono **subtracts the physical `ZODI` model per exposure** so faint targets emerge cleanly.
- **`FLAGS` (L2b Bitmask):** Hardware quality flags identify cosmic rays (South Atlantic Anomaly), LEO satellite streaks, and diode persistence to suppress false anomaly alerts.

### 1.3 Does the Universe Have a "North" or "South Pole"? (Cosmological Principle)
> [!IMPORTANT]
> **Physical cosmology has NO absolute "up", "down", "North Pole", or "South Pole".** Under the **Cosmological Principle**, the Universe on large scales is **isotropic and homogeneous** in every direction.

Orientations inside our 360° viewer strictly reflect **3 standard astronomical reference frames**:
- **Galactic $(l, b)$:** Aligns the Milky Way disk horizontally (`Sgr A*` centered), ideal for interstellar dust and SPLICES molecular clouds.
- **Ecliptic $(\lambda, \beta)$:** Aligns Earth's orbital plane, scanning the **Planet X / KBO** search belt, zodiacal dust glow, and SPHEREx's ultra-deep **NEP** & **SEP** fields (`>2,400 exposures`).
- **Equatorial ICRS (RA, Dec):** International quasar-locked reference grid used by Gaia DR3, SIMBAD, and the IAU MPC.

---

## Chapter 2 · User Manual: 360° Universe and Discovery Tools

### 2.1 Global Header & Reference Targets
From left to right, the top bar organizes global scientific and export actions:
- **🎯 Quick Tour** & **📚 Manuals & Docs**: Open this single unified bilingual Documentation Center with chapter jump navigation and raw Markdown download.
- **🏛️ NASA / IRSA Resources**: Opens live deep links pre-bound to the active **RA/Dec** in IRSA Viewer (Firefly), SPHEREx Portal, CDS SIMBAD, VizieR (Gaia DR3 / AllWISE), official DOIs (`IRSA678`, `IRSA679`, `IRSA662`), SPLICES/3I-ATLAS, and Caltech-IPAC.
- **📐 MPC 80-Col Report**: Generates, copies, or downloads strict 80-column **IAU Minor Planet Center** astrometry (`C59`).
- **🔗 Share** & **🎞️ Export Blink GIF**: Copy reproducible state URLs (`?ra=...&dec=...&fov=...&bands=...&mode=...&lang=...`) or export multi-epoch `.GIF` animations.
- **🌐 ES / EN**: Switches all UI panels, charts, tooltips, and AstroAI responses instantaneously between English and Spanish.

Directly below sits the **Reference Targets** strip:
- Hover over any target card to display the **Cursor-Tracking Scientific Tooltip** without shifting page geometry.
- Click **`+ New`** to add custom targets via coordinates or SIMBAD/Sesame, or **`⚙️ Manage`** for full CRUD editing (ES/EN metadata, removal, and factory restore).

### 2.2 360° Observable Universe Mode (Official SPHEREx DR1 Cube)
Select **`🌌 360° Observable Universe`** to switch seamlessly among **3 synchronized engines**:

| 360° Engine | Technology | Operational Advantage |
| :--- | :--- | :--- |
| **360° × 180° Plane (Official DR1 Aitoff)** | Equal-area Hammer-Aitoff built from Official IRSA DR1 Cube (`10.26131/IRSA679`) | Full-sky view of the Galactic disk, ecliptic band, NEP/SEP, and 18 major sky landmarks. |
| **3D Celestial Sphere (Free Rotation)** | Unrestricted spherical trackball (*yaw / pitch / roll*, no cosmic poles) | Rotate freely backward, zenith, nadir, and across every sky hemisphere. |
| **Progressive IRSA HiPS / Aladin** | Aladin Lite v3 via local CORS proxy (`/api/hips/spherex/...`) | Continuous multi-resolution HiPS zooming across DR1 (`DR1 RGB`, `0.91–4.67 µm` bands), `AllWISE`, and `2MASS`. |

- **Isotropic Controls:** Switch **Reference Plane** (`Galactic`, `Ecliptic`, `ICRS`), jump to **`Galactic Center`**, **`Deep NEP`**, **`Deep SEP`**, step **`-30° / +30°`**, reset via **`🎯 Isotropic 360° View`**, and double-click anywhere (or click **`🔬 Extract DR1 FITS Cube Here`**) to extract the matching `Norder5` tile (`Npix{ipix}_cube.fits`) and load the high-resolution L2b multi-epoch cube.

### 2.3 Analysis Controls, Continuous Sky Streaming & 3D Cosmic Ruler
- **Left Sidebar (`01–03`):** Resolve decimal/sexagesimal coordinates or SIMBAD names propagated to epoch `2025.5`; pick **FOV** across 7 calibrated zoom steps (`0.06°` to `1.60°`), stacking depth (`5–20 exp/epoch`), epoch gap (`15–90 days`), IRSA release (`QR1/QR2/DR1`), and `D1–D6` arrays. Adjust real-time 60 FPS stretches (`ZScale`, `Log`, `Linear`, `Sqrt`, `Asinh`), colormaps (`Inferno`, `Viridis`, `CyanHot`, `Grayscale`), Gaussian smoothing, WCS grid, aperture radius, live **Gaia DR3 / AllWISE** overlays, **`FLAGS` / `ZODI`** diagnostics, **`🔭 Objects (ON/OFF)`**, and **`📏 Measure Distance A↔B`**.
- **Central Viewport:** Switch modes across **`Blink`**, **`Diff (E_n - E_1)`**, **`RGB`**, **`Sum`**, **`Split (E_1 | E_n)`**, and **`360° Universe`**.
  - *Drag to Pan:* Continuous exploration; panning beyond the cached tile automatically queries IRSA TAP/S3 to stream neighboring exposures (**zero black borders**).
  - *Mouse Wheel:* Cursor-anchored continuous zoom across the 7 `FOV` steps. *Single Click:* Extract point spectrum (`/api/point_spectrum`). *Double Click:* Recenter and reload cube. *Keyboard:* `Spacebar` (Play/Pause), `← / →` (Step epochs).
  - *Floating AI Anomaly HUD:* Lists ranked candidates (`#1`, `#2`...) with one-click **`💬 Gemini`** visual analysis.
  - *3D Cosmic Distance Ruler (`📏 A ↔ B`):* Click **Object A** and **Object B** on the map to measure telescope distance, angular separation ($\theta$), Position Angle ($\text{PA}$), projected separation, and **true 3D Euclidean distance ($D_{3\text{D}}$)** in `ly`, `pc`, and `AU`.
- **Right Sidebar (`04–05` & AstroAI):** Live `0.75–5.0 µm` LVF spectrum with **`Planck Model + Ices τ(λ)`** overlay (`T_eff` in K + optical depths of `H₂O`, `CH₄`, `CO₂`, `CO`) and **`.CSV`** export; Multi-Epoch Light Curve + clickable recognized-object pills; and **AstroAI Copilot** chat.

---

## Chapter 3 · Technical Architecture, L2b Mathematics and API

### 3.1 Asynchronous Pipeline (`app.py` + `spherex_engine.py`)
Built on **Python 3.11+ / `aiohttp`**, delegating FITS I/O and WCS algebra to `asyncio.to_thread` and a **16-thread** parallel byte-range pool:

```mermaid
sequenceDiagram
    participant UI as Web Client (Canvas 2D / Aladin v3)
    participant API as aiohttp Server (app.py)
    participant TAP as IRSA TAP (ADQL)
    participant S3 as AWS S3 / IBE (HTTP Range)
    participant Eng as WCS/Tractor Engine (spherex_engine.py)

    UI->>API: GET /api/cube?ra=...&dec=...&fov=...&bands=...
    API->>Eng: build_sky_cube_and_spectrum()
    alt RAM Cache Hit (&lt;1 ms) or Disk (&lt;20 ms)
        Eng-->>API: Enriched Cube + Telemetry + 3D Objects
    else Cache Miss or Continuous Pan Outside Footprint
        Eng->>TAP: SELECT uri, obsid, t_min... FROM spherex.artifact JOIN spherex.plane (0.14° spatial cache)
        TAP-->>Eng: Time-ordered exposure list
        Eng->>S3: Parallel HTTP Range (16 threads) -> IMAGE, ZODI, FLAGS, VARIANCE, WCS-WAVE
        Eng->>Eng: ZODI Subtraction + BAD_MASK + reproject_interp (2× oversampling)
        Eng->>Eng: 15×15 Tractor + σ_MAD Detector + 3D Recognizer + 80-Col MPC
        Eng-->>API: JSON Payload (float32 Base64 + full telemetry)
    end
```

For **Official DR1 360° mode**, `ang2pix_nest_scalar(nside, ra, dec)` implements the exact **HEALPix `NESTED`** indexing of Górski et al. (2005) —verified against Caltech/IPAC's `hpgeom` (`ra=60.8109955°, dec=51.3404038°, nside=32 → ipix=445`)— serving `Norder3` tiles and partial `Norder5` `Npix{ipix}_cube.fits` extracts across `102` nominal channels (`SPHEREX_DR1_WAVELENGTHS_UM`). Client LUTs (`1024` steps) render at **60 FPS** with strict DOM/WebGL exclusion between `#allskyContainer` and `#skyCanvas`.

### 3.2 Live Quantitative Mathematical Equations (`math_telemetry`)
1. **Physical ZODI Subtraction & L2b Bitmasking:**
   $$I_{\text{clean}}(x,y) = \left[\text{IMAGE}(x,y) - \text{ZODI}(x,y)\right] \cdot M_{\text{flags}}(x,y)$$
   `BAD_MASK` filters critical instrumental bits `(2, 4, 6, 7, 9, 10, 11, 25, 26, 27)` while **preserving `Bit 21 (SOURCE)`**.
2. **Linear Forced Photometry (15×15 Tractor) & WCS Oversampling:**
   $$\theta = (A^T W A)^{-1} A^T W I \quad \longrightarrow \quad \text{FWHM} = 2.355 \cdot \sigma_{\text{PSF}}$$
   Cube projections apply **2× oversampling** relative to SPHEREx native `6.15"/px` (`~3.075"/px` at standard FOV), calibrated to `Ω_pix = 8.894 × 10⁻¹⁰ sr`.
3. **Apparent AB Magnitude Conversion:**
   $$m_{\text{AB}} = 23.9001 - 2.5 \cdot \log_{10}(F_{\mu\text{Jy}})$$
4. **Exact 2D Bilinear LVF Spectroscopy (`WCS-WAVE`):**
   $$\lambda(x,y) = \sum_{i,j \in \{0,1\}} w_{ij}(t_x, t_y) \cdot V_{\text{WAVE}}(i,j)$$
5. **Wien Thermal Estimate & Biogenic Ice Optical Depth (SPLICES):**
   $$\tau(\lambda) = -\ln\!\left[\frac{F_{\text{obs}}(\lambda)}{F_{\text{cont}}(\lambda)}\right]$$
   evaluated at **H₂O (`3.05 µm`)**, **CH₄ (`3.32 µm`)**, **CO₂ (`4.27 µm`)**, and **CO (`4.67 µm`)**, with $T_{\text{eff}} \in [220, 4800]\,\text{K}$.
6. **Robust Kinematics ($\sigma_{\text{MAD}}$) & 3D Euclidean Separation:**
   $$\Delta I = E_n - E_1, \qquad \sigma_{\text{MAD}} = 1.4826 \cdot \text{med}\left|\Delta I - \text{med}(\Delta I)\right|$$
   $$D_{3\text{D}} = \sqrt{d_A^2 + d_B^2 - 2\, d_A\, d_B \cos\theta}$$

### 3.3 6-Module L2b Anti-Artifact Shield, MPC 80-Col & Multimodal Copilot
- **6 H2RG / LEO Guards:** (1) Band 1 *Charge Blooming* around `(1648, 1752)` `r = 85 px`, (2) SUR/SAA Cosmic Rays (`Bit 0`), (3) H2RG Persistence & 32-ch SIDECAR Crosstalk (`Bits 17/20`), (4) `ZODI` + He I `1.083 µm` airglow subtraction, (5) LEO Satellite Streak median suppression (`Bits 25/28`), (6) `2.42 µm` Dichroic Edge & `Bit 21 (SOURCE)` protection.
- **80-Col IAU MPC Export:** `format_mpc_80col()` emits strict 80-byte records with space-based flag **`S`**, fractional UTC date, and observatory code **`C59`**.
- **AstroAI Copilot:** 3-tier resilient cascade: **`gemini-3-flash-preview`** (receiving `#skyCanvas` JPEG snapshot) → **`gemini-flash-lite-latest`** → **`_expert_astrophysics_response`** (deterministic offline Python astrophysics engine at **USD 0** cost).

### 3.4 Complete REST API Reference (14 Routes in `app.py`)

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/` | Serves web UI (`static/index.html`). |
| `GET / POST / DELETE` | `/api/targets` | Full target CRUD (`?id=__RESTORE_DEFAULTS__` resets factory list). |
| `GET` | `/api/resolve?q=...` | Resolves SIMBAD TAP / Astropy Sesame names propagated to `2025.5`. |
| `GET` | `/api/cube` | Multi-epoch Float32 Base64 cube, flags, AI candidates, Tractor & 3D objects. |
| `GET` | `/api/point_spectrum` | Extracts `0.75–5.0 µm` LVF spectrum and light curve at clicked sky coordinate. |
| `GET` | `/api/catalogs` | Live **Gaia DR3** and **AllWISE** VizieR overlays projected onto canvas. |
| `GET` | `/api/gif` | Renders and downloads multi-epoch `.GIF` blink animation. |
| `POST` | `/api/ai/chat` | Multimodal Copilot (cube telemetry + `#skyCanvas` JPEG + chat history). |
| `GET` | `/api/docs?lang=es\|en` | Serves this unified master documentation (`es` / `en`). |
| `GET` | `/api/spherex-allsky-map` | `1440×720` equirectangular DR1 mosaic PNG generator. |
| `GET` | `/api/hips/spherex/{ch}/{tail}` | CORS IVOA HiPS proxy for Aladin Lite v3 across all 102 DR1 channels. |
| `GET` | `/static/*`, `/docs/*` | Static assets and direct Markdown download. |

---

## Chapter 4 · Security, Live Deployment and Submission

### 4.1 API Key Safety & Local Run (`USD 0`)
- `.gitignore` excludes `.env`, `.venv/`, `__pycache__/`, `cache/`, and `poc/out/*.fits`. Never commit keys; `render.yaml` declares `GEMINI_API_KEY` with `sync: false`. Without any external API key, the offline deterministic engine runs 100% free (**`USD 0`**).
- **Local Quickstart:**
  ```bash
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1   # Windows | Linux/macOS: source .venv/bin/activate
  pip install -r requirements.txt
  python app.py                   # http://localhost:8050 (background prewarm active)
  ```
- **Render (`render.yaml`) & Docker (`Dockerfile`):**
  ```bash
  docker build -t spherex-skychrono .
  docker run -d -p 8050:8050 -e GEMINI_API_KEY="optional" spherex-skychrono
  ```

### 4.2 45–55s Demo Video Script & Submission Summary
1. **0:00–0:12:** Open in **`🌌 360° Observable Universe`** (DR1 Aitoff → 3D Sphere → Galactic Center / NEP) and double-click `WISE 0855−0714`.
2. **0:12–0:28:** Switch `Blink → Diff` revealing the moving dipole (`8.1″/yr`), pan smoothly into adjacent sky tiles, and toggle **`🔭 Objects: ON`** + **`📏 A ↔ B`** 3D separation.
3. **0:28–0:45:** Inspect **`Planck + Ices τ(λ)`**, open **`📐 MPC 80-Col` (`C59`)**, and trigger **`💬 Gemini`** on Candidate #1 for multimodal visual diagnosis.
4. **0:45–0:55:** Showcase **`🏛️ NASA / IRSA Resources`** and **`ES / EN`** toggle.

**Copy-Paste Project Summary (NASA Space Apps Form):**
> **SPHEREx SkyChrono** is an open-source 360° astrophysics explorer and multi-epoch time-domain workbench built for NASA's *Planet X and SPHEREx* challenge. Powered directly by NASA/IPAC IRSA's Official SPHEREx DR1 All-Sky Spectral Cube (`10.26131/IRSA679`), IRSA TAP ADQL, and AWS S3 HTTP Byte-Range FITS streaming, SkyChrono delivers unrestricted 360° navigation (Hammer-Aitoff, 3D Sphere, and Aladin Lite v3 HiPS), continuous sky panning/zooming across Level-2b cubes, automated $\sigma_{\text{MAD}}$ kinematic dipole detection, 15×15 Tractor forced photometry, 102-channel `WCS-WAVE` spectroscopy with cryogenic ice $\tau(\lambda)$ fitting, 3D cosmic distance measurement, 80-column IAU MPC (`C59`) reporting, and a multimodal Gemini Vision AstroAI Copilot.

---

## Chapter 5 · Reference Targets, Citations and DOIs

| Target / Landmark | ICRS Coordinates | Scientific Highlight |
| :--- | :--- | :--- |
| **WISE 0855−0714** | `133.79513°, -7.24515°` | Coldest known Y brown dwarf (~`250 K`, `2.28 pc`, `~8.1″/yr`), radiant in `D6`. |
| **Barnard's Star** | `269.4485°, +4.7394°` | Highest sky proper motion (`10.36″/yr`, `1.83 pc`, `4.4'` displacement since J2000). |
| **Epsilon Indi Ba/Bb** | `331.0689°, -56.7938°` | Binary `T1+T6` brown dwarf pair (`3.63 pc`, `4.70″/yr`, deep `H₂O`/`CH₄` absorption). |
| **RW Aurigae** | `76.9565°, +30.4014°` | Young *T Tauri* binary with dusty disk eclipses & strong `D2–D5` IR variability. |
| **R Draconis** | `248.1669°, +66.7549°` | Mira pulsating red giant (`P ≈ 245.6 days`, `>2,400 exp`) near North Ecliptic Pole. |
| **Comet 3I/ATLAS & Elias 16** | Pre-mapped 360° Landmarks | Interstellar `CO₂/H₂O` coma visitor & benchmark SPLICES cryogenic ice probe. |

### Official References
1. **SPHEREx Mission Archive at IRSA:** https://irsa.ipac.caltech.edu/Missions/spherex.html
2. **NASA Space Apps 2026 Challenge Resources:** https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=resources
3. **SPHEREx Spectral Images & Releases:** https://doi.org/10.26131/IRSA678
4. **SPHEREx DR1 All-Sky Spectral Cube HiPS:** https://doi.org/10.26131/IRSA679
5. **SPHEREx Cutout Service & Archival Data:** https://doi.org/10.26131/IRSA662
6. **SPLICES & 3I/ATLAS Portal (IRSA):** https://irsa.ipac.caltech.edu/data/SPHEREx/
7. **Caltech-IPAC SPHEREx Archive Tutorials:** https://github.com/Caltech-IPAC/spherex-archive-tutorials
8. **IAU Minor Planet Center (80-Column Format):** https://www.minorplanetcenter.net/iau/info/OpticalObs.html
9. **Górski, K. M. et al. (2005):** *HEALPix: A Framework for High-Resolution Discretization and Fast Analysis of Data Distributed on the Sphere*, ApJ 622, 759.

---

*Complete Documentation v3.0 · **SPHEREx SkyChrono** · Delegación Zuliana de Astronomía · NASA Space Apps Challenge 2026*
