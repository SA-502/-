"""سنة طقس صناعية بصيغة رد PVGIS (سماء صافية مخففة) لاختبارات لا تحتاج الإنترنت."""

import numpy as np
import pandas as pd
import pvlib


def pvgis_payload(latitude: float = 24.7136, longitude: float = 46.6753, elevation: float = 612.0) -> dict:
    # كل شهر من سنة مختلفة كما في TMY الحقيقي
    frames = []
    for month in range(1, 13):
        year = 2010 + month
        start = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
        end = start + pd.offsets.MonthBegin(1)
        frames.append(pd.date_range(start, end, freq="h", inclusive="left"))
    index = frames[0].append(frames[1:])
    # 29 فبراير غير موجود لأن فبراير مأخوذ من 2012 الكبيسة؛ نحذف 29 فبراير ليصبح 8760 ساعة
    index = index[~((index.month == 2) & (index.day == 29))]

    location = pvlib.location.Location(latitude, longitude, altitude=elevation)
    clear = location.get_clearsky(index, model="ineichen")
    hours = np.arange(len(index))
    temp = 27 + 11 * np.sin((index.day_of_year - 105) / 365 * 2 * np.pi) + 6 * np.sin((index.hour + 3 - 9) / 24 * 2 * np.pi)
    rows = []
    for i, ts in enumerate(index):
        rows.append(
            {
                "time(UTC)": ts.strftime("%Y%m%d:%H%M"),
                "T2m": round(float(temp[i]), 2),
                "RH": 20.0,
                "G(h)": round(float(clear["ghi"].iloc[i]) * 0.9, 2),
                "Gb(n)": round(float(clear["dni"].iloc[i]) * 0.85, 2),
                "Gd(h)": round(float(clear["dhi"].iloc[i]) * 1.1, 2),
                "IR(h)": 380.0,
                "WS10m": 3.0 + (hours[i] % 5) * 0.2,
                "WD10m": 330.0,
                "SP": 94000.0,
            }
        )
    return {
        "inputs": {
            "location": {"latitude": latitude, "longitude": longitude, "elevation": elevation},
            "meteo_data": {"radiation_db": "PVGIS-SARAH3"},
        },
        "outputs": {
            "months_selected": [{"month": m, "year": 2010 + m} for m in range(1, 13)],
            "tmy_hourly": rows,
        },
        "meta": {"inputs": {}},
    }
