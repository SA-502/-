/**
 * الهندسة ثنائية الأبعاد: الإسقاط المحلي، مسافة الارتداد، المسافة بين الصفوف، وتوزيع الألواح داخل المضلع.
 * نفس اصطلاحات الخادم: x شرقًا وy شمالًا بالمتر من موقع المشروع، والاتجاه (azimuth) بالدرجات من الشمال (180 = جنوب).
 */
import { area as turfArea, booleanIntersects, booleanWithin, buffer, polygon as turfPolygon } from "@turf/turf";
import type { Feature, MultiPolygon, Polygon, Position } from "geojson";

export const M_PER_DEG = 111_320;
const RAD = Math.PI / 180;

export type LngLat = [number, number];
export type XY = [number, number];
export interface Origin {
  lat: number;
  lon: number;
}

export interface ModuleSpec {
  length_m: number;
  width_m: number;
  power_w: number;
}

export type Orientation = "portrait" | "landscape";
export type Mounting = "tilted_rows" | "flush" | "ground";

export interface LayoutParams {
  orientation: Orientation;
  mounting: Mounting;
  tilt_deg: number;
  azimuth_deg: number;
  row_spacing_m: number; // الفراغ بين نهاية صف وبداية التالي (للصفوف المائلة)
  module_gap_m: number;
  setback_m: number;
  obstruction_clearance_m: number;
  roof_height_m: number;
}

export interface PlacedModule {
  lon: number;
  lat: number;
  x: number;
  y: number;
  z: number;
  rotation_deg: number;
}

export function toLocal([lon, lat]: LngLat, origin: Origin): XY {
  return [(lon - origin.lon) * M_PER_DEG * Math.cos(origin.lat * RAD), (lat - origin.lat) * M_PER_DEG];
}

export function toLngLat([x, y]: XY, origin: Origin): LngLat {
  return [origin.lon + x / (M_PER_DEG * Math.cos(origin.lat * RAD)), origin.lat + y / M_PER_DEG];
}

export function closeRing(ring: Position[]): Position[] {
  if (ring.length === 0) return ring;
  const [first, last] = [ring[0], ring[ring.length - 1]];
  return first[0] === last[0] && first[1] === last[1] ? ring : [...ring, first];
}

/** مساحة المضلع الجغرافي بالمتر المربع. */
export function areaM2(ring: LngLat[]): number {
  if (ring.length < 3) return 0;
  return turfArea(turfPolygon([closeRing(ring)]));
}

/** العرض على امتداد الصف والعمق الأفقي للوح المائل (نفس معادلة تقرير الخادم). */
export function footprint(spec: ModuleSpec, orientation: Orientation, tiltDeg: number) {
  const [along, slope] = orientation === "portrait" ? [spec.width_m, spec.length_m] : [spec.length_m, spec.width_m];
  return { along, slope, depth: slope * Math.cos(tiltDeg * RAD), height: slope * Math.sin(tiltDeg * RAD) };
}

/** ارتفاع وسمت الشمس (بالدرجات، السمت من الشمال) بمعادلات مبسطة لزاوية الميل والساعة الشمسية. */
export function sunPosition(latDeg: number, declinationDeg: number, solarHour: number) {
  const lat = latDeg * RAD;
  const dec = declinationDeg * RAD;
  const h = (solarHour - 12) * 15 * RAD;
  const sinEl = Math.sin(lat) * Math.sin(dec) + Math.cos(lat) * Math.cos(dec) * Math.cos(h);
  const el = Math.asin(sinEl);
  const cosAz = (Math.sin(dec) - sinEl * Math.sin(lat)) / (Math.cos(el) * Math.cos(lat));
  let az = Math.acos(Math.min(1, Math.max(-1, cosAz))) / RAD;
  if (h > 0) az = 360 - az;
  return { elevation: el / RAD, azimuth: az };
}

/**
 * أقل فراغ بين الصفوف يمنع تظليل الصف الخلفي بين 9 صباحًا و3 عصرًا يوم 21 ديسمبر (أقصر نهار).
 * الظل يمتد عكس الشمس؛ نأخذ مركبته باتجاه الصف الخلفي.
 */
