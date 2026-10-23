import type { StyleSpecification } from "maplibre-gl";

/** صور أقمار صناعية من Esri World Imagery (مجانية بدون مفتاح، مع ذكر المصدر). */
export const satelliteStyle: StyleSpecification = {
  version: 8,
  sources: {
    satellite: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
    },
  },
  layers: [{ id: "satellite", type: "raster", source: "satellite" }],
};

export const RIYADH = { lat: 24.7136, lon: 46.6753 };
