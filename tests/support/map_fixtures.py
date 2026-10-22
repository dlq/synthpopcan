"""Shared synthetic data and assertions for test_map_render.py."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np


def _wgs84_to_lcc(lon_deg: float, lat_deg: float) -> tuple[float, float]:
    """Forward StatCan LCC for test round-trips."""
    a = 6_378_137.0
    f = 1.0 / 298.257_222_101
    e2 = 2 * f - f**2
    e = math.sqrt(e2)
    phi0 = math.radians(63.390675)
    phi1 = math.radians(49.0)
    phi2 = math.radians(77.0)
    lam0 = math.radians(-91.86666666666666)
    E0, N0 = 6_200_000.0, 3_000_000.0  # noqa: N806 - projection notation

    def _m(phi: float) -> float:
        return math.cos(phi) / math.sqrt(1 - e2 * math.sin(phi) ** 2)

    def _t(phi: float) -> float:
        sp = math.sin(phi)
        return math.tan(math.pi / 4 - phi / 2) * ((1 + e * sp) / (1 - e * sp)) ** (
            e / 2
        )

    m1, m2 = _m(phi1), _m(phi2)
    t1, t2 = _t(phi1), _t(phi2)
    n = math.log(m1 / m2) / math.log(t1 / t2)
    F = m1 / (n * t1**n)  # noqa: N806 - projection notation
    rho0 = a * F * _t(phi0) ** n

    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    rho = a * F * _t(phi) ** n
    theta = n * (lam - lam0)
    x = E0 + rho * math.sin(theta)
    y = N0 + rho0 - rho * math.cos(theta)
    return x, y


def _square_ring(n: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """Return a closed square ring with *n* points per side."""
    t = np.linspace(0, 1, n, endpoint=False)
    top = np.column_stack([t, np.ones(n)])
    right = np.column_stack([np.ones(n), 1 - t])
    bottom = np.column_stack([1 - t, np.zeros(n)])
    left = np.column_stack([np.zeros(n), t])
    pts = np.vstack([top, right, bottom, left])
    return pts[:, 0], pts[:, 1]


def _write_households(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_persons(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_fake_shapefile(
    shp_dir: Path,
    geo_id: str,
    *,
    dguid: str | None = None,
    landarea: float | None = None,
    pruid: str | None = None,
) -> Path:
    """Write the simplest possible polygon shapefile using pyshp."""
    import shapefile

    shp_path = shp_dir / "fake_lct.shp"
    # Use forward-projected LCC coordinates for a small square near Montreal.
    x0, y0 = _wgs84_to_lcc(-73.6, 45.5)
    d = 5_000.0  # 5 km square
    ring = [
        (x0, y0),
        (x0 + d, y0),
        (x0 + d, y0 + d),
        (x0, y0 + d),
        (x0, y0),
    ]
    with shapefile.Writer(str(shp_path)) as w:
        w.field("CTUID", "C", 20)
        if dguid is not None:
            w.field("DGUID", "C", 30)
        if landarea is not None:
            w.field("LANDAREA", "F", 18, 6)
        if pruid is not None:
            w.field("PRUID", "C", 2)
        w.poly([ring])
        record = {"CTUID": geo_id}
        if dguid is not None:
            record["DGUID"] = dguid
        if landarea is not None:
            record["LANDAREA"] = landarea
        if pruid is not None:
            record["PRUID"] = pruid
        w.record(**record)
    return shp_path


def _hh_row(
    hh_id: str,
    ct: str,
    *,
    household_size: str = "2",
    tenur: str = "1",
    dtype: str = "1",
    repair: str = "1",
    shelco: str = "1000",
) -> dict[str, str]:
    return {
        "synthetic_household_id": hh_id,
        "ct": ct,
        "household_size": household_size,
        "TENUR": tenur,
        "DTYPE": dtype,
        "REPAIR": repair,
        "SHELCO": shelco,
    }


def _person_row(
    pid: str,
    hh_id: str,
    ct: str,
    *,
    agegrp: str = "5",
    immstat: str = "1",
    vismin: str = "2",
    totinc: str = "0",
) -> dict[str, str]:
    return {
        "synthetic_person_id": pid,
        "synthetic_household_id": hh_id,
        "ct": ct,
        "AGEGRP": agegrp,
        "IMMSTAT": immstat,
        "VISMIN": vismin,
        "TOTINC": totinc,
    }


def _write_fake_geojson(path: Path, geo_ids: list[str]) -> None:
    """Write a minimal WGS-84 GeoJSON FeatureCollection."""
    import json as _json

    features = [
        {
            "type": "Feature",
            "properties": {"geo_id": gid},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-73.6, 45.5],
                        [-73.5, 45.5],
                        [-73.5, 45.6],
                        [-73.6, 45.6],
                        [-73.6, 45.5],
                    ]
                ],
            },
        }
        for gid in geo_ids
    ]
    path.write_text(_json.dumps({"type": "FeatureCollection", "features": features}))
