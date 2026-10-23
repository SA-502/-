import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api } from "../../api/client";
import type { Role, User } from "../../api/types";
import { useAuth } from "../../auth";
import { ROLE_LABELS } from "../../lib/format";

export function UsersPage() {
  const queryClient = useQueryClient();
  const { user: me } = useAuth();
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get<User[]>("/users") });
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "engineer" as Role });
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api.post<User>("/users", form),
    onSuccess: () => {
      setForm({ name: "", email: "", password: "", role: "engineer" });
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err) => setError((err as Error).message),
  });
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<User> & { password?: string } }) => api.patch<User>(`/users/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    onError: (err) => setError((err as Error).message),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <div className="stack">
      <h1>المستخدمون والصلاحيات</h1>
      <div className="notice small">
        المهندس: التصميم والمحاكاة · المبيعات: العملاء والمشاريع وإصدار العروض · المدير: كل شيء بما فيه المكونات والأسعار والمستخدمون.
      </div>
      <form className="card form-grid" onSubmit={submit}>
        <label className="field">
          الاسم
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        </label>
        <label className="field">
          البريد
          <input type="email" dir="ltr" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        </label>
        <label className="field">
          كلمة المرور (8 أحرف على الأقل)
          <input type="password" dir="ltr" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        </label>
        <label className="field">
          الدور
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            {Object.entries(ROLE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <div style={{ alignSelf: "end" }}>
          <button className="primary" disabled={create.isPending}>
            إضافة مستخدم
          </button>
        </div>
      </form>
      {error && <div className="error">{error}</div>}
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>الاسم</th>
              <th>البريد</th>
              <th>الدور</th>
              <th>الحالة</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.data?.map((u) => (
              <tr key={u.id}>
                <td>{u.name}</td>
                <td dir="ltr" style={{ textAlign: "end" }}>
                  {u.email}
                </td>
                <td>
                  <select value={u.role} disabled={u.id === me?.id} onChange={(e) => patch.mutate({ id: u.id, body: { role: e.target.value as Role } })}>
                    {Object.entries(ROLE_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{u.is_active ? "نشط" : <span className="muted">موقوف</span>}</td>
                <td className="row">
                  {u.id !== me?.id && (
                    <button onClick={() => patch.mutate({ id: u.id, body: { is_active: !u.is_active } })}>{u.is_active ? "إيقاف" : "تفعيل"}</button>
                  )}
                  <button
                    onClick={() => {
                      const password = window.prompt("كلمة المرور الجديدة (8 أحرف على الأقل)");
                      if (password) patch.mutate({ id: u.id, body: { password } });
                    }}
                  >
                    تغيير كلمة المرور
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
