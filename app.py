import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
import numpy_financial as npf
import folium
from folium.plugins import Draw, Fullscreen
from streamlit_folium import st_folium
from shapely.geometry import shape
import math

# ==========================================
# 🏷️ إعدادات الشركة
# ==========================================
PAGE_TITLE = "النظام الشامل للطاقة الشمسية"
COMPANY_NAME = "شركة حلول الطاقة المتقدمة"
REPORT_TITLE = "عرض فني ومالي - Technical & Financial Proposal"
# ==========================================

st.set_page_config(page_title=PAGE_TITLE, layout="wide", page_icon="☀️")

# --- دالة تنسيق الأرقام (بدون كسور) ---
def fmt(num):
    return f"{int(num):,}" # 12,500

# --- دالة حساب المساحة ---
def calculate_area_m2(geojson_geometry):
    if geojson_geometry is None: return 0.0
    geom = shape(geojson_geometry)
    center_lat = geom.centroid.y
    lat_to_m = 111132.92
    lon_to_m = 40075000 * math.cos(math.radians(center_lat)) / 360
    new_coords = []
    if geom.geom_type == 'Polygon':
        coords = list(geom.exterior.coords)
        for x, y in coords:
            new_coords.append((x * lon_to_m, y * lat_to_m))
    else: return 0.0
    from shapely.geometry import Polygon
    poly_m = Polygon(new_coords)
    return poly_m.area

# --- النصوص ---
translations = {
    "English": {
        "sidebar_title": "Project Inputs", "map_title": "📍 High-Res Site Survey", "area_calc": "Drawn Area (m²)",
        "input_mode": "Calculation Method", "mode_avg": "Simple Average", "mode_seasonal": "Seasonal Simulation",
        "mode_12m": "12-Month Bills", "consumer_type": "Consumer Type", "res": "Residential",
        "com": "Commercial", "bill_avg": "Avg Monthly Bill (SAR)", "area": "Usable Roof Area (m²)",
        "cost_per_kw": "System Cost/kW (SAR)", "city": "City", "battery_section": "🔋 Battery Storage", 
        "add_battery": "Add Batteries?", "battery_hours": "Backup Hours", "calculate": "Run Analysis", 
        "results": "Feasibility Analysis", "breakdown": "Cost Breakdown", "ai_opinion": "🤖 AI Analysis & Definitions", 
        "download_pdf": "Download Report", "chart_title": "Load vs Generation", "chart_cashflow": "Cash Flow", 
        "currency": "SAR", "panels_count": "Panels", "coords": "Coordinates", "lcoe_help": "Cost to produce 1 kWh over 25 years",
        "npv_help": "Total profit value in today's money"
    },
    "العربية": {
        "sidebar_title": "مدخلات المشروع", "map_title": "📍 معاينة الموقع (أقمار صناعية)", "area_calc": "المساحة المرسومة (م²)",
        "input_mode": "طريقة الحساب", "mode_avg": "متوسط بسيط (سريع)", "mode_seasonal": "محاكاة موسمية (دقيق)",
        "mode_12m": "إدخال 12 فاتورة (فعلي)", "consumer_type": "نوع النشاط", "res": "سكني (تكييف عالي)",
        "com": "تجاري (متوازن)", "bill_avg": "متوسط الفاتورة (ريال)", "area": "مساحة السطح (م²)",
        "cost_per_kw": "تكلفة الكيلوواط (ريال)", "city": "المدينة", "battery_section": "🔋 نظام البطاريات", 
        "add_battery": "إضافة بطاريات؟", "battery_hours": "ساعات التشغيل الليلي", "calculate": "بدء التحليل الشامل", 
        "results": "نتائج الدراسة", "breakdown": "تفاصيل التكلفة", "ai_opinion": "🤖 رأي المستشار الذكي (مع الشرح)", 
        "download_pdf": "تحميل التقرير الرسمي (PDF)", "chart_title": "تحليل الأحمال مقابل الإنتاج", 
        "chart_cashflow": "تحليل التدفق النقدي", "currency": "ر.س", "panels_count": "لوح", "coords": "الإحداثيات",
        "lcoe_help": "LCOE: هي التكلفة الفعلية عليك لإنتاج كيلوواط واحد من الطاقة الشمسية طوال عمر المشروع.",
        "npv_help": "NPV: صافي القيمة الحالية، وهو مقياس للربح الحقيقي بعد خصم التضخم وقيمة المال الزمنية."
    }
}

