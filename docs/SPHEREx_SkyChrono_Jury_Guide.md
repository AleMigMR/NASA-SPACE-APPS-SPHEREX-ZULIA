# SPHEREx SkyChrono
## NASA Space Apps Challenge — Planet X and SPHEREx
### Technical and Scientific Jury Guide

**Team:** Stars Finders — Delegación Zuliana  
**Event:** NASA International Space Apps Challenge 2026 — Evento Universal  
**Project lead:** Jesús Durán  
**Programming:** Alejandro Montiel and José Montiel  
**Research:** Jeshua Durán  
**Repository:** https://github.com/AleMigMR/NASA-SPACE-APPS-SPHEREX-ZULIA

> **Companion documents:** [Beginner's Guide](SPHEREx_SkyChrono_Beginners_Guide.md) · [User Guide](SPHEREx_SkyChrono_User_Guide.md) · [Complete documentation (EN)](SPHEREx_SkyChrono_Documentation_EN.md) · [README](../README.md)

---

## 1. Purpose of this document

This guide presents SPHEREx SkyChrono to technical and scientific evaluators. It explains the problem addressed, the mission data context, the application's workflow and computational approach, the validation targets, and the limits that must be considered when interpreting its outputs.

SkyChrono is an exploratory analysis and visualization application designed for the **Planet X and SPHEREx** challenge. Its central idea is to make multi-epoch infrared observations easier to inspect: users can navigate to a sky position, inspect available SPHEREx data, compare observations when suitable epochs exist, and investigate candidate motion or brightness changes.

The application should be understood as a research-support and educational tool. It does not replace the SPHEREx science pipeline, the official IRSA archive, or a peer-reviewed astrophysical analysis. Scientific conclusions depend on the provenance, calibration, quality, temporal coverage, and suitability of the data selected for each target.

## 2. Executive overview

SPHEREx SkyChrono brings several tasks into one browser-based environment:

- celestial navigation by sky map, object name, or equatorial coordinates;
- inspection of SPHEREx infrared data across the mission's six detector arrays and 102 nominal spectral channels;
- chronological image playback and side-by-side or difference-style comparisons when multiple compatible observations are available;
- visualization tools such as false-colour rendering, co-addition, and an A/B comparison curtain;
- inspection of source candidates, spectra, exposure metadata, and data-quality information;
- measurement-oriented tools, including source-centroiding and proper-motion estimates, where the necessary observations and astrometric inputs are available;
- a conversational assistant intended to explain the interface and help users understand analysis concepts.

The design aims to shorten the path from “I have a sky position” to “I can inspect the available infrared observations and determine whether there is enough evidence to investigate a candidate.”

**Important distinction:** a static all-sky cube is not a time series. If no individual multi-epoch exposures are available for a target, the application must report that limitation rather than present a static image as evidence of motion or variability. SkyChrono shows this state explicitly: the status bar reads “Static DR1 (no L2b available)” and the viewer states that there is no real blink, difference or light curve for that field. This is a scientifically important safeguard, not a failed detection.

## 3. Scientific context: what SPHEREx contributes

The Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx) is a NASA astrophysics mission launched in March 2025. It is conducting an all-sky spectroscopic survey from approximately **0.75 to 5.0 micrometres (µm)**. Its instrument uses six detector arrays and linear variable filters (LVFs) to obtain low-resolution spectra over a large number of sky positions.

SPHEREx data can support investigations beyond the mission's principal cosmology and galaxy/ice science goals. For the Planet X challenge, its infrared observations are potentially useful for examining sources whose infrared colours or spectra are of interest, and for exploring changes between observations when temporal data are available.

SPHEREx is not, by itself, a dedicated moving-object discovery system. A moving-object claim requires correctly associated observations at different times, astrometric calibration, consistent coordinate handling, and checks against artifacts and known sources.

### 3.1 Six detector arrays

The application presents the six detector ranges as follows. The ranges below are rounded display ranges; the official instrument documentation gives slightly different boundary values in some bands.

| Detector | Approximate wavelength range | Broad observational relevance |
|---|---:|---|
| D1 | 0.75–1.10 µm | Near-infrared continuum and shorter-wavelength source information |
| D2 | 1.10–1.63 µm | Near-infrared source colours and spectral structure |
| D3 | 1.63–2.42 µm | Near-infrared continuum and molecular-feature regions |
| D4 | 2.42–3.82 µm | Longer near-infrared features, including regions relevant to water and hydrocarbon absorption |
| D5 | 3.82–4.42 µm | Mid-infrared spectral region, including the vicinity of the CO₂ feature near 4.27 µm |
| D6 | 4.42–5.00 µm | Longest SPHEREx wavelength range, including the vicinity of the CO feature near 4.67 µm |

The instrument's 102 nominal spectral channels are distributed across the six arrays. A detector selection is therefore a selection of wavelength coverage, not a claim that each detector independently contains 102 channels.

