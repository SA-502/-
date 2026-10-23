import type { ComponentKind, CustomerType, ObstructionKind, PriceUnit, ProjectStatus, Role } from "../api/types";

const nf = (digits: number) => new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export function num(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return nf(digits).format(value);
}

export function sar(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "—" : `${num(value, digits)} ر.س`;
}

export function date(value: string): string {
  return new Date(value).toLocaleDateString("ar-SA-u-ca-gregory-nu-latn", { year: "numeric", month: "short", day: "numeric" });
}

export const MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  new: "جديد",
  designing: "قيد التصميم",
  simulated: "تمت المحاكاة",
  quoted: "صدر العرض",
  won: "تم التعاقد",
  lost: "لم يتم",
};

export const CUSTOMER_TYPES: Record<CustomerType, string> = {
  residential: "سكني",
  commercial: "تجاري",
  industrial: "صناعي",
  agricultural: "زراعي",
  governmental: "حكومي",
};

export const ROLE_LABELS: Record<Role, string> = { engineer: "مهندس", sales: "مبيعات", admin: "مدير" };

export const COMPONENT_KINDS: Record<ComponentKind, string> = { module: "ألواح", inverter: "انفرترات", racking: "هياكل" };

export const PRICE_UNITS: Record<PriceUnit, string> = {
  per_unit: "للوحدة",
  per_watt: "للواط",
  per_kwp: "لكل kWp",
  per_module: "لكل لوح",
  fixed: "مبلغ مقطوع",
};

export const OBSTRUCTION_KINDS: Record<ObstructionKind, string> = {
  keepout: "منطقة ممنوعة",
  tank: "خزان",
  wall: "جدار",
  tree: "شجرة",
  other: "أخرى",
};

/** اسم الاتجاه بالعربية من السمت بالدرجات. */
export function compass(azimuth: number): string {
  const names = ["شمال", "شمال شرق", "شرق", "جنوب شرق", "جنوب", "جنوب غرب", "غرب", "شمال غرب"];
  return names[Math.round((((azimuth % 360) + 360) % 360) / 45) % 8];
}
