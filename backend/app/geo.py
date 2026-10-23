"""تحويل الأشكال بين GeoJSON وأعمدة PostGIS."""

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, mapping, shape


def _listify(value):
    if isinstance(value, (list, tuple)):
        return [_listify(v) for v in value]
    return value


def polygon_to_db(geojson: dict):
    geom = shape(geojson)
    if not geom.is_valid:
        raise ValueError("المضلع غير صالح (أضلاع متقاطعة)")
    return from_shape(geom, srid=4326)


def polygon_from_db(column) -> dict:
    geo = mapping(to_shape(column))
    return {"type": "Polygon", "coordinates": _listify(geo["coordinates"])}


def point_to_db(lat: float, lon: float):
    return from_shape(Point(lon, lat), srid=4326)


def point_from_db(column) -> dict:
    point = to_shape(column)
    return {"lat": point.y, "lon": point.x}
