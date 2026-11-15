/**
 * SPHEREx SkyChrono — Frontend Científico Interactivo (NASA Space Apps Challenge)
 * Delegación Zuliana de Astronomía
 *
 * Incluye:
 * - Visor del Universo Observable 360° (Proyección Elíptica Galáctica Aitoff Rotable 360° + Globo 3D + Aladin Lite v3 HiPS).
 * - Renderizado FITS L2b acelerado por LUTs (1024 pasos) y caché de OffscreenCanvas a 60 FPS (<1.5 ms/frame).
 * - Modos: Blink Video, Diferencia (E_n - E_1), Falso Color RGB Cronológico, Co-Adición y Cortina A/B.
 * - Detector Super-Inteligente de Anomalías IA integrado en el visor con puente directo a Gemini Copilot (Visión + Telemetría).
 * - Escudo Anti-Artefactos L2b (Charge Blooming B1, SAA, Persistencia H2RG, ZODI, Trazas LEO, Dicroico).
 * - Fotometría PSF forzada con la ePSF oficial, magnitud AB (ZP = 23.9), profundidad aparente de bandas y borrador MPC (código 288).
 * - Administrador Completo de Objetivos de Referencia + Tooltip Flotante con el cursor.
 * - Simetría visual y traducción dinámica 100% completa Español (ES) <-> Inglés (EN).
 */

const STATE = {
  lang: "es",
  docLang: "es",
  targets: [],
  landmarks: [],
  activeTarget: null,
  ra: 133.75976,
  dec: -7.24218,
  pmRa: 0.0,
  pmDec: 0.0,
  fov: 0.10,
  maxPerEpoch: 5,
  gapDays: 45,
  release: "all",
  bands: ["D6"],
  cube: null,
  decodedEpochs: [],
  catalogs: { gaia: [], allwise: [] },
  currentEpochIdx: 0,
  isPlaying: true,
  blinkSpeedMs: 650,
  blinkTimer: null,
  mode: "blink", // "allsky" | "blink" | "diff" | "rgb" | "sum" | "split"
  allskyEngine: "aitoff_canvas", // "aitoff_canvas" | "globe_3d" | "aladin_hips"
  allskyFrame: "galactic", // "galactic" | "equatorial" | "ecliptic"
  allskySurvey: "rgb_dr1", // "rgb_dr1" | "ch62" | "ch59" | "ch80" | "ch92" | "ch8" | "ch25" | "ch42" | "P/allWISE/color" | "P/2MASS/color"
  allskyRotLon: 0.0, // Rotación isótropa 360° en longitud (-180..360)
  allskyRotLat: 0.0, // Orientación isótropa 360° en latitud (-90..+90)
  allskyRoll: 0.0, // Ángulo de posición de cámara (0°..360°)
  aladinInstance: null,
  aladinLoadedSurvey: "",
  // Mapas equirectangulares oficiales NASA/IPAC IRSA SPHEREx DR1 (1440×720 RGBA, ivo://IPAC/P/SPHEREx/DR1/cube)
  officialAllskyMaps: {},
  officialAllskyLoading: {},
  cachedAllskyProjCanvas: null,
  cachedAllskyProjKey: "",
  cmap: "inferno",
  stretch: "zscale",
  contrast: 1.0,
  smoothImage: true,
  splitPct: 50,
  aperturePx: null,
  pointSpectrum: null,
  pointForcedPsf: null,
  activeCandidateRank: null,
  aiDetectorEnabled: true,
  starRecognizerEnabled: true,
  showBlackbodyModel: true,
  dr1Spectrum: null,
  dr1SpectrumKey: "",
  astrometry: null,
  pointLightCurve: null,
  chatHistory: [],
  // Navegación libre tipo IRSA (Pan & Zoom continuo con el mouse + auto-streaming)
  viewZoom: 1.0,
  viewPanX: 0.0,
  viewPanY: 0.0,
  isDragging: false,
  dragMoved: false,
  dragStartX: 0,
  dragStartY: 0,
  dragOriginPanX: 0,
  dragOriginPanY: 0,
  dragOriginLon: 0,
  dragOriginLat: 0,
  zoomDebounceTimer: null,
  panFetchInProgress: false,
  hoverTargetId: null,
  // Caché de renderizado de alta velocidad (60 FPS)
  cachedOffCanvas: null,
  cachedFrameKey: "",
  cubeStamp: 0,
};

// Diccionario exhaustivo de internacionalización (100% paridad ES / EN)
const I18N = {
  es: {
    i18nBadgeMission: "NASA SPACE APPS · PLANET X & SPHEREx",
    i18nBadgeIrsa: "IRSA TAP/SIA + AWS S3 + ePSF",
    i18nSubtitle:
      "Explorador de cielo completo, blinking multi-época, espectroscopía LVF (0.75–5.0 µm) y verificación de candidatos con la ePSF oficial · Delegación Zuliana de Astronomía",
    i18nBtnResources: "Recursos NASA / IRSA",
    i18nBtnTour: "Guía Rápida",
    i18nBtnDocs: "Manuales y Docs",
    i18nBtnMpc: "Reporte MPC 80-Col",
    i18nBtnShare: "Compartir",
    i18nBtnGif: "Exportar GIF Blink",
    i18nPresetsTitle: "Objetivos de Referencia",
    i18nPresetsSub: "Misión SPHEREx · Clic para explorar",
    i18nBtnNewPreset: "Nuevo",
    i18nBtnManagePresets: "Administrar",
    i18nSec1: "Navegación Celeste",
    i18nLabelQuery: "Coordenadas (RA, Dec) o Nombre (SIMBAD)",
    i18nBtnGo: "Explorar",
    i18nLblRa: "RA (ICRS):",
    i18nLblDec: "Dec (ICRS):",
    i18nLblPm: "Mov. Propio:",
    i18nLabelFov: "Campo de Visión (FOV)",
    i18nLabelDepth: "Exposiciones / Época",
    i18nLabelGap: "Separación mínima entre épocas",
    i18nSec2: "Bandas Infrarrojas LVF",
    i18nBandHint: "Selecciona los detectores SPHEREx para construir el cubo temporal (SWIR: D1–D3 · MWIR: D4–D6):",
    btnBandsAll: "Todas (D1–D6)",
    btnBandsSwir: "SWIR (Estrellas)",
    btnBandsThermal: "Térmico (Enanas Y/T)",
    "mol-D1": "Continuo estelar · He I 1.083 µm atmosférico",
    "mol-D2": "H₂O 1.4 µm · CH₄ 1.6 µm (gas)",
    "mol-D3": "H₂O 1.9 · CH₄ 2.2 · CO 2.3 µm",
    "mol-D4": "H₂O 3.0 (hielo o gas) · CH₄ 3.3 · PAH",
    "mol-D5": "Ventana de 4 µm · CO₂ 4.27 µm",
    "mol-D6": "CO 4.67 µm · pico de enanas Y",
    i18nBtnRebuild: "Reconstruir Cubo SPHEREx",
    i18nSec3: "Capas, Catálogos y FLAGS",
    i18nChkCandidates: "🎯 Candidatos en movimiento / variables",
    i18nChkGaia: "✦ Estrellas Gaia DR3 + Vectores Mov. Propio",
    i18nChkGrid: "🧭 Grilla WCS y Brújula Astronómica (N/E)",
    i18nChkFlags: "⚠️ Mapa de Bits de Contaminación (FLAGS)",
    i18nLabelCmap: "Paleta Científica",
    optCmapInferno: "Inferno (Térmico)",
    optCmapViridis: "Viridis (Perceptual)",
    optCmapCyan: "Cyan-Hot (Profundo)",
    optCmapGray: "Gris Invertido (FITS)",
    i18nLabelStretch: "Estiramiento (Stretch)",
    optStrZ: "ZScale + Asinh (IRSA HDR)",
    optStrAsinh: "Asinh (Rango Dinámico)",
    optStrSqrt: "Raíz Cuadrada (Suave)",
    optStrLin: "Lineal (P1–P99.5)",
    optStrLog: "Logarítmico (Halo)",
    i18nLabelContrast: "Contraste Cielo",
    i18nLabelSmooth: "Interpolación Bicúbica Suave",
    i18nFlagsTitle: "Diagnóstico de Calidad y Luz Zodiacal",
    i18nModeAllsky: "Universo 360°",
    i18nModeBlink: "Blink Video",
    i18nModeDiff: "Diferencia",
    i18nModeRgb: "Falso Color RGB",
    i18nModeSum: "Co-Adición",
    i18nModeSplit: "Cortina A/B",
    i18nAllskyBadge: "🌌 CUBO ALL-SKY OFICIAL SPHEREx DR1 (DOI: 10.26131/IRSA679)",
    i18nAllskyEngineLbl: "Vista:",
    optEngineAitoff: "Proyección 360° Aitoff (FITS DR1 Oficial)",
    optEngineGlobe: "Esfera 3D Isótropa (Rotación Libre SO(3))",
    optEngineAladin: "Mosaico Progresivo HiPS (Aladin Lite v3)",
    i18nAllskyFrameLbl: "Plano:",
    optFrameGal: "Galáctico (l, b · Vía Láctea)",
    optFrameEq: "Ecuatorial ICRS (RA, Dec)",
    optFrameEc: "Eclíptico (λ, β · Campos Profundos SPHEREx)",
    i18nAllskySurveyLbl: "Canal DR1:",
    optAllskyDr1Rgb: "SPHEREx DR1 Tricolor Oficial (0.91 + 3.29 PAH + 4.67 µm)",
    optAllskyCh62: "SPHEREx DR1 · 3.29 µm PAH Galáctico (Ch 62)",
    optAllskyCh59: "SPHEREx DR1 · 3.03 µm Hielo H₂O (Ch 59)",
    optAllskyCh80: "SPHEREx DR1 · 4.26 µm Hielo CO₂ (Ch 80)",
    optAllskyCh92: "SPHEREx DR1 · 4.67 µm CO / Enanas Y (Ch 92)",
    optAllskyCh8: "SPHEREx DR1 · 0.91 µm Continuo D1 (Ch 8)",
    optAllskyCh25: "SPHEREx DR1 · 1.35 µm Cercano IR D2 (Ch 25)",
    optAllskyCh42: "SPHEREx DR1 · 2.00 µm Banda K D3 (Ch 42)",
    optAllskyWise: "IRSA AllWISE Infrarrojo (3.4–22 µm HiPS)",
    optAllsky2mass: "IRSA 2MASS Cercano IR (JHK HiPS)",
    i18nBtnGalCenter: "Centro Galáctico",
    i18nBtnNep: "Campo NEP",
    i18nBtnSep: "Campo SEP",
    i18nAllskyReset: "Vista Isótropa 360°",
    i18nAllskyExtract: "Extraer Cubo FITS DR1 Aquí",
    i18nBtnRecenter: "Re-centrar Aquí",
    i18nNavHint: "Arrastra para navegar continuo / rotar 360° · Rueda para zoom dinámico · Clic para espectro · Doble clic para centrar",
    i18nAiHudTitle: "Detector de candidatos (verificación ePSF)",
    i18nSplitLabel: "Cortina Comparadora (Izquierda = Época 1 · Derecha = Época Actual):",
    i18nCursorPrompt:
      "Pasa el cursor sobre la imagen para leer coordenadas y brillo superficial (MJy/sr)",
    i18nSpeed: "Cadencia",
    i18nMathShieldSummary:
      "🛡️ Calidad de datos (FLAGS oficiales), fotometría ePSF y ecuaciones en vivo",
    i18nShieldSubTitle:
      "Calculado con las banderas oficiales del pipeline SPHEREx (Suplemento Explicativo v2.1, Tabla 16)",
    i18nMathEqHeader: "🧮 Fórmulas aplicadas a esta calidad de datos (valor medido)",
    i18nExpSummary: "📋 Registro de exposiciones L2b: λ en la posición del objetivo, flujo ePSF y calidad",
    thEpoch: "Época",
    thObsId: "ID Observación (OBS_ID)",
    thBand: "Banda",
    thDate: "Fecha UTC",
    thWave: "λ Central (µm)",
    thZodi: "Zodi (MJy/sr)",
    thFlags: "Píx. rechazados",
    thSource: "Origen",
    i18nSec4: "Espectro del objetivo (fotometría ePSF por exposición)",
    i18nChkBlackbody: "Superponer espectro DR1 (102 canales)",
    spectrumSubtitle:
      "Flujo (µJy) vs. longitud de onda. Cada punto es una exposición L2b a su λ real; la línea es la co-adición DR1. Huecos = saturado o sin detección.",
    i18nMolBands: "Profundidad aparente de banda (espectro DR1):",
    i18nSec5: "Candidatos y fuentes del campo",
    i18nLcSub: "Clic en un candidato o en una fuente para medir su espectro ePSF en todas las exposiciones:",
    i18nAiTitle: "AstroAI Copilot · Diagnóstico Científico",
    qChip1: "🚀 ¿Qué se mueve aquí?",
    qChip2: "🌈 Interpretar el espectro",
    qChip3: "📈 ¿Hay variabilidad real?",
    btnAiSend: "Enviar",
    i18nAiKeySummary: "🔑 Conectar API Key opcional (Gemini / OpenAI)",
    i18nBtnAiKeyConfirm: "Confirmar",
    i18nBtnAiKeyClear: "Quitar",
    i18nAiKeyNote: "La clave se guarda solo en esta pestaña del navegador y se envía a tu servidor SkyChrono, que la pasa a Google u OpenAI en una cabecera. No se escribe en disco ni en Git.",
    i18nPresetModalBadge: "OBJETIVO PERSONALIZADO",
    addPresetModalTitle: "Agregar Nuevo Objetivo de Referencia",
    i18nBtnClosePreset: "Cerrar",
    i18nPresetNameLbl: "Nombre del Objeto / Región *",
    i18nPresetCoordLbl: "Coordenadas (RA, Dec) o Nombre SIMBAD *",
    i18nPresetSubLbl: "Subtítulo Corto (ES)",
    i18nPresetSubEnLbl: "Subtítulo Corto (EN)",
    i18nPresetBandsLbl: "Bandas Recomendadas",
    i18nPresetFovLbl: "FOV Recomendado (grados)",
    i18nPresetNoteLbl: "Descripción Científica Completa (Aparecerá al pasar el cursor)",
    i18nBtnSavePreset: "Guardar y Explorar",
    i18nManageModalBadge: "ADMINISTRADOR DE OBJETIVOS",
    managePresetsModalTitle: "Administrar Objetivos de Referencia",
    i18nManageBtnAdd: "Agregar Nuevo",
    i18nManageBtnRestore: "Restaurar Predeterminados",
    i18nBtnCloseManage: "Cerrar",
    i18nMpcModalBadge: "IAU MINOR PLANET CENTER · 80 COLUMNAS · CÓDIGO 288",
    mpcModalTitle: "Borrador astrométrico MPC (formato satélite de 2 líneas)",
    i18nBtnCloseMpc: "Cerrar",
    i18nMpcDesc:
      "Formato de 80 columnas para observaciones desde satélite: línea «S» con la posición medida y línea «s» con el vector geocéntrico de SPHEREx en km (de la cabecera FITS). Código oficial de SPHEREx: 288. Solo se genera para candidatos con movimiento confirmado por la ePSF y sin contrapartida estelar; el MPC solo acepta objetos del Sistema Solar.",
    i18nBtnDownloadMpc: "Descargar .TXT",
    i18nBtnCopyMpc: "Copiar reporte MPC",
    i18nResModalBadge: "NASA SPACE APPS CHALLENGE 2026 · PLANET X & SPHEREx",
    resourcesModalTitle: "Centro Oficial de Recursos NASA, IRSA/IPAC y Herramientas de Misión",
    i18nBtnCloseRes: "Cerrar",
    i18nResLiveTitle: "Puente Directo en Vivo a Archivos Oficiales NASA/IPAC para la Coordenada Actual",
    resTag1: "NASA DATA · NASA/IPAC IRSA",
    resTitle1: "SPHEREx Mission at IRSA",
    resDesc1: "Archivo oficial: imágenes espectrales L2b (IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE), cubo All-Sky DR1, Suplemento Explicativo y servicios TAP/SIA.",
    resTag2: "NASA DATA · TUTORIALES OFICIALES",
    resTitle2: "SPHEREx Tutorial Notebooks",
    resDesc2: "Notebooks de IRSA en Python (acceso SIA/TAP, recortes, PSF, cubo HiPS, mosaicos). SkyChrono sigue los mismos métodos: SIA con colecciones DR1/QR3 y lectura en S3.",
    resTag3: "NASA DATA · HERRAMIENTAS OFICIALES DE IRSA",
    resTitle3: "SPHEREx Data Explorer · MOST · Espectrofotometría",
    resDesc3: "Para contrastar resultados: el explorador oficial de datos, MOST (busca las imágenes de SPHEREx que cubren la órbita de un objeto del Sistema Solar, el camino para buscar objetos tipo Planeta X) y la herramienta oficial de fotometría forzada.",
    resTag4: "NASA DATA · MODELO DE HERRAMIENTA",
    resTitle4: "WiseView",
    resDesc4: "Visor de parpadeo (blink) de datos de WISE usado por el público para cientos de descubrimientos de movimiento propio. Inspiración del modo Blink de SkyChrono.",
    resTag5: "NASA DATA · GAIA DR3 EN MAST",
    resTitle5: "Gaia Mission Data (Data Release 3)",
    resDesc5: "SkyChrono consulta Gaia DR3 en MAST para identificar fuentes, propagar posiciones y dar distancias solo cuando la paralaje es fiable (π/σ ≥ 5).",
    resTag6: "DOIs · DATOS UTILIZADOS",
    resTitle6: "DR1 Spectral Images · DR1 All-Sky Cube · QR3 · SPLICES",
    resDesc6: "Citas de los productos usados: imágenes DR1, cubo All-Sky DR1, imágenes QR3 y la lista de objetivos de hielos SPLICES.",
    resTag7: "IAU MINOR PLANET CENTER",
    resTitle7: "Formato de observaciones desde satélite",
    resDesc7: "Código de observatorio de SPHEREx: 288. Las observaciones espaciales requieren una segunda línea con el vector geocéntrico del satélite. El MPC solo acepta objetos del Sistema Solar.",
    resTag8: "SOCIO · AGENCIA ESPACIAL CANADIENSE (CSA)",
    resTitle8: "NEOSSat · CADC",
    resDesc8: "NEOSSat, primer telescopio espacial dedicado a asteroides, cometas y basura espacial, y el Canadian Astronomy Data Centre con su tutorial y conjunto de datos.",
    resTag9: "RETO OFICIAL · NASA SPACE APPS 2026",
    resTitle9: "Planet X and SPHEREx",
    resDesc9: "Página del reto con la lista oficial de recursos. NASA no respalda entidades ajenas al Gobierno de EE. UU.; respeta las condiciones de uso de cada sitio.",
    linkIrsaSpherexLive: "🔭 Abrir Misión SPHEREx en IRSA",
    linkIrsaViewerLive: "🌌 Abrir Coordenada en IRSA Viewer (Firefly)",
    linkSimbadLive: "✦ Consultar Campo en SIMBAD (CDS)",
    linkVizierLive: "◈ Catálogos Gaia DR3 / AllWISE en VizieR",
    i18nDocsBadge: "DOCUMENTACIÓN OFICIAL",
    docsModalTitle: "Centro de Documentación SPHEREx SkyChrono",
    i18nBtnRawMd: "Abrir Markdown",
    i18nBtnCloseDocs: "Cerrar",
    thFlux: "Flujo (µJy)",
    thQual: "Calidad",
    i18nTrackLegend: "✚ Posición predicha por la astrometría de catálogo",
  },
  en: {
    i18nBadgeMission: "NASA SPACE APPS · PLANET X & SPHEREx",
    i18nBadgeIrsa: "IRSA TAP/SIA + AWS S3 + ePSF",
    i18nSubtitle:
      "All-sky explorer, multi-epoch blinking, LVF spectroscopy (0.75–5.0 µm) and candidate verification with the official ePSF · Zulian Astronomy Delegation",
    i18nBtnResources: "NASA / IRSA Resources",
    i18nBtnTour: "Quick Tour",
    i18nBtnDocs: "Manuals & Docs",
    i18nBtnMpc: "80-Col MPC Report",
    i18nBtnShare: "Share Link",
    i18nBtnGif: "Export Blink GIF",
    i18nPresetsTitle: "Reference Targets",
    i18nPresetsSub: "SPHEREx Mission · Click to explore",
    i18nBtnNewPreset: "New",
    i18nBtnManagePresets: "Manage",
    i18nSec1: "Celestial Navigation",
    i18nLabelQuery: "Coordinates (RA, Dec) or Object Name (SIMBAD)",
    i18nBtnGo: "Explore",
    i18nLblRa: "RA (ICRS):",
    i18nLblDec: "Dec (ICRS):",
    i18nLblPm: "Proper Motion:",
    i18nLabelFov: "Field of View (FOV)",
    i18nLabelDepth: "Exposures / Epoch",
    i18nLabelGap: "Minimum gap between epochs",
    i18nSec2: "LVF Infrared Bands",
    i18nBandHint: "Select SPHEREx detector arrays to build the temporal cube (SWIR: D1–D3 · MWIR: D4–D6):",
    btnBandsAll: "All (D1–D6)",
    btnBandsSwir: "SWIR (Stars)",
    btnBandsThermal: "Thermal (Y/T Dwarfs)",
    "mol-D1": "Stellar continuum · atmospheric He I 1.083 µm",
    "mol-D2": "H₂O 1.4 µm · CH₄ 1.6 µm (gas)",
    "mol-D3": "H₂O 1.9 · CH₄ 2.2 · CO 2.3 µm",
    "mol-D4": "H₂O 3.0 (ice or gas) · CH₄ 3.3 · PAH",
    "mol-D5": "4 µm window · CO₂ 4.27 µm",
    "mol-D6": "CO 4.67 µm · Y-dwarf peak",
    i18nBtnRebuild: "Rebuild SPHEREx Cube",
    i18nSec3: "Layers, Catalogs & FLAGS",
    i18nChkCandidates: "🎯 Moving / variable candidates",
    i18nChkGaia: "✦ Gaia DR3 Stars + Proper Motion Vectors",
    i18nChkGrid: "🧭 WCS Grid & Astronomical Compass (N/E)",
    i18nChkFlags: "⚠️ Contamination Bitmask Overlay (FLAGS)",
    i18nLabelCmap: "Scientific Colormap",
    optCmapInferno: "Inferno (Thermal)",
    optCmapViridis: "Viridis (Perceptual)",
    optCmapCyan: "Cyan-Hot (Deep IR)",
    optCmapGray: "Inverted Gray (FITS)",
    i18nLabelStretch: "Histogram Stretch",
    optStrZ: "ZScale + Asinh (IRSA HDR)",
    optStrAsinh: "Asinh (High Dynamic)",
    optStrSqrt: "Square Root (Soft)",
    optStrLin: "Linear (P1–P99.5)",
    optStrLog: "Logarithmic (Halo)",
    i18nLabelContrast: "Sky Contrast",
    i18nLabelSmooth: "Smooth Bicubic Interpolation",
    i18nFlagsTitle: "Data Quality & Zodiacal Light",
    i18nModeAllsky: "360° Universe",
    i18nModeBlink: "Blink Video",
    i18nModeDiff: "Difference",
    i18nModeRgb: "Chrono RGB",
    i18nModeSum: "Co-Add Stack",
    i18nModeSplit: "A/B Curtain",
    i18nAllskyBadge: "🌌 OFFICIAL SPHEREx DR1 ALL-SKY CUBE (DOI: 10.26131/IRSA679)",
    i18nAllskyEngineLbl: "View:",
    optEngineAitoff: "360° Aitoff Projection (Official DR1 FITS)",
    optEngineGlobe: "3D Isotropic Sphere (Free SO(3) Rotation)",
    optEngineAladin: "Progressive HiPS Mosaic (Aladin Lite v3)",
    i18nAllskyFrameLbl: "Plane:",
    optFrameGal: "Galactic (l, b · Milky Way)",
    optFrameEq: "Equatorial ICRS (RA, Dec)",
    optFrameEc: "Ecliptic (λ, β · SPHEREx Deep Fields)",
    i18nAllskySurveyLbl: "DR1 Channel:",
    optAllskyDr1Rgb: "Official SPHEREx DR1 Tricolor (0.91 + 3.29 PAH + 4.67 µm)",
    optAllskyCh62: "SPHEREx DR1 · 3.29 µm Galactic PAH (Ch 62)",
    optAllskyCh59: "SPHEREx DR1 · 3.03 µm H₂O Ice (Ch 59)",
    optAllskyCh80: "SPHEREx DR1 · 4.26 µm CO₂ Ice (Ch 80)",
    optAllskyCh92: "SPHEREx DR1 · 4.67 µm CO / Y Dwarfs (Ch 92)",
    optAllskyCh8: "SPHEREx DR1 · 0.91 µm D1 Continuum (Ch 8)",
    optAllskyCh25: "SPHEREx DR1 · 1.35 µm Near-IR D2 (Ch 25)",
    optAllskyCh42: "SPHEREx DR1 · 2.00 µm K-Band D3 (Ch 42)",
    optAllskyWise: "IRSA AllWISE Infrared (3.4–22 µm HiPS)",
    optAllsky2mass: "IRSA 2MASS Near-IR (JHK HiPS)",
    i18nBtnGalCenter: "Galactic Center",
    i18nBtnNep: "NEP Deep Field",
    i18nBtnSep: "SEP Deep Field",
    i18nAllskyReset: "Isotropic 360° View",
    i18nAllskyExtract: "Extract DR1 FITS Cube Here",
    i18nBtnRecenter: "Recenter Here",
    i18nNavHint: "Drag for continuous sky pan / 360° rotation · Wheel for dynamic zoom · Click for spectrum · Double-click to center",
    i18nAiHudTitle: "Candidate detector (ePSF verification)",
    i18nSplitLabel: "Split Comparator (Left = Epoch 1 · Right = Active Epoch):",
    i18nCursorPrompt:
      "Hover over the image to read coordinates and surface brightness (MJy/sr)",
    i18nSpeed: "Cadence",
    i18nMathShieldSummary:
      "🛡️ Data quality (official FLAGS), ePSF photometry and live equations",
    i18nShieldSubTitle:
      "Computed from the official SPHEREx pipeline flags (Explanatory Supplement v2.1, Table 16)",
    i18nMathEqHeader: "🧮 Formulas behind this data quality (measured value)",
    i18nExpSummary: "📋 L2b exposure log: λ at the target position, ePSF flux and quality",
    thEpoch: "Epoch",
    thObsId: "Observation ID (OBS_ID)",
    thBand: "Band",
    thDate: "UTC Date",
    thWave: "Central λ (µm)",
    thZodi: "Zodi (MJy/sr)",
    thFlags: "Rejected px",
    thSource: "Source",
    i18nSec4: "Target spectrum (per-exposure ePSF photometry)",
    i18nChkBlackbody: "Overlay DR1 spectrum (102 channels)",
    spectrumSubtitle:
      "Flux (µJy) vs. wavelength. Each point is one L2b exposure at its true λ; the line is the DR1 co-add. Gaps = saturated or not detected.",
    i18nMolBands: "Apparent band depth (DR1 spectrum):",
    i18nSec5: "Candidates and field sources",
    i18nLcSub: "Click a candidate or a source to measure its ePSF spectrum in every exposure:",
    i18nAiTitle: "AstroAI Copilot · Scientific Diagnosis",
    qChip1: "🚀 What is moving here?",
    qChip2: "🌈 Interpret the spectrum",
    qChip3: "📈 Is there real variability?",
    btnAiSend: "Send",
    i18nAiKeySummary: "🔑 Connect optional API Key (Gemini / OpenAI)",
    i18nBtnAiKeyConfirm: "Confirm",
    i18nBtnAiKeyClear: "Remove",
    i18nAiKeyNote: "The key is kept only in this browser tab and is sent to your SkyChrono server, which passes it to Google or OpenAI in a header. It is never written to disk or Git.",
    i18nPresetModalBadge: "CUSTOM TARGET",
    addPresetModalTitle: "Add New Reference Target",
    i18nBtnClosePreset: "Close",
    i18nPresetNameLbl: "Object / Region Name *",
    i18nPresetCoordLbl: "Coordinates (RA, Dec) or SIMBAD Name *",
    i18nPresetSubLbl: "Short Subtitle (ES)",
    i18nPresetSubEnLbl: "Short Subtitle (EN)",
    i18nPresetBandsLbl: "Recommended Bands",
    i18nPresetFovLbl: "Recommended FOV (deg)",
    i18nPresetNoteLbl: "Full Scientific Description (Shown on cursor hover)",
    i18nBtnSavePreset: "Save & Explore",
    i18nManageModalBadge: "TARGET MANAGER",
    managePresetsModalTitle: "Manage Reference Targets",
    i18nManageBtnAdd: "Add New",
    i18nManageBtnRestore: "Restore Defaults",
    i18nBtnCloseManage: "Close",
    i18nMpcModalBadge: "IAU MINOR PLANET CENTER · 80 COLUMNS · CODE 288",
    mpcModalTitle: "MPC astrometric draft (2-line satellite format)",
    i18nBtnCloseMpc: "Close",
    i18nMpcDesc:
      "80-column format for satellite observations: an 'S' line with the measured position and an 's' line with SPHEREx's geocentric vector in km (from the FITS header). Official SPHEREx code: 288. It is only generated for candidates whose motion was confirmed with the ePSF and that have no stellar counterpart; the MPC only accepts Solar System objects.",
    i18nBtnDownloadMpc: "Download .TXT",
    i18nBtnCopyMpc: "Copy MPC report",
    i18nResModalBadge: "NASA SPACE APPS CHALLENGE 2026 · PLANET X & SPHEREx",
    resourcesModalTitle: "Official NASA, IRSA/IPAC & Mission Tools Resource Hub",
    i18nBtnCloseRes: "Close",
    i18nResLiveTitle: "Live Direct Bridge to Official NASA/IPAC Archives for Current Coordinates",
    resTag1: "NASA DATA · NASA/IPAC IRSA",
    resTitle1: "SPHEREx Mission at IRSA",
    resDesc1: "Official archive: L2b spectral images (IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE), DR1 All-Sky cube, Explanatory Supplement and TAP/SIA services.",
    resTag2: "NASA DATA · OFFICIAL TUTORIALS",
    resTitle2: "SPHEREx Tutorial Notebooks",
    resDesc2: "IRSA Python notebooks (SIA/TAP access, cutouts, PSF, HiPS cube, mosaics). SkyChrono follows the same methods: SIA with DR1/QR3 collections and reads from S3.",
    resTag3: "NASA DATA · OFFICIAL IRSA TOOLS",
    resTitle3: "SPHEREx Data Explorer · MOST · Spectrophotometry",
    resDesc3: "To cross-check results: the official data explorer, MOST (finds the SPHEREx images that cover a Solar System object's orbit, the way to search for Planet X-like objects) and the official forced-photometry tool.",
    resTag4: "NASA DATA · TOOL MODEL",
    resTitle4: "WiseView",
    resDesc4: "Blink viewer for WISE data used by the public for hundreds of proper-motion discoveries. Inspiration for SkyChrono's Blink mode.",
    resTag5: "NASA DATA · GAIA DR3 AT MAST",
    resTitle5: "Gaia Mission Data (Data Release 3)",
    resDesc5: "SkyChrono queries Gaia DR3 at MAST to identify sources, propagate positions and give distances only when the parallax is reliable (π/σ ≥ 5).",
    resTag6: "DOIs · DATA USED",
    resTitle6: "DR1 Spectral Images · DR1 All-Sky Cube · QR3 · SPLICES",
    resDesc6: "Citations of the products used: DR1 images, DR1 All-Sky cube, QR3 images and the SPLICES ice target list.",
    resTag7: "IAU MINOR PLANET CENTER",
    resTitle7: "Format for observations from satellites",
    resDesc7: "SPHEREx observatory code: 288. Space-based observations need a second line with the satellite's geocentric vector. The MPC only accepts Solar System objects.",
    resTag8: "PARTNER · CANADIAN SPACE AGENCY (CSA)",
    resTitle8: "NEOSSat · CADC",
    resDesc8: "NEOSSat, the first space telescope dedicated to asteroids, comets and space debris, and the Canadian Astronomy Data Centre with its tutorial and dataset.",
    resTag9: "OFFICIAL CHALLENGE · NASA SPACE APPS 2026",
    resTitle9: "Planet X and SPHEREx",
    resDesc9: "Challenge page with the official list of resources. NASA does not endorse non-U.S. Government entities; follow each site's terms of use.",
    linkIrsaSpherexLive: "🔭 Open SPHEREx Mission at IRSA",
    linkIrsaViewerLive: "🌌 Open Coordinate in IRSA Viewer (Firefly)",
    linkSimbadLive: "✦ Query Field in SIMBAD (CDS)",
    linkVizierLive: "◈ Gaia DR3 / AllWISE Catalogs in VizieR",
    i18nDocsBadge: "OFFICIAL DOCUMENTATION",
    docsModalTitle: "SPHEREx SkyChrono Documentation Center",
    i18nBtnRawMd: "Open Markdown",
    i18nBtnCloseDocs: "Close",
    thFlux: "Flux (µJy)",
    thQual: "Quality",
    i18nTrackLegend: "✚ Position predicted by catalogue astrometry",
  },
};