export function autoRowSpacing(spec: ModuleSpec, orientation: Orientation, tiltDeg: number, azimuthDeg: number, latDeg: number): number {
  const { height } = footprint(spec, orientation, tiltDeg);
  let gap = 0;
  for (const hour of [9, 10, 11, 12, 13, 14, 15]) {
    const sun = sunPosition(latDeg, -23.44, hour);
    if (sun.elevation <= 1) continue;
    const shadow = height / Math.tan(sun.elevation * RAD);
    gap = Math.max(gap, shadow * Math.cos((sun.azimuth - azimuthDeg) * RAD));
  }
  return Math.round(gap * 100) / 100;
}

type Area = Feature<Polygon | MultiPolygon>;

/** المناطق الممنوعة مع هامش حولها. */
export function blockedAreas(keepouts: LngLat[][], clearanceM: number): Area[] {
  return keepouts
    .filter((k) => k.length >= 3)
    .map((k) => {
      const poly = turfPolygon([closeRing(k)]);
      return clearanceM > 0 ? (buffer(poly, clearanceM, { units: "meters" }) as Area) : poly;
    });
}

/** المساحة القابلة للتركيب: السطح ناقص الارتداد وناقص المناطق الممنوعة. */
export function usableArea(roof: LngLat[], keepouts: LngLat[][], setbackM: number, clearanceM: number) {
  const roofPoly = turfPolygon([closeRing(roof)]);
  const inner = setbackM > 0 ? (buffer(roofPoly, -setbackM, { units: "meters" }) as Area | undefined) : roofPoly;
  return { inner: inner && inner.geometry ? inner : null, blocked: blockedAreas(keepouts, clearanceM) };
}

function toLocalFeature(feature: Area, origin: Origin): Area {
  const mapRing = (ring: Position[]) => ring.map((p) => toLocal(p as LngLat, origin));
  if (feature.geometry.type === "Polygon") {
    return { ...feature, geometry: { type: "Polygon", coordinates: feature.geometry.coordinates.map(mapRing) } };
  }
  return {
    ...feature,
    geometry: { type: "MultiPolygon", coordinates: feature.geometry.coordinates.map((poly) => poly.map(mapRing)) },
  };
}

/** زوايا مستطيل اللوح محليًا. الوجه باتجاه azimuth، والعرض على امتداد الصف. */
export function moduleCorners(center: XY, along: number, depth: number, azimuthDeg: number): XY[] {
  const a = azimuthDeg * RAD;
  const f: XY = [Math.sin(a), Math.cos(a)];
  const r: XY = [f[1], -f[0]];
  const [hw, hd] = [along / 2, depth / 2];
  return [
    [-1, -1],
    [1, -1],
    [1, 1],
    [-1, 1],
  ].map(([su, sv]) => [center[0] + su * hw * r[0] + sv * hd * f[0], center[1] + su * hw * r[1] + sv * hd * f[1]] as XY);
}

function rectFeature(corners: XY[]): Feature<Polygon> {
  return turfPolygon([[...corners, corners[0]]]);
}

export interface LayoutResult {
  modules: PlacedModule[];
  usable: Area | null;
  rowPitch: number;
}

/**
 * توزيع تلقائي: صفوف موازية لاتجاه الوجه، تُملأ بطريقة جشعة من بداية كل صف
 * (يناسب الأشكال غير المنتظمة)، مع تخطي المناطق الممنوعة.
 */
