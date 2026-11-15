"""
Pruebas de rigor científico (no requieren red). Ejecutar con:
    python -m pytest tests/        (o)        python tests/test_science.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy.wcs import WCS
import astropy.units as u

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SPHEREX_PREWARM", "0")
import spherex_engine as se  # noqa: E402


def test_healpix_nested_reference_values():
    # Valores de referencia calculados con astropy-healpix (NESTED, nside = 32)
    cases = {
        (60.8109955, 51.3404038): 445,
        (133.79513, -7.24515): 10226,
        (269.4485, 4.7394): 7945,
        (331.0689, -56.7938): 11391,
        (76.9565, 30.4014): 277,
        (248.1669, 66.7549): 2928,
    }
    for (ra, dec), ipix in cases.items():
        assert se.ang2pix_nest_scalar(32, ra, dec) == ipix, (ra, dec)


def test_healpix_matches_astropy_healpix_if_available():
    try:
        from astropy_healpix import HEALPix
    except ImportError:  # dependencia opcional de desarrollo
        return
    rng = np.random.default_rng(3)
    ra = rng.uniform(0, 360, 50000)
    dec = np.degrees(np.arcsin(rng.uniform(-1, 1, 50000)))
    for nside in (32, 512):
        ref = HEALPix(nside=nside, order="nested").lonlat_to_healpix(ra * u.deg, dec * u.deg)
        f, ix, iy = se.ang2pix_nest_vec(nside, ra, dec)
        assert np.all(f * nside * nside + se._interleave_bits(ix, iy) == ref)


def test_wise0855_nasa_coordinates_are_allwise_epoch():
    """Las coordenadas del enunciado NASA corresponden a la época AllWISE (MJD 55412.3 ≈ 2010.6)."""
    t = se._TARGETS_BY_ID["WISE0855"]
    ra, dec = se.propagate_astrometry(t["astrometry"], 55412.33)
    allwise = SkyCoord(133.7947597 * u.deg, -7.2451456 * u.deg)
    assert SkyCoord(ra * u.deg, dec * u.deg).separation(allwise).arcsec < 1.0
    # En 2026.0 el objeto está a ~2.1′ de esas coordenadas
    ra26, dec26 = se.propagate_astrometry(t["astrometry"], Time(2026.0, format="jyear").mjd)
    assert 115 < SkyCoord(ra26 * u.deg, dec26 * u.deg).separation(allwise).arcsec < 135


def test_nasa_prompt_coordinates_resolve_to_wise0855():
    res = se.parse_coordinates("08h55m10.831s", "-07d14m42.53s")
    assert res.get("preset_id") == "WISE0855"


def test_barnard_proper_motion_scale():
    t = se._TARGETS_BY_ID["Barnard"]
    r0, d0 = se.propagate_astrometry(t["astrometry"], Time(2000.0, format="jyear").mjd)
    r1, d1 = se.propagate_astrometry(t["astrometry"], Time(2026.0, format="jyear").mjd)
    sep = SkyCoord(r0 * u.deg, d0 * u.deg).separation(SkyCoord(r1 * u.deg, d1 * u.deg)).arcsec
    assert abs(sep - 10.393 * 26.0) < 2.0


def test_flag_masks_follow_official_table():
    bit = {f["name"]: f["bit"] for f in se.FLAG_DEFINITIONS}
    assert bit["SOURCE"] == 21 and bit["BLOOM"] == 26 and bit["SATELLITE_HALO"] == 29
    assert not se.PHOT_MASK & (1 << 21)
    assert not se.DISPLAY_REJECT_MASK & (1 << 21)
    assert se.PHOT_MASK & (1 << 26) and se.DISPLAY_REJECT_MASK & (1 << 26)
    assert "PHANTOM" not in bit  # no existe en la Tabla 16 de DR1


def test_ab_zero_point():
    f_ujy = 3631.0e6
    assert abs(se.AB_ZP_UJY - 2.5 * np.log10(f_ujy)) < 2e-3


def test_mpc_satellite_records():
    lines = se.format_mpc_satellite_obs("SPX0001", 60807.007543, 163.5888, 43.6488, [-3700.2265, 2168.3347, 5562.8512])
    assert len(lines) == 2 and all(len(l) == 80 for l in lines)
    l1, l2 = lines
    assert l1[14] == "S" and l2[14] == "s"
    assert l1[15:32] == l2[15:32]
    assert l1[77:80] == "288" and l2[77:80] == "288"
    assert l2[32] == "1"
    assert l2[34] == "-" and l2[40] == "."  # signo en col. 35 y punto decimal en col. 41 (X en km)
    assert l2[46] == "+" and l2[52] == "."
    assert l2[58] == "+" and l2[64] == "."


def test_band_depth_has_no_bias_on_rayleigh_jeans():
    tbl = [{"wavelength_um": float(w)} for w in se.SPHEREX_DR1_WAVELENGTHS_UM]
    pts = [{"wavelength_um": p["wavelength_um"], "flux_ujy": 1e4 * p["wavelength_um"] ** -2,
            "err_ujy": 300.0 * p["wavelength_um"] ** -2, "snr": 33.0, "quality": "good"} for p in tbl]
    for b in se.compute_band_depths(pts):
        assert b["tau"] is not None and abs(b["tau"]) < 0.01
        assert not b["significant"]


def test_psf_model_normalisation():
    ys, xs = np.mgrid[-10:11, -10:11].astype(float)
    g = se.psf_native_model(None, xs, ys, 0.3, -0.2, 1.3)
    assert abs(g.sum() - 1.0) < 0.02
    # ePSF sintética 33×33 con muestreo 5×, normalizada como la oficial (suma = 1)
    fy, fx = np.mgrid[0:33, 0:33]
    e = np.exp(-(((fx - 16) / 5.0) ** 2 + ((fy - 16) / 5.0) ** 2) / (2 * 0.55 ** 2))
    e /= e.sum()
    m = se.psf_native_model(e, xs, ys, 0.0, 0.0, 1.3)
    assert abs(m.sum() - 1.0) < 0.02


def _fake_cut(flux_ujy: float, noise: float = 0.002, seed: int = 1):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [150.0, 2.0]
    w.wcs.crpix = [32.5, 32.5]
    w.wcs.cdelt = [-6.15 / 3600.0, 6.15 / 3600.0]
    ny = nx = 64
    ys, xs = np.mgrid[0:ny, 0:nx]
    x0, y0 = 31.3, 32.6
    om = se.pixel_solid_angle_sr(w, x0, y0)
    P = se.psf_native_model(None, xs, ys, x0, y0, 7.5 / 6.15)
    rng = np.random.default_rng(seed)
    img = (flux_ujy / (om * 1e12) * P + 0.05 + rng.normal(0, noise, (ny, nx))).astype(np.float32)
    ra, dec = [float(v) for v in w.pixel_to_world_values(x0, y0)]
    row = {"obs_id": "TEST_0001_1", "band": "D2", "release": "dr1", "t_min": 60807.0, "uri": "test"}
    cut = {"row": row, "img": img, "var": np.full_like(img, noise ** 2), "flags": np.zeros((ny, nx), dtype=np.int64),
           "wcs": w, "wave_tab": (np.zeros(1), np.zeros(1), np.zeros(1)), "psf": None,
           "meta": {"mjd_avg": 60807.0, "psf_fwhm": 7.5, "x0_det": 0, "y0_det": 0}, "zodi": 0.1, "source": "test"}
    return cut, ra, dec


def test_forced_photometry_recovers_injected_flux():
    cut, ra, dec = _fake_cut(2000.0)
    p = se.forced_photometry_cut(cut, ra, dec, fit_position=True)
    assert p["quality"] in ("good", "warning")
    assert abs(p["flux_ujy"] - 2000.0) < 3 * p["err_ujy"]
    assert p["offset_arcsec"] is not None and p["offset_arcsec"] < 1.6


def test_forced_photometry_reports_upper_limit_for_blank_sky():
    cut, ra, dec = _fake_cut(0.0)
    p = se.forced_photometry_cut(cut, ra, dec, fit_position=False)
    assert p["ab_mag"] is None and p["upper_limit_ujy"] is not None
    assert p["quality"] == "non_detection"


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok", name)
    print(f"{n} pruebas superadas")