// ============================================================================
// 1. TABLAS DE BÚSQUEDA PRECALCULADAS (LUTs DE 1024 PASOS PARA 60 FPS REALES)
// ============================================================================
const LUT_SIZE = 1024;
const COLORMAP_LUTS = {};

function computeColormapRgbExact(t, cmap) {
  const x = Math.max(0, Math.min(1, t));
  if (cmap === "grayscale") {
    const v = Math.round((1.0 - x) * 255);
    return [v, v, v];
  }
  if (cmap === "viridis") {
    const r = Math.round(255 * Math.min(1, Math.max(0, 0.267 + x * (0.004 + x * (2.7 - 1.98 * x)))));
    const g = Math.round(255 * Math.min(1, Math.max(0, 0.005 + x * (1.38 - 0.48 * x))));
    const b = Math.round(255 * Math.min(1, Math.max(0, 0.329 + x * (1.42 - x * (2.62 - 1.1 * x)))));
    return [r, g, b];
  }
  if (cmap === "cyanHot") {
    const r = Math.round(255 * Math.pow(x, 1.7));
    const g = Math.round(255 * Math.pow(x, 0.85));
    const b = Math.round(255 * Math.min(1, x * 1.45 + 0.06));
    return [r, g, b];
  }
  // Default: Inferno espacial
  const r = Math.round(255 * Math.min(1, Math.max(0, Math.sin(x * Math.PI * 0.55) * 1.18)));
  const g = Math.round(255 * Math.min(1, Math.max(0, Math.pow(Math.max(0, x - 0.18) / 0.82, 1.35))));
  const b = Math.round(
    255 *
      Math.min(
        1,
        Math.max(0, 0.12 + 0.72 * Math.sin(x * Math.PI) * (1 - 0.45 * x) + Math.pow(x, 3.2) * 0.85)
      )
  );
  return [r, g, b];
}

function initLookupTables() {
  for (const cmap of ["inferno", "viridis", "cyanHot", "grayscale"]) {
    const lut = new Uint8Array(LUT_SIZE * 3);
    for (let i = 0; i < LUT_SIZE; i++) {
      const [r, g, b] = computeColormapRgbExact(i / (LUT_SIZE - 1), cmap);
      lut[i * 3] = r;
      lut[i * 3 + 1] = g;
      lut[i * 3 + 2] = b;
    }
    COLORMAP_LUTS[cmap] = lut;
  }
}
initLookupTables();

function applyStretchFast(x, stretch) {
  const c = Math.max(0, Math.min(1, x));
  if (stretch === "linear") return c;
  if (stretch === "sqrt") return Math.sqrt(c);
  if (stretch === "log") return Math.log10(1 + 99 * c) * 0.5;
  // asinh o zscale (con constante precalculada 1 / asinh(12) = 0.3145545)
  return Math.asinh(12.0 * c) * 0.3145545;
}

function invalidateFrameCache() {
  STATE.cachedFrameKey = "";
}

// ============================================================================
// 2. CONVERSIONES SEXAGESIMALES Y COORDENADAS ESFÉRICAS (WCS / GALÁCTICAS)
// ============================================================================
function formatRaSexagesimal(raDeg) {
  const raNorm = ((Number(raDeg) % 360) + 360) % 360;
  const hTot = raNorm / 15.0;
  let h = Math.floor(hTot);
  const mTot = (hTot - h) * 60.0;
  let m = Math.floor(mTot);
  let s = (mTot - m) * 60.0;
  if (s >= 59.995) {
    s = 0;
    m += 1;
  }
  if (m >= 60) {
    m = 0;
    h = (h + 1) % 24;
  }
  return `${String(h).padStart(2, "0")}h${String(m).padStart(2, "0")}m${s.toFixed(2).padStart(5, "0")}s`;
}

function formatDecSexagesimal(decDeg) {
  const sign = decDeg >= 0 ? "+" : "-";
  const dAbs = Math.abs(Number(decDeg));
  let d = Math.floor(dAbs);
  const mTot = (dAbs - d) * 60.0;
  let m = Math.floor(mTot);
  let s = (mTot - m) * 60.0;
  if (s >= 59.95) {
    s = 0;
    m += 1;
  }
  if (m >= 60) {
    m = 0;
    d += 1;
  }
  return `${sign}${String(d).padStart(2, "0")}d${String(m).padStart(2, "0")}m${s.toFixed(1).padStart(4, "0")}s`;
}

// Conversión ICRS (RA, Dec) <-> Galáctica (l, b) para la proyección Aitoff 360° estilo IRSA
const DEG2RAD = Math.PI / 180.0;
const RAD2DEG = 180.0 / Math.PI;
// Matriz de rotación ICRS -> Galáctica (J2000 estándar IAU)
const R_ICRS_TO_GAL = [
  [-0.0548755604, -0.8734370902, -0.4838350155],
  [0.4941094279, -0.44482963, 0.7469822445],
  [-0.867666149, -0.1980763734, 0.4559837762],
];

function eqToGalactic(raDeg, decDeg) {
  const a = raDeg * DEG2RAD;
  const d = decDeg * DEG2RAD;
  const x = Math.cos(d) * Math.cos(a);
  const y = Math.cos(d) * Math.sin(a);
  const z = Math.sin(d);
  const gx = R_ICRS_TO_GAL[0][0] * x + R_ICRS_TO_GAL[0][1] * y + R_ICRS_TO_GAL[0][2] * z;
  const gy = R_ICRS_TO_GAL[1][0] * x + R_ICRS_TO_GAL[1][1] * y + R_ICRS_TO_GAL[1][2] * z;
  const gz = Math.max(-1, Math.min(1, R_ICRS_TO_GAL[2][0] * x + R_ICRS_TO_GAL[2][1] * y + R_ICRS_TO_GAL[2][2] * z));
  let l = Math.atan2(gy, gx) * RAD2DEG;
  if (l < 0) l += 360.0;
  const b = Math.asin(gz) * RAD2DEG;
  return { l, b };
}

function galacticToEq(lDeg, bDeg) {
  const l = lDeg * DEG2RAD;
  const b = bDeg * DEG2RAD;
  const gx = Math.cos(b) * Math.cos(l);
  const gy = Math.cos(b) * Math.sin(l);
  const gz = Math.sin(b);
  // Transpuesta de R_ICRS_TO_GAL
  const x = R_ICRS_TO_GAL[0][0] * gx + R_ICRS_TO_GAL[1][0] * gy + R_ICRS_TO_GAL[2][0] * gz;
  const y = R_ICRS_TO_GAL[0][1] * gx + R_ICRS_TO_GAL[1][1] * gy + R_ICRS_TO_GAL[2][1] * gz;
  const z = Math.max(-1, Math.min(1, R_ICRS_TO_GAL[0][2] * gx + R_ICRS_TO_GAL[1][2] * gy + R_ICRS_TO_GAL[2][2] * gz));
  let ra = Math.atan2(y, x) * RAD2DEG;
  if (ra < 0) ra += 360.0;
  const dec = Math.asin(z) * RAD2DEG;
  return { ra, dec };
}

// Conversión Ecuatorial ICRS <-> Eclíptica (J2000 ε = 23.4392911°)
const OBLIQUITY_RAD = 23.4392911 * DEG2RAD;
const COS_EPS = Math.cos(OBLIQUITY_RAD);
const SIN_EPS = Math.sin(OBLIQUITY_RAD);

function eqToEcliptic(raDeg, decDeg) {
  const a = raDeg * DEG2RAD;
  const d = decDeg * DEG2RAD;
  const x = Math.cos(d) * Math.cos(a);
  const y = Math.cos(d) * Math.sin(a);
  const z = Math.sin(d);
  const ex = x;
  const ey = y * COS_EPS + z * SIN_EPS;
  const ez = Math.max(-1, Math.min(1, -y * SIN_EPS + z * COS_EPS));
  let lam = Math.atan2(ey, ex) * RAD2DEG;
  if (lam < 0) lam += 360.0;
  const beta = Math.asin(ez) * RAD2DEG;
  return { lon: lam, lat: beta };
}

function eclipticToEq(lamDeg, betaDeg) {
  const lam = lamDeg * DEG2RAD;
  const beta = betaDeg * DEG2RAD;
  const ex = Math.cos(beta) * Math.cos(lam);
  const ey = Math.cos(beta) * Math.sin(lam);
  const ez = Math.sin(beta);
  const x = ex;
  const y = ey * COS_EPS - ez * SIN_EPS;
  const z = Math.max(-1, Math.min(1, ey * SIN_EPS + ez * COS_EPS));
  let ra = Math.atan2(y, x) * RAD2DEG;
  if (ra < 0) ra += 360.0;
  const dec = Math.asin(z) * RAD2DEG;
  return { ra, dec };
}

function eqToActiveFrame(raDeg, decDeg) {
  if (STATE.allskyFrame === "equatorial") {
    return { lon: ((raDeg % 360) + 360) % 360, lat: decDeg };
  }
  if (STATE.allskyFrame === "ecliptic") {
    return eqToEcliptic(raDeg, decDeg);
  }
  const g = eqToGalactic(raDeg, decDeg);
  return { lon: g.l, lat: g.b };
}

function activeFrameToEq(lonDeg, latDeg) {
  if (STATE.allskyFrame === "equatorial") {
    return { ra: ((lonDeg % 360) + 360) % 360, dec: Math.max(-90, Math.min(90, latDeg)) };
  }
  if (STATE.allskyFrame === "ecliptic") {
    return eclipticToEq(lonDeg, latDeg);
  }
  return galacticToEq(lonDeg, latDeg);
}

// Rotación Esférica 3D SO(3) Completa (Yaw: rotLonDeg, Pitch: rotLatDeg -90°..+90°, Roll: rollDeg 0°/180°)
function rotateSpherical3D(lonDeg, latDeg, rotLonDeg, rotLatDeg, rollDeg = 0.0) {
  const lam1 = (lonDeg - rotLonDeg) * DEG2RAD;
  const phi1 = latDeg * DEG2RAD;
  const x1 = Math.cos(phi1) * Math.cos(lam1);
  const y1 = Math.cos(phi1) * Math.sin(lam1);
  const z1 = Math.sin(phi1);

  const beta = rotLatDeg * DEG2RAD;
  const cosB = Math.cos(beta);
  const sinB = Math.sin(beta);
  // Inclinación Pitch alrededor del eje Y para centrar cualquier latitud (-90° Polo Sur a +90° Polo Norte)
  const x2 = x1 * cosB + z1 * sinB;
  const y2 = y1;
  const z2 = -x1 * sinB + z1 * cosB;

  const gamma = (rollDeg || 0.0) * DEG2RAD;
  const cosG = Math.cos(gamma);
  const sinG = Math.sin(gamma);
  // Giro Roll alrededor del eje de visión X (permite voltear / invertir 180°)
  const x3 = x2;
  const y3 = y2 * cosG - z2 * sinG;
  const z3 = y2 * sinG + z2 * cosG;

  const dl = Math.atan2(y3, x3) * RAD2DEG;
  const bRot = Math.asin(Math.max(-1, Math.min(1, z3))) * RAD2DEG;
  return { dl, bRot, x3, y3, z3 };
}

function inverseRotateSpherical3D(dlDeg, bRotDeg, rotLonDeg, rotLatDeg, rollDeg = 0.0) {
  const dl = dlDeg * DEG2RAD;
  const bRot = bRotDeg * DEG2RAD;
  const x3 = Math.cos(bRot) * Math.cos(dl);
  const y3 = Math.cos(bRot) * Math.sin(dl);
  const z3 = Math.sin(bRot);

  const gamma = (rollDeg || 0.0) * DEG2RAD;
  const cosG = Math.cos(gamma);
  const sinG = Math.sin(gamma);
  const x2 = x3;
  const y2 = y3 * cosG + z3 * sinG;
  const z2 = -y3 * sinG + z3 * cosG;

  const beta = rotLatDeg * DEG2RAD;
  const cosB = Math.cos(beta);
  const sinB = Math.sin(beta);
  const x1 = x2 * cosB - z2 * sinB;
  const y1 = y2;
  const z1 = x2 * sinB + z2 * cosB;

  const lon = ((Math.atan2(y1, x1) * RAD2DEG + rotLonDeg) % 360.0 + 360.0) % 360.0;
  const lat = Math.asin(Math.max(-1, Math.min(1, z1))) * RAD2DEG;
  return { lon, lat };
}

// Proyección Elíptica Hammer-Aitoff 360° (Directa e Inversa con rotación SO(3) omnidireccional)
function projectHammerAitoff(lonDeg, latDeg, rotLonDeg, rotLatDeg, cx, cy, rx, ry) {
  const rot = rotateSpherical3D(lonDeg, latDeg, rotLonDeg, rotLatDeg, STATE.allskyRoll);
  const lam = -rot.dl * DEG2RAD; // Este astronómico a la izquierda como IRSA
  const phi = rot.bRot * DEG2RAD;
  const denom = Math.sqrt(1.0 + Math.cos(phi) * Math.cos(lam * 0.5));
  if (denom < 1e-6) return { x: cx, y: cy, visible: false };
  const xn = (Math.cos(phi) * Math.sin(lam * 0.5)) / denom;
  const yn = Math.sin(phi) / denom;
  return {
    x: cx + xn * rx,
    y: cy - (yn / 0.70710678) * ry,
    visible: true,
    dl: rot.dl,
    bRot: rot.bRot,
  };
}

function inverseHammerAitoff(canvasX, canvasY, rotLonDeg, rotLatDeg, cx, cy, rx, ry) {
  const isGlobe = STATE.allskyEngine === "globe_3d";
  if (isGlobe) {
    const nx = (canvasX - cx) / rx;
    const ny = (cy - canvasY) / ry;
    const r2 = nx * nx + ny * ny;
    if (r2 > 1.0) return null;
    const x3 = Math.sqrt(Math.max(0, 1.0 - r2));
    const y3 = -nx;
    const z3 = ny;
    const dlDeg = Math.atan2(y3, x3) * RAD2DEG;
    const bRotDeg = Math.asin(Math.max(-1, Math.min(1, z3))) * RAD2DEG;
    const orig = inverseRotateSpherical3D(dlDeg, bRotDeg, rotLonDeg, rotLatDeg, STATE.allskyRoll);
    const eq = activeFrameToEq(orig.lon, orig.lat);
    const gal = eqToGalactic(eq.ra, eq.dec);
    return { l: gal.l, b: gal.b, lon: orig.lon, lat: orig.lat, ra: eq.ra, dec: eq.dec };
  }

  const u = (canvasX - cx) / rx;
  const v = ((cy - canvasY) / ry) * 0.70710678;
  const rho2 = u * u * 2.0 + v * v * 2.0;
  if (rho2 > 2.0) return null;
  const z = Math.sqrt(Math.max(0, 1.0 - 0.5 * u * u - 0.5 * v * v));
  const phi = Math.asin(Math.max(-1, Math.min(1, Math.sqrt(2.0) * z * v)));
  const lam = 2.0 * Math.atan2(Math.sqrt(2.0) * z * u, 2.0 * z * z - 1.0);
  const dlDeg = -lam * RAD2DEG;
  const bRotDeg = phi * RAD2DEG;
  const orig = inverseRotateSpherical3D(dlDeg, bRotDeg, rotLonDeg, rotLatDeg, STATE.allskyRoll);
  const eq = activeFrameToEq(orig.lon, orig.lat);
  const gal = eqToGalactic(eq.ra, eq.dec);
  return { l: gal.l, b: gal.b, lon: orig.lon, lat: orig.lat, ra: eq.ra, dec: eq.dec };
}

// Geometría del lienzo: la imagen del cielo se dibuja SIEMPRE en un cuadrado (píxeles cuadrados, sin deformar
// ángulos ni distancias) centrado en el lienzo, cuyo tamaño interno coincide con su tamaño en pantalla.
function skyGeom(canvas) {
  const c = canvas || document.getElementById("skyCanvas");
  const W = c ? c.width : 760;
  const H = c ? c.height : 760;
  const S = Math.max(10, Math.min(W, H));
  return { W, H, S, ox: (W - S) / 2, oy: (H - S) / 2 };
}

// Geometría del visor 360°: Hammer-Aitoff con proporción real 2:1 y globo circular.
function allskyGeom(W, H) {
  const isGlobe = STATE.allskyEngine === "globe_3d";
  const cx = W * 0.5 + STATE.viewPanX * 0.35;
  const cy = H * 0.54 + STATE.viewPanY * 0.35;
  if (isGlobe) {
    const r = Math.min(W, H) * 0.4 * STATE.viewZoom;
    return { cx, cy, rx: r, ry: r, isGlobe };
  }
  const rx = Math.min(W * 0.45, H * 0.84) * STATE.viewZoom;
  return { cx, cy, rx, ry: rx / 2, isGlobe };
}

// Ajusta la resolución interna del lienzo a su tamaño real en pantalla (evita el estiramiento CSS).
function syncCanvasSize() {
  const canvas = document.getElementById("skyCanvas");
  if (!canvas) return false;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(200, Math.round(rect.width));
  const h = Math.max(200, Math.round(rect.height));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
    STATE.cachedAllskyProjKey = "";
    return true;
  }
  return false;
}

// Pantalla completa del visor (API Fullscreen; tecla F para alternar, Esc para salir)
function toggleViewerFullscreen() {
  const stage = document.getElementById("canvasStage");
  if (!stage) return;
  const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
  if (fsEl) {
    (document.exitFullscreen || document.webkitExitFullscreen).call(document);
  } else if (stage.requestFullscreen) {
    stage.requestFullscreen().catch(() => {});
  } else if (stage.webkitRequestFullscreen) {
    stage.webkitRequestFullscreen();
  }
}

function onFullscreenChange() {
  const stage = document.getElementById("canvasStage");
  const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
  const on = Boolean(fsEl && fsEl === stage);
  if (stage) stage.classList.toggle("is-fullscreen", on);
  const btn = document.getElementById("btnFullscreen");
  if (btn) {
    btn.textContent = on ? "🗗" : "⛶";
    btn.title = STATE.lang === "en" ? (on ? "Exit full screen (Esc)" : "Full screen (F)") : on ? "Salir de pantalla completa (Esc)" : "Pantalla completa (F)";
  }
  requestAnimationFrame(() => {
    syncCanvasSize();
    invalidateFrameCache();
    renderCanvasFrame();
  });
}

// Proyección gnomónica (TAN) inversa exacta para la grilla común (Norte arriba, Este a la izquierda)
function tanPixelToWorld(gx, gy, wcs) {
  const D2R = Math.PI / 180.0;
  const xi = (gx + 1 - wcs.crpix[0]) * wcs.cdelt[0] * D2R;
  const eta = (gy + 1 - wcs.crpix[1]) * wcs.cdelt[1] * D2R;
  const a0 = wcs.crval[0] * D2R;
  const d0 = wcs.crval[1] * D2R;
  const denom = Math.cos(d0) - eta * Math.sin(d0);
  const ra = a0 + Math.atan2(xi, denom);
  const dec = Math.atan2(Math.sin(d0) + eta * Math.cos(d0), Math.sqrt(xi * xi + denom * denom));
  return { ra: ((ra / D2R) % 360 + 360) % 360, dec: dec / D2R };
}

function fmtNum(v, digits = 2, fallback = "—") {
  return Number.isFinite(Number(v)) && v !== null ? Number(v).toFixed(digits) : fallback;
}

// ============================================================================
// 3. INICIALIZACIÓN Y GESTIÓN DE IDIOMA (100% SIMÉTRICO ES / EN)
// ============================================================================
document.addEventListener("DOMContentLoaded", async () => {
  readUrlParams();
  bindEvents();
  initAiKeyPanel();
  syncCanvasSize();
  const stageEl = document.getElementById("canvasStage");
  if (stageEl && "ResizeObserver" in window) {
    new ResizeObserver(() => {
      if (syncCanvasSize()) {
        invalidateFrameCache();
        renderCanvasFrame();
      }
    }).observe(stageEl);
  }
  document.addEventListener("fullscreenchange", onFullscreenChange);
  document.addEventListener("webkitfullscreenchange", onFullscreenChange);
  // Pre-cargar en memoria el Mapa All-Sky Oficial SPHEREx DR1 (ivo://IPAC/P/SPHEREx/DR1/cube)
  ensureOfficialAllskyMapLoaded("rgb_dr1");
  await loadMetadataTargets();
  applyLanguage(STATE.lang);
  syncViewportVisibility();
  await loadSkyPatch();
});

function readUrlParams() {
  const p = new URLSearchParams(window.location.search);
  if (p.get("embed") === "1") {
    document.body.classList.add("embed-mode");
  }
  if (p.get("lang") === "en" || p.get("lang") === "es") {
    STATE.lang = p.get("lang");
  }
  if (p.get("ra") && p.get("dec")) {
    STATE.ra = parseFloat(p.get("ra"));
    STATE.dec = parseFloat(p.get("dec"));
    STATE.pmRa = 0.0;
    STATE.pmDec = 0.0;
    const inp = document.getElementById("inputQuery");
    if (inp) inp.value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
  }
  if (p.get("fov")) {
    STATE.fov = parseFloat(p.get("fov"));
    const sf = document.getElementById("selectFov");
    if (sf) sf.value = STATE.fov.toFixed(2);
  }
  if (p.get("bands")) {
    STATE.bands = p
      .get("bands")
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    syncBandsCheckboxes(STATE.bands);
  }
  if (p.get("mode")) {
    const m = p.get("mode");
    if (["allsky", "blink", "diff", "rgb", "sum", "split"].includes(m)) {
      STATE.mode = m;
    }
  }
}

function updateAiDetectorButtonText() {
  const span = document.getElementById("i18nBtnAiDetector");
  const btn = document.getElementById("btnToggleAiDetector");
  if (span) {
    span.textContent =
      STATE.lang === "en"
        ? `Detector: ${STATE.aiDetectorEnabled ? "ON" : "OFF"}`
        : `Detector: ${STATE.aiDetectorEnabled ? "ON" : "OFF"}`;
  }
  if (btn) {
    btn.classList.toggle("active", STATE.aiDetectorEnabled);
  }
}

function updateStarRecognizerButtonText() {
  const span = document.getElementById("i18nBtnStarRecognizer");
  const btn = document.getElementById("btnToggleStarRecognizer");
  if (span) {
    span.textContent =
      STATE.lang === "en"
        ? `Sources: ${STATE.starRecognizerEnabled ? "ON" : "OFF"}`
        : `Fuentes: ${STATE.starRecognizerEnabled ? "ON" : "OFF"}`;
  }
  if (btn) {
    btn.classList.toggle("active", STATE.starRecognizerEnabled);
  }
}


function updateLiveResourceLinks() {
  const ra = Number(STATE.ra || 0);
  const dec = Number(STATE.dec || 0);
  const badge = document.getElementById("resLiveCoordBadge");
  if (badge) {
    badge.textContent = `RA ${ra.toFixed(4)}° (${formatRaSexagesimal(ra)}) · Dec ${dec >= 0 ? "+" : ""}${dec.toFixed(4)}° (${formatDecSexagesimal(dec)})`;
  }
  const irsaV = document.getElementById("linkIrsaViewerLive");
  if (irsaV) {
    irsaV.href = `https://irsa.ipac.caltech.edu/irsaviewer/?__action=layout.showDropDown&locstr=${encodeURIComponent(`${ra.toFixed(5)} ${dec.toFixed(5)}`)}`;
  }
  const simbadL = document.getElementById("linkSimbadLive");
  if (simbadL) {
    simbadL.href = `https://simbad.cds.unistra.fr/simbad/sim-coo?Coord=${encodeURIComponent(`${ra.toFixed(5)} ${dec >= 0 ? "+" : ""}${dec.toFixed(5)}`)}&Radius=10&Radius.unit=arcmin`;
  }
  const vizL = document.getElementById("linkVizierLive");
  if (vizL) {
    vizL.href = `https://vizier.cds.unistra.fr/viz-bin/VizieR-4?-c=${encodeURIComponent(`${ra.toFixed(5)}${dec >= 0 ? "+" : ""}${dec.toFixed(5)}`)}&-c.rm=10`;
  }
}

function applyLanguage(lang) {
  STATE.lang = lang;
  document.documentElement.lang = lang;
  const dict = I18N[lang] || I18N.es;
  for (const [id, text] of Object.entries(dict)) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }
  renderAiKeyStatus();
  updateAiEngineTag();

  // Traducir opciones de selects dinámicamente (los 7 niveles de FOV hasta Gran Angular 1.60°)
  const fovSel = document.getElementById("selectFov");
  if (fovSel && fovSel.options.length >= 4) {
    const fovTextsEs = [
      "3.6′ × 3.6′ (Zoom Alto)",
      "6.0′ × 6.0′ (Óptimo)",
      "7.2′ × 7.2′ (Estándar)",
      "10.8′ × 10.8′ (Amplio)",
      "21.0′ × 21.0′ (Panorámico)",
      "48.0′ × 48.0′ (0.8° Gran Campo)",
      "96.0′ × 96.0′ (1.6° Ultra-Amplio)",
    ];
    const fovTextsEn = [
      "3.6′ × 3.6′ (High Zoom)",
      "6.0′ × 6.0′ (Optimal)",
      "7.2′ × 7.2′ (Standard)",
      "10.8′ × 10.8′ (Wide)",
      "21.0′ × 21.0′ (Panoramic)",
      "48.0′ × 48.0′ (0.8° Wide Field)",
      "96.0′ × 96.0′ (1.6° Ultra-Wide)",
    ];
    for (let i = 0; i < fovSel.options.length && i < fovTextsEs.length; i++) {
      fovSel.options[i].text = lang === "en" ? fovTextsEn[i] : fovTextsEs[i];
    }
  }
  const depSel = document.getElementById("selectDepth");
  if (depSel && depSel.options.length >= 4) {
    depSel.options[0].text = lang === "en" ? "5 exp/epoch (Fast)" : "5 exp/época (Rápido)";
    depSel.options[1].text = lang === "en" ? "8 exp/epoch (Balanced)" : "8 exp/época (Balanceado)";
    depSel.options[2].text = lang === "en" ? "12 exp/epoch (Deep)" : "12 exp/época (Profundo)";
    depSel.options[3].text = lang === "en" ? "20 exp/epoch (Ultra S/N)" : "20 exp/época (Ultra S/N)";
  }
  const gapSel = document.getElementById("selectGap");
  if (gapSel && gapSel.options.length >= 4) {
    gapSel.options[0].text = lang === "en" ? "15 days (Fine Cadence)" : "15 días (Cadencia Fina)";
    gapSel.options[1].text = lang === "en" ? "30 days (Monthly)" : "30 días (Mensual)";
    gapSel.options[2].text = lang === "en" ? "45 days (Multi-Month)" : "45 días (Multi-Mes)";
    gapSel.options[3].text = lang === "en" ? "90 days (Seasonal)" : "90 días (Semestral)";
  }

  // Placeholders
  const inpQ = document.getElementById("inputQuery");
  if (inpQ) {
    inpQ.placeholder =
      lang === "en"
        ? "E.g.: 08h55m10.83s -07d14m42.5s or Barnard's Star or Polaris"
        : "Ej: 08h55m10.83s -07d14m42.5s o Barnard's Star o Polaris";
  }
  const inpAi = document.getElementById("aiChatInput");
  if (inpAi) {
    inpAi.placeholder =
      lang === "en"
        ? "Ask AstroAI about this field, moving dipoles or LVF spectrum..."
        : "Pregunta a AstroAI sobre este campo, dipolos o espectro...";
  }
  const inpKey = document.getElementById("inputApiKey");
  if (inpKey) {
    inpKey.placeholder =
      lang === "en"
        ? "Paste your GEMINI_API_KEY or OPENAI_API_KEY (optional)"
        : "Pega tu GEMINI_API_KEY o OPENAI_API_KEY (opcional)";
  }
  const mSearch = document.getElementById("managePresetsSearch");
  if (mSearch) {
    mSearch.placeholder =
      lang === "en"
        ? "Filter targets by name, category, coordinates or band..."
        : "Filtrar objetivos por nombre, categoría, coordenadas o banda...";
  }

  const langLbl = document.getElementById("langLabel");
  if (langLbl) langLbl.textContent = lang === "es" ? "EN" : "ES";
  const playLbl = document.getElementById("playLabel");
  if (playLbl) {
    playLbl.textContent = STATE.isPlaying
      ? lang === "en"
        ? "Pause"
        : "Pausar"
      : lang === "en"
      ? "Play"
      : "Reproducir";
  }

  updateAiDetectorButtonText();
  updateStarRecognizerButtonText();
  updateLiveResourceLinks();
  renderPresets();
  if (STATE.cube) {
    updateScienceBanner();
    renderAutoAiSummary();
    renderCandidatesBar();
    renderRecognizedObjectsBar();
    renderAiDetectorHud();
    renderArtifactShieldAndMath();
    renderSpectrumChart();
    renderCanvasFrame();
  }
}

