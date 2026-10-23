import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api } from "../../api/client";
import type { Component, ComponentKind, PriceUnit } from "../../api/types";
import { COMPONENT_KINDS, PRICE_UNITS, num } from "../../lib/format";

// الحقول الفنية لكل نوع (من ورقة البيانات)
const SPEC_FIELDS: Record<ComponentKind, { key: string; label: string; required?: boolean }[]> = {
  module: [
    { key: "power_w", label: "القدرة (W)", required: true },
    { key: "length_m", label: "الطول (m)", required: true },
    { key: "width_m", label: "العرض (m)", required: true },
    { key: "gamma_pdc_pct", label: "معامل حرارة القدرة (%/°C)" },
    { key: "voc", label: "Voc (V)" },
    { key: "isc", label: "Isc (A)" },
    { key: "vmp", label: "Vmp (V)" },
    { key: "imp", label: "Imp (A)" },
    { key: "beta_voc_pct", label: "معامل حرارة Voc (%/°C)" },
  ],
  inverter: [
    { key: "ac_power_kw", label: "قدرة AC (kW)", required: true },
    { key: "efficiency_pct", label: "الكفاءة (%)" },
    { key: "max_dc_voltage", label: "أقصى جهد DC (V)" },
    { key: "mppt_min_v", label: "أدنى جهد MPPT (V)" },
    { key: "mppt_max_v", label: "أعلى جهد MPPT (V)" },
    { key: "mppt_count", label: "عدد مداخل MPPT" },
  ],
  racking: [],
};

const DEFAULT_UNIT: Record<ComponentKind, PriceUnit> = { module: "per_watt", inverter: "per_unit", racking: "per_kwp" };

interface Draft {
  id?: number;
  kind: ComponentKind;
  manufacturer: string;
  model: string;
  specs: Record<string, string>;
  price_sar: number;
  price_unit: PriceUnit;
  is_active: boolean;
}

const blank = (kind: ComponentKind): Draft => ({ kind, manufacturer: "", model: "", specs: {}, price_sar: 0, price_unit: DEFAULT_UNIT[kind], is_active: true });

export function ComponentsPage() {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<ComponentKind>("module");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["components", "all", kind], queryFn: () => api.get<Component[]>(`/components?kind=${kind}&include_inactive=true`) });

  const save = useMutation({
    mutationFn: (d: Draft) => {
      const specs = Object.fromEntries(
        Object.entries(d.specs)
          .filter(([, v]) => v !== "")
          .map(([k, v]) => [k, Number.isNaN(Number(v)) ? v : Number(v)]),
      );
      const body = { manufacturer: d.manufacturer, model: d.model, specs, price_sar: d.price_sar, price_unit: d.price_unit, is_active: d.is_active };
      return d.id ? api.patch<Component>(`/components/${d.id}`, body) : api.post<Component>("/components", { ...body, kind: d.kind });
    },
    onSuccess: () => {
      setDraft(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["components"] });
    },
    onError: (err) => setError((err as Error).message),
  });

  function edit(c: Component) {
    setDraft({ ...c, specs: Object.fromEntries(Object.entries(c.specs).map(([k, v]) => [k, String(v)])) });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (draft) save.mutate(draft);
  }

  return (
    <div className="stack">
      <div className="spread">
        <h1>قاعدة المكونات</h1>
        <button className="primary" onClick={() => setDraft(blank(kind))}>
          + إضافة {COMPONENT_KINDS[kind]}
        </button>
      </div>
      <div className="row">
        {(Object.keys(COMPONENT_KINDS) as ComponentKind[]).map((k) => (
          <button key={k} className={k === kind ? "active" : ""} onClick={() => { setKind(k); setDraft(null); }}>
            {COMPONENT_KINDS[k]}
          </button>
        ))}
      </div>

      {draft && (
        <form className="card stack" onSubmit={submit}>
          <h2>{draft.id ? "تعديل مكون" : "مكون جديد"}</h2>
          <div className="form-grid">
            <label className="field">
              الشركة المصنعة
              <input value={draft.manufacturer} onChange={(e) => setDraft({ ...draft, manufacturer: e.target.value })} required />
            </label>
            <label className="field">
              الموديل
              <input value={draft.model} onChange={(e) => setDraft({ ...draft, model: e.target.value })} required />
            </label>
            {SPEC_FIELDS[draft.kind].map((f) => (
              <label key={f.key} className="field">
                {f.label}
                {f.required ? " *" : ""}
                <input type="number" step="any" value={draft.specs[f.key] ?? ""} required={f.required} onChange={(e) => setDraft({ ...draft, specs: { ...draft.specs, [f.key]: e.target.value } })} />
              </label>
            ))}
            <label className="field">
              السعر (ريال، قبل الضريبة)
              <input type="number" step="any" min={0} value={draft.price_sar} onChange={(e) => setDraft({ ...draft, price_sar: Number(e.target.value) })} />
            </label>
            <label className="field">
              وحدة السعر
              <select value={draft.price_unit} onChange={(e) => setDraft({ ...draft, price_unit: e.target.value as PriceUnit })}>
                {Object.entries(PRICE_UNITS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              الحالة
              <select value={draft.is_active ? "1" : "0"} onChange={(e) => setDraft({ ...draft, is_active: e.target.value === "1" })}>
                <option value="1">متاح</option>
                <option value="0">موقوف</option>
              </select>
            </label>
          </div>
          {error && <div className="error">{error}</div>}
          <div className="row">
            <button className="primary" disabled={save.isPending}>
              حفظ
            </button>
            <button type="button" onClick={() => setDraft(null)}>
              إلغاء
            </button>
          </div>
        </form>
      )}

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>الشركة</th>
              <th>الموديل</th>
              <th>المواصفات</th>
              <th className="n">السعر</th>
              <th>الحالة</th>
            </tr>
          </thead>
          <tbody>
            {list.data?.map((c) => (
              <tr key={c.id} className="clickable" onClick={() => edit(c)}>
                <td>{c.manufacturer}</td>
                <td>{c.model}</td>
                <td className="muted small num">
                  {SPEC_FIELDS[c.kind]
                    .filter((f) => c.specs[f.key] !== undefined)
                    .slice(0, 4)
                    .map((f) => `${f.label.split(" (")[0]}: ${c.specs[f.key]}`)
                    .join(" · ")}
                </td>
                <td className="n">
                  <span className="num">{num(c.price_sar, 2)}</span> {PRICE_UNITS[c.price_unit]}
                </td>
                <td>{c.is_active ? "متاح" : <span className="muted">موقوف</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {list.data?.length === 0 && <div className="center muted">لا توجد مكونات من هذا النوع.</div>}
      </div>
    </div>
  );
}
