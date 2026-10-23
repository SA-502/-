"""جلب السنة النموذجية (TMY) من PVGIS وتحويلها إلى جدول طقس ساعي."""

import httpx
import pandas as pd

PVGIS_COLUMNS = {
    "G(h)": "ghi",
    "Gb(n)": "dni",
    "Gd(h)": "dhi",
    "T2m": "temp_air",
    "WS10m": "wind_speed",
    "SP": "pressure",
    "RH": "relative_humidity",
}
# سنة غير كبيسة يُعاد إليها كل شهر من أشهر TMY (كل شهر مأخوذ من سنة مختلفة)
NOMINAL_YEAR = 2023


class PVGISError(RuntimeError):
    pass


def fetch_tmy_json(latitude: float, longitude: float, base_url: str, timeout: float = 60.0) -> dict:
    params = {"lat": latitude, "lon": longitude, "outputformat": "json", "usehorizon": 1}
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/tmy", params=params, timeout=timeout)
    except httpx.HTTPError as exc:
        raise PVGISError(f"تعذر الاتصال بـ PVGIS: {exc}") from exc
    if response.status_code != 200:
        message = response.text[:300]
        try:
            message = response.json().get("message", message)
        except ValueError:
            pass
        raise PVGISError(f"PVGIS رد بخطأ {response.status_code}: {message}")
    return response.json()


def parse_tmy(payload: dict) -> tuple[pd.DataFrame, dict]:
    """يعيد (طقس ساعي بفهرس UTC لسنة اسمية واحدة، بيانات وصفية)."""
    try:
        hourly = payload["outputs"]["tmy_hourly"]
        location = payload["inputs"]["location"]
    except (KeyError, TypeError) as exc:
        raise PVGISError("صيغة رد PVGIS غير متوقعة") from exc

    data = pd.DataFrame(hourly)
    stamps = pd.to_datetime(data.pop("time(UTC)"), format="%Y%m%d:%H%M", utc=True)
    stamps = stamps.map(lambda ts: ts.replace(year=NOMINAL_YEAR))
    data.index = pd.DatetimeIndex(stamps, name="time")
    data = data.rename(columns=PVGIS_COLUMNS)
    data = data[[c for c in PVGIS_COLUMNS.values() if c in data.columns]].astype(float)
    data = data.sort_index()
    data = data[~data.index.duplicated()]
    missing = {"ghi", "dni", "dhi", "temp_air", "wind_speed"} - set(data.columns)
    if missing:
        raise PVGISError(f"بيانات PVGIS تنقصها الأعمدة: {sorted(missing)}")
    if len(data) != 8760:
        raise PVGISError(f"عدد ساعات غير صحيح في السنة النموذجية: {len(data)}")

    meta = {
        "source": "PVGIS TMY",
        "latitude": float(location["latitude"]),
        "longitude": float(location["longitude"]),
        "elevation": float(location.get("elevation", 0.0)),
        "months_selected": payload["outputs"].get("months_selected", []),
        "radiation_db": payload.get("inputs", {}).get("meteo_data", {}).get("radiation_db"),
    }
    return data, meta