// ============================================================================
// 4. SEPARACIÓN ESTRICTA DE DOM / WEBGL ENTRE ALL-SKY 360° Y #skyCanvas
// ============================================================================
function syncViewportVisibility() {
  const allskyStage = document.getElementById("allskyStage");
  const aladinBox = document.getElementById("allskyAladinDiv");
  const splitWrap = document.getElementById("splitControlWrap");
  const aiHud = document.getElementById("aiDetectorHud");
  const hudTL = document.getElementById("hudTopLeft");
  const hudTR = document.getElementById("hudTopRight");

  // Actualizar pestaña activa en la barra de modos
  document.querySelectorAll(".mode-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === STATE.mode);
  });

  if (STATE.mode === "allsky") {
    if (allskyStage) allskyStage.hidden = false;
    if (splitWrap) splitWrap.hidden = true;
    if (aiHud) aiHud.hidden = true;
    if (hudTL) hudTL.hidden = true;
    if (hudTR) hudTR.hidden = true;

    if (STATE.allskyEngine === "aladin_hips") {
      if (aladinBox) aladinBox.hidden = false;
      initOrUpdateAladinAllsky();
    } else {
      if (aladinBox) aladinBox.hidden = true;
    }
  } else {
    // Modo FITS SPHEREx (blink, diff, rgb, sum, split): ocultar 100% el overlay All-Sky
    if (allskyStage) allskyStage.hidden = true;
    if (aladinBox) aladinBox.hidden = true;
    if (splitWrap) splitWrap.hidden = STATE.mode !== "split";
    if (hudTL) hudTL.hidden = false;
    if (hudTR) hudTR.hidden = false;
    if (aiHud) aiHud.hidden = !STATE.aiDetectorEnabled;
  }
}

function resolveDr1ChannelKey(surveySpec) {
  if (!surveySpec || surveySpec === "rgb_dr1") return "rgb_dr1";
  if (surveySpec.startsWith("ch")) return surveySpec;
  if (surveySpec.includes("2MASS")) return "ch25";
  if (surveySpec.includes("allWISE")) return "ch62";
  return "rgb_dr1";
}

function ensureOfficialAllskyMapLoaded(surveySpec) {
  const key = resolveDr1ChannelKey(surveySpec);
  if (STATE.officialAllskyMaps[key]) {
    return STATE.officialAllskyMaps[key];
  }
  if (STATE.officialAllskyLoading[key]) {
    return STATE.officialAllskyMaps["rgb_dr1"] || null;
  }
  STATE.officialAllskyLoading[key] = true;
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    const c = document.createElement("canvas");
    c.width = img.width || 1440;
    c.height = img.height || 720;
    const cctx = c.getContext("2d");
    cctx.drawImage(img, 0, 0);
    const idata = cctx.getImageData(0, 0, c.width, c.height);
    STATE.officialAllskyMaps[key] = {
      width: c.width,
      height: c.height,
      data: idata.data,
      isRgb: key === "rgb_dr1",
    };
    STATE.officialAllskyLoading[key] = false;
    STATE.cachedAllskyProjKey = "";
    renderCanvasFrame();
  };
  img.onerror = () => {
    STATE.officialAllskyLoading[key] = false;
  };
  img.src = `/api/spherex-allsky-map?channel=${encodeURIComponent(key)}`;
  return STATE.officialAllskyMaps["rgb_dr1"] || null;
}

function applySurveyToAladin(aladin, surveySpec) {
  if (!aladin) return;
  if (surveySpec && surveySpec.startsWith("P/")) {
    aladin.setImageSurvey(surveySpec);
    STATE.aladinLoadedSurvey = surveySpec;
    return;
  }
  const m = (surveySpec || "").match(/(\d+)/);
  const chNum = surveySpec === "rgb_dr1" ? 62 : m ? parseInt(m[1], 10) : 62;
  const surveyId = `SPHEREx_DR1_CH${chNum}`;
  const hipsUrl = `${window.location.origin}/api/hips/spherex/${chNum}`;
  try {
    const customHips = aladin.createImageSurvey(
      surveyId,
      `NASA/IPAC SPHEREx DR1 Channel ${chNum}`,
      hipsUrl,
      "equatorial",
      5,
      { imgFormat: "png" }
    );
    aladin.setImageSurvey(customHips);
    STATE.aladinLoadedSurvey = surveySpec;
  } catch (err) {
    console.warn("Aladin custom HiPS fallback:", err);
    aladin.setImageSurvey("P/allWISE/color");
  }
}

function initOrUpdateAladinAllsky() {
  const aladinBox = document.getElementById("allskyAladinDiv");
  if (!aladinBox || aladinBox.hidden) return;
  if (typeof window.A === "undefined" || !window.A.init) {
    setTimeout(() => {
      if (STATE.mode === "allsky" && STATE.allskyEngine === "aladin_hips") {
        initOrUpdateAladinAllsky();
      }
    }, 500);
    return;
  }

  window.A.init.then(() => {
    if (!STATE.aladinInstance) {
      STATE.aladinInstance = window.A.aladin("#allskyAladinDiv", {
        survey: "P/allWISE/color",
        projection: "AIT",
        cooFrame: STATE.allskyFrame === "equatorial" ? "equatorial" : "galactic",
        fov: 360,
        target: "266.4168 -29.0078",
        showReticle: true,
        showCooGrid: true,
        showZoomControl: false,
        showFullscreenControl: false,
        showLayersControl: false,
        showGotoControl: false,
      });

      applySurveyToAladin(STATE.aladinInstance, STATE.allskySurvey);

      const cat = window.A.catalog({
        name: "SPHEREx Targets",
        sourceSize: 14,
        color: "#00f5d4",
        onClick: (src) => {
          if (src && src.data && src.data.targetObj) {
            selectTargetFromAllsky(src.data.targetObj);
          }
        },
      });
      STATE.aladinInstance.addCatalog(cat);
      [...STATE.targets.filter((t) => !t.is_allsky), ...(STATE.landmarks || [])].forEach((t) => {
        cat.addSources([
          window.A.marker(t.ra, t.dec, {
            popupTitle: t.name,
            popupDesc: t.subtitle,
            targetObj: t,
          }),
        ]);
      });
    } else {
      if (STATE.aladinLoadedSurvey !== STATE.allskySurvey) {
        applySurveyToAladin(STATE.aladinInstance, STATE.allskySurvey);
      }
    }
  });
}

function selectTargetFromAllsky(t) {
  STATE.activeTarget = t;
  STATE.ra = t.ra;
  STATE.dec = t.dec;
  STATE.pmRa = t.pm_ra || 0;
  STATE.pmDec = t.pm_dec || 0;
  STATE.fov = t.recommended_fov || 0.1;
  STATE.bands = [...(t.recommended_bands || ["D6"])];
  STATE.mode = "blink";
  document.getElementById("inputQuery").value = `${t.ra.toFixed(5)}, ${t.dec.toFixed(5)}`;
  const sf = document.getElementById("selectFov");
  if (sf) sf.value = STATE.fov.toFixed(2);
  syncBandsCheckboxes(STATE.bands);
  renderPresets();
  syncViewportVisibility();
  loadSkyPatch();
}

// ============================================================================
// 5. OBJETIVOS DE REFERENCIA, TOOLTIP FLOTANTE Y ADMINISTRADOR COMPLETO
// ============================================================================
async function loadMetadataTargets() {
  try {
    const r = await fetch("/api/targets");
    const data = await r.json();
    STATE.targets = data.targets || [];
    STATE.landmarks = data.landmarks || [];
    const defaultTgt =
      STATE.targets.find((t) => !t.is_allsky && t.id === "WISE0855") ||
      STATE.targets.find((t) => !t.is_allsky) ||
      STATE.targets[0];
    const urlP = new URLSearchParams(window.location.search);
    if (!STATE.activeTarget && defaultTgt && !urlP.get("ra")) {
      STATE.activeTarget = defaultTgt;
      const p = urlP;
      if (!p.get("ra")) {
        STATE.ra = STATE.activeTarget.ra;
        STATE.dec = STATE.activeTarget.dec;
        STATE.pmRa = STATE.activeTarget.pm_ra;
        STATE.pmDec = STATE.activeTarget.pm_dec;
        STATE.fov = STATE.activeTarget.recommended_fov;
        STATE.bands = [...STATE.activeTarget.recommended_bands];
        document.getElementById("inputQuery").value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
        syncBandsCheckboxes(STATE.bands);
      }
    }
    renderPresets();
  } catch (err) {
    console.error("Error cargando /api/targets:", err);
  }
}

function renderPresets() {
  const container = document.getElementById("presetsContainer");
  if (!container) return;
  container.innerHTML = "";
  const tooltip = document.getElementById("presetFloatingTooltip");

  STATE.targets.forEach((t) => {
    const card = document.createElement("button");
    card.type = "button";
    const isAct =
      STATE.activeTarget &&
      STATE.activeTarget.id === t.id &&
      ((t.is_allsky && STATE.mode === "allsky") || (!t.is_allsky && STATE.mode !== "allsky"));
    card.className = "preset-card" + (isAct ? " active" : "");

    const subText = STATE.lang === "en" && t.subtitle_en ? t.subtitle_en : t.subtitle;
    const badgeTxt = t.is_allsky ? "360° IRSA" : (t.recommended_bands || []).join("+");

    card.innerHTML = `
      <div class="preset-card-head">
        <span class="preset-name">${t.name}</span>
        <span class="preset-badge">${badgeTxt}</span>
      </div>
      <span class="preset-sub">${subText}</span>
    `;

    // Tooltip flotante con el cursor (position: fixed, pointer-events: none)
    card.addEventListener("mouseenter", (ev) => {
      if (!tooltip) return;
      const noteText =
        STATE.lang === "en" && t.science_note_en ? t.science_note_en : t.science_note || subText;
      const pmLbl = STATE.lang === "en" ? "Proper Motion" : "Mov. Propio";
      tooltip.innerHTML = `
        <div class="pft-header">
          <span class="pft-title">${t.name}</span>
          <span class="pft-badge">${badgeTxt} · FOV ${(t.recommended_fov * 60).toFixed(1)}′</span>
        </div>
        <div class="pft-sub">${subText}</div>
        <div class="pft-coords">RA ${t.ra.toFixed(5)}° (${formatRaSexagesimal(t.ra)}) · Dec ${t.dec.toFixed(5)}° (${formatDecSexagesimal(t.dec)})${t.display_epoch ? ` · ${STATE.lang === "en" ? "epoch" : "época"} ${t.display_epoch}` : ""} · ${pmLbl}: ${t.pm_ra || 0}, ${t.pm_dec || 0} mas/yr</div>
        <div class="pft-desc">${noteText}${(STATE.lang === "en" ? t.prompt_epoch_note_en : t.prompt_epoch_note) ? `<br><em>${STATE.lang === "en" ? t.prompt_epoch_note_en : t.prompt_epoch_note}</em>` : ""}</div>
      `;
      tooltip.hidden = false;
      positionFloatingTooltip(ev);
    });
    card.addEventListener("mousemove", (ev) => {
      positionFloatingTooltip(ev);
    });
    card.addEventListener("mouseleave", () => {
      if (tooltip) tooltip.hidden = true;
    });

    card.addEventListener("click", () => {
      if (tooltip) tooltip.hidden = true;
      STATE.activeTarget = t;
      STATE.ra = t.ra;
      STATE.dec = t.dec;
      STATE.pmRa = t.pm_ra || 0;
      STATE.pmDec = t.pm_dec || 0;
      STATE.fov = t.recommended_fov || 0.1;
      STATE.bands = [...(t.recommended_bands || ["D6"])];
      STATE.aperturePx = null;
      STATE.pointSpectrum = null;
      STATE.pointForcedPsf = null;
      STATE.activeCandidateRank = null;
      STATE.viewZoom = 1.0;
      STATE.viewPanX = 0.0;
      STATE.viewPanY = 0.0;

      if (t.is_allsky) {
        STATE.mode = "allsky";
        renderPresets();
        syncViewportVisibility();
        updateScienceBanner();
        invalidateFrameCache();
        renderCanvasFrame();
        return;
      } else if (STATE.mode === "allsky") {
        STATE.mode = "blink";
      }

      document.getElementById("inputQuery").value = `${t.ra.toFixed(5)}, ${t.dec.toFixed(5)}`;
      document.getElementById("selectFov").value = STATE.fov.toFixed(2);
      syncBandsCheckboxes(STATE.bands);
      renderPresets();
      syncViewportVisibility();
      loadSkyPatch();
    });

    container.appendChild(card);
  });
}

