import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
import numpy_financial as npf

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Pro Solar KSA", layout="wide", page_icon="☀️")

# --- النصوص والترجمة ---
translations = {
    "English": {
        "title": "☀️ Saudi Solar Feasibility Tool (Pro)",
        "sidebar_title": "Project Inputs",
        "bill": "Average Monthly Bill (SAR)",
        "area": "Roof Area (m²)",
        "cost_per_kw": "Solar System Cost/kW (SAR)",
        "city": "City (Saudi Arabia)",
        "price_kwh": "Tariff Rate (SAR/kWh)",
        "inflation": "Electricity Inflation (%)",
        "degradation": "Panel Degradation (%)",
        "consumer_type": "Consumer Type",
        "residential": "Residential (High Summer Load)",
        "commercial": "Commercial (Balanced Load)",
        "battery_section": "🔋 Battery Storage System",
        "add_battery": "Add Battery Storage?",
        "battery_hours": "Backup Hours Needed",
        "battery_cost": "Battery Cost (SAR/kWh)",
        "calculate": "Calculate Results",
        "results": "Feasibility Analysis",
        "breakdown": "Quotation Breakdown",
        "system_size": "System Size",
        "panels": "Panels (450W)",
        "cost": "Total Investment",
        "savings": "Annual Savings",
        "roi": "ROI (25 Years)",
        "payback": "Payback Period",
        "npv": "Net Present Value (NPV)",
        "co2": "CO2 Saved (25 Years)",
        "chart_title": "Production vs Consumption (Seasonal)",
        "chart_cashflow": "Cumulative Cash Flow",
        "download_pdf": "Download Professional Proposal",
        "currency": "SAR",
        "panels_count": "Panels",
        "rec_title": "Technical Recommendations"
    },
    "العربية": {
        "title": "☀️ أداة جدوى الطاقة الشمسية (النسخة الاحترافية)",
        "sidebar_title": "مدخلات المشروع",
        "bill": "متوسط الفاتورة الشهرية (ريال)",
        "area": "مساحة السطح المتاحة (متر مربع)",
        "cost_per_kw": "تكلفة النظام الشمسي للكيلوواط",
        "city": "المدينة / المنطقة",
        "price_kwh": "تعرفة الكهرباء (ريال/ك.و.س)",
        "inflation": "نسبة التضخم السنوي للكهرباء (%)",
        "degradation": "نسبة تناقص كفاءة الألواح (%)",
        "consumer_type": "نوع الاستهلاك",
        "residential": "سكني (أحمال تكييف صيفية عالية)",
        "commercial": "تجاري (أحمال متوازنة)",
        "battery_section": "🔋 نظام البطاريات والتخزين",
        "add_battery": "هل تريد إضافة بطاريات؟",
        "battery_hours": "عدد ساعات التشغيل الاحتياطي",
        "battery_cost": "تكلفة البطارية (ريال/kWh)",
        "calculate": "احسب النتائج",
        "results": "تحليل الجدوى الاقتصادية",
        "breakdown": "تفاصيل عرض السعر",
        "system_size": "حجم المحطة المطلوب",
        "panels": "عدد الألواح (450 واط)",
        "cost": "إجمالي الاستثمار المتوقع",
        "savings": "التوفير السنوي",
        "roi": "العائد على الاستثمار (25 سنة)",
        "payback": "فترة استرداد رأس المال",
        "npv": "صافي القيمة الحالية (NPV)",
        "co2": "توفير CO2 (25 سنة)",
        "chart_title": "مقارنة الإنتاج والاستهلاك (موسمي)",
        "chart_cashflow": "تحليل التدفق النقدي التراكمي",
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
    
    # نوع الاستهلاك (الميزة 1)
    consumer_type = st.selectbox(t["consumer_type"], [t["residential"], t["commercial"]])
    monthly_bill = st.number_input(t["bill"], min_value=0.0, value=1500.0, step=100.0)
    
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
    cost_per_kw = st.number_input(t["cost_per_kw"], min_value=1000.0, value=3000.0)

    # قسم البطاريات (الميزة 2)
    st.markdown("---")
    st.subheader(t["battery_section"])
    want_batteries = st.checkbox(t["add_battery"])
    battery_cost_total = 0.0
    battery_size_kwh = 0.0
    
    if want_batteries:
        backup_hours = st.slider(t["battery_hours"], 1, 12, 4)
        cost_battery_unit = st.number_input(t["battery_cost"], value=1500.0)
    
    st.markdown("---")
    with st.expander("إعدادات متقدمة / Advanced"):
        inflation_rate = st.slider(t["inflation"], 0.0, 10.0, 3.0, 0.1) / 100
        degradation_rate = st.slider(t["degradation"], 0.0, 2.0, 0.5, 0.1) / 100
        discount_rate = 0.05
    
    run_calc = st.button(t["calculate"], type="primary")

# --- المحرك الرئيسي ---
st.title(t["title"])

if run_calc:
    # 1. حساب الاستهلاك الموسمي (الميزة 1)
    avg_monthly_kwh = monthly_bill / price_per_kwh if price_per_kwh > 0 else 0
    
    # محاكاة الاستهلاك الشهري (السعودية: الصيف نار، الشتاء معتدل)
    cons_curve = []
    if consumer_type == t["residential"]:
        # أشهر الصيف (5-9) تضرب في معامل عالي، الشتاء معامل منخفض
        factors = [0.6, 0.7, 0.8, 1.1, 1.4, 1.5, 1.5, 1.5, 1.3, 1.0, 0.8, 0.7]
    else:
        # التجاري أكثر ثباتاً
        factors = [0.9, 0.9, 1.0, 1.0, 1.1, 1.1, 1.1, 1.1, 1.1, 1.0, 0.9, 0.9]
    
    # ضبط المعاملات بحيث يكون المتوسط يساوي الفاتورة المدخلة
    avg_factor = sum(factors) / 12
    normalized_factors = [f / avg_factor for f in factors]
    cons_curve = [avg_monthly_kwh * f for f in normalized_factors]
    
    yearly_consumption = sum(cons_curve)
    
    # 2. حساب حجم النظام
    # نستخدم أعلى شهر في الصيف لتحديد الحجم المطلوب (أو المتوسط حسب الرغبة)
    # هنا سنستخدم المتوسط السنوي مع معامل تغطية
    daily_avg_consumption = avg_monthly_kwh / 30
    required_system_kw = (daily_avg_consumption / sun_hours) * 1.15
    max_system_by_area = roof_area / 7
    final_system_kw = min(required_system_kw, max_system_by_area)
    
    panel_wattage = 450
    num_panels = int((final_system_kw * 1000) / panel_wattage)
    if num_panels < 1: num_panels = 1
    actual_system_kw = (num_panels * panel_wattage) / 1000
    
    # تكلفة الطاقة الشمسية فقط
    solar_investment = actual_system_kw * cost_per_kw
    
    # 3. حساب البطاريات (الميزة 2)
    if want_batteries:
        # نحسب حجم البطارية بناء على معدل الاستهلاك اليومي والساعات المطلوبة
        battery_size_kwh = (daily_avg_consumption / 24) * backup_hours
        battery_cost_total = battery_size_kwh * cost_battery_unit
    else:
        battery_size_kwh = 0
        battery_cost_total = 0
        
    total_investment = solar_investment + battery_cost_total
    
    # 4. المحاكاة المالية
    years_range = range(1, 26)
    cash_flow = []
    cumulative_cash_flow = []
    cumulative_val = -total_investment
    
    current_price = price_per_kwh
    yearly_prod = actual_system_kw * sun_hours * 365 * 0.9
    
    # نحتاج توزيع الإنتاج شهرياً للرسم البياني
    mon_prod_avg = yearly_prod / 12
    prod_curve = []
    for i in range(12):
        # الإنتاج أيضاً يتغير في الصيف (حرارة عالية تقلل الكفاءة قليلاً) وفي الربيع يزيد
        if i in [5, 6, 7, 8]: # أشهر الصيف الحارة
             val = mon_prod_avg * 0.95
        elif i in [2, 3, 9, 10]: # أشهر الربيع والخريف (أفضل إنتاج)
             val = mon_prod_avg * 1.1
        else:
             val = mon_prod_avg
        prod_curve.append(val)
        
    # تصحيح المجموع ليطابق الإنتاج السنوي
    current_total_prod = sum(prod_curve)
    prod_curve = [p * (yearly_prod / current_total_prod) for p in prod_curve]

    for year in years_range:
        # التوفير = الإنتاج * السعر (مع افتراض استهلاك كل الإنتاج أو تصديره)
        savings = yearly_prod * current_price
        
        # إذا كان هناك بطاريات، قد تزيد التوفير بتقليل الاعتماد على الشبكة وقت الذروة (نفترض توفير كامل هنا)
        
        # مصاريف صيانة (O&M) - نخصم 1% سنوياً
        om_cost = total_investment * 0.01
        net_year_savings = savings - om_cost
        
        cash_flow.append(net_year_savings)
        cumulative_val += net_year_savings
        cumulative_cash_flow.append(cumulative_val)
        
        current_price *= (1 + inflation_rate)
        yearly_prod *= (1 - degradation_rate)
        
    annual_savings = cash_flow[0] + (total_investment * 0.01) # نعرض التوفير الإجمالي قبل خصم الصيانة للعرض
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
        npv_value += flow / ((1 + discount_rate) ** (i + 1))
        
    co2_saved_tons = (actual_system_kw * sun_hours * 365 * 25 * 0.5) / 1000

    # --- عرض النتائج ---
    st.divider()
    st.subheader(t["results"])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t["system_size"], f"{actual_system_kw:.2f} kW")
    c2.metric(t["panels"], f"{num_panels} {t['panels_count']}")
    
    # عرض التكلفة مع توضيح البطارية
    cost_label = t["cost"]
    if want_batteries: cost_label += " (+Battery)"
    c3.metric(cost_label, f"{total_investment:,.0f} {curr}")
    
    c4.metric(t["savings"], f"{annual_savings:,.0f} {curr}")
    
    c5, c6, c7 = st.columns(3)
    c5.metric(t["roi"], f"{roi_percent:.0f}%")
    c6.metric(t["payback"], f"{payback_years:.1f} Years")
    c7.metric(t["npv"], f"{npv_value:,.0f} {curr}")
    
    st.divider()
    
    # عرض تفصيل السعر (الميزة 3)
    st.subheader(t["breakdown"])
    # تقديرات السوق: الألواح 45%، العواكس 15%، التركيب 20%، الهيكل 20%
    solar_panels_cost = solar_investment * 0.45
    inverter_cost = solar_investment * 0.15
    structure_cost = solar_investment * 0.20
    installation_cost = solar_investment * 0.20
    
    # ننشئ DataFrame للعرض
    breakdown_data = {
        "Item / البند": ["Solar Panels (الألواح)", "Inverter (العواكس)", "Mounting Structure (الهيكل)", "Installation & Labor (التركيب)", "Batteries (البطاريات)"],
        "Cost / التكلفة": [solar_panels_cost, inverter_cost, structure_cost, installation_cost, battery_cost_total]
    }
    df_breakdown = pd.DataFrame(breakdown_data)
    # تنسيق الأرقام
    df_breakdown["Cost / التكلفة"] = df_breakdown["Cost / التكلفة"].apply(lambda x: f"{x:,.0f} {curr}")
    st.table(df_breakdown)

    # --- الرسومات البيانية ---
    months_lbl = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    if language == "العربية":
         months_lbl = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=months_lbl, y=prod_curve, name='Production / الإنتاج', marker_color='#FBC02D'))
    fig1.add_trace(go.Scatter(x=months_lbl, y=cons_curve, name='Consumption / الاستهلاك', line=dict(color='#1565C0', width=3)))
    fig1.update_layout(title=t["chart_title"], yaxis_title="kWh", height=400)
    st.plotly_chart(fig1, use_container_width=True)
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=list(years_range), y=cumulative_cash_flow, fill='tozeroy', name='Net Savings', line=dict(color='#2E7D32')))
    fig2.update_layout(title=t["chart_cashflow"], xaxis_title="Year", yaxis_title=curr, height=400)
    fig2.add_hline(y=0, line_dash="dash", line_color="red")
    st.plotly_chart(fig2, use_container_width=True)

    # --- ملف PDF (مع تفصيل السعر) ---
    def create_pro_pdf():
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
        pdf.cell(190, 5, txt=txt("Professional Technical & Financial Proposal"), ln=True, align='C')
        pdf.ln(15)
        
        def table_row(label, value):
            pdf.set_font('Amiri', '', 12)
            pdf.cell(110, 8, txt=txt(label), border=1, align='R' if language=="العربية" else 'L')
            pdf.set_font('Amiri', '', 12)
            pdf.cell(80, 8, txt=txt(str(value)), border=1, ln=True, align='C')

        # 1. الملخص
        pdf.set_fill_color(46, 125, 50) 
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt("1. ملخص المشروع (Project Summary)"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        pdf.set_text_color(0, 0, 0)
        
        table_row(t["city"], location_key.split('/')[0])
        table_row(t["bill"], f"{monthly_bill} {curr}")
        if want_batteries:
            table_row("نظام البطاريات", f"{battery_size_kwh:.1f} kWh")
        
        pdf.ln(5)

        # 2. الفني والمالي
        pdf.set_fill_color(46, 125, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, txt=txt("2. التحليل الفني والمالي"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        pdf.set_text_color(0, 0, 0)
        
        table_row(t["system_size"], f"{actual_system_kw:.2f} kW")
        table_row(t["panels"], f"{num_panels}")
        table_row(t["savings"], f"{annual_savings:,.0f} {curr}")
        table_row(t["payback"], f"{payback_years:.1f} Years")
        table_row(t["roi"], f"{roi_percent:.1f}%")
        
        # 3. تفاصيل السعر (الميزة 3 في PDF)
        pdf.ln(5)
        pdf.set_fill_color(46, 125, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, txt=txt("3. تفاصيل عرض السعر (Quotation Breakdown)"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        pdf.set_text_color(0, 0, 0)
        
        # جدول الأسعار
        table_row("الألواح الشمسية (Panels)", f"{solar_panels_cost:,.0f} {curr}")
        table_row("العواكس (Inverters)", f"{inverter_cost:,.0f} {curr}")
        table_row("الهيكل والتركيب (Structure & Install)", f"{(structure_cost+installation_cost):,.0f} {curr}")
        if want_batteries:
             table_row("نظام البطاريات (Batteries)", f"{battery_cost_total:,.0f} {curr}")
        
        # السطر الأخير للمجموع
        pdf.set_font('Amiri', '', 12) # بولد لو أمكن
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(110, 10, txt=txt(t["cost"]), border=1, fill=True, align='R' if language=="العربية" else 'L')
        pdf.cell(80, 10, txt=txt(f"{total_investment:,.0f} {curr}"), border=1, fill=True, align='C')

        # التوصيات
        pdf.ln(10)
        pdf.set_text_color(46, 125, 50)
        pdf.set_font_size(14)
        pdf.cell(190, 8, txt=txt(t["rec_title"]), ln=True, align='R' if language=="العربية" else 'L')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font_size(11)
        recs = [
            "- التصميم يعتمد على نمط الاستهلاك السكني (صيف حار).",
            "- الأسعار تقديرية وقد تختلف حسب معاينة الموقع.",
            f"- هذا النظام يعادل زراعة {int(co2_saved_tons * 5)} شجرة تقريباً."
        ]
        for r in recs:
            pdf.cell(190, 6, txt=txt(r), ln=True, align='R' if language=="العربية" else 'L')

        return pdf.output(dest='S').encode('latin-1')

    pdf_data = create_pro_pdf()
    st.download_button(
        label=t["download_pdf"],
        data=pdf_data,
        file_name="Pro_Saudi_Solar_Study.pdf",
        mime="application/pdf",
        type="primary"
    )

else:
    st.info("Ready. Adjust inputs and click Calculate. / جاهز. أدخل البيانات واضغط احسب.")
