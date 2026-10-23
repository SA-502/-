import * as maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import { RIYADH, satelliteStyle } from "../lib/mapStyle";

interface Props {
  value: { lat: number; lon: number } | null;
  onChange: (value: { lat: number; lon: number }) => void;
}

/** خريطة صغيرة لتحديد موقع المشروع بالنقر أو البحث عن عنوان. */
export function LocationPicker({ value, onChange }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const marker = useRef<maplibregl.Marker | null>(null);
  const changeRef = useRef(onChange);
  changeRef.current = onChange;
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ name: string; lat: number; lon: number }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const start = value ?? RIYADH;
    const m = new maplibregl.Map({ container: container.current!, style: satelliteStyle, center: [start.lon, start.lat], zoom: value ? 18 : 11, maxZoom: 21 });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    m.on("click", (e: maplibregl.MapMouseEvent) => changeRef.current({ lat: e.lngLat.lat, lon: e.lngLat.lng }));
    map.current = m;
    return () => {
      marker.current = null;
      m.remove();
    };
  }, []);

  useEffect(() => {
    if (!map.current || !value) return;
    if (!marker.current) {
      marker.current = new maplibregl.Marker({ color: "#d97706", draggable: true }).setLngLat([value.lon, value.lat]).addTo(map.current);
      marker.current.on("dragend", () => {
        const p = marker.current!.getLngLat();
        changeRef.current({ lat: p.lat, lon: p.lng });
      });
    } else {
      marker.current.setLngLat([value.lon, value.lat]);
    }
  }, [value]);

  async function search() {
    setError(null);
    try {
      const found = await api.get<{ name: string; lat: number; lon: number }[]>(`/geocode?q=${encodeURIComponent(query)}`);
      setResults(found);
      if (found.length === 0) setError("لم يتم العثور على نتائج");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function pick(r: { lat: number; lon: number }) {
    onChange({ lat: r.lat, lon: r.lon });
    map.current?.flyTo({ center: [r.lon, r.lat], zoom: 18 });
    setResults([]);
  }

  return (
    <div className="stack">
      <div className="row">
        <input
          placeholder="ابحث عن حي أو عنوان"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void search();
            }
          }}
          style={{ flex: 1 }}
        />
        <button type="button" onClick={search} disabled={!query.trim()}>
          بحث
        </button>
      </div>
      {error && <div className="muted small">{error}</div>}
      {results.length > 0 && (
        <div className="card" style={{ padding: 6 }}>
          {results.map((r) => (
            <div key={`${r.lat},${r.lon}`} className="area-item" onClick={() => pick(r)}>
              {r.name}
            </div>
          ))}
        </div>
      )}
      <div ref={container} className="picker" />
      <div className="muted small">انقر على الخريطة لتحديد موقع المبنى، أو اسحب العلامة.</div>
    </div>
  );
}