### 3.2 Wavelength and infrared radiation

Wavelength, usually written as **λ**, is the distance between successive wave crests. It is commonly expressed in micrometres for SPHEREx. The infrared region lies beyond visible red light and is useful for studying cool objects, dust-obscured regions, and molecular absorption or emission features.

A spectrum plots measured flux against wavelength. A feature in a spectrum can be consistent with a molecule or physical process, but identifying composition requires more than seeing a peak or dip: calibration, uncertainty, spectral resolution, signal-to-noise, and comparison with suitable reference spectra are essential.

### 3.3 Equatorial coordinates: Right Ascension and Declination

SkyChrono accepts **Right Ascension (RA)** and **Declination (Dec)** to specify a sky position.

- **RA** is the celestial equivalent of longitude. It is commonly expressed in degrees or hours, minutes, and seconds.
- **Dec** is the celestial equivalent of latitude and is expressed in degrees north or south of the celestial equator.

The coordinate frame and epoch matter. Sky positions from different catalogues or observation dates may require transformations or proper-motion propagation before they are compared. SkyChrono's displayed coordinates should be interpreted with the coordinate system stated by the data product, such as ICRS.

## 4. Data sources and provenance

SkyChrono reads only public, official data: SPHEREx Level-2b spectral images (DR1 and QR3 releases), located with the IRSA TAP and SIA services and read directly from the AWS Open Data bucket `s3://nasa-irsa-spherex/` (IRSA IBE cutouts as fallback); the SPHEREx DR1 Spectral All-Sky Cube (order-5 HEALPix tiles, plus the official HiPS for visualisation); Gaia DR3 (MAST, VizieR fallback); AllWISE (VizieR, IRSA Gator fallback); and SIMBAD/Sesame for name resolution. Aladin Lite v3 is used only for interactive sky visualisation. The interface cites the data DOIs:

- **SPHEREx DR1 Spectral Images:** DOI `10.26131/IRSA678`
- **SPHEREx DR1 Spectral All-Sky Cube:** DOI `10.26131/IRSA679`

The DR1 All-Sky Cube provides all-sky coverage in 102 nominal spectral channels. The cube is a valuable visualization and spectral-inspection product, but it is constructed from Year 1 calibrated spectral images and is not itself a sequence of repeated observations with independent timestamps at every sky position.

For temporal analysis, the relevant individual calibrated spectral-image exposures (for example, Level 2b products) must be retrieved and checked for the target position, detector, observation time, and quality. The availability of such exposures is not guaranteed for every target, detector, or date.

SkyChrono performs this retrieval automatically. For each field it lists the L2b exposures that cover the position, groups them into visits by observation date (`MJD-AVG`), and reads the `IMAGE`, `ZODI`, `FLAGS` and `VARIANCE` layers, the `WCS-WAVE` table and the ePSF of each exposure. For the five challenge targets, the official exposure lists returned by IRSA SIA (with their query date) are also stored in the repository (`data/spherex_exposure_index/`), so the blink keeps working when IRSA is temporarily unavailable; the images themselves are always read from the official archive.

### 4.1 Data products must not be conflated

| Data product / input | What it can support | What it cannot establish on its own |
|---|---|---|
| DR1 All-Sky Cube | All-sky visual context and spectral-channel inspection | Motion, a light curve, or temporal variability without time-resolved observations |
| Individual calibrated spectral-image exposures (e.g. L2b) | Position- and wavelength-dependent measurements at specific observation times | A reliable motion/variability result without adequate repeated coverage and quality checks |
| External catalogues (e.g. Gaia) | Source identification, reference positions, and catalogue astrometry | A SPHEREx detection or confirmation by themselves |
| Aladin sky visualization | Spatial context and cross-identification support | Independent photometric or astrometric validation |

The application should display the product type and observation state clearly. The application shows a message explaining that, when L2b multi-epoch exposures are unavailable, SkyChrono displays a static DR1 cube image and does not claim a real blink, difference image, or light curve. This disclosure should be preserved in demonstrations and evaluation.

### 4.2 Provenance and reproducibility

For each scientific result presented to a jury or user, the team should be able to identify:

1. the archive and data release used;
2. the product identifier or filename and, where available, DOI;
3. detector and spectral channel or wavelength;
4. observation date/time for every exposure used;
5. coordinate frame and WCS information;
6. quality flags and any rejected or masked pixels;
7. processing operations applied by SkyChrono;
8. whether the displayed result is measured from individual exposures, derived from a co-add, or rendered from the static All-Sky Cube.

A reproducible result should retain these inputs and settings alongside any exported table, image, or animation.

In SkyChrono, these items are visible in the interface. The **L2b exposure log** lists, for every exposure, the epoch, observation ID (`OBS_ID`), detector, central wavelength at the target position, UTC date, ePSF flux, quality and subtracted ZODI. The **Data Quality** panel lists the official flags applied and shows the formula behind each value. The `/api/cube` response contains the provenance of every frame.