# --- القائمة الجانبية ---
with st.sidebar:
    language = st.radio("Language / اللغة", ["العربية", "English"])
    t = translations[language]
    curr = t["currency"]
    
    st.header(t["sidebar_title"])

    # 1. الخريطة
    if 'calculated_area' not in st.session_state: st.session_state['calculated_area'] = 0.0
    if 'coords' not in st.session_state: st.session_state['coords'] = (0.0, 0.0)

    with st.expander(t["map_title"], expanded=True):
        default_location = [24.7136, 46.6753]
        google_tiles = 'http://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}'
        m = folium.Map(location=default_location, zoom_start=18, max_zoom=22, tiles=None)
        folium.TileLayer(tiles=google_tiles, attr='Google', name='Google Satellite', overlay=False, control=True).add_to(m)
        Fullscreen().add_to(m)
        draw = Draw(export=False, position='topleft', draw_options={'polyline':False,'rectangle':False,'circle':False,'marker':True,'circlemarker':False,'polygon':True}, edit_options={'edit': True})
        draw.add_to(m)
        map_output = st_folium(m, height=350, width=300)
        
        if map_output and 'last_active_drawing' in map_output and map_output['last_active_drawing']:
            drawing = map_output['last_active_drawing']
            if drawing['geometry']['type'] == 'Polygon':
                drawn_area = calculate_area_m2(drawing['geometry'])
                st.session_state['calculated_area'] = drawn_area
                st.success(f"{t['area_calc']}: {int(drawn_area)} m²")
            elif drawing['geometry']['type'] == 'Point':
                c = drawing['geometry']['coordinates']
                st.session_state['coords'] = (c[1], c[0])

    st.divider()
    
    # 2. الفواتير
    input_method = st.radio(t["input_mode"], [t["mode_seasonal"], t["mode_12m"], t["mode_avg"]])
    monthly_bills = []
    
    if input_method == t["mode_seasonal"]:
        avg_val = st.number_input(t["bill_avg"], value=1500.0, step=100.0)
        cons_type = st.selectbox(t["consumer_type"], [t["res"], t["com"]])
        factors = [0.6, 0.7, 0.8, 1.1, 1.4, 1.5, 1.5, 1.5, 1.3, 1.0, 0.8, 0.7] if cons_type == t["res"] else [0.9, 0.9, 1.0, 1.0, 1.1, 1.1, 1.1, 1.1, 1.1, 1.0, 0.9, 0.9]
        avg_factor = sum(factors) / 12
        monthly_bills = [avg_val * (f / avg_factor) for f in factors]
        
    elif input_method == t["mode_12m"]:
        months_display = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'] if language == "العربية" else ['Jan','Feb','...']
        cols = st.columns(3)
        for i, m in enumerate(months_display):
            with cols[i%3]:
                val = st.number_input(m, value=(2000.0 if i in [5,6,7,8] else 800.0), key=i)
                monthly_bills.append(val)
    else:
        val = st.number_input(t["bill_avg"], value=1500.0)
        monthly_bills = [val]*12

    # 3. الموقع والمساحة
    saudi_cities = {"الرياض":5.8, "جدة":6.0, "الدمام":5.6, "مكة":6.2, "المدينة":6.3, "أبها":5.9, "تبوك":6.1, "حائل":6.0, "جازان":5.9, "القصيم":5.8}
    location_key = st.selectbox(t["city"], list(saudi_cities.keys()))
    sun_hours = saudi_cities[location_key]
    
    default_area = st.session_state['calculated_area'] if st.session_state['calculated_area'] > 0 else 300.0
    roof_area = st.number_input("المساحة (m²)", value=float(default_area))
    
    price_kwh = st.number_input("سعر الكيلوواط", value=0.18, format="%.3f")
    cost_kw = st.number_input("سعر النظام (SAR/kW)", value=3000.0)
    
    # 4. البطاريات والتقنية
    st.markdown("---")
    want_battery = st.checkbox(t["add_battery"])
    batt_cost_unit = 1500.0
    batt_hours = 0
    if want_battery:
        batt_hours = st.slider(t["battery_hours"], 1, 12, 4)
        batt_cost_unit = st.number_input("سعر البطارية (SAR/kWh)", value=1500.0)
    
    # إعدادات مخفية (للمختصين) مع شروحات
    with st.expander("⚙️ إعدادات متقدمة"):
        inflation_rate = st.slider("التضخم / Inflation", 0.0, 10.0, 3.0, 0.1) / 100
        st.caption("معدل زيادة أسعار الكهرباء سنوياً.")
        degradation_rate = 0.005
        discount_rate = 0.05
    
    run_calc = st.button(t["calculate"], type="primary")

# --- المحرك الرئيسي ---
st.title(PAGE_TITLE)

