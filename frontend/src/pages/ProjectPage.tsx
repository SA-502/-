import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { Design, DesignSummary, Project, ProjectStatus, Report, Simulation } from "../api/types";
import { useAuth } from "../auth";
import { CUSTOMER_TYPES, MONTHS, STATUS_LABELS, date, num, sar } from "../lib/format";

function DesignRow({ summary, projectId }: { summary: DesignSummary; projectId: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { can } = useAuth();
  const design = useQuery({ queryKey: ["design", summary.id], queryFn: () => api.get<Design>(`/designs/${summary.id}`) });
  const sims = useQuery({ queryKey: ["simulations", summary.id], queryFn: () => api.get<Simulation[]>(`/designs/${summary.id}/simulations`) });
  const copy = useMutation({
    mutationFn: () => api.post<Design>(`/projects/${projectId}/designs`, { copy_from_id: summary.id }),
    onSuccess: (d) => {
      queryClient.invalidateQueries({ queryKey: ["project", String(projectId)] });
      navigate(`/designs/${d.id}`);
    },
  });
  const latest = sims.data?.[0];
  return (
    <tr>
      <td>
        <b>{summary.name}</b>
        <div className="muted small">
          النسخة <span className="num">{summary.version_no}</span> · {date(summary.created_at)}
        </div>
      </td>
      <td className="n num">{design.data ? design.data.module_count : "…"}</td>
      <td className="n num">{design.data ? num(design.data.dc_kwp, 2) : "…"}</td>
      <td className="n num">{latest ? num(latest.results.annual_energy_kwh) : "—"}</td>
      <td className="n num">{latest ? num(latest.results.specific_yield_kwh_kwp) : "—"}</td>
      <td>
        <div className="row">
          <Link className="btn" to={`/designs/${summary.id}`}>
            {can("engineer") ? "فتح المصمم" : "عرض"}
          </Link>
          {latest && (
            <Link className="btn" to={`/simulations/${latest.id}`}>
              النتائج والعرض
            </Link>
          )}
          {can("engineer") && (
            <button onClick={() => copy.mutate()} disabled={copy.isPending}>
              نسخة جديدة منه
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export function ProjectPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { can } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const project = useQuery({ queryKey: ["project", id], queryFn: () => api.get<Project>(`/projects/${id}`) });
  const reports = useQuery({ queryKey: ["reports", id], queryFn: () => api.get<Report[]>(`/projects/${id}/reports`) });

  const createDesign = useMutation({
    mutationFn: () => api.post<Design>(`/projects/${id}/designs`, {}),
    onSuccess: (d) => navigate(`/designs/${d.id}`),
    onError: (err) => setError((err as Error).message),
  });
  const setStatus = useMutation({
    mutationFn: (status: ProjectStatus) => api.patch<Project>(`/projects/${id}`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", id] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  if (project.isLoading) return <div className="center muted">جارٍ التحميل…</div>;
  if (project.error || !project.data) return <div className="error">{(project.error as Error)?.message ?? "غير موجود"}</div>;
  const p = project.data;
  const yearly = p.monthly_consumption_kwh?.reduce((a, b) => a + b, 0);

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{p.name}</h1>
          <div className="row muted">
            <span className={`badge ${p.status}`}>{STATUS_LABELS[p.status]}</span>
            <span>
              {p.customer.name} · {CUSTOMER_TYPES[p.customer.customer_type]} {p.customer.phone && <span className="num">· {p.customer.phone}</span>}
            </span>
            <span>{p.city}</span>
          </div>
        </div>
        <div className="row">
          <select value={p.status} onChange={(e) => setStatus.mutate(e.target.value as ProjectStatus)}>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <Link className="btn" to={`/projects/${p.id}/edit`}>
            تعديل البيانات
          </Link>
          {can("engineer") && (
            <button className="primary" onClick={() => createDesign.mutate()} disabled={createDesign.isPending}>
              + تصميم جديد
            </button>
          )}
        </div>
      </div>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h2>الاستهلاك</h2>
        {p.monthly_consumption_kwh ? (
          <table>
            <thead>
              <tr>
                {MONTHS.map((m) => (
                  <th key={m} className="n">
                    {m}
                  </th>
                ))}
                <th className="n">السنة</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                {p.monthly_consumption_kwh.map((v, i) => (
                  <td key={i} className="n num">
                    {num(v)}
                  </td>
                ))}
                <td className="n num">
                  <b>{num(yearly)}</b>
                </td>
              </tr>
            </tbody>
          </table>
        ) : (
          <div className="notice">لم يُدخل الاستهلاك بعد؛ مطلوب للدراسة المالية.</div>
        )}
      </div>

      <div className="card" style={{ padding: 0 }}>
        <h2 style={{ padding: "16px 16px 0" }}>نسخ التصميم</h2>
        <table>
          <thead>
            <tr>
              <th>النسخة</th>
              <th className="n">الألواح</th>
              <th className="n">kWp</th>
              <th className="n">الإنتاج السنوي (kWh)</th>
              <th className="n">kWh/kWp</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {p.designs.map((d) => (
              <DesignRow key={d.id} summary={d} projectId={p.id} />
            ))}
          </tbody>
        </table>
        {p.designs.length === 0 && <div className="center muted">لا توجد تصاميم بعد.</div>}
      </div>

      <div className="card" style={{ padding: 0 }}>
        <h2 style={{ padding: "16px 16px 0" }}>التقارير الصادرة</h2>
        <table>
          <thead>
            <tr>
              <th>رقم العرض</th>
              <th>التاريخ</th>
              <th>اللغة</th>
              <th className="n">السعر</th>
              <th className="n">الاسترداد</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {reports.data?.map((r) => (
              <tr key={r.id}>
                <td className="num">Q-{String(r.id).padStart(5, "0")}</td>
                <td>{date(r.created_at)}</td>
                <td>{r.language === "ar" ? "عربي" : "إنجليزي"}</td>
                <td className="n num">{sar(r.quote.capex_sar)}</td>
                <td className="n num">{r.financial.payback_years ? `${num(r.financial.payback_years, 1)} سنة` : "—"}</td>
                <td>
                  <button onClick={() => api.openPdf(`/reports/${r.id}/pdf`).catch((e) => setError(e.message))}>فتح PDF</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {reports.data?.length === 0 && <div className="center muted">لم يصدر تقرير بعد.</div>}
      </div>
    </div>
  );
}