function positionFloatingTooltip(ev) {
  const tooltip = document.getElementById("presetFloatingTooltip");
  if (!tooltip || tooltip.hidden) return;
  const pad = 14;
  const rect = tooltip.getBoundingClientRect();
  let x = ev.clientX + 16;
  let y = ev.clientY + 18;
  if (x + rect.width + pad > window.innerWidth) {
    x = Math.max(pad, window.innerWidth - rect.width - pad);
  }
  if (y + rect.height + pad > window.innerHeight) {
    y = Math.max(pad, ev.clientY - rect.height - 12);
  }
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

function openPresetModalForTarget(t) {
  const editIdEl = document.getElementById("presetEditId");
  const titleEl = document.getElementById("addPresetModalTitle");
  const statusEl = document.getElementById("presetFormStatus");
  if (statusEl) statusEl.textContent = "";

  if (t) {
    if (editIdEl) editIdEl.value = t.id;
    if (titleEl) {
      titleEl.textContent =
        STATE.lang === "en" ? `Edit Reference Target: ${t.name}` : `Editar Objetivo: ${t.name}`;
    }
    document.getElementById("presetName").value = t.name || "";
    document.getElementById("presetCoord").value = `${t.ra}, ${t.dec}`;
    document.getElementById("presetSub").value = t.subtitle || "";
    const subEnEl = document.getElementById("presetSubEn");
    if (subEnEl) subEnEl.value = t.subtitle_en || t.subtitle || "";
    document.getElementById("presetBands").value = (t.recommended_bands || ["D1", "D2", "D3", "D4"]).join(",");
    document.getElementById("presetFov").value = Number(t.recommended_fov || 0.1).toFixed(2);
    document.getElementById("presetNote").value =
      (STATE.lang === "en" ? t.science_note_en : t.science_note) || t.science_note || "";
  } else {
    if (editIdEl) editIdEl.value = "";
    if (titleEl) {
      titleEl.textContent =
        STATE.lang === "en" ? "Add New Reference Target" : "Agregar Nuevo Objetivo de Referencia";
    }
    document.getElementById("presetName").value = "";
    document.getElementById("presetCoord").value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
    document.getElementById("presetSub").value = "";
    const subEnEl = document.getElementById("presetSubEn");
    if (subEnEl) subEnEl.value = "";
    document.getElementById("presetBands").value = STATE.bands.join(",");
    document.getElementById("presetFov").value = STATE.fov.toFixed(2);
    document.getElementById("presetNote").value = "";
  }
  document.getElementById("addPresetModal").hidden = false;
}

function renderManagePresetsList() {
  const listEl = document.getElementById("managePresetsList");
  const countEl = document.getElementById("managePresetsCount");
  const searchEl = document.getElementById("managePresetsSearch");
  if (!listEl) return;

  const q = ((searchEl && searchEl.value) || "").trim().toLowerCase();
  const filtered = STATE.targets.filter((t) => {
    if (!q) return true;
    const hay = `${t.name} ${t.subtitle || ""} ${t.subtitle_en || ""} ${t.category || ""} ${(t.recommended_bands || []).join(" ")} ${t.ra} ${t.dec}`.toLowerCase();
    return hay.includes(q);
  });

  if (countEl) {
    countEl.textContent =
      STATE.lang === "en" ? `${filtered.length} targets` : `${filtered.length} objetivos`;
  }

  listEl.innerHTML = "";
  filtered.forEach((t) => {
    const item = document.createElement("div");
    item.className = "manage-preset-item";
    const subText = STATE.lang === "en" && t.subtitle_en ? t.subtitle_en : t.subtitle;
    const typeTag = t.custom
      ? STATE.lang === "en"
        ? "CUSTOM"
        : "PERSONALIZADO"
      : STATE.lang === "en"
      ? "OFFICIAL MISSION"
      : "OFICIAL MISIÓN";
    const loadTxt = STATE.lang === "en" ? "🎯 Explore" : "🎯 Explorar";
    const editTxt = STATE.lang === "en" ? "✏️ Edit" : "✏️ Editar";
    const delTxt = STATE.lang === "en" ? "🗑️ Delete" : "🗑️ Eliminar";

    item.innerHTML = `
      <div class="manage-preset-info">
        <div class="manage-preset-title-row">
          <span class="manage-preset-name">${t.name}</span>
          <span class="preset-badge">${typeTag}</span>
          <span class="preset-badge">${(t.recommended_bands || []).join("+")}</span>
        </div>
        <div class="manage-preset-sub">${subText}</div>
        <div class="manage-preset-meta">
          RA ${t.ra.toFixed(5)}° (${formatRaSexagesimal(t.ra)}) · Dec ${t.dec.toFixed(5)}° (${formatDecSexagesimal(t.dec)}) · FOV ${(t.recommended_fov * 60).toFixed(1)}′ · PM: ${t.pm_ra || 0}, ${t.pm_dec || 0} mas/yr
        </div>
      </div>
      <div class="manage-preset-actions">
        <button type="button" class="btn btn-xs btn-primary btn-m-load">${loadTxt}</button>
        <button type="button" class="btn btn-xs btn-ghost btn-m-edit">${editTxt}</button>
        <button type="button" class="btn btn-xs btn-ghost btn-m-del">${delTxt}</button>
      </div>
    `;

    item.querySelector(".btn-m-load").addEventListener("click", () => {
      document.getElementById("managePresetsModal").hidden = true;
      selectTargetFromAllsky(t);
    });
    item.querySelector(".btn-m-edit").addEventListener("click", () => {
      document.getElementById("managePresetsModal").hidden = true;
      openPresetModalForTarget(t);
    });
    item.querySelector(".btn-m-del").addEventListener("click", async () => {
      try {
        const r = await fetch(`/api/targets?id=${encodeURIComponent(t.id)}`, { method: "DELETE" });
        const d = await r.json();
        if (d.targets) {
          STATE.targets = d.targets;
          renderPresets();
          renderManagePresetsList();
        }
      } catch (err) {
        console.error("Error eliminando objetivo:", err);
      }
    });

    listEl.appendChild(item);
  });
}

function syncBandsCheckboxes(bands) {
  const cards = document.querySelectorAll(".band-card");
  cards.forEach((card) => {
    const b = card.dataset.band;
    const chk = card.querySelector("input[type='checkbox']");
    const active = bands.includes(b);
    chk.checked = active;
    card.classList.toggle("active", active);
  });
}

// ============================================================================
// 6. EVENTOS DE INTERFAZ Y NAVEGACIÓN LIBRE (PAN, ZOOM, ROTACIÓN 360°)
// ============================================================================
function bindEvents() {
  // Selector de idioma
  document.getElementById("btnLangToggle").addEventListener("click", () => {
    applyLanguage(STATE.lang === "es" ? "en" : "es");
  });

  // Modal Oficial de Recursos NASA / IRSA / Space Apps
  const btnOpenRes = document.getElementById("btnOpenResources");
  const btnCloseRes = document.getElementById("btnCloseResources");
  const resModal = document.getElementById("resourcesModal");
  if (btnOpenRes && resModal) {
    btnOpenRes.addEventListener("click", () => {
      updateLiveResourceLinks();
      resModal.hidden = false;
    });
    if (btnCloseRes) {
      btnCloseRes.addEventListener("click", () => {
        resModal.hidden = true;
      });
    }
    resModal.addEventListener("click", (e) => {
      if (e.target === resModal) resModal.hidden = true;
    });
  }

  // Guía Rápida interactiva
  const btnTour = document.getElementById("btnQuickTour");
  if (btnTour) {
    btnTour.addEventListener("click", () => {
      openDocsModal(STATE.lang);
    });
  }

  // Modal Agregar / Editar Objetivo de Referencia
  const btnOpenPreset = document.getElementById("btnOpenAddPreset");
  const btnClosePreset = document.getElementById("btnCloseAddPreset");
  const addPresetModal = document.getElementById("addPresetModal");
  if (btnOpenPreset && addPresetModal) {
    btnOpenPreset.addEventListener("click", () => openPresetModalForTarget(null));
    btnClosePreset.addEventListener("click", () => {
      addPresetModal.hidden = true;
    });
    addPresetModal.addEventListener("click", (e) => {
      if (e.target === addPresetModal) addPresetModal.hidden = true;
    });
    document.getElementById("formAddPreset").addEventListener("submit", async (e) => {
      e.preventDefault();
      const statusEl = document.getElementById("presetFormStatus");
      statusEl.textContent =
        STATE.lang === "en" ? "Resolving coordinates..." : "Resolviendo coordenadas...";
      try {
        const editId = document.getElementById("presetEditId").value.trim();
        const subEs = document.getElementById("presetSub").value.trim();
        const subEnEl = document.getElementById("presetSubEn");
        const subEn = (subEnEl && subEnEl.value.trim()) || subEs;
        const payload = {
          id: editId || undefined,
          name: document.getElementById("presetName").value.trim(),
          query: document.getElementById("presetCoord").value.trim(),
          subtitle: subEs,
          subtitle_en: subEn,
          bands: document.getElementById("presetBands").value.trim(),
          fov: parseFloat(document.getElementById("presetFov").value),
          science_note: document.getElementById("presetNote").value.trim(),
        };
        const r = await fetch("/api/targets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await r.json();
        if (data.error) {
          statusEl.textContent = `⚠️ ${data.error}`;
          return;
        }
        STATE.targets = data.targets || STATE.targets;
        STATE.activeTarget = data.added;
        addPresetModal.hidden = true;
        selectTargetFromAllsky(data.added);
      } catch (err) {
        statusEl.textContent = `⚠️ ${err.message}`;
      }
    });
  }

  // Modal Administrador de Objetivos de Referencia
  const btnOpenManage = document.getElementById("btnOpenManagePresets");
  const manageModal = document.getElementById("managePresetsModal");
  if (btnOpenManage && manageModal) {
    btnOpenManage.addEventListener("click", () => {
      renderManagePresetsList();
      manageModal.hidden = false;
    });
    document.getElementById("btnCloseManagePresets").addEventListener("click", () => {
      manageModal.hidden = true;
    });
    manageModal.addEventListener("click", (e) => {
      if (e.target === manageModal) manageModal.hidden = true;
    });
    document.getElementById("managePresetsSearch").addEventListener("input", () => {
      renderManagePresetsList();
    });
    document.getElementById("btnManageAddNew").addEventListener("click", () => {
      manageModal.hidden = true;
      openPresetModalForTarget(null);
    });
    document.getElementById("btnManageRestoreDefaults").addEventListener("click", async () => {
      try {
        const r = await fetch("/api/targets?id=__RESTORE_DEFAULTS__", { method: "DELETE" });
        const d = await r.json();
        if (d.targets) {
          STATE.targets = d.targets;
          renderPresets();
          renderManagePresetsList();
        }
      } catch (err) {
        console.error("Error restaurando objetivos predeterminados:", err);
      }
    });
  }

  // Modal Reporte MPC 80 Columnas
  const btnExportMpc = document.getElementById("btnExportMpc");
  const mpcModal = document.getElementById("mpcModal");
  if (btnExportMpc && mpcModal) {
    btnExportMpc.addEventListener("click", () => {
      const txtEl = document.getElementById("mpcReportText");
      const lines = (STATE.cube && STATE.cube.mpc_report) || [];
      const info = (STATE.cube && STATE.cube.mpc_info) || {};
      if (txtEl) txtEl.value = lines.join("\n");
      const st = document.getElementById("mpcCopyStatus");
      if (st) {
        const disc = STATE.lang === "en" ? info.disclaimer_en : info.disclaimer_es;
        const reason = STATE.lang === "en" ? info.reason_en : info.reason_es;
        st.textContent = lines.length ? disc || "" : `${reason || ""} ${disc || ""}`.trim();
      }
      mpcModal.hidden = false;
    });
    document.getElementById("btnCloseMpcModal").addEventListener("click", () => {
      mpcModal.hidden = true;
    });
    mpcModal.addEventListener("click", (e) => {
      if (e.target === mpcModal) mpcModal.hidden = true;
    });
    document.getElementById("btnCopyMpcReport").addEventListener("click", () => {
      const txtEl = document.getElementById("mpcReportText");
      if (txtEl) {
        navigator.clipboard.writeText(txtEl.value);
        const st = document.getElementById("mpcCopyStatus");
        if (st) {
          st.textContent =
            STATE.lang === "en"
              ? "✓ 80-column MPC report copied to clipboard"
              : "✓ Reporte MPC de 80 columnas copiado al portapapeles";
        }
      }
    });
    document.getElementById("btnDownloadMpcTxt").addEventListener("click", () => {
      const txtEl = document.getElementById("mpcReportText");
      if (!txtEl) return;
      const blob = new Blob([txtEl.value + "\n"], { type: "text/plain;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `spherex_mpc80_${STATE.ra.toFixed(3)}_${STATE.dec.toFixed(3)}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  // Búsqueda por coordenadas o SIMBAD
  document.getElementById("btnResolve").addEventListener("click", handleSearchResolve);
  document.getElementById("inputQuery").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSearchResolve();
  });

  // Cambios de parámetros del cubo
  document.getElementById("selectFov").addEventListener("change", (e) => {
    STATE.fov = parseFloat(e.target.value);
    if (STATE.mode === "allsky") STATE.mode = "blink";
    syncViewportVisibility();
    loadSkyPatch();
  });
  document.getElementById("selectDepth").addEventListener("change", (e) => {
    STATE.maxPerEpoch = parseInt(e.target.value, 10);
    loadSkyPatch();
  });
  document.getElementById("selectGap").addEventListener("change", (e) => {
    STATE.gapDays = parseFloat(e.target.value);
    loadSkyPatch();
  });

  // Selección rápida de bandas
  document.querySelectorAll(".chip-btn[data-preset-bands]").forEach((btn) => {
    btn.addEventListener("click", () => {
      STATE.bands = btn.dataset.presetBands.split(",");
      syncBandsCheckboxes(STATE.bands);
      if (STATE.mode === "allsky") STATE.mode = "blink";
      syncViewportVisibility();
      loadSkyPatch();
    });
  });

  // Tarjetas individuales de banda D1-D6
  document.querySelectorAll(".band-card").forEach((card) => {
    const chk = card.querySelector("input[type='checkbox']");
    chk.addEventListener("change", () => {
      card.classList.toggle("active", chk.checked);
      const checked = Array.from(document.querySelectorAll(".band-card input:checked")).map(
        (c) => c.value
      );
      if (checked.length === 0) {
        chk.checked = true;
        card.classList.add("active");
        return;
      }
      STATE.bands = checked;
    });
  });

  document.getElementById("btnUpdateCube").addEventListener("click", () => {
    if (STATE.mode === "allsky") STATE.mode = "blink";
    syncViewportVisibility();
    loadSkyPatch();
  });

  // Toggles de capas, Detector IA, Reconocedor Automático de Astros y Regla de Distancia 3D
  const chkAiDet = document.getElementById("chkAiDetector");
  if (chkAiDet) {
    chkAiDet.addEventListener("change", (e) => {
      STATE.aiDetectorEnabled = e.target.checked;
      updateAiDetectorButtonText();
      syncViewportVisibility();
      renderCanvasFrame();
    });
  }
  const btnToggleAi = document.getElementById("btnToggleAiDetector");
  if (btnToggleAi) {
    btnToggleAi.addEventListener("click", () => {
      STATE.aiDetectorEnabled = !STATE.aiDetectorEnabled;
      if (chkAiDet) chkAiDet.checked = STATE.aiDetectorEnabled;
      updateAiDetectorButtonText();
      syncViewportVisibility();
      renderCanvasFrame();
    });
  }

  const chkStarRec = document.getElementById("chkStarRecognizer");
  const btnToggleStarRec = document.getElementById("btnToggleStarRecognizer");
  if (chkStarRec) {
    chkStarRec.addEventListener("change", (e) => {
      STATE.starRecognizerEnabled = e.target.checked;
      updateStarRecognizerButtonText();
      renderCanvasFrame();
    });
  }
  if (btnToggleStarRec) {
    btnToggleStarRec.addEventListener("click", () => {
      STATE.starRecognizerEnabled = !STATE.starRecognizerEnabled;
      if (chkStarRec) chkStarRec.checked = STATE.starRecognizerEnabled;
      updateStarRecognizerButtonText();
      renderCanvasFrame();
    });
  }



  ["chkCandidates", "chkGaia", "chkGrid"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", () => renderCanvasFrame());
  });
  document.getElementById("chkFlags").addEventListener("change", () => {
    invalidateFrameCache();
    renderCanvasFrame();
  });

  document.getElementById("selectColormap").addEventListener("change", (e) => {
    STATE.cmap = e.target.value;
    updateColorbarGradient();
    invalidateFrameCache();
    renderCanvasFrame();
  });
  document.getElementById("selectStretch").addEventListener("change", (e) => {
    STATE.stretch = e.target.value;
    invalidateFrameCache();
    renderCanvasFrame();
  });
  document.getElementById("rangeContrast").addEventListener("input", (e) => {
    STATE.contrast = parseFloat(e.target.value);
    document.getElementById("lblContrast").textContent = `${STATE.contrast.toFixed(1)}×`;
    invalidateFrameCache();
    renderCanvasFrame();
  });
  document.getElementById("chkSmooth").addEventListener("change", (e) => {
    STATE.smoothImage = e.target.checked;
    renderCanvasFrame();
  });
  const chkBb = document.getElementById("chkShowBlackbody");
  if (chkBb) {
    chkBb.addEventListener("change", (e) => {
      STATE.showBlackbodyModel = e.target.checked;
      renderSpectrumChart();
    });
  }

  // Pestañas de modo de visualización
  document.querySelectorAll(".mode-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      STATE.mode = tab.dataset.mode;
      syncViewportVisibility();
      invalidateFrameCache();
      renderPresets();
      renderCanvasFrame();
    });
  });

  // Controles del Visor del Universo Observable 360° (Orientación Isótropa SO(3) + Cubo All-Sky Oficial SPHEREx DR1)
  const selEngine = document.getElementById("selectAllskyEngine");
  if (selEngine) {
    selEngine.addEventListener("change", (e) => {
      STATE.allskyEngine = e.target.value;
      STATE.cachedAllskyProjKey = "";
      syncViewportVisibility();
      renderCanvasFrame();
    });
  }
  const selFrame = document.getElementById("selectAllskyFrame");
  if (selFrame) {
    selFrame.addEventListener("change", (e) => {
      STATE.allskyFrame = e.target.value;
      STATE.allskyRotLon = 0.0;
      STATE.allskyRotLat = 0.0;
      STATE.cachedAllskyProjKey = "";
      if (STATE.aladinInstance && STATE.allskyEngine === "aladin_hips" && STATE.aladinInstance.setFrame) {
        STATE.aladinInstance.setFrame(STATE.allskyFrame === "equatorial" ? "ICRS" : "galactic");
      }
      renderCanvasFrame();
    });
  }
  const selSurvey = document.getElementById("selectAllskySurvey");
  if (selSurvey) {
    selSurvey.addEventListener("change", (e) => {
      STATE.allskySurvey = e.target.value;
      STATE.cachedAllskyProjKey = "";
      ensureOfficialAllskyMapLoaded(STATE.allskySurvey);
      if (STATE.allskyEngine === "aladin_hips") {
        initOrUpdateAladinAllsky();
      } else {
        renderCanvasFrame();
      }
    });
  }
  const btnRotL = document.getElementById("btnAllskyRotLeft");
  if (btnRotL) {
    btnRotL.addEventListener("click", () => {
      STATE.allskyRotLon = (STATE.allskyRotLon - 30.0 + 360.0) % 360.0;
      renderCanvasFrame();
    });
  }
  const btnRotR = document.getElementById("btnAllskyRotRight");
  if (btnRotR) {
    btnRotR.addEventListener("click", () => {
      STATE.allskyRotLon = (STATE.allskyRotLon + 30.0) % 360.0;
      renderCanvasFrame();
    });
  }
  const btnGalCenter = document.getElementById("btnAllskyGalCenter");
  if (btnGalCenter) {
    btnGalCenter.addEventListener("click", () => {
      const frm = eqToActiveFrame(266.4168, -29.0078);
      STATE.allskyRotLon = frm.lon;
      STATE.allskyRotLat = frm.lat;
      if (STATE.aladinInstance && STATE.allskyEngine === "aladin_hips") {
        STATE.aladinInstance.gotoRaDec(266.4168, -29.0078);
      }
      renderCanvasFrame();
    });
  }
  const btnNep = document.getElementById("btnAllskyNep");
  if (btnNep) {
    btnNep.addEventListener("click", () => {
      const frm = eqToActiveFrame(270.0, 66.5607);
      STATE.allskyRotLon = frm.lon;
      STATE.allskyRotLat = frm.lat;
      if (STATE.aladinInstance && STATE.allskyEngine === "aladin_hips") {
        STATE.aladinInstance.gotoRaDec(270.0, 66.5607);
      }
      renderCanvasFrame();
    });
  }
  const btnSep = document.getElementById("btnAllskySep");
  if (btnSep) {
    btnSep.addEventListener("click", () => {
      const frm = eqToActiveFrame(90.0, -66.5607);
      STATE.allskyRotLon = frm.lon;
      STATE.allskyRotLat = frm.lat;
      if (STATE.aladinInstance && STATE.allskyEngine === "aladin_hips") {
        STATE.aladinInstance.gotoRaDec(90.0, -66.5607);
      }
      renderCanvasFrame();
    });
  }
  const btnAllskyReset = document.getElementById("btnAllskyReset");
  if (btnAllskyReset) {
    btnAllskyReset.addEventListener("click", () => {
      STATE.allskyRotLon = 0.0;
      STATE.allskyRotLat = 0.0;
      STATE.allskyRoll = 0.0;
      STATE.viewZoom = 1.0;
      STATE.viewPanX = 0.0;
      STATE.viewPanY = 0.0;
      if (STATE.aladinInstance && STATE.allskyEngine === "aladin_hips") {
        STATE.aladinInstance.setFov(360);
        STATE.aladinInstance.gotoRaDec(266.4168, -29.0078);
      }
      renderCanvasFrame();
    });
  }
  const btnAllskyExtract = document.getElementById("btnAllskyExtract");
  if (btnAllskyExtract) {
    btnAllskyExtract.addEventListener("click", () => {
      if (STATE.allskyEngine === "aladin_hips" && STATE.aladinInstance) {
        const radec = STATE.aladinInstance.getRaDec();
        if (radec && radec.length === 2) {
          STATE.ra = Number(radec[0]);
          STATE.dec = Number(radec[1]);
        }
      } else {
        const canvas = document.getElementById("skyCanvas");
        const W = canvas.width;
        const H = canvas.height;
        const { cx: centerX, cy: centerY, rx, ry } = allskyGeom(W, H);
        const inv = inverseHammerAitoff(W * 0.5, H * 0.54, STATE.allskyRotLon, STATE.allskyRotLat, centerX, centerY, rx, ry);
        if (inv) {
          STATE.ra = inv.ra;
          STATE.dec = inv.dec;
        }
      }
      STATE.mode = "blink";
      document.getElementById("inputQuery").value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
      syncViewportVisibility();
      renderPresets();
      loadSkyPatch();
    });
  }

  document.getElementById("rangeSplit").addEventListener("input", (e) => {
    STATE.splitPct = parseInt(e.target.value, 10);
    invalidateFrameCache();
    renderCanvasFrame();
  });

  // Controles del reproductor Blinking
  document.getElementById("btnPlayPause").addEventListener("click", togglePlayPause);
  document.getElementById("btnPrevEpoch").addEventListener("click", () => stepEpoch(-1));
  document.getElementById("btnNextEpoch").addEventListener("click", () => stepEpoch(1));
  document.getElementById("rangeSpeed").addEventListener("input", (e) => {
    STATE.blinkSpeedMs = parseInt(e.target.value, 10);
    document.getElementById("lblSpeed").textContent = `${STATE.blinkSpeedMs} ms`;
    restartBlinkTimer();
  });

  // Atajos de teclado (incluyendo rotación 360° vertical con Flechas Arriba/Abajo)
  const btnFs = document.getElementById("btnFullscreen");
  if (btnFs) btnFs.addEventListener("click", toggleViewerFullscreen);
  const btnFs2 = document.getElementById("btnFullscreenToolbar");
  if (btnFs2) btnFs2.addEventListener("click", toggleViewerFullscreen);

  window.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    if (e.code === "KeyF" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      toggleViewerFullscreen();
      return;
    }
    if (e.code === "Space") {
      e.preventDefault();
      togglePlayPause();
    } else if (e.code === "ArrowLeft") {
      e.preventDefault();
      if (STATE.mode === "allsky") {
        STATE.allskyRotLon = (STATE.allskyRotLon - 15.0 + 360.0) % 360.0;
        renderCanvasFrame();
      } else {
        stepEpoch(-1);
      }
    } else if (e.code === "ArrowRight") {
      e.preventDefault();
      if (STATE.mode === "allsky") {
        STATE.allskyRotLon = (STATE.allskyRotLon + 15.0) % 360.0;
        renderCanvasFrame();
      } else {
        stepEpoch(1);
      }
    } else if (e.code === "ArrowUp" && STATE.mode === "allsky") {
      e.preventDefault();
      STATE.allskyRotLat = Math.max(-90, Math.min(90, STATE.allskyRotLat + 15.0));
      renderCanvasFrame();
    } else if (e.code === "ArrowDown" && STATE.mode === "allsky") {
      e.preventDefault();
      STATE.allskyRotLat = Math.max(-90, Math.min(90, STATE.allskyRotLat - 15.0));
      renderCanvasFrame();
    }
  });

  // Interacción en #skyCanvas: Arrastrar para Navegación Continua del Cielo o Rotar 360° Libremente
  const canvas = document.getElementById("skyCanvas");
  canvas.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    STATE.isDragging = true;
    STATE.dragMoved = false;
    const rect = canvas.getBoundingClientRect();
    STATE.dragStartX = (ev.clientX - rect.left) * (canvas.width / rect.width);
    STATE.dragStartY = (ev.clientY - rect.top) * (canvas.height / rect.height);
    STATE.dragOriginPanX = STATE.viewPanX;
    STATE.dragOriginPanY = STATE.viewPanY;
    STATE.dragOriginLon = STATE.allskyRotLon;
    STATE.dragOriginLat = STATE.allskyRotLat;
  });

  window.addEventListener("mouseup", () => {
    if (!STATE.isDragging) return;
    STATE.isDragging = false;
    // Si estamos en modo FITS y el usuario arrastró el cielo para explorar los alrededores,
    // actualizamos automáticamente las coordenadas centrales y transmitimos el nuevo cubo continuo sin pantallas negras
    if (STATE.mode !== "allsky" && STATE.cube) {
      const panDist = Math.hypot(STATE.viewPanX, STATE.viewPanY);
      if (panDist > 18) {
        const c = document.getElementById("skyCanvas");
        const { gx, gy } = canvasToGrid(c.width * 0.5, c.height * 0.5);
        const { ra, dec } = pixelToWorld(gx, gy);
        if (STATE.panFetchInProgress) {
          // Arrastre durante una carga: se guarda el último destino y se carga al terminar (no se pierde)
          STATE.pendingPan = { ra, dec };
          return;
        }
        applyPanCenter(ra, dec);
        loadSkyPatch({ silent: true });
      }
    }
  });

  canvas.addEventListener("mousemove", (ev) => {
    if (STATE.isDragging) {
      const rect = canvas.getBoundingClientRect();
      const cx = (ev.clientX - rect.left) * (canvas.width / rect.width);
      const cy = (ev.clientY - rect.top) * (canvas.height / rect.height);
      const dx = cx - STATE.dragStartX;
      const dy = cy - STATE.dragStartY;
      if (Math.hypot(dx, dy) > 4) {
        STATE.dragMoved = true;
      }
      if (STATE.mode === "allsky" && STATE.allskyEngine !== "aladin_hips") {
        // Rotación omnidireccional 360° (incluyendo Polo Norte +90° y Polo Sur -90°)
        const degPerPx = 180.0 / (canvas.width * 0.42 * Math.max(STATE.viewZoom, 0.8));
        STATE.allskyRotLon = ((STATE.dragOriginLon - dx * degPerPx) % 360.0 + 360.0) % 360.0;
        STATE.allskyRotLat = Math.max(-90.0, Math.min(90.0, STATE.dragOriginLat + dy * degPerPx * 0.85));
      } else {
        STATE.viewPanX = STATE.dragOriginPanX + dx;
        STATE.viewPanY = STATE.dragOriginPanY + dy;
      }
      renderCanvasFrame();
      return;
    }
    handleCanvasHover(ev);
  });

  canvas.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = (ev.clientX - rect.left) * (canvas.width / rect.width);
      const my = (ev.clientY - rect.top) * (canvas.height / rect.height);
      const factor = ev.deltaY < 0 ? 1.22 : 1 / 1.22;
      const newZoom = Math.max(0.45, Math.min(18.0, STATE.viewZoom * factor));
      const g0 = STATE.mode === "allsky" ? { ox: 0, oy: 0 } : skyGeom(canvas);
      const lx = mx - g0.ox;
      const ly = my - g0.oy;
      STATE.viewPanX = lx - (lx - STATE.viewPanX) * (newZoom / STATE.viewZoom);
      STATE.viewPanY = ly - (ly - STATE.viewPanY) * (newZoom / STATE.viewZoom);
      STATE.viewZoom = newZoom;
      renderCanvasFrame();
      scheduleDynamicZoomUpdate();
    },
    { passive: false }
  );

  canvas.addEventListener("click", (ev) => {
    if (STATE.dragMoved) {
      STATE.dragMoved = false;
      return;
    }
    handleCanvasClick(ev);
  });

  canvas.addEventListener("dblclick", (ev) => {
    ev.preventDefault();
    handleCanvasDoubleClick(ev);
  });

  // Botones flotantes de Zoom y Re-centrado
  document.getElementById("btnZoomIn").addEventListener("click", () => {
    const c = document.getElementById("skyCanvas");
    const gz = STATE.mode === "allsky" ? { ox: 0, oy: 0, S: c.width } : skyGeom(c);
    const cx = STATE.mode === "allsky" ? c.width / 2 : gz.S / 2;
    const cy = STATE.mode === "allsky" ? c.height / 2 : gz.S / 2;
    const nz = Math.min(18.0, STATE.viewZoom * 1.35);
    STATE.viewPanX = cx - (cx - STATE.viewPanX) * (nz / STATE.viewZoom);
    STATE.viewPanY = cy - (cy - STATE.viewPanY) * (nz / STATE.viewZoom);
    STATE.viewZoom = nz;
    renderCanvasFrame();
    scheduleDynamicZoomUpdate();
  });
  document.getElementById("btnZoomOut").addEventListener("click", () => {
    const c = document.getElementById("skyCanvas");
    const gz = STATE.mode === "allsky" ? { ox: 0, oy: 0, S: c.width } : skyGeom(c);
    const cx = STATE.mode === "allsky" ? c.width / 2 : gz.S / 2;
    const cy = STATE.mode === "allsky" ? c.height / 2 : gz.S / 2;
    const nz = Math.max(0.45, STATE.viewZoom / 1.35);
    STATE.viewPanX = cx - (cx - STATE.viewPanX) * (nz / STATE.viewZoom);
    STATE.viewPanY = cy - (cy - STATE.viewPanY) * (nz / STATE.viewZoom);
    STATE.viewZoom = nz;
    renderCanvasFrame();
    scheduleDynamicZoomUpdate();
  });
  document.getElementById("btnZoomReset").addEventListener("click", () => {
    STATE.viewZoom = 1.0;
    STATE.viewPanX = 0.0;
    STATE.viewPanY = 0.0;
    STATE.allskyRotLon = 0.0;
    STATE.allskyRotLat = 0.0;
    STATE.allskyRoll = 0.0;
    renderCanvasFrame();
  });
  document.getElementById("btnRecenterHere").addEventListener("click", () => {
    if (!STATE.cube) return;
    const c = document.getElementById("skyCanvas");
    const { gx, gy } = canvasToGrid(c.width / 2, c.height / 2);
    const { ra, dec } = pixelToWorld(gx, gy);
    STATE.ra = ((ra % 360.0) + 360.0) % 360.0;
    STATE.dec = Math.max(-89.9, Math.min(89.9, dec));
    STATE.activeTarget = null;
    STATE.viewZoom = 1.0;
    STATE.viewPanX = 0.0;
    STATE.viewPanY = 0.0;
    if (STATE.mode === "allsky") STATE.mode = "blink";
    document.getElementById("inputQuery").value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
    renderPresets();
    syncViewportVisibility();
    loadSkyPatch();
  });

  // Exportar CSV del espectro
  document.getElementById("btnDownloadSpecCsv").addEventListener("click", downloadSpectrumCsv);

  // Exportar GIF y compartir URL
  document.getElementById("btnExportGif").addEventListener("click", exportBlinkGif);
  document.getElementById("btnShareUrl").addEventListener("click", shareCurrentUrl);

  // Centro de Documentación (Documento Único Bilingüe ES/EN)
  document.getElementById("btnOpenDocs").addEventListener("click", () => {
    openDocsModal(STATE.lang);
  });
  document.getElementById("btnCloseDocs").addEventListener("click", closeDocsModal);
  document.getElementById("docsModal").addEventListener("click", (e) => {
    if (e.target.id === "docsModal") closeDocsModal();
  });
  const btnDocLang = document.getElementById("btnToggleDocLang");
  if (btnDocLang) {
    btnDocLang.addEventListener("click", async () => {
      const contentEl = document.getElementById("docsModalContent");
      const ratio =
        contentEl && contentEl.scrollHeight > contentEl.clientHeight
          ? contentEl.scrollTop / (contentEl.scrollHeight - contentEl.clientHeight)
          : 0;
      const nextLang = STATE.docLang === "en" ? "es" : "en";
      await loadDocumentIntoModal(nextLang);
      if (contentEl && ratio > 0.02) {
        const maxTop = Math.max(0, contentEl.scrollHeight - contentEl.clientHeight);
        contentEl.scrollTop = Math.round(ratio * maxTop);
      }
    });
  }
  document.querySelectorAll("#docsModalTabs .doc-toc-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#docsModalTabs .doc-toc-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const ch = btn.dataset.chapter;
      const container = document.getElementById("docsModalContent");
      const targetEl = container && container.querySelector(`[data-chapter="${ch}"]`);
      if (container && targetEl) {
        container.scrollTo({ top: Math.max(0, targetEl.offsetTop - container.offsetTop - 8), behavior: "smooth" });
      }
    });
  });
  const docsBodyEl = document.getElementById("docsModalContent");
  if (docsBodyEl) {
    docsBodyEl.addEventListener("click", (e) => {
      const link = e.target.closest("a[href^='#']");
      if (!link) return;
      e.preventDefault();
      const targetId = link.getAttribute("href").slice(1);
      const targetEl = docsBodyEl.querySelector(`#${CSS.escape(targetId)}`);
      if (targetEl) {
        docsBodyEl.scrollTo({ top: Math.max(0, targetEl.offsetTop - docsBodyEl.offsetTop - 8), behavior: "smooth" });
      }
    });
  }

  // AstroAI Copilot Chat
  document.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = STATE.lang === "en" ? chip.dataset.qEn : chip.dataset.qEs;
      sendAiQuestion(q);
    });
  });
  document.getElementById("aiChatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const inp = document.getElementById("aiChatInput");
    const q = inp.value.trim();
    if (!q) return;
    inp.value = "";
    sendAiQuestion(q);
  });

  updateColorbarGradient();
}

// ============================================================================
// 7. STREAMING CONTINUO DE ZOOM/PAN Y CARGA DE DATOS DESDE EL BACKEND
// ============================================================================
const FOV_LADDER = [0.06, 0.10, 0.12, 0.18, 0.35, 0.80, 1.60];

function scheduleDynamicZoomUpdate() {
  if (STATE.zoomDebounceTimer) clearTimeout(STATE.zoomDebounceTimer);
  STATE.zoomDebounceTimer = setTimeout(() => {
    if (STATE.panFetchInProgress) return;
    const canvas = document.getElementById("skyCanvas");
    if (!canvas) return;

    if (STATE.mode === "allsky") {
      // Si el usuario hace mucho zoom hacia adentro en el mapa 360°, conmutar automáticamente al cubo FITS de esa coordenada
      if (STATE.viewZoom > 4.2 && STATE.allskyEngine !== "aladin_hips") {
        const W = canvas.width;
        const H = canvas.height;
        const { cx: centerX, cy: centerY, rx, ry } = allskyGeom(W, H);
        const inv = inverseHammerAitoff(W * 0.5, H * 0.54, STATE.allskyRotLon, STATE.allskyRotLat, centerX, centerY, rx, ry);
        if (inv) {
          STATE.ra = inv.ra;
          STATE.dec = inv.dec;
          STATE.fov = 0.80;
          STATE.viewZoom = 1.0;
          STATE.viewPanX = 0.0;
          STATE.viewPanY = 0.0;
          STATE.mode = "blink";
          const sf = document.getElementById("selectFov");
          if (sf) sf.value = "0.80";
          const inp = document.getElementById("inputQuery");
          if (inp) inp.value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
          syncViewportVisibility();
          renderPresets();
          loadSkyPatch({ silent: true });
        }
      }
      return;
    }

    if (!STATE.cube) return;
    let curIdx = 0;
    let minDiff = Infinity;
    FOV_LADDER.forEach((f, idx) => {
      const d = Math.abs(f - STATE.fov);
      if (d < minDiff) {
        minDiff = d;
        curIdx = idx;
      }
    });

    if (STATE.viewZoom < 0.72) {
      // El usuario alejó la cámara: ampliar el FOV nativamente o pasar a la esfera 360° si ya está en el máximo FOV
      if (curIdx < FOV_LADDER.length - 1) {
        const { gx, gy } = canvasToGrid(canvas.width * 0.5, canvas.height * 0.5);
        const { ra, dec } = pixelToWorld(gx, gy);
        STATE.ra = ((ra % 360.0) + 360.0) % 360.0;
        STATE.dec = Math.max(-89.9, Math.min(89.9, dec));
        STATE.fov = FOV_LADDER[curIdx + 1];
        const sf = document.getElementById("selectFov");
        if (sf) sf.value = STATE.fov.toFixed(2);
        loadSkyPatch({ silent: true });
      } else if (STATE.viewZoom < 0.54) {
        STATE.viewZoom = 1.0;
        STATE.viewPanX = 0.0;
        STATE.viewPanY = 0.0;
        STATE.mode = "allsky";
        syncViewportVisibility();
        renderPresets();
        renderCanvasFrame();
      }
    } else if (STATE.viewZoom > 2.35 && curIdx > 0) {
      // El usuario acercó la cámara: refinar el FOV nativamente en la región enfocada
      const { gx, gy } = canvasToGrid(canvas.width * 0.5, canvas.height * 0.5);
      const { ra, dec } = pixelToWorld(gx, gy);
      STATE.ra = ((ra % 360.0) + 360.0) % 360.0;
      STATE.dec = Math.max(-89.9, Math.min(89.9, dec));
      STATE.fov = FOV_LADDER[curIdx - 1];
      const sf = document.getElementById("selectFov");
      if (sf) sf.value = STATE.fov.toFixed(2);
      const inp = document.getElementById("inputQuery");
      if (inp) inp.value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
      loadSkyPatch({ silent: true });
    }
  }, 320);
}

async function handleSearchResolve() {
  const q = document.getElementById("inputQuery").value.trim();
  if (!q) return;
  setStatus(STATE.lang === "en" ? "Resolving name / coordinates..." : "Resolviendo nombre / coordenadas...", true);
  try {
    const r = await fetch(`/api/resolve?q=${encodeURIComponent(q)}&epoch=2026.0`);
    const data = await r.json();
    if (data.error) {
      setStatus(data.error, false);
      return;
    }
    STATE.ra = data.ra;
    STATE.dec = data.dec;
    STATE.pmRa = data.pm_ra || 0;
    STATE.pmDec = data.pm_dec || 0;
    STATE.activeTarget = data.preset_id ? STATE.targets.find((t) => t.id === data.preset_id) || null : null;
    STATE.astrometry = !STATE.activeTarget && data.astrometry ? data.astrometry : null;
    STATE.aperturePx = null;
    STATE.pointSpectrum = null;
    STATE.pointLightCurve = null;
    STATE.pointForcedPsf = null;
    if (STATE.mode === "allsky") STATE.mode = "blink";
    const note = STATE.lang === "en" ? data.note_en || data.note : data.note;
    if (note) setStatus(note, false);
    renderPresets();
    syncViewportVisibility();
    await loadSkyPatch();
  } catch (err) {
    console.error(err);
    setStatus("Error", false);
  }
}

function applyPanCenter(ra, dec) {
  STATE.ra = ((ra % 360.0) + 360.0) % 360.0;
  STATE.dec = Math.max(-89.9, Math.min(89.9, dec));
  STATE.activeTarget = null;
  STATE.aperturePx = null;
  STATE.pointSpectrum = null;
  const inp = document.getElementById("inputQuery");
  if (inp) inp.value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
  renderPresets();
}

function runPendingPan() {
  if (!STATE.pendingPan || STATE.panFetchInProgress) return;
  const p = STATE.pendingPan;
  STATE.pendingPan = null;
  applyPanCenter(p.ra, p.dec);
  loadSkyPatch({ silent: true });
}

async function loadSkyPatch(opts = {}) {
  const silent = Boolean(opts && opts.silent);
  if (STATE.irsaRetryTimer) {
    clearTimeout(STATE.irsaRetryTimer);
    STATE.irsaRetryTimer = null;
  }
  STATE.panFetchInProgress = true;
  if (!silent) {
    showLoading(true);
  }
  setStatus(
    STATE.lang === "en"
      ? silent
        ? "Streaming adjacent SPHEREx sky..."
        : "Loading SPHEREx FITS..."
      : silent
      ? "Transmitiendo campo SPHEREx continuo..."
      : "Cargando FITS SPHEREx...",
    true
  );

  document.getElementById("valRa").textContent = `${STATE.ra.toFixed(5)}°`;
  document.getElementById("valDec").textContent = `${STATE.dec.toFixed(5)}°`;
  document.getElementById("valPm").textContent = `${Math.round(STATE.pmRa)}, ${Math.round(STATE.pmDec)} mas/yr`;
  updateLiveResourceLinks();

  try {
    const params = new URLSearchParams({
      ra: STATE.ra.toFixed(6),
      dec: STATE.dec.toFixed(6),
      fov: STATE.fov.toFixed(3),
      bands: STATE.bands.join(","),
      // Navegación (arrastre/zoom): 3 exp/época para que el campo vecino llegue rápido; el selector sigue mandando al cargar a propósito
      max_per_epoch: String(silent ? Math.min(3, STATE.maxPerEpoch) : STATE.maxPerEpoch),
      gap_days: String(STATE.gapDays),
      release: STATE.release,
    });
    appendAstrometryParams(params);
    const r = await fetch(`/api/cube?${params.toString()}`);
    const cube = await r.json();
    if (cube.error) {
      showLoading(false);
      STATE.panFetchInProgress = false;
      setTimeout(runPendingPan, 0);
      setStatus(cube.error, false);
      return;
    }

    STATE.cube = cube;
    STATE.cubeStamp += 1;
    if (!silent || STATE.currentEpochIdx >= cube.epochs.length) {
      STATE.currentEpochIdx = 0;
    }
    STATE.viewZoom = 1.0;
    STATE.viewPanX = 0.0;
    STATE.viewPanY = 0.0;
    decodeEpochArrays(cube);
    invalidateFrameCache();

    // Actualizar contadores de exposiciones por banda D1-D6
    if (cube.band_summary) {
      Object.entries(cube.band_summary).forEach(([b, info]) => {
        const el = document.getElementById(`cnt-${b}`);
        if (el) el.textContent = info.count === null || info.count === undefined ? "—" : `${info.count} exp`;
      });
    }

    if (!STATE.aperturePx) {
      const [ny, nx] = cube.shape;
      const tr = (cube.target_track || [])[0];
      STATE.aperturePx = tr && cube.target
        ? { x: Math.round(tr.px), y: Math.round(tr.py), label: cube.target.name }
        : { x: Math.floor(nx / 2), y: Math.floor(ny / 2), label: "Centro" };
    }

    // Si la regla 3D está activa, actualizar o inicializar los puntos A y B en el nuevo campo

    syncViewportVisibility();
    renderEpochTimeline();
    updateScienceBanner();
    renderExposureTable();
    renderCandidatesBar();
    renderRecognizedObjectsBar();
    renderAiDetectorHud();
    renderArtifactShieldAndMath();
    renderSpectrumChart();
    renderAutoAiSummary();
    renderCanvasFrame();
    if (!silent) {
      restartBlinkTimer();
    }

    showLoading(false);
    STATE.panFetchInProgress = false;
    setTimeout(runPendingPan, 0);
    setStatus(
      cube.data_mode === "dr1_static"
        ? STATE.lang === "en"
          ? `Static DR1 (no L2b available)${cube.retry_after_s ? " · retrying IRSA automatically" : ""} · ${cube.elapsed_sec}s`
          : `DR1 estático (sin L2b disponible)${cube.retry_after_s ? " · reintento automático de IRSA" : ""} · ${cube.elapsed_sec}s`
        : `${cube.epochs.length} ${STATE.lang === "en" ? "epochs" : "épocas"} · ${cube.used_exposures} exp (${cube.elapsed_sec}s)`,
      false
    );

    fetchExternalCatalogs();
    fetchDr1Spectrum();
    // IRSA no respondió: reintento automático del mismo campo (el cubo DR1 estático no tiene épocas reales)
    if (cube.retry_after_s && cube.data_mode === "dr1_static") {
      const stamp = STATE.cubeStamp;
      STATE.irsaRetryTimer = setTimeout(() => {
        STATE.irsaRetryTimer = null;
        if (STATE.cubeStamp === stamp && STATE.mode !== "allsky") loadSkyPatch({ silent: false });
      }, cube.retry_after_s * 1000);
    }
  } catch (err) {
    console.error("Error construyendo cubo SPHEREx:", err);
    showLoading(false);
    STATE.panFetchInProgress = false;
    setTimeout(runPendingPan, 0);
    setStatus("Error", false);
  }
}

function appendAstrometryParams(params) {
  if (STATE.activeTarget && !STATE.activeTarget.is_allsky && STATE.activeTarget.astrometry) {
    params.set("target_id", STATE.activeTarget.id);
  } else if (STATE.astrometry) {
    const a = STATE.astrometry;
    params.set("pmra", String(a.pmra_masyr || 0));
    params.set("pmdec", String(a.pmdec_masyr || 0));
    params.set("ast_ra", String(a.ra_deg));
    params.set("ast_dec", String(a.dec_deg));
    params.set("ast_epoch", String(a.epoch_jyear || 2000.0));
    if (a.parallax_mas) params.set("plx", String(a.parallax_mas));
    if (a.ref) params.set("ast_ref", String(a.ref));
  }
}

async function fetchDr1Spectrum() {
  if (!STATE.cube) return;
  const params = new URLSearchParams({ ra: STATE.ra.toFixed(6), dec: STATE.dec.toFixed(6) });
  appendAstrometryParams(params);
  const key = params.toString();
  if (STATE.dr1SpectrumKey === key && STATE.dr1Spectrum) {
    renderSpectrumChart();
    renderBandDepthPills();
    return;
  }
  STATE.dr1Spectrum = null;
  STATE.dr1SpectrumKey = key;
  renderBandDepthPills();
  try {
    const r = await fetch(`/api/dr1_spectrum?${key}`);
    const data = await r.json();
    if (STATE.dr1SpectrumKey !== key) return;
    STATE.dr1Spectrum = data.error ? null : data;
    renderSpectrumChart();
    renderBandDepthPills();
  } catch (err) {
    console.warn("Espectro DR1 no disponible:", err);
  }
}

