import { describe, expect, it } from "vitest";

import {
  areaM2,
  autoRowSpacing,
  canPlaceModule,
  footprint,
  keepoutsToLocal,
  layoutModules,
  sunPosition,
  toLngLat,
  toLocal,
  type LayoutParams,
  type LngLat,
  type ModuleSpec,
  type Origin,
} from "./layout";

const origin: Origin = { lat: 24.7136, lon: 46.6753 };
const spec: ModuleSpec = { length_m: 2.278, width_m: 1.134, power_w: 550 };

function square(x0: number, y0: number, size: number): LngLat[] {
  return [
    [x0, y0],
    [x0 + size, y0],
    [x0 + size, y0 + size],
    [x0, y0 + size],
  ].map((p) => toLngLat(p as [number, number], origin));
}

const flush: LayoutParams = {
  orientation: "portrait",
  mounting: "flush",
  tilt_deg: 0,
  azimuth_deg: 180,
  row_spacing_m: 0,
  module_gap_m: 0.02,
  setback_m: 1,
  obstruction_clearance_m: 0.5,
  roof_height_m: 6,
};

describe("projection", () => {
  it("round-trips local metres", () => {
    const [lon, lat] = toLngLat([35.5, -12.25], origin);
    const [x, y] = toLocal([lon, lat], origin);
    expect(x).toBeCloseTo(35.5, 6);
    expect(y).toBeCloseTo(-12.25, 6);
  });

  it("measures a 20 m square as ~400 m²", () => {
    expect(areaM2(square(0, 0, 20))).toBeGreaterThan(398);
    expect(areaM2(square(0, 0, 20))).toBeLessThan(402);
  });
});

describe("footprint", () => {
  it("projects the tilted slope length", () => {
    const fp = footprint(spec, "portrait", 20);
    expect(fp.along).toBeCloseTo(1.134);
    expect(fp.depth).toBeCloseTo(2.278 * Math.cos((20 * Math.PI) / 180));
    expect(fp.height).toBeCloseTo(2.278 * Math.sin((20 * Math.PI) / 180));
    expect(footprint(spec, "landscape", 0).along).toBeCloseTo(2.278);
  });
});

describe("sun and row spacing", () => {
  it("matches hand-calculated winter solstice sun at 09:00 in Riyadh", () => {
    const sun = sunPosition(24.7136, -23.44, 9);
    expect(sun.elevation).toBeCloseTo(25.0, 0);
    expect(sun.azimuth).toBeCloseTo(134.3, 0);
    const noon = sunPosition(24.7136, -23.44, 12);
    expect(noon.elevation).toBeCloseTo(90 - 24.7136 - 23.44, 1);
    expect(noon.azimuth).toBeCloseTo(180, 3);
  });

  it("gives ~1.16 m for 20° portrait rows facing south", () => {
    expect(autoRowSpacing(spec, "portrait", 20, 180, 24.7136)).toBeCloseTo(1.16, 1);
    expect(autoRowSpacing(spec, "portrait", 0, 180, 24.7136)).toBe(0);
  });
});

describe("layoutModules", () => {
  it("fills an 18×18 m usable square with a full grid", () => {
    const { modules } = layoutModules(square(0, 0, 20), [], spec, flush, origin);
    // 15 عمودًا × 7 صفوف
    expect(modules.length).toBeGreaterThanOrEqual(100);
    expect(modules.length).toBeLessThanOrEqual(105);
    for (const m of modules) {
      expect(m.x).toBeGreaterThan(1);
      expect(m.x).toBeLessThan(19);
      expect(m.y).toBeGreaterThan(1);
      expect(m.y).toBeLessThan(19);
      expect(m.rotation_deg).toBe(180);
      expect(m.z).toBe(6);
    }
  });

  it("uses fewer modules with tilted rows and spacing", () => {
    const tilted = layoutModules(square(0, 0, 20), [], spec, { ...flush, mounting: "tilted_rows", tilt_deg: 20, row_spacing_m: 1.2 }, origin);
    const flat = layoutModules(square(0, 0, 20), [], spec, flush, origin);
    expect(tilted.modules.length).toBeLessThan(flat.modules.length);
    expect(tilted.rowPitch).toBeCloseTo(2.278 * Math.cos((20 * Math.PI) / 180) + 1.2);
    expect(tilted.modules[0].z).toBeGreaterThan(6);
  });

  it("keeps modules out of keep-out zones", () => {
    const keepout = square(8, 8, 4);
    const { modules } = layoutModules(square(0, 0, 20), [keepout], spec, flush, origin);
    const full = layoutModules(square(0, 0, 20), [], spec, flush, origin).modules;
    expect(modules.length).toBeLessThan(full.length);
    // لا يوجد مركز لوح داخل المنطقة الممنوعة مع الهامش
    for (const m of modules) {
      const inside = m.x > 7.5 && m.x < 12.5 && m.y > 7.5 && m.y < 12.5;
      expect(inside).toBe(false);
    }
  });

  it("returns nothing when setback eats the roof", () => {
    const { modules, usable } = layoutModules(square(0, 0, 3), [], spec, { ...flush, setback_m: 2 }, origin);
    expect(modules).toHaveLength(0);
    expect(usable).toBeNull();
  });

  it("follows a rotated azimuth", () => {
    const { modules } = layoutModules(square(0, 0, 20), [], spec, { ...flush, azimuth_deg: 225 }, origin);
    expect(modules.length).toBeGreaterThan(60);
    expect(modules.every((m) => m.rotation_deg === 225)).toBe(true);
  });
});

describe("canPlaceModule", () => {
  it("rejects overlaps and accepts free spots", () => {
    const roof = square(0, 0, 20);
    const result = layoutModules(roof, [], spec, flush, origin);
    const first = result.modules[0];
    const ko = keepoutsToLocal([], 0.5, origin);
    expect(canPlaceModule([first.x, first.y], result.modules, spec, flush, result.usable, ko, origin)).toBe(false);
    const fewer = result.modules.slice(1);
    expect(canPlaceModule([first.x, first.y], fewer, spec, flush, result.usable, ko, origin)).toBe(true);
    expect(canPlaceModule([50, 50], fewer, spec, flush, result.usable, ko, origin)).toBe(false);
  });
});
