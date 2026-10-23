import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../../api/client";
import type { PriceItem, PriceUnit, Tariff } from "../../api/types";
import { PRICE_UNITS } from "../../lib/format";

function PriceItems() {
  const queryClient = useQueryClient();
  const items = useQuery({ queryKey: ["price-items"], queryFn: () => api.get<PriceItem[]>("/price-items") });
  const [rows, setRows] = useState<(Omit<PriceItem, "id"> & { id?: number })[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (items.data) setRows(items.data);
  }, [items.data]);

  const save = useMutation({
    mutationFn: async () => {
      for (const row of rows) {
        const { id, ...body } = row;
        if (id) await api.put(`/price-items/${id}`, body);
        else if (body.name.trim()) await api.post("/price-items", body);
      }
    },
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["price-items"] });
    },
    onError: (err) => setError((err as Error).message),
  });

  return (
    <div className="card stack">
      <h2>بنود عرض السعر</h2>
      <p className="muted small">تُضاف لكل عرض سعر مع المكونات. الأسعار قبل ضريبة القيمة المضافة.</p>
      <table>
        <thead>
          <tr>
            <th>البند</th>
            <th>الوحدة</th>
            <th className="n">السعر</th>
            <th className="n">الترتيب</th>
            <th>مفعّل</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const set = (patch: Partial<PriceItem>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
            return (
              <tr key={row.id ?? `new${i}`}>
                <td>
                  <input value={row.name} onChange={(e) => set({ name: e.target.value })} style={{ width: "100%" }} />
                </td>
                <td>
                  <select value={row.unit} onChange={(e) => set({ unit: e.target.value as PriceUnit })}>
                    {Object.entries(PRICE_UNITS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="n">
                  <input type="number" min={0} step="any" value={row.unit_price_sar} onChange={(e) => set({ unit_price_sar: Number(e.target.value) })} style={{ width: 110 }} />
                </td>
                <td className="n">
                  <input type="number" value={row.sort_order} onChange={(e) => set({ sort_order: Number(e.target.value) })} style={{ width: 70 }} />
                </td>
                <td>
                  <input type="checkbox" checked={row.is_active} onChange={(e) => set({ is_active: e.target.checked })} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {error && <div className="error">{error}</div>}
      <div className="row">
        <button onClick={() => setRows([...rows, { name: "", unit: "per_kwp", unit_price_sar: 0, sort_order: rows.length + 1, is_active: true }])}>+ بند</button>
        <button className="primary" onClick={() => save.mutate()} disabled={save.isPending}>
          حفظ البنود
        </button>
      </div>
    </div>
  );
}

function TariffEditor({ tariff }: { tariff: Tariff }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(tariff);
  const [status, setStatus] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.put<Tariff>(`/tariffs/${tariff.code}`, draft),
    onSuccess: () => {
      setStatus("تم الحفظ");
      queryClient.invalidateQueries({ queryKey: ["tariffs"] });
    },
    onError: (err) => setStatus((err as Error).message),
  });
  return (
    <div className="card stack">
      <div className="spread" style={{ marginBottom: 0 }}>
        <h3 style={{ margin: 0 }}>{draft.name}</h3>
        <span className="muted small">{status}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>حتى (kWh شهريًا)</th>
            <th>السعر (ريال/kWh)</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {draft.tiers.map((tier, i) => (
            <tr key={i}>
              <td>
                {i === draft.tiers.length - 1 ? (
                  <span className="muted">بلا حد</span>
                ) : (
                  <input type="number" min={1} value={tier.up_to_kwh ?? ""} onChange={(e) => setDraft({ ...draft, tiers: draft.tiers.map((t, j) => (j === i ? { ...t, up_to_kwh: Number(e.target.value) } : t)) })} style={{ width: 110 }} />
                )}
              </td>
              <td>
                <input type="number" min={0} step={0.001} value={tier.rate_sar} onChange={(e) => setDraft({ ...draft, tiers: draft.tiers.map((t, j) => (j === i ? { ...t, rate_sar: Number(e.target.value) } : t)) })} style={{ width: 110 }} />
              </td>
              <td>
                {draft.tiers.length > 1 && (
                  <button
                    className="danger"
                    onClick={() => {
                      const tiers = draft.tiers.filter((_, j) => j !== i);
                      tiers[tiers.length - 1] = { ...tiers[tiers.length - 1], up_to_kwh: null };
                      setDraft({ ...draft, tiers });
                    }}
                  >
                    ×
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="form-grid">
        <label className="field">
          ضريبة القيمة المضافة %
          <input type="number" min={0} max={100} value={Math.round(draft.vat * 1000) / 10} onChange={(e) => setDraft({ ...draft, vat: Number(e.target.value) / 100 })} />
        </label>
        <label className="field">
          سعر الفائض المُصدَّر (ريال/kWh)
          <input type="number" min={0} step={0.001} value={draft.export_rate_sar} onChange={(e) => setDraft({ ...draft, export_rate_sar: Number(e.target.value) })} />
        </label>
      </div>
      <div className="row">
        <button
          onClick={() => {
            const tiers = draft.tiers.map((t, j) => (j === draft.tiers.length - 1 ? { ...t, up_to_kwh: (draft.tiers[j - 1]?.up_to_kwh ?? 0) + 6000 } : t));
            setDraft({ ...draft, tiers: [...tiers, { up_to_kwh: null, rate_sar: draft.tiers[draft.tiers.length - 1].rate_sar }] });
          }}
        >
          + شريحة
        </button>
        <button className="primary" onClick={() => save.mutate()} disabled={save.isPending}>
          حفظ التعرفة
        </button>
      </div>
    </div>
  );
}

export function PricesPage() {
  const tariffs = useQuery({ queryKey: ["tariffs"], queryFn: () => api.get<Tariff[]>("/tariffs") });
  return (
    <div className="stack">
      <h1>الأسعار والتعرفة</h1>
      <PriceItems />
      <h2>تعرفة الكهرباء</h2>
      <p className="muted small">
        القيم الافتراضية: جدول الشركة السعودية للكهرباء المطبق منذ 2018، والتجاري 0.22/0.32 حسب تقارير 2026، وسعر الفائض حسب مقترح هيئة تنظيم الكهرباء. راجعها قبل الاعتماد.
      </p>
      <div className="grid cols-2">{tariffs.data?.map((t) => <TariffEditor key={t.code} tariff={t} />)}</div>
    </div>
  );
}