async function fetchExternalCatalogs() {
  try {
    const params = new URLSearchParams({
      ra: STATE.ra.toFixed(6),
      dec: STATE.dec.toFixed(6),
      fov: STATE.fov.toFixed(3),
    });
    if (STATE.cube && STATE.cube.epochs && STATE.cube.epochs.length) {
      const mjd = STATE.cube.epochs.reduce((s, e) => s + e.mjd, 0) / STATE.cube.epochs.length;
      params.set("epoch", (2000.0 + (mjd - 51544.5) / 365.25).toFixed(3));
    }
    const r = await fetch(`/api/catalogs?${params.toString()}`);
    const data = await r.json();
    STATE.catalogs = {
      gaia: data.gaia || [],
      allwise: data.allwise || [],
    };
    renderCanvasFrame();
  } catch (err) {
    console.warn("Catálogos externos no disponibles:", err);
  }
}

function decodeEpochArrays(cube) {
  const [ny, nx] = cube.shape;
  STATE.decodedEpochs = cube.epochs.map((ep) => {
    const rawImg = Uint8Array.from(atob(ep.data_b64), (c) => c.charCodeAt(0));
    const floatArr = new Float32Array(rawImg.buffer);
    const rawFlg = Uint8Array.from(atob(ep.flags_b64), (c) => c.charCodeAt(0));
    const intFlags = new Int32Array(rawFlg.buffer);
    const cov = ep.cov_b64 ? Uint8Array.from(atob(ep.cov_b64), (c) => c.charCodeAt(0)) : null;
    return { ...ep, floatArr, intFlags, cov, nx, ny };
  });
}

// ============================================================================
// 8. RENDERIZADO CIENTÍFICO DEL LIENZO (CACHÉ OFFSCREEN + LUTs A 60 FPS)
// ============================================================================
function renderCanvasFrame() {
  const canvas = document.getElementById("skyCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // Modo Universo Observable 360° (Proyección Elíptica Galáctica Aitoff Rotable o Globo 3D)
  if (STATE.mode === "allsky") {
    if (STATE.allskyEngine !== "aladin_hips") {
      renderAllskyPanorama(canvas, ctx);
    }
    return;
  }

  if (!STATE.decodedEpochs.length || !STATE.cube) return;
  const ep = STATE.decodedEpochs[STATE.currentEpochIdx] || STATE.decodedEpochs[0];
  const firstEp = STATE.decodedEpochs[0];
  const lastEp = STATE.decodedEpochs[STATE.decodedEpochs.length - 1];
  const { nx, ny } = ep;

  // Verificar si el frame rasterizado ya está en caché (evita recalcular píxeles durante Pan/Zoom/Hover)
  const chkFlags = document.getElementById("chkFlags").checked;
  const frameKey = `${STATE.mode}_${STATE.currentEpochIdx}_${STATE.cmap}_${STATE.stretch}_${STATE.contrast}_${chkFlags}_${STATE.splitPct}_${STATE.cubeStamp}`;

  if (STATE.cachedFrameKey !== frameKey || !STATE.cachedOffCanvas) {
    const offCanvas = document.createElement("canvas");
    offCanvas.width = nx;
    offCanvas.height = ny;
    const offCtx = offCanvas.getContext("2d");
    const imgData = offCtx.createImageData(nx, ny);
    const data = imgData.data;

    const stats = STATE.cube.stats;
    const span = (stats.p995 - stats.p05) / STATE.contrast;
    const lo = stats.p05;
    const hi = Math.max(lo + 1e-4, lo + span);
    const invRange = 1.0 / (hi - lo);

    const skyMed = stats.sky_med !== undefined ? stats.sky_med : stats.p50;
    const skySigma = stats.sky_sigma !== undefined ? stats.sky_sigma : Math.max((stats.p95 - stats.p05) * 0.12, 0.01);
    const zLo = skyMed - 1.4 * skySigma;
    const zHi = Math.max(zLo + 1e-4, stats.p995 / Math.max(STATE.contrast * 0.75, 0.35));
    const invZRange = 1.0 / (zHi - zLo);

    const midIdx = Math.floor((STATE.decodedEpochs.length - 1) / 2);
    const midEp = STATE.decodedEpochs[midIdx] || ep;

    let sumArr = null;
    if (STATE.mode === "sum") {
      sumArr = new Float32Array(nx * ny);
      const invLen = 1.0 / STATE.decodedEpochs.length;
      for (const e of STATE.decodedEpochs) {
        const fa = e.floatArr;
        for (let i = 0; i < fa.length; i++) sumArr[i] += fa[i];
      }
      for (let i = 0; i < sumArr.length; i++) sumArr[i] *= invLen;
    }

    const diffMax = Math.max(Math.abs(stats.p95 - stats.p05) * (0.95 / STATE.contrast), 0.12);
    const invDiffMax = 1.0 / diffMax;
    const lut = COLORMAP_LUTS[STATE.cmap] || COLORMAP_LUTS.inferno;
    const splitCol = Math.floor((STATE.splitPct / 100) * nx);

    for (let gy = 0; gy < ny; gy++) {
      const cy = ny - 1 - gy; // Norte arriba
      const rowOffG = gy * nx;
      const rowOffC = cy * nx;
      for (let gx = 0; gx < nx; gx++) {
        const gIdx = rowOffG + gx;
        const cIdx = (rowOffC + gx) * 4;

        let r = 0,
          g = 0,
          b = 0;

        if (STATE.mode === "rgb") {
          const vB = applyStretchFast((firstEp.floatArr[gIdx] - zLo) * invZRange, "zscale");
          const vG = applyStretchFast((midEp.floatArr[gIdx] - zLo) * invZRange, "zscale");
          const vR = applyStretchFast((lastEp.floatArr[gIdx] - zLo) * invZRange, "zscale");
          r = Math.min(255, Math.max(0, Math.round(vR * 255)));
          g = Math.min(255, Math.max(0, Math.round(vG * 255)));
          b = Math.min(255, Math.max(0, Math.round(vB * 255)));
        } else if (STATE.mode === "diff") {
          const dv = ep.floatArr[gIdx] - firstEp.floatArr[gIdx];
          const norm = Math.max(-1, Math.min(1, dv * invDiffMax));
          if (norm >= 0) {
            const s = Math.pow(norm, 0.72);
            r = 255;
            g = Math.round(235 * (1 - s * 0.78));
            b = Math.round(235 * (1 - s));
          } else {
            const s = Math.pow(-norm, 0.72);
            r = Math.round(235 * (1 - s));
            g = Math.round(235 * (1 - s * 0.65));
            b = 255;
          }
        } else {
          let val = ep.floatArr[gIdx];
          if (STATE.mode === "sum") {
            val = sumArr[gIdx];
          } else if (STATE.mode === "split") {
            val = gx < splitCol ? firstEp.floatArr[gIdx] : ep.floatArr[gIdx];
          }
          const norm = STATE.stretch === "zscale" ? (val - zLo) * invZRange : (val - lo) * invRange;
          const s = applyStretchFast(norm, STATE.stretch);
          const lutIdx = Math.min(LUT_SIZE - 1, Math.max(0, Math.round(s * (LUT_SIZE - 1)))) * 3;
          r = lut[lutIdx];
          g = lut[lutIdx + 1];
          b = lut[lutIdx + 2];
        }

        if (ep.cov && ep.cov[gIdx] < 128 && STATE.mode !== "diff") {
          // Sin datos L2b reales en este píxel: se muestra atenuado y con tinte gris (no es cielo medido)
          r = Math.round(r * 0.3 + 40);
          g = Math.round(g * 0.3 + 40);
          b = Math.round(b * 0.3 + 46);
        } else if (STATE.mode === "diff" && ((ep.cov && ep.cov[gIdx] < 128) || (firstEp.cov && firstEp.cov[gIdx] < 128))) {
          r = 46;
          g = 46;
          b = 52;
        }
        if (chkFlags) {
          const flg = ep.intFlags[gIdx];
          // Banderas oficiales que invalidan el píxel: TRANSIENT, SUR_ERROR, NONFUNC, HOT, COLD, NONLINEAR, PERSIST, STREAK, BLOOM, SNOWBALL, HALO, SATELLITE_HALO
          if (flg & ((1 << 0) | (1 << 2) | (1 << 6) | (1 << 10) | (1 << 11) | (1 << 15) | (1 << 17) | (1 << 25) | (1 << 26) | (1 << 27) | (1 << 28) | (1 << 29))) {
            r = Math.min(255, Math.round(r * 0.45 + 255 * 0.55));
            g = Math.round(g * 0.35);
            b = Math.min(255, Math.round(b * 0.45 + 140 * 0.55));
          }
        }

        data[cIdx] = r;
        data[cIdx + 1] = g;
        data[cIdx + 2] = b;
        data[cIdx + 3] = 255;
      }
    }

    offCtx.putImageData(imgData, 0, 0);
    STATE.cachedOffCanvas = offCanvas;
    STATE.cachedFrameKey = frameKey;
  }

  const geom = skyGeom(canvas);
  ctx.save();
  drawContinuousSkyBackdrop(ctx, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = STATE.smoothImage;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(
    STATE.cachedOffCanvas,
    0,
    0,
    nx,
    ny,
    geom.ox + STATE.viewPanX,
    geom.oy + STATE.viewPanY,
    geom.S * STATE.viewZoom,
    geom.S * STATE.viewZoom
  );
  ctx.restore();

  drawVectorOverlays(ctx, canvas.width, canvas.height, nx, ny, ep);
  updateHudOverlays(ep);
  updateFlagsInspector(ep);
}

// Fondo celeste continuo anclado a WCS usando el Mapa All-Sky Oficial SPHEREx DR1 de NASA/IPAC IRSA
function drawContinuousSkyBackdrop(ctx, cw, ch) {
  const lut = COLORMAP_LUTS[STATE.cmap] || COLORMAP_LUTS.inferno;
  const bgIdx = 42 * 3;
  const rBg = lut[bgIdx];
  const gBg = lut[bgIdx + 1];
  const bBg = lut[bgIdx + 2];
  ctx.fillStyle = `rgb(${rBg}, ${gBg}, ${bBg})`;
  ctx.fillRect(0, 0, cw, ch);

  if (!STATE.cube || !STATE.cube.wcs) return;
  if (
    STATE.viewPanX <= 0 &&
    STATE.viewPanY <= 0 &&
    STATE.viewPanX + cw * STATE.viewZoom >= cw &&
    STATE.viewPanY + ch * STATE.viewZoom >= ch
  ) {
    return;
  }

  // Mientras se transmite el nuevo recorte Npix_cube.fits durante el arrastre, muestrear el mapa oficial SPHEREx DR1
  const dr1Map = ensureOfficialAllskyMapLoaded(STATE.allskySurvey);
  if (!dr1Map || !dr1Map.data) return;

  const step = 8;
  const srcW = dr1Map.width;
  const srcH = dr1Map.height;
  const srcData = dr1Map.data;

  for (let py = 0; py < ch; py += step) {
    for (let px = 0; px < cw; px += step) {
      // Saltar región ya cubierta por el cubo de alta resolución
      if (
        px >= STATE.viewPanX &&
        px + step <= STATE.viewPanX + cw * STATE.viewZoom &&
        py >= STATE.viewPanY &&
        py + step <= STATE.viewPanY + ch * STATE.viewZoom
      ) {
        continue;
      }
      const { gx, gy } = canvasToGrid(px + step * 0.5, py + step * 0.5);
      const { ra, dec } = pixelToWorld(gx, gy);
      const raNorm = ((ra % 360.0) + 360.0) % 360.0;
      const decClamp = Math.max(-89.95, Math.min(89.95, dec));
      const col = Math.min(srcW - 1, Math.max(0, Math.floor((raNorm / 360.0) * srcW)));
      const row = Math.min(srcH - 1, Math.max(0, Math.floor(((90.0 - decClamp) / 180.0) * srcH)));
      const idx = (row * srcW + col) * 4;
      const lum = Math.min(255, Math.max(0, srcData[idx]));
      const lutIdx = Math.min(LUT_SIZE - 1, Math.max(0, Math.round((lum / 255.0) * (LUT_SIZE - 1)))) * 3;
      ctx.fillStyle = `rgb(${lut[lutIdx]}, ${lut[lutIdx + 1]}, ${lut[lutIdx + 2]})`;
      ctx.fillRect(px, py, step, step);
    }
  }
}

// ============================================================================
// 9. VISOR DEL UNIVERSO OBSERVABLE 360° (CUBO ALL-SKY OFICIAL SPHEREx DR1 · DOI: 10.26131/IRSA679)
// ============================================================================
function viewVecToIcrsCartesian(x3, y3, z3) {
  const gamma = (STATE.allskyRoll || 0.0) * DEG2RAD;
  const cosG = Math.cos(gamma);
  const sinG = Math.sin(gamma);
  const x2 = x3;
  const y2 = y3 * cosG + z3 * sinG;
  const z2 = -y3 * sinG + z3 * cosG;

  const beta = STATE.allskyRotLat * DEG2RAD;
  const cosB = Math.cos(beta);
  const sinB = Math.sin(beta);
  const x1 = x2 * cosB - z2 * sinB;
  const y1 = y2;
  const z1 = x2 * sinB + z2 * cosB;

  const alpha = STATE.allskyRotLon * DEG2RAD;
  const cosA = Math.cos(alpha);
  const sinA = Math.sin(alpha);
  const xf = x1 * cosA - y1 * sinA;
  const yf = x1 * sinA + y1 * cosA;
  const zf = z1;

  if (STATE.allskyFrame === "equatorial") {
    return { x: xf, y: yf, z: zf };
  }
  if (STATE.allskyFrame === "ecliptic") {
    return {
      x: xf,
      y: yf * COS_EPS - zf * SIN_EPS,
      z: yf * SIN_EPS + zf * COS_EPS,
    };
  }
  // Marco Galáctico (l, b) -> Ecuatorial ICRS (RA, Dec) mediante la transpuesta de R_ICRS_TO_GAL
  return {
    x: R_ICRS_TO_GAL[0][0] * xf + R_ICRS_TO_GAL[1][0] * yf + R_ICRS_TO_GAL[2][0] * zf,
    y: R_ICRS_TO_GAL[0][1] * xf + R_ICRS_TO_GAL[1][1] * yf + R_ICRS_TO_GAL[2][1] * zf,
    z: R_ICRS_TO_GAL[0][2] * xf + R_ICRS_TO_GAL[1][2] * yf + R_ICRS_TO_GAL[2][2] * zf,
  };
}

function renderAllskyPanorama(canvas, ctx) {
  const W = canvas.width;
  const H = canvas.height;
  ctx.save();

  // Fondo del espacio profundo
  const bg = ctx.createRadialGradient(W * 0.5, H * 0.5, 20, W * 0.5, H * 0.5, W * 0.72);
  bg.addColorStop(0, "#0b1329");
  bg.addColorStop(0.55, "#050914");
  bg.addColorStop(1, "#020307");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  const { cx, cy, rx, ry, isGlobe } = allskyGeom(W, H);

  // Proyección unificada con rotación 3D SO(3) isótropa
  const projectPt = (lonDeg, latDeg) => {
    if (isGlobe) {
      const rot = rotateSpherical3D(lonDeg, latDeg, STATE.allskyRotLon, STATE.allskyRotLat, STATE.allskyRoll);
      if (rot.x3 < 0) return { x: cx, y: cy, visible: false };
      return {
        x: cx - rot.y3 * rx,
        y: cy - rot.z3 * ry,
        visible: true,
        dl: rot.dl,
        bRot: rot.bRot,
      };
    }
    return projectHammerAitoff(lonDeg, latDeg, STATE.allskyRotLon, STATE.allskyRotLat, cx, cy, rx, ry);
  };

  // Recorte elíptico / esférico del Universo Observable 360°
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.clip();

  // Cargar y proyectar píxel a píxel el Cubo All-Sky Oficial SPHEREx DR1 de NASA/IPAC IRSA (ivo://IPAC/P/SPHEREx/DR1/cube)
  const chKey = resolveDr1ChannelKey(STATE.allskySurvey);
  const dr1Map = ensureOfficialAllskyMapLoaded(chKey);

  if (dr1Map && dr1Map.data) {
    const projKey = `${chKey}_${STATE.allskyEngine}_${STATE.allskyFrame}_${STATE.allskyRotLon.toFixed(1)}_${STATE.allskyRotLat.toFixed(1)}_${STATE.allskyRoll.toFixed(1)}_${STATE.cmap}_${STATE.contrast.toFixed(1)}`;
    if (STATE.cachedAllskyProjKey !== projKey || !STATE.cachedAllskyProjCanvas) {
      const rw = isGlobe ? 380 : 480;
      const rh = isGlobe ? 380 : 310;
      if (!STATE.cachedAllskyProjCanvas) {
        STATE.cachedAllskyProjCanvas = document.createElement("canvas");
      }
      const pCan = STATE.cachedAllskyProjCanvas;
      pCan.width = rw;
      pCan.height = rh;
      const pCtx = pCan.getContext("2d");
      const pImg = pCtx.createImageData(rw, rh);
      const dst = pImg.data;

      const srcW = dr1Map.width;
      const srcH = dr1Map.height;
      const src = dr1Map.data;
      const isRgb = dr1Map.isRgb;
      const lut = COLORMAP_LUTS[STATE.cmap] || COLORMAP_LUTS.inferno;
      const cGain = Math.max(0.5, Math.min(2.2, STATE.contrast));

      // Columnas de la matriz ortogonal 3×3 M ∈ SO(3) (Espacio de Vista -> Ecuatorial ICRS)
      const c0 = viewVecToIcrsCartesian(1, 0, 0);
      const c1 = viewVecToIcrsCartesian(0, 1, 0);
      const c2 = viewVecToIcrsCartesian(0, 0, 1);

      const invHalfW = 2.0 / rw;
      const invHalfH = 2.0 / rh;
      const SQRT2 = 1.41421356237;
      const INV_SQRT2 = 0.70710678118;
      const INV_TWO_PI = 1.0 / (2.0 * Math.PI);
      const INV_PI = 1.0 / Math.PI;

      for (let py = 0; py < rh; py++) {
        const vNorm = 1.0 - (py + 0.5) * invHalfH;
        const vNorm2 = vNorm * vNorm;
        const rowOff = py * rw * 4;

        for (let px = 0; px < rw; px++) {
          const u = (px + 0.5) * invHalfW - 1.0;
          const r2 = u * u + vNorm2;
          if (r2 > 1.0) continue;

          let x3 = 0,
            y3 = 0,
            z3 = 0;

          if (isGlobe) {
            x3 = Math.sqrt(Math.max(0.0, 1.0 - r2));
            y3 = -u;
            z3 = vNorm;
          } else {
            const v = vNorm * INV_SQRT2;
            const z = Math.sqrt(Math.max(0.0, 1.0 - 0.5 * u * u - 0.5 * v * v));
            z3 = Math.max(-1.0, Math.min(1.0, SQRT2 * z * v));
            const cosPhi = Math.sqrt(Math.max(0.0, 1.0 - z3 * z3));
            const A = 2.0 * z * z - 1.0;
            const B = SQRT2 * z * u;
            const denom2 = A * A + B * B;
            if (denom2 > 1e-12) {
              const cosDl = (A * A - B * B) / denom2;
              const sinDl = (-2.0 * A * B) / denom2;
              x3 = cosPhi * cosDl;
              y3 = cosPhi * sinDl;
            } else {
              x3 = -cosPhi;
              y3 = 0.0;
            }
          }

          // Multiplicación matricial directa O(1) hacia coordenadas cartesianas ICRS (RA, Dec)
          const xEq = c0.x * x3 + c1.x * y3 + c2.x * z3;
          const yEq = c0.y * x3 + c1.y * y3 + c2.y * z3;
          const zEq = Math.max(-1.0, Math.min(1.0, c0.z * x3 + c1.z * y3 + c2.z * z3));

          let raRad = Math.atan2(yEq, xEq);
          if (raRad < 0.0) raRad += 2.0 * Math.PI;
          const decRad = Math.asin(zEq);

          const sCol = Math.min(srcW - 1, Math.max(0, (raRad * INV_TWO_PI * srcW) | 0));
          const sRow = Math.min(srcH - 1, Math.max(0, ((0.5 * Math.PI - decRad) * INV_PI * srcH) | 0));
          const sIdx = (sRow * srcW + sCol) * 4;
          const dIdx = rowOff + px * 4;

          if (isRgb) {
            dst[dIdx] = Math.min(255, Math.round(src[sIdx] * cGain));
            dst[dIdx + 1] = Math.min(255, Math.round(src[sIdx + 1] * cGain));
            dst[dIdx + 2] = Math.min(255, Math.round(src[sIdx + 2] * cGain));
            dst[dIdx + 3] = 255;
          } else {
            const norm = Math.min(1.0, (src[sIdx] / 255.0) * cGain);
            const lutIdx = Math.min(LUT_SIZE - 1, Math.max(0, (norm * (LUT_SIZE - 1)) | 0)) * 3;
            dst[dIdx] = lut[lutIdx];
            dst[dIdx + 1] = lut[lutIdx + 1];
            dst[dIdx + 2] = lut[lutIdx + 2];
            dst[dIdx + 3] = 255;
          }
        }
      }

      pCtx.putImageData(pImg, 0, 0);
      STATE.cachedAllskyProjKey = projKey;
    }

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(STATE.cachedAllskyProjCanvas, cx - rx, cy - ry, rx * 2, ry * 2);
  } else {
    // Mientras termina la primera descarga desde el backend
    ctx.fillStyle = "#060d1f";
    ctx.fillRect(cx - rx, cy - ry, rx * 2, ry * 2);
  }

  // Grilla de Coordenadas Esféricas (Paralelos cada 30° y Meridianos cada 30°) con corte limpio en la costura ±180°
  ctx.strokeStyle = "rgba(56, 189, 248, 0.24)";
  ctx.lineWidth = 1;
  for (let bLat = -60; bLat <= 60; bLat += 30) {
    ctx.beginPath();
    let prevPt = null;
    for (let lLon = 0; lLon <= 360; lLon += 4) {
      const pt = projectPt(lLon % 360, bLat);
      if (!pt.visible) {
        prevPt = null;
        continue;
      }
      if (!prevPt || Math.hypot(pt.x - prevPt.x, pt.y - prevPt.y) > rx * 0.35) {
        ctx.moveTo(pt.x, pt.y);
      } else {
        ctx.lineTo(pt.x, pt.y);
      }
      prevPt = pt;
    }
    ctx.stroke();
  }

  const lonPrefix = STATE.allskyFrame === "galactic" ? "l" : STATE.allskyFrame === "ecliptic" ? "λ" : "RA";
  for (let lMer = 0; lMer < 360; lMer += 30) {
    ctx.beginPath();
    let prevPt = null;
    for (let bLat = -88; bLat <= 88; bLat += 4) {
      const pt = projectPt(lMer, bLat);
      if (!pt.visible) {
        prevPt = null;
        continue;
      }
      if (!prevPt || Math.hypot(pt.x - prevPt.x, pt.y - prevPt.y) > rx * 0.35) {
        ctx.moveTo(pt.x, pt.y);
      } else {
        ctx.lineTo(pt.x, pt.y);
      }
      prevPt = pt;
    }
    ctx.stroke();
    const eqPt = projectPt(lMer, 0);
    if (eqPt.visible && Math.abs(eqPt.dl) < 160) {
      ctx.fillStyle = "rgba(226, 232, 240, 0.82)";
      ctx.font = "600 10px 'JetBrains Mono', monospace";
      ctx.fillText(`${lonPrefix}=${lMer}°`, eqPt.x - 16, eqPt.y - 5);
    }
  }

  // Curva del Plano Eclíptico (β = 0° · Plano del Sistema Solar y búsqueda de Planeta X)
  ctx.save();
  ctx.strokeStyle = "rgba(250, 204, 21, 0.65)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  let prevEcl = null;
  for (let lamEcl = 0; lamEcl <= 360; lamEcl += 3) {
    const eqE = eclipticToEq(lamEcl, 0);
    const frmE = eqToActiveFrame(eqE.ra, eqE.dec);
    const pt = projectPt(frmE.lon, frmE.lat);
    if (!pt.visible) {
      prevEcl = null;
      continue;
    }
    if (!prevEcl || Math.hypot(pt.x - prevEcl.x, pt.y - prevEcl.y) > rx * 0.35) {
      ctx.moveTo(pt.x, pt.y);
    } else {
      ctx.lineTo(pt.x, pt.y);
    }
    prevEcl = pt;
  }
  ctx.stroke();
  ctx.restore();

  // Dibujar Efemérides y Regiones de Referencia Observacional (Sgr A*, Campos Profundos NEP y SEP de SPHEREx, etc.)
  (STATE.landmarks || []).forEach((lm) => {
    const frm = eqToActiveFrame(lm.ra, lm.dec);
    const pt = projectPt(frm.lon, frm.lat);
    if (!pt.visible) return;
    const isHover = STATE.hoverTargetId === lm.id;
    ctx.strokeStyle = isHover ? "#00f5d4" : "rgba(56, 189, 248, 0.78)";
    ctx.fillStyle = isHover ? "rgba(0, 245, 212, 0.28)" : "rgba(6, 12, 26, 0.65)";
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, isHover ? 9 : 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = isHover ? "#00f5d4" : "#bae6fd";
    ctx.font = "600 9.5px 'JetBrains Mono', monospace";
    const shortName = lm.name.split("(")[0].trim();
    ctx.fillText(shortName, pt.x + 8, pt.y + 3);
  });

  // Marcadores interactivos de todos los Objetivos de Referencia SPHEREx
  STATE.targets
    .filter((t) => !t.is_allsky)
    .forEach((t) => {
      const frm = eqToActiveFrame(t.ra, t.dec);
      const pt = projectPt(frm.lon, frm.lat);
      if (!pt.visible) return;
      const isHover = STATE.hoverTargetId === t.id;
      const isCurrent = Math.hypot(t.ra - STATE.ra, t.dec - STATE.dec) < 0.25;

      // Halo pulsante
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, isHover ? 15 : 10, 0, Math.PI * 2);
      ctx.fillStyle = isHover
        ? "rgba(0, 245, 212, 0.3)"
        : isCurrent
        ? "rgba(250, 204, 21, 0.24)"
        : "rgba(56, 189, 248, 0.16)";
      ctx.fill();

      // Punto central
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, isHover ? 6.5 : 5, 0, Math.PI * 2);
      ctx.fillStyle = isCurrent ? "#facc15" : "#00f5d4";
      ctx.fill();
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = "#040814";
      ctx.stroke();

      // Etiqueta
      ctx.font = "600 11px 'Inter', sans-serif";
      const lbl = t.name;
      const tw = ctx.measureText(lbl).width;
      const lx = Math.min(Math.max(pt.x + 10, 14), W - tw - 22);
      const ly = Math.min(Math.max(pt.y - 9, 64), H - 54);
      ctx.fillStyle = "rgba(6, 11, 23, 0.88)";
      ctx.fillRect(lx - 4, ly - 11, tw + 10, 16);
      ctx.strokeStyle = isCurrent ? "rgba(250, 204, 21, 0.7)" : "rgba(0, 245, 212, 0.55)";
      ctx.lineWidth = 1;
      ctx.strokeRect(lx - 4, ly - 11, tw + 10, 16);
      ctx.fillStyle = isCurrent ? "#fef08a" : "#e0f2fe";
      ctx.fillText(lbl, lx + 1, ly + 1);
    });

  ctx.restore();

  // Contorno exterior brillante de la elipse 360° estilo IRSA
  ctx.strokeStyle = "rgba(56, 189, 248, 0.72)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.stroke();

  // Indicador de orientación isótropa 3D y fuente oficial NASA/IPAC IRSA SPHEREx DR1
  ctx.fillStyle = "#93c5fd";
  ctx.font = "700 10.5px 'JetBrains Mono', monospace";
  const frameTag =
    STATE.allskyFrame === "galactic"
      ? "GALACTIC PLANE (l, b)"
      : STATE.allskyFrame === "ecliptic"
      ? "ECLIPTIC PLANE (λ, β)"
      : "ICRS EQUATORIAL (RA, Dec)";
  const orientTxt = `NASA/IPAC IRSA SPHEREx DR1 (ivo://IPAC/P/SPHEREx/DR1/cube) · ${frameTag} · Lon₀=${STATE.allskyRotLon.toFixed(1)}° · Lat₀=${STATE.allskyRotLat >= 0 ? "+" : ""}${STATE.allskyRotLat.toFixed(1)}°`;
  ctx.fillText(orientTxt, Math.max(18, cx - 285), Math.min(H - 42, cy + ry + 16));

  // Mini-ventana Picture-in-Picture (abajo a la izquierda) con la vista previa del cubo SPHEREx activo
  if (STATE.decodedEpochs.length > 0 && STATE.cube) {
    const pipW = 136;
    const pipH = 136;
    const pipX = 14;
    const pipY = H - pipH - 76;

    ctx.fillStyle = "rgba(6, 10, 22, 0.92)";
    ctx.fillRect(pipX - 4, pipY - 22, pipW + 8, pipH + 26);
    ctx.strokeStyle = "rgba(56, 189, 248, 0.6)";
    ctx.lineWidth = 1.2;
    ctx.strokeRect(pipX - 4, pipY - 22, pipW + 8, pipH + 26);

    ctx.fillStyle = "#7dd3fc";
    ctx.font = "600 10px 'JetBrains Mono', monospace";
    const pipTitle =
      STATE.lang === "en" ? "Active SPHEREx FITS (Click):" : "Cubo FITS Activo (Clic):";
    ctx.fillText(pipTitle, pipX, pipY - 7);

    if (STATE.cachedOffCanvas) {
      ctx.drawImage(STATE.cachedOffCanvas, pipX, pipY, pipW, pipH);
    }
  }

  ctx.restore();
}

// ============================================================================
// 10. TRANSFORMACIONES SUB-PÍXEL, RECONOCEDOR DE ASTROS Y REGLA DE DISTANCIA 3D
// ============================================================================
function gridToCanvas(gx, gy) {
  const { S, ox, oy } = skyGeom();
  const [ny, nx] = STATE.cube ? STATE.cube.shape : [78, 78];
  const baseX = ((gx + 0.5) / nx) * S;
  const baseY = ((ny - 1 - gy + 0.5) / ny) * S;
  return {
    cx: ox + STATE.viewPanX + baseX * STATE.viewZoom,
    cy: oy + STATE.viewPanY + baseY * STATE.viewZoom,
  };
}

function canvasToGrid(cx, cy) {
  const { S, ox, oy } = skyGeom();
  const [ny, nx] = STATE.cube ? STATE.cube.shape : [78, 78];
  const baseX = (cx - ox - STATE.viewPanX) / STATE.viewZoom;
  const baseY = (cy - oy - STATE.viewPanY) / STATE.viewZoom;
  const gx = Math.floor((baseX / S) * nx);
  const gy = ny - 1 - Math.floor((baseY / S) * ny);
  return {
    gx: Math.max(0, Math.min(nx - 1, gx)),
    gy: Math.max(0, Math.min(ny - 1, gy)),
  };
}

