import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/projects" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? "/projects", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card login stack" onSubmit={submit}>
      <h1>☀ مصمم الأنظمة الشمسية</h1>
      <p className="muted">سجّل الدخول بحساب الشركة.</p>
      <label className="field">
        البريد الإلكتروني
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus dir="ltr" />
      </label>
      <label className="field">
        كلمة المرور
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required dir="ltr" />
      </label>
      {error && <div className="error">{error}</div>}
      <button className="primary" disabled={busy}>
        {busy ? "جارٍ الدخول…" : "دخول"}
      </button>
    </form>
  );
}