if run_calc:
    # 1. الحسابات
    cons_kwh = [b/price_kwh if price_kwh > 0 else 0 for b in monthly_bills]
    total_cons = sum(cons_kwh)
    daily_avg = (total_cons/12)/30
    
    req_sys = (daily_avg/sun_hours)*1.15
    max_sys = roof_area/7
    final_sys = min(req_sys, max_sys)
    
    panels = int((final_sys*1000)/450)
    if panels < 1: panels = 1
    actual_sys = (panels*450)/1000
    
    solar_cost = actual_sys * cost_kw
    batt_size = 0
    batt_cost = 0
    if want_battery:
        load_hourly = daily_avg / 24
        batt_size = load_hourly * batt_hours
        batt_cost = batt_size * batt_cost_unit
    
    total_invest = solar_cost + batt_cost
    
    # المحاكاة مع الفواقد الحرارية
    prod_curve_kwh = []
    total_prod_year = 0
    mon_prod_base = actual_sys * sun_hours * 30 * 0.80 # كفاءة 80%
    
    for i in range(12):
        temp_factor = 0.85 if i in [5, 6, 7, 8] else 1.0 # حرارة الصيف
        monthly_gen = mon_prod_base * temp_factor
        prod_curve_kwh.append(monthly_gen)
        total_prod_year += monthly_gen

    # التحليل المالي
    years_range = range(1, 26)
    cash_flow = []
    cumulative_cash_flow = []
    cumulative_val = -total_invest
    current_price_sim = price_kwh
    yearly_prod_sim = total_prod_year
    total_prod_lifecycle = 0
    
    for year in years_range:
        net_savings = (min(yearly_prod_sim, total_cons) * current_price_sim) - (total_invest * 0.01)
        cash_flow.append(net_savings)
        cumulative_val += net_savings
        cumulative_cash_flow.append(cumulative_val)
        
        total_prod_lifecycle += min(yearly_prod_sim, total_cons)
        current_price_sim *= (1 + inflation_rate)
        yearly_prod_sim *= (1 - degradation_rate)
        
    annual_savings_y1 = cash_flow[0] + (total_invest * 0.01)
    
    # LCOE & NPV & Payback
    lcoe = (total_invest + (total_invest * 0.01 * 25)) / total_prod_lifecycle if total_prod_lifecycle > 0 else 0
    npv_value = npf.npv(discount_rate, [-total_invest] + cash_flow)
    
    payback_years = 0
    for i, val in enumerate(cumulative_cash_flow):
        if val >= 0:
            payback_years = i + 1
            break
    if payback_years == 0: payback_years = 25
            
    roi = ((sum(cash_flow) / total_invest) * 100)

    # --- النتائج (أرقام نظيفة) ---
    st.subheader(t["results"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("حجم النظام (kWp)", f"{actual_sys:.2f}")
    c2.metric("عدد الألواح", f"{panels}")
    c3.metric("التكلفة الكلية", f"{fmt(total_invest)} {curr}")
    c4.metric("التوفير السنوي", f"{fmt(annual_savings_y1)} {curr}")
    
    st.markdown("---")
    st.markdown("##### **المؤشرات المالية المتقدمة**")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("العائد (ROI)", f"{int(roi)}%")
    f2.metric("الاسترداد (Payback)", f"{payback_years} Years")
    f3.metric("صافي القيمة (NPV)", f"{fmt(npv_value)} {curr}", help=t["npv_help"])
    f4.metric("تكلفة الكيلوواط (LCOE)", f"{lcoe:.3f} {curr}", help=t["lcoe_help"])

    # --- الذكاء الاصطناعي (مع الشرح) ---
    st.markdown("---")
    st.subheader(t["ai_opinion"])
    
    advice = ""
    if roi > 250: advice = f"🚀 **مشروع ممتاز (A+):** العميل سيسترد رأس المال في {payback_years} سنوات فقط. الأرباح المتوقعة خلال 25 سنة تتجاوز {fmt(sum(cash_flow))} ريال."
    elif roi > 100: advice = f"✅ **مشروع مجدي (B):** النظام يغطي الاستهلاك بشكل جيد. الاستثمار آمن بمعدل عائد {int(roi)}%."
    else: advice = f"⚠️ **جدوى منخفضة (C):** التوفير السنوي ({fmt(annual_savings_y1)}) قليل مقارنة بالتكلفة. حاول تقليل عدد الألواح."
    
    # إضافة شرح للمصطلحات
    ai_explanation = f"""
    \n\n--- **شرح المصطلحات:** ---
    * **LCOE ({lcoe:.3f}):** تعني أن كل كيلوواط تنتجه من شمسك يكلفك {lcoe:.3f} ريال، بينما تشتريه من الدولة بـ {price_kwh} ريال. الفرق هو ربحك!
    * **NPV ({fmt(npv_value)}):** هذا هو الربح الصافي الحقيقي للمشروع بفلوس "اليوم"، بعد خصم التضخم. إذا كان موجباً، فالمشروع رابح 100%.
    """
    st.info(advice + ai_explanation, icon="🤖")

    # --- الرسوم البيانية ---
    st.markdown("---")
    fig = go.Figure()
    months_ar = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
    fig.add_trace(go.Bar(x=months_ar, y=prod_curve_kwh, name='الإنتاج الشمسي', marker_color='#FBC02D'))
    fig.add_trace(go.Scatter(x=months_ar, y=cons_kwh, name='استهلاك العميل', line=dict(color='#D32F2F', width=3)))
    fig.update_layout(title=t["chart_title"], yaxis_title="kWh")
    st.plotly_chart(fig, use_container_width=True)

    # --- PDF محسن (مع رسوميات داخلية) ---
    def create_pdf():
        pdf = FPDF()
        pdf.add_page()
        font_path = 'Amiri-Regular.ttf'
        if os.path.exists(font_path):
            pdf.add_font('Amiri', '', font_path, uni=True)
            pdf.set_font('Amiri', '', 12)
        else: pdf.set_font("Arial", size=12)
        
        def txt(text):
            if language == "العربية" and os.path.exists(font_path): return get_display(arabic_reshaper.reshape(text))
            return text

        # Header
        pdf.set_fill_color(44, 62, 80)
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(24)
        pdf.cell(190, 15, txt=txt(COMPANY_NAME), ln=True, align='C') 
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt(REPORT_TITLE), ln=True, align='C')
        pdf.ln(20)
        pdf.set_text_color(0, 0, 0)
        
        def row(k, v):
            pdf.cell(110, 8, txt=txt(k), border=1, align='R')
            pdf.cell(80, 8, txt=txt(str(v)), border=1, ln=True, align='C')

        # 1. البيانات
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt("1. ملخص المشروع والبيانات"), ln=True, fill=True, align='R')
        pdf.set_font_size(12)
        
        lat, lng = st.session_state['coords']
        loc_str = f"{lat:.5f}, {lng:.5f}" if lat!=0 else "غير محدد"
        row("الموقع والإحداثيات", f"{location_key} ({loc_str})")
        row("حجم النظام المقترح", f"{actual_sys:.2f} kWp")
        row("عدد الألواح", f"{panels}")
        row("إجمالي الاستهلاك السنوي", f"{fmt(total_cons)} kWh")
        row("الإنتاج المتوقع (السنة 1)", f"{fmt(total_prod_year)} kWh")
        pdf.ln(5)

        # 2. المالي
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt("2. التحليل المالي والاستثماري"), ln=True, fill=True, align='R')
        pdf.set_font_size(12)
        row("إجمالي التكلفة (CAPEX)", f"{fmt(total_invest)} SAR")
        row("التوفير السنوي (Year 1)", f"{fmt(annual_savings_y1)} SAR")
        row("صافي القيمة الحالية (NPV)", f"{fmt(npv_value)} SAR")
        row("تكلفة الكيلوواط (LCOE)", f"{lcoe:.3f} SAR/kWh")
        row("فترة استرداد رأس المال", f"{payback_years} Years")
        
        # 3. رسم بياني بسيط داخل PDF (Visual Savings)
        pdf.ln(10)
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt("3. مقارنة التكلفة والعائد (Visual Chart)"), ln=True, fill=True, align='R')
        pdf.ln(5)
        
        # رسم مستطيلات تمثل الأرقام
        max_val = max(total_invest, sum(cash_flow))
        w_invest = (total_invest / max_val) * 150
        w_savings = (sum(cash_flow) / max_val) * 150
        
        pdf.set_font_size(10)
        # شريط التكلفة (أحمر)
        pdf.set_fill_color(231, 76, 60)
        pdf.cell(30, 10, txt=txt("التكلفة:"), align='R')
        pdf.cell(w_invest, 10, txt="", fill=True)
        pdf.cell(30, 10, txt=f"{fmt(total_invest)} SAR", ln=True)
        
        # شريط الأرباح (أخضر)
        pdf.set_fill_color(46, 204, 113)
        pdf.cell(30, 10, txt=txt("أرباح 25 سنة:"), align='R')
        pdf.cell(w_savings, 10, txt="", fill=True)
        pdf.cell(30, 10, txt=f"{fmt(sum(cash_flow))} SAR", ln=True)
        
        pdf.ln(10)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(190, 6, txt=txt("توصية المستشار: " + advice.replace('**','')), border=1, align='R')

        return pdf.output(dest='S').encode('latin-1')

    st.download_button(t["download_pdf"], create_pdf(), "Solar_Platinum_Report.pdf", "application/pdf", type="primary")

else:
    st.info("النظام جاهز. ابدأ بتحديد الموقع على الخريطة.")
