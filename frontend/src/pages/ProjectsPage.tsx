import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { Project, ProjectStatus } from "../api/types";
import { CUSTOMER_TYPES, STATUS_LABELS, date } from "../lib/format";

export function ProjectsPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<ProjectStatus | "">("");
  const params = new URLSearchParams();
  if (q.trim()) params.set("q", q.trim());
  if (status) params.set("status", status);

  const projects = useQuery({ queryKey: ["projects", q, status], queryFn: () => api.get<Project[]>(`/projects?${params}`) });
  const stats = useQuery({ queryKey: ["project-stats"], queryFn: () => api.get<Record<string, number>>("/projects/stats") });

  return (
    <>
      <div className="spread">
        <h1>المشاريع</h1>
        <Link to="/projects/new" className="btn primary">
          + مشروع جديد
        </Link>
      </div>

      <div className="row" style={{ marginBottom: 14 }}>
        <button className={status === "" ? "active" : ""} onClick={() => setStatus("")}>
          الكل
        </button>
        {(Object.keys(STATUS_LABELS) as ProjectStatus[]).map((s) => (
          <button key={s} className={status === s ? "active" : ""} onClick={() => setStatus(s)}>
            {STATUS_LABELS[s]} <span className="num">{stats.data?.[s] ?? 0}</span>
          </button>
        ))}
        <input placeholder="بحث بالمشروع أو العميل أو المدينة" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1, minWidth: 220 }} />
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>المشروع</th>
              <th>العميل</th>
              <th>النوع</th>
              <th>المدينة</th>
              <th>الحالة</th>
              <th className="n">نسخ التصميم</th>
              <th>آخر تحديث</th>
            </tr>
          </thead>
          <tbody>
            {projects.data?.map((p) => (
              <tr key={p.id} className="clickable" onClick={() => navigate(`/projects/${p.id}`)}>
                <td>
                  <b>{p.name}</b>
                </td>
                <td>{p.customer.name}</td>
                <td>{CUSTOMER_TYPES[p.customer.customer_type]}</td>
                <td>{p.city ?? "—"}</td>
                <td>
                  <span className={`badge ${p.status}`}>{STATUS_LABELS[p.status]}</span>
                </td>
                <td className="n num">{p.designs.length}</td>
                <td className="muted">{date(p.updated_at ?? p.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {projects.isLoading && <div className="center muted">جارٍ التحميل…</div>}
        {projects.data?.length === 0 && <div className="center muted">لا توجد مشاريع بعد.</div>}
        {projects.error && <div className="error">{(projects.error as Error).message}</div>}
      </div>
    </>
  );
}
