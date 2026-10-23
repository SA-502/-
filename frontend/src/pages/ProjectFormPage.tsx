import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { Customer, CustomerType, Project, Tariff } from "../api/types";
import { LocationPicker } from "../components/LocationPicker";
import { CUSTOMER_TYPES, MONTHS, num } from "../lib/format";

type ConsumptionMode = "kwh" | "bills" | "average";

// توزيع موسمي تقريبي لفواتير السعودية (ذروة التكييف صيفًا) يُستخدم عند إدخال متوسط فقط
const SEASONAL = [0.6, 0.7, 0.8, 1.1, 1.4, 1.5, 1.5, 1.5, 1.3, 1.0, 0.8, 0.7];

const emptyCustomer = { name: "", phone: "", city: "الرياض", customer_type: "residential" as CustomerType };

export function ProjectFormPage() {
  const { id } = useParams();
  const editing = Boolean(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const existing = useQuery({ queryKey: ["project", id], queryFn: () => api.get<Project>(`/projects/${id}`), enabled: editing });
  const customers = useQuery({ queryKey: ["customers"], queryFn: () => api.get<Customer[]>("/customers?limit=500") });
  const tariffs = useQuery({ queryKey: ["tariffs"], queryFn: () => api.get<Tariff[]>("/tariffs") });

  const [name, setName] = useState("");
  const [customerId, setCustomerId] = useState<number | "new">("new");
  const [newCustomer, setNewCustomer] = useState(emptyCustomer);
  const [location, setLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [city, setCity] = useState("الرياض");
  const [address, setAddress] = useState("");
  const [tariffCode, setTariffCode] = useState<string>("");
  const [mode, setMode] = useState<ConsumptionMode>("bills");
  const [months, setMonths] = useState<number[]>(Array(12).fill(0));
  const [average, setAverage] = useState(1000);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const p = existing.data;
    if (!p) return;
    setName(p.name);
    setCustomerId(p.customer.id);
    setLocation(p.location);
    setCity(p.city ?? "");
    setAddress(p.address ?? "");
    setTariffCode(p.tariff_code);
    if (p.monthly_consumption_kwh) {
      setMode("kwh");
      setMonths(p.monthly_consumption_kwh);
    }
  }, [existing.data]);

  const save = useMutation({
    mutationFn: async () => {
      let cid = customerId;
      if (cid === "new") {
        const created = await api.post<Customer>("/customers", newCustomer);
        cid = created.id;
      }
      const bills = mode === "average" ? SEASONAL.map((f) => (average * f * 12) / SEASONAL.reduce((a, b) => a + b, 0)) : months;
      const body: Record<string, unknown> = {
        name,
        customer_id: cid,
        location,
        city,
        address: address || null,
        tariff_code: tariffCode || undefined,
      };
      if (mode === "kwh") body.monthly_consumption_kwh = months;
      else if (bills.some((b) => b > 0)) body.monthly_bill_sar = bills;
      return editing ? api.patch<Project>(`/projects/${id}`, body) : api.post<Project>("/projects", body);
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["project", String(project.id)] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      navigate(`/projects/${project.id}`);
    },
    onError: (err) => setError((err as Error).message),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!location) {
      setError("حدد موقع المشروع على الخريطة");
      return;
    }
    save.mutate();
  }

  const selectedCustomer = customers.data?.find((c) => c.id === customerId);
  const defaultTariff = customerId === "new" ? newCustomer.customer_type : selectedCustomer?.customer_type;

  return (
    <form onSubmit={submit} className="stack">
      <div className="spread">
        <h1>{editing ? "تعديل بيانات المشروع" : "مشروع جديد"}</h1>
        <button className="primary" disabled={save.isPending}>
          {save.isPending ? "جارٍ الحفظ…" : "حفظ"}
        </button>
      </div>
      {error && <div className="error">{error}</div>}

      <div className="grid cols-2">
        <div className="card stack">
          <h2>العميل والمشروع</h2>
          <label className="field">
            العميل
            <select value={customerId} onChange={(e) => setCustomerId(e.target.value === "new" ? "new" : Number(e.target.value))}>
              <option value="new">+ عميل جديد</option>
              {customers.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} {c.phone ? `— ${c.phone}` : ""}
                </option>
              ))}
            </select>
          </label>
          {customerId === "new" && (
            <div className="form-grid">
              <label className="field">
                اسم العميل
                <input value={newCustomer.name} onChange={(e) => setNewCustomer({ ...newCustomer, name: e.target.value })} required />
              </label>
              <label className="field">
                الجوال
                <input value={newCustomer.phone} onChange={(e) => setNewCustomer({ ...newCustomer, phone: e.target.value })} dir="ltr" />
              </label>
              <label className="field">
                المدينة
                <input value={newCustomer.city} onChange={(e) => setNewCustomer({ ...newCustomer, city: e.target.value })} />
              </label>
              <label className="field">
                نوع العميل
                <select value={newCustomer.customer_type} onChange={(e) => setNewCustomer({ ...newCustomer, customer_type: e.target.value as CustomerType })}>
                  {Object.entries(CUSTOMER_TYPES).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <label className="field">
            اسم المشروع
            <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="مثال: فيلا حي الملقا" />
          </label>
          <div className="form-grid">
            <label className="field">
              المدينة
              <input value={city} onChange={(e) => setCity(e.target.value)} />
            </label>
            <label className="field">
              العنوان
              <input value={address} onChange={(e) => setAddress(e.target.value)} />
            </label>
            <label className="field">
              التعرفة
              <select value={tariffCode} onChange={(e) => setTariffCode(e.target.value)}>
                <option value="">حسب نوع العميل ({defaultTariff ? CUSTOMER_TYPES[defaultTariff] : "—"})</option>
                {tariffs.data?.map((t) => (
                  <option key={t.code} value={t.code}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="row small muted">
            خط العرض <input type="number" step="0.000001" value={location?.lat ?? ""} onChange={(e) => setLocation({ lat: Number(e.target.value), lon: location?.lon ?? 0 })} style={{ width: 130 }} />
            خط الطول <input type="number" step="0.000001" value={location?.lon ?? ""} onChange={(e) => setLocation({ lon: Number(e.target.value), lat: location?.lat ?? 0 })} style={{ width: 130 }} />
          </div>
        </div>

        <div className="card">
          <h2>الموقع</h2>
          {(!editing || existing.data) && <LocationPicker value={location} onChange={setLocation} />}
        </div>
      </div>

      <div className="card stack">
        <div className="spread" style={{ marginBottom: 0 }}>
          <h2 style={{ margin: 0 }}>الاستهلاك الشهري</h2>
          <div className="row">
            <button type="button" className={mode === "bills" ? "active" : ""} onClick={() => setMode("bills")}>
              الفواتير (ريال)
            </button>
            <button type="button" className={mode === "kwh" ? "active" : ""} onClick={() => setMode("kwh")}>
              الاستهلاك (kWh)
            </button>
            <button type="button" className={mode === "average" ? "active" : ""} onClick={() => setMode("average")}>
              متوسط الفاتورة
            </button>
          </div>
        </div>
        {mode === "average" ? (
          <div className="row">
            <label className="field">
              متوسط الفاتورة الشهرية شاملة الضريبة (ريال)
              <input type="number" min={0} value={average} onChange={(e) => setAverage(Number(e.target.value))} />
            </label>
            <span className="muted small">يُوزَّع على الأشهر بنمط موسمي تقريبي (ذروة الصيف)، والأدق إدخال 12 فاتورة.</span>
          </div>
        ) : (
          <div className="months">
            {MONTHS.map((m, i) => (
              <label key={m} className="field">
                {m}
                <input
                  type="number"
                  min={0}
                  value={months[i]}
                  onChange={(e) => setMonths(months.map((v, j) => (j === i ? Number(e.target.value) : v)))}
                />
              </label>
            ))}
          </div>
        )}
        <div className="muted small">
          {mode === "bills" && "تُحوَّل الفواتير إلى kWh حسب شرائح التعرفة وضريبة القيمة المضافة. "}
          المجموع السنوي: <span className="num">{num(mode === "average" ? average * 12 : months.reduce((a, b) => a + b, 0))}</span> {mode === "kwh" ? "kWh" : "ريال"}
        </div>
      </div>
    </form>
  );
}