function pixelToWorld(gx, gy) {
  if (!STATE.cube || !STATE.cube.wcs) return { ra: STATE.ra, dec: STATE.dec };
  return tanPixelToWorld(gx, gy, STATE.cube.wcs);
}

function formatCosmicDistance(distPc, distLy) {
  if (!Number.isFinite(distPc)) return "";
  if (distPc >= 1000) {
    return `${(distPc / 1000).toFixed(2)} kpc (${(distLy / 1000).toFixed(1)} kly)`;
  }
  return `${distPc.toFixed(1)} pc (${distLy.toFixed(1)} ly)`;
}

function computePairTelemetry3D(ptA, ptB) {
  if (!ptA || !ptB) return null;
  const ra1 = ptA.ra * DEG2RAD;
  const dec1 = ptA.dec * DEG2RAD;
  const ra2 = ptB.ra * DEG2RAD;
  const dec2 = ptB.dec * DEG2RAD;
  // Separación angular (haversine) y ángulo de posición (Norte = 0°, Este = 90°)
  const dRa = ra2 - ra1;
  const dDec = dec2 - dec1;
  const aHav = Math.pow(Math.sin(dDec * 0.5), 2) + Math.cos(dec1) * Math.cos(dec2) * Math.pow(Math.sin(dRa * 0.5), 2);
  const thetaRad = 2.0 * Math.asin(Math.min(1.0, Math.sqrt(Math.max(0.0, aHav))));
  const yPa = Math.sin(dRa) * Math.cos(dec2);
  const xPa = Math.cos(dec1) * Math.sin(dec2) - Math.sin(dec1) * Math.cos(dec2) * Math.cos(dRa);
  const paDeg = ((Math.atan2(yPa, xPa) * RAD2DEG) % 360.0 + 360.0) % 360.0;
  const out = {
    thetaDeg: thetaRad * RAD2DEG,
    thetaArcmin: thetaRad * RAD2DEG * 60.0,
    thetaArcsec: thetaRad * RAD2DEG * 3600.0,
    paDeg,
    dA_pc: Number.isFinite(Number(ptA.dist_pc)) && ptA.dist_pc ? Number(ptA.dist_pc) : null,
    dB_pc: Number.isFinite(Number(ptB.dist_pc)) && ptB.dist_pc ? Number(ptB.dist_pc) : null,
    projPc: null,
    projAu: null,
    dist3dPc: null,
    dist3dLy: null,
    dist3dAu: null,
  };
  // La distancia 3D solo se calcula si AMBOS objetos tienen distancia medida (paralaje o literatura)
  if (out.dA_pc !== null && out.dB_pc !== null) {
    const dA = out.dA_pc;
    const dB = out.dB_pc;
    out.dist3dPc = Math.sqrt(Math.max(0.0, dA * dA + dB * dB - 2.0 * dA * dB * Math.cos(thetaRad)));
    out.dist3dLy = out.dist3dPc * 3.26156;
    out.dist3dAu = out.dist3dPc * 206264.8;
    out.projPc = 0.5 * (dA + dB) * Math.sin(thetaRad);
    out.projAu = out.projPc * 206264.8;
  }
  return out;
}

