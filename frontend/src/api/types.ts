import type { LngLat, Mounting, Orientation, PlacedModule } from "../geometry/layout";

export type Role = "engineer" | "sales" | "admin";
export type CustomerType = "residential" | "commercial" | "industrial" | "agricultural" | "governmental";
export type ProjectStatus = "new" | "designing" | "simulated" | "quoted" | "won" | "lost";
export type ComponentKind = "module" | "inverter" | "racking";
export type PriceUnit = "per_unit" | "per_watt" | "per_kwp" | "per_module" | "fixed";
export type ObstructionKind = "keepout" | "tank" | "wall" | "tree" | "other";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  is_active: boolean;
}

export interface Customer {
  id: number;
  name: string;
  phone: string | null;
  email: string | null;
  city: string | null;
  customer_type: CustomerType;
  notes: string | null;
  created_at: string;
}

export interface DesignSummary {
  id: number;
  version_no: number;
  name: string;
  created_at: string;
}

export interface Project {
  id: number;
  name: string;
  customer: Customer;
  location: { lat: number; lon: number };
  address: string | null;
  city: string | null;
  status: ProjectStatus;
  tariff_code: string;
  monthly_consumption_kwh: number[] | null;
  designer: User | null;
  designs: DesignSummary[];
  created_at: string;
  updated_at: string | null;
}

export interface Component {
  id: number;
  kind: ComponentKind;
  manufacturer: string;
  model: string;
  specs: Record<string, number | string>;
  price_sar: number;
  price_unit: PriceUnit;
  is_active: boolean;
}

export interface PriceItem {
  id: number;
  name: string;
  unit: PriceUnit;
  unit_price_sar: number;
  sort_order: number;
  is_active: boolean;
}

export interface Tariff {
  code: string;
  name: string;
  tiers: { up_to_kwh: number | null; rate_sar: number }[];
  vat: number;
  export_rate_sar: number;
}

export interface GeoPolygon {
  type: "Polygon";
  coordinates: LngLat[][];
}

export interface ArrayDesign {
  id?: number | null;
  module_id: number;
  orientation: Orientation;
  mounting: Mounting;
  tilt_deg: number;
  azimuth_deg: number;
  row_spacing_m: number;
  module_gap_m: number;
  modules: PlacedModule[];
}

export interface RoofAreaDesign {
  id?: number | null;
  name: string;
  kind: "roof" | "ground";
  geometry: GeoPolygon;
  height_m: number;
  pitch_deg: number;
  azimuth_deg: number;
  setback_m: number;
  arrays: ArrayDesign[];
}

export interface ObstructionDesign {
  id?: number | null;
  kind: ObstructionKind;
  geometry: GeoPolygon;
  height_m: number;
}

export interface DesignContent {
  name: string;
  inverter_id: number | null;
  inverter_count: number;
  racking_id: number | null;
  notes: string | null;
  roof_areas: RoofAreaDesign[];
  obstructions: ObstructionDesign[];
}

export interface Design extends DesignContent {
  id: number;
  project_id: number;
  version_no: number;
  created_at: string;
  module_count: number;
  dc_kwp: number;
  ac_kw: number;
}

export interface LossRow {
  key: string;
  label: string;
  energy_kwh: number;
  loss_pct: number;
}

export interface SimulationResults {
  dc_kwp: number;
  ac_kw: number;
  annual_ghi_kwh_m2: number;
  annual_poa_kwh_m2: number;
  annual_energy_kwh: number;
  specific_yield_kwh_kwp: number;
  performance_ratio: number;
  monthly_energy_kwh: number[];
  monthly_poa_kwh_m2: number[];
  losses: LossRow[];
  arrays: { name: string; module_count: number; dc_kwp: number; tilt_deg: number; azimuth_deg: number; annual_poa_kwh_m2: number; dc_energy_kwh: number }[];
}

export interface Simulation {
  id: number;
  design_id: number;
  weather_meta: { source: string; latitude: number; longitude: number; elevation: number; radiation_db?: string };
  inputs: { losses: Losses; ac_kw_assumed: boolean; inverter_efficiency: number };
  results: SimulationResults;
  created_at: string;
}

export interface Losses {
  albedo: number;
  soiling_monthly_pct: number[];
  mismatch_pct: number;
  dc_wiring_pct: number;
  lid_pct: number;
  ac_wiring_pct: number;
  transformer_pct: number;
}

export interface FinanceParams {
  discount_pct: number;
  extra_lines: { description: string; quantity: number; unit_price_sar: number }[];
  override_total_sar: number | null;
  years: number;
  discount_rate_pct: number;
  degradation_pct: number;
  om_pct: number;
  tariff_escalation_pct: number;
  inverter_replacement_year: number | null;
  inverter_replacement_cost_sar: number;
}

export interface QuoteLine {
  description: string;
  quantity: number;
  unit: PriceUnit;
  unit_label: string;
  unit_price_sar: number;
  total_sar: number;
}

export interface Quote {
  lines: QuoteLine[];
  subtotal_sar: number;
  discount_pct: number;
  discount_sar: number;
  net_sar: number;
  vat: number;
  vat_sar: number;
  total_sar: number;
  capex_sar: number;
}

export interface MonthBalance {
  consumption_kwh: number;
  production_kwh: number;
  self_consumed_kwh: number;
  imported_kwh: number;
  exported_kwh: number;
  bill_before_sar: number;
  bill_after_sar: number;
  export_credit_sar: number;
  credit_applied_sar: number;
  payable_sar: number;
  savings_sar: number;
}

export interface Financial {
  capex_sar: number;
  rows: { year: number; production_kwh: number; savings_sar: number; om_sar: number; other_costs_sar: number; net_cash_flow_sar: number; cumulative_sar: number }[];
  npv_sar: number;
  irr: number | null;
  payback_years: number | null;
  discounted_payback_years: number | null;
  lcoe_sar_per_kwh: number;
  roi_pct: number;
  first_year_savings_sar: number;
  first_year_bill_before_sar: number;
  first_year_bill_after_sar: number;
  lifetime_savings_sar: number;
  first_year_months: MonthBalance[];
}

export interface Report {
  id: number;
  simulation_id: number;
  language: "ar" | "en";
  quote: Quote;
  financial: Financial;
  created_at: string;
}
