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
PAGE_TITLE = "النظام الهندسي للطاقة الشمسية"
COMPANY_NAME = "شركة حلول الطاقة المتقدمة"
REPORT_TITLE = "دراسة جدوى هندسية ومالية - Engineering Proposal"
# ==========================================

st.set_page_config(page_title=PAGE_TITLE, layout="wide", page_icon="⚡")

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
        "sidebar_title": "Engineering Inputs", "map_title": "📍 Satellite Site Survey", "area_calc": "Net Area (m²)",
        "input_mode": "Load Analysis Method", "mode_seasonal": "Seasonal Simulation (Recommended)",
        "mode_12m": "12-Month Bills", "mode_avg": "Simple Average", "bill_avg": "Avg Bill (SAR)",
        "city": "Location", "battery_section": "🔋 Storage System", "add_battery": "Add Batteries?",
        "battery_hours": "Autonomy Hours", "calculate": "Run Engineering Analysis", "results": "Technical Analysis",
        "financials": "Financial KPIs", "breakdown": "CAPEX Breakdown", "ai_opinion": "🤖 Expert Analysis",
        "download_pdf": "Download Engineering Report", "lcoe": "LCOE (SAR/kWh)", "autonomy": "Real Autonomy",
        "heat_loss": "Heat Loss Factor Applied"
    },
    "العربية": {
        "sidebar_title": "المدخلات الهندسية", "map_title": "📍 مسح الموقع (أقمار صناعية)", "area_calc": "المساحة الصافية (م²)",
        "input_mode": "طريقة تحليل الأحمال", "mode_seasonal": "محاكاة موسمية (موصى به)",
        "mode_12m": "إدخال 12 فاتورة", "mode_avg": "متوسط بسيط", "bill_avg": "متوسط الفاتورة (ريال)",
        "city": "المدينة والمناخ", "battery_section": "🔋 نظام التخزين", "add_battery": "إضافة بطاريات؟",
        "battery_hours": "ساعات التشغيل الاحتياطي", "calculate": "بدء التحليل الهندسي", "results": "النتائج الفنية",
        "financials": "المؤشرات المالية", "breakdown": "تفاصيل التكلفة الرأسمالية", "ai_opinion": "🤖 رأي الخبير الرقمي",
        "download_pdf": "تحميل التقرير الهندسي (PDF)", "lcoe": "سعر التكلفة المستوي (LCOE)", "autonomy": "الاستقلالية الفعلية",
        "heat_loss": "تم تطبيق معامل الفقد الحراري"
    }
}

# --- القائمة الجانبية ---
with st.sidebar:
    language = st.radio("Language / اللغة", ["العربية", "English"])
    t = translations[language]
    
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
        
        map_output = st_folium(m, height=300, width=280)
        
        if map_output and 'last_active_drawing' in map_output and map_output['last_active_drawing']:
            drawing = map_output['last_active_drawing']
            if drawing['geometry']['type'] == 'Polygon':
                drawn_area = calculate_area_m2(drawing['geometry'])
                st.session_state['calculated_area'] = drawn_area
                st.success(f"{t['area_calc']}: {drawn_area:.2f}")
            elif drawing['geometry']['type'] == 'Point':
                c = drawing['geometry']['coordinates']
                st.session_state['coords'] = (c[1], c[0])

    st.divider()
    
    # 2. الفواتير
    input_method = st.radio(t["input_mode"], [t["mode_seasonal"], t["mode_12m"], t["mode_avg"]])
    monthly_bills = []
    
    if input_method == t["mode_seasonal"]:
        avg_val = st.number_input(t["bill_avg"], value=1500.0, step=100.0)
        # نمط سكني افتراضي (صيف عالي)
        factors = [0.6, 0.7, 0.8, 1.1, 1.4, 1.5, 1.5, 1.5, 1.3, 1.0, 0.8, 0.7]
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
    
    price_kwh = st.number_input("تعرفة الكهرباء (SAR)", value=0.18, format="%.3f")
    cost_kw = st.number_input("سعر النظام (SAR/kW)", value=3000.0)
    
    # 4. البطاريات
    st.markdown("---")
    want_battery = st.checkbox(t["add_battery"])
    batt_cost_unit = 1500.0
    batt_hours = 0
    if want_battery:
        batt_hours = st.slider(t["battery_hours"], 1, 12, 4)
        batt_cost_unit = st.number_input("سعر البطارية (SAR/kWh)", value=1500.0)
    
    run_calc = st.button(t["calculate"], type="primary")

