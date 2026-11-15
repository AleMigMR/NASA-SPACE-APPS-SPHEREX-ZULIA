# Documentación Integral — SPHEREx SkyChrono (ES)

**Plataforma interactiva de cielo completo 360° (DR1 Oficial), blinking multi-época Nivel 2b, espectroscopía infrarroja LVF (`0.75–5.0 µm`), fotometría forzada Tractor, reconocimiento 3D de astros y copiloto multimodal AstroAI · Reto *"Planet X and SPHEREx"* (NASA Space Apps Challenge 2026 · Delegación Zuliana de Astronomía).**

> [!NOTE]
> Este **documento maestro único** consolida en una sola referencia sin redundancias los **Conceptos Básicos**, el **Manual de Usuario**, la **Arquitectura Técnica y Matemática para Jueces NASA/IPAC** y la **Guía de Despliegue y Entrega**. Usa el botón superior **🌐 Ver en English** para leer la versión íntegra en inglés.

## Índice Rápido

- [Capítulo 1 · Conceptos Básicos y Misión SPHEREx](#capitulo-1-conceptos-basicos-y-mision-spherex)
- [Capítulo 2 · Manual de Usuario: Universo 360°, Navegación y Análisis](#capitulo-2-manual-de-usuario-universo-360-navegacion-y-analisis)
- [Capítulo 3 · Arquitectura Técnica, Matemática y API](#capitulo-3-arquitectura-tecnica-matematica-y-api)
- [Capítulo 4 · Seguridad, Despliegue y Entrega Space Apps](#capitulo-4-seguridad-despliegue-y-entrega-space-apps)
- [Capítulo 5 · Objetivos, Referencias y DOIs](#capitulo-5-objetivos-referencias-y-dois)

---

## Capítulo 1 · Conceptos Básicos y Misión SPHEREx

### 1.1 ¿Qué es SPHEREx y por qué observar en Infrarrojo?
**SPHEREx** (*Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer*) es un telescopio espacial de la **NASA** que cartografía **el 100% de la esfera celeste (`360° × 180°`)** desde una órbita heliosíncrona polar. Emplea **Filtros Linealmente Variables (LVF)** sobre **6 detectores HgCdTe H2RG (`D1–D6`)** para descomponer la luz en **102 canales espectrales infrarrojos** desde **0.753 µm** hasta **4.988 µm** (`100` bandas activas tras excluir las `2` bandas de transición en el espejo dicroico a `2.42 µm`).

| Arreglo Detector | Rango Espectral ($\lambda$) | Canales DR1 | ¿Qué revela mejor en astrofísica? |
| :--- | :---: | :---: | :--- |
| **D1** | `0.753 – 1.102 µm` | `Ch 0 – 16` | Continuo óptico-rojo, estrellas brillantes y líneas metálicas / Hα. |
| **D2** | `1.113 – 1.631 µm` | `Ch 17 – 33` | Enanas rojas (*Barnard's Star*), bandas de **H₂O** (`1.4 µm`) y **CH₄** (`1.15–1.6 µm`). |
| **D3** | `1.656 – 2.345 µm` | `Ch 34 – 49` | Vapor de **H₂O** (`1.9 µm`), **CO** (`2.3 µm`), penetración de polvo circunestelar. |
| **Borde Dicroico** | `~2.42 µm` | `Ch 50 – 51` | Espejo divisor interno del instrumento entre brazo SWIR (`D1–D3`) y MWIR (`D4–D6`). |
| **D4** | `2.506 – 3.768 µm` | `Ch 52 – 67` | **Hielo de H₂O** (`3.05 µm`), **CH₄** (`3.32 µm`) y emisión PAH (`3.29 µm`). |
| **D5** | `3.833 – 4.405 µm` | `Ch 68 – 84` | **Hielo de CO₂** (`4.27 µm`) y transición al infrarrojo térmico. |
| **D6** | `4.435 – 4.988 µm` | `Ch 85 – 101` | **CO** (`4.67 µm`), emisión térmica de enanas marrones clase **Y (~250 K)** y **Planeta X / KBOs**. |

- **Objetos fríos vs. luz visible:** Una enana marrón clase Y como `WISE 0855−0714` (`T_eff ≈ 250 K`) es prácticamente invisible en óptico y SWIR por absorción de agua y metano, pero brilla intensamente en `D5–D6`.
- **Hielos Biogénicos (Catálogo SPLICES):** El infrarrojo permite medir directamente las huellas de absorción sólida de moléculas esenciales para la vida (**H₂O**, **CH₄**, **CO₂**, **CO**).

### 1.2 Movimiento, Dipolos, `ZODI` y `FLAGS`
- **Blink vs. Diff ($E_n - E_1$):** SPHEREx visita las mismas regiones en distintas épocas. En modo **`Blink`**, nuestros ojos detectan saltos o pulsaciones. En **`Diff`**, los astros estacionarios se cancelan a tono neutro mientras:
  - Un **objeto en movimiento** (*Planeta X*, *3I/ATLAS*, *WISE 0855*, *Barnard's Star*) deja un **dipolo** (lóbulo negativo en su posición antigua + lóbulo positivo en la actual).
  - Un **astro variable** (*RW Aurigae*, *R Draconis*) destaca como un punto brillante aislado (se iluminó) o un hueco oscuro (se atenuó).
- **`ZODI` (Luz Zodiacal):** Polvo interplanetario en nuestro Sistema Solar que dispersa luz solar y emite calor infrarrojo. SkyChrono **resta el modelo `ZODI` en cada exposición** para revelar objetos tenues.
- **`FLAGS` (Máscara L2b):** Bits instrumentales que marcan rayos cósmicos (Anomalía del Atlántico Sur), trazas de satélites LEO y persistencia de diodos para bloquear falsas alarmas.

### 1.3 ¿El Universo tiene Polo Norte o Polo Sur? (Principio Cosmológico)
> [!IMPORTANT]
> **En cosmología física el Universo NO tiene arriba, abajo, Polo Norte ni Polo Sur absolutos.** Por el **Principio Cosmológico**, el cosmos es **isótropo y homogéneo** en todas las direcciones.

Las orientaciones del visor 360° corresponden únicamente a los **3 planos de referencia astronómicos estándar**:
- **Galáctico $(l, b)$:** Centra el disco de la Vía Láctea (`Sgr A*` en el origen). Ideal para nubes moleculares y polvo interestelar.
- **Eclíptico $(\lambda, \beta)$:** Alinea el plano orbital de la Tierra alrededor del Sol; revela el cinturón orbital de **Planeta X / KBOs**, el polvo zodiacal y los campos ultra-profundos **NEP** y **SEP** (`>2,400 exposiciones`).
- **Ecuatorial ICRS (RA, Dec):** Marco universal estándar utilizado por Gaia DR3, SIMBAD y el Minor Planet Center (IAU).

---

## Capítulo 2 · Manual de Usuario: Universo 360°, Navegación y Análisis

### 2.1 Cabecera Global y Objetivos de Referencia
De izquierda a derecha, la barra superior concentra las herramientas globales:
- **🎯 Guía Rápida** y **📚 Manuales y Docs**: Abren este Centro de Documentación bilingüe con navegación por capítulos y descarga Markdown.
- **🏛️ Recursos NASA / IRSA**: Portal con **enlaces dinámicos pre-cargados en la coordenada RA/Dec activa** hacia IRSA Viewer (Firefly), Archivo SPHEREx, SIMBAD (CDS), VizieR (Gaia DR3 / AllWISE), DOIs (`IRSA678`, `IRSA679`, `IRSA662`), SPLICES/3I-ATLAS y Caltech-IPAC.
- **📐 Reporte MPC 80-Col**: Genera, copia o descarga el formato astrométrico estricto de 80 columnas para el IAU Minor Planet Center (`C59`).
- **🔗 Compartir** y **🎞️ Exportar GIF Blink**: Copian enlace reproducible con query params (`?ra=...&dec=...&fov=...&bands=...&mode=...&lang=...`) y generan animación `.GIF` multi-época.
- **🌐 EN / ES**: Conmuta en tiempo real toda la interfaz y el copiloto IA entre español e inglés.

Debajo de la cabecera se encuentra el cintillo de **Objetivos de Referencia**:
- Pasa el cursor sobre cualquier tarjeta para ver el **Tooltip Científico Flotante** (sin alterar ningún píxel del layout).
- Usa **`+ Nuevo`** para registrar cualquier coordenada o nombre SIMBAD/Sesame y **`⚙️ Administrar`** para abrir el CRUD completo (editar ES/EN, eliminar o restaurar valores de fábrica).

### 2.2 Modo Universo Observable 360° (Cubo Oficial SPHEREx DR1)
Haz clic en **`🌌 Universo Observable 360°`** para alternar entre **3 motores sincronizados**:

| Motor 360° | Tecnología | Ventaja Operativa |
| :--- | :--- | :--- |
| **Plano 360° × 180° (Aitoff DR1 Oficial)** | Proyección equiareal Hammer-Aitoff desde el cubo oficial DR1 (`10.26131/IRSA679`) | Visualización simultánea de la Vía Láctea, banda eclíptica, NEP/SEP y 18 hitos cósmicos. |
| **Esfera Celeste 3D (Rotación Libre)** | Globo trackball interactivo (*yaw / pitch / roll* sin límites ni polos) | Giro libre en todas direcciones alrededor de nuestra posición en el Universo. |
| **HiPS IRSA / Aladin Progresivo** | Aladin Lite v3 conectado vía proxy CORS (`/api/hips/spherex/...`) | Zoom continuo multiresolución con capas DR1 (`DR1 RGB`, canales `0.91–4.67 µm`), `AllWISE` y `2MASS`. |

- **Navegación Isótropa:** Utiliza el selector de **Plano de Referencia** (`Galáctico`, `Eclíptico`, `ICRS`), los atajos **`Centro Galáctico`**, **`NEP Profundo`**, **`SEP Profundo`**, giros **`-30° / +30°`**, **`🎯 Vista Isótropa 360°`** y haz doble clic (o pulsa **`🔬 Extraer Cubo FITS DR1 Aquí`**) para capturar el tile `Norder5` (`Npix{ipix}_cube.fits`) e inspeccionar su cubo multi-época L2b.

### 2.3 Controles de Análisis, Navegación Continua y Regla Cósmica 3D
- **Panel Izquierdo (`01–03`):** Resuelve coordenadas o nombres SIMBAD propagados a época `2025.5`; ajusta **FOV** en 7 pasos (`0.06°` hasta `1.60°`), profundidad (`5–20 exp/época`), brecha temporal (`15–90 días`), lanzamiento IRSA (`QR1/QR2/DR1`) y detectores `D1–D6`. En tiempo real (60 FPS) ajusta escalas (`ZScale`, `Log`, `Linear`, `Sqrt`, `Asinh`), paletas (`Inferno`, `Viridis`, `CyanHot`, `Grayscale`), suavizado, retícula WCS, apertura fotométrica, catálogos **Gaia DR3 / AllWISE**, visualización de **`FLAGS` / `ZODI`**, **`🔭 Astros (ON/OFF)`** y **`📏 Medir Distancia A↔B`**.
- **Visor Central:** Alterna entre **`Blink`**, **`Diff (E_n - E_1)`**, **`RGB`**, **`Sum`**, **`Split (E_1 | E_n)`** y **`Universo 360°`**.
  - *Arrastre libre:* Pan continuo; al cruzar la huella en caché descarga automáticamente el campo adyacente desde IRSA TAP/S3 (**streaming sin bordes negros**).
  - *Rueda del ratón:* Zoom continuo anclado al cursor. *Clic simple:* Espectro puntual `/api/point_spectrum`. *Doble clic:* Recentra y recarga cubo. *Teclado:* `Espacio` (Play/Pause), `← / →` (Épocas).
  - *Detector IA Flotante:* Lista los candidatos rankeados (`#1`, `#2`...) con acceso directo **`💬 Gemini`**.
  - *Regla Cósmica 3D (`📏 A ↔ B`):* Haz clic en **Astro A** y **Astro B** para medir distancia al telescopio, separación angular ($\theta$), Ángulo de Posición ($\text{PA}$), distancia proyectada y **distancia euclidiana tridimensional ($D_{3\text{D}}$)** en `al`, `pc` y `UA`.
- **Panel Derecho (`04–05` y AstroAI):** Espectro LVF (`0.75–5.0 µm`) con ajuste **`Modelo Planck + Hielos τ(λ)`** (`T_eff` en K + profundidades ópticas de `H₂O`, `CH₄`, `CO₂`, `CO`) y descarga **`.CSV`**; Curva de Luz multi-época + píldoras de astros reconocidos; y chat **AstroAI Copilot**.

---

## Capítulo 3 · Arquitectura Técnica, Matemática y API

### 3.1 Tubería de Datos Asíncrona (`app.py` + `spherex_engine.py`)
El backend en **Python 3.11+ / `aiohttp`** separa descargas de red e interpolación WCS en `asyncio.to_thread` y un `ThreadPoolExecutor` de **16 hilos** paralelos:

```mermaid
sequenceDiagram
    participant UI as Cliente Canvas 2D / Aladin v3
    participant API as Servidor aiohttp (app.py)
    participant TAP as IRSA TAP (ADQL)
    participant S3 as AWS S3 / IBE (HTTP Range)
    participant Eng as Motor WCS/Tractor (spherex_engine.py)

    UI->>API: GET /api/cube?ra=...&dec=...&fov=...&bands=...
    API->>Eng: build_sky_cube_and_spectrum()
    alt Hit RAM (&lt;1 ms) o Disco (&lt;20 ms)
        Eng-->>API: Cubo enriquecido + Métricas + Objetos 3D
    else Cache Miss o Pan Continuo fuera de huella
        Eng->>TAP: SELECT uri, obsid, t_min... FROM spherex.artifact JOIN spherex.plane (caché espacial ≤ 0.14°)
        TAP-->>Eng: Lista cronológica de exposiciones
        Eng->>S3: Parallel HTTP Range (16 hilos) -> IMAGE, ZODI, FLAGS, VARIANCE, WCS-WAVE
        Eng->>Eng: ZODI Subtraction + BAD_MASK + reproject_interp (2× oversampling)
        Eng->>Eng: Tractor 15×15 + Detector σ_MAD + Reconocedor 3D + MPC 80-Col
        Eng-->>API: Payload JSON (float32 Base64 + telemetría)
    end
```

Para el modo **360° DR1 Oficial**, `ang2pix_nest_scalar(nside, ra, dec)` implementa la codificación exacta **HEALPix `NESTED`** de Górski et al. (2005) —validada frente a `hpgeom` (`ra=60.8109955°, dec=51.3404038°, nside=32 → ipix=445`)— para servir tiles `Norder3` y recortes parciales `Norder5` (`Npix{ipix}_cube.fits`) de `102` canales nominales (`SPHEREX_DR1_WAVELENGTHS_UM`). El cliente aplica LUTs precalculadas de **1024 pasos** a **60 FPS** con aislamiento estricto DOM/WebGL entre `#allskyContainer` y `#skyCanvas`.

### 3.2 Formulación Matemática Verificada en Tiempo Real (`math_telemetry`)
1. **Sustracción Física ZODI y Máscara L2b:**
   $$I_{\text{clean}}(x,y) = \left[\text{IMAGE}(x,y) - \text{ZODI}(x,y)\right] \cdot M_{\text{flags}}(x,y)$$
   `BAD_MASK` filtra los bits críticos `(2, 4, 6, 7, 9, 10, 11, 25, 26, 27)` mientras **preserva `Bit 21 (SOURCE)`**.
2. **Fotometría Forzada Lineal (Tractor 15×15) y Escala WCS:**
   $$\theta = (A^T W A)^{-1} A^T W I \quad \longrightarrow \quad \text{FWHM} = 2.355 \cdot \sigma_{\text{PSF}}$$
   Con sobremuestreo **2×** sobre el píxel nativo `6.15"/px` (`~3.075"/px` a FOV estándar) y ángulo sólido `Ω_pix = 8.894 × 10⁻¹⁰ sr`.
3. **Magnitud Aparente AB:**
   $$m_{\text{AB}} = 23.9001 - 2.5 \cdot \log_{10}(F_{\mu\text{Jy}})$$
4. **Espectroscopía LVF Bilineal Exacta (`WCS-WAVE`):**
   $$\lambda(x,y) = \sum_{i,j \in \{0,1\}} w_{ij}(t_x, t_y) \cdot V_{\text{WAVE}}(i,j)$$
5. **Térmica de Wien y Profundidad Óptica de Hielos Biogénicos (SPLICES):**
   $$\tau(\lambda) = -\ln\!\left[\frac{F_{\text{obs}}(\lambda)}{F_{\text{cont}}(\lambda)}\right]$$
   evaluada en **H₂O (`3.05 µm`)**, **CH₄ (`3.32 µm`)**, **CO₂ (`4.27 µm`)** y **CO (`4.67 µm`)**, con $T_{\text{eff}} \in [220, 4800]\,\text{K}$.
6. **Cinemática Diferencial ($\sigma_{\text{MAD}}$) y Distancia Euclidiana 3D:**
   $$\Delta I = E_n - E_1, \qquad \sigma_{\text{MAD}} = 1.4826 \cdot \text{med}\left|\Delta I - \text{med}(\Delta I)\right|$$
   $$D_{3\text{D}} = \sqrt{d_A^2 + d_B^2 - 2\, d_A\, d_B \cos\theta}$$

### 3.3 Escudo Anti-Artefactos L2b (6 Módulos) + MPC 80-Col + Copiloto IA
- **6 Guardas H2RG / LEO:** (1) *Charge Blooming* Banda 1 en `(1648, 1752)` radio `85 px`, (2) Rayos Cósmicos SUR/SAA (`Bit 0`), (3) Persistencia & Crosstalk 32 canales SIDECAR (`Bits 17/20`), (4) Sustracción `ZODI` + Airglow He I `1.083 µm`, (5) Supresión de trazas satelitales LEO por mediana temporal (`Bits 25/28`), (6) Borde dicroico `2.42 µm` y conservación de fuentes `Bit 21`.
- **IAU MPC 80 Columnas:** `format_mpc_80col()` genera registros ASCII con nota espacial **`S`**, fecha fraccional UTC y código **`C59`**.
- **AstroAI Copilot:** Cascada de 3 niveles: **`gemini-3-flash-preview`** (con captura JPEG de `#skyCanvas`) → **`gemini-flash-lite-latest`** → **`_expert_astrophysics_response`** (motor determinista local con **0 costo y 100% disponibilidad offline**).

### 3.4 Referencia de la API REST (14 Rutas en `app.py`)

| Método | Ruta | Función |
| :--- | :--- | :--- |
| `GET` | `/` | Interfaz web principal (`static/index.html`). |
| `GET / POST / DELETE` | `/api/targets` | CRUD completo de objetivos (incluye `?id=__RESTORE_DEFAULTS__`). |
| `GET` | `/api/resolve?q=...` | Resolución SIMBAD TAP / Astropy Sesame con propagación a `2025.5`. |
| `GET` | `/api/cube` | Cubo multi-época FITS Base64, flags, candidatos IA, métricas Tractor y objetos 3D. |
| `GET` | `/api/point_spectrum` | Espectro LVF (`0.75–5.0 µm`) y curva de luz para cualquier píxel del mapa. |
| `GET` | `/api/catalogs` | Fuentes en vivo de **Gaia DR3** y **AllWISE** vía VizieR TAP. |
| `GET` | `/api/gif` | Renderizado y descarga de animación `.GIF` blink del cubo activo. |
| `POST` | `/api/ai/chat` | Copiloto multimodal (telemetría + captura `#skyCanvas` + historial). |
| `GET` | `/api/docs?lang=es\|en` | Sirve esta documentación integral (`es` / `en`). |
| `GET` | `/api/spherex-allsky-map` | Mapa equirectangular `1440×720` PNG desde el cubo oficial DR1. |
| `GET` | `/api/hips/spherex/{ch}/{tail}` | Proxy IVOA HiPS CORS para Aladin Lite v3 sobre los 102 canales DR1. |
| `GET` | `/static/*`, `/docs/*` | Activos estáticos y descarga Markdown pura. |

---

## Capítulo 4 · Seguridad, Despliegue y Entrega Space Apps

### 4.1 Seguridad de Claves e Instalación Local (`USD 0`)
- `.gitignore` excluye `.env`, `.venv/`, `__pycache__/`, `cache/` y `poc/out/*.fits`. Nunca publiques `GEMINI_API_KEY` en commits; `render.yaml` usa `sync: false`. Sin API Key, el motor determinista local mantiene todas las funciones científicas activas con coste **`USD 0`**.
- **Ejecución Local:**
  ```bash
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1   # Windows | Linux/macOS: source .venv/bin/activate
  pip install -r requirements.txt
  python app.py                   # http://localhost:8050 (con prewarm automático)
  ```
- **Despliegue en Render (`render.yaml`) o Docker (`Dockerfile`):**
  ```bash
  docker build -t spherex-skychrono .
  docker run -d -p 8050:8050 -e GEMINI_API_KEY="opcional" spherex-skychrono
  ```

### 4.2 Guion Rápido de Video Demo (45–55 s) y Postulación Oficial (EN)
1. **0:00–0:12:** Arranca en **`🌌 Universo Observable 360°`** (Aitoff DR1 → Esfera 3D libre → Centro Galáctico / NEP) y haz doble clic en `WISE 0855−0714`.
2. **0:12–0:28:** Alterna `Blink → Diff` revelando el dipolo (`8.1″/yr`), navega libremente por regiones vecinas y activa **`🔭 Astros: ON`** + **`📏 A ↔ B`** para medir distancia cósmica 3D.
3. **0:28–0:45:** Abre el espectro **`Planck + Hielos τ(λ)`**, genera **`📐 Reporte MPC 80-Col` (`C59`)** y pulsa **`💬 Gemini`** en el candidato #1 para mostrar el diagnóstico multimodal sobre `#skyCanvas`.
4. **0:45–0:55:** Muestra **`🏛️ Recursos NASA / IRSA`** y conmutador **`ES / EN`**.

**Texto listo para copiar/pegar en NASA Space Apps (`High-Level Summary`, EN):**
> **SPHEREx SkyChrono** is an open-source 360° astrophysics explorer and multi-epoch time-domain workbench built for NASA's *Planet X and SPHEREx* challenge. Powered directly by NASA/IPAC IRSA's Official SPHEREx DR1 All-Sky Spectral Cube (`10.26131/IRSA679`), IRSA TAP ADQL, and AWS S3 HTTP Byte-Range FITS streaming, SkyChrono delivers unrestricted 360° navigation (Hammer-Aitoff, 3D Sphere, and Aladin Lite v3 HiPS), continuous sky panning/zooming across Level-2b cubes, automated $\sigma_{\text{MAD}}$ kinematic dipole detection, 15×15 Tractor forced photometry, 102-channel `WCS-WAVE` spectroscopy with cryogenic ice $\tau(\lambda)$ fitting, 3D cosmic distance measurement, 80-column IAU MPC (`C59`) reporting, and a multimodal Gemini Vision AstroAI Copilot.

---

## Capítulo 5 · Objetivos, Referencias y DOIs

| Objetivo / Hito | Coordenadas ICRS | Fenómeno Científico Clave |
| :--- | :--- | :--- |
| **WISE 0855−0714** | `133.79513°, -7.24515°` | Enana marrón clase Y más fría (~`250 K`, `2.28 pc`, `~8.1″/año`), brillante en `D6`. |
| **Barnard's Star** | `269.4485°, +4.7394°` | Mayor movimiento propio del cielo (`10.36″/año`, `1.83 pc`, salto de `4.4'` desde J2000). |
| **Epsilon Indi Ba/Bb** | `331.0689°, -56.7938°` | Par binario de enanas marrones `T1+T6` (`3.63 pc`, `4.70″/año`, bandas `H₂O`/`CH₄`). |
| **RW Aurigae** | `76.9565°, +30.4014°` | Binaria joven *T Tauri* con disco de polvo y eclipses variables en `D2–D5`. |
| **R Draconis** | `248.1669°, +66.7549°` | Gigante roja Mira (`P ≈ 245.6 días`, `>2,400 exp`) junto al Polo Eclíptico Norte. |
| **Cometa 3I/ATLAS & Elias 16** | Hitos 360° precargados | Coma interestelar de `CO₂/H₂O` y estrella estándar SPLICES de absorción de hielos. |

### Referencias Oficiales
1. **Archivo Misión SPHEREx en IRSA:** https://irsa.ipac.caltech.edu/Missions/spherex.html
2. **Reto Oficial NASA Space Apps 2026:** https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=resources
3. **SPHEREx Spectral Images & Releases:** https://doi.org/10.26131/IRSA678
4. **SPHEREx DR1 All-Sky Spectral Cube HiPS:** https://doi.org/10.26131/IRSA679
5. **SPHEREx Cutout Service & Archival Data:** https://doi.org/10.26131/IRSA662
6. **Catálogo SPLICES & 3I/ATLAS (IRSA):** https://irsa.ipac.caltech.edu/data/SPHEREx/
7. **Caltech-IPAC SPHEREx Archive Tutorials:** https://github.com/Caltech-IPAC/spherex-archive-tutorials
8. **IAU Minor Planet Center (80-Column Format):** https://www.minorplanetcenter.net/iau/info/OpticalObs.html
9. **Górski, K. M. et al. (2005):** *HEALPix: A Framework for High-Resolution Discretization and Fast Analysis of Data Distributed on the Sphere*, ApJ 622, 759.

---

*Documentación Integral v3.0 · **SPHEREx SkyChrono** · Delegación Zuliana de Astronomía · NASA Space Apps Challenge 2026*
