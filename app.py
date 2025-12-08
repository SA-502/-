import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
import numpy_financial as npf

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Advanced Solar KSA", layout="wide", page_icon="☀️")

# --- النصوص والترجمة ---
translations = {
    "English": {
        "title": "☀️ Saudi Solar Feasibility Tool (Advanced)",
        "sidebar_title": "Project Inputs",
        "bill": "Monthly Bill (SAR)",
        "area": "Roof Area (m²)",
        "cost_per_kw": "System Cost/kW (SAR)",
        "city": "City (Saudi Arabia)",
        "price_kwh": "Tariff Rate (SAR/kWh)",
        "inflation": "Electricity Inflation (%)",
        "degradation": "Panel Degradation (%)",
        "calculate": "Calculate Results",
        "results": "Feasibility Analysis",
        "system_size": "Required System Size",
        "panels": "Number of Panels",
        "cost": "Total Investment",
        "savings": "Annual Savings",
        "roi": "ROI (25 Years)",
        "payback": "Payback Period",
        "npv": "Net Present Value (NPV)",
        "co2": "CO2 Saved (25 Years)",
        "chart_title": "Production vs Consumption",
        "chart_cashflow": "Cumulative Cash Flow (25 Years)",
        "download_pdf": "Download Professional PDF",
        "currency": "SAR",
        "panels_count": "Panels",
        "rec_title": "Technical Recommendations"
    },
    "العربية": {
        "title": "☀️ أداة جدوى الطاقة الشمسية المتقدمة",
        "sidebar_title": "مدخلات المشروع",
        "bill": "فاتورة الكهرباء الشهرية (ريال)",
        "area": "مساحة السطح المتاحة (متر مربع)",
        "cost_per_kw": "تكلفة النظام للكيلوواط (ريال)",
        "city": "المدينة / المنطقة",
        "price_kwh": "تعرفة الكهرباء (ريال/ك.و.س)",
        "inflation": "نسبة التضخم السنوي للكهرباء (%)",
        "degradation": "نسبة تناقص كفاءة الألواح (%)",
        "calculate": "احسب النتائج",
        "results": "تحليل الجدوى الاقتصادية",
        "system_size": "حجم المحطة المطلوب",
        "panels": "عدد الألواح (450 واط)",
        "cost": "إجمالي الاستثمار المتوقع",
        "savings": "التوفير السنوي",
        "roi": "العائد على الاستثمار (25 سنة)",
        "payback": "فترة استرداد رأس المال",
        "npv": "صافي القيمة الحالية (NPV)",
        "co2": "توفير CO2 (25 سنة)",
        "chart_title": "مقارنة الإنتاج والاستهلاك المتوقع",
        "chart_cashflow": "تحليل التدفق النقدي التراكمي (25 سنة)",
        "download_pdf": "تحميل التقرير الفني (PDF)",
        "currency": "ر.س",
        "panels_count": "لوح",
        "rec_title": "توصيات وملاحظات فنية"
    }
}

# --- القائمة الجانبية ---
with st.sidebar:
    language = st.radio("Language / اللغة", ["العربية", "English"])
    t = translations[language]
    curr = t["currency"]
    
    st.header(t["sidebar_title"])
    
    # المدخلات الأساسية
    monthly_bill = st.number_input(t["bill"], min_value=0.0, value=1500.0, step=100.0)
    
    # قائمة مدن السعودية
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
        "القصيم / Qassim (5.8h)": 5.8,
        "الطائف / Taif (5.9h)": 5.9
    }
    
    location_key = st.selectbox(t["city"], list(saudi_cities.keys()))
    sun_hours = saudi_cities[location_key]
    
    roof_area = st.number_input(t["area"], min_value=10.0, value=300.0)
    price_per_kwh = st.number_input(t["price_kwh"], min_value=0.01, value=0.18, format="%.3f")
    cost_per_kw = st.number_input(t["cost_per_kw"], min_value=1000.0, value=3200.0)
    
    # --- خانات التضخم والتدهور (رجعت لك!) ---
    st.markdown("---")
    with st.expander("إعدادات متقدمة / Advanced Settings", expanded=True):
        inflation_rate = st.slider(t["inflation"], 0.0, 10.0, 3.0, 0.1) / 100
        degradation_rate = st.slider(t["degradation"], 0.0, 2.0, 0.5, 0.1) / 100
        discount_rate = 0.05
    
    # زر الحساب الكلاسيكي
    run_calc = st.button(t["calculate"], type="primary")