## 5. Application workflow

### 5.1 Celestial navigation

The user can enter an object name or an RA/Dec position. The central sky viewer supports navigation and zooming, while the cursor readout is intended to expose the sky coordinates corresponding to the pointed-at image location.

A coordinate readout is only as accurate as the image's WCS mapping and the coordinate transformation used by the application. The displayed coordinate frame should remain visible or discoverable.

### 5.2 Field of view and observation selection

The user can adjust the field of view (FOV), select detector arrays, and configure the number of exposures per epoch and the minimum separation between epochs. These controls define the region and data subset being inspected.

The selected FOV is an analysis/display window, not a change to the telescope's native angular resolution. Any resampling or interpolation used for display should not be confused with additional measured information. SkyChrono reprojects each exposure onto a common grid for display (for example 3.075″ per display pixel in the 6′ field) and always shows the native SPHEREx scale (6.15″) next to it; photometry and positions are measured on the native L2b pixels with the ePSF.

### 5.3 Infrared detector selection

The six detector controls allow users to focus on the relevant wavelength intervals. Combining information across detectors can provide broader spectral context, but combining measurements is scientifically valid only when the wavelength mapping, calibration, uncertainties, and data quality are handled consistently.

The interface describes the detector families as SWIR (D1–D3) and the longer-wavelength group (D4–D6). These labels are useful for navigation; the physical interpretation should always be tied to the actual wavelength values and channel metadata.

### 5.4 Temporal playback and blinking

When multiple compatible observations exist, SkyChrono can arrange them chronologically and display them as a time-lapse or blink sequence. The purpose is to make changes in source position or brightness easier to notice.

A blink is a visual screening method, not a detection proof. Before interpreting an apparent displacement, the analysis must account for:

- observation timestamps and elapsed time;
- image registration and WCS consistency;
- the same or appropriately matched wavelength/channel;
- differences in point-spread function (PSF/ePSF), pixel scale, and image quality;
- source confusion, saturation, artifacts, and contamination;
- the expected motion of the target and the astrometric reference frame.

If the application has only a static DR1 All-Sky Cube at a location, temporal playback must be disabled or clearly marked as unavailable for that dataset. SkyChrono does this: in that state it shows one labelled static image, offers no blink or difference, and retries IRSA automatically about once a minute.

### 5.5 Difference, chronological RGB, co-addition, and A/B curtain

These modes are intended to reveal different aspects of the data:

- **Difference:** compares images from different epochs. A difference image can highlight changes, but imperfect registration, PSF mismatch, background variation, and calibration differences can create residuals that resemble sources.
- **Chronological RGB:** maps epochs to red, green, and blue display components (R = last epoch, B = first epoch), so sources that do not change appear neutral and changes between epochs appear coloured. The colours are a visualization encoding, not the object's true visible appearance.
- **Co-addition:** combines compatible observations to improve effective depth or signal-to-noise. It requires suitable alignment, calibration, and treatment of uncertainties and outliers.
- **A/B curtain:** reveals two image states on opposite sides of a movable divider. It is an interactive comparison aid; it does not itself calculate a motion or variability measurement.

The viewer states the epoch, date, MJD, number of exposures, detector and wavelength range of the frame shown (for example “2025-05-05 (MJD 60800.75) · 3 exp [D6] · λ 4.86–5.003 µm”), together with the display scale and the surface-brightness range.

## 6. Measurement concepts and mathematical interpretation

### 6.1 Proper motion

Proper motion is the angular change in a source's position on the sky over time, commonly expressed in milliarcseconds per year (mas/yr) or arcseconds per year (arcsec/yr).

For two positions measured in a consistent reference frame, a simplified angular displacement is:

$$
\Delta \theta \simeq \sqrt{(\Delta \alpha \cos \delta)^2 + (\Delta \delta)^2}
$$

where the RA difference is expressed as an angle, Dec is the declination, and the $\cos\delta$ factor accounts for the convergence of RA coordinate lines toward the poles.

The corresponding approximate proper-motion magnitude is:

$$
\mu = \frac{\Delta \theta}{\Delta t}
$$

where $\Delta t$ is the elapsed time in years.

This simplified expression is suitable for explaining the concept. A production-quality astrometric measurement should use the appropriate spherical-coordinate or tangent-plane formulation, propagate uncertainties, account for coordinate epochs, and fit more than two measurements when possible. Parallax and perspective effects may also matter.

SkyChrono's measured motion follows this approach. It fits the ePSF position of the target in every exposure, averages each visit, fits a weighted linear motion across all visits (adding a 0.7″ systematic for saturated cores), and compares the result with the catalogue prediction for the same dates (Gaia DR3 or literature astrometry propagated with `SkyCoord.apply_space_motion`), reporting the difference in σ.

