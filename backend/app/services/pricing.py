"""بناء عرض السعر من المكونات وبنود قائمة الأسعار."""

from dataclasses import dataclass, field

# وحدات التسعير المدعومة
UNITS = ("per_unit", "per_watt", "per_kwp", "per_module", "fixed")


@dataclass
class QuoteLine:
    description: str
    quantity: float
    unit: str
    unit_price_sar: float

    @property
    def total_sar(self) -> float:
        return self.quantity * self.unit_price_sar


@dataclass
class Quote:
    lines: list[QuoteLine] = field(default_factory=list)
    discount_pct: float = 0.0
    vat: float = 0.15

    @property
    def subtotal_sar(self) -> float:
        return sum(line.total_sar for line in self.lines)

    @property
    def discount_sar(self) -> float:
        return self.subtotal_sar * self.discount_pct / 100

    @property
    def net_sar(self) -> float:
        return self.subtotal_sar - self.discount_sar

    @property
    def vat_sar(self) -> float:
        return self.net_sar * self.vat

    @property
    def total_sar(self) -> float:
        return self.net_sar + self.vat_sar

    def to_dict(self) -> dict:
        return {
            "lines": [
                {
                    "description": line.description,
                    "quantity": round(line.quantity, 3),
                    "unit": line.unit,
                    "unit_price_sar": round(line.unit_price_sar, 2),
                    "total_sar": round(line.total_sar, 2),
                }
                for line in self.lines
            ],
            "subtotal_sar": round(self.subtotal_sar, 2),
            "discount_pct": self.discount_pct,
            "discount_sar": round(self.discount_sar, 2),
            "net_sar": round(self.net_sar, 2),
            "vat": self.vat,
            "vat_sar": round(self.vat_sar, 2),
            "total_sar": round(self.total_sar, 2),
        }


def quantity_for(unit: str, *, units: float, module_count: int, dc_kwp: float) -> float:
    """الكمية التي يُضرب فيها سعر البند حسب وحدته."""
    if unit == "per_unit":
        return units
    if unit == "per_watt":
        return dc_kwp * 1000
    if unit == "per_kwp":
        return dc_kwp
    if unit == "per_module":
        return module_count
    if unit == "fixed":
        return 1
    raise ValueError(f"وحدة تسعير غير معروفة: {unit}")


def module_line(name: str, price: float, unit: str, module_count: int, module_power_w: float) -> QuoteLine:
    """سطر الألواح: الكمية بعدد الألواح، والسعر يُحوَّل لسعر اللوح إذا كان بالواط."""
    unit_price = price * module_power_w if unit == "per_watt" else price
    return QuoteLine(name, module_count, "per_unit", unit_price)
