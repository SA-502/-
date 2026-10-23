import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Feature, FeatureCollection } from "geojson";
import * as maplibregl from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../../api/client";
import type { ArrayDesign, Component, Design, DesignContent, Losses, ObstructionKind, Project, RoofAreaDesign, Simulation } from "../../api/types";
import { useAuth } from "../../auth";
import {
  areaM2,
  autoRowSpacing,
  canPlaceModule,
  closeRing,
  keepoutsToLocal,
  layoutModules,
  modulePolygons,
  toLocal,
  usableArea,
  type LayoutParams,
  type LngLat,
  type ModuleSpec,
  type Origin,
} from "../../geometry/layout";
import { MONTHS, OBSTRUCTION_KINDS, compass, num } from "../../lib/format";
import { useDesignerMap, type MapData } from "./useDesignerMap";

type Mode = "idle" | "draw-area" | "draw-obstruction" | "edit-modules";
type Selection = { type: "area"; index: number } | { type: "obstruction"; index: number } | null;

const OBSTRUCTION_CLEARANCE_M = 0.5;
// عائد نوعي تقديري للرياض لتحجيم النظام قبل المحاكاة
const ESTIMATED_YIELD_KWH_KWP = 1750;
const DEFAULT_LOSSES: Losses = {
  albedo: 0.25,
  soiling_monthly_pct: Array(12).fill(4),
  mismatch_pct: 2,
  dc_wiring_pct: 1.5,
  lid_pct: 1.5,
  ac_wiring_pct: 1,
  transformer_pct: 0,
};

const ring = (area: { geometry: { coordinates: LngLat[][] } }) => area.geometry.coordinates[0];
const polygon = (points: LngLat[]) => ({ type: "Polygon" as const, coordinates: [closeRing(points) as LngLat[]] });
const fc = (features: Feature[]): FeatureCollection => ({ type: "FeatureCollection", features });

function moduleSpec(component: Component | undefined): ModuleSpec | null {
  if (!component) return null;
  const { length_m, width_m, power_w } = component.specs as Record<string, number>;
  return length_m && width_m && power_w ? { length_m, width_m, power_w } : null;
}

function newArray(moduleId: number): ArrayDesign {
  return { module_id: moduleId, orientation: "portrait", mounting: "tilted_rows", tilt_deg: 20, azimuth_deg: 180, row_spacing_m: 1.2, module_gap_m: 0.02, modules: [] };
}

function layoutParams(area: RoofAreaDesign, arr: ArrayDesign): LayoutParams {
  return {
    orientation: arr.orientation,
    mounting: arr.mounting,
    tilt_deg: arr.tilt_deg,
    azimuth_deg: arr.azimuth_deg,
    row_spacing_m: arr.row_spacing_m,
    module_gap_m: arr.module_gap_m,
    setback_m: area.setback_m,
    obstruction_clearance_m: OBSTRUCTION_CLEARANCE_M,
    roof_height_m: area.height_m,
  };
}

/** يزيل النقاط المكررة المتتالية (النقر المزدوج يضيف نقطتين في نفس المكان). */
function dedupe(points: LngLat[]): LngLat[] {
  return points.filter((p, i) => i === 0 || Math.hypot(p[0] - points[i - 1][0], p[1] - points[i - 1][1]) > 1e-7);
}