A proper-motion value shown by the interface must be labelled as catalogue-derived, measured from the selected images, or predicted. These are not interchangeable. SkyChrono labels them in exactly that way: “Expected motion (catalogue astrometry)”, “Motion measured by SPHEREx”, and the ✚ marker for the predicted position at each epoch.

### 6.2 Source centroiding

Centroiding estimates the centre of a source's light distribution. Sub-pixel centroiding can estimate a source position more finely than one detector pixel under suitable signal and PSF conditions.

The result is not automatically an astrometric accuracy guarantee. It depends on source brightness, background, crowding, PSF modelling, detector sampling, and calibration. SkyChrono fits the official SPHEREx ePSF of the corresponding detector zone to each exposure by weighted least squares, which gives a sub-pixel position and its uncertainty; for saturated stars it uses the centroid of the saturated (`OVERFLOW`) core instead. Against Gaia DR3 and literature astrometry, Epsilon Indi Ba/Bb is recovered at a median 0.0″ from its predicted position and WISE 0855−0714 at a median 1.1″ (Section 9.1).

### 6.3 Flux and microjanskys

Flux density describes the amount of energy received per unit area, per unit time, per unit frequency or wavelength interval. The jansky (Jy) is a unit of spectral flux density:

$$
1\ \mathrm{Jy} = 10^{-26}\ \mathrm{W\,m^{-2}\,Hz^{-1}}
$$

A microjansky is:

$$
1\ \mu\mathrm{Jy} = 10^{-6}\ \mathrm{Jy}
$$

Flux values must be interpreted with the relevant calibration, aperture or PSF measurement method, background treatment, and uncertainty. A plotted flux value should not be treated as a calibrated source measurement unless the data path and photometric method support that interpretation.

SkyChrono's point-source fluxes come from forced ePSF photometry on the calibrated L2b images (surface brightness in MJy/sr converted with the pixel solid angle), weighted by the official `VARIANCE` layer, with neighbouring Gaia sources fitted simultaneously and a 3 % systematic added in quadrature.

### 6.4 Signal-to-noise ratio (SNR)

The signal-to-noise ratio compares the measured signal with the uncertainty or noise associated with that measurement. A simplified expression is:

$$
\mathrm{SNR} = \frac{F}{\sigma_F}
$$

where $F$ is the measured flux and $\sigma_F$ is its uncertainty.

The exact uncertainty model may include source Poisson noise, background noise, detector noise, calibration uncertainty, and correlated noise. The interface's displayed SNR should be traceable to the implemented estimator and the uncertainty fields or assumptions used. In SkyChrono, $\sigma_F$ comes from the weighted least-squares fit with the official `VARIANCE` layer plus the 3 % systematic; measurements below S/N = 3 are reported as 3σ upper limits, not as detections.

### 6.5 Apparent and absolute magnitude

Apparent magnitude describes how bright an object appears to an observer. Absolute magnitude is the magnitude the object would have at a standard distance of 10 parsecs, under the applicable magnitude convention and bandpass.

For a source with negligible extinction, the distance modulus is:

$$
m - M = 5\log_{10}(d) - 5
$$

where $d$ is in parsecs. If extinction is relevant, it must be included. Infrared magnitudes also require a defined photometric system and bandpass; they should not be inferred from an arbitrary image pixel value.

SkyChrono reports the AB apparent magnitude, $m_{\mathrm{AB}} = 23.9 - 2.5\log_{10}(F_{\mu\mathrm{Jy}})$, only for valid detections. It does not compute absolute magnitudes, and it shows a distance only when the Gaia parallax has $\varpi/\sigma_\varpi \ge 5$ or a published distance exists.

### 6.6 Zodiacal light and ZODI

Zodiacal light is diffuse sunlight scattered by interplanetary dust. In infrared observations it contributes foreground emission that can affect the measured sky background.

Two cases must be distinguished. Each L2b exposure includes a zodiacal-light model in its `ZODI` layer that is **not** subtracted from `IMAGE`; SkyChrono subtracts it pixel by pixel ($I_{\mathrm{clean}} = \mathrm{IMAGE} - \mathrm{ZODI}$), and the Data Quality panel and the exposure log report the subtracted value. The DR1 All-Sky Cube is already ZODI-subtracted by the pipeline, so SkyChrono does not subtract anything further from it.

The unit **MJy/sr** means megajanskys per steradian. It is a surface-brightness unit: flux density per unit solid angle. It is not interchangeable with the point-source flux-density unit µJy.

### 6.7 Epochs and observation dates

An epoch is a defined observation time or observing period. In this application, E1, E2, and E3 are labels for selected observation groups. The actual dates and time separation must be read from the underlying exposure metadata.

The cadence of SPHEREx coverage should not be simplified to “one observation every six months” for every sky position. Coverage and revisit times depend on the survey strategy, sky location, detector, and data release. The application should use actual timestamps rather than assume a fixed cadence. SkyChrono uses the `MJD-AVG` header of every exposure and groups exposures into visits with the user-selected minimum gap between visits.