function drawVectorOverlays(ctx, cw, ch, nx, ny, ep) {
  const scaleX = (skyGeom().S / nx) * STATE.viewZoom;
  const scaleY = (skyGeom().S / ny) * STATE.viewZoom;

  // 1. Grilla WCS y Brújula N/E
  const sg = skyGeom();
  if (document.getElementById("chkGrid").checked) {
    ctx.save();
    ctx.strokeStyle = "rgba(148, 163, 184, 0.16)";
    ctx.lineWidth = 1;
    for (let f = 0.2; f < 0.9; f += 0.2) {
      ctx.beginPath();
      ctx.moveTo(sg.ox + sg.S * f, sg.oy);
      ctx.lineTo(sg.ox + sg.S * f, sg.oy + sg.S);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(sg.ox, sg.oy + sg.S * f);
      ctx.lineTo(sg.ox + sg.S, sg.oy + sg.S * f);
      ctx.stroke();
    }

    // Brújula astronómica (Norte arriba, Este a la izquierda)
    const bx = sg.ox + sg.S - 48;
    const by = sg.oy + sg.S - 58;
    ctx.strokeStyle = "#38bdf8";
    ctx.fillStyle = "#38bdf8";
    ctx.lineWidth = 1.8;
    ctx.font = "600 11px 'JetBrains Mono', monospace";
    ctx.beginPath();
    ctx.moveTo(bx, by);
    ctx.lineTo(bx, by - 28);
    ctx.moveTo(bx, by);
    ctx.lineTo(bx - 28, by);
    ctx.stroke();
    ctx.fillText("N", bx - 4, by - 33);
    ctx.fillText("E", bx - 40, by + 4);
    ctx.restore();
  }

  // 2. Cortina divisoria A/B
  if (STATE.mode === "split") {
    const sx = (STATE.splitPct / 100) * cw;
    ctx.save();
    ctx.strokeStyle = "#00f5d4";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(sx, 0);
    ctx.lineTo(sx, ch);
    ctx.stroke();
    ctx.restore();
  }

  // 3. Fuentes Infrarrojas AllWISE (Rombo Ámbar)
  if (false /* capa AllWISE retirada de la interfaz */ && STATE.catalogs.allwise) {
    ctx.save();
    ctx.strokeStyle = "rgba(255, 190, 11, 0.85)";
    ctx.lineWidth = 1.4;
    for (const w of STATE.catalogs.allwise) {
      if (w.px < 0 || w.px >= nx || w.py < 0 || w.py >= ny) continue;
      const { cx, cy } = gridToCanvas(w.px, w.py);
      const r = 6;
      ctx.beginPath();
      ctx.moveTo(cx, cy - r);
      ctx.lineTo(cx + r, cy);
      ctx.lineTo(cx, cy + r);
      ctx.lineTo(cx - r, cy);
      ctx.closePath();
      ctx.stroke();
    }
    ctx.restore();
  }

  // 4. Estrellas Gaia DR3 + Vectores de Movimiento Propio
  if (document.getElementById("chkGaia").checked && STATE.catalogs.gaia) {
    ctx.save();
    for (const g of STATE.catalogs.gaia) {
      if (g.px < 0 || g.px >= nx || g.py < 0 || g.py >= ny) continue;
      const { cx, cy } = gridToCanvas(g.px, g.py);
      ctx.strokeStyle = "rgba(56, 189, 248, 0.9)";
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(cx, cy, 4.5, 0, Math.PI * 2);
      ctx.stroke();

      const { cx: fx, cy: fy } = gridToCanvas(g.px_10yr, g.py_10yr);
      const dist = Math.hypot(fx - cx, fy - cy);
      if (dist > 3.5) {
        ctx.strokeStyle = "#00f5d4";
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(fx, fy);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // Registro de cajas de texto dibujadas para evitar colisiones entre etiquetas
  const placedBoxes = [];
  const placeNonOverlappingBox = (prefX, prefY, w, h) => {
    const offsets = [
      [0, 0],
      [0, 24],
      [0, -22],
      [18, 12],
      [-18, -14],
      [0, 42],
    ];
    for (const [ox, oy] of offsets) {
      const tx = Math.min(Math.max(prefX + ox, 6), cw - w - 8);
      const ty = Math.min(Math.max(prefY + oy, 48), ch - h - 42);
      const collides = placedBoxes.some(
        (b) => !(tx + w < b.x - 3 || tx > b.x + b.w + 3 || ty + h < b.y - 2 || ty > b.y + b.h + 2)
      );
      if (!collides) {
        placedBoxes.push({ x: tx, y: ty, w, h });
        return { tx, ty };
      }
    }
    const tx = Math.min(Math.max(prefX, 6), cw - w - 8);
    const ty = Math.min(Math.max(prefY, 48), ch - h - 42);
    placedBoxes.push({ x: tx, y: ty, w, h });
    return { tx, ty };
  };

  // 5. Reconocedor Automático de Estrellas y Objetos Celestes (Nombre, Clasificación Espectral y Distancia al Telescopio)
  if (STATE.starRecognizerEnabled && STATE.cube && STATE.cube.recognized_objects) {
    ctx.save();
    const recObjs = STATE.cube.recognized_objects.slice(0, 9);
    for (const obj of recObjs) {
      const { cx, cy } = gridToCanvas(obj.px, obj.py);
      if (cx < -20 || cx > cw + 20 || cy < -20 || cy > ch + 20) continue;

      const col = obj.color || (obj.obj_class === "reference_target" ? "#38bdf8" : "#94a3b8");

      // Anillo astrométrico con marcadores laterales
      ctx.strokeStyle = col;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(cx, cy, 8.5, 0, Math.PI * 2);
      ctx.stroke();

      // Etiqueta solo para el objetivo de referencia o la fuente bajo el cursor (imagen limpia)
      const isHoverObj = STATE.hoverSourceKey === `${obj.px},${obj.py}`;
      if (obj.obj_class !== "reference_target" && !isHoverObj) continue;
      const spType = STATE.lang === "en" ? obj.spectral_type_en : obj.spectral_type_es;
      const shortClass = spType ? spType.split("(")[0].trim() : "";
      const distStr = obj.dist_pc ? ` · d=${formatCosmicDistance(obj.dist_pc, obj.dist_ly)}` : "";
      const labelLine = `✦ ${obj.name}${obj.obj_class === "reference_target" ? " · " + shortClass : ""}${distStr}`;

      ctx.font = "600 9.5px 'JetBrains Mono', monospace";
      const tw = ctx.measureText(labelLine).width;
      const { tx, ty } = placeNonOverlappingBox(cx + 11, cy - 8, tw + 10, 15);

      ctx.fillStyle = "rgba(4, 12, 24, 0.86)";
      ctx.fillRect(tx, ty, tw + 10, 15);
      ctx.strokeStyle = "rgba(56, 189, 248, 0.55)";
      ctx.lineWidth = 1;
      ctx.strokeRect(tx, ty, tw + 10, 15);
      ctx.fillStyle = "#e0f2fe";
      ctx.fillText(labelLine, tx + 5, ty + 11);
    }
    ctx.restore();
  }

  // 6. Detector Super-Inteligente de Anomalías IA + Candidatos
  const showCandidates = document.getElementById("chkCandidates").checked;
  if (
    (STATE.aiDetectorEnabled || showCandidates) &&
    STATE.cube &&
    STATE.cube.candidates
  ) {
    ctx.save();
    for (const c of STATE.cube.candidates) {
      const { cx, cy } = gridToCanvas(c.px, c.py);
      const isDipole = c.type === "dipole";
      const rejected = c.verification === "not_confirmed";
      const color = rejected ? "rgba(148, 163, 184, 0.75)" : isDipole ? "#00f5d4" : "#ffbe0b";

      if (isDipole && (c.px_old !== c.px || c.py_old !== c.py)) {
        const { cx: ox, cy: oy } = gridToCanvas(c.px_old, c.py_old);
        ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
        ctx.lineWidth = 2;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(ox, oy);
        ctx.lineTo(cx, cy);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.strokeStyle = "#38bdf8";
        ctx.beginPath();
        ctx.arc(ox, oy, 6, 0, Math.PI * 2);
        ctx.stroke();
      }

      if (STATE.aiDetectorEnabled) {
        const boxR = Math.max(14, 2.7 * scaleX);
        const corner = 6;
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(cx - boxR, cy - boxR + corner);
        ctx.lineTo(cx - boxR, cy - boxR);
        ctx.lineTo(cx - boxR + corner, cy - boxR);
        ctx.moveTo(cx + boxR - corner, cy - boxR);
        ctx.lineTo(cx + boxR, cy - boxR);
        ctx.lineTo(cx + boxR, cy - boxR + corner);
        ctx.moveTo(cx - boxR, cy + boxR - corner);
        ctx.lineTo(cx - boxR, cy + boxR);
        ctx.lineTo(cx - boxR + corner, cy + boxR);
        ctx.moveTo(cx + boxR - corner, cy + boxR);
        ctx.lineTo(cx + boxR, cy + boxR);
        ctx.lineTo(cx + boxR, cy + boxR - corner);
        ctx.stroke();

        const vLbl = STATE.lang === "en" ? c.label_en : c.label_es;
        const tagTxt = `#${c.rank} ${vLbl} · ${c.snr_diff}σ`;
        ctx.font = "700 10px 'JetBrains Mono', monospace";
        const tw = ctx.measureText(tagTxt).width;
        const { tx, ty } = placeNonOverlappingBox(cx - boxR, cy - boxR - 18, tw + 10, 15);
        ctx.fillStyle = "rgba(6, 10, 20, 0.9)";
        ctx.fillRect(tx, ty, tw + 10, 15);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.strokeRect(tx, ty, tw + 10, 15);
        ctx.fillStyle = color;
        ctx.fillText(tagTxt, tx + 5, ty + 11);
      } else {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, 11, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = color;
        ctx.font = "700 10.5px 'JetBrains Mono', monospace";
        ctx.fillText(`#${c.rank} (${c.snr_diff}σ)`, cx + 13, cy - 6);
      }
    }
    ctx.restore();
  }

  // 7. Regla de Distancia Cósmica 3D (Vector Láser A ↔ B en el Lienzo)

  // 7b. Posición predicha del objetivo en cada época (Gaia DR3 / literatura + movimiento propio)
  const track = (STATE.cube && STATE.cube.target && STATE.cube.target_track) || [];
  if (track.length) {
    ctx.save();
    if (track.length > 1) {
      ctx.strokeStyle = "rgba(244, 244, 245, 0.55)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      track.forEach((t, i) => {
        const { cx, cy } = gridToCanvas(t.px, t.py);
        if (i === 0) ctx.moveTo(cx, cy);
        else ctx.lineTo(cx, cy);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }
    track.forEach((t) => {
      const { cx, cy } = gridToCanvas(t.px, t.py);
      const isCur = t.epoch_index === STATE.currentEpochIdx;
      const arm = isCur ? 9 : 5;
      ctx.strokeStyle = isCur ? "#f4f4f5" : "rgba(244, 244, 245, 0.5)";
      ctx.lineWidth = isCur ? 1.6 : 1.0;
      ctx.beginPath();
      ctx.moveTo(cx - arm, cy);
      ctx.lineTo(cx - 3, cy);
      ctx.moveTo(cx + 3, cy);
      ctx.lineTo(cx + arm, cy);
      ctx.moveTo(cx, cy - arm);
      ctx.lineTo(cx, cy - 3);
      ctx.moveTo(cx, cy + 3);
      ctx.lineTo(cx, cy + arm);
      ctx.stroke();
    });
    const tCur = track.find((t) => t.epoch_index === STATE.currentEpochIdx) || track[0];
    if (tCur && STATE.cube.target) {
      const { cx, cy } = gridToCanvas(tCur.px, tCur.py);
      ctx.font = "600 10px 'JetBrains Mono', monospace";
      ctx.fillStyle = "#f4f4f5";
      const lbl = STATE.lang === "en" ? `predicted: ${STATE.cube.target.name}` : `predicha: ${STATE.cube.target.name}`;
      // Encima del marcador (la etiqueta de la fuente reconocida va debajo): sin solapamiento
      const tw = ctx.measureText(lbl).width;
      ctx.fillStyle = "rgba(9, 9, 11, 0.72)";
      ctx.fillRect(cx + 9, cy - 25, tw + 6, 14);
      ctx.fillStyle = "#f4f4f5";
      ctx.fillText(lbl, cx + 12, cy - 14);
    }
    ctx.restore();
  }

  // 8. Apertura Fotométrica Activa + Anillo de Fondo de Cielo (Retícula Corregida al Sub-Píxel)
  if (true /* apertura siempre visible */ && STATE.aperturePx) {
    const { cx: ax, cy: ay } = gridToCanvas(STATE.aperturePx.x, STATE.aperturePx.y);
    const apRadiusCanvas = 2.5 * ((scaleX + scaleY) / 2);
    const annRadiusCanvas = 6.5 * ((scaleX + scaleY) / 2);

    ctx.save();
    ctx.strokeStyle = "#f43f5e";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.arc(ax, ay, apRadiusCanvas, 0, Math.PI * 2);
    ctx.stroke();

    // Anillo de cielo local
    ctx.strokeStyle = "rgba(244, 63, 94, 0.45)";
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.arc(ax, ay, annRadiusCanvas, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Retícula de precisión (4 brazos completos con ctx.lineTo)
    ctx.strokeStyle = "#f43f5e";
    ctx.beginPath();
    ctx.moveTo(ax - apRadiusCanvas - 6, ay);
    ctx.lineTo(ax - apRadiusCanvas - 1, ay);
    ctx.moveTo(ax + apRadiusCanvas + 1, ay);
    ctx.lineTo(ax + apRadiusCanvas + 6, ay);
    ctx.moveTo(ax, ay - apRadiusCanvas - 6);
    ctx.lineTo(ax, ay - apRadiusCanvas - 1);
    ctx.moveTo(ax, ay + apRadiusCanvas + 1);
    ctx.lineTo(ax, ay + apRadiusCanvas + 6);
    ctx.stroke();
    ctx.restore();
  }
}

// ============================================================================
// 11. INTERACCIÓN CON EL CURSOR Y TELEMETRÍA EN TIEMPO REAL (SEXAGESIMAL + AB + DISTANCIA)
// ============================================================================
function handleCanvasHover(ev) {
  const canvas = document.getElementById("skyCanvas");
  const rect = canvas.getBoundingClientRect();
  const cx = (ev.clientX - rect.left) * (canvas.width / rect.width);
  const cy = (ev.clientY - rect.top) * (canvas.height / rect.height);

  if (STATE.mode === "allsky") {
    const W = canvas.width;
    const H = canvas.height;
    const { cx: centerX, cy: centerY, rx, ry, isGlobe } = allskyGeom(W, H);

    let foundHover = null;
    const allInteractives = [
      ...STATE.targets.filter((t) => !t.is_allsky),
      ...(STATE.landmarks || []),
    ];
    for (const t of allInteractives) {
      const frm = eqToActiveFrame(t.ra, t.dec);
      let pt = null;
      if (isGlobe) {
        const rot = rotateSpherical3D(frm.lon, frm.lat, STATE.allskyRotLon, STATE.allskyRotLat, STATE.allskyRoll);
        pt = rot.x3 >= 0 ? { x: centerX - rot.y3 * rx, y: centerY - rot.z3 * ry, visible: true } : { visible: false };
      } else {
        pt = projectHammerAitoff(
          frm.lon,
          frm.lat,
          STATE.allskyRotLon,
          STATE.allskyRotLat,
          centerX,
          centerY,
          rx,
          ry
        );
      }
      if (pt.visible && Math.hypot(cx - pt.x, cy - pt.y) < 16) {
        foundHover = t;
        break;
      }
    }
    const prevHover = STATE.hoverTargetId;
    STATE.hoverTargetId = foundHover ? foundHover.id : null;
    if (prevHover !== STATE.hoverTargetId) renderCanvasFrame();

    const inv = inverseHammerAitoff(cx, cy, STATE.allskyRotLon, STATE.allskyRotLat, centerX, centerY, rx, ry);
    const readout = document.getElementById("cursorReadout");
    if (foundHover) {
      const distInfo = foundHover.dist_pc
        ? ` · 📏 d = <strong>${formatCosmicDistance(foundHover.dist_pc, foundHover.dist_ly)}</strong>`
        : "";
      readout.innerHTML =
        `🎯 <strong>${foundHover.name}</strong> · RA <strong>${foundHover.ra.toFixed(4)}°</strong> (${formatRaSexagesimal(foundHover.ra)}) · Dec <strong>${foundHover.dec.toFixed(4)}°</strong> (${formatDecSexagesimal(foundHover.dec)})${distInfo}`;
    } else if (inv) {
      readout.innerHTML =
        `🌌 Gal (l=<strong>${inv.l.toFixed(1)}°</strong>, b=<strong>${inv.b.toFixed(1)}°</strong>) · ICRS RA <strong>${inv.ra.toFixed(4)}°</strong> (${formatRaSexagesimal(inv.ra)}) · Dec <strong>${inv.dec.toFixed(4)}°</strong> (${formatDecSexagesimal(inv.dec)})`;
    }
    return;
  }

  if (!STATE.decodedEpochs.length || !STATE.cube) return;
  const { gx, gy } = canvasToGrid(cx, cy);
  const ep = STATE.decodedEpochs[STATE.currentEpochIdx] || STATE.decodedEpochs[0];
  const idx = gy * ep.nx + gx;
  const sbVal = ep.floatArr[idx];
  const flg = ep.intFlags[idx];
  const { ra, dec } = pixelToWorld(gx, gy);

  // Fuente identificada bajo el cursor (la distancia solo se muestra si hay paralaje medida)
  let nearAstroStr = "";
  if (STATE.cube.recognized_objects) {
    const nearObj = STATE.cube.recognized_objects.find(
      (o) => Math.hypot(o.px - gx, o.py - gy) <= 3.5
    );
    if (nearObj) {
      const spT = STATE.lang === "en" ? nearObj.spectral_type_en : nearObj.spectral_type_es;
      const dStr = nearObj.dist_pc ? ` · d=<strong>${formatCosmicDistance(nearObj.dist_pc, nearObj.dist_ly)}</strong>` : "";
      nearAstroStr = ` · 🔭 <strong>${nearObj.name}</strong> (${spT}${dStr})`;
    }
    const newKey = nearObj ? `${nearObj.px},${nearObj.py}` : null;
    if (newKey !== STATE.hoverSourceKey) {
      STATE.hoverSourceKey = newKey;
      renderCanvasFrame();
    }
  }
  const covStr = ep.cov && ep.cov[idx] < 128 ? (STATE.lang === "en" ? " · ⬚ no L2b data" : " · ⬚ sin datos L2b") : "";

  const activeFlagNames = [];
  if (STATE.cube.flag_definitions) {
    for (const fd of STATE.cube.flag_definitions) {
      if (flg & (1 << fd.bit)) activeFlagNames.push(fd.name);
    }
  }
  const flagStr = activeFlagNames.length ? ` · ⚠️ ${activeFlagNames.join(",")}` : "";

  document.getElementById("cursorReadout").innerHTML =
    `Px(<strong>${gx}</strong>,<strong>${gy}</strong>) · ` +
    `RA <strong>${ra.toFixed(5)}°</strong> (${formatRaSexagesimal(ra)}) · ` +
    `Dec <strong>${dec.toFixed(5)}°</strong> (${formatDecSexagesimal(dec)}) · ` +
    `I: <strong>${Number.isFinite(sbVal) ? sbVal.toFixed(3) : "—"} MJy/sr</strong>${nearAstroStr}${flagStr}${covStr}`;
}

function resolvePointToAstroObject(gx, gy) {
  if (STATE.cube && STATE.cube.recognized_objects) {
    let best = null;
    let bestDist = 5.5;
    for (const o of STATE.cube.recognized_objects) {
      const d = Math.hypot(o.px - gx, o.py - gy);
      if (d < bestDist) {
        bestDist = d;
        best = o;
      }
    }
    if (best) return best;
  }
  // Punto sin fuente identificada: sin distancia (no se puede medir con una sola imagen)
  const { ra, dec } = pixelToWorld(gx, gy);
  return {
    name: `Px (${gx},${gy})`,
    px: gx,
    py: gy,
    ra: Number(ra.toFixed(6)),
    dec: Number(dec.toFixed(6)),
    dist_pc: null,
    dist_ly: null,
    spectral_type_es: "Posición sin fuente identificada",
    spectral_type_en: "Position without identified source",
  };
}

async function handleCanvasClick(ev) {
  const canvas = document.getElementById("skyCanvas");
  const rect = canvas.getBoundingClientRect();
  const cx = (ev.clientX - rect.left) * (canvas.width / rect.width);
  const cy = (ev.clientY - rect.top) * (canvas.height / rect.height);

  if (STATE.mode === "allsky") {
    const W = canvas.width;
    const H = canvas.height;
    const pipW = 136,
      pipH = 136,
      pipX = 14,
      pipY = H - pipH - 76;
    if (cx >= pipX - 4 && cx <= pipX + pipW + 4 && cy >= pipY - 22 && cy <= pipY + pipH + 4) {
      STATE.mode = "blink";
      syncViewportVisibility();
      renderPresets();
      renderCanvasFrame();
      return;
    }

    const { cx: centerX, cy: centerY, rx, ry, isGlobe } = allskyGeom(W, H);

    const allInteractives = [
      ...STATE.targets.filter((t) => !t.is_allsky),
      ...(STATE.landmarks || []),
    ];
    for (const t of allInteractives) {
      const frm = eqToActiveFrame(t.ra, t.dec);
      let pt = null;
      if (isGlobe) {
        const rot = rotateSpherical3D(frm.lon, frm.lat, STATE.allskyRotLon, STATE.allskyRotLat, STATE.allskyRoll);
        pt = rot.x3 >= 0 ? { x: centerX - rot.y3 * rx, y: centerY - rot.z3 * ry, visible: true } : { visible: false };
      } else {
        pt = projectHammerAitoff(
          frm.lon,
          frm.lat,
          STATE.allskyRotLon,
          STATE.allskyRotLat,
          centerX,
          centerY,
          rx,
          ry
        );
      }
      if (pt.visible && Math.hypot(cx - pt.x, cy - pt.y) < 18) {
        selectTargetFromAllsky(t);
        return;
      }
    }
    return;
  }

  if (!STATE.decodedEpochs.length || !STATE.cube) return;
  const { gx, gy } = canvasToGrid(cx, cy);
  const obj = resolvePointToAstroObject(gx, gy);

  // Si la herramienta de Medición de Distancia Cósmica 3D (A <-> B) está activa, asignar Punto A o Punto B

  await selectPixelAperture(obj.px, obj.py, obj.name || `Px (${gx}, ${gy})`);
}

async function handleCanvasDoubleClick(ev) {
  const canvas = document.getElementById("skyCanvas");
  const rect = canvas.getBoundingClientRect();
  const cx = (ev.clientX - rect.left) * (canvas.width / rect.width);
  const cy = (ev.clientY - rect.top) * (canvas.height / rect.height);

  if (STATE.mode === "allsky") {
    const W = canvas.width;
    const H = canvas.height;
    const { cx: centerX, cy: centerY, rx, ry, isGlobe } = allskyGeom(W, H);
    const inv = inverseHammerAitoff(cx, cy, STATE.allskyRotLon, STATE.allskyRotLat, centerX, centerY, rx, ry);
    if (!inv) return;
    STATE.ra = inv.ra;
    STATE.dec = inv.dec;
    STATE.activeTarget = null;
    STATE.mode = "blink";
    document.getElementById("inputQuery").value = `${inv.ra.toFixed(5)}, ${inv.dec.toFixed(5)}`;
    renderPresets();
    syncViewportVisibility();
    await loadSkyPatch();
    return;
  }

  if (!STATE.cube) return;
  const { gx, gy } = canvasToGrid(cx, cy);
  const { ra, dec } = pixelToWorld(gx, gy);
  STATE.ra = ((ra % 360.0) + 360.0) % 360.0;
  STATE.dec = Math.max(-89.9, Math.min(89.9, dec));
  STATE.activeTarget = null;
  STATE.viewZoom = 1.0;
  STATE.viewPanX = 0.0;
  STATE.viewPanY = 0.0;
  document.getElementById("inputQuery").value = `${STATE.ra.toFixed(5)}, ${STATE.dec.toFixed(5)}`;
  renderPresets();
  await loadSkyPatch();
}

function renderRecognizedObjectsBar() {
  const bar = document.getElementById("recognizedObjectsBar");
  if (!bar || !STATE.cube) return;
  bar.innerHTML = "";
  const objs = STATE.cube.recognized_objects || [];
  if (!objs.length) return;
  objs.slice(0, 8).forEach((o) => {
    const btn = document.createElement("button");
    btn.type = "button";
    const isSelected = STATE.aperturePx && Math.hypot(STATE.aperturePx.x - o.px, STATE.aperturePx.y - o.py) <= 1.5;
    btn.className = "rec-obj-pill" + (isSelected ? " active" : "");
    const spType = STATE.lang === "en" ? o.spectral_type_en : o.spectral_type_es;
    const distTag = o.dist_pc ? ` · <span class="rec-dist-tag">${formatCosmicDistance(o.dist_pc, o.dist_ly)}</span>` : "";
    btn.innerHTML = `🔭 <strong>${o.name}</strong>${distTag}`;
    const dm = STATE.lang === "en" ? o.dist_method_en : o.dist_method_es;
    const noDist = STATE.lang === "en" ? "No reliable distance (no parallax with π/σ ≥ 5)" : "Sin distancia fiable (no hay paralaje con π/σ ≥ 5)";
    btn.title = `${o.name} | ${spType || ""} | ${o.dist_pc ? (dm || "") : noDist}${o.match_sep_arcsec !== null && o.match_sep_arcsec !== undefined ? ` | Δ=${o.match_sep_arcsec}″` : ""}`;
    btn.addEventListener("click", () => {
      selectPixelAperture(o.px, o.py, o.name);
      renderRecognizedObjectsBar();
    });
    bar.appendChild(btn);
  });
}


async function selectPixelAperture(gx, gy, labelText) {
  STATE.aperturePx = { x: gx, y: gy, label: labelText };
  document.getElementById("apertureCoordBadge").textContent = `${labelText}`;
  renderCanvasFrame();
  try {
    const params = new URLSearchParams({
      ra: STATE.ra.toFixed(6),
      dec: STATE.dec.toFixed(6),
      fov: STATE.fov.toFixed(3),
      bands: STATE.bands.join(","),
      px: String(gx),
      py: String(gy),
    });
    const r = await fetch(`/api/point_spectrum?${params.toString()}`);
    const data = await r.json();
    if (data.spectrum && data.spectrum.length > 0) {
      STATE.pointSpectrum = data.spectrum;
      STATE.pointLightCurve = data.light_curve || null;
      STATE.pointForcedPsf = data.best || null;
      const b = data.best;
      const info = b
        ? ` · ${STATE.lang === "en" ? "best" : "mejor"}: ${fmtNum(b.flux_ujy, 1)} ± ${fmtNum(b.err_ujy, 1)} µJy @ ${b.wavelength_um} µm${b.ab_mag ? ` (m_AB ${b.ab_mag})` : ""}`
        : STATE.lang === "en"
        ? " · no S/N ≥ 3 detection"
        : " · sin detección con S/N ≥ 3";
      document.getElementById("spectrumSubtitle").textContent =
        (STATE.lang === "en" ? `ePSF spectrum at ${labelText} (RA ${data.ra}°, Dec ${data.dec}°)` : `Espectro ePSF en ${labelText} (RA ${data.ra}°, Dec ${data.dec}°)`) +
        `${info} · ${data.spectrum.length} exp` +
        (data.uses_target_astrometry ? (STATE.lang === "en" ? " · with proper motion" : " · con movimiento propio") : "");
    } else {
      STATE.pointSpectrum = null;
      STATE.pointLightCurve = null;
    }
    renderSpectrumChart();
  } catch (err) {
    console.warn("No se pudo extraer espectro puntual:", err);
  }
}

// ============================================================================
// 12. HUD DEL DETECTOR IA, ESCUDO ANTI-ARTEFACTOS Y ECUACIONES EN VIVO
// ============================================================================
function renderAiDetectorHud() {
  const pillsEl = document.getElementById("aiDetectorHudPills");
  const badgeEl = document.getElementById("aiHudCountBadge");
  if (!pillsEl || !STATE.cube) return;
  const en = STATE.lang === "en";
  const cands = STATE.cube.candidates || [];
  const nConf = cands.filter((c) => String(c.verification || "").startsWith("confirmed")).length;
  if (badgeEl) {
    badgeEl.textContent = en ? `${nConf} confirmed / ${cands.length}` : `${nConf} confirmados / ${cands.length}`;
  }
  pillsEl.innerHTML = "";
  if (cands.length === 0) {
    const msg =
      STATE.cube.data_mode === "dr1_static"
        ? en
          ? "Static DR1 image: no time information"
          : "Imagen DR1 estática: sin información temporal"
        : en
        ? "No ≥5σ peaks in the difference image"
        : "Sin picos ≥5σ en la imagen de diferencia";
    pillsEl.innerHTML = `<div class="ai-hud-item"><span>${msg}</span></div>`;
    return;
  }
  cands.slice(0, 3).forEach((c) => {
    const row = document.createElement("div");
    row.className = "ai-hud-item";
    const lbl = en ? c.label_en : c.label_es;
    const ver =
      c.verification === "confirmed_motion" || c.verification === "confirmed_variability"
        ? "✔"
        : c.verification === "not_confirmed"
        ? "✖"
        : "?";
    const notes = (en ? c.notes_en : c.notes_es) || [];
    row.innerHTML = `
      <span class="ai-hud-item-main" title="${notes.join(" ").replace(/"/g, "&quot;")}">
        <strong>#${c.rank}</strong> ${ver} ${lbl} · <span style="color:#34d399">${c.snr_diff}σ</span>
      </span>
      <button type="button" class="ai-hud-ask-btn">💬 AI</button>
    `;
    row.querySelector(".ai-hud-item-main").addEventListener("click", () => {
      STATE.activeCandidateRank = c.rank;
      selectPixelAperture(c.px, c.py, `#${c.rank}`);
      renderCandidatesBar();
    });
    row.querySelector(".ai-hud-ask-btn").addEventListener("click", () => {
      STATE.activeCandidateRank = c.rank;
      selectPixelAperture(c.px, c.py, `#${c.rank}`);
      askGeminiAboutAnomaly(c);
    });
    pillsEl.appendChild(row);
  });
}

function askGeminiAboutAnomaly(cand) {
  const c = cand || (STATE.cube && STATE.cube.candidates && STATE.cube.candidates[0]);
  const en = STATE.lang === "en";
  if (!c) {
    sendAiQuestion(
      en
        ? "Summarise what the measured data of this field show (motion, variability, data quality), using only the telemetry."
        : "Resume lo que muestran los datos medidos de este campo (movimiento, variabilidad, calidad de datos), usando solo la telemetría."
    );
    return;
  }
  const notes = ((en ? c.notes_en : c.notes_es) || []).join(" ");
  const q = en
    ? `Evaluate candidate #${c.rank} (${c.label_en}, verification: ${c.verification}, ${c.snr_diff}σ in the difference image, ePSF shift ${c.psf_shift_arcsec ?? "n/a"}″ ± ${c.psf_shift_err_arcsec ?? "n/a"}″) at RA ${c.ra}°, Dec ${c.dec}°. Notes: ${notes}. Is it real motion, real variability or an artifact? Use only the telemetry.`
    : `Evalúa el candidato #${c.rank} (${c.label_es}, verificación: ${c.verification}, ${c.snr_diff}σ en la imagen de diferencia, desplazamiento ePSF ${c.psf_shift_arcsec ?? "n/d"}″ ± ${c.psf_shift_err_arcsec ?? "n/d"}″) en RA ${c.ra}°, Dec ${c.dec}°. Notas: ${notes}. ¿Es movimiento real, variabilidad real o un artefacto? Usa solo la telemetría.`;
  sendAiQuestion(q);
}

function renderArtifactShieldAndMath() {
  // Reporte MPC: solo visible con un candidato de movimiento confirmado sin contrapartida estelar
  const mpcBtn = document.getElementById("btnExportMpc");
  if (mpcBtn) mpcBtn.hidden = !(STATE.cube && (STATE.cube.mpc_report || []).length);
  const shieldGrid = document.getElementById("artifactShieldGrid");
  const eqGrid = document.getElementById("mathEquationsGrid");
  if (!STATE.cube) return;
  const en = STATE.lang === "en";
  const dq = STATE.cube.data_quality || {};
  if (shieldGrid) {
    shieldGrid.innerHTML = "";
    (dq.checks || []).forEach((chk) => {
      const card = document.createElement("div");
      card.className = "shield-card";
      card.innerHTML = `
        <div class="shield-card-top">
          <span class="shield-card-title">${en ? chk.title_en : chk.title_es}</span>
          <span class="shield-status-tag">${chk.status}</span>
        </div>
        <div class="shield-metric">${en ? chk.metric_en || chk.metric : chk.metric}</div>
        <div class="shield-desc">${en ? chk.desc_en : chk.desc_es}</div>`;
      shieldGrid.appendChild(card);
    });
  }
  if (eqGrid && STATE.cube.math_telemetry && STATE.cube.math_telemetry.equations) {
    eqGrid.innerHTML = "";
    STATE.cube.math_telemetry.equations.forEach((eq) => {
      const card = document.createElement("div");
      card.className = "math-eq-card";
      card.innerHTML = `
        <div class="math-eq-title">${en ? eq.title_en : eq.title_es}</div>
        <div class="math-eq-formula">${en ? eq.formula_en || eq.formula : eq.formula}</div>
        <div class="math-eq-val">${en ? eq.live_value_en || eq.live_value : eq.live_value}</div>`;
      eqGrid.appendChild(card);
    });
  }
  renderBandDepthPills();
}

function renderBandDepthPills() {
  const en = STATE.lang === "en";
  const pills = { H2O_3: "tauPillH2O", CH4_3: "tauPillCH4", CO2_4: "tauPillCO2" };
  const bd = (STATE.dr1Spectrum && STATE.dr1Spectrum.band_depths) || [];
  const fmt = (id) => {
    const b = bd.find((x) => x.id === id);
    if (!b) return null;
    if (b.tau === null || b.tau === undefined) return `${b.label}: ${en ? "not measurable" : "no medible"}`;
    const sig = b.significant
      ? ""
      : b.above_continuum
        ? en ? " (above continuum: not absorption)" : " (sobre el continuo: no es absorción)"
        : en ? " (not significant)" : " (no significativo)";
    return `${b.label}: τ = ${b.tau} ± ${b.tau_err}${sig}`;
  };
  const titleOf = (id) => {
    const b = bd.find((x) => x.id === id);
    if (!b) return "";
    return (en ? b.interpretation_en : b.interpretation_es) + (b.reason_es ? " · " + (en ? b.reason_en : b.reason_es) : "");
  };
  const e1 = document.getElementById(pills.H2O_3);
  const e2 = document.getElementById(pills.CH4_3);
  const e3 = document.getElementById(pills.CO2_4);
  if (!bd.length) {
    if (e1) e1.textContent = en ? "H₂O 3.0 µm: loading DR1…" : "H₂O 3.0 µm: cargando DR1…";
    if (e2) e2.textContent = "CH₄ 3.3 µm";
    if (e3) e3.textContent = "CO₂ 4.27 µm · CO 4.67 µm";
    return;
  }
  if (e1) {
    e1.textContent = fmt("H2O_3.0");
    e1.title = titleOf("H2O_3.0");
  }
  if (e2) {
    e2.textContent = fmt("CH4_3.3");
    e2.title = titleOf("CH4_3.3");
  }
  if (e3) {
    e3.textContent = `${fmt("CO2_4.27")} · ${fmt("CO_4.67")}`;
    e3.title = `${titleOf("CO2_4.27")} | ${titleOf("CO_4.67")}`;
  }
}

function updateHudOverlays(ep) {
  const total = STATE.decodedEpochs.length;
  const en = STATE.lang === "en";
  const epWord = en ? "EPOCH" : "ÉPOCA";
  let modeLabel = `${epWord} ${STATE.currentEpochIdx + 1} / ${total}`;
  if (STATE.cube && STATE.cube.data_mode === "dr1_static") {
    modeLabel = en ? "DR1 STATIC CO-ADD (no time info)" : "CO-ADICIÓN DR1 ESTÁTICA (sin tiempo)";
  } else if (STATE.mode === "diff") {
    modeLabel = en ? `DIFF (E${STATE.currentEpochIdx + 1} − E1)` : `DIFERENCIA (E${STATE.currentEpochIdx + 1} − E1)`;
  } else if (STATE.mode === "rgb") {
    modeLabel = en ? `CHRONO RGB (R=E${total}, B=E1)` : `RGB CRONOLÓGICO (R=E${total}, B=E1)`;
  } else if (STATE.mode === "sum") {
    modeLabel = en ? `CO-ADD (${total} EPOCHS)` : `CO-ADICIÓN (${total} ÉPOCAS)`;
  }
  document.getElementById("hudEpochTitle").textContent = modeLabel;
  const lamStr = ep.lam_min_um ? ` · λ ${ep.lam_min_um}–${ep.lam_max_um} µm` : "";
  document.getElementById("hudDateMjd").textContent = `${ep.date} (MJD ${Number(ep.mjd).toFixed(2)}) · ${ep.n_exp} exp [${(ep.bands || []).join("+")}]${lamStr}`;
  document.getElementById("hudFovScale").textContent = `FOV ${(STATE.fov * 60).toFixed(1)}′ · ${STATE.cube.pix_scale_arcsec}″/px (${en ? "native" : "nativo"} 6.15″)`;
  const pk = ep.peak_sb_mjy_sr;
  const tgtWord = en ? "Target peak" : "Pico objetivo";
  const snrTxt = ep.target_snr_median ? ` · S/N ePSF ${Number(ep.target_snr_median).toFixed(1)}` : "";
  document.getElementById("hudSnrPeak").textContent =
    pk !== null && pk !== undefined
      ? `${tgtWord}: ${Number(pk).toFixed(3)} MJy/sr${snrTxt} · ${ep.n_target_detections || 0}/${ep.n_exp} det.`
      : en
      ? "Target peak: n/a"
      : "Pico objetivo: n/d";
  if (STATE.cube && STATE.cube.stats) {
    document.getElementById("cbarMin").textContent = STATE.cube.stats.p05.toFixed(2);
    document.getElementById("cbarMax").textContent = STATE.cube.stats.p995.toFixed(2);
  }
}

function updateFlagsInspector(ep) {
  const sumEl = document.getElementById("flagsSummaryText");
  const chipsEl = document.getElementById("flagsChips");
  sumEl.textContent =
    STATE.lang === "en"
      ? `Subtracted zodiacal dust (ZODI): ${ep.mean_zodi.toFixed(3)} MJy/sr`
      : `Luz zodiacal sustraída (ZODI): ${ep.mean_zodi.toFixed(3)} MJy/sr`;

  chipsEl.innerHTML = "";
  const counts = ep.flag_counts || {};
  const defs = (STATE.cube && STATE.cube.flag_definitions) || [];
  let hasAny = false;
  for (const d of defs) {
    const cnt = counts[d.name] || 0;
    if (cnt > 0) {
      hasAny = true;
      const chip = document.createElement("span");
      chip.className = "flag-chip";
      chip.title = STATE.lang === "en" ? d.label_en : d.label;
      chip.innerHTML = `<span class="flag-dot" style="background:${d.color}"></span>${d.name}: ${cnt} px`;
      chipsEl.appendChild(chip);
    }
  }
  if (!hasAny) {
    chipsEl.innerHTML = `<span class="flag-chip">${
      STATE.lang === "en" ? "✓ Clean epoch" : "✓ Época limpia"
    }</span>`;
  }
}

function renderCandidatesBar() {
  const bar = document.getElementById("candidatesBar");
  if (!bar || !STATE.cube) return;
  bar.innerHTML = "";
  const en = STATE.lang === "en";
  const centerBtn = document.createElement("button");
  centerBtn.type = "button";
  centerBtn.className = "cand-pill" + (STATE.activeCandidateRank === null ? " active" : "");
  centerBtn.textContent = STATE.cube.target ? `🎯 ${STATE.cube.target.name}` : en ? "🎯 Field centre" : "🎯 Centro del campo";
  centerBtn.addEventListener("click", () => {
    STATE.activeCandidateRank = null;
    STATE.pointSpectrum = null;
    STATE.pointLightCurve = null;
    STATE.pointForcedPsf = null;
    const [ny, nx] = STATE.cube.shape;
    const tr = (STATE.cube.target_track || [])[STATE.currentEpochIdx] || (STATE.cube.target_track || [])[0];
    STATE.aperturePx = tr ? { x: Math.round(tr.px), y: Math.round(tr.py), label: STATE.cube.target ? STATE.cube.target.name : "Centro" } : { x: Math.floor(nx / 2), y: Math.floor(ny / 2), label: "Centro" };
    document.getElementById("apertureCoordBadge").textContent = STATE.aperturePx.label;
    renderCandidatesBar();
    renderCanvasFrame();
    renderSpectrumChart();
  });
  bar.appendChild(centerBtn);
  for (const c of STATE.cube.candidates || []) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cand-pill" + (STATE.activeCandidateRank === c.rank ? " active" : "") + (c.verification === "not_confirmed" ? " cand-rejected" : "");
    const lbl = en ? c.label_en : c.label_es;
    btn.textContent = `#${c.rank} ${lbl}`;
    btn.title = ((en ? c.notes_en : c.notes_es) || []).join(" ");
    btn.addEventListener("click", () => {
      STATE.activeCandidateRank = c.rank;
      renderCandidatesBar();
      selectPixelAperture(c.px, c.py, `#${c.rank} ${lbl}`);
    });
    bar.appendChild(btn);
  }
}

// ============================================================================
// 13. REPRODUCTOR BLINKING Y TABLA DE EXPOSICIONES
// ============================================================================
function renderEpochTimeline() {
  const container = document.getElementById("epochTimeline");
  container.innerHTML = "";
  STATE.decodedEpochs.forEach((ep, idx) => {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "epoch-pill" + (idx === STATE.currentEpochIdx ? " active" : "");
    pill.innerHTML = `<strong>E${idx + 1}</strong> · ${ep.date}`;
    pill.addEventListener("click", () => {
      STATE.currentEpochIdx = idx;
      syncActiveEpochPill();
      renderCanvasFrame();
    });
    container.appendChild(pill);
  });
}

function syncActiveEpochPill() {
  const pills = document.querySelectorAll(".epoch-pill");
  pills.forEach((p, idx) => {
    p.classList.toggle("active", idx === STATE.currentEpochIdx);
  });
}

function stepEpoch(delta) {
  if (!STATE.decodedEpochs.length) return;
  const n = STATE.decodedEpochs.length;
  STATE.currentEpochIdx = (STATE.currentEpochIdx + delta + n) % n;
  syncActiveEpochPill();
  renderCanvasFrame();
}

function togglePlayPause() {
  STATE.isPlaying = !STATE.isPlaying;
  const playLbl = document.getElementById("playLabel");
  const btn = document.getElementById("btnPlayPause");
  if (STATE.isPlaying) {
    btn.innerHTML = `⏸ <span id="playLabel">${STATE.lang === "en" ? "Pause" : "Pausar"}</span>`;
    restartBlinkTimer();
  } else {
    btn.innerHTML = `▶ <span id="playLabel">${STATE.lang === "en" ? "Play" : "Reproducir"}</span>`;
    if (STATE.blinkTimer) clearInterval(STATE.blinkTimer);
  }
}

function restartBlinkTimer() {
  if (STATE.blinkTimer) clearInterval(STATE.blinkTimer);
  if (!STATE.isPlaying || STATE.decodedEpochs.length < 2) return;
  STATE.blinkTimer = setInterval(() => {
    if (STATE.mode === "allsky") return;
    stepEpoch(1);
  }, STATE.blinkSpeedMs);
}

function updateScienceBanner() {
  const titleEl = document.getElementById("scienceTitle");
  const descEl = document.getElementById("scienceDesc");
  const en = STATE.lang === "en";
  let desc = "";
  if (STATE.activeTarget) {
    const t = STATE.activeTarget;
    titleEl.textContent = `${t.name} · ${en && t.subtitle_en ? t.subtitle_en : t.subtitle}`;
    desc = en && t.science_note_en ? t.science_note_en : t.science_note;
    const pn = en ? t.prompt_epoch_note_en : t.prompt_epoch_note;
    if (pn) desc += ` ${pn}`;
  } else {
    titleEl.textContent = en
      ? `Sky patch (RA ${STATE.ra.toFixed(4)}°, Dec ${STATE.dec.toFixed(4)}°)`
      : `Parche celeste (RA ${STATE.ra.toFixed(4)}°, Dec ${STATE.dec.toFixed(4)}°)`;
    desc = en
      ? "Calibrated SPHEREx L2b exposures from NASA/IPAC IRSA and AWS S3."
      : "Exposiciones calibradas SPHEREx L2b de NASA/IPAC IRSA y AWS S3.";
  }
  if (STATE.cube) {
    const src = STATE.cube.data_source ? `${en ? "Data" : "Datos"}: ${STATE.cube.data_source}.` : "";
    const notes = (STATE.cube.notes || []).map((n) => (en ? n.en : n.es)).join(" ");
    desc = `${desc} ${src} ${notes}`.trim();
  }
  descEl.textContent = desc;
}

function renderExposureTable() {
  const tbody = document.getElementById("expTableBody");
  if (!tbody || !STATE.cube) return;
  tbody.innerHTML = "";
  const qLbl = {
    good: STATE.lang === "en" ? "good" : "buena",
    warning: STATE.lang === "en" ? "warning" : "aviso",
    saturated: STATE.lang === "en" ? "saturated" : "saturada",
    non_detection: STATE.lang === "en" ? "not detected" : "no detectada",
    masked: STATE.lang === "en" ? "masked" : "enmascarada",
    no_coverage: STATE.lang === "en" ? "outside" : "fuera",
  };
  for (const ep of STATE.cube.epochs) {
    for (const ex of ep.exposures || []) {
      const tr = document.createElement("tr");
      const lam = ex.wavelength_um ? `<strong>${Number(ex.wavelength_um).toFixed(4)}</strong> ± ${(Number(ex.bandwidth_um || 0) / 2).toFixed(3)}` : "—";
      const flux = ex.flux_ujy !== null && ex.flux_ujy !== undefined ? `${Number(ex.flux_ujy).toFixed(1)} ± ${Number(ex.err_ujy).toFixed(1)}` : "—";
      tr.innerHTML = `
        <td><strong>E${ep.index + 1}</strong></td>
        <td>${ex.obs_id}</td>
        <td><span class="band-tag ${String(ex.band).toLowerCase()}">${ex.band}</span></td>
        <td>${String(ex.date_iso).replace("T", " ").slice(0, 19)}</td>
        <td>${lam}</td>
        <td>${flux}</td>
        <td title="${ex.lvf_edge ? (STATE.lang === "en" ? "Detector edge or λ outside the nominal filter range: flux not used for variability" : "Borde del detector o λ fuera del rango nominal del filtro: el flujo no se usa para variabilidad") : ""}">${qLbl[ex.quality] || ex.quality || "—"}${ex.lvf_edge ? (STATE.lang === "en" ? " · edge" : " · borde") : ""}</td>
        <td>${Number(ex.zodi).toFixed(3)}</td>
        <td>${ex.bad_pct}%</td>
        <td>${ex.release || ""} · ${ex.source}</td>
      `;
      tbody.appendChild(tr);
    }
  }
}

// ============================================================================
// 14. GRÁFICAS CIENTÍFICAS (ESPECTRO ePSF/DR1 Y CURVA DE LUZ POR CANAL)
// ============================================================================
const BAND_COLORS = {
  D1: "#6366f1",
  D2: "#3b82f6",
  D3: "#06b6d4",
  D4: "#10b981",
  D5: "#f59e0b",
  D6: "#f43f5e",
};

function renderSpectrumChart() {
  const canvas = document.getElementById("spectrumCanvas");
  if (!canvas || !STATE.cube) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  const en = STATE.lang === "en";
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#060911";
  ctx.fillRect(0, 0, W, H);

  const pts = (STATE.pointSpectrum || STATE.cube.spectrum || []).filter((p) => p.wavelength_um);
  const dr1 = STATE.showBlackbodyModel && STATE.dr1Spectrum && !STATE.pointSpectrum ? STATE.dr1Spectrum.channels || [] : [];
  const usableL2 = pts.filter((p) => p.flux_ujy !== null && p.flux_ujy !== undefined && p.quality !== "saturated");
  const usableDr1 = dr1.filter((c) => c.flux_ujy !== null && c.flux_ujy !== undefined && c.quality !== "saturated" && c.quality !== "blank");
  if (!usableL2.length && !usableDr1.length) {
    ctx.fillStyle = "#8492a6";
    ctx.font = "12px 'Inter', sans-serif";
    const nSat = pts.filter((p) => p.quality === "saturated").length;
    const msg = nSat
      ? en
        ? `All ${nSat} measurements are saturated: no reliable flux.`
        : `Las ${nSat} mediciones están saturadas: no hay flujo fiable.`
      : en
      ? "No flux measurements in the active bands (or loading DR1)."
      : "Sin mediciones de flujo en las bandas activas (o cargando DR1).";
    ctx.fillText(msg, 18, H / 2);
    return;
  }
  const padL = 54, padR = 14, padT = 26, padB = 24;
  const pw = W - padL - padR;
  const ph = H - padT - padB;
  const allF = [...usableL2.map((p) => p.flux_ujy + (p.err_ujy || 0)), ...usableDr1.map((c) => c.flux_ujy + (c.err_ujy || 0))];
  const allFmin = [...usableL2.map((p) => p.flux_ujy - (p.err_ujy || 0)), ...usableDr1.map((c) => c.flux_ujy - (c.err_ujy || 0))];
  const maxF = Math.max(...allF, 1e-3);
  const minF = Math.min(0, ...allFmin);
  const useMjy = maxF > 5000;
  const k = useMjy ? 1e-3 : 1.0;
  const unit = useMjy ? "mJy" : "µJy";
  const minY = minF * k;
  const maxY = maxF * 1.12 * k;
  const xPx = (lam) => padL + ((lam - 0.72) / (5.05 - 0.72)) * pw;
  const yPx = (f) => padT + ph - ((f * k - minY) / Math.max(maxY - minY, 1e-9)) * ph;

  // Bandas moleculares (gas en atmósferas frías; hielo solo en nubes moleculares / protoestrellas)
  const molBands = [
    { l0: 1.33, l1: 1.5, label: "H₂O" },
    { l0: 1.6, l1: 1.72, label: "CH₄" },
    { l0: 1.8, l1: 2.0, label: "H₂O" },
    { l0: 2.2, l1: 2.4, label: "CH₄/CO" },
    { l0: 2.7, l1: 3.15, label: "H₂O" },
    { l0: 3.2, l1: 3.45, label: "CH₄" },
    { l0: 4.22, l1: 4.32, label: "CO₂" },
    { l0: 4.6, l1: 4.75, label: "CO" },
  ];
  ctx.font = "9px 'JetBrains Mono', monospace";
  for (const mb of molBands) {
    const x0 = xPx(mb.l0);
    const x1 = xPx(mb.l1);
    ctx.fillStyle = "rgba(148, 163, 184, 0.07)";
    ctx.fillRect(x0, padT, x1 - x0, ph);
    ctx.fillStyle = "rgba(148, 163, 184, 0.6)";
    ctx.fillText(mb.label, x0 + 1, padT + 9);
  }
  // Grilla y eje Y
  ctx.strokeStyle = "rgba(148, 163, 184, 0.14)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (ph * i) / 4;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();
    const v = maxY - ((maxY - minY) * i) / 4;
    ctx.fillStyle = "#8492a6";
    ctx.font = "9.5px 'JetBrains Mono', monospace";
    ctx.fillText(v >= 100 ? v.toFixed(0) : v.toFixed(2), 4, y + 3);
  }
  ctx.save();
  ctx.translate(11, padT + ph / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = "#94a3b8";
  ctx.font = "9px 'Inter', sans-serif";
  ctx.fillText(`F (${unit})`, -16, 0);
  ctx.restore();

  // Espectro DR1 (co-adición, 102 canales): línea con huecos donde hay saturación o canal vacío
  if (dr1.length) {
    ctx.strokeStyle = "rgba(250, 204, 21, 0.85)";
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    let pen = false;
    for (const c of dr1) {
      const ok = c.flux_ujy !== null && c.flux_ujy !== undefined && c.quality !== "saturated" && c.quality !== "blank";
      if (!ok) {
        pen = false;
        continue;
      }
      const x = xPx(c.wavelength_um);
      const y = yPx(c.flux_ujy);
      if (!pen) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      pen = true;
    }
    ctx.stroke();
  }
  // Mediciones L2b por exposición (ePSF): punto = detección, triángulo = límite superior 3σ, × = saturada
  for (const p of pts) {
    const x = xPx(p.wavelength_um);
    const col = BAND_COLORS[p.band] || "#00f5d4";
    if (p.quality === "saturated") {
      if (p.flux_ujy === null || p.flux_ujy === undefined) continue;
      const y = Math.max(padT, Math.min(padT + ph, yPx(p.flux_ujy)));
      ctx.strokeStyle = "#f87171";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(x - 3, y - 3);
      ctx.lineTo(x + 3, y + 3);
      ctx.moveTo(x + 3, y - 3);
      ctx.lineTo(x - 3, y + 3);
      ctx.stroke();
      continue;
    }
    if (p.upper_limit_ujy !== null && p.upper_limit_ujy !== undefined && (p.snr === null || p.snr < 3)) {
      const y = Math.max(padT + 4, Math.min(padT + ph, yPx(p.upper_limit_ujy)));
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.moveTo(x - 3.5, y);
      ctx.lineTo(x + 3.5, y);
      ctx.lineTo(x, y + 5);
      ctx.closePath();
      ctx.fill();
      continue;
    }
    if (p.flux_ujy === null || p.flux_ujy === undefined) continue;
    const y = yPx(p.flux_ujy);
    const err = p.err_ujy || 0;
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    ctx.moveTo(x, Math.max(padT, yPx(p.flux_ujy + err)));
    ctx.lineTo(x, Math.min(padT + ph, yPx(p.flux_ujy - err)));
    ctx.stroke();
    ctx.fillStyle = col;
    ctx.beginPath();
    ctx.arc(x, y, 3.3, 0, Math.PI * 2);
    ctx.fill();
    if (p.quality === "warning") {
      ctx.strokeStyle = "#fb923c";
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  // Eje X
  ctx.fillStyle = "#cbd5e1";
  ctx.font = "10px 'JetBrains Mono', monospace";
  for (const tick of [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]) {
    ctx.fillText(`${tick.toFixed(1)}`, xPx(tick) - 8, H - 8);
  }
  ctx.fillText("µm", W - padR - 14, H - 8);
  ctx.font = "9px 'Inter', sans-serif";
  ctx.fillStyle = "#94a3b8";
  const leg = dr1.length
    ? en
      ? "● L2b ePSF per exposure  ▼ 3σ limit  × saturated   — DR1 co-add"
      : "● L2b ePSF por exposición  ▼ límite 3σ  × saturada   — co-adición DR1"
    : en
    ? "● L2b ePSF per exposure  ▼ 3σ limit  × saturated"
    : "● L2b ePSF por exposición  ▼ límite 3σ  × saturada";
  ctx.fillText(leg, padL, 11);
  const teffBadge = document.getElementById("specTeffBadge");
  if (teffBadge) {
    const t = STATE.cube.target;
    teffBadge.textContent = t && t.teff_k_lit ? `T_eff ${t.teff_k_lit} (${t.teff_ref || "lit."})` : en ? "T_eff: not measured by SPHEREx" : "T_eff: no la mide SPHEREx";
    teffBadge.title = en ? "Literature value; it is NOT fitted from this spectrum." : "Valor de la literatura; NO se ajusta a este espectro.";
  }
}


// ============================================================================
// 15. ASTRO-AI COPILOT (DIAGNÓSTICO AUTOMÁTICO Y PUENTE MULTIMODAL GEMINI)
// ============================================================================
function renderAutoAiSummary() {
  if (!STATE.cube) return;
  const analysis = STATE.lang === "en" ? STATE.cube.ai_analysis_en : STATE.cube.ai_analysis_es;
  if (!analysis) return;

  document.getElementById("aiAutoTitle").textContent = `🔭 ${analysis.title}`;
  const ul = document.getElementById("aiBulletList");
  ul.innerHTML = "";
  for (const b of analysis.bullets || []) {
    const li = document.createElement("li");
    li.innerHTML = formatMarkdownLite(b);
    ul.appendChild(li);
  }
  document.getElementById("aiTipBox").innerHTML = formatMarkdownLite(analysis.tip || "");
}

// ============================================================================
// CLAVE DE IA OPCIONAL (Gemini / OpenAI): confirmación con el proveedor y estado visible
// ============================================================================
const AI_KEY_STORE = "skychrono_ai_key";

function aiKeyStorageGet() {
  try {
    return sessionStorage.getItem(AI_KEY_STORE) || "";
  } catch (e) {
    return "";
  }
}

function aiKeyStorageSet(value) {
  try {
    if (value) sessionStorage.setItem(AI_KEY_STORE, value);
    else sessionStorage.removeItem(AI_KEY_STORE);
  } catch (e) {
    /* almacenamiento no disponible: la clave vive solo en memoria */
  }
}

function renderAiKeyStatus() {
  const el = document.getElementById("aiKeyStatus");
  if (!el) return;
  const en = STATE.lang === "en";
  el.classList.remove("ok", "err", "pending", "muted");
  const info = STATE.aiKeyInfo;
  if (STATE.aiKeyChecking) {
    el.textContent = en ? "⏳ Checking the key with the provider…" : "⏳ Verificando la clave con el proveedor…";
    el.classList.add("pending");
  } else if (info) {
    const icon = info.ok ? (info.warning ? "⚠️" : "✅") : "❌";
    el.textContent = `${icon} ${en ? info.message_en : info.message_es}`;
    el.classList.add(info.ok ? (info.warning ? "pending" : "ok") : "err");
  } else if (STATE.aiServerKey && STATE.aiServerKey.server_key) {
    const prov = STATE.aiServerKey.provider === "openai" ? "OpenAI" : "Google Gemini";
    el.textContent = en
      ? `🔐 The server has its own key (.env) for ${prov}: the copilot uses it unless you confirm another one here.`
      : `🔐 El servidor tiene su propia clave (.env) de ${prov}: el copiloto la usa salvo que confirmes otra aquí.`;
    el.classList.add("ok");
  } else {
    el.textContent = en
      ? "No key: the copilot answers with the local deterministic engine (it works without AI)."
      : "Sin clave: el copiloto responde con el motor local determinista (funciona sin IA).";
    el.classList.add("muted");
  }
  const btnOk = document.getElementById("btnAiKeyConfirm");
  const btnClr = document.getElementById("btnAiKeyClear");
  if (btnOk) btnOk.disabled = Boolean(STATE.aiKeyChecking);
  if (btnClr) btnClr.disabled = Boolean(STATE.aiKeyChecking);
}

function updateAiEngineTag() {
  const tag = document.getElementById("aiEngineTag");
  if (!tag) return;
  const en = STATE.lang === "en";
  const info = STATE.aiKeyInfo;
  if (info && info.ok) tag.textContent = `${info.provider_label} · ${info.model}`;
  else if (STATE.aiServerKey && STATE.aiServerKey.server_key) tag.textContent = en ? "AI with server key (.env)" : "IA con clave del servidor (.env)";
  else tag.textContent = en ? "Local engine (no AI key)" : "Motor local (sin clave de IA)";
}

async function confirmAiKey() {
  const inp = document.getElementById("inputApiKey");
  const key = inp ? inp.value.trim() : "";
  if (!key) {
    clearAiKey();
    return false;
  }
  STATE.aiKeyChecking = true;
  renderAiKeyStatus();
  try {
    const r = await fetch("/api/ai/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key }),
    });
    STATE.aiKeyInfo = await r.json();
  } catch (err) {
    STATE.aiKeyInfo = {
      ok: false,
      message_es: "No se pudo contactar con el servidor SkyChrono para comprobar la clave.",
      message_en: "Could not reach the SkyChrono server to check the key.",
    };
  }
  STATE.aiKeyChecking = false;
  STATE.aiKeyTyped = STATE.aiKeyInfo && STATE.aiKeyInfo.reason === "network" ? "" : key;
  if (STATE.aiKeyInfo && STATE.aiKeyInfo.ok) {
    STATE.aiKey = key;
    aiKeyStorageSet(key);
  } else {
    STATE.aiKey = "";
    aiKeyStorageSet("");
  }
  renderAiKeyStatus();
  updateAiEngineTag();
  return Boolean(STATE.aiKeyInfo && STATE.aiKeyInfo.ok);
}

function clearAiKey() {
  const inp = document.getElementById("inputApiKey");
  if (inp) inp.value = "";
  STATE.aiKey = "";
  STATE.aiKeyTyped = "";
  STATE.aiKeyInfo = null;
  aiKeyStorageSet("");
  renderAiKeyStatus();
  updateAiEngineTag();
}

async function initAiKeyPanel() {
  const btnOk = document.getElementById("btnAiKeyConfirm");
  const btnClr = document.getElementById("btnAiKeyClear");
  const inp = document.getElementById("inputApiKey");
  if (btnOk) btnOk.addEventListener("click", () => confirmAiKey());
  if (btnClr) btnClr.addEventListener("click", () => clearAiKey());
  if (inp) {
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        confirmAiKey();
      }
    });
  }
  try {
    const r = await fetch("/api/ai/status");
    STATE.aiServerKey = await r.json();
  } catch (e) {
    STATE.aiServerKey = null;
  }
  const saved = aiKeyStorageGet();
  if (saved && inp) {
    inp.value = saved;
    await confirmAiKey();
  } else {
    renderAiKeyStatus();
    updateAiEngineTag();
  }
}

async function sendAiQuestion(question) {
  const log = document.getElementById("aiChatLog");
  const userDiv = document.createElement("div");
  userDiv.className = "ai-msg user";
  userDiv.textContent = question;
  log.appendChild(userDiv);

  const botDiv = document.createElement("div");
  botDiv.className = "ai-msg bot";
  const usingAi = Boolean(STATE.aiKey || (STATE.aiServerKey && STATE.aiServerKey.server_key));
  botDiv.textContent =
    STATE.lang === "en"
      ? usingAi
        ? "Analyzing with the AI and the SPHEREx telemetry (it may take up to a minute if the provider is busy)..."
        : "Analyzing the SPHEREx telemetry with the local engine..."
      : usingAi
      ? "Analizando con la IA y la telemetría SPHEREx (puede tardar hasta un minuto si el proveedor está saturado)..."
      : "Analizando la telemetría SPHEREx con el motor local...";
  log.appendChild(botDiv);
  log.scrollTop = log.scrollHeight;

  const spec = STATE.pointSpectrum || (STATE.cube && STATE.cube.spectrum) || [];
  const cube = STATE.cube || {};
  const dr1 = STATE.dr1Spectrum;
  const context = {
    target_name: cube.target ? cube.target.name : STATE.activeTarget ? STATE.activeTarget.name : `RA ${STATE.ra.toFixed(4)}, Dec ${STATE.dec.toFixed(4)}`,
    ra: STATE.ra,
    dec: STATE.dec,
    fov_deg: STATE.fov,
    bands: STATE.bands,
    data_source: cube.data_source,
    data_mode: cube.data_mode,
    notes: (cube.notes || []).map((n) => (STATE.lang === "en" ? n.en : n.es)),
    target: cube.target || null,
    epochs: (cube.epochs || []).map((e) => ({
      date: e.date, mjd: e.mjd, n_exp: e.n_exp, bands: e.bands, lam_min_um: e.lam_min_um, lam_max_um: e.lam_max_um,
      mean_zodi: e.mean_zodi, n_target_detections: e.n_target_detections,
    })),
    photometry_summary: cube.photometry_summary || null,
    photometry: spec.slice(0, 40).map((p) => ({
      date: (p.date_iso || "").slice(0, 10), band: p.band, wavelength_um: p.wavelength_um, flux_ujy: p.flux_ujy,
      err_ujy: p.err_ujy, snr: p.snr, quality: p.quality, upper_limit_ujy: p.upper_limit_ujy, offset_arcsec: p.offset_arcsec,
    })),
    light_curve: cube.light_curve ? { strongest_change: cube.light_curve.strongest_change, n_points: cube.light_curve.n_points } : null,
    candidates: (cube.candidates || []).map((c) => ({
      rank: c.rank, label: STATE.lang === "en" ? c.label_en : c.label_es, verification: c.verification, snr_diff: c.snr_diff,
      psf_shift_arcsec: c.psf_shift_arcsec, psf_shift_err_arcsec: c.psf_shift_err_arcsec, catalog_match: c.catalog_match,
      notes: STATE.lang === "en" ? c.notes_en : c.notes_es,
    })),
    recognized_objects: (cube.recognized_objects || []).slice(0, 8).map((o) => ({ name: o.name, class: o.obj_class, dist_pc: o.dist_pc, dist_method: o.dist_method_en })),
    data_quality: cube.data_quality ? cube.data_quality.checks.map((c) => ({ id: c.id, status: c.status, metric: c.metric })) : null,
    dr1_spectrum: dr1
      ? {
          n_saturated_channels: dr1.n_saturated,
          contamination_warning: dr1.contamination_warning,
          neighbors: dr1.neighbors,
          band_depths: dr1.band_depths,
          notes: STATE.lang === "en" ? dr1.notes_en : dr1.notes_es,
        }
      : null,
    aperture: STATE.aperturePx,
  };

  let canvasSnapshotB64 = null;
  try {
    const skyCanvas = document.getElementById("skyCanvas");
    if (skyCanvas) {
      canvasSnapshotB64 = skyCanvas.toDataURL("image/jpeg", 0.82);
    }
  } catch (e) {
    canvasSnapshotB64 = null;
  }

  try {
    const inpKey = document.getElementById("inputApiKey");
    const typed = inpKey ? inpKey.value.trim() : "";
    if (typed && typed !== STATE.aiKeyTyped && !STATE.aiKeyChecking) {
      await confirmAiKey();
    }
    const apiKey = STATE.aiKey || "";
    const r = await fetch("/api/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: question,
        context,
        lang: STATE.lang,
        api_key: apiKey,
        image_b64: canvasSnapshotB64,
        history: STATE.chatHistory.slice(-8),
      }),
    });
    const data = await r.json();
    const replyText = data.reply || (STATE.lang === "en" ? "No answer." : "Sin respuesta.");
    let warn = "";
    if (data.ai_error) {
      const m = STATE.lang === "en" ? data.ai_error.message_en : data.ai_error.message_es;
      warn = `⚠️ ${m} ${STATE.lang === "en" ? "Answer from the local engine:" : "Respuesta del motor local:"}\n\n`;
    }
    botDiv.innerHTML = formatChatMarkdown(warn + replyText);
    STATE.chatHistory.push({ role: "user", text: question });
    STATE.chatHistory.push({ role: "model", text: replyText });
    if (data.engine) {
      document.getElementById("aiEngineTag").textContent = data.engine;
    }
  } catch (err) {
    botDiv.textContent = `Error: ${err.message}`;
  }
  log.scrollTop = log.scrollHeight;
}

