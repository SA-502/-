import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
import numpy_financial as npf

# --- 1. إعدادات الصفحة والتصميم ---
st.set_page_config(page_title="Solar KSA | المنصة السعودية للطاقة", layout="wide", page_icon="☀️")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Tajawal', sans-serif; }
    div[data-testid="stMetric"] {
        background-color: #fcfcfc; border: 1px solid #ddd; padding: 10px; border-radius: 10px;
        box-shadow: 1px 1px 3px rgba(0,0,0,0.05); text-align: center;
    }
    div[data-testid="stMetric"]:hover { border-color: #2e7d32; }
    .stButton button { background-color: #2e7d32; color: white; font-weight: bold; }
    .stButton button:hover { background-color: #1b5e20; }
</style>
""", unsafe_allow_html=True)

# --- النصوص والبيانات السعودية ---
translations = {
    "English": {
        "title": "☀️ Saudi Solar Feasibility Platform",
        "sidebar_title": "Project Inputs",
        "bill": "Monthly Bill (SAR)",
        "area": "Roof Area (m²)",
        "cost_per_kw": "System Cost/kW (SAR)",
        "city": "City (Select Region)",
        "price_kwh": "Tariff Rate (SAR/kWh)",
        "calculate": "Analyze Project",
        "tab1": "📊 Dashboard",
        "tab2": "💰 Financials",
        "tab3": "📑 Official Report",
        "results": "Project Summary",
        "system_size": "System Capacity",
        "panels": "Panels Count",
        "cost": "Total Investment",
        "savings_1st": "1st Year Savings",
        "roi": "ROI (25 Years)",
        "payback": "Payback Period",
        "npv": "Net Present Value",
        "co2": "CO2 Avoided",
        "chart_title": "Monthly Production vs Consumption",
        "chart_cashflow": "Cash Flow Analysis (25 Years)",
        "download_pdf": "Download Proposal (PDF)",
        "currency": "SAR",
        "rec_title": "Recommendations"
    },
    "العربية": {
        "title": "☀️ المنصة السعودية لجدوى الطاقة الشمسية",
        "sidebar_title": "بيانات المشروع",
        "bill": "متوسط الفاتورة الشهرية (ريال)",
        "area": "مساحة السطح المتاحة (م²)",
        "cost_per_kw": "تكلفة النظام للكيلوواط (ريال)",
        "city": "المدينة / المنطقة",
        "price_kwh": "تعرفة الكهرباء (ريال/ك.و.س)",
        "calculate": "بدء التحليل",
        "tab1": "📊 لوحة المعلومات",
        "tab2": "💰 التحليل المالي",
        "tab3": "📑 التقرير الرسمي",
        "results": "ملخص المشروع",
        "system_size": "حجم المحطة المقترح",
        "panels": "عدد الألواح",
        "cost": "إجمالي الاستثمار",
        "savings_1st": "توفير السنة الأولى",
        "roi": "العائد الاستثماري",
        "payback": "فترة الاسترداد",
        "npv": "صافي القيمة الحالية",
        "co2": "الخفض الكربوني",
        "chart_title": "مقارنة الإنتاج والاستهلاك المتوقع",
        "chart_cashflow": "تحليل التدفق النقدي (25 سنة)",
        "download_pdf": "تحميل العرض الفني (PDF)",
        "currency": "ر.س",
        "rec_title": "توصيات وملاحظات"
    }
}

# --- القائمة الجانبية ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Flag_of_Saudi_Arabia.svg/320px-Flag_of_Saudi_Arabia.svg.png", width=60)
    st.markdown("### Saudi Solar Tool")
    
    language = st.radio("", ["العربية", "English"], horizontal=True)
    t = translations[language]
    curr = t["currency"]
    
    st.divider()
    st.subheader(t["sidebar_title"])
    
    monthly_bill = st.number_input(t['bill'], value=1500.0, step=100.0)
    
    # قائمة المدن السعودية
    saudi_cities = {
        "الرياض / Riyadh (5.8h)": 5.8,
        "جدة / Jeddah (6.0h)": 6.0,
        "الدمام / Dammam (5.6h)": 5.6,
        "مكة المكرمة / Mecca (6.2h)": 6.2,
        "المدينة المنورة / Medina (6.3h)": 6.3,
        "أبها / Abha (5.9h)": 5.9,
        "تبوك / Tabuk (6.1h)": 6.1,
        "حائل / Hail (6.0h)": 6.0,
        "جازان / Jizan (5.9h)": 5.9,
        "نجران / Najran (6.4h)": 6.4,
        "القصيم / Qassim (5.8h)": 5.8
    }
    
    location_key = st.selectbox(t["city"], list(saudi_cities.keys()))
    sun_hours = saudi_cities[location_key]
    
    col1, col2 = st.columns(2)
    with col1:
        roof_area = st.number_input(t['area'], value=300.0)
    with col2:
        price_per_kwh = st.number_input(t['price_kwh'], value=0.18, format="%.3f")
        
    cost_per_kw = st.number_input(t['cost_per_kw'], value=3200.0, help="متوسط السوق بين 3000 - 3800 ريال")
    
    with st.expander("إعدادات متقدمة / Advanced"):
        inflation_rate = st.slider("التضخم / Inflation", 0.0, 5.0, 2.5) / 100
        degradation_rate = 0.005 # ثابت 0.5%
        
    run_calc = st.button(t["calculate"], use_container_width=True)

# --- المحرك الرئيسي ---
if run_calc:
    # الحسابات
    monthly_consumption_kwh = monthly_bill / price_per_kwh if price_per_kwh > 0 else 0
    daily_consumption = monthly_consumption_kwh / 30
    required_system_kw = (daily_consumption / sun_hours) * 1.15
    max_system_by_area = roof_area / 7 
    final_system_kw = min(required_system_kw, max_system_by_area)
    num_panels = int((final_system_kw * 1000) / 450)
    if num_panels < 1: num_panels = 1
    actual_system_kw = (num_panels * 450) / 1000
    total_investment = actual_system_kw * cost_per_kw
    
    years_range = range(1, 26)
    cash_flow = []
    cumulative_cash_flow = []
    cumulative_savings_val = -total_investment
    current_electricity_price = price_per_kwh
    yearly_production_kwh = actual_system_kw * sun_hours * 365 * 0.9 
    
    for year in years_range:
        savings = yearly_production_kwh * current_electricity_price
        cash_flow.append(savings)
        cumulative_savings_val += savings
        cumulative_cash_flow.append(cumulative_savings_val)
        current_electricity_price *= (1 + inflation_rate)
        yearly_production_kwh *= (1 - degradation_rate)
        
    first_year_savings = cash_flow[0]
    total_savings_25y = sum(cash_flow)
    
    payback_years = 0
    for i, val in enumerate(cumulative_cash_flow):
        if val >= 0:
            payback_years = i + 1 - (val - 0) / (val - cumulative_cash_flow[i-1])
            break
    if payback_years == 0 and cumulative_cash_flow[-1] < 0: payback_years = 25
    
    roi_percent = ((total_savings_25y - total_investment) / total_investment) * 100
    npv_value = -total_investment
    for i, flow in enumerate(cash_flow):
        npv_value += flow / ((1.05) ** (i + 1))
    co2_tons = (actual_system_kw * sun_hours * 365 * 25 * 0.5) / 1000

    # --- العرض ---
    st.title(t["title"])
    tab1, tab2, tab3 = st.tabs([t["tab1"], t["tab2"], t["tab3"]])
    
    with tab1:
        st.markdown(f"### {t['results']}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t["system_size"], f"{actual_system_kw:.2f} kW", "Capacity")
        c2.metric("عدد الألواح", f"{num_panels}", "450W")
        c3.metric(t["cost"], f"{total_investment:,.0f} {curr}", "CAPEX")
        c4.metric(t["savings_1st"], f"{first_year_savings:,.0f} {curr}", "Year 1")
        
        st.markdown("---")
        # الرسم البياني
        mon_prod = actual_system_kw * sun_hours * 30 * 0.9
prod_curve = [mon_prod * (1 + (i-6)*0.1) if i<6 else mon_prod * (1 - (i-6)*0.1) for i in range(12)]