## 7. Spectral inspection and composition claims

SkyChrono provides a target-spectrum panel and describes the use of spectral emission/absorption features to investigate possible chemical composition.

A spectrum can show wavelength-dependent flux and may contain absorption or emission features associated with molecules, atoms, dust, or thermal processes. However, a feature is not a definitive chemical identification by itself.

A defensible interpretation should document:

- the spectral channel and wavelength calibration;
- flux units and uncertainty;
- signal-to-noise and detection threshold;
- whether a channel is missing, saturated, masked, or otherwise unreliable;
- spectral resolution and instrumental response;
- comparison templates or physical models;
- possible blending, background, and temperature effects.

The application should therefore present chemical composition as a **candidate interpretation** or spectral diagnostic unless a validated fitting procedure and appropriate uncertainties support a stronger statement. “Feature near a known molecular band” is more defensible than “molecule confirmed” when only a visual inspection is available.

SkyChrono follows this rule. On the DR1 spectrum it reports an apparent band depth τ for H₂O 3.0, CH₄ 3.3, CO₂ 4.27 and CO 4.67 µm, measured against a power-law continuum, with its error and significance. A band is marked “not measurable” when the sampling or data quality do not allow an estimate, and it is interpreted as gas or ice according to the type of object; for example, a brown-dwarf band is never labelled as ice.

## 8. Data quality, contamination, and rejected pixels

The application includes a data-quality area referring to official pipeline flags, contamination information, and rejected pixels. These indicators are important because an apparent source or brightness change can be caused by an instrumental or processing artifact.

For every displayed flag, the interface should make clear whether it is:

1. an official flag read directly from the source product;
2. a mask or quality rule applied by SkyChrono; or
3. a derived diagnostic calculated by the application.

In SkyChrono, rejected pixels use the official list of `FLAGS` bits that the pipeline rejects when building the DR1 cube (Table 16 of the SPHEREx Explanatory Supplement); `SOURCE` (bit 21), `OVERFLOW` and `OUTLIER` are kept, and saturation is handled separately with the official `OVERFLOW`, `NONLINEAR` and `BLOOM` bits. Artefacts are counted from `STREAK`, `SATELLITE_HALO`, `BLOOM` and `SNOWBALL`. Each card of the Data Quality panel is tagged by origin (for example OFFICIAL, SUBTRACTED, MASKED or INFO), and the panel shows the formula and the measured value behind each number.

The same distinction applies to contamination maps and “clean epoch” labels. A displayed value such as ZODI = 0.000 MJy/sr should be described according to its provenance and precision; it should not automatically be interpreted as proof that the field contains no foreground contribution.

## 9. Candidate targets and validation plan

The project identifies five required astronomical validation targets. They provide different scientific test cases: high proper motion, brown-dwarf infrared emission, a brown-dwarf pair, and variable stars.

| Validation target | Scientific role in the test plan | What should be demonstrated |
|---|---|---|
| Barnard's Star | High-proper-motion stellar benchmark | Correct target identification, coordinate handling, and recovery/visualization of its known displacement when suitable time-separated data are available |
| Epsilon Indi B | Brown-dwarf system | Correct identification and infrared/spectral inspection; distinguish the brown-dwarf components and their system context using appropriate reference data |
| WISE 0855−0714 | Very cool, high-interest brown-dwarf target; supplied challenge coordinates: RA 08h55m10.831s, Dec −07°14′42.53″ | Target-centred navigation, infrared channel inspection, and a transparent statement of whether usable repeated exposures exist |
| RW Aurigae | Young stellar system with variability interest | Compare valid observations and investigate brightness changes without confusing wavelength or calibration differences with intrinsic variability |
| R Draconis | Variable-star test case | Demonstrate time-aware photometric inspection where adequate observations exist and distinguish a real light curve from static imagery |

### 9.1 Results obtained with real SPHEREx data

The following results come from the validation run of SkyChrono on real L2b exposures. Values can change slightly as new exposures are released, and the run can be repeated with `python tools/validate_targets.py`.