function _escapeHtmlDocs(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function _beautifyLatexInline(expr) {
  return String(expr || "")
    .replace(/\\left\s*/g, "")
    .replace(/\\right\s*/g, "")
    .replace(/\\qquad|\\quad|\\;|\\:|\\,|\\!/g, " ")
    .replace(/\\\{/g, "{")
    .replace(/\\\}/g, "}")
    .replace(/\\text\{([^{}]*)\}/g, "$1")
    .replace(/\\mathrm\{([^{}]*)\}/g, "$1")
    .replace(/\\mathbf\{([^{}]*)\}/g, "$1")
    .replace(/_\{([^{}]+)\}/g, "_$1")
    .replace(/\^\{([^{}]+)\}/g, "^$1")
    .replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, "($1) / ($2)")
    .replace(/\\sqrt\{([^}]*)\}/g, "√($1)")
    .replace(/\\longrightarrow(?![a-zA-Z])/g, "→")
    .replace(/\\rightarrow(?![a-zA-Z])|\\to(?![a-zA-Z])/g, "→")
    .replace(/\\leftrightarrow(?![a-zA-Z])/g, "↔")
    .replace(/\\approx(?![a-zA-Z])/g, "≈")
    .replace(/\\times(?![a-zA-Z])/g, "×")
    .replace(/\\cdot(?![a-zA-Z])/g, "·")
    .replace(/\\pm(?![a-zA-Z])/g, "±")
    .replace(/\\leq(?![a-zA-Z])|\\le(?![a-zA-Z])/g, "≤")
    .replace(/\\geq(?![a-zA-Z])|\\ge(?![a-zA-Z])/g, "≥")
    .replace(/\\neq(?![a-zA-Z])|\\ne(?![a-zA-Z])/g, "≠")
    .replace(/\\infty(?![a-zA-Z])/g, "∞")
    .replace(/\\in(?![a-zA-Z])/g, "∈")
    .replace(/\\Delta(?![a-zA-Z])/g, "Δ")
    .replace(/\\Omega(?![a-zA-Z])/g, "Ω")
    .replace(/\\Sigma(?![a-zA-Z])|\\sum(?![a-zA-Z])/g, "Σ")
    .replace(/\\lambda(?![a-zA-Z])/g, "λ")
    .replace(/\\mu/g, "μ")
    .replace(/\\tau(?![a-zA-Z])/g, "τ")
    .replace(/\\sigma(?![a-zA-Z])/g, "σ")
    .replace(/\\theta(?![a-zA-Z])/g, "θ")
    .replace(/\\alpha(?![a-zA-Z])/g, "α")
    .replace(/\\beta(?![a-zA-Z])/g, "β")
    .replace(/\\delta(?![a-zA-Z])/g, "δ")
    .replace(/\\varpi(?![a-zA-Z])/g, "ϖ")
    .replace(/\\pi(?![a-zA-Z])/g, "π")
    .replace(/\\chi(?![a-zA-Z])/g, "χ")
    .replace(/\\nu(?![a-zA-Z])/g, "ν")
    .replace(/\\star(?![a-zA-Z])/g, "⋆")
    .replace(/\\langle(?![a-zA-Z])/g, "⟨")
    .replace(/\\rangle(?![a-zA-Z])/g, "⟩")
    .replace(/\^\\circ(?![a-zA-Z])|\\circ(?![a-zA-Z])|\\degree(?![a-zA-Z])/g, "°")
    .replace(/\\prime\\prime(?![a-zA-Z])|\\arcsec(?![a-zA-Z])/g, "″")
    .replace(/\\prime(?![a-zA-Z])|\\arcmin(?![a-zA-Z])/g, "′")
    .replace(/\\odot(?![a-zA-Z])/g, "☉")
    .replace(/\\lesssim(?![a-zA-Z])/g, "≲")
    .replace(/\\gtrsim(?![a-zA-Z])/g, "≳")
    .replace(/\\propto(?![a-zA-Z])/g, "∝")
    .replace(/\\sim(?![a-zA-Z])/g, "~")
    .replace(/\\cos(?![a-zA-Z])/g, "cos")
    .replace(/\\sin(?![a-zA-Z])/g, "sin")
    .replace(/\\ln(?![a-zA-Z])/g, "ln")
    .replace(/\\log_\{?10\}?/g, "log₁₀")
    .replace(/\\log(?![a-zA-Z])/g, "log")
    .replace(/\s+/g, " ")
    .trim();
}

function _renderInlineMath(s, pushToken) {
  let out = "";
  let i = 0;
  while (i < s.length) {
    const a = s.indexOf("$", i);
    if (a < 0) {
      out += s.slice(i);
      break;
    }
    out += s.slice(i, a);
    const money = /^\d[\d.,]*(?:\s|$)/.test(s.slice(a + 1));
    const b = money ? -1 : s.indexOf("$", a + 1);
    const nl = s.indexOf("\n", a + 1);
    if (b > a + 1 && (nl < 0 || b < nl)) {
      out += pushToken(`<code>${_beautifyLatexInline(s.slice(a + 1, b))}</code>`);
      i = b + 1;
    } else {
      out += "$";
      i = a + 1;
    }
  }
  return out;
}

function formatMarkdownInline(text) {
  const tokens = [];
  const pushToken = (htmlStr) => {
    const idx = tokens.length;
    tokens.push(htmlStr);
    return `\u0000TOK${idx}\u0000`;
  };

  let s = _escapeHtmlDocs(text).replace(/`([^`]+)`/g, (_m, code) =>
    pushToken(`<code>${code}</code>`)
  );

  // Inline LaTeX $...$ (un "$" seguido de un número y un espacio o fin, como "$10 ", es un monto y no abre fórmula)
  s = _renderInlineMath(s, pushToken);

  // Links Markdown [label](url)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]+|#[^\s)]+)\)/g, (_m, label, url) => {
    const isExt = /^https?:\/\//i.test(url);
    const attrs = isExt ? ' target="_blank" rel="noopener noreferrer"' : "";
    return pushToken(`<a href="${url}"${attrs}>${label}</a>`);
  });

  // URLs sueltas https://...
  s = s.replace(/(https?:\/\/[^\s<>()]+[^\s<>().,;:'"!?])/g, (url) =>
    pushToken(`<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`)
  );

  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^\*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  s = s.replace(/\u0000TOK(\d+)\u0000/g, (_m, i) => tokens[Number(i)] || "");
  return s;
}

function formatMarkdownLite(text) {
  return formatMarkdownInline(text).replace(/\n/g, "<br/>");
}

// Respuestas del copiloto: títulos, listas, tablas y fórmulas con el mismo intérprete (con HTML escapado) de la documentación
function formatChatMarkdown(text) {
  return renderMarkdownDocument(String(text || ""), STATE.lang);
}

// ============================================================================
// 16. CENTRO DE DOCUMENTACIÓN ÚNICO (ES / EN) Y EXPORTADORES (CSV, GIF, URL)
// ============================================================================
function updateDocsModalChrome(lang = STATE.docLang) {
  const isEn = lang === "en";
  const badge = document.getElementById("i18nDocsBadge");
  const title = document.getElementById("docsModalTitle");
  const langBtnLbl = document.getElementById("docLangBtnLabel");
  const rawLbl = document.getElementById("i18nBtnRawMd");
  const closeLbl = document.getElementById("i18nBtnCloseDocs");
  if (badge) badge.textContent = isEn ? "OFFICIAL DOCUMENTATION" : "DOCUMENTACIÓN OFICIAL";
  if (title) {
    title.textContent = isEn
      ? "SPHEREx SkyChrono Complete Documentation"
      : "Documentación Integral SPHEREx SkyChrono";
  }
  if (langBtnLbl) langBtnLbl.textContent = isEn ? "Ver en Español" : "View in English";
  if (rawLbl) rawLbl.textContent = isEn ? "Open Markdown" : "Abrir Markdown";
  if (closeLbl) closeLbl.textContent = isEn ? "Close" : "Cerrar";

  const chapterLabels = isEn
    ? {
        docCh1: "🌱 1. Basics & Mission",
        docCh2: "🔭 2. User Manual",
        docCh3: "🏛️ 3. Technical & Math (NASA)",
        docCh4: "🚀 4. Deploy & Pitch",
        docCh5: "🔗 5. Targets & DOIs",
      }
    : {
        docCh1: "🌱 1. Conceptos Básicos",
        docCh2: "🔭 2. Manual de Usuario",
        docCh3: "🏛️ 3. Arquitectura y Matemática (NASA)",
        docCh4: "🚀 4. Despliegue y Pitch",
        docCh5: "🔗 5. Objetivos y DOIs",
      };
  for (const [id, txt] of Object.entries(chapterLabels)) {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
  }
}

async function openDocsModal(defaultLang = STATE.lang) {
  const modal = document.getElementById("docsModal");
  modal.hidden = false;
  document.querySelectorAll("#docsModalTabs .doc-toc-btn").forEach((b, idx) => {
    b.classList.toggle("active", idx === 0);
  });
  await loadDocumentIntoModal(defaultLang === "en" ? "en" : "es");
}

function closeDocsModal() {
  document.getElementById("docsModal").hidden = true;
}

async function loadDocumentIntoModal(docLang = STATE.docLang) {
  const normLang = docLang === "en" ? "en" : "es";
  STATE.docLang = normLang;
  updateDocsModalChrome(normLang);

  const body = document.getElementById("docsModalContent");
  body.innerHTML =
    normLang === "en" ? "Loading official documentation..." : "Cargando documentación oficial...";
  try {
    const r = await fetch(`/api/docs?lang=${encodeURIComponent(normLang)}`);
    const data = await r.json();
    document.getElementById("btnDownloadDocRaw").href = `/${data.filename}`;
    body.innerHTML = renderMarkdownDocument(data.content || "", normLang);
    body.scrollTop = 0;
  } catch (err) {
    body.textContent = `Error: ${err.message}`;
  }
}

function _slugifyHeading(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

function _splitTableRow(line) {
  return String(line || "")
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split(/(?<!\\)\|/)
    .map((cell) => cell.replace(/\\\|/g, "|").trim());
}

function _isTableSeparatorLine(line) {
  const cells = _splitTableRow(line);
  return cells.length > 0 && cells.every((c) => /^:?-{3,}:?$/.test(c));
}

function renderMarkdownDocument(md, docLang = STATE.docLang) {
  const isEn = docLang === "en";
  const lines = String(md || "").split(/\r?\n/);
  let html = "";
  let inCode = false;
  let codeLang = "";
  let codeBuf = [];
  let inMathBlock = false;
  let mathBuf = [];
  let listType = null; // "ul" | "ol"
  let quoteBuf = [];

  const closeList = () => {
    if (listType) {
      html += `</${listType}>`;
      listType = null;
    }
  };

  const flushQuote = () => {
    if (!quoteBuf.length) return;
    let first = quoteBuf[0];
    let cls = "doc-blockquote";
    let headerHtml = "";
    const calloutMatch = first.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$/i);
    if (calloutMatch) {
      const kind = calloutMatch[1].toLowerCase();
      cls += ` doc-callout-${kind === "caution" ? "warning" : kind}`;
      const labelMap = isEn
        ? { note: "NOTE", tip: "TIP", important: "IMPORTANT", warning: "WARNING", caution: "CAUTION" }
        : { note: "NOTA", tip: "TIP", important: "IMPORTANTE", warning: "ADVERTENCIA", caution: "PRECAUCIÓN" };
      headerHtml = `<div class="doc-callout-title">${labelMap[kind] || kind.toUpperCase()}</div>`;
      first = calloutMatch[2] || "";
    }
    const bodyLines = [first, ...quoteBuf.slice(1)].filter((l) => l.length > 0);
    html += `<blockquote class="${cls}">${headerHtml}${bodyLines
      .map((l) => `<p>${formatMarkdownInline(l)}</p>`)
      .join("")}</blockquote>`;
    quoteBuf = [];
  };

  const flushCode = () => {
    const label = codeLang ? `<div class="doc-code-lang">${_escapeHtmlDocs(codeLang)}</div>` : "";
    html += `<div class="doc-code-wrap">${label}<pre><code>${_escapeHtmlDocs(
      codeBuf.join("\n")
    )}</code></pre></div>`;
    codeBuf = [];
    codeLang = "";
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (trimmed.startsWith("```")) {
      closeList();
      flushQuote();
      if (!inCode) {
        inCode = true;
        codeLang = trimmed.slice(3).trim();
        codeBuf = [];
      } else {
        flushCode();
        inCode = false;
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(rawLine);
      continue;
    }

    if (trimmed.startsWith("$$")) {
      closeList();
      flushQuote();
      if (!inMathBlock && trimmed.endsWith("$$") && trimmed.length > 4) {
        const inner = trimmed.slice(2, -2).trim();
        html += `<div class="doc-math-block">${_escapeHtmlDocs(_beautifyLatexInline(inner))}</div>`;
      } else if (!inMathBlock) {
        inMathBlock = true;
        mathBuf = trimmed.length > 2 ? [trimmed.slice(2)] : [];
      } else {
        if (trimmed.length > 2) mathBuf.push(trimmed.slice(0, -2));
        html += `<div class="doc-math-block">${_escapeHtmlDocs(
          _beautifyLatexInline(mathBuf.join(" "))
        )}</div>`;
        inMathBlock = false;
        mathBuf = [];
      }
      continue;
    }
    if (inMathBlock) {
      mathBuf.push(trimmed);
      continue;
    }

    if (trimmed.startsWith(">")) {
      closeList();
      quoteBuf.push(trimmed.replace(/^>\s?/, ""));
      continue;
    }
    flushQuote();

    if (!trimmed) {
      closeList();
      continue;
    }

    if (/^([-*_])\1{2,}$/.test(trimmed)) {
      closeList();
      html += '<hr class="doc-hr"/>';
      continue;
    }

    // Tabla Markdown GFM: fila encabezado + fila separadora
    if (
      trimmed.startsWith("|") &&
      i + 1 < lines.length &&
      lines[i + 1].trim().startsWith("|") &&
      _isTableSeparatorLine(lines[i + 1])
    ) {
      closeList();
      const headers = _splitTableRow(trimmed);
      const aligns = _splitTableRow(lines[i + 1]).map((c) => {
        if (c.startsWith(":") && c.endsWith(":")) return "center";
        if (c.endsWith(":")) return "right";
        return "left";
      });
      i += 2;
      const bodyRows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        bodyRows.push(_splitTableRow(lines[i]));
        i++;
      }
      i--;
      html += '<div class="doc-table-wrap"><table class="doc-md-table"><thead><tr>';
      headers.forEach((h, idx) => {
        const al = aligns[idx] || "left";
        html += `<th style="text-align:${al}">${formatMarkdownInline(h)}</th>`;
      });
      html += "</tr></thead><tbody>";
      bodyRows.forEach((row) => {
        html += "<tr>";
        headers.forEach((_, idx) => {
          const al = aligns[idx] || "left";
          html += `<td style="text-align:${al}">${formatMarkdownInline(row[idx] || "")}</td>`;
        });
        html += "</tr>";
      });
      html += "</tbody></table></div>";
      continue;
    }

    if (trimmed.startsWith("#### ")) {
      closeList();
      const rawH = trimmed.slice(5);
      html += `<h4 id="${_slugifyHeading(rawH)}">${formatMarkdownInline(rawH)}</h4>`;
    } else if (trimmed.startsWith("### ")) {
      closeList();
      const rawH = trimmed.slice(4);
      html += `<h3 id="${_slugifyHeading(rawH)}">${formatMarkdownInline(rawH)}</h3>`;
    } else if (trimmed.startsWith("## ")) {
      closeList();
      const rawH = trimmed.slice(3);
      const chMatch = rawH.match(/^(?:Cap[ií]tulo|Chapter)\s+(\d+)/i);
      const chAttr = chMatch ? ` data-chapter="${chMatch[1]}"` : "";
      html += `<h2 id="${_slugifyHeading(rawH)}"${chAttr}>${formatMarkdownInline(rawH)}</h2>`;
    } else if (trimmed.startsWith("# ")) {
      closeList();
      const rawH = trimmed.slice(2);
      html += `<h1 id="${_slugifyHeading(rawH)}">${formatMarkdownInline(rawH)}</h1>`;
    } else if (/^[-*+]\s+/.test(trimmed) && (listType === "ol" || listType === "ul") && /^\s{2,}/.test(rawLine) && html.endsWith("</li>")) {
      // Sub-lista con sangría dentro del último elemento de la lista (sin reiniciar la numeración)
      const item = `<li>${formatMarkdownInline(trimmed.replace(/^[-*+]\s+/, ""))}</li>`;
      if (html.endsWith("</ul></li>")) html = html.slice(0, -"</ul></li>".length) + item + "</ul></li>";
      else html = html.slice(0, -"</li>".length) + `<ul>${item}</ul></li>`;
    } else if (/^[-*+]\s+/.test(trimmed)) {
      if (listType !== "ul") {
        closeList();
        html += "<ul>";
        listType = "ul";
      }
      html += `<li>${formatMarkdownInline(trimmed.replace(/^[-*+]\s+/, ""))}</li>`;
    } else if (/^\d+\.\s+/.test(trimmed)) {
      if (listType !== "ol") {
        closeList();
        const startNum = parseInt(trimmed, 10);
        html += startNum > 1 ? `<ol start="${startNum}">` : "<ol>";
        listType = "ol";
      }
      html += `<li>${formatMarkdownInline(trimmed.replace(/^\d+\.\s+/, ""))}</li>`;
    } else {
      closeList();
      html += `<p>${formatMarkdownInline(trimmed)}</p>`;
    }
  }
  closeList();
  flushQuote();
  if (inCode) flushCode();
  return html;
}

function downloadSpectrumCsv() {
  const pts = STATE.pointSpectrum || (STATE.cube && STATE.cube.spectrum) || [];
  const dr1 = (STATE.dr1Spectrum && STATE.dr1Spectrum.channels) || [];
  if (!pts.length && !dr1.length) return;
  const rows = ["# SPHEREx SkyChrono · ePSF photometry per L2b exposure (flux in uJy, 1-sigma errors incl. 3% systematic)"];
  rows.push("source,obs_id,band,mjd,date_iso,wavelength_um,bandwidth_um,flux_ujy,err_ujy,snr,ab_mag,upper_limit_ujy,quality,flags");
  for (const p of pts) {
    rows.push(["L2b", p.obs_id, p.band, p.mjd, p.date_iso, p.wavelength_um, p.bandwidth_um, p.flux_ujy ?? "", p.err_ujy ?? "", p.snr ?? "", p.ab_mag ?? "", p.upper_limit_ujy ?? "", p.quality, (p.flags || []).join("|")].join(","));
  }
  for (const c of dr1) {
    rows.push(["DR1_cube", `ch${c.ch}`, c.band, "", "", c.wavelength_um, c.bandwidth_um, c.flux_ujy ?? "", c.err_ujy ?? "", c.snr ?? "", c.ab_mag ?? "", c.upper_limit_ujy ?? "", c.quality, (c.flags || []).join("|")].join(","));
  }
  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `spherex_spectrum_${STATE.ra.toFixed(3)}_${STATE.dec.toFixed(3)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportBlinkGif() {
  const params = new URLSearchParams({
    ra: STATE.ra.toFixed(6),
    dec: STATE.dec.toFixed(6),
    fov: STATE.fov.toFixed(3),
    bands: STATE.bands.join(","),
    max_per_epoch: String(STATE.maxPerEpoch),
    gap_days: String(STATE.gapDays),
  });
  appendAstrometryParams(params);
  window.open(`/api/gif?${params.toString()}`, "_blank");
}

function shareCurrentUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set("ra", STATE.ra.toFixed(5));
  url.searchParams.set("dec", STATE.dec.toFixed(5));
  url.searchParams.set("fov", STATE.fov.toFixed(2));
  url.searchParams.set("bands", STATE.bands.join(","));
  url.searchParams.set("mode", STATE.mode);
  url.searchParams.set("lang", STATE.lang);
  navigator.clipboard.writeText(url.toString());
  const btn = document.getElementById("i18nBtnShare");
  const prev = btn.textContent;
  btn.textContent = STATE.lang === "en" ? "Copied! ✓" : "¡Copiado! ✓";
  setTimeout(() => {
    btn.textContent = prev;
  }, 1800);
}

function updateColorbarGradient() {
  const el = document.getElementById("colorbarGradient");
  if (!el) return;
  if (STATE.cmap === "viridis") {
    el.style.background = "linear-gradient(90deg, #440154, #3b528b, #21918c, #5ec962, #fde725)";
  } else if (STATE.cmap === "cyanHot") {
    el.style.background = "linear-gradient(90deg, #020617, #0284c7, #00f5d4, #e0f2fe, #ffffff)";
  } else if (STATE.cmap === "grayscale") {
    el.style.background = "linear-gradient(90deg, #ffffff, #888888, #000000)";
  } else {
    el.style.background = "linear-gradient(90deg, #000004, #420a68, #932667, #dd513a, #fca50a, #fcffa4)";
  }
}

function showLoading(show) {
  const el = document.getElementById("loadingOverlay");
  if (el) el.hidden = !show;
}

function setStatus(text, busy) {
  const st = document.getElementById("statusText");
  const dot = document.getElementById("statusDot");
  if (st) st.textContent = text;
  if (dot) dot.classList.toggle("busy", Boolean(busy));
}
