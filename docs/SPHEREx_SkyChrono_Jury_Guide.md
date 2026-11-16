# SPHEREx SkyChrono
## Technical and Scientific Jury Guide
**NASA International Space Apps Challenge 2026 — “Planet X and SPHEREx” · Evento Universal**

**Team:** Stars Finders — Delegación Zuliana de Astronomía  
**Project lead:** Jesús Durán · **Programming:** Alejandro Montiel and José Montiel · **Research:** Jeshua Durán  
**Website:** https://skychrono.earth · **Video (30 s):** [watch](https://skychrono.earth/docs/media/SPHEREx_SkyChrono_presentation.mp4) · **Repository:** https://github.com/AleMigMR/NASA-SPACE-APPS-SPHEREX-ZULIA

> **Companion documents:** [Beginner's Guide](SPHEREx_SkyChrono_Beginners_Guide.md) · [User Guide](SPHEREx_SkyChrono_User_Guide.md) · [Complete documentation (EN)](SPHEREx_SkyChrono_Documentation_EN.md) · [README](../README.md)

---

## Contents

1. [Summary](#1-summary)
2. [The problem and our approach](#2-the-problem-and-our-approach)
3. [Data and provenance](#3-data-and-provenance)
4. [Methods](#4-methods)
5. [Validation with the five challenge targets](#5-validation-with-the-five-challenge-targets)
6. [Architecture, performance and tests](#6-architecture-performance-and-tests)
7. [Security and privacy](#7-security-and-privacy)
8. [Use of artificial intelligence](#8-use-of-artificial-intelligence)
9. [Known limitations](#9-known-limitations)
10. [Suggested demonstration](#10-suggested-demonstration)
11. [References](#11-references)

---

## 1. Summary

**SPHEREx SkyChrono** is an open-source web application that turns SPHEREx survey data into a time-domain tool. For any point in the sky, it finds the individual SPHEREx Level-2b exposures that cover it, plays the visits as a blink sequence, and **measures** what it shows: forced photometry with the official ePSF, positions propagated from Gaia DR3, motion measured between visits, and a rule-based verification of every candidate before it is called motion or variability.

What the jury can check in the application and in this repository:

- **Real multi-epoch data, not a static map.** All five challenge targets have 3 to 8 SPHEREx visits; the blink, difference and RGB views show those real exposures.
- **SPHEREx measures proper motion.** For Barnard's Star the motion measured between visits is 6.59 ± 1.00″ against 6.19″ predicted by Gaia DR3 (0.4σ). For Epsilon Indi Ba/Bb it is 6.88 ± 0.25″ against 6.65″ (1.0σ).
- **Every number is traceable.** Each value comes from an official product (SPHEREx at IRSA/AWS, Gaia DR3, AllWISE, SIMBAD) or from a documented formula. When something cannot be measured (saturation, low S/N, no parallax), the application says so instead of inventing a value.
- **False positives are rejected.** Difference-image peaks are confirmed or rejected with exposure-by-exposure ePSF measurements. Saturated stars, detector edges and wavelength differences are handled explicitly.
- **29 automated tests** and a validation tool (`tools/validate_targets.py`) reproduce the results with real data.

## 2. The problem and our approach

The challenge asks how SPHEREx data can help search for objects such as the hypothetical Planet X. SPHEREx (launched in March 2025) maps the whole sky in **102 spectral channels between 0.75 and 5.0 µm**. It uses six detectors, each behind a **linear variable filter (LVF)**: the wavelength a pixel measures depends on where the source falls on the detector. Pixels are 6.15″, and each part of the sky is revisited roughly every six months (more often near the ecliptic poles).

That design creates three difficulties for anyone looking for moving or variable sources:

1. **The all-sky cube has no time axis.** The DR1 All-Sky Cube is a one-year co-add. Motion and variability can only be studied with the individual Level-2b exposures, which must be found and downloaded per position.
2. **The same source is measured at a different wavelength in each exposure** because of the LVF, so a simple brightness comparison can mistake a spectral difference for variability.
3. **The PSF is undersampled** (FWHM ≈ 7.5″ on 6.15″ pixels): a star's peak changes with its sub-pixel position, so a difference image produces residuals even for stars that do not move.

SkyChrono addresses each one. It works directly on the Level-2b exposures; it compares brightness only within the same spectral channel; and it treats difference images as a **candidate finder only**, confirming or rejecting each candidate with the same forced-ePSF method used by the official pipeline.

## 3. Data and provenance

### 3.1 Sources

| Data | Identifier | How SkyChrono uses it |
|---|---|---|
| SPHEREx Level-2b spectral images (DR1, QR3) | DOI [10.26131/IRSA678](https://doi.org/10.26131/IRSA678) · QR3 [10.26131/IRSA662](https://doi.org/10.26131/IRSA662) | Multi-epoch images, photometry, astrometry and candidate verification |
| SPHEREx DR1 Spectral All-Sky Cube | DOI [10.26131/IRSA679](https://doi.org/10.26131/IRSA679) | 102-channel reference spectrum at the target position; official HiPS for the 360° view (visualisation only) |
| Gaia DR3 (MAST, VizieR fallback) | — | Reference astrometry, proper motions, parallaxes and deblending of neighbours |
| AllWISE (VizieR, IRSA Gator fallback) | — | Identification of infrared field sources |
| SIMBAD / Sesame | — | Name resolution |
| Literature astrometry | Kirkpatrick et al. 2021 (WISE 0855−0714) | Proper motion and parallax of WISE 0855−0714, which has no Gaia astrometry |

### 3.2 How the exposures are found and read

1. **Discovery.** IRSA TAP (`spherex.artifact` joined with `spherex.plane`) and IRSA SIA (collections `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`) are queried in parallel and the first valid answer is used. An observation published in several releases is used once (priority DR1 > QR3 > QR2). Short IRSA outages are retried automatically.
2. **Reading.** The images are read from the AWS Open Data bucket `s3://nasa-irsa-spherex/` with HTTP range requests: only the rows needed for the field are downloaded from each layer. IRSA's IBE cutout service is the fallback. For each exposure SkyChrono reads `IMAGE`, `ZODI`, `FLAGS`, `VARIANCE`, the `WCS-WAVE` table, the ePSF of the detector zone, and the header (including `MJD-AVG` and the spacecraft position).
3. **Grouping into visits.** Exposures are grouped into visits by observation date, with a user-selected minimum gap (15 to 90 days; 45 by default).
4. **Fallback for the challenge targets.** The official exposure lists returned by IRSA SIA for the five targets are stored in `data/spherex_exposure_index/` with their query date. If IRSA does not respond, the blink still works, because the images themselves are always read from the official archive.
5. **Static fallback.** If a position has no Level-2b exposures available, SkyChrono shows **one** image from the DR1 cube, labelled “Static DR1 (no L2b available)”. It offers no blink or difference there, and retries IRSA automatically about once a minute.

### 3.3 Provenance shown in the interface

- The viewer label gives the epoch, date, MJD, number of exposures, detector and wavelength range of the frame shown, for example “2025-05-05 (MJD 60800.75) · 3 exp [D6] · λ 4.86–5.003 µm”.
- The **L2b exposure log** lists every exposure with its observation ID (`OBS_ID`), detector, wavelength at the target, UTC date, ePSF flux, quality and subtracted zodiacal light.
- The **Data Quality** panel tags each value by origin (official product, subtracted, masked, measured or derived) and shows the formula and measured value behind it.

### 3.4 What each product can and cannot establish

| Product | Supports | Does not establish |
|---|---|---|
| Level-2b exposures | Positions and fluxes at known times and wavelengths | Nothing on its own without quality checks and comparable wavelengths |
| DR1 All-Sky Cube | Sky context and a 102-channel co-added spectrum | Motion or variability (no time information; 12.9″ pixels) |
| Gaia DR3 / literature | Predicted positions at any date | A SPHEREx detection |
| HiPS images in the 360° view | Orientation | Any measurement (fixed visual stretch) |

## 4. Methods

All methods are deterministic, documented in Chapter 3 of the [complete documentation](SPHEREx_SkyChrono_Documentation_EN.md), and implemented in `spherex_engine.py`.

### 4.1 Image preparation

Each L2b exposure contains a zodiacal-light model in its `ZODI` layer that is not subtracted from `IMAGE`. SkyChrono subtracts it:

$$
I = \mathrm{IMAGE} - \mathrm{ZODI}
$$

For display, pixels are rejected using the official list of `FLAGS` bits that the pipeline rejects when building the DR1 cube (Table 16 of the Explanatory Supplement). `SOURCE` (bit 21) only marks catalogued sources and is never masked. The exposures of a visit are reprojected onto a common grid for display, always drawn with square pixels; all measurements are made on the native exposure pixels.

### 4.2 Display modes

**Blink** (visits in sequence), **Difference** ($E_n - E_1$), **Chronological RGB** (R = last epoch, B = first), **Co-add** and **A/B Curtain**. These are visual screening tools; the measurements below decide whether a change is real.

### 4.3 Forced ePSF photometry

The flux of the target and of every Gaia source within 20″ is fitted at the same time with the official effective PSF $P_{\mathrm{eff}}$ of the detector zone, as in the pipeline (Explanatory Supplement, sec. 3.3):

$$
d_j = F\,P_{\mathrm{eff}}(x_j - x_\star) + \sum_k F_k\,P_{\mathrm{eff}}(x_j - x_k) + B
$$

The system is solved by weighted least squares with $W = 1/\mathrm{VARIANCE}$, masking pixels with the official photometry flags. The flux is converted to µJy with the pixel solid angle from the WCS ($F_{\mu\mathrm{Jy}} = F\,\Omega_{\mathrm{pix}}\,10^{12}$), and a 3 % systematic is added in quadrature:

$$
\sigma_F^2 = \sigma_{\mathrm{stat}}^2 + (0.03\,F)^2, \qquad \mathrm{S/N} = F/\sigma_F
$$

Below S/N = 3 an upper limit $F + 3\sigma_F$ is reported instead of a detection. For detections, the AB magnitude is $m_{\mathrm{AB}} = 23.9 - 2.5\log_{10}F_{\mu\mathrm{Jy}}$. A measurement is flagged **saturated** when `OVERFLOW`, `NONLINEAR` or `BLOOM` pixels lie within 2.5 px; its flux is never reported. Against 2MASS, twelve unsaturated stars gave a mean SPHEREx/2MASS flux ratio of 1.03 with 3 % scatter.

### 4.4 Astrometry and measured motion

- **Prediction.** The catalogue position is propagated to the `MJD-AVG` of each exposure with `SkyCoord.apply_space_motion`, using the proper motion, parallax and radial velocity (Gaia DR3, or Kirkpatrick et al. 2021 for WISE 0855−0714). The predicted position is shown as ✚ in every frame.
- **Measurement.** The ePSF fit gives a sub-pixel position in each exposure. For saturated stars, the position is the centroid of the saturated `OVERFLOW` core, with a 0.7″ per-axis systematic per visit (measured from the scatter of R Draconis's 8 visits).
- **Motion.** Positions are averaged per visit. With two visits they are subtracted; with three or more, a weighted linear motion is fitted. The result is compared with the shift predicted for the same dates, and the difference is reported in σ.
- **Labels.** The interface separates three values that are often confused: “Expected motion (catalogue astrometry)”, “Motion measured by SPHEREx”, and the ✚ predicted position.

### 4.5 Candidate detection and verification

The candidate detector is **rule-based, not a machine-learning model**:

1. In the difference image $\Delta I = E_n - E_1$, peaks above $5\sigma$ are candidates, where $\sigma_{\mathrm{MAD}} = 1.4826\,\mathrm{med}\,|\Delta I - \mathrm{med}\,\Delta I|$, using only pixels with real data in both epochs.
2. Each candidate is measured with the ePSF in the individual exposures of the first and last epoch:
   - **confirmed motion** if the centroid shift is ≥ 3σ and ≥ 0.3 native pixels;
   - **confirmed variability** if the flux changes by ≥ 5σ between measurements in the **same spectral channel**, in at least two independent pairs with the same sign (a single pair is reported only as possible variability);
   - **not confirmed** otherwise.
3. Saturated measurements, measurements within 32 px of the detector edge, and measurements outside the detector's nominal wavelength range do not count. If only saturated measurements exist, the candidate is labelled a **saturated-star artefact**: blooming changes shape with the spacecraft orientation and mimics motions of several arcseconds.

In a test, a synthetic 5 mJy source moving 12″, injected into real exposures, was recovered as confirmed motion of 12.0 ± 0.4″, while static stars whose peak changed with the sub-pixel phase stayed not confirmed. An astrometric report in the Minor Planet Center satellite format (observatory code 288) is drafted only for a confirmed mover without a stellar counterpart.

### 4.6 Spectra and composition

- **Per exposure:** the wavelength at the source comes from bilinear interpolation of the official `WCS-WAVE` table at its detector position (within 5 % of the bandwidth of the official `CWAVE` files).
- **DR1 spectrum:** aperture photometry on the All-Sky Cube (r = 25.8″, background annulus 51–90″) in all 102 channels. Saturated channels and Gaia neighbours inside the aperture are flagged. Channels 50–51, at the dichroic boundary, are empty in DR1.
- **Band depths:** for H₂O 3.0, CH₄ 3.3, CO₂ 4.27 and CO 4.67 µm, $\tau = \ln F_{\mathrm{cont}} - \ln F_{\mathrm{band}}$ against a power-law continuum, with a minimum error of 0.04. A band is “not measurable” when sampling is insufficient. A negative τ at ≥ 3σ is reported as “above continuum”, not as absorption.
- **Interpretation:** bands are interpreted as **gas** in cool atmospheres (all challenge targets) or as **ice** on dust grains only where that applies. The application reports a band depth as a spectral diagnostic, not as a confirmed chemical identification.

## 5. Validation with the five challenge targets

Results of SkyChrono on real Level-2b exposures. Values change slightly as new exposures are released; the run can be repeated with `python tools/validate_targets.py`.

| Target | Reference astrometry | Result | What it demonstrates |
|---|---|---|---|
| **Barnard's Star** (M4V, 1.83 pc) | Gaia DR3: μ = (−801.6, +10362.4) mas/yr | Saturated in 28 of 28 exposures, so no flux is reported. The saturated-core centroid lies 1.2″ (0.19 px) from the prediction. Measured shift **6.59 ± 1.00″** (PA 355°) between 2025-08-25 and 2026-03-30, against **6.19″** (PA 356°) predicted: 0.4σ. | Proper motion measured with SPHEREx even for a saturated star |
| **Epsilon Indi Ba/Bb** (T1 + T6, 3.64 pc) | Gaia DR3: μ = (+3982.0, −2466.8) mas/yr | Detected in 32 of 32 exposures (S/N ≈ 32) at a median 0.0″ from the prediction. Measured **6.88 ± 0.25″** (PA 122°) in 519 days, against **6.65″**: 1.0σ. The difference image flags it as confirmed motion. DR1: τ(CH₄ 3.3 µm) = 1.51 ± 0.05 and τ(H₂O 3.0 µm) = 0.52 ± 0.05, gas absorption. The two components (about 0.7″ apart) are not resolved. | ePSF photometry, motion verification and molecular bands |
| **WISE 0855−0714** (Y dwarf, 2.28 pc) | Kirkpatrick et al. 2021: μ = (−8123.7, +673.2) mas/yr, ϖ = 439.0 mas | The challenge coordinates are from the AllWISE epoch (2010.6); in 2026 the object is about 2.1′ away, and SkyChrono propagates its position to each exposure. Detected in 9 of 19 exposures at 4.4–5.0 µm over 3 visits (S/N ≈ 4; best 1.0 ± 0.2 mJy at 4.74 µm), at a median 1.1″ from the prediction. A G = 16.3 star 8″ away is separated by the ePSF, but dominates the DR1 aperture below 3.5 µm. | Correct epoch handling for a faint, fast-moving object; blending reported |
| **RW Aurigae A** (T Tauri, 156 pc) | Gaia DR3 (2016.0) | Saturated in 24 of 24 exposures. Measured motion 0.56 ± 1.23″ in one year, consistent with zero as expected. A false 9.5″ “motion” on its blooming is labelled a saturated-star artefact. | Rejection of a saturation false positive |
| **R Draconis** (Mira, ~800 pc) | Gaia DR3 (2016.0) | Saturated in 64 of 64 exposures (8 visits). Measured motion 1.82 ± 0.83″ in 503 days (2.2σ, not significant). Blooming artefacts labelled as such; no light curve is claimed because no flux is measurable. | Honest reporting when variability cannot be measured |

Saturation is reported as a result in its own right: for the bright targets, the application states that the flux cannot be measured instead of producing a light curve.

## 6. Architecture, performance and tests

**Stack:** Python 3.11+ (aiohttp, NumPy, SciPy, Astropy, reproject, s3fs, Pillow) for the backend and the science; HTML, CSS and JavaScript (Canvas 2D, Aladin Lite v3) for the interface, in Spanish and English.

| Layer | Code | Role |
|---|---|---|
| Interface | `static/index.html`, `static/app.js`, `static/styles.css` | Viewer and display modes, 360° view, spectrum, data quality, copilot |
| API | `app.py` (aiohttp) | REST endpoints such as `/api/cube`, `/api/point_spectrum`, `/api/dr1_spectrum`, `/api/catalogs`, `/api/gif` and `/api/ai/*`, plus a HiPS proxy |
| Science engine | `spherex_engine.py` | Discovery, S3 reads, ZODI and FLAGS, ePSF photometry, astrometry, verification, spectra, MPC report |
| Data | `data/spherex_exposure_index/`, `cache/` (not versioned) | Stored official exposure lists; on-disk cache rebuilt every 7 days |

- **Access:** the source code is public in the repository above. The application runs locally with `python app.py`, and a Dockerfile and a Render configuration are included.
- **Performance:** a field that has never been loaded takes about 30 s, mostly archive queries. While panning, a neighbouring field appears in about 1–3 s, because the exposure list and catalogues are reused and nearby fields are prefetched.
- **Tests:** 29 offline tests (`tests/test_science.py`, `tests/test_copilot.py`). They cover HEALPix indexing (0 mismatches against `astropy-healpix` in 200,000 positions), astrometric propagation of WISE 0855−0714, the official flag bits, the AB zero point, the MPC format, unbiased band depths, recovery of an injected flux, the fallback when IRSA does not respond, and copilot key handling. The interface has been tested in Chromium.

## 7. Security and privacy

- Every scientific function works **without any API key**.
- A key pasted into the interface stays only in that browser tab (`sessionStorage`) and is never written to disk or to logs. It is checked with the provider before use, and the check never returns it.
- The Gemini key travels in the `x-goog-api-key` header and the OpenAI key in the `Authorization` header, never in a URL. Provider error messages are shown without fragments of the key.
- The server's optional `.env` file is excluded from Git. No personal data are collected.

## 8. Use of artificial intelligence

### 8.1 During development

The team used **Antigravity (Argon)** and **Claude Opus** as development assistants, mainly to:

- generate base code that the team then integrated and adapted;
- get advanced astronomy guidance, for example on SPHEREx data products, ePSF photometry and astrometric propagation;
- solve very complex debugging cases and advanced programming problems.

These tools were a valuable support, not the authors of the project. The team defined the goals and the scientific requirements, chose the targets and the approach, directed the development, reviewed and tested the results, and is responsible for every decision in the application.

### 8.2 Inside the application

- **No measurement is produced by AI.** Positions, fluxes, motions, band depths and candidate verdicts come from the deterministic code described in Section 4, which can be read and tested in the repository.
- **The AstroAI Copilot only explains.** It receives the measured telemetry of the current field, with explicit rules that forbid inventing values. With a user's key it uses Gemini or OpenAI; without one, a deterministic local engine (no generative AI) writes the summary from the same measurements. The interface always shows which engine answered.

## 9. Known limitations

1. **Saturation.** Barnard's Star, RW Aurigae and R Draconis saturate SPHEREx in almost every channel: their positions are measured, but their fluxes are not.
2. **Few epochs.** Most of the sky has a visit every six months, so a light curve has only a few points, and each exposure measures a different wavelength. Variability is therefore evaluated only within the same channel.
3. **Undersampling and blending.** With 6.15″ pixels, close sources blend. The ePSF fit separates known Gaia neighbours in Level-2b images, but the DR1 aperture (25.8″) can still include them.
4. **Faint sources.** WISE 0855−0714 has S/N ≈ 4 per exposure and is not detected below about 3.5 µm.
5. **Planet X.** It is a hypothetical object that has not been detected. At about 500 AU it would move about 7″ per day, so it would have to be searched for within a single SPHEREx visit (days), not between visits six months apart. The DR1 cube (12.9″ pixels, one-year co-add) is not suitable for that search. SkyChrono is a tool to find and test candidates; it claims no discovery.
6. **No permanent public deployment.** The application runs locally or in a container.

## 10. Suggested demonstration

1. **Barnard's Star.** Select it in Reference Targets and play the blink: the star shifts against the field. Open the copilot (“What is moving here?”) to see the measured motion against the Gaia prediction, and note that its flux is reported as saturated.
2. **Epsilon Indi Ba/Bb.** Show the confirmed-motion candidate, the per-exposure ePSF fluxes over the DR1 spectrum, and the CH₄ and H₂O band depths.
3. **WISE 0855−0714.** Show that the challenge coordinates are from 2010.6 and that the predicted position ✚ follows the object in D5–D6.
4. **Data quality.** Open the Data Quality panel and the L2b exposure log to show the official flags, the subtracted ZODI, and the date and wavelength of each exposure.
5. **A false positive.** In RW Aurigae, show the blooming candidate labelled as a saturated-star artefact.

## 11. References

1. SPHEREx Explanatory Supplement: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf
2. SPHEREx archive at NASA/IPAC IRSA: https://irsa.ipac.caltech.edu/Missions/spherex.html
3. Official IRSA SPHEREx tutorials: https://caltech-ipac.github.io/irsa-tutorials/spherex/
4. SPHEREx DR1 Spectral Images, DOI [10.26131/IRSA678](https://doi.org/10.26131/IRSA678); DR1 Spectral All-Sky Cube, DOI [10.26131/IRSA679](https://doi.org/10.26131/IRSA679); QR3, DOI [10.26131/IRSA662](https://doi.org/10.26131/IRSA662)
5. NASA Space Apps Challenge 2026, Planet X and SPHEREx: https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/
6. Gaia DR3 at MAST: https://archive.stsci.edu/missions-and-data/gaia
7. Minor Planet Center, observations from satellites: https://www.minorplanetcenter.net/iau/info/SatelliteObs.html
8. Kirkpatrick, J. D. et al. 2021, ApJS 253, 7 (WISE 0855−0714 astrometry)
9. Górski, K. M. et al. 2005, ApJ 622, 759 (HEALPix)

**Data acknowledgement:** This application makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, funded by the National Aeronautics and Space Administration.

---

**SPHEREx SkyChrono — Stars Finders, Delegación Zuliana de Astronomía**  
*Technical and Scientific Jury Guide · NASA Space Apps Challenge 2026*