# --- الصفحة الرئيسية ---
st.title(t["title"])

if run_calc:
    # --- العمليات الحسابية ---
    monthly_consumption_kwh = monthly_bill / price_per_kwh if price_per_kwh > 0 else 0
    daily_consumption = monthly_consumption_kwh / 30
    required_system_kw = (daily_consumption / sun_hours) * 1.15
    max_system_by_area = roof_area / 7
    final_system_kw = min(required_system_kw, max_system_by_area)
    
    # ألواح 450 واط
    panel_wattage = 450
    num_panels = int((final_system_kw * 1000) / panel_wattage)
    if num_panels < 1: num_panels = 1
    actual_system_kw = (num_panels * panel_wattage) / 1000
    
    total_investment = actual_system_kw * cost_per_kw
    
    # محاكاة مالية متقدمة (تستخدم مدخلات التضخم من القائمة الجانبية)
    years_range = range(1, 26)
    cash_flow = []
    cumulative_cash_flow = []
    cumulative_val = -total_investment
    
    current_price = price_per_kwh
    yearly_prod = actual_system_kw * sun_hours * 365 * 0.9
    
    for year in years_range:
        savings = yearly_prod * current_price
        cash_flow.append(savings)
        cumulative_val += savings
        cumulative_cash_flow.append(cumulative_val)
        
        # تطبيق التضخم والتدهور الذي اخترته
        current_price *= (1 + inflation_rate)
        yearly_prod *= (1 - degradation_rate)
        
    annual_savings = cash_flow[0]
    total_savings_25y = sum(cash_flow)
    
    payback_years = 0
    for i, val in enumerate(cumulative_cash_flow):
        if val >= 0:
            payback_years = i + 1 - (val - 0) / (val - cumulative_cash_flow[i-1])
            break
    if payback_years == 0 and cumulative_cash_flow[-1] < 0: payback_years = 25
            
    roi_percent = ((total_savings_25y - total_investment) / total_investment) * 100
    
    # حساب NPV باستخدام numpy_financial
    npv_value = -total_investment
    for i, flow in enumerate(cash_flow):
        npv_value += flow / ((1 + discount_rate) ** (i + 1))
        
    co2_saved_tons = (actual_system_kw * sun_hours * 365 * 25 * 0.5) / 1000

    # --- عرض النتائج (الواجهة البسيطة) ---
    st.divider()
    st.subheader(t["results"])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t["system_size"], f"{actual_system_kw:.2f} kW")
    col2.metric(t["panels"], f"{num_panels} {t['panels_count']}")
    col3.metric(t["cost"], f"{total_investment:,.0f} {curr}")
    col4.metric(t["savings"], f"{annual_savings:,.0f} {curr}")
    
    col5, col6, col7 = st.columns(3)
    col5.metric(t["roi"], f"{roi_percent:.0f}%")
    col6.metric(t["payback"], f"{payback_years:.1f} Years")
    col7.metric(t["npv"], f"{npv_value:,.0f} {curr}")
    
    st.divider()

    # --- الرسومات البيانية ---
    mon_prod = actual_system_kw * sun_hours * 30 * 0.9
    prod_curve = []
    for i in range(12):
        if i < 6: val = mon_prod * (1 + (i-6)*0.1)
        else: val = mon_prod * (1 - (i-6)*0.1)
        prod_curve.append(val)
        
    cons_curve = [monthly_consumption_kwh] * 12
    months_lbl = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    if language == "العربية":
         months_lbl = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=months_lbl, y=prod_curve, name='Production / الإنتاج', marker_color='#FBC02D'))
    fig1.add_trace(go.Scatter(x=months_lbl, y=cons_curve, name='Consumption / الاستهلاك', line=dict(color='#1565C0', width=3)))
    fig1.update_layout(title=t["chart_title"], yaxis_title="kWh", height=400)
    st.plotly_chart(fig1, use_container_width=True)
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=list(years_range), y=cumulative_cash_flow, fill='tozeroy', name='Cumulative Savings', line=dict(color='#2E7D32')))
    fig2.update_layout(title=t["chart_cashflow"], xaxis_title="Year", yaxis_title=curr, height=400)
    fig2.add_hline(y=0, line_dash="dash", line_color="red")
    st.plotly_chart(fig2, use_container_width=True)

    # --- ملف PDF (بدون شعار، وبدون علم، مع جداول وتوصيات) ---
    def create_saudi_pdf():
        pdf = FPDF()
        pdf.add_page()
        
        font_path = 'Amiri-Regular.ttf'
        has_arabic_font = os.path.exists(font_path)
        
        if has_arabic_font:
            pdf.add_font('Amiri', '', font_path, uni=True)
            pdf.set_font('Amiri', '', 12)
        else:
            pdf.set_font("Arial", size=12)

        def txt(text):
            if language == "العربية" and has_arabic_font:
                return get_display(arabic_reshaper.reshape(text))
            return text

        # الترويسة
        pdf.set_fill_color(245, 245, 245)
        pdf.rect(0, 0, 210, 30, 'F')
        pdf.set_font_size(20)
        pdf.cell(190, 15, txt=txt(t["title"]), ln=True, align='C')
        pdf.set_font_size(10)
        pdf.cell(190, 5, txt=txt("تقرير فني ومالي - Technical & Financial Proposal"), ln=True, align='C')
        pdf.ln(15)
        
        def table_row(label, value):
            pdf.set_font('Amiri', '', 12)
            pdf.cell(100, 8, txt=txt(label), border=1, align='R' if language=="العربية" else 'L')
            pdf.set_font('Amiri', '', 12)
            pdf.cell(90, 8, txt=txt(str(value)), border=1, ln=True, align='C')

        # القسم 1
        pdf.set_fill_color(46, 125, 50) 
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt("1. بيانات المشروع"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        pdf.set_text_color(0, 0, 0)
        
        table_row(t["city"], location_key.split('/')[0])
        table_row(t["bill"], f"{monthly_bill} {curr}")
        table_row(t["area"], f"{roof_area} m2")
        # إضافة التضخم للتقرير ليكون دقيقاً
        table_row(t["inflation"], f"{inflation_rate*100} %")
        pdf.ln(5)

        # القسم 2
        pdf.set_fill_color(46, 125, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, txt=txt("2. المواصفات الفنية"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        pdf.set_text_color(0, 0, 0)
        
        table_row(t["system_size"], f"{actual_system_kw:.2f} kW")
        table_row(t["panels"], f"{num_panels}")
        table_row("إنتاج السنة الأولى", f"{int(yearly_prod):,} kWh")
        pdf.ln(5)
        
        # القسم 3
        pdf.set_fill_color(46, 125, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, txt=txt("3. المؤشرات الاقتصادية"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        pdf.set_text_color(0, 0, 0)
        
        table_row(t["cost"], f"{total_investment:,.0f} {curr}")
        table_row(t["savings"], f"{annual_savings:,.0f} {curr}")
        table_row(t["payback"], f"{payback_years:.1f} Years")
        table_row(t["roi"], f"{roi_percent:.1f}%")
        table_row(t["npv"], f"{npv_value:,.0f} {curr}")

        # التوصيات
        pdf.ln(10)
        pdf.set_text_color(46, 125, 50)
        pdf.set_font_size(14)
        pdf.cell(190, 8, txt=txt(t["rec_title"]), ln=True, align='R' if language=="العربية" else 'L')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font_size(11)
        recs = [
            "- ينصح باستخدام ألواح Mono-PERC لكفاءة أعلى في أجواء المملكة.",
            "- يجب تنظيف الألواح بانتظام (مرتين شهرياً) بسبب الغبار.",
            f"- هذا النظام يعادل زراعة {int(co2_saved_tons * 5)} شجرة تقريباً."
        ]
        for r in recs:
            pdf.cell(190, 6, txt=txt(r), ln=True, align='R' if language=="العربية" else 'L')

        return pdf.output(dest='S').encode('latin-1')

    # زر التحميل
    pdf_data = create_saudi_pdf()
    st.download_button(
        label=t["download_pdf"],
        data=pdf_data,
        file_name="Saudi_Solar_Study.pdf",
        mime="application/pdf",
        type="primary"
    )

else:
    st.info("Ready. Adjust inputs and click Calculate. / جاهز. أدخل البيانات واضغط احسب.")
