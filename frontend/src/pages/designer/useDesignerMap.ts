import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import { useEffect, useRef, useState } from "react";

import { satelliteStyle } from "../../lib/mapStyle";

export interface MapData {
  areas: FeatureCollection;
  usable: FeatureCollection;
  obstructions: FeatureCollection;
  modules: FeatureCollection;
  draft: FeatureCollection;
}

export interface MapHandlers {
  onClick: (lngLat: [number, number], hit: { layer: string; properties: Record<string, unknown> } | null) => void;
  onDoubleClick: () => void;
}

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const CLICKABLE = ["modules-fill", "obstructions-fill", "areas-fill"];

function addLayers(map: maplibregl.Map) {
  for (const id of ["areas", "usable", "obstructions", "modules", "draft"]) {
    map.addSource(id, { type: "geojson", data: EMPTY });
  }
  map.addLayer({ id: "areas-fill", type: "fill", source: "areas", paint: { "fill-color": "#f59e0b", "fill-opacity": ["case", ["get", "selected"], 0.22, 0.1] } });
  map.addLayer({
    id: "areas-line",
    type: "line",
    source: "areas",
    paint: { "line-color": ["case", ["get", "selected"], "#ffffff", "#f59e0b"], "line-width": ["case", ["get", "selected"], 3, 2] },
  });
  map.addLayer({ id: "usable-line", type: "line", source: "usable", paint: { "line-color": "#4ade80", "line-width": 1.5, "line-dasharray": [2, 2] } });
  map.addLayer({ id: "obstructions-fill", type: "fill", source: "obstructions", paint: { "fill-color": "#ef4444", "fill-opacity": 0.35 } });
  map.addLayer({
    id: "obstructions-line",
    type: "line",
    source: "obstructions",
    paint: { "line-color": ["case", ["get", "selected"], "#ffffff", "#ef4444"], "line-width": 2 },
  });
  map.addLayer({ id: "modules-fill", type: "fill", source: "modules", paint: { "fill-color": "#1e3a8a", "fill-opacity": 0.92 } });
  map.addLayer({ id: "modules-line", type: "line", source: "modules", paint: { "line-color": "#93c5fd", "line-width": 0.6 } });
  map.addLayer({
    id: "draft-line",
    type: "line",
    source: "draft",
    filter: ["==", ["geometry-type"], "LineString"],
    paint: { "line-color": "#fde047", "line-width": 2, "line-dasharray": [2, 1] },
  });
  map.addLayer({
    id: "draft-points",
    type: "circle",
    source: "draft",
    filter: ["==", ["geometry-type"], "Point"],
    paint: { "circle-radius": 4, "circle-color": "#fde047", "circle-stroke-color": "#111827", "circle-stroke-width": 1 },
  });
}

/** خريطة المصمم: تُنشأ مرة واحدة، وتُحدَّث مصادرها عند تغير البيانات. */
export function useDesignerMap(center: { lat: number; lon: number } | null, data: MapData, handlers: MapHandlers, drawing: boolean) {
  // ref بدالة: الحاوية تظهر بعد تحميل البيانات، فنعيد إنشاء الخريطة عند ظهورها
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loaded = useRef(false);
  const dataRef = useRef(data);
  const handlersRef = useRef(handlers);
  dataRef.current = data;
  handlersRef.current = handlers;

  useEffect(() => {
    if (!center || !container) return;
    const map = new maplibregl.Map({
      container,
      style: satelliteStyle,
      center: [center.lon, center.lat],
      zoom: 19,
      maxZoom: 22,
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.on("load", () => {
      addLayers(map);
      loaded.current = true;
      apply(map, dataRef.current);
      fitToAreas(map, dataRef.current.areas);
    });
    map.on("click", (e: MapMouseEvent) => {
      const layers = CLICKABLE.filter((l) => map.getLayer(l));
      const hit = map.queryRenderedFeatures(e.point, { layers })[0];
      handlersRef.current.onClick([e.lngLat.lng, e.lngLat.lat], hit ? { layer: hit.layer.id, properties: hit.properties ?? {} } : null);
    });
    map.on("dblclick", (e: MapMouseEvent) => {
      if (map.doubleClickZoom.isEnabled()) return;
      e.preventDefault();
      handlersRef.current.onDoubleClick();
    });
    mapRef.current = map;
    return () => {
      loaded.current = false;
      mapRef.current = null;
      map.remove();
    };
    // الخريطة تُنشأ مرة واحدة لكل حاوية وموقع مشروع
  }, [container, center?.lat, center?.lon]);

  useEffect(() => {
    if (mapRef.current && loaded.current) apply(mapRef.current, data);
  }, [data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (drawing) map.doubleClickZoom.disable();
    else map.doubleClickZoom.enable();
    map.getCanvas().style.cursor = drawing ? "crosshair" : "";
  }, [drawing]);

  return { container: setContainer, map: mapRef };
}

function apply(map: maplibregl.Map, data: MapData) {
  for (const [id, fc] of Object.entries(data)) {
    (map.getSource(id) as GeoJSONSource | undefined)?.setData(fc);
  }
}

function fitToAreas(map: maplibregl.Map, areas: FeatureCollection) {
  const bounds = new maplibregl.LngLatBounds();
  let any = false;
  for (const f of areas.features) {
    if (f.geometry.type !== "Polygon") continue;
    for (const p of f.geometry.coordinates[0]) {
      bounds.extend(p as [number, number]);
      any = true;
    }
  }
  if (any) map.fitBounds(bounds, { padding: 80, maxZoom: 20, duration: 0 });
}