export function DesignerPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { can } = useAuth();
  const editable = can("engineer");

  const design = useQuery({ queryKey: ["design", Number(id)], queryFn: () => api.get<Design>(`/designs/${id}`) });
  const project = useQuery({
    queryKey: ["project", String(design.data?.project_id)],
    queryFn: () => api.get<Project>(`/projects/${design.data!.project_id}`),
    enabled: Boolean(design.data),
  });
  const components = useQuery({ queryKey: ["components"], queryFn: () => api.get<Component[]>("/components") });

  const [content, setContent] = useState<DesignContent | null>(null);
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<Mode>("idle");
  const [draft, setDraft] = useState<LngLat[]>([]);
  const [selection, setSelection] = useState<Selection>(null);
  const [obstructionKind, setObstructionKind] = useState<ObstructionKind>("keepout");
  const [losses, setLosses] = useState<Losses>(DEFAULT_LOSSES);
  const [showLosses, setShowLosses] = useState(false);
  const [maxModules, setMaxModules] = useState<number | "">("");
  const [message, setMessage] = useState<{ kind: "error" | "notice"; text: string } | null>(null);

  useEffect(() => {
    if (design.data && !content) {
      const { id: _id, project_id: _p, version_no: _v, created_at: _c, module_count: _m, dc_kwp: _d, ac_kw: _a, ...rest } = design.data;
      setContent(rest);
    }
  }, [design.data, content]);

  const origin: Origin | null = project.data ? project.data.location : null;
  const modulesById = useMemo(() => new Map((components.data ?? []).filter((c) => c.kind === "module").map((c) => [c.id, c])), [components.data]);
  const inverters = (components.data ?? []).filter((c) => c.kind === "inverter");
  const rackings = (components.data ?? []).filter((c) => c.kind === "racking");
  const defaultModuleId = modulesById.keys().next().value as number | undefined;
  const annualKwh = project.data?.monthly_consumption_kwh?.reduce((a, b) => a + b, 0) ?? 0;

  const update = useCallback((fn: (c: DesignContent) => DesignContent) => {
    setContent((c) => (c ? fn(c) : c));
    setDirty(true);
  }, []);

  const updateArea = useCallback(
    (index: number, patch: Partial<RoofAreaDesign>) => update((c) => ({ ...c, roof_areas: c.roof_areas.map((a, i) => (i === index ? { ...a, ...patch } : a)) })),
    [update],
  );

  const updateArray = useCallback(
    (index: number, patch: Partial<ArrayDesign>, keepModules = false) =>
      update((c) => ({
        ...c,
        roof_areas: c.roof_areas.map((a, i) =>
          i === index ? { ...a, arrays: [{ ...a.arrays[0], ...patch, ...(keepModules || "modules" in patch ? {} : { modules: [] }) }] } : a,
        ),
      })),
    [update],
  );

  // ---------- ملخص ----------
  const totals = useMemo(() => {
    let modules = 0;
    let watts = 0;
    for (const area of content?.roof_areas ?? []) {
      for (const arr of area.arrays) {
        modules += arr.modules.length;
        watts += arr.modules.length * Number(modulesById.get(arr.module_id)?.specs.power_w ?? 0);
      }
    }
    const inverter = inverters.find((c) => c.id === content?.inverter_id);
    const ac = inverter ? Number(inverter.specs.ac_power_kw) * (content?.inverter_count ?? 0) : 0;
    return { modules, kwp: watts / 1000, ac, ratio: ac ? watts / 1000 / ac : null, inverter };
  }, [content, modulesById, inverters]);

  // ---------- بيانات الخريطة ----------
  const mapData: MapData = useMemo(() => {
    const empty = fc([]);
    if (!content || !origin) return { areas: empty, usable: empty, obstructions: empty, modules: empty, draft: empty };
    const keepouts = content.obstructions.map(ring);
    const areas = content.roof_areas.map((a, i) => ({
      type: "Feature" as const,
      properties: { index: i, selected: selection?.type === "area" && selection.index === i },
      geometry: a.geometry,
    }));
    const obstructions = content.obstructions.map((o, i) => ({
      type: "Feature" as const,
      properties: { index: i, selected: selection?.type === "obstruction" && selection.index === i },
      geometry: o.geometry,
    }));
    const modules: Feature[] = [];
    content.roof_areas.forEach((a, i) => {
      const arr = a.arrays[0];
      const spec = arr && moduleSpec(modulesById.get(arr.module_id));
      if (!arr || !spec) return;
      modulePolygons(arr.modules, spec, arr.orientation, arr.tilt_deg, origin).forEach((poly, j) =>
        modules.push({ type: "Feature", properties: { area: i, module: j }, geometry: { type: "Polygon", coordinates: [poly] } }),
      );
    });
    const usable: Feature[] = [];
    if (selection?.type === "area") {
      const a = content.roof_areas[selection.index];
      const inner = a && usableArea(ring(a), keepouts, a.setback_m, OBSTRUCTION_CLEARANCE_M).inner;
      if (inner) usable.push(inner);
    }
    const draftFeatures: Feature[] = draft.map((p) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: p } }));
    if (draft.length > 1) draftFeatures.push({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: draft } });
    return { areas: fc(areas), usable: fc(usable), obstructions: fc(obstructions), modules: fc(modules), draft: fc(draftFeatures) };
  }, [content, origin, selection, draft, modulesById]);

  // ---------- الرسم ----------
  const finishDrawing = useCallback(() => {
    const points = dedupe(draft);
    if (points.length < 3) {
      setMessage({ kind: "error", text: "المضلع يحتاج 3 نقاط على الأقل" });
      return;
    }
    if (mode === "draw-area") {
      const index = content?.roof_areas.length ?? 0;
      update((c) => ({
        ...c,
        roof_areas: [
          ...c.roof_areas,
          {
            name: `مساحة ${index + 1}`,
            kind: "roof",
            geometry: polygon(points),
            height_m: 6,
            pitch_deg: 0,
            azimuth_deg: 180,
            setback_m: 1,
            arrays: defaultModuleId ? [newArray(defaultModuleId)] : [],
          },
        ],
      }));
      setSelection({ type: "area", index });
    } else if (mode === "draw-obstruction") {
      const index = content?.obstructions.length ?? 0;
      update((c) => ({ ...c, obstructions: [...c.obstructions, { kind: obstructionKind, geometry: polygon(points), height_m: obstructionKind === "keepout" ? 0 : 1.5 }] }));
      setSelection({ type: "obstruction", index });
    }
    setDraft([]);
    setMode("idle");
    setMessage(null);
  }, [draft, mode, content, update, defaultModuleId, obstructionKind]);

  const handleClick = useCallback(
    (lngLat: LngLat, hit: { layer: string; properties: Record<string, unknown> } | null) => {
      if (mode === "draw-area" || mode === "draw-obstruction") {
        setDraft((d) => [...d, lngLat]);
        return;
      }
      if (mode === "edit-modules" && content && origin) {
        if (hit?.layer === "modules-fill") {
          const areaIndex = Number(hit.properties.area);
          const moduleIndex = Number(hit.properties.module);
          const arr = content.roof_areas[areaIndex].arrays[0];
          updateArray(areaIndex, { modules: arr.modules.filter((_, j) => j !== moduleIndex) });
          return;
        }
        if (selection?.type !== "area") {
          setMessage({ kind: "notice", text: "اختر مساحة أولًا ثم انقر داخلها لإضافة لوح" });
          return;
        }
        const area = content.roof_areas[selection.index];
        const arr = area.arrays[0];
        const spec = arr && moduleSpec(modulesById.get(arr.module_id));
        if (!arr || !spec) return;
        const params = layoutParams(area, arr);
        const keepouts = content.obstructions.map(ring);
        const { inner } = usableArea(ring(area), keepouts, area.setback_m, OBSTRUCTION_CLEARANCE_M);
        const center = toLocal(lngLat, origin);
        if (!canPlaceModule(center, arr.modules, spec, params, inner, keepoutsToLocal(keepouts, OBSTRUCTION_CLEARANCE_M, origin), origin)) {
          setMessage({ kind: "notice", text: "لا مكان للوح هنا (خارج المساحة أو متداخل)" });
          return;
        }
        const z = arr.modules[0]?.z ?? area.height_m;
        updateArray(selection.index, {
          modules: [...arr.modules, { lon: lngLat[0], lat: lngLat[1], x: center[0], y: center[1], z, rotation_deg: arr.azimuth_deg }],
        });
        setMessage(null);
        return;
      }
      if (hit?.layer === "obstructions-fill") setSelection({ type: "obstruction", index: Number(hit.properties.index) });
      else if (hit?.layer === "areas-fill" || hit?.layer === "modules-fill")
        setSelection({ type: "area", index: Number(hit.properties.index ?? hit.properties.area) });
      else setSelection(null);
    },
    [mode, content, origin, selection, modulesById, updateArray],
  );

  const drawing = mode === "draw-area" || mode === "draw-obstruction";
  const { container, map } = useDesignerMap(origin, mapData, { onClick: handleClick, onDoubleClick: finishDrawing }, drawing);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!drawing) return;
      if (e.key === "Escape") {
        setDraft([]);
        setMode("idle");
      } else if (e.key === "Enter") finishDrawing();
      else if (e.key === "Backspace") setDraft((d) => d.slice(0, -1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawing, finishDrawing]);

  // ---------- تحريك رؤوس المضلع المحدد ----------
  const markers = useRef<maplibregl.Marker[]>([]);
  useEffect(() => {
    markers.current.forEach((m) => m.remove());
    markers.current = [];
    if (!map.current || !content || !editable || mode !== "idle" || !selection) return;
    const shape = selection.type === "area" ? content.roof_areas[selection.index] : content.obstructions[selection.index];
    if (!shape) return;
    const points = ring(shape).slice(0, -1);
    points.forEach((p, k) => {
      const el = document.createElement("div");
      el.style.cssText = "width:12px;height:12px;border-radius:50%;background:#fff;border:2px solid #d97706;cursor:move";
      const marker = new maplibregl.Marker({ element: el, draggable: true }).setLngLat(p).addTo(map.current!);
      marker.on("dragend", () => {
        const { lng, lat } = marker.getLngLat();
        const next = points.map((q, j) => (j === k ? ([lng, lat] as LngLat) : q));
        if (selection.type === "area") {
          update((c) => ({
            ...c,
            roof_areas: c.roof_areas.map((a, i) => (i === selection.index ? { ...a, geometry: polygon(next), arrays: a.arrays.map((arr) => ({ ...arr, modules: [] })) } : a)),
          }));
          setMessage({ kind: "notice", text: "تغير شكل المساحة؛ أعد التوزيع التلقائي" });
        } else {
          update((c) => ({ ...c, obstructions: c.obstructions.map((o, i) => (i === selection.index ? { ...o, geometry: polygon(next) } : o)) }));
        }
      });
      markers.current.push(marker);
    });
    return () => {
      markers.current.forEach((m) => m.remove());
      markers.current = [];
    };
  }, [map, content, selection, mode, editable, update]);

  // ---------- التوزيع التلقائي ----------
  function autoLayout(index: number) {
    if (!content || !origin) return;
    const area = content.roof_areas[index];
    const arr = area.arrays[0];
    const spec = arr && moduleSpec(modulesById.get(arr.module_id));
    if (!arr || !spec) {
      setMessage({ kind: "error", text: "اختر لوحًا لهذه المساحة أولًا" });
      return;
    }
    const result = layoutModules(ring(area), content.obstructions.map(ring), spec, layoutParams(area, arr), origin);
    // الصفوف الأمامية أولًا، فالحد الأقصى يترك الصفوف الخلفية فارغة
    const modules = maxModules ? result.modules.slice(0, maxModules) : result.modules;
    updateArray(index, { modules });
    const capped = modules.length < result.modules.length ? ` من أصل ${result.modules.length} ممكن` : "";
    setMessage(
      modules.length
        ? { kind: "notice", text: `تم توزيع ${modules.length} لوح (${num((modules.length * spec.power_w) / 1000, 2)} kWp)${capped}` }
        : { kind: "error", text: "لا توجد مساحة كافية بعد الارتداد" },
    );
  }

  /** عدد الألواح الذي يغطي الاستهلاك السنوي تقريبًا (بعائد نوعي تقديري)، بعد خصم ألواح المساحات الأخرى. */
  function sizeToConsumption(index: number) {
    if (!content) return;
    const arr = content.roof_areas[index].arrays[0];
    const spec = arr && moduleSpec(modulesById.get(arr.module_id));
    if (!spec || !annualKwh) return;
    const thisKwp = (arr.modules.length * spec.power_w) / 1000;
    const targetKwp = Math.max(annualKwh / ESTIMATED_YIELD_KWH_KWP - (totals.kwp - thisKwp), 0);
    setMaxModules(Math.ceil((targetKwp * 1000) / spec.power_w));
  }

  function autoSpacing(index: number) {
    if (!content || !origin) return;
    const arr = content.roof_areas[index].arrays[0];
    const spec = moduleSpec(modulesById.get(arr.module_id));
    if (!spec) return;
    updateArray(index, { row_spacing_m: autoRowSpacing(spec, arr.orientation, arr.tilt_deg, arr.azimuth_deg, origin.lat) });
  }

  // ---------- الحفظ والمحاكاة ----------
  const save = useMutation({
    mutationFn: () => api.put<Design>(`/designs/${id}`, content),
    onSuccess: (saved) => {
      setDirty(false);
      queryClient.setQueryData(["design", Number(id)], saved);
      queryClient.invalidateQueries({ queryKey: ["project", String(saved.project_id)] });
      setMessage({ kind: "notice", text: "تم الحفظ" });
    },
    onError: (err) => setMessage({ kind: "error", text: (err as Error).message }),
  });

  const simulate = useMutation({
    mutationFn: async () => {
      if (dirty) await save.mutateAsync();
      return api.post<Simulation>(`/designs/${id}/simulate`, { losses });
    },
    onSuccess: (sim) => {
      queryClient.invalidateQueries({ queryKey: ["simulations", Number(id)] });
      navigate(`/simulations/${sim.id}`);
    },
    onError: (err) => setMessage({ kind: "error", text: (err as Error).message }),
  });

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (design.error) return <div className="error">{(design.error as Error).message}</div>;
  if (!content || !project.data || !components.data) return <div className="center muted">جارٍ تحميل التصميم…</div>;

  const selectedArea = selection?.type === "area" ? content.roof_areas[selection.index] : null;
  const selectedArray = selectedArea?.arrays[0];
  const selectedObstruction = selection?.type === "obstruction" ? content.obstructions[selection.index] : null;
  const suggestedInverters = totals.inverter ? Math.max(1, Math.ceil(totals.kwp / 1.2 / Number(totals.inverter.specs.ac_power_kw))) : null;

  return (
    <div className="designer">
      <aside className="panel">
        <section>
          <div className="spread" style={{ marginBottom: 6 }}>
            <Link to={`/projects/${project.data.id}`} className="small">
              ← {project.data.name}
            </Link>
            <span className="muted small">
              النسخة <span className="num">{design.data!.version_no}</span>
            </span>
          </div>
          <input value={content.name} onChange={(e) => update((c) => ({ ...c, name: e.target.value }))} disabled={!editable} style={{ width: "100%" }} />
        </section>

        <section className="grid cols-4" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div className="kpi">
            <div className="label">الألواح</div>
            <div className="value num">{totals.modules}</div>
          </div>
          <div className="kpi">
            <div className="label">قدرة DC</div>
            <div className="value num">{num(totals.kwp, 2)} kWp</div>
          </div>
          <div className="kpi">
            <div className="label">قدرة AC</div>
            <div className="value num">{totals.ac ? `${num(totals.ac, 1)} kW` : "—"}</div>
          </div>
          <div className="kpi">
            <div className="label">نسبة DC/AC</div>
            <div className="value num" style={{ color: totals.ratio && (totals.ratio > 1.35 || totals.ratio < 0.9) ? "var(--danger)" : undefined }}>
              {totals.ratio ? num(totals.ratio, 2) : "—"}
            </div>
          </div>
        </section>

        {message && <div className={message.kind === "error" ? "error" : "notice"} style={{ marginBottom: 12 }}>{message.text}</div>}

        <section>
          <h3>المساحات</h3>
          {content.roof_areas.map((a, i) => (
            <div key={i} className={`area-item ${selection?.type === "area" && selection.index === i ? "selected" : ""}`} onClick={() => setSelection({ type: "area", index: i })}>
              <span>{a.name || `مساحة ${i + 1}`}</span>
              <span className="muted small num">
                {num(areaM2(ring(a)))} m² · {a.arrays[0]?.modules.length ?? 0} لوح
              </span>
            </div>
          ))}
          {content.obstructions.map((o, i) => (
            <div key={`o${i}`} className={`area-item ${selection?.type === "obstruction" && selection.index === i ? "selected" : ""}`} onClick={() => setSelection({ type: "obstruction", index: i })}>
              <span style={{ color: "var(--danger)" }}>{OBSTRUCTION_KINDS[o.kind]}</span>
              <span className="muted small num">{num(areaM2(ring(o)), 1)} m²</span>
            </div>
          ))}
          {content.roof_areas.length === 0 && <div className="muted small">ارسم حدود السطح من شريط الأدوات فوق الخريطة.</div>}
        </section>

        {selectedArea && selection?.type === "area" && (
          <section className="stack">
            <div className="spread" style={{ marginBottom: 0 }}>
              <h3 style={{ margin: 0 }}>إعدادات المساحة</h3>
              {editable && (
                <button
                  className="danger"
                  onClick={() => {
                    update((c) => ({ ...c, roof_areas: c.roof_areas.filter((_, i) => i !== selection.index) }));
                    setSelection(null);
                  }}
                >
                  حذف
                </button>
              )}
            </div>
            <fieldset disabled={!editable} style={{ border: "none", padding: 0, margin: 0 }} className="stack">
              <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                <label className="field">
                  الاسم
                  <input value={selectedArea.name} onChange={(e) => updateArea(selection.index, { name: e.target.value })} />
                </label>
                <label className="field">
                  النوع
                  <select
                    value={selectedArea.kind}
                    onChange={(e) => {
                      const kind = e.target.value as "roof" | "ground";
                      updateArea(selection.index, { kind, height_m: kind === "ground" ? 0 : selectedArea.height_m });
                      if (kind === "ground" && selectedArray) updateArray(selection.index, { mounting: "ground" });
                    }}
                  >
                    <option value="roof">سطح</option>
                    <option value="ground">أرض</option>
                  </select>
                </label>
                <label className="field">
                  الارتفاع (م)
                  <input type="number" min={0} step={0.5} value={selectedArea.height_m} onChange={(e) => updateArea(selection.index, { height_m: Number(e.target.value) })} />
                </label>
                <label className="field">
                  الارتداد عن الحواف (م)
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    value={selectedArea.setback_m}
                    onChange={(e) => {
                      updateArea(selection.index, { setback_m: Number(e.target.value) });
                      if (selectedArray) updateArray(selection.index, {});
                    }}
                  />
                </label>
                <label className="field">
                  ميل السطح (°)
                  <input
                    type="number"
                    min={0}
                    max={60}
                    value={selectedArea.pitch_deg}
                    onChange={(e) => {
                      const pitch = Number(e.target.value);
                      updateArea(selection.index, { pitch_deg: pitch });
                      // سطح مائل ⇒ الألواح ملاصقة بنفس الميل والاتجاه
                      if (pitch > 0 && selectedArray) updateArray(selection.index, { mounting: "flush", tilt_deg: pitch, azimuth_deg: selectedArea.azimuth_deg });
                    }}
                  />
                </label>
                <label className="field">
                  اتجاه ميل السطح (°)
                  <input
                    type="number"
                    min={0}
                    max={359}
                    value={selectedArea.azimuth_deg}
                    onChange={(e) => {
                      const azimuth = Number(e.target.value);
                      updateArea(selection.index, { azimuth_deg: azimuth });
                      if (selectedArea.pitch_deg > 0 && selectedArray) updateArray(selection.index, { azimuth_deg: azimuth });
                    }}
                  />
                </label>
              </div>

              {selectedArray ? (
                <>
                  <h3 style={{ marginTop: 8 }}>الألواح وطريقة التركيب</h3>
                  <label className="field">
                    اللوح
                    <select value={selectedArray.module_id} onChange={(e) => updateArray(selection.index, { module_id: Number(e.target.value) })}>
                      {[...modulesById.values()].map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.manufacturer} {m.model} — {m.specs.power_w} W
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                    <label className="field">
                      التركيب
                      <select value={selectedArray.mounting} onChange={(e) => updateArray(selection.index, { mounting: e.target.value as ArrayDesign["mounting"] })}>
                        <option value="tilted_rows">صفوف مائلة (سطح مستوٍ)</option>
                        <option value="flush">ملاصق للسطح</option>
                        <option value="ground">أرضي</option>
                      </select>
                    </label>
                    <label className="field">
                      الوضع
                      <select value={selectedArray.orientation} onChange={(e) => updateArray(selection.index, { orientation: e.target.value as ArrayDesign["orientation"] })}>
                        <option value="portrait">رأسي</option>
                        <option value="landscape">أفقي</option>
                      </select>
                    </label>
                    <label className="field">
                      ميل اللوح (°)
                      <input type="number" min={0} max={60} value={selectedArray.tilt_deg} onChange={(e) => updateArray(selection.index, { tilt_deg: Number(e.target.value) })} />
                    </label>
                    <label className="field">
                      اتجاه اللوح (°) · {compass(selectedArray.azimuth_deg)}
                      <input type="number" min={0} max={359} value={selectedArray.azimuth_deg} onChange={(e) => updateArray(selection.index, { azimuth_deg: Number(e.target.value) })} />
                    </label>
                    <label className="field">
                      الفراغ بين الصفوف (م)
                      <div className="row" style={{ gap: 4, flexWrap: "nowrap" }}>
                        <input
                          type="number"
                          min={0}
                          step={0.05}
                          value={selectedArray.row_spacing_m}
                          disabled={selectedArray.mounting === "flush"}
                          onChange={(e) => updateArray(selection.index, { row_spacing_m: Number(e.target.value) })}
                          style={{ width: "100%" }}
                        />
                        <button type="button" title="بدون تظليل 9 صباحًا حتى 3 عصرًا يوم 21 ديسمبر" onClick={() => autoSpacing(selection.index)} disabled={selectedArray.mounting === "flush"}>
                          تلقائي
                        </button>
                      </div>
                    </label>
                    <label className="field">
                      الفراغ بين الألواح (م)
                      <input type="number" min={0} step={0.01} value={selectedArray.module_gap_m} onChange={(e) => updateArray(selection.index, { module_gap_m: Number(e.target.value) })} />
                    </label>
                  </div>
                  <div className="row" style={{ flexWrap: "nowrap" }}>
                    <label className="field" style={{ flex: 1 }}>
                      أقصى عدد ألواح (اختياري)
                      <input type="number" min={1} value={maxModules} placeholder="املأ المساحة" onChange={(e) => setMaxModules(e.target.value ? Number(e.target.value) : "")} />
                    </label>
                    <button
                      type="button"
                      style={{ alignSelf: "end" }}
                      disabled={!annualKwh}
                      title={`تقدير بعائد ${ESTIMATED_YIELD_KWH_KWP} kWh/kWp؛ المحاكاة تعطي الرقم الدقيق`}
                      onClick={() => sizeToConsumption(selection.index)}
                    >
                      حسب الاستهلاك
                    </button>
                  </div>
                  <div className="row">
                    <button className="primary" onClick={() => autoLayout(selection.index)}>
                      توزيع تلقائي
                    </button>
                    <button onClick={() => updateArray(selection.index, { modules: [] })} disabled={!selectedArray.modules.length}>
                      مسح الألواح
                    </button>
                  </div>
                  <div className="muted small">
                    <span className="num">{selectedArray.modules.length}</span> لوح ·{" "}
                    <span className="num">{num((selectedArray.modules.length * Number(modulesById.get(selectedArray.module_id)?.specs.power_w ?? 0)) / 1000, 2)} kWp</span> · مساحة{" "}
                    <span className="num">{num(areaM2(ring(selectedArea)))} m²</span>
                  </div>
                </>
              ) : (
                defaultModuleId && (
                  <button onClick={() => update((c) => ({ ...c, roof_areas: c.roof_areas.map((a, i) => (i === selection.index ? { ...a, arrays: [newArray(defaultModuleId)] } : a)) }))}>
                    إضافة ألواح لهذه المساحة
                  </button>
                )
              )}
            </fieldset>
          </section>
        )}

        {selectedObstruction && selection?.type === "obstruction" && (
          <section className="stack">
            <div className="spread" style={{ marginBottom: 0 }}>
              <h3 style={{ margin: 0 }}>العائق</h3>
              {editable && (
                <button
                  className="danger"
                  onClick={() => {
                    update((c) => ({ ...c, obstructions: c.obstructions.filter((_, i) => i !== selection.index) }));
                    setSelection(null);
                  }}
                >
                  حذف
                </button>
              )}
            </div>
            <fieldset disabled={!editable} style={{ border: "none", padding: 0, margin: 0 }} className="form-grid">
              <label className="field">
                النوع
                <select
                  value={selectedObstruction.kind}
                  onChange={(e) =>
                    update((c) => ({ ...c, obstructions: c.obstructions.map((o, i) => (i === selection.index ? { ...o, kind: e.target.value as ObstructionKind } : o)) }))
                  }
                >
                  {Object.entries(OBSTRUCTION_KINDS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                الارتفاع (م) — للتظليل لاحقًا
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  value={selectedObstruction.height_m}
                  onChange={(e) => update((c) => ({ ...c, obstructions: c.obstructions.map((o, i) => (i === selection.index ? { ...o, height_m: Number(e.target.value) } : o)) }))}
                />
              </label>
            </fieldset>
            <div className="muted small">الألواح تبتعد عن العوائق {OBSTRUCTION_CLEARANCE_M} م؛ أعد التوزيع بعد إضافة عائق.</div>
          </section>
        )}

        <section className="stack">
          <h3>الانفرتر والهيكل</h3>
          <fieldset disabled={!editable} style={{ border: "none", padding: 0, margin: 0 }} className="stack">
            <div className="form-grid" style={{ gridTemplateColumns: "2fr 1fr" }}>
              <label className="field">
                الانفرتر
                <select value={content.inverter_id ?? ""} onChange={(e) => update((c) => ({ ...c, inverter_id: e.target.value ? Number(e.target.value) : null }))}>
                  <option value="">— بدون —</option>
                  {inverters.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.manufacturer} {c.model} ({c.specs.ac_power_kw} kW)
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                العدد
                <input type="number" min={0} value={content.inverter_count} onChange={(e) => update((c) => ({ ...c, inverter_count: Number(e.target.value) }))} />
              </label>
            </div>
            {suggestedInverters !== null && suggestedInverters !== content.inverter_count && (
              <button className="link small" onClick={() => update((c) => ({ ...c, inverter_count: suggestedInverters }))}>
                العدد المقترح لنسبة DC/AC ≈ 1.2: {suggestedInverters}
              </button>
            )}
            <label className="field">
              هيكل التثبيت
              <select value={content.racking_id ?? ""} onChange={(e) => update((c) => ({ ...c, racking_id: e.target.value ? Number(e.target.value) : null }))}>
                <option value="">— بدون —</option>
                {rackings.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.manufacturer} {c.model}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>
        </section>

        {editable && (
          <section className="stack">
            <button className="link" onClick={() => setShowLosses(!showLosses)}>
              {showLosses ? "▾" : "▸"} إعدادات الخسائر
            </button>
            {showLosses && (
              <>
                <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                  {(
                    [
                      ["albedo", "انعكاس الأرض (Albedo)", 0.01],
                      ["mismatch_pct", "عدم التطابق %", 0.1],
                      ["dc_wiring_pct", "أسلاك DC %", 0.1],
                      ["lid_pct", "التدهور الأولي %", 0.1],
                      ["ac_wiring_pct", "أسلاك AC %", 0.1],
                      ["transformer_pct", "المحولات %", 0.1],
                    ] as const
                  ).map(([key, label, step]) => (
                    <label key={key} className="field">
                      {label}
                      <input type="number" min={0} step={step} value={losses[key]} onChange={(e) => setLosses({ ...losses, [key]: Number(e.target.value) })} />
                    </label>
                  ))}
                </div>
                <div className="muted small">الاتساخ الشهري % (حسب جدول التنظيف)</div>
                <div className="months" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
                  {MONTHS.map((m, i) => (
                    <label key={m} className="field">
                      {m}
                      <input
                        type="number"
                        min={0}
                        max={50}
                        step={0.5}
                        value={losses.soiling_monthly_pct[i]}
                        onChange={(e) => setLosses({ ...losses, soiling_monthly_pct: losses.soiling_monthly_pct.map((v, j) => (j === i ? Number(e.target.value) : v)) })}
                      />
                    </label>
                  ))}
                </div>
              </>
            )}
          </section>
        )}

        {editable && (
          <div className="row">
            <button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
              {save.isPending ? "جارٍ الحفظ…" : dirty ? "حفظ التصميم" : "محفوظ"}
            </button>
            <button className="primary" onClick={() => simulate.mutate()} disabled={simulate.isPending || totals.modules === 0}>
              {simulate.isPending ? "جارٍ حساب الإنتاج…" : "تشغيل المحاكاة"}
            </button>
          </div>
        )}
      </aside>

      <div className="mapwrap">
        {editable && (
          <div className="toolbar">
            <button className={mode === "draw-area" ? "active" : ""} onClick={() => { setDraft([]); setMode(mode === "draw-area" ? "idle" : "draw-area"); }}>
              رسم سطح/أرض
            </button>
            <select value={obstructionKind} onChange={(e) => setObstructionKind(e.target.value as ObstructionKind)}>
              {Object.entries(OBSTRUCTION_KINDS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <button className={mode === "draw-obstruction" ? "active" : ""} onClick={() => { setDraft([]); setMode(mode === "draw-obstruction" ? "idle" : "draw-obstruction"); }}>
              رسم عائق
            </button>
            <button className={mode === "edit-modules" ? "active" : ""} onClick={() => setMode(mode === "edit-modules" ? "idle" : "edit-modules")}>
              تعديل الألواح يدويًا
            </button>
            {drawing && (
              <>
                <button onClick={() => setDraft((d) => d.slice(0, -1))} disabled={!draft.length}>
                  تراجع
                </button>
                <button className="primary" onClick={finishDrawing} disabled={draft.length < 3}>
                  إنهاء
                </button>
              </>
            )}
          </div>
        )}
        {drawing && <div className="hint">انقر لإضافة نقاط · نقر مزدوج أو Enter للإنهاء · Esc للإلغاء</div>}
        {mode === "edit-modules" && <div className="hint">انقر على لوح لحذفه، أو داخل المساحة المحددة لإضافة لوح</div>}
        <div ref={container} className="map" />
      </div>
    </div>
  );
}
