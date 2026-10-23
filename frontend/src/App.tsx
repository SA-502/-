import { Suspense, lazy, type ComponentType, type ReactNode } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import type { Role } from "./api/types";
import { useAuth } from "./auth";
import { ROLE_LABELS } from "./lib/format";
import { LoginPage } from "./pages/LoginPage";
import { ProjectPage } from "./pages/ProjectPage";
import { ProjectsPage } from "./pages/ProjectsPage";

// الصفحات الثقيلة (الخرائط والرسوم) تُحمَّل عند الحاجة
const named = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));
const ComponentsPage = named(() => import("./pages/admin/ComponentsPage"), "ComponentsPage");
const PricesPage = named(() => import("./pages/admin/PricesPage"), "PricesPage");
const UsersPage = named(() => import("./pages/admin/UsersPage"), "UsersPage");
const DesignerPage = named(() => import("./pages/designer/DesignerPage"), "DesignerPage");
const ProjectFormPage = named(() => import("./pages/ProjectFormPage"), "ProjectFormPage");
const ResultsPage = named(() => import("./pages/ResultsPage"), "ResultsPage");

function Guard({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user, loading, can } = useAuth();
  const location = useLocation();
  if (loading) return <div className="center muted">جارٍ التحميل…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (roles && !can(...roles)) return <div className="center">ليست لديك صلاحية لهذه الصفحة.</div>;
  return <>{children}</>;
}

function Shell({ children }: { children: ReactNode }) {
  const { user, logout, can } = useAuth();
  const full = useLocation().pathname.startsWith("/designs/");
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">☀ مصمم الأنظمة الشمسية</div>
        <nav>
          <NavLink to="/projects">المشاريع</NavLink>
          {can("admin") && (
            <>
              <NavLink to="/admin/components">المكونات</NavLink>
              <NavLink to="/admin/prices">الأسعار والتعرفة</NavLink>
              <NavLink to="/admin/users">المستخدمون</NavLink>
            </>
          )}
        </nav>
        <div className="user">
          {user?.name} <span className="badge">{user && ROLE_LABELS[user.role]}</span>
          <button className="link" onClick={logout}>
            خروج
          </button>
        </div>
      </header>
      <main className={full ? "full" : undefined}>
        <Suspense fallback={<div className="center muted">جارٍ التحميل…</div>}>{children}</Suspense>
      </main>
    </div>
  );
}

const page = (node: ReactNode, roles?: Role[]) => (
  <Guard roles={roles}>
    <Shell>{node}</Shell>
  </Guard>
);

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/projects" element={page(<ProjectsPage />)} />
      <Route path="/projects/new" element={page(<ProjectFormPage />)} />
      <Route path="/projects/:id" element={page(<ProjectPage />)} />
      <Route path="/projects/:id/edit" element={page(<ProjectFormPage />)} />
      <Route path="/designs/:id" element={page(<DesignerPage />)} />
      <Route path="/simulations/:id" element={page(<ResultsPage />)} />
      <Route path="/admin/components" element={page(<ComponentsPage />, ["admin"])} />
      <Route path="/admin/prices" element={page(<PricesPage />, ["admin"])} />
      <Route path="/admin/users" element={page(<UsersPage />, ["admin"])} />
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}
