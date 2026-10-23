import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api/client";
import type { Design, FinanceParams, Financial, Project, Quote, Report, Simulation } from "../api/types";
import { MONTHS, date, num, sar } from "../lib/format";

const DEFAULT_FINANCE: FinanceParams = {
  discount_pct: 0,
  extra_lines: [],
  override_total_sar: null,
  years: 25,
  discount_rate_pct: 6,
  degradation_pct: 0.5,
  om_pct: 1,
  tariff_escalation_pct: 0,
  inverter_replacement_year: null,
  inverter_replacement_cost_sar: 0,
};

function Kpi({ label, value, hl }: { label: string; value: string; hl?: boolean }) {
  return (
    <div className={`card kpi ${hl ? "hl" : ""}`}>
      <div className="label">{label}</div>
      <div className="value num">{value}</div>
    </div>
  );
}

export function ResultsPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const sim = useQuery({ queryKey: ["simulation", id], queryFn: () => api.get<Simulation>(`/simulations/${id}`) });
  const design = useQuery({
    queryKey: ["design", sim.data?.design_id],
    queryFn: () => api.get<Design>(`/designs/${sim.data!.design_id}`),
    enabled: Boolean(sim.data),
  });
  const project = useQuery({
    queryKey: ["project", String(design.data?.project_id)],
    queryFn: () => api.get<Project>(`/projects/${design.data!.project_id}`),
    enabled: Boolean(design.data),
  });

  const [params, setParams] = useState<FinanceParams>(DEFAULT_FINANCE);
  const [language, setLanguage] = useState<"ar" | "en">("ar");
  const [study, setStudy] = useState<{ quote: Quote; financial: Financial } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const preview = useMutation({
    mutationFn: (p: FinanceParams) => api.post<{ quote: Quote; financial: Financial }>(`/simulations/${id}/financial`, p),
    onSuccess: (data) => {
      setStudy(data);
      setError(null);
    },
    onError: (err) => setError((err as Error).message),
  });

  const issue = useMutation({
    mutationFn: () => api.post<Report>(`/simulations/${id}/reports`, { ...params, language }),
    onSuccess: async (report) => {
      queryClient.invalidateQueries({ queryKey: ["reports", String(design.data?.project_id)] });
      queryClient.invalidateQueries({ queryKey: ["project", String(design.data?.project_id)] });
      await api.openPdf(`/reports/${report.id}/pdf`);
    },
    onError: (err) => setError((err as Error).message),
  });

  useEffect(() => {
    if (sim.data && project.data?.monthly_consumption_kwh) preview.mutate(params);
    // نحسب المعاينة أول مرة فقط؛ بعدها بزر "تحديث"
  }, [sim.data?.id, project.data?.id]);

  if (sim.error) return <div className="error">{(sim.error as Error).message}</div>;
  if (!sim.data || !design.data || !project.data) return <div className="center muted">جارٍ التحميل…</div>;

  const r = sim.data.results;
  const consumption = project.data.monthly_consumption_kwh;
  const chartData = MONTHS.map((m, i) => ({ month: m, production: r.monthly_energy_kwh[i], consumption: consumption?.[i] ?? null }));
  const maxLoss = Math.max(...r.losses.slice(1).map((l) => l.loss_pct), 1);
  const fin = study?.financial;
  const set = <K extends keyof FinanceParams>(key: K, value: FinanceParams[K]) => setParams((p) => ({ ...p, [key]: value }));

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>نتائج المحاكاة</h1>
          <div className="muted">
            <Link to={`/projects/${project.data.id}`}>{project.data.name}</Link> · {design.data.name} · {date(sim.data.created_at)}
          </div>
        </div>
        <Link className="btn" to={`/designs/${design.data.id}`}>
          العودة للمصمم
        </Link>
      </div>

      {sim.data.inputs.ac_kw_assumed && <div className="notice">لم يُحدد انفرتر في التصميم؛ افتُرضت قدرة AC مساوية لقدرة الألواح بدون قص.</div>}

      <div className="grid cols-4">
        <Kpi label="قدرة النظام" value={`${num(r.dc_kwp, 2)} kWp`} />
        <Kpi label="الإنتاج السنوي" value={`${num(r.annual_energy_kwh)} kWh`} hl />
        <Kpi label="العائد النوعي" value={`${num(r.specific_yield_kwh_kwp)} kWh/kWp`} />
        <Kpi label="نسبة الأداء (PR)" value={`${num(r.performance_ratio * 100, 1)}%`} />
        <Kpi label="الإشعاع الأفقي السنوي" value={`${num(r.annual_ghi_kwh_m2)} kWh/m²`} />
        <Kpi label="الإشعاع على اللوح" value={`${num(r.annual_poa_kwh_m2)} kWh/m²`} />
        {consumption && <Kpi label="تغطية الاستهلاك" value={`${num((r.annual_energy_kwh / consumption.reduce((a, b) => a + b, 0)) * 100)}%`} />}
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2>الإنتاج الشهري مقابل الاستهلاك (kWh)</h2>
          <div style={{ height: 300, direction: "ltr" }}>
            <ResponsiveContainer>
              <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="month" reversed tick={{ fontSize: 11 }} interval={0} angle={-35} textAnchor="end" height={50} />
                <YAxis orientation="right" tick={{ fontSize: 11 }} tickFormatter={(v) => num(v)} />
                <Tooltip formatter={(v) => num(Number(v))} />
                <Legend />
                <Bar dataKey="production" name="الإنتاج الشمسي" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                {consumption && <Line dataKey="consumption" name="الاستهلاك" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3 }} />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card">
          <h2>دليل الخسائر</h2>
          <table>
            <thead>
              <tr>
                <th>المرحلة</th>
                <th className="n">الطاقة بعدها (kWh)</th>
                <th className="n">الخسارة</th>
                <th style={{ width: "30%" }}></th>
              </tr>
            </thead>
            <tbody>
              {r.losses.map((l, i) => (
                <tr key={l.key}>
                  <td>{l.label}</td>
                  <td className="n num">{num(l.energy_kwh)}</td>
                  <td className="n num">{i === 0 ? "—" : `${num(l.loss_pct, 1)}%`}</td>
                  <td>{i > 0 && l.loss_pct > 0 && <div className="bar" style={{ width: `${(l.loss_pct / maxLoss) * 100}%` }} />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2>الدراسة المالية وعرض السعر</h2>
        {!consumption ? (
          <div className="notice">
            أدخل الاستهلاك الشهري في <Link to={`/projects/${project.data.id}/edit`}>بيانات المشروع</Link> لحساب التوفير والاسترداد.
          </div>
        ) : (
          <div className="stack">
            <div className="form-grid">
              <label className="field">
                خصم على العرض %
                <input type="number" min={0} max={100} step={0.5} value={params.discount_pct} onChange={(e) => set("discount_pct", Number(e.target.value))} />
              </label>
              <label className="field">
                سعر نهائي يدوي (اختياري)
                <input type="number" min={0} value={params.override_total_sar ?? ""} onChange={(e) => set("override_total_sar", e.target.value ? Number(e.target.value) : null)} />
              </label>
              <label className="field">
                معدل الخصم المالي %
                <input type="number" min={0} max={30} step={0.5} value={params.discount_rate_pct} onChange={(e) => set("discount_rate_pct", Number(e.target.value))} />
              </label>
              <label className="field">
                تراجع الإنتاج سنويًا %
                <input type="number" min={0} max={5} step={0.05} value={params.degradation_pct} onChange={(e) => set("degradation_pct", Number(e.target.value))} />
              </label>
              <label className="field">
                التشغيل والصيانة % سنويًا
                <input type="number" min={0} max={10} step={0.1} value={params.om_pct} onChange={(e) => set("om_pct", Number(e.target.value))} />
              </label>
              <label className="field">
                زيادة التعرفة سنويًا %
                <input type="number" min={-10} max={20} step={0.5} value={params.tariff_escalation_pct} onChange={(e) => set("tariff_escalation_pct", Number(e.target.value))} />
              </label>
              <label className="field">
                سنة استبدال الانفرتر
                <input type="number" min={1} max={40} value={params.inverter_replacement_year ?? ""} onChange={(e) => set("inverter_replacement_year", e.target.value ? Number(e.target.value) : null)} />
              </label>
              <label className="field">
                تكلفة الاستبدال (ريال)
                <input type="number" min={0} value={params.inverter_replacement_cost_sar} onChange={(e) => set("inverter_replacement_cost_sar", Number(e.target.value))} />
              </label>
            </div>

            <div>
              <div className="muted small" style={{ marginBottom: 6 }}>
                بنود إضافية في العرض
              </div>
              {params.extra_lines.map((line, i) => (
                <div key={i} className="row" style={{ marginBottom: 6 }}>
                  <input placeholder="الوصف" value={line.description} onChange={(e) => set("extra_lines", params.extra_lines.map((l, j) => (j === i ? { ...l, description: e.target.value } : l)))} style={{ flex: 2 }} />
                  <input type="number" placeholder="الكمية" value={line.quantity} onChange={(e) => set("extra_lines", params.extra_lines.map((l, j) => (j === i ? { ...l, quantity: Number(e.target.value) } : l)))} style={{ width: 90 }} />
                  <input type="number" placeholder="السعر" value={line.unit_price_sar} onChange={(e) => set("extra_lines", params.extra_lines.map((l, j) => (j === i ? { ...l, unit_price_sar: Number(e.target.value) } : l)))} style={{ width: 120 }} />
                  <button className="danger" onClick={() => set("extra_lines", params.extra_lines.filter((_, j) => j !== i))}>
                    ×
                  </button>
                </div>
              ))}
              <button className="link" onClick={() => set("extra_lines", [...params.extra_lines, { description: "", quantity: 1, unit_price_sar: 0 }])}>
                + إضافة بند
              </button>
            </div>

            <div className="row">
              <button onClick={() => preview.mutate(params)} disabled={preview.isPending}>
                {preview.isPending ? "جارٍ الحساب…" : "تحديث الحساب"}
              </button>
              <select value={language} onChange={(e) => setLanguage(e.target.value as "ar" | "en")}>
                <option value="ar">تقرير عربي</option>
                <option value="en">تقرير إنجليزي</option>
              </select>
              <button className="primary" onClick={() => issue.mutate()} disabled={issue.isPending || !study}>
                {issue.isPending ? "جارٍ إصدار التقرير…" : "إصدار التقرير PDF"}
              </button>
            </div>
            {error && <div className="error">{error}</div>}

            {study && fin && (
              <>
                <div className="grid cols-4">
                  <Kpi label="السعر الإجمالي شامل الضريبة" value={sar(study.quote.capex_sar)} hl />
                  <Kpi label="توفير السنة الأولى" value={sar(fin.first_year_savings_sar)} hl />
                  <Kpi label="فترة الاسترداد" value={fin.payback_years ? `${num(fin.payback_years, 1)} سنة` : "لا يسترد"} hl />
                  <Kpi label="صافي القيمة الحالية" value={sar(fin.npv_sar)} />
                  <Kpi label="العائد الداخلي" value={fin.irr !== null ? `${num(fin.irr * 100, 1)}%` : "—"} />
                  <Kpi label="تكلفة الكيلوواط ساعة" value={`${num(fin.lcoe_sar_per_kwh, 3)} ر.س`} />
                  <Kpi label={`إجمالي التوفير (${fin.rows.length} سنة)`} value={sar(fin.lifetime_savings_sar)} />
                  <Kpi label="الفاتورة السنوية قبل ← بعد" value={`${num(fin.first_year_bill_before_sar)} ← ${num(fin.first_year_bill_after_sar)}`} />
                </div>

                <div className="grid cols-2">
                  <div>
                    <h3>عرض السعر</h3>
                    <table>
                      <thead>
                        <tr>
                          <th>البند</th>
                          <th className="n">الكمية</th>
                          <th className="n">سعر الوحدة</th>
                          <th className="n">المجموع</th>
                        </tr>
                      </thead>
                      <tbody>
                        {study.quote.lines.map((l, i) => (
                          <tr key={i}>
                            <td>{l.description}</td>
                            <td className="n">
                              <span className="num">{num(l.quantity, l.quantity % 1 ? 2 : 0)}</span> {l.unit_label}
                            </td>
                            <td className="n num">{num(l.unit_price_sar, 2)}</td>
                            <td className="n num">{num(l.total_sar, 2)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr>
                          <td colSpan={3}>الصافي بعد الخصم</td>
                          <td className="n num">{num(study.quote.net_sar, 2)}</td>
                        </tr>
                        <tr>
                          <td colSpan={3}>ضريبة القيمة المضافة</td>
                          <td className="n num">{num(study.quote.vat_sar, 2)}</td>
                        </tr>
                        <tr>
                          <td colSpan={3}>الإجمالي</td>
                          <td className="n num">{num(study.quote.total_sar, 2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                  <div>
                    <h3>الموازنة الشهرية (السنة الأولى)</h3>
                    <table>
                      <thead>
                        <tr>
                          <th>الشهر</th>
                          <th className="n">استهلاك ذاتي</th>
                          <th className="n">مُصدَّر</th>
                          <th className="n">الفاتورة قبل</th>
                          <th className="n">بعد</th>
                          <th className="n">التوفير</th>
                        </tr>
                      </thead>
                      <tbody>
                        {fin.first_year_months.map((m, i) => (
                          <tr key={i}>
                            <td>{MONTHS[i]}</td>
                            <td className="n num">{num(m.self_consumed_kwh)}</td>
                            <td className="n num">{num(m.exported_kwh)}</td>
                            <td className="n num">{num(m.bill_before_sar)}</td>
                            <td className="n num">{num(m.payable_sar)}</td>
                            <td className="n num">{num(m.savings_sar)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