export function layoutModules(
  roof: LngLat[],
  keepouts: LngLat[][],
  spec: ModuleSpec,
  params: LayoutParams,
  origin: Origin,
): LayoutResult {
  const { inner, blocked } = usableArea(roof, keepouts, params.setback_m, params.obstruction_clearance_m);
  if (!inner) return { modules: [], usable: null, rowPitch: 0 };

  const { along, depth, height } = footprint(spec, params.orientation, params.tilt_deg);
  const rowGap = params.mounting === "flush" ? params.module_gap_m : Math.max(params.row_spacing_m, params.module_gap_m);
  const rowPitch = depth + rowGap;
  const colPitch = along + params.module_gap_m;

  const usableLocal = toLocalFeature(inner, origin);
  const blockedLocal = blocked.map((b) => toLocalFeature(b, origin));

  const a = params.azimuth_deg * RAD;
  const f: XY = [Math.sin(a), Math.cos(a)];
  const r: XY = [f[1], -f[0]];
  const ring = (usableLocal.geometry.type === "Polygon"
    ? usableLocal.geometry.coordinates.flat()
    : usableLocal.geometry.coordinates.flat(2)) as XY[];
  const us = ring.map((p) => p[0] * r[0] + p[1] * r[1]);
  const vs = ring.map((p) => p[0] * f[0] + p[1] * f[1]);
  const [uMin, uMax, vMin, vMax] = [Math.min(...us), Math.max(...us), Math.min(...vs), Math.max(...vs)];
  const toXY = (u: number, v: number): XY => [u * r[0] + v * f[0], u * r[1] + v * f[1]];

  const fits = (center: XY) => {
    const rect = rectFeature(moduleCorners(center, along, depth, params.azimuth_deg));
    return booleanWithin(rect, usableLocal) && !blockedLocal.some((b) => booleanIntersects(rect, b));
  };

  const modules: PlacedModule[] = [];
  const scanStep = Math.min(0.25, colPitch / 4);
  const z = params.roof_height_m + (params.mounting === "flush" ? 0 : height / 2);
  // الصف الأمامي (الأقرب للشمس) يبدأ من أعلى v ثم نتجه للخلف
  const eps = 0.005; // هامش 5 مم حتى لا يُرفض لوح يلامس الحد بسبب تقريب الأرقام
  for (let v = vMax - depth / 2 - eps; v >= vMin + depth / 2 + eps; v -= rowPitch) {
    let u = uMin + along / 2 + eps;
    while (u <= uMax - along / 2 - eps) {
      const center = toXY(u, v);
      if (fits(center)) {
        const [lon, lat] = toLngLat(center, origin);
        modules.push({ lon, lat, x: round(center[0]), y: round(center[1]), z: round(z), rotation_deg: params.azimuth_deg });
        u += colPitch;
      } else {
        u += scanStep;
      }
    }
  }
  return { modules, usable: inner, rowPitch };
}

/** هل يمكن إضافة لوح يدويًا في هذا الموضع بدون تداخل مع الألواح الحالية؟ */
export function canPlaceModule(
  center: XY,
  existing: PlacedModule[],
  spec: ModuleSpec,
  params: LayoutParams,
  usable: Area | null,
  keepoutsLocal: Area[],
  origin: Origin,
): boolean {
  if (!usable) return false;
  const { along, depth } = footprint(spec, params.orientation, params.tilt_deg);
  const rect = rectFeature(moduleCorners(center, along, depth, params.azimuth_deg));
  if (!booleanWithin(rect, toLocalFeature(usable, origin))) return false;
  if (keepoutsLocal.some((k) => booleanIntersects(rect, k))) return false;
  const shrink = 0.98; // يسمح بالتلامس عند الحواف
  return !existing.some((m) => {
    const other = rectFeature(moduleCorners([m.x, m.y], along * shrink, depth * shrink, m.rotation_deg));
    return booleanIntersects(rect, other);
  });
}

export function keepoutsToLocal(keepouts: LngLat[][], clearanceM: number, origin: Origin): Area[] {
  return blockedAreas(keepouts, clearanceM).map((b) => toLocalFeature(b, origin));
}

/** مضلعات الألواح للعرض على الخريطة. */
export function modulePolygons(modules: PlacedModule[], spec: ModuleSpec, orientation: Orientation, tiltDeg: number, origin: Origin): LngLat[][] {
  const { along, depth } = footprint(spec, orientation, tiltDeg);
  return modules.map((m) => {
    const corners = moduleCorners([m.x, m.y], along, depth, m.rotation_deg).map((c) => toLngLat(c, origin));
    return [...corners, corners[0]];
  });
}

function round(value: number) {
  return Math.round(value * 1000) / 1000;
}
