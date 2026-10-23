import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.models import User
from app.schemas import GeocodeResult
from app.security import current_user

router = APIRouter(tags=["الخريطة"])


@router.get("/geocode", response_model=list[GeocodeResult])
def geocode(q: str, _: User = Depends(current_user)):
    """بحث عن عنوان عبر Nominatim (OpenStreetMap)، مقيد بالسعودية ودول الخليج."""
    settings = get_settings()
    params = {"q": q, "format": "jsonv2", "limit": 8, "countrycodes": "sa,ae,kw,bh,qa,om", "accept-language": "ar"}
    headers = {"User-Agent": f"solar-designer ({settings.company_name})"}
    try:
        response = httpx.get(f"{settings.nominatim_url}/search", params=params, headers=headers, timeout=15)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"تعذر البحث عن العنوان: {exc}") from exc
    return [GeocodeResult(name=r["display_name"], lat=float(r["lat"]), lon=float(r["lon"])) for r in response.json()]
