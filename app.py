import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
import numpy_financial as npf  # نحتاج دالة لحساب NPV إذا توفرت، أو سنحسبها يدوياً

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Advanced Solar Feasibility", layout="wide", page_icon="☀️")

# --- النصوص والترجمة ---
translations = {
    "English": {
        "title": "☀️ Advanced Solar Feasibility Tool",
        "sidebar_title": "Project Inputs",
        "bill": "Monthly Electricity Bill",
        "area": "Available Roof Area (m²)",
        "cost_per_kw": "System Cost per kW",
        "city": "Location / Peak Sun Hours",
        "price_kwh": "Price per kWh",
        "inflation": "Electricity Inflation Rate (%)",
        "degradation": "Panel Degradation Rate (%)",
        "calculate": "Run Advanced Analysis",
        "results": "Financial Indicators",
        "system_size": "System Size",
        "panels": "Panels (450W)",
        "cost": "Total Investment",
        "savings_1st": "1st Year Savings",
        "roi": "ROI (25 Years)",
        "payback": "Payback Period",
        "npv": "Net Present Value (NPV)",
        "co2": "CO2 Avoided (25 Years)",
        "chart_title": "Monthly Production vs Consumption",
        "chart_cashflow": "Cumulative Cash Flow (25 Years)",
        "download_pdf": "Download Professional Proposal",
        "currency_symbol": "SAR",
        "panels_count": "Panels",
        "error_font": "Warning: 'Amiri-Regular.ttf' not found. Arabic PDF text may fail."
    },
    "العربية": {
        "title": "☀️ أداة دراسة الجدوى الشمسية المتقدمة",
        "sidebar_title": "مدخلات المشروع",
        "bill": "فاتورة الكهرباء الشهرية",
        "area": "مساحة السطح المتاحة (متر مربع)",
        "cost_per_kw": "تكلفة النظام لكل كيلوواط",
        "city": "الموقع / ساعات الشمس",
        "price_kwh": "تعرفة الكهرباء (سعر الكيلوواط)",
        "inflation": "نسبة التضخم السنوي للكهرباء (%)",
        "degradation": "نسبة تناقص كفاءة الألواح سنوياً (%)",
        "calculate": "بدء التحليل المتقدم",
        "results": "المؤشرات المالية",
        "system_size": "حجم المحطة",
        "panels": "عدد الألواح (450 واط)",
        "cost": "إجمالي الاستثمار",
        "savings_1st": "توفير السنة الأولى",
        "roi": "العائد الكلي (25 سنة)",
        "payback": "فترة استرداد رأس المال",
        "npv": "صافي القيمة الحالية (NPV)",
        "co2": "توفير كربون (25 سنة)",
        "chart_title": "مقارنة الإنتاج والاستهلاك الشهري",
        "chart_cashflow": "التدفق النقدي التراكمي (25 سنة)",
        "download_pdf": "تحميل الدراسة المتقدمة (PDF)",
        "currency_symbol": "ر.س",
        "panels_count": "لوح",
        "error_font": "تنبيه: ملف الخط 'Amiri-Regular.ttf' غير موجود. يرجى وضعه في المجلد."
    }
}

# --- القائمة الجانبية ---
with st.sidebar:
    language = st.radio("Language / اللغة", ["العربية", "English"])
    t = translations[language]
    curr = t["currency_symbol"] # العملة المختارة
    
    st.header(t["sidebar_title"])
    
    # المدخلات الأساسية
    monthly_bill = st.number_input(f"{t['bill']} ({curr})", min_value=0.0, value=2000.0)
    price_per_kwh = st.number_input(f"{t['price_kwh']} ({curr})", min_value=0.01, value=0.18, format="%.3f")
    roof_area = st.number_input(t["area"], min_value=10.0, value=500.0)
    cost_per_kw = st.number_input(f"{t['cost_per_kw']} ({curr})", min_value=1000.0, value=3000.0)
    
    city_options = {"Riyadh (5.5h)": 5.5, "Cairo (5.4h)": 5.4, "Dubai (5.6h)": 5.6, "Average (5.0h)": 5.0}
    location_key = st.selectbox(t["city"], list(city_options.keys()))
    sun_hours = city_options[location_key]

    # --- المدخلات المتقدمة (داخل قائمة منسدلة) ---
    st.markdown("---")
    with st.expander("Advanced Settings / إعدادات متقدمة", expanded=True):
        inflation_rate = st.slider(t["inflation"], 0.0, 10.0, 3.0, 0.1) / 100
        degradation_rate = st.slider(t["degradation"], 0.0, 2.0, 0.5, 0.1) / 100
        discount_rate = 0.05 # نسبة الخصم لصافي القيمة الحالية (ثابتة 5%)
    
    run_calc = st.button(t["calculate"], use_container_width=True, type="primary")