| Target | Reference astrometry | Result |
|---|---|---|
| Barnard's Star | Gaia DR3: μ = (−801.6, +10362.4) mas/yr | Saturated in 28 of 28 L2b exposures, so its flux is not measured. Its position is: the saturated-core centroid lies 1.2″ (0.19 px) from the prediction, and SPHEREx measures a shift of 6.59 ± 1.00″ (PA 355°) between 2025-08-25 and 2026-03-30, against 6.19″ (PA 356°) predicted (0.4σ). |
| Epsilon Indi Ba/Bb | Gaia DR3: μ = (+3982.0, −2466.8) mas/yr | Detected in 32 of 32 L2b exposures (S/N ≈ 32) at a median 0.0″ from the prediction. Measured motion 6.88 ± 0.25″ (PA 122°) in 519 days against 6.65″ (PA 122°) predicted (1.0σ); the difference image flags it as confirmed motion. The two components (separated by about 0.7″) are not resolved: SPHEREx measures the blended system. DR1 band depths: τ(CH₄ 3.3 µm) = 1.51 ± 0.05 and τ(H₂O 3.0 µm) = 0.52 ± 0.05 (gas absorption). |
| WISE 0855−0714 | Kirkpatrick et al. 2021: μ = (−8123.7, +673.2) mas/yr, ϖ = 439.0 mas | The challenge coordinates are from the AllWISE epoch (2010.6); in 2026 the object is about 2.1′ away from them, and SkyChrono propagates its position to each exposure. Detected in 9 of 19 L2b exposures at 4.4–5.0 µm over 3 visits (S/N ≈ 4; best 1.0 ± 0.2 mJy at 4.74 µm), at a median 1.1″ from the prediction. The star Gaia DR3 5756956644387831296 (G = 16.3), 8″ away, is separated by the ePSF in L2b but dominates the DR1 aperture below 3.5 µm. |
| RW Aurigae A | Gaia DR3 (2016.0) | Saturated in 24 of 24 L2b exposures. Measured motion 0.56 ± 1.23″ in one year, consistent with zero as expected. A false 9.5″ “motion” on its blooming is flagged as a saturated-star artefact. |
| R Draconis | Gaia DR3 (2016.0) | Saturated in 64 of 64 L2b exposures (8 visits, near the north ecliptic pole), so no light curve is claimed. Measured motion 1.82 ± 0.83″ in 503 days (2.2σ, not significant); its blooming artefacts are flagged as such. |

Saturation is reported as a result in its own right: for the bright targets the application states that the flux cannot be measured instead of producing a light curve.

### 9.2 What constitutes a successful validation

A successful software demonstration is not simply that the target name appears on the map. For each target, the team should show:

- the reference coordinates and catalogue/source used for identification;
- the SPHEREx product(s) retrieved and their data-release provenance;
- detector and wavelength selection;
- exposure timestamps and time baseline, if temporal analysis is claimed;
- quality screening and any missing or rejected observations;
- the measurement or visualization produced;
- comparison with an independent reference value or catalogue where applicable;
- uncertainty and a clear statement of what the test does and does not establish.

For Barnard's Star and WISE 0855−0714, a motion demonstration should report the measured positions, time interval, fitted displacement, and uncertainty. For RW Aurigae and R Draconis, a variability demonstration should use calibrated fluxes at comparable wavelengths and include uncertainties. For Epsilon Indi B, the analysis should state whether the data resolve the components or only show the blended system.

### 9.3 Static-data fallback

If the required L2b exposures are not available for a particular target, the validation should be reported as a **data-availability and navigation test**, not as a successful motion or variability measurement. SkyChrono explicitly reports static DR1 data and the absence of multi-epoch L2b exposures whenever that happens. This is the correct scientific distinction to retain. All five challenge targets do have multi-epoch L2b coverage (3 to 8 visits each), so the results in Section 9.1 do not rely on this fallback.

## 10. Technical architecture and implementation

The application was developed using:

- **HTML, CSS, and JavaScript** for the web interface and interactive visualization;
- **Python** (aiohttp, NumPy, SciPy, Astropy, reproject, s3fs) for the backend and the scientific processing;
- **Astropy** for astronomical coordinate and data-handling support;
- **Aladin Lite v3** for the interactive sky view and astronomical context;
- **NASA/IPAC IRSA** and challenge-provided data for SPHEREx data access;
- **Claude (Opus)** and **AntiGravity (Argon)** as AI-assisted development tools;
- **Gemini and OpenAI APIs** for the application's conversational assistant.

The team reports using AI tools for debugging, programming and astrophysical guidance, and UI/UX design support. These tools should be described as development assistance, not as the source of scientific measurements. Scientific outputs must be reproducible from the underlying data and documented algorithms independently of the language model.

### 10.1 Architecture description for the jury

A useful way to explain the application is as four cooperating layers:

1. **Data access layer:** locates and retrieves SPHEREx/IRSA products and supporting catalogue information.
2. **Scientific processing layer:** handles coordinate transformations, image preparation, source measurements, quality information, and any temporal or spectral calculations actually implemented.
3. **Visualization layer:** renders the sky view, detector/channel selections, blink playback, difference views, RGB mapping, co-addition, A/B curtain, and spectrum panel.
4. **Interaction and assistance layer:** provides target search, saved reference targets, export functions, documentation, and the AI assistant.

In the repository these layers map to the following code:

1. **Data access:** `spherex_engine.py` (IRSA TAP/SIA discovery, AWS S3 HTTP-range reads with IRSA IBE fallback, Gaia DR3/AllWISE/SIMBAD clients) with an on-disk cache.
2. **Scientific processing:** `spherex_engine.py` (reprojection, ZODI subtraction, official FLAGS, forced ePSF photometry, astrometry, candidate verification, DR1 spectrum and band depths, MPC report in satellite format with observatory code 288).
3. **Visualization:** `static/index.html`, `static/app.js` and `static/styles.css` (Canvas 2D viewer, Aladin Lite, spectrum chart).
4. **Interaction and assistance:** `app.py`, an asynchronous aiohttp REST API (`/api/cube`, `/api/point_spectrum`, `/api/dr1_spectrum`, `/api/catalogs`, `/api/gif`, `/api/ai/*`, `/api/docs`), and the copilot.

The README contains the architecture diagram and the full API table.

## 11. Responsible use of artificial intelligence

AI is used in two distinct ways:

**During development:** to assist with debugging, explain programming and astrophysical concepts, and support interface design.

**Inside the application:** to answer user questions and explain features through Gemini and OpenAI APIs.

The assistant should not be treated as an authority for astronomical detections. It can explain a result, but any numeric measurement, candidate classification, or physical interpretation must come from the application's documented data-processing methods and be checked against source data.

Recommended safeguards include:

- label AI-generated explanations as assistance rather than measured results;
- do not let the assistant invent missing exposure dates, fluxes, or catalogue matches;
- preserve links or identifiers for the underlying data products;
- distinguish measured, catalogue-derived, model-predicted, and AI-explained values;
- avoid sending sensitive credentials or unnecessary personal data to external APIs.

SkyChrono applies these safeguards. The copilot receives only the measured telemetry of the current field, with explicit rules that forbid it to invent values. Without an API key, a deterministic local engine (no generative AI) writes the same kind of summary from the measurements, and the interface labels which engine answered.

## 12. Known limitations and scientific risks to disclose

The jury should be given a clear account of the following limitations:

1. **Uneven temporal coverage:** not every sky position, detector, or target necessarily has the repeated exposures needed for a time series.
2. **Static cube versus time-resolved exposures:** a co-added all-sky cube cannot establish motion or variability.
3. **Astrometric systematics:** WCS errors, frame registration, proper-motion propagation, parallax, and centroid uncertainty can affect apparent displacement.
4. **Photometric systematics:** PSF changes, background subtraction, saturation, source blending, and calibration differences can mimic variability.
5. **Spectral interpretation:** low-resolution spectral features require uncertainty-aware comparison with models or reference spectra before chemical claims are made.
6. **Display transformations:** interpolation, contrast stretching, false-colour mapping, and image arithmetic can improve visibility but do not create new observational information.
7. **AI limitations:** generated explanations may be incomplete or incorrect and must not replace scientific validation.

A credible system communicates “insufficient data” or “not measurable” when appropriate. It does not convert missing data into a positive or negative scientific detection.

## 13. Demonstration protocol for the jury

A concise, reproducible demonstration can follow this sequence:

**Step 1 — Establish the data context.** Open the target and show its name, coordinates, selected data product, release, detector, and available observation dates.

**Step 2 — Inspect the sky region.** Show the sky map, FOV, coordinate readout, and relevant reference sources.

**Step 3 — Inspect the spectral coverage.** Select one or more detector arrays and explain the wavelength range and channel information being displayed.

**Step 4 — Check temporal availability.** Show the list of individual exposures and their timestamps. If no suitable repeated exposures exist, state that the target cannot be tested for motion or variability with that selection.

**Step 5 — Run the appropriate comparison.** Where valid data exist, demonstrate blink/time-lapse, difference, or A/B curtain. Keep wavelength and image-processing settings comparable.

**Step 6 — Explain the measurement.** Show the centroid, flux/SNR, proper-motion estimate, or spectral diagnostic only if the corresponding calculation is implemented and supported by the selected data. Explain the units and uncertainty.

**Step 7 — Show quality and provenance.** Open the quality flags, rejected-pixel information, and data identifiers. Explain which fields come from the official product and which are calculated by SkyChrono.

**Step 8 — State the conclusion carefully.** Separate what was directly measured, what was retrieved from a catalogue, what is only a candidate, and what remains unverified.

## 14. Innovation and challenge relevance

SkyChrono's principal contribution is the integration of astronomical navigation, SPHEREx data inspection, multi-epoch comparison tools, spectral context, quality information, and user-facing explanations in a single interface.

For the Planet X and SPHEREx challenge, this integration can help users explore how infrared data may contribute to the search for unusual or moving sources. The most important scientific value is not a claim that the application has discovered a new planet. It is the provision of a transparent workflow for locating data, inspecting evidence, testing candidate behaviour, and recognizing when the available observations are insufficient.

The combination of a visual workflow and explicit data-availability messaging can also make advanced astronomical concepts more accessible to students, educators, and citizen scientists.

## 15. Team and development acknowledgements

**Stars Finders — Delegación Zuliana**

- **Jesús Durán:** Team leader
- **Alejandro Montiel:** Programmer
- **José Montiel:** Programmer
- **Jeshua Durán:** Researcher

