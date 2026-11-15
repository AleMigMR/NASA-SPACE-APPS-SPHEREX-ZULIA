# Documentación Integral — SPHEREx SkyChrono (ES)

**Explorador de cielo completo y de series temporales para SPHEREx: blinking multi-época de imágenes L2b reales, fotometría con la ePSF oficial, espectros de 0.75–5.0 µm y verificación de candidatos en movimiento o variables · Reto *"Planet X and SPHEREx"* (NASA Space Apps Challenge 2026 · Delegación Zuliana de Astronomía).**

> [!NOTE]
> Documento maestro único con **Conceptos Básicos**, **Manual de Usuario**, **Métodos y API**, **Validación, Seguridad y Despliegue** y **Objetivos y Referencias**. Usa **🌐 Ver en English** para la versión en inglés.
>
> **Principio de rigor:** todo número que muestra la app proviene de un producto oficial (SPHEREx en IRSA/AWS, Gaia DR3, AllWISE, SIMBAD, JPL Horizons) o de un cálculo documentado aquí. Si un dato no existe o no es fiable (saturación, baja S/N, sin paralaje), la app lo dice en lugar de inventarlo.

## Índice Rápido

- [Capítulo 1 · Conceptos Básicos y Misión SPHEREx](#capitulo-1-conceptos-basicos-y-mision-spherex)
- [Capítulo 2 · Manual de Usuario](#capitulo-2-manual-de-usuario)
- [Capítulo 3 · Métodos, Matemática y API](#capitulo-3-metodos-matematica-y-api)
- [Capítulo 4 · Validación, Seguridad y Despliegue](#capitulo-4-validacion-seguridad-y-despliegue)
- [Capítulo 5 · Objetivos, Referencias y DOIs](#capitulo-5-objetivos-referencias-y-dois)

---

## Capítulo 1 · Conceptos Básicos y Misión SPHEREx

### 1.1 ¿Qué es SPHEREx?
**SPHEREx** (*Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer*) es un observatorio de la NASA lanzado el **12 de marzo de 2025** que observa todo el cielo desde una órbita polar heliosíncrona (~7037 km de semieje). Desde el **1 de mayo de 2025** hace cuatro relevamientos completos en 25 meses. Su telescopio de 20 cm reparte la luz entre **6 detectores H2RG**, cada uno con un **filtro lineal variable (LVF)**: la longitud de onda que mide un píxel depende de su posición en el detector. Los píxeles miden **6.15″** y cada exposición dura **113.58 s**.

| Detector | Rango (µm) | Resolución R | Qué se ve mejor |
| :--- | :---: | :---: | :--- |
| **D1** | 0.744 – 1.116 | 39 | Continuo estelar; la línea atmosférica de He I a 1.083 µm contamina el fondo |
| **D2** | 1.099 – 1.651 | 41 | H₂O (1.4 µm) y CH₄ (1.6 µm) en atmósferas frías |
| **D3** | 1.636 – 2.421 | 41 | H₂O (1.9 µm), CH₄ (2.2 µm), CO (2.3 µm) |
| **D4** | 2.423 – 3.822 | 35 | H₂O (2.7–3.1 µm, gas o hielo), CH₄ (3.3 µm), PAH (3.29 µm) |
| **D5** | 3.809 – 4.420 | 112 | Ventana de 4 µm, CO₂ (4.27 µm, gas o hielo) |
| **D6** | 4.412 – 5.002 | 128 | CO (4.67 µm); pico de emisión de las enanas Y |

*Fuente: SPHEREx Explanatory Supplement v2.1, Tabla 2.* El cubo All-Sky DR1 agrupa los datos en **102 canales** (17 por detector); los canales 50–51, junto al divisor dicroico, están vacíos en DR1.

### 1.2 Cómo se detecta el movimiento y la variabilidad
- **Blink:** SPHEREx vuelve a observar cada zona aproximadamente cada 6 meses (y con más frecuencia cerca de los polos eclípticos). Alternar las épocas permite ver qué cambia.
- **Diferencia ($E_n - E_1$):** un objeto que se mueve deja un **dipolo** (negativo donde estaba, positivo donde está); un objeto que cambia de brillo deja un residuo en el mismo sitio.
- **Cuidado con el submuestreo y el LVF:** con píxeles de 6.15″ la PSF está submuestreada (FWHM ≈ 7.5″), así que el pico de una estrella cambia con su fase dentro del píxel. Además, cada exposición mide la fuente a una λ distinta. Por eso la diferencia de imágenes **solo propone** candidatos: la app los verifica con fotometría ePSF exposición por exposición (capítulo 3).
- **`ZODI`:** cada imagen L2b incluye un modelo de luz zodiacal que **no** está restado en `IMAGE`; la app lo resta.
- **`FLAGS`:** bits oficiales por píxel (Tabla 16 del Suplemento). `SOURCE` (bit 21) solo indica que el píxel pertenece a una fuente catalogada y **nunca** se enmascara.

### 1.3 Hielo y gas no son lo mismo
Las bandas de H₂O, CH₄, CO₂ y CO aparecen de dos formas:
- **Gas** en atmósferas frías: enanas marrones como WISE 0855 o Eps Indi B, enanas M y gigantes tipo Mira. Es el caso de todos los objetivos del reto.
- **Hielo** en granos de polvo: estrellas de fondo vistas a través de nubes moleculares (p. ej. Elias 16 tras la nube de Tauro) y protoestrellas. Es el objetivo científico de SPHEREx con su lista de objetivos SPLICES.

La app mide una **profundidad aparente de banda** y explica cuál de los dos casos aplica; nunca afirma "hielo" en una enana marrón.

### 1.4 Planos de referencia del visor 360°
El universo no tiene un "arriba" absoluto. El visor ofrece tres planos estándar: **Galáctico** $(l, b)$, **Eclíptico** $(\lambda, \beta)$ (el de la órbita terrestre y de los relevamientos de SPHEREx) y **Ecuatorial ICRS** (RA, Dec), el de Gaia, SIMBAD y el Minor Planet Center.

---

## Capítulo 2 · Manual de Usuario

### 2.1 Cabecera y objetivos de referencia
- **🏛️ Recursos NASA / IRSA:** enlaces oficiales del reto (IRSA, notebooks de tutoriales, herramientas oficiales de IRSA como el Data Explorer y MOST, WiseView, Gaia DR3 en MAST, recursos de la Agencia Espacial Canadiense) y enlaces en vivo a la coordenada actual.
- **📐 Reporte MPC:** borrador en el formato oficial de dos líneas para satélites (código de SPHEREx **288**). Solo se genera para candidatos con movimiento confirmado y sin contrapartida estelar; en otro caso la ventana explica por qué está vacío.
- **🔗 Compartir** y **🎞️ GIF:** enlace reproducible y animación de las épocas.
- **Objetivos de referencia:** al elegir uno, la app centra el campo en su **posición propagada a la época 2026.0** y propaga su posición a la fecha de **cada** exposición para medirlo. El tooltip explica a qué época corresponden las coordenadas de referencia (p. ej. las de WISE 0855 del enunciado son de 2010.6).

### 2.2 Visor 360° (cubo All-Sky DR1)
Tres vistas sincronizadas: **Hammer-Aitoff** (proporción real 2:1), **globo 3D** y **Aladin Lite HiPS**. El mapa usa los PNG oficiales de visualización (estiramiento fijo asinh 0–40 MJy/sr): sirve para orientarse, no para medir. Doble clic en cualquier punto abre las exposiciones multi-época de esa zona.

### 2.3 Visor de imágenes y pantalla completa
- **Modos:** Blink, Diferencia, RGB cronológico (R = última época, B = primera), Co-adición y Cortina A/B.
- **Pantalla completa:** botón **⛶** junto a los controles de zoom o tecla **F**; **Esc** para salir. La imagen se dibuja siempre con píxeles cuadrados (sin deformar ángulos ni distancias).
- **Ratón:** arrastrar mueve el campo (al soltar se descarga el campo vecino), la rueda hace zoom anclado al cursor, un clic mide la fuente bajo el cursor y un doble clic recentra.
- **Teclado:** `Espacio` reproduce o pausa, `← / →` cambian de época y `F` activa la pantalla completa.
- **Marcas:** ✚ es la **posición predicha** del objetivo en cada época (Gaia DR3 o literatura más movimiento propio). Las zonas grises son píxeles sin datos L2b reales. Los candidatos muestran ✔ (confirmado por la ePSF), ✖ (no confirmado) o ? (no verificable).
- **Movimiento medido:** la ecuación 5 del panel de matemática y el análisis del copiloto comparan el desplazamiento que **mide SPHEREx** entre la primera y la última visita con el que predice el catálogo para las mismas fechas.
- **Fuentes del campo:** se identifican con Gaia DR3 o AllWISE; la distancia solo aparece si hay paralaje con π/σ ≥ 5 o una distancia publicada.
- **📏 Medir A↔B:** la separación angular y el ángulo de posición son exactos; la distancia 3D solo se calcula si ambas fuentes tienen distancia medida.

### 2.4 Panel derecho
- **Espectro del objetivo:** cada punto es una exposición L2b medida con la ePSF a su λ real (en µJy, error 1σ). ▼ indica un límite superior a 3σ y × una medición saturada. La línea amarilla es el espectro de 102 canales de la co-adición DR1 en la misma posición.
- **Profundidad aparente de banda:** τ de H₂O 3.0, CH₄ 3.3, CO₂ 4.27 y CO 4.67 µm sobre el espectro DR1, con su error y su interpretación (gas o hielo).
- **Curva de luz por canal:** flujo / mediana para cada canal (misma λ). Solo son comparables los puntos del mismo color.
- **Copiloto:** usa Gemini (si hay clave) o un motor local determinista. En ambos casos recibe solo telemetría medida y tiene prohibido inventar valores.

### 2.5 Calidad de datos
El panel **🛡️ Calidad de datos** resume, con datos del cubo actual: origen (L2b o DR1 estático), luz zodiacal restada, porcentaje de píxeles rechazados (lista oficial), PSF usada (ePSF oficial o gaussiana), saturación del objetivo, satélites y artefactos (`STREAK`, `SATELLITE_HALO`, `BLOOM`, `SNOWBALL`) y avisos de borde dicroico y He I.

---

## Capítulo 3 · Métodos, Matemática y API

### 3.1 Flujo de datos
1. **Búsqueda de exposiciones:** IRSA TAP (`spherex.artifact ⋈ spherex.plane`). Si TAP falla se usa **IRSA SIA** con las colecciones `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3` y `spherex_qr3_deep`, el método de los tutoriales oficiales. Un servicio que acaba de fallar no se vuelve a esperar durante 2 minutos. Si ninguno responde, para los cinco objetivos del reto se usa la **lista oficial de exposiciones guardada** en `data/spherex_exposure_index/` (la respuesta real de IRSA SIA, con su fecha de consulta), así que el blink sigue funcionando: IRSA solo hace falta para saber qué imágenes cubren un punto, porque las imágenes mismas se leen de AWS S3. Una misma observación publicada en varias versiones se usa una sola vez (prioridad DR1 > QR3 > QR2).
2. **Recortes:** lectura parcial (HTTP Range) de `s3://nasa-irsa-spherex/` con respaldo en el servicio de recortes IBE de IRSA. Se leen `IMAGE`, `ZODI`, `FLAGS`, `VARIANCE`, la tabla `WCS-WAVE`, la fila de la **ePSF** de la zona del detector (~9 KB; la zona se elige con sus columnas `XCENTER`/`YCENTER`, así que no le afecta el error de cabecera de la PSF de QR1/QR2 descrito por IRSA) y la cabecera completa: `MJD-AVG`, `PSF_FWHM` y la posición geocéntrica de la nave.
3. **Sin exposiciones L2b** (un punto sin lista guardada mientras IRSA no responde): se muestra **una** imagen estática del cubo All-Sky DR1, claramente señalada, y la app reintenta IRSA automáticamente cada ~2 minutos. No hay blink ni diferencia, porque el cubo no tiene información temporal.

### 3.2 Fórmulas implementadas
1. **Imagen limpia:** $I = \text{IMAGE} - \text{ZODI}$. Para visualizar se rechazan los píxeles con la lista oficial usada al construir el cubo DR1: `TRANSIENT, SUR_ERROR, NONFUNC, DICHROIC, MISSING_DATA, HOT, COLD, PHANMISS, NONLINEAR, PERSIST, CROSSTALK, STREAK, BLOOM, SNOWBALL, HALO, SATELLITE_HALO`.
2. **Posición del objetivo:** $(\alpha, \delta)(t)$ = `SkyCoord.apply_space_motion` con $\mu_{\alpha*}$, $\mu_\delta$, $\varpi$ y $v_r$ desde la época de la astrometría hasta el `MJD-AVG` de cada exposición. La paralaje anual (≤ 0.55″) se desprecia por ser menor que 0.1 píxel. El **desplazamiento medido** se obtiene de la posición media de cada visita (visitas separadas más de 30 días) con su error estándar: con dos visitas se restan, y con tres o más se ajusta un movimiento lineal ponderado. Se compara con el desplazamiento predicho entre las mismas fechas y se informa la diferencia en σ.
3. **Fotometría PSF forzada** (Suplemento sec. 3.3): $d_j = F\,P_{\text{eff}}(x_j - x_\star) + \sum_k F_k P_{\text{eff}}(x_j - x_k) + B$, resuelta por mínimos cuadrados ponderados $\theta = (A^T W A)^{-1} A^T W d$ con $W = 1/\text{VARIANCE}$. Las fuentes Gaia a menos de 20″ ($k$) se ajustan a la vez (*deblending*). Los píxeles se enmascaran con la máscara fotométrica oficial: `SUR_ERROR, NONFUNC, MISSING_DATA, HOT, COLD, NONLINEAR, PERSIST, BLOOM, SNOWBALL, HALO, SATELLITE_HALO`.
4. **Flujo y error:** $F_{\mu\text{Jy}} = F\,\Omega_{\text{pix}}\,10^{12}$, con $\Omega_{\text{pix}}$ obtenido del jacobiano del WCS con distorsión SIP (≈ 8.86 × 10⁻¹⁰ sr; el valor nominal $(6.15'')^2$ es 8.890 × 10⁻¹⁰ sr). El error es $\sigma^2 = \sigma_{\text{stat}}^2 + (0.03F)^2$. La calidad del ajuste es $\langle|p-m|/\sigma\rangle$ en r ≤ 2.5 px. Si S/N < 3 se informa un **límite superior** $F + 3\sigma$.
5. **Magnitud AB:** $m_{\text{AB}} = 23.9 - 2.5\log_{10}F_{\mu\text{Jy}}$, con $\sigma_m = 1.0857/(S/N)$, solo para detecciones.
6. **Longitud de onda:** $\lambda(x,y)$ por interpolación bilineal de `WCS-WAVE` en la posición del detector donde cae la fuente. Error frente a los archivos oficiales `CWAVE`: ≤ 5 % del ancho de banda (verificado).
7. **Borde del detector y del filtro:** una medición a menos de 32 px del borde del detector, o con λ fuera del rango nominal del detector (p. ej. 5.006 µm en D6), se marca con aviso y no cuenta para la variabilidad: en WISE 0855, una de esas mediciones daba ×4.8 el flujo real de una estrella vecina. **Saturación:** una medición se marca *saturada* si hay `OVERFLOW`, `NONLINEAR` o `BLOOM` en r ≤ 2.5 px, o si faltan ≥ 2 píxeles del núcleo (r ≤ 1.2 px). Su flujo no se informa, pero su **posición** se mide con el centroide de los píxeles `OVERFLOW` a ≤ 4 px de la posición predicha (solo astrometría). Como la forma de la mancha saturada cambia con la orientación de la nave, cada visita lleva un error sistemático de 0.7″ por eje, medido con la dispersión entre las 8 visitas de R Dra.
8. **Candidatos:** $\Delta I = E_n - E_1$ y $\sigma_{\text{MAD}} = 1.4826\,\text{med}|\Delta I - \text{med}\,\Delta I|$, con umbral de 5σ y solo en píxeles con datos reales en ambas épocas. Cada candidato se **verifica con la ePSF**:
   - *movimiento confirmado* si los centroides de la primera y la última época difieren en ≥ 3σ y ≥ 0.3 píxeles nativos;
   - *variabilidad confirmada* si el flujo cambia ≥ 5σ entre mediciones del **mismo canal** en al menos **dos pares independientes** con el mismo signo (un solo par queda como *posible variabilidad*);
   - *no confirmado* en cualquier otro caso. Las mediciones saturadas (`OVERFLOW`, `NONLINEAR` o `BLOOM` en r ≤ 2.5 px) no cuentan: si solo hay mediciones saturadas, el candidato se marca como *artefacto de estrella saturada*, porque el *blooming* cambia con la orientación de la nave y simula movimientos de varios segundos de arco (comprobado en RW Aur y R Dra).
9. **Curva de luz:** las mediciones se agrupan por canal DR1; la variabilidad se evalúa con $\chi^2_\nu$ respecto a un flujo constante y con el mayor cambio en σ dentro de cada canal.
10. **Espectro DR1:** fotometría de apertura en el cubo All-Sky (r = 25.8″, fondo en un anillo de 51–90″, $\Omega$ HEALPix de orden 14 = 3.901 × 10⁻⁹ sr). Un canal se marca saturado si el núcleo no tiene datos, si `NHITS` = 0, o si hay una caída de `NHITS` cuando el detector muestra saturación en otros canales. Se avisa cuando hay fuentes Gaia dentro de la apertura.
11. **Profundidad aparente de banda:** $\tau = \ln F_{\text{cont}} - \ln F_{\text{banda}}$, con un continuo de **ley de potencias** (recta en log F – log λ) ajustado a ventanas a ambos lados de la banda y un error sistemático mínimo de 0.04. Si el muestreo no basta, τ = no medible. Con este continuo, una cola de Rayleigh–Jeans sin absorción da τ = 0.00 (un continuo lineal habría dado un τ falso de ~0.19 a 3 µm). Un τ **negativo** a ≥ 3σ significa que la banda está por encima del continuo interpolado (por ejemplo, el pico de 4 µm de las enanas T): la app lo indica y no lo interpreta como absorción.
12. **Distancias:** $d = 1000/\varpi$ pc solo si $\varpi/\sigma_\varpi \ge 5$ (Gaia DR3) o a partir de la distancia publicada de los objetivos de referencia. La distancia 3D entre A y B, $D = \sqrt{d_A^2 + d_B^2 - 2 d_A d_B \cos\theta}$, solo se calcula si ambas existen.
13. **MPC:** dos registros de 80 columnas: «S» con la posición medida por la ePSF y «s» con el vector geocéntrico de SPHEREx en km. Ese vector se obtiene de `X/Y/Z_SC_START` y `_END` por interpolación de Hermite a mitad de exposición. Código de observatorio **288**.

### 3.3 HEALPix
El cubo DR1 se organiza en teselas HEALPix NESTED de orden 5 (512×512 píxeles de 12.9″). La conversión (α, δ) → índice sigue el algoritmo de referencia de HEALPix (Górski et al. 2005) y está validada contra `astropy-healpix` en 200 000 posiciones aleatorias sin discrepancias.

### 3.4 API REST (`app.py`)

| Método | Ruta | Función |
| :--- | :--- | :--- |
| `GET` | `/` | Interfaz web |
| `GET · POST · DELETE` | `/api/targets` | Objetivos (la astrometría oficial no es editable) |
| `GET` | `/api/resolve?q=` | Coordenadas o nombre (Sesame/SIMBAD) propagados a 2026.0; reconoce las coordenadas antiguas de los objetivos |
| `GET` | `/api/cube` | Cubo multi-época. Parámetros: `ra, dec, fov, bands, max_per_epoch, gap_days, release, target_id` o `pmra, pmdec, plx, ast_ra, ast_dec, ast_epoch` |
| `GET` | `/api/point_spectrum` | Fotometría ePSF por exposición en el píxel elegido |
| `GET` | `/api/dr1_spectrum` | Espectro de 102 canales del cubo DR1, profundidades de banda y avisos |
| `GET` | `/api/catalogs` | Gaia DR3 (MAST → VizieR) y AllWISE (VizieR → IRSA Gator) proyectados en la grilla |
| `GET` | `/api/gif` | GIF de las épocas |
| `POST` | `/api/ai/chat` | Copiloto (clave de Gemini en la cabecera `x-goog-api-key`, nunca en la URL) |
| `GET` | `/api/docs?lang=` | Esta documentación |
| `GET` | `/api/spherex-allsky-map` | Mapa equirectangular del cubo DR1 (visualización) |
| `GET` | `/api/hips/spherex/{canal}/{ruta}` | Proxy HiPS para Aladin Lite |
| `GET` | `/static/*`, `/docs/*` | Archivos estáticos |

---

## Capítulo 4 · Validación, Seguridad y Despliegue

### 4.1 Validación con datos reales
- **Fotometría:** 12 estrellas no saturadas de un campo L2b real (D2, λ ≈ 1.30–1.38 µm) dieron una razón SPHEREx / 2MASS (interpolada entre J y H) de **1.03** de media (mediana 1.02) con 3 % de dispersión. Los centroides de Gaia DR3 propagados cayeron a 0.0–0.1 píxeles de las estrellas medidas.
- **Movimiento medido con exposiciones L2b reales:**
   - **Barnard** (saturada; 28 exposiciones, 3 visitas): el centroide del núcleo saturado cae a una mediana de 1.2″ (0.19 px) de la posición predicha. SPHEREx mide **6.59 ± 1.00″** (AP 355°) entre 2025-08-25 y 2026-03-30, frente a 6.19″ (AP 356°) predichos por Gaia DR3 (0.4σ).
   - **Epsilon Indi B** (no saturada; 32 exposiciones, 6 visitas): **6.88 ± 0.25″** (AP 122°) en 519 días, frente a 6.65″ predichos (1.0σ).
   - **RW Aur** y **R Dra** (saturadas, casi sin movimiento propio): 0.56 ± 1.23″ y 1.82 ± 0.83″, ambos compatibles con cero.
- **Verificación de candidatos:** una fuente sintética de 5 mJy que se movía 12″, inyectada en exposiciones reales, se recuperó como *movimiento confirmado 12.0″ ± 0.4″*. Las estrellas estáticas cuyo pico cambiaba por la fase subpíxel quedaron como *no confirmadas*.
- **Objetivos del reto:** ver la tabla del capítulo 5 y la herramienta `tools/validate_targets.py`.
- **Pruebas unitarias:** `python -m pytest tests/` (o `python tests/test_science.py`) comprueba HEALPix, propagación de WISE 0855 a la época AllWISE, bits oficiales, punto cero AB, formato MPC, ausencia de sesgo en τ y recuperación de flujo inyectado.

### 4.2 Seguridad
- `.env` está en `.gitignore`. La clave de Gemini viaja en la cabecera `x-goog-api-key` y nunca en la URL, para que no quede en registros. Los mensajes de error no reproducen la petición.
- Sin clave, todas las funciones científicas siguen operativas y el copiloto usa el motor local.

### 4.3 Instalación y despliegue
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py                      # http://localhost:8050
```
Variables opcionales: `GEMINI_API_KEY`, `GEMINI_MODEL`, `PORT`, `SPHEREX_TAP_TIMEOUT` (s, por defecto 30), `SPHEREX_SIA_TIMEOUT` (s, por defecto 60) y `SPHEREX_PREWARM=0` (desactiva la precarga). Para Docker: `docker build -t spherex-skychrono .` y `docker run -p 8050:8050 spherex-skychrono`.

### 4.4 Limitaciones conocidas
- **Saturación:** Barnard (J ≈ 5.2), RW Aur (K ≈ 7) y R Dra saturan SPHEREx en casi todos los canales. Su **posición** se mide con el núcleo saturado y su movimiento se ve en el blink, pero sus flujos no son fiables.
- **Mezcla de fuentes:** en 2025–2026 WISE 0855 pasa a **8″** de la estrella Gaia DR3 5756956644387831296 (G = 16.3). Con píxeles de 6.15″ se mezclan; la fotometría L2b separa ambas fuentes con la ePSF, pero el espectro DR1 (apertura de 25.8″) incluye a la vecina.
- **WISE 0855** es débil en SPHEREx (≈ 0.5 mJy a 4.6 µm, W2 ≈ 13.9): espera S/N bajo por exposición e invisibilidad por debajo de ~3.5 µm.
- **Planeta X / Nueve** es hipotético y nadie lo ha detectado. A ~500 UA su movimiento paraláctico sería de ~7″ por día. Entre visitas separadas seis meses saldría de un campo de 0.1°, así que debe buscarse comparando exposiciones de una misma visita (días). Para objetos del Sistema Solar con órbita conocida, la herramienta oficial **MOST** de IRSA encuentra las imágenes de SPHEREx que los cubren.
- **Cubo DR1:** píxeles de 12.9″ y sin información temporal. Sus PNG HiPS sirven solo para visualizar.

### 4.5 Texto de presentación (EN)
> **SPHEREx SkyChrono** is an open-source time-domain explorer for NASA's SPHEREx survey. It blinks real Level-2 spectral images retrieved from IRSA (TAP/SIA) and AWS S3, propagates catalogue astrometry to every exposure, measures fluxes with the official ePSF (variance-weighted forced photometry with Gaia deblending) and verifies every difference-image candidate before calling it motion or variability. It shows 0.75–5 µm spectra from individual exposures and from the DR1 all-sky cube, flags saturation and blending explicitly, and drafts MPC satellite-format astrometry (code 288) only for confirmed movers without a stellar counterpart.

---

## Capítulo 5 · Objetivos, Referencias y DOIs

### 5.1 Objetivos del reto (astrometría verificada en SIMBAD / Gaia DR3)

| Objetivo | Posición de referencia | Mov. propio (mas/año) | Distancia | En SPHEREx |
| :--- | :--- | :--- | :--- | :--- |
| **WISE 0855−0714** (Y) | J2000 133.81891°, −7.24705° (Kirkpatrick+2021) · coordenadas NASA = época 2010.6 | −8123.7, +673.2 | 2.28 pc (ϖ = 439.0 ± 2.4 mas) | En 2026 está a **~2.1′** de las coordenadas del enunciado. L2b: detectada en 9 de 19 exposiciones de 4.4–5.0 µm (S/N ≈ 4) a 1.1″ de la posición predicha. A 8″ de una estrella G = 16.3: la ePSF las separa, pero en DR1 la vecina domina por debajo de 3.5 µm y a 4.6 µm da 0.58 ± 0.32 mJy (sin detección significativa). |
| **Barnard's Star** (M4V) | J2000 269.45208°, +4.69336° (Gaia DR3) | −801.6, +10362.4 | 1.828 pc | **Saturada** en 28/28 exposiciones L2b y 99/100 canales DR1: flujo no medible. Posición medida a 1.2″ de la predicha; SPHEREx mide **6.59 ± 1.00″** en 217 d frente a 6.19″ predichos. |
| **Epsilon Indi Ba/Bb** (T1 + T6) | J2000 331.04415°, −56.78284° (Gaia DR3) | +3982.0, −2466.8 | 3.64 pc (sistema ε Ind) | No saturada: 32/32 detecciones L2b (S/N ≈ 32); SPHEREx mide **6.88 ± 0.25″** en 519 d frente a 6.65″. SED de enana T en DR1: 31 mJy (1.25 µm), 36 (1.66), 25 (2.19), 8 (3.29), 63 (4.0) y 18 mJy (4.6 µm); **τ(CH₄ 3.3 µm) = 1.51 ± 0.05** y τ(H₂O 3.0 µm) = 0.52 ± 0.05 (gas). |
| **RW Aurigae A** (T Tauri) | Gaia DR3 2016.0: 76.95608°, +30.40120° | +2.6, −27.4 | 156 pc | **Saturada** en 24/24 exposiciones L2b y ~48 canales DR1. Un falso movimiento de 9.5″ sobre su *blooming* se marca como artefacto. |
| **R Draconis** (Mira, P ≈ 245.6 d) | Gaia DR3 2016.0: 248.16738°, +66.75501° | −20.6, +6.1 | ~800 pc (paralaje de Mira, con cautela) | **Saturada** en 64/64 exposiciones L2b (8 visitas) y en los 100 canales DR1. Sus artefactos de *blooming* se marcan como tales. |

La herramienta `tools/validate_targets.py` repite esta validación con exposiciones L2b reales: desplazamiento medido frente al predicho, detecciones, saturación y candidatos.

### 5.2 Hitos del mapa 360°
Las coordenadas se verificaron en SIMBAD y JPL Horizons. **Elias 16** está en 69.912°, +26.191° (gigante K1III de fondo tras la nube de Tauro). **3I/ATLAS** se muestra en su posición geocéntrica del 2025-08-08: SPHEREx lo observó del 1 al 15 de agosto de 2025 (Lisse et al. 2026) y se mueve ~1° por día. Se eliminó un supuesto "candidato a Planeta X" que tenía coordenadas y parámetros inventados.

### 5.3 Referencias
1. SPHEREx Explanatory Supplement v2.1 (2026-11-10): https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf
2. Archivo SPHEREx en IRSA: https://irsa.ipac.caltech.edu/Missions/spherex.html
3. Tutoriales oficiales: https://caltech-ipac.github.io/irsa-tutorials/spherex/
4. Recursos del reto: https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=resources
5. Gaia DR3 en MAST: https://archive.stsci.edu/missions-and-data/gaia
6. WiseView: http://byw.tools/wiseview
7. MPC, formato de observaciones desde satélite: https://www.minorplanetcenter.net/iau/info/SatelliteObs.html (SPHEREx = código 288)
8. Kirkpatrick, J. D. et al. 2021, ApJS 253, 7 (WISE 0855). Luhman, K. L. 2014, ApJL 786, L18. Luhman, K. L. et al. 2024, AJ 167, 5.
9. King, R. R. et al. 2010, A&A 510, A99 (ε Indi Ba/Bb).
10. Rustamkulov, Z. et al. 2026, *SPHEREx 0.75 to 5 µm Spectra for a Sequence of Nearby Brown Dwarfs*, arXiv:2607.00543.
11. Lisse, C. M. et al. 2026, ApJL 1000, L52 (3I/ATLAS con SPHEREx).
12. Górski, K. M. et al. 2005, ApJ 622, 759 (HEALPix).
13. Artículos canónicos de SPHEREx (según IRSA): misión, Bock et al. 2026, ApJ 999, 139; pipeline, Akeson et al. 2026, ApJS 285, 67; instrumento y calibración, Korngut et al. 2026, arXiv:2603.29835; simulador del cielo, Crill et al. 2025, ApJS 281, 10.

### 5.4 DOIs de los datos
- SPHEREx DR1 Spectral Images: [10.26131/IRSA678](https://doi.org/10.26131/IRSA678)
- SPHEREx DR1 Spectral All-Sky Cube: [10.26131/IRSA679](https://doi.org/10.26131/IRSA679)
- SPHEREx Quick Release Spectral Images – QR3: [10.26131/IRSA662](https://doi.org/10.26131/IRSA662)
- SPLICES (SPHEREx Target List of Ice Sources): [10.26131/IRSA554](https://doi.org/10.26131/IRSA554)

> *Agradecimiento requerido:* This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.

---

*Documentación Integral v4.0 · **SPHEREx SkyChrono** · Delegación Zuliana de Astronomía · NASA Space Apps Challenge 2026*