# --- المحرك الرئيسي ---
st.title(PAGE_TITLE)

if run_calc:
    # 1. تحليل الأحمال
    cons_kwh = [b/price_kwh if price_kwh > 0 else 0 for b in monthly_bills]
    total_cons = sum(cons_kwh)
    daily_avg = (total_cons/12)/30
    
    # Sizing
    req_sys = (daily_avg/sun_hours)*1.15
    max_sys = roof_area/7
    final_sys = min(req_sys, max_sys)
    
    panels = int((final_sys*1000)/450)
    if panels < 1: panels = 1
    actual_sys = (panels*450)/1000
    
    # التكاليف
    solar_cost = actual_sys * cost_kw
    batt_size = 0
    batt_cost = 0
    real_autonomy = 0
    
    if want_battery:
        load_hourly = daily_avg / 24
        batt_size = load_hourly * batt_hours
        batt_cost = batt_size * batt_cost_unit
        real_autonomy = batt_size / load_hourly if load_hourly > 0 else 0
        
    total_invest = solar_cost + batt_cost
    
    # 2. المحاكاة الهندسية الدقيقة (Heat Loss & Efficiency)
    # نظام تقييم الخسائر: 20% فواقد (أسلاك، غبار، محولات) + فواقد حرارية في الصيف
    base_efficiency = 0.80 
    
    prod_curve_kwh = []
    total_prod_year = 0
    
    mon_prod_base = actual_sys * sun_hours * 30 * base_efficiency
    
    for i in range(12):
        # معادلة الفقد الحراري (Heat Derating)
        # الصيف (يونيو-سبتمبر) الحرارة عالية => فقدان إضافي 10-15%
        temp_factor = 1.0
        if i in [5, 6, 7, 8]: temp_factor = 0.85 # حرارة عالية
        elif i in [4, 9]: temp_factor = 0.90     # حرارة متوسطة
        
        monthly_gen = mon_prod_base * temp_factor
        prod_curve_kwh.append(monthly_gen)
        total_prod_year += monthly_gen

    # 3. التحليل المالي المتقدم (LCOE & NPV)
    years_range = range(1, 26)
    cash_flow = []
    total_production_lifecycle = 0
    inflation_rate = 0.03
    degradation_rate = 0.005
    current_price_sim = price_kwh
    yearly_prod_sim = total_prod_year
    
    for year in years_range:
        useful_prod = min(yearly_prod_sim, total_cons)
        savings = (useful_prod * current_price_sim) - (total_invest * 0.01) # O&M
        cash_flow.append(savings)
        
        total_production_lifecycle += useful_prod
        
        current_price_sim *= (1 + inflation_rate)
        yearly_prod_sim *= (1 - degradation_rate)
        
    # LCOE = Total Cost / Total Energy Produced
    # تكلفة الصيانة التقريبية طوال العمر
    total_om_lifecycle = (total_invest * 0.01) * 25
    lcoe = (total_invest + total_om_lifecycle) / total_production_lifecycle if total_production_lifecycle > 0 else 0
    
    npv_value = npf.npv(0.05, [-total_invest] + cash_flow)
    payback_years = 0
    cum_cf = []
    curr_cum = -total_invest
    for cf in cash_flow:
        curr_cum += cf
        cum_cf.append(curr_cum)
        
    for i, val in enumerate(cum_cf):
        if val >= 0:
            payback_years = i + 1
            break
            
    roi = ((sum(cash_flow) / total_invest) * 100)

    # --- واجهة النتائج ---
    
    # 1. النتائج الفنية
    st.subheader(t["results"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("حجم النظام (kWp)", f"{actual_sys:.2f}")
    c2.metric("عدد الألواح", f"{panels}")
    c3.metric("الإنتاج السنوي (المتوقع)", f"{int(total_prod_year):,} kWh")
    if want_battery:
        c4.metric("الاستقلالية (Autonomy)", f"{real_autonomy:.1f} Hours")
    else:
        c4.metric("تغطية الاستهلاك", f"{(total_prod_year/total_cons)*100:.0f}%")

    # 2. النتائج المالية
    st.markdown("---")
    st.subheader(t["financials"])
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("التكلفة (CAPEX)", f"{total_invest:,.0f} SAR")
    f2.metric("LCOE (تكلفة الكيلوواط)", f"{lcoe:.3f} SAR/kWh", help="تكلفتك لإنتاج الطاقة مقارنة بـ 0.18 للشركة")
    f3.metric("NPV (القيمة الحالية)", f"{npv_value:,.0f} SAR")
    f4.metric("فترة الاسترداد", f"{payback_years} Years")

    # 3. رأي الخبير
    st.markdown("---")
    st.subheader(t["ai_opinion"])
    
    verdict = ""
    color = "blue"
    if lcoe < 0.10: 
        verdict = f"🌟 **مشروع استثنائي!** تكلفة إنتاجك للطاقة ({lcoe:.3f}) أقل من نصف سعر شركة الكهرباء. هذا المشروع هو 'طابعة نقود' حقيقية."
        color = "green"
    elif lcoe < price_kwh:
        verdict = f"✅ **مشروع رابح.** تكلفة إنتاجك ({lcoe:.3f}) أرخص من الشبكة. العائد الاستثماري {roi:.0f}% ممتاز."
    else:
        verdict = "⚠️ **تنبيه:** تكلفة النظام مرتفعة مقارنة بالتوفير. ينصح بتقليل البطاريات أو التفاوض على سعر النظام."
        color = "red"
        
    if want_battery:
        verdict += f" \n🔋 **ملاحظة:** إضافة البطاريات رفعت التكلفة ولكنها تمنحك أماناً لمدة {real_autonomy:.1f} ساعة."
        
    st.info(verdict, icon="🤖")

    # 4. الرسوم
    st.markdown("---")
    fig = go.Figure()
    months_ar = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
    fig.add_trace(go.Bar(x=months_ar, y=prod_curve_kwh, name='الإنتاج (بعد خصم الحرارة)', marker_color='#FBC02D'))
    fig.add_trace(go.Scatter(x=months_ar, y=cons_kwh, name='الاستهلاك', line=dict(color='#D32F2F', width=3)))
    st.plotly_chart(fig, use_container_width=True)

    # 5. PDF المحسن
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

        # Header Professional
        pdf.set_fill_color(44, 62, 80) # Navy Blue
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(24)
        pdf.cell(190, 15, txt=txt(COMPANY_NAME), ln=True, align='C') 
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt(REPORT_TITLE), ln=True, align='C')
        pdf.ln(20)
        
        pdf.set_text_color(0, 0, 0)
        
        # Helper for colored tables
        def section_title(title):
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font('Amiri', '', 14)
            pdf.cell(190, 10, txt=txt(title), ln=True, fill=True, align='R')
            pdf.ln(2)

        def row(k, v, bold=False):
            pdf.set_font('Amiri', '', 12)
            if bold: pdf.set_text_color(0, 102, 204)
            pdf.cell(120, 8, txt=txt(k), border=1, align='R')
            pdf.cell(70, 8, txt=txt(str(v)), border=1, ln=True, align='C')
            pdf.set_text_color(0, 0, 0)

        # 1. Technical
        section_title("1. المواصفات الفنية والهندسية")
        lat, lng = st.session_state['coords']
        row("إحداثيات الموقع", f"{lat:.5f}, {lng:.5f}" if lat!=0 else "غير محدد")
        row("حجم النظام الكهروضوئي", f"{actual_sys:.2f} kWp", True)
        row("عدد الألواح المطلوبة", f"{panels} Panels")
        row("إنتاج الطاقة السنوي (بعد الفواقد)", f"{int(total_prod_year):,} kWh")
        if want_battery: row("سعة التخزين (البطاريات)", f"{batt_size:.1f} kWh")

        pdf.ln(5)
        
        # 2. Financial
        section_title("2. الجدوى الاقتصادية والاستثمارية")
        row("إجمالي التكلفة الاستثمارية", f"{total_invest:,.0f} SAR", True)
        row("التوفير السنوي المتوقع", f"{cash_flow[0]:,.0f} SAR")
        row("سعر تكلفة الطاقة المستوي (LCOE)", f"{lcoe:.3f} SAR/kWh")
        row("صافي القيمة الحالية (NPV)", f"{npv_value:,.0f} SAR")
        row("فترة استرداد رأس المال", f"{payback_years} Years")

        pdf.ln(10)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(190, 6, txt=txt("ملاحظة: تأخذ هذه الدراسة في الاعتبار فواقد الحرارة في الصيف بنسبة 15%، وفواقد الغبار والكابلات بنسبة 20%، لضمان دقة النتائج."), align='R')

        return pdf.output(dest='S').encode('latin-1')

    st.download_button(t["download_pdf"], create_pdf(), "Engineering_Report.pdf", "application/pdf", type="primary")

else:
    st.info("جاهز للتحليل. الرجاء تحديد الموقع على الخريطة أولاً.")