# --- المحرك الرئيسي ---
st.title(t["title"])

if run_calc:
    # 1. الحسابات الهندسية الأساسية
    monthly_consumption_kwh = monthly_bill / price_per_kwh if price_per_kwh > 0 else 0
    daily_consumption = monthly_consumption_kwh / 30
    required_system_kw = (daily_consumption / sun_hours) * 1.1 # 1.1 تغطية
    
    max_system_by_area = roof_area / 7 # كل كيلوواط يحتاج 7 متر تقريباً
    final_system_kw = min(required_system_kw, max_system_by_area)
    
    num_panels = int((final_system_kw * 1000) / 450)
    if num_panels < 1: num_panels = 1
    # إعادة حساب حجم النظام بدقة بناءً على عدد الألواح الصحيح
    actual_system_kw = (num_panels * 450) / 1000
    
    total_investment = actual_system_kw * cost_per_kw
    
    # 2. المحاكاة المالية لمدة 25 سنة (Advanced Simulation)
    years_range = range(1, 26)
    cash_flow = []
    cumulative_cash_flow = []
    cumulative_savings_val = -total_investment
    
    current_electricity_price = price_per_kwh
    yearly_production_kwh = actual_system_kw * sun_hours * 365 * 0.9 # 0.9 كفاءة تشغيلية
    
    # حلقة تكرارية لكل سنة (Loop)
    for year in years_range:
        # قيمة التوفير لهذه السنة
        savings = yearly_production_kwh * current_electricity_price
        
        # تخزين التدفق النقدي
        cash_flow.append(savings)
        cumulative_savings_val += savings
        cumulative_cash_flow.append(cumulative_savings_val)
        
        # تجهيز السنة القادمة (تضخم السعر + تدهور الألواح)
        current_electricity_price *= (1 + inflation_rate) # الكهرباء تغلى
        yearly_production_kwh *= (1 - degradation_rate)   # الألواح تضعف
        
    # 3. المؤشرات المالية النهائية
    first_year_savings = cash_flow[0]
    total_savings_25y = sum(cash_flow)
    
    # حساب فترة الاسترداد (متى تحول الرقم من سالب لموجب؟)
    payback_years = 0
    for i, val in enumerate(cumulative_cash_flow):
        if val >= 0:
            payback_years = i + 1 - (val - 0) / (val - cumulative_cash_flow[i-1]) # معادلة دقيقة
            break
    if payback_years == 0 and cumulative_cash_flow[-1] < 0:
        payback_years = 25 # لم يسترد المبلغ

    roi_percent = ((total_savings_25y - total_investment) / total_investment) * 100
    
    # حساب NPV يدوياً
    npv_value = -total_investment
    for i, flow in enumerate(cash_flow):
        npv_value += flow / ((1 + discount_rate) ** (i + 1))
        
    co2_tons = (actual_system_kw * sun_hours * 365 * 25 * 0.45) / 1000 # 25 سنة

    # --- عرض النتائج ---
    
    # الصف الأول: المقاييس الرئيسية
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t["system_size"], f"{actual_system_kw:.2f} kW")
    c2.metric(t["panels"], f"{num_panels} {t['panels_count']}")
    c3.metric(t["cost"], f"{total_investment:,.0f} {curr}")
    c4.metric(t["savings_1st"], f"{first_year_savings:,.0f} {curr}")
    
    # الصف الثاني: المؤشرات المالية المتقدمة
    st.markdown("###")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(t["payback"], f"{payback_years:.1f} Years")
    k2.metric(t["roi"], f"{roi_percent:,.0f}%")
    k3.metric(t["npv"], f"{npv_value:,.0f} {curr}", delta="Project Value", help="صافي القيمة الحالية للمشروع اليوم")
    k4.metric(t["co2"], f"{co2_tons:.1f} Tons", delta_color="normal")
    
    st.divider()

    # --- الرسوم البيانية ---
    col_g1, col_g2 = st.columns(2)
    
    # 1. رسم التدفق النقدي (المنحنى المالي)
    with col_g1:
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Scatter(x=list(years_range), y=cumulative_cash_flow, fill='tozeroy', 
                                  mode='lines', name='Cumulative Balance', line=dict(color='#00C853', width=3)))
        fig_cf.add_hline(y=0, line_dash="dash", line_color="red")
        fig_cf.update_layout(title=t["chart_cashflow"], xaxis_title="Years", yaxis_title=curr, hovermode="x unified")
        st.plotly_chart(fig_cf, use_container_width=True)
        
    # 2. رسم الإنتاج الشهري
    with col_g2:
        mon_prod = actual_system_kw * sun_hours * 30 * 0.9
        prod_curve = [mon_prod * (1 + (i-6)*0.08) if i<6 else mon_prod * (1 - (i-6)*0.08) for i in range(12)] 
        cons_curve = [monthly_consumption_kwh] * 12
        months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=months_labels, y=prod_curve, name='Solar Gen.', marker_color='#FFAB00'))
        fig_bar.add_trace(go.Scatter(x=months_labels, y=cons_curve, name='Usage', line=dict(color='#2962FF', width=3)))
        fig_bar.update_layout(title=t["chart_title"], yaxis_title="kWh", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- تقرير PDF المطور ---
    def create_advanced_pdf():
        pdf = FPDF()
        pdf.add_page()
        
        # الخط العربي
        font_path = 'Amiri-Regular.ttf'
        if os.path.exists(font_path):
            pdf.add_font('Amiri', '', font_path, uni=True)
            pdf.set_font('Amiri', '', 12)
        else:
            pdf.set_font("Arial", size=12)
            st.warning(t["error_font"])

        def txt(text):
            if language == "العربية" and os.path.exists(font_path):
                return get_display(arabic_reshaper.reshape(text))
            return text
            
        def cell_val(label, value):
            pdf.cell(100, 8, txt=txt(label), border=1)
            pdf.cell(90, 8, txt=txt(str(value)), border=1, ln=True, align='C')

        # العنوان
        pdf.set_font_size(18)
        pdf.cell(190, 15, txt=txt(t["title"]), ln=True, align='C')
        pdf.ln(5)
        
        # القسم 1: المدخلات
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt(f"1. {t['sidebar_title']}"), ln=True, fill=True)
        pdf.set_font_size(12)
        cell_val(f"{t['bill']}", f"{monthly_bill} {curr}")
        cell_val(f"{t['price_kwh']}", f"{price_per_kwh} {curr}")
        cell_val(f"{t['inflation']}", f"{inflation_rate*100} %")
        pdf.ln(5)
        
        # القسم 2: المواصفات الفنية
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt(f"2. {t['results']} (Technical)"), ln=True, fill=True)
        pdf.set_font_size(12)
        cell_val(t["system_size"], f"{actual_system_kw:.2f} kW")
        cell_val(t["panels"], f"{num_panels}")
        pdf.ln(5)

        # القسم 3: التحليل المالي
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt(f"3. {t['results']} (Financial 25Y)"), ln=True, fill=True)
        pdf.set_font_size(12)
        
        # تلوين خاص للنتائج المهمة
        pdf.set_text_color(0, 100, 0) # أخضر
        cell_val(t["savings_1st"], f"{first_year_savings:,.0f} {curr}")
        cell_val(t["npv"], f"{npv_value:,.0f} {curr}")
        pdf.set_text_color(0, 0, 0) # أسود
        cell_val(t["cost"], f"{total_investment:,.0f} {curr}")
        cell_val(t["payback"], f"{payback_years:.1f} Years")
        
        pdf.ln(10)
        pdf.set_font_size(10)
        pdf.cell(190, 10, txt=txt("Generated by Advanced Solar Tool - Professional Edition"), ln=True, align='C')
        
        return pdf.output(dest='S').encode('latin-1')

    pdf_data = create_advanced_pdf()
    st.download_button(label=t["download_pdf"], data=pdf_data, file_name="Advanced_Solar_Study.pdf", mime="application/pdf", type="primary")

else:
    st.info("Ready for analysis. Adjust inputs and click start. / جاهز للتحليل، أدخل البيانات واضغط زر البدء")