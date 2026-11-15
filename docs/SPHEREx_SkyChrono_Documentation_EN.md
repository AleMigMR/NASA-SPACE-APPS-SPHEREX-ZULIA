# Complete Documentation — SPHEREx SkyChrono (EN)

**All-sky and time-domain explorer for SPHEREx: multi-epoch blinking of real L2b images, photometry with the official ePSF, 0.75–5.0 µm spectra, and verification of moving or variable candidates · *"Planet X and SPHEREx"* Challenge (NASA Space Apps Challenge 2026 · Delegación Zuliana de Astronomía).**

> [!NOTE]
> Single master document with **Basic Concepts**, **User Manual**, **Methods and API**, **Validation, Security and Deployment**, and **Targets and References**. Use **🌐 View in Español** for the Spanish edition.
>
> **Rigor principle:** every number shown by the app comes from an official product (SPHEREx at IRSA/AWS, Gaia DR3, AllWISE, SIMBAD, JPL Horizons) or from a calculation documented here. When a value does not exist or is not reliable (saturation, low S/N, no parallax), the app says so instead of inventing it.

## Quick Index

- [Chapter 1 · Basic Concepts and the SPHEREx Mission](#chapter-1-basic-concepts-and-the-spherex-mission)
- [Chapter 2 · User Manual](#chapter-2-user-manual)
- [Chapter 3 · Methods, Mathematics and API](#chapter-3-methods-mathematics-and-api)
- [Chapter 4 · Validation, Security and Deployment](#chapter-4-validation-security-and-deployment)
- [Chapter 5 · Targets, References and DOIs](#chapter-5-targets-references-and-dois)

---

## Chapter 1 · Basic Concepts and the SPHEREx Mission

### 1.1 What is SPHEREx?
**SPHEREx** (*Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer*) is a NASA observatory launched on **12 March 2025**. It observes the whole sky from a sun-synchronous polar orbit (~7037 km semi-major axis). Since **1 May 2025** it has been carrying out four complete surveys in 25 months. Its 20 cm telescope feeds **6 H2RG detectors**, each with a **linear variable filter (LVF)**: the wavelength a pixel measures depends on its position on the detector. Pixels are **6.15″** and each exposure lasts **113.58 s**.

| Detector | Range (µm) | Resolution R | What it shows best |
| :--- | :---: | :---: | :--- |
| **D1** | 0.744 – 1.116 | 39 | Stellar continuum; the atmospheric He I line at 1.083 µm contaminates the background |
| **D2** | 1.099 – 1.651 | 41 | H₂O (1.4 µm) and CH₄ (1.6 µm) in cool atmospheres |
| **D3** | 1.636 – 2.421 | 41 | H₂O (1.9 µm), CH₄ (2.2 µm), CO (2.3 µm) |
| **D4** | 2.423 – 3.822 | 35 | H₂O (2.7–3.1 µm, gas or ice), CH₄ (3.3 µm), PAH (3.29 µm) |
| **D5** | 3.809 – 4.420 | 112 | The 4 µm window, CO₂ (4.27 µm, gas or ice) |
| **D6** | 4.412 – 5.002 | 128 | CO (4.67 µm); emission peak of Y dwarfs |

*Source: SPHEREx Explanatory Supplement v2.1, Table 2.* The DR1 All-Sky cube groups the data into **102 channels** (17 per detector); channels 50–51, next to the dichroic split, are empty in DR1.

### 1.2 How motion and variability are detected
- **Blink:** SPHEREx revisits each area roughly every 6 months (more often near the ecliptic poles). Alternating the epochs shows what changes.
- **Difference ($E_n - E_1$):** a moving object leaves a **dipole** (negative where it was, positive where it is); an object that changes brightness leaves a residual at the same place.
- **Beware of undersampling and the LVF:** with 6.15″ pixels the PSF is undersampled (FWHM ≈ 7.5″), so a star's peak changes with its sub-pixel phase. In addition, each exposure measures the source at a different λ. Difference imaging therefore **only proposes** candidates: the app verifies them with exposure-by-exposure ePSF photometry (chapter 3).
- **`ZODI`:** each L2b image includes a zodiacal-light model that is **not** subtracted from `IMAGE`; the app subtracts it.
- **`FLAGS`:** official per-pixel bits (Table 16 of the Supplement). `SOURCE` (bit 21) only means that the pixel belongs to a catalogued source and is **never** masked.

### 1.3 Ice and gas are not the same
The H₂O, CH₄, CO₂ and CO bands appear in two forms:
- **Gas** in cool atmospheres: brown dwarfs such as WISE 0855 or Eps Indi B, M dwarfs and Mira-type giants. This is the case for every challenge target.
- **Ice** on dust grains: background stars seen through molecular clouds (e.g. Elias 16 behind the Taurus cloud) and protostars. This is SPHEREx's science goal with its SPLICES target list.

The app measures an **apparent band depth** and explains which of the two cases applies; it never claims "ice" in a brown dwarf.

### 1.4 Reference planes of the 360° viewer
The universe has no absolute "up". The viewer offers three standard planes: **Galactic** $(l, b)$, **Ecliptic** $(\lambda, \beta)$ (the plane of Earth's orbit and of the SPHEREx surveys) and **Equatorial ICRS** (RA, Dec), the frame of Gaia, SIMBAD and the Minor Planet Center.

---

## Chapter 2 · User Manual

### 2.1 Header and reference targets
- **🏛️ NASA / IRSA Resources:** official challenge links (IRSA, tutorial notebooks, WiseView, Gaia DR3 at MAST, Canadian Space Agency resources) and live links to the current coordinate.
- **📐 MPC Report:** draft in the official two-line satellite format (SPHEREx code **288**). It is only generated for candidates with confirmed motion and no stellar counterpart; otherwise the window explains why it is empty.
- **🔗 Share** and **🎞️ GIF:** reproducible link and animation of the epochs.
- **Reference targets:** when you choose one, the app centres the field on its **position propagated to epoch 2026.0** and propagates its position to the date of **each** exposure to measure it. The tooltip explains which epoch the reference coordinates belong to (e.g. the WISE 0855 coordinates in the challenge statement are from 2010.6).

### 2.2 360° viewer (DR1 All-Sky cube)
Three synchronised views: **Hammer-Aitoff** (true 2:1 aspect ratio), **3D globe** and **Aladin Lite HiPS**. The map uses the official visualisation PNGs (fixed asinh stretch, 0–40 MJy/sr): it is for orientation, not for measurement. Double-click any point to open the multi-epoch exposures of that area.

### 2.3 Image viewer and fullscreen
- **Modes:** Blink, Difference, chronological RGB (R = last epoch, B = first), Co-add and A/B Curtain.
- **Fullscreen:** the **⛶** button next to the zoom controls, or the **F** key; **Esc** to exit. The image is always drawn with square pixels (no distortion of angles or distances).
- **Mouse:** dragging pans the field (the neighbouring field is downloaded on release), the wheel zooms anchored at the cursor, a click measures the source under the cursor and a double-click re-centres.
- **Keyboard:** `Space` plays or pauses, `← / →` change epoch and `F` toggles fullscreen.
- **Marks:** ✚ is the target's **predicted position** at each epoch (Gaia DR3 or literature plus proper motion). Grey areas are pixels without real L2b data. Candidates show ✔ (confirmed by the ePSF), ✖ (not confirmed) or ? (not verifiable).
- **Measured motion:** equation 5 of the maths panel and the copilot analysis compare the shift that **SPHEREx measures** between the first and last visit with the shift the catalogue predicts for the same dates.
- **Field sources:** identified with Gaia DR3 or AllWISE; a distance only appears if there is a parallax with π/σ ≥ 5 or a published distance.
- **📏 Measure A↔B:** the angular separation and position angle are exact; the 3D distance is only computed when both sources have a measured distance.

### 2.4 Right panel
- **Target spectrum:** each point is one L2b exposure measured with the ePSF at its real λ (in µJy, 1σ error). ▼ marks a 3σ upper limit and × a saturated measurement. The yellow line is the 102-channel spectrum of the DR1 co-add at the same position.
- **Apparent band depth:** τ of H₂O 3.0, CH₄ 3.3, CO₂ 4.27 and CO 4.67 µm on the DR1 spectrum, with its error and its interpretation (gas or ice).
- **Light curve per channel:** flux / median for each channel (same λ). Only points of the same colour are comparable.
- **Copilot:** uses Gemini (if a key is available) or a deterministic local engine. In both cases it receives only measured telemetry and is forbidden from inventing values.

### 2.5 Data quality
The **🛡️ Data quality** panel summarises, with data from the current cube: origin (L2b or static DR1), zodiacal light subtracted, percentage of rejected pixels (official list), PSF used (official ePSF or Gaussian), target saturation, satellites and artefacts (`STREAK`, `SATELLITE_HALO`, `BLOOM`, `SNOWBALL`) and warnings about the dichroic edge and He I.

---

## Chapter 3 · Methods, Mathematics and API

### 3.1 Data flow
1. **Exposure search:** IRSA TAP (`spherex.artifact ⋈ spherex.plane`). If TAP fails, **IRSA SIA** is used with the collections `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3` and `spherex_qr3_deep`, the method of the official tutorials. A service that has just failed is not waited for again for 5 minutes. An observation published in several releases is used only once (priority DR1 > QR3 > QR2).
2. **Cutouts:** partial reads (HTTP Range) from `s3://nasa-irsa-spherex/`, with IRSA's IBE cutout service as fallback. The app reads `IMAGE`, `ZODI`, `FLAGS`, `VARIANCE`, the `WCS-WAVE` table, the **ePSF** row of the detector zone (~9 KB) and the full header: `MJD-AVG`, `PSF_FWHM` and the geocentric position of the spacecraft.
3. **No L2b exposures** (or IRSA down): **one** static image from the DR1 All-Sky cube is shown, clearly labelled. There is no blink or difference, because the cube has no time information.

### 3.2 Implemented formulas
1. **Clean image:** $I = \text{IMAGE} - \text{ZODI}$. For display, pixels are rejected with the official list used to build the DR1 cube: `TRANSIENT, SUR_ERROR, NONFUNC, DICHROIC, MISSING_DATA, HOT, COLD, PHANMISS, NONLINEAR, PERSIST, CROSSTALK, STREAK, BLOOM, SNOWBALL, HALO, SATELLITE_HALO`.
2. **Target position:** $(\alpha, \delta)(t)$ = `SkyCoord.apply_space_motion` with $\mu_{\alpha*}$, $\mu_\delta$, $\varpi$ and $v_r$ from the astrometry epoch to the `MJD-AVG` of each exposure. The annual parallax (≤ 0.55″) is neglected because it is smaller than 0.1 pixel. The **measured shift** comes from the mean position of each visit (visits more than 30 days apart) with its standard error: with two visits they are subtracted, and with three or more a weighted linear motion is fitted. It is compared with the shift predicted between the same dates and the difference is reported in σ.
3. **Forced PSF photometry** (Supplement sec. 3.3): $d_j = F\,P_{\text{eff}}(x_j - x_\star) + \sum_k F_k P_{\text{eff}}(x_j - x_k) + B$, solved by weighted least squares $\theta = (A^T W A)^{-1} A^T W d$ with $W = 1/\text{VARIANCE}$. Gaia sources within 20″ ($k$) are fitted at the same time (deblending). Pixels are masked with the official photometry mask: `SUR_ERROR, NONFUNC, MISSING_DATA, HOT, COLD, NONLINEAR, PERSIST, BLOOM, SNOWBALL, HALO, SATELLITE_HALO`.
4. **Flux and error:** $F_{\mu\text{Jy}} = F\,\Omega_{\text{pix}}\,10^{12}$, with $\Omega_{\text{pix}}$ obtained from the Jacobian of the WCS with SIP distortion (≈ 8.86 × 10⁻¹⁰ sr; the nominal value $(6.15'')^2$ is 8.890 × 10⁻¹⁰ sr). The error is $\sigma^2 = \sigma_{\text{stat}}^2 + (0.03F)^2$. The fit quality is $\langle|p-m|/\sigma\rangle$ within r ≤ 2.5 px. If S/N < 3 an **upper limit** $F + 3\sigma$ is reported.
5. **AB magnitude:** $m_{\text{AB}} = 23.9 - 2.5\log_{10}F_{\mu\text{Jy}}$, with $\sigma_m = 1.0857/(S/N)$, for detections only.
6. **Wavelength:** $\lambda(x,y)$ by bilinear interpolation of `WCS-WAVE` at the detector position where the source falls. Error against the official `CWAVE` files: ≤ 5 % of the bandwidth (verified).
7. **Detector and filter edge:** a measurement less than 32 px from the detector edge, or with λ outside the nominal range of the detector (e.g. 5.006 µm in D6), is flagged with a warning and does not count towards variability: in WISE 0855, one such measurement gave ×4.8 the real flux of a neighbouring star. **Saturation:** a measurement is flagged *saturated* if there is `OVERFLOW`, `NONLINEAR` or `BLOOM` within r ≤ 2.5 px, or if ≥ 2 core pixels (r ≤ 1.2 px) are missing. Its flux is not reported, but its **position** is measured with the centroid of the `OVERFLOW` pixels within 4 px of the predicted position (astrometry only). Because the shape of the saturated blob changes with the spacecraft orientation, each visit carries a systematic error of 0.7″ per axis, measured from the scatter between the 8 visits of R Dra.
8. **Candidates:** $\Delta I = E_n - E_1$ and $\sigma_{\text{MAD}} = 1.4826\,\text{med}|\Delta I - \text{med}\,\Delta I|$, with a 5σ threshold and only in pixels with real data in both epochs. Each candidate is **verified with the ePSF**:
   - *motion confirmed* if the centroids of the first and last epoch differ by ≥ 3σ and ≥ 0.3 native pixels;
   - *variability confirmed* if the flux changes by ≥ 5σ between measurements of the **same channel** in at least **two independent pairs** with the same sign (a single pair stays as *possible variability*);
   - *not confirmed* in any other case. Saturated measurements (`OVERFLOW`, `NONLINEAR` or `BLOOM` within r ≤ 2.5 px) do not count: if there are only saturated measurements, the candidate is marked as a *saturated-star artifact*, because blooming changes with the spacecraft orientation and mimics motions of several arcseconds (checked in RW Aur and R Dra).
9. **Light curve:** measurements are grouped by DR1 channel; variability is evaluated with $\chi^2_\nu$ against a constant flux and with the largest change in σ within each channel.
10. **DR1 spectrum:** aperture photometry on the All-Sky cube (r = 25.8″, background in a 51–90″ annulus, order-14 HEALPix $\Omega$ = 3.901 × 10⁻⁹ sr). A channel is flagged saturated if the core has no data, if `NHITS` = 0, or if there is a dip in `NHITS` while the detector shows saturation in other channels. A warning is issued when there are Gaia sources inside the aperture.
11. **Apparent band depth:** $\tau = \ln F_{\text{cont}} - \ln F_{\text{band}}$, with a **power-law** continuum (a straight line in log F – log λ) fitted to windows on both sides of the band and a minimum systematic error of 0.04. If the sampling is insufficient, τ = not measurable. With this continuum, an absorption-free Rayleigh–Jeans tail gives τ = 0.00 (a linear continuum would have given a spurious τ of ~0.19 at 3 µm). A **negative** τ at ≥ 3σ means that the band lies above the interpolated continuum (for example, the 4 µm peak of T dwarfs): the app says so and does not interpret it as absorption.
12. **Distances:** $d = 1000/\varpi$ pc only if $\varpi/\sigma_\varpi \ge 5$ (Gaia DR3), or from the published distance of the reference targets. The 3D distance between A and B, $D = \sqrt{d_A^2 + d_B^2 - 2 d_A d_B \cos\theta}$, is only computed when both exist.
13. **MPC:** two 80-column records: «S» with the position measured by the ePSF and «s» with the geocentric SPHEREx vector in km. That vector is obtained from `X/Y/Z_SC_START` and `_END` by Hermite interpolation to mid-exposure. Observatory code **288**.

### 3.3 HEALPix
The DR1 cube is organised in order-5 NESTED HEALPix tiles (512×512 pixels of 12.9″). The (α, δ) → index conversion follows the HEALPix reference algorithm (Górski et al. 2005) and is validated against `astropy-healpix` at 200,000 random positions with no discrepancies.

### 3.4 REST API (`app.py`)

| Method | Route | Function |
| :--- | :--- | :--- |
| `GET` | `/` | Web interface |
| `GET · POST · DELETE` | `/api/targets` | Targets (the official astrometry cannot be edited) |
| `GET` | `/api/resolve?q=` | Coordinates or name (Sesame/SIMBAD) propagated to 2026.0; recognises the old coordinates of the targets |
| `GET` | `/api/cube` | Multi-epoch cube. Parameters: `ra, dec, fov, bands, max_per_epoch, gap_days, release, target_id` or `pmra, pmdec, plx, ast_ra, ast_dec, ast_epoch` |
| `GET` | `/api/point_spectrum` | Per-exposure ePSF photometry at the chosen pixel |
| `GET` | `/api/dr1_spectrum` | 102-channel spectrum from the DR1 cube, band depths and warnings |
| `GET` | `/api/catalogs` | Gaia DR3 (MAST → VizieR) and AllWISE (VizieR → IRSA Gator) projected onto the grid |
| `GET` | `/api/gif` | GIF of the epochs |
| `POST` | `/api/ai/chat` | Copilot (Gemini key in the `x-goog-api-key` header, never in the URL) |
| `GET` | `/api/docs?lang=` | This documentation |
| `GET` | `/api/spherex-allsky-map` | Equirectangular map of the DR1 cube (visualisation) |
| `GET` | `/api/hips/spherex/{channel}/{path}` | HiPS proxy for Aladin Lite |
| `GET` | `/static/*`, `/docs/*` | Static files |

---

## Chapter 4 · Validation, Security and Deployment

### 4.1 Validation with real data
- **Photometry:** 12 unsaturated stars in a real L2b field (D2, λ ≈ 1.30–1.38 µm) gave a SPHEREx / 2MASS ratio (interpolated between J and H) of **1.03** on average (median 1.02) with 3 % scatter. The propagated Gaia DR3 centroids fell within 0.0–0.1 pixels of the measured stars.
- **Motion measured with real L2b exposures:**
   - **Barnard** (saturated; 28 exposures, 3 visits): the centroid of the saturated core falls a median 1.2″ (0.19 px) from the predicted position. SPHEREx measures **6.59 ± 1.00″** (PA 355°) between 2025-08-25 and 2026-03-30, against 6.19″ (PA 356°) predicted by Gaia DR3 (0.4σ).
   - **Epsilon Indi B** (not saturated; 32 exposures, 6 visits): **6.88 ± 0.25″** (PA 122°) in 519 days, against 6.65″ predicted (1.0σ).
   - **RW Aur** and **R Dra** (saturated, almost no proper motion): 0.56 ± 1.23″ and 1.82 ± 0.83″, both consistent with zero.
- **Candidate verification:** a synthetic 5 mJy source moving 12″, injected into real exposures, was recovered as *motion confirmed 12.0″ ± 0.4″*. Static stars whose peak changed with the sub-pixel phase stayed *not confirmed*.
- **Challenge targets:** see the table in chapter 5 and the `tools/validate_targets.py` tool.
- **Unit tests:** `python -m pytest tests/` (or `python tests/test_science.py`) checks HEALPix, the propagation of WISE 0855 to the AllWISE epoch, the official bits, the AB zero point, the MPC format, the absence of bias in τ and the recovery of an injected flux.

### 4.2 Security
- `.env` is in `.gitignore`. The Gemini key travels in the `x-goog-api-key` header and never in the URL, so it does not end up in logs. Error messages do not echo the request.
- Without a key, every scientific function keeps working and the copilot uses the local engine.

### 4.3 Installation and deployment
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py                      # http://localhost:8050
```
Optional variables: `GEMINI_API_KEY`, `GEMINI_MODEL`, `PORT`, `SPHEREX_TAP_TIMEOUT` (s, default 30), `SPHEREX_SIA_TIMEOUT` (s, default 60) and `SPHEREX_PREWARM=0` (disables pre-loading). With Docker: `docker build -t spherex-skychrono .` and `docker run -p 8050:8050 spherex-skychrono`.

### 4.4 Known limitations
- **Saturation:** Barnard (J ≈ 5.2), RW Aur (K ≈ 7) and R Dra saturate SPHEREx in almost every channel. Their **position** is measured from the saturated core and their motion is visible in the blink, but their fluxes are not reliable.
- **Blending:** in 2025–2026 WISE 0855 passes **8″** from the star Gaia DR3 5756956644387831296 (G = 16.3). With 6.15″ pixels they blend; the L2b photometry separates both sources with the ePSF, but the DR1 spectrum (25.8″ aperture) includes the neighbour.
- **WISE 0855** is faint in SPHEREx (≈ 0.5 mJy at 4.6 µm, W2 ≈ 13.9): expect low S/N per exposure and invisibility below ~3.5 µm.
- **Planet X / Nine** is hypothetical and nobody has detected it. At ~500 AU its parallactic motion would be ~7″ per day. Between visits six months apart it would leave a 0.1° field, so it must be searched for by comparing exposures from the same visit (days).
- **DR1 cube:** 12.9″ pixels and no time information. Its HiPS PNGs are for visualisation only.

### 4.5 Submission text (EN)
> **SPHEREx SkyChrono** is an open-source time-domain explorer for NASA's SPHEREx survey. It blinks real Level-2 spectral images retrieved from IRSA (TAP/SIA) and AWS S3, propagates catalogue astrometry to every exposure, measures fluxes with the official ePSF (variance-weighted forced photometry with Gaia deblending) and verifies every difference-image candidate before calling it motion or variability. It shows 0.75–5 µm spectra from individual exposures and from the DR1 all-sky cube, flags saturation and blending explicitly, and drafts MPC satellite-format astrometry (code 288) only for confirmed movers without a stellar counterpart.

---

## Chapter 5 · Targets, References and DOIs

### 5.1 Challenge targets (astrometry verified in SIMBAD / Gaia DR3)

| Target | Reference position | Proper motion (mas/yr) | Distance | In SPHEREx |
| :--- | :--- | :--- | :--- | :--- |
| **WISE 0855−0714** (Y) | J2000 133.81891°, −7.24705° (Kirkpatrick+2021) · NASA coordinates = epoch 2010.6 | −8123.7, +673.2 | 2.28 pc (ϖ = 439.0 ± 2.4 mas) | In 2026 it is **~2.1′** from the coordinates in the challenge statement. L2b: detected in 9 of 19 exposures at 4.4–5.0 µm (S/N ≈ 4) 1.1″ from the predicted position. 8″ from a G = 16.3 star: the ePSF separates them, but in DR1 the neighbour dominates below 3.5 µm and at 4.6 µm DR1 gives 0.58 ± 0.32 mJy (no significant detection). |
| **Barnard's Star** (M4V) | J2000 269.45208°, +4.69336° (Gaia DR3) | −801.6, +10362.4 | 1.828 pc | **Saturated** in 28/28 L2b exposures and 99/100 DR1 channels: flux not measurable. Position measured 1.2″ from the prediction; SPHEREx measures **6.59 ± 1.00″** in 217 d against 6.19″ predicted. |
| **Epsilon Indi Ba/Bb** (T1 + T6) | J2000 331.04415°, −56.78284° (Gaia DR3) | +3982.0, −2466.8 | 3.64 pc (ε Ind system) | Not saturated: 32/32 L2b detections (S/N ≈ 32); SPHEREx measures **6.88 ± 0.25″** in 519 d against 6.65″. T-dwarf SED in DR1: 31 mJy (1.25 µm), 36 (1.66), 25 (2.19), 8 (3.29), 63 (4.0) and 18 mJy (4.6 µm); **τ(CH₄ 3.3 µm) = 1.51 ± 0.05** and τ(H₂O 3.0 µm) = 0.52 ± 0.05 (gas). |
| **RW Aurigae A** (T Tauri) | Gaia DR3 2016.0: 76.95608°, +30.40120° | +2.6, −27.4 | 156 pc | **Saturated** in 24/24 L2b exposures and ~48 DR1 channels. A false 9.5″ motion on its blooming is marked as an artifact. |
| **R Draconis** (Mira, P ≈ 245.6 d) | Gaia DR3 2016.0: 248.16738°, +66.75501° | −20.6, +6.1 | ~800 pc (Mira parallax, use with caution) | **Saturated** in 64/64 L2b exposures (8 visits) and all 100 DR1 channels. Its blooming artifacts are marked as such. |

The `tools/validate_targets.py` tool repeats this validation with real L2b exposures: measured versus predicted offset, detections, saturation and candidates.

### 5.2 Landmarks of the 360° map
The coordinates were verified in SIMBAD and JPL Horizons. **Elias 16** is at 69.912°, +26.191° (K1III background giant behind the Taurus cloud). **3I/ATLAS** is shown at its geocentric position on 2025-08-08: SPHEREx observed it from 1 to 15 August 2025 (Lisse et al. 2026) and it moves ~1° per day. A supposed "Planet X candidate" with invented coordinates and parameters was removed.

### 5.3 References
1. SPHEREx Explanatory Supplement v2.1 (2026-11-10): https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf
2. SPHEREx archive at IRSA: https://irsa.ipac.caltech.edu/Missions/spherex.html
3. Official tutorials: https://caltech-ipac.github.io/irsa-tutorials/spherex/
4. Challenge resources: https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=resources
5. Gaia DR3 at MAST: https://archive.stsci.edu/missions-and-data/gaia
6. WiseView: http://byw.tools/wiseview
7. MPC, format for observations from satellites: https://www.minorplanetcenter.net/iau/info/SatelliteObs.html (SPHEREx = code 288)
8. Kirkpatrick, J. D. et al. 2021, ApJS 253, 7 (WISE 0855). Luhman, K. L. 2014, ApJL 786, L18. Luhman, K. L. et al. 2024, AJ 167, 5.
9. King, R. R. et al. 2010, A&A 510, A99 (ε Indi Ba/Bb).
10. Rustamkulov, Z. et al. 2026, *SPHEREx 0.75 to 5 µm Spectra for a Sequence of Nearby Brown Dwarfs*, arXiv:2607.00543.
11. Lisse, C. M. et al. 2026, ApJL 1000, L52 (3I/ATLAS with SPHEREx).
12. Górski, K. M. et al. 2005, ApJ 622, 759 (HEALPix).

### 5.4 Data DOIs
- SPHEREx DR1 Spectral Images: [10.26131/IRSA678](https://doi.org/10.26131/IRSA678)
- SPHEREx DR1 Spectral All-Sky Cube: [10.26131/IRSA679](https://doi.org/10.26131/IRSA679)
- SPHEREx Quick Release Spectral Images – QR3: [10.26131/IRSA662](https://doi.org/10.26131/IRSA662)
- SPLICES (SPHEREx Target List of Ice Sources): [10.26131/IRSA554](https://doi.org/10.26131/IRSA554)

> *Required acknowledgment:* This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.

---

*Complete Documentation v4.0 · **SPHEREx SkyChrono** · Delegación Zuliana de Astronomía · NASA Space Apps Challenge 2026*