**Tools and resources reported by the team:** SPHEREx challenge data, NASA/IPAC IRSA, Aladin, Astropy, HTML, CSS, JavaScript, Python, Claude (Opus), AntiGravity (Argon), Gemini API, and OpenAI API.

## 16. Verification facts

These facts answer the questions a technical reviewer usually asks. Each one can be checked in the repository.

- **Access and version:** the source code is public at https://github.com/AleMigMR/NASA-SPACE-APPS-SPHEREX-ZULIA. The version presented is the `main` branch. The application runs locally with `python app.py` (a Dockerfile and a Render configuration are included) and is shown in the demonstration video.
- **Archive endpoints and data releases:** IRSA TAP (`spherex.artifact` joined with `spherex.plane`) and IRSA SIA (collections `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`) are queried in parallel to find exposures. Images are read from `s3://nasa-irsa-spherex/` with HTTP range requests, with IRSA IBE cutouts as fallback. An observation published in several releases is used once (priority DR1 > QR3 > QR2).
- **Official versus application processing:** the calibrated L2b `IMAGE`, the `ZODI` model, `FLAGS`, `VARIANCE`, the ePSF, the `WCS-WAVE` table and the DR1 All-Sky Cube are official pipeline products. SkyChrono performs the ZODI subtraction on L2b images, the reprojection, the Blink/Difference/RGB/Co-add/Curtain views, forced ePSF photometry, astrometry, candidate verification, DR1 spectrum extraction and band depths.
- **Algorithms and uncertainties:** described in Section 6 of this guide and in Chapter 3 of the [complete documentation](SPHEREx_SkyChrono_Documentation_EN.md), which lists every implemented formula.
- **Candidate detector:** it is a rule-based detector, not a machine-learning model. Difference-image peaks above 5σ (σ estimated with the MAD) are candidates. Each one is verified with exposure-by-exposure ePSF photometry: motion is confirmed when the first-to-last centroid shift is ≥ 3σ and ≥ 0.3 native pixels, and variability when the flux changes by ≥ 5σ in the same DR1 channel in at least two independent pairs. Saturated measurements, detector-edge measurements and those outside the filter range are not counted. The AI copilot only explains these results.
- **Wavelength mapping:** for every L2b exposure, the wavelength at the source position comes from the official `WCS-WAVE` table. The DR1 cube has 102 channels (17 per detector); channels 50–51, at the dichroic boundary, are empty in DR1 and reported as such. Brightness is compared only within the same DR1 channel.
- **ZODI:** SkyChrono subtracts the official `ZODI` model from each L2b image; the DR1 All-Sky Cube is already ZODI-subtracted and is not modified (Section 6.6).
- **Validation:** results for the five challenge targets are in Section 9.1 and can be reproduced with `python tools/validate_targets.py`.
- **Automated tests and performance:** 29 offline tests (`tests/test_science.py` and `tests/test_copilot.py`) cover HEALPix indexing, astrometric propagation, official flag bits, AB magnitudes, the MPC format, band depths, photometry, the fallback when IRSA does not respond, and the copilot key handling. A field that has never been loaded takes about 30 s, mainly archive queries. A neighbouring field loads in about 3 s while panning, because the exposure list and catalogues are reused. The interface has been tested in Chromium.
- **API-key handling:** the application works fully without any key. A key pasted in the interface is kept only in that browser tab (`sessionStorage`) and is never written to disk or to logs. The Gemini key travels in the `x-goog-api-key` header and the OpenAI key in the `Authorization` header, never in a URL. Provider error messages are shown without fragments of the key, and the server's own `.env` file is excluded from Git.

## 17. Official references

The following official resources support the mission and data-product descriptions in this guide:

1. **SPHEREx Instrument — mission instrument overview and detector characteristics**  
   https://spherex.caltech.edu/page/instrument

2. **NASA/IPAC IRSA — SPHEREx Data Release 1 overview**  
   https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html

3. **NASA/IPAC IRSA — SPHEREx Archive documentation and data releases**  
   https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-releases/

4. **NASA/IPAC IRSA — SPHEREx data products**  
   https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/

5. **NASA/IPAC IRSA — SPHEREx data access**  
   https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-access/

6. **SPHEREx DR1 Spectral Images — DOI 10.26131/IRSA678**  
   https://doi.org/10.26131/IRSA678

7. **SPHEREx DR1 Spectral All-Sky Cube — DOI 10.26131/IRSA679**  
   https://doi.org/10.26131/IRSA679

8. **SPHEREx Explanatory Supplement (pipeline, FLAGS bits, ePSF)**  
   https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf

When publishing results based on SPHEREx data, follow the acknowledgement and citation instructions provided by IRSA for the specific data products used.

---

**End of NASA Jury Guide**  
*SPHEREx SkyChrono — Stars Finders, NASA Space Apps Challenge 2026*
