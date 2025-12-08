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
# 🏷️ منطقة تعديل العناوين والأسماء (عدل هنا)
# ==========================================
PAGE_TITLE = "النظام الشامل للطاقة الشمسية"
COMPANY_NAME = "شركة حلول الطاقة المتقدمة"
REPORT_TITLE = "عرض فني ومالي - Technical & Financial Proposal"
# ==========================================

st.set_page_config(page_title=PAGE_TITLE, layout="wide", page_icon="☀️")

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

# --- النصوص والترجمة (تم التأكد من جميع المفاتيح) ---
translations = {
    "English": {
        "sidebar_title": "Project Inputs",
        "map_title": "📍 High-Res Site Survey",
        "area_calc": "Drawn Area (m²)",
        "input_mode": "Calculation Method",
        "mode_avg": "Simple Average",
        "mode_seasonal": "Seasonal Simulation (High Accuracy)",
        "mode_12m": "12-Month Exact Bills",
        "consumer_type": "Consumer Type",
        "res": "Residential (High Summer Load)",
        "com": "Commercial (Balanced Load)",
        "bill_avg": "Avg Monthly Bill (SAR)",
        "area": "Usable Roof Area (m²)",
        "cost_per_kw": "System Cost/kW (SAR)",
        "city": "City",
        "battery_section": "🔋 Battery Storage",
        "add_battery": "Add Batteries?",
        "battery_hours": "Backup Hours",
        "calculate": "Run Analysis",
        "results": "Feasibility Analysis",
        "breakdown": "Cost Breakdown",
        "ai_opinion": "🤖 AI Smart Recommendation",
        "download_pdf": "Download Official Report",
        "chart_title": "Load Profile vs Solar Generation",
        "chart_cashflow": "Cumulative Cash Flow",
        "currency": "SAR",
        "panels_count": "Panels",
    },
    "العربية": {
        "sidebar_title": "مدخلات المشروع",
        "map_title": "📍 معاينة الموقع (أقمار صناعية)",
        "area_calc": "المساحة المرسومة (م²)",
        "input_mode": "طريقة الحساب",
        "mode_avg": "متوسط بسيط (سريع)",
        "mode_seasonal": "محاكاة موسمية (دقيق جداً)",
        "mode_12m": "إدخال 12 فاتورة (فعلي)",
        "consumer_type": "نوع النشاط",
        "res": "سكني (تكييف عالي في الصيف)",
        "com": "تجاري (استهلاك متوازن)",
        "bill_avg": "متوسط الفاتورة (ريال)",
        "area": "مساحة السطح (م²)",
        "cost_per_kw": "تكلفة الكيلوواط (ريال)",
        "city": "المدينة",
        "battery_section": "🔋 نظام البطاريات",
        "add_battery": "إضافة بطاريات؟",
        "battery_hours": "ساعات التشغيل الليلي",
        "calculate": "بدء التحليل الشامل",
        "results": "نتائج الدراسة",
        "breakdown": "تفاصيل التكلفة",
        "ai_opinion": "🤖 رأي المستشار الذكي (AI)",
        "download_pdf": "تحميل التقرير الرسمي (PDF)",
        "chart_title": "تحليل الأحمال مقابل الإنتاج الشمسي",
        "chart_cashflow": "تحليل التدفق النقدي التراكمي",
        "currency": "ر.س",
        "panels_count": "لوح",
    }
}

# --- القائمة الجانبية ---
with st.sidebar:
    language = st.radio("Language / اللغة", ["العربية", "English"])
    t = translations[language]
    curr = t["currency"]
    
    st.header(t["sidebar_title"])

    # 1. الخريطة (Google Satellite)
    if 'calculated_area' not in st.session_state: st.session_state['calculated_area'] = 0.0
    if 'coords' not in st.session_state: st.session_state['coords'] = (0.0, 0.0)

    with st.expander(t["map_title"], expanded=True):
        default_location = [24.7136, 46.6753]
        google_tiles = 'http://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}'
        
        m = folium.Map(location=default_location, zoom_start=18, max_zoom=22, tiles=None)
        folium.TileLayer(tiles=google_tiles, attr='Google', name='Google Satellite', overlay=False, control=True).add_to(m)
        Fullscreen().add_to(m)
        
        draw = Draw(
            export=False, position='topleft',
            draw_options={'polyline':False,'rectangle':False,'circle':False,'marker':True,'circlemarker':False,'polygon':True},
            edit_options={'edit': True}
        )
        draw.add_to(m)
        
        st.caption("استخدم 'المضلع' لرسم السطح وتفادي العوائق. اضغط زر ملء الشاشة ↗️")
        map_output = st_folium(m, height=350, width=300)
        
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
    
    # 2. بيانات الفواتير (مع ميزة المحاكاة الموسمية)
    input_method = st.radio(t["input_mode"], [t["mode_seasonal"], t["mode_12m"], t["mode_avg"]])
    monthly_bills = []
    
    if input_method == t["mode_seasonal"]:
        avg_val = st.number_input(t["bill_avg"], value=1500.0, step=100.0)
        cons_type = st.selectbox(t["consumer_type"], [t["res"], t["com"]])
        
        if cons_type == t["res"]:
            factors = [0.6, 0.7, 0.8, 1.1, 1.4, 1.5, 1.5, 1.5, 1.3, 1.0, 0.8, 0.7]
        else:
            factors = [0.9, 0.9, 1.0, 1.0, 1.1, 1.1, 1.1, 1.1, 1.1, 1.0, 0.9, 0.9]
            
        avg_factor = sum(factors) / 12
        monthly_bills = [avg_val * (f / avg_factor) for f in factors]
        
    elif input_method == t["mode_12m"]:
        months = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
        months_display = months if language == "العربية" else ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
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
    roof_area = st.number_input(t["area"], value=float(default_area))
    
    price_kwh = st.number_input("سعر الكيلوواط", value=0.18, format="%.3f")
    cost_kw = st.number_input("تكلفة النظام/kW", value=3000.0)
    
    # 4. البطاريات والتقنية
    st.markdown("---")
    with st.expander("⚙️ إعدادات متقدمة / Advanced"):
        want_battery = st.checkbox(t["add_battery"])
        batt_cost_unit = 1500.0 # Default outside check
        batt_hours = 4 # Default
        if want_battery:
            batt_hours = st.slider(t["battery_hours"], 1, 12, 4)
            batt_cost_unit = st.number_input("تكلفة البطارية (SAR/kWh)", value=1500.0)
        inflation_rate = st.slider("التضخم / Inflation", 0.0, 10.0, 3.0, 0.1) / 100
        degradation_rate = 0.005
        discount_rate = 0.05
    
    run_calc = st.button(t["calculate"], type="primary")

# --- المحرك الرئيسي ---
st.title(PAGE_TITLE)

if run_calc:
    # 1. الحسابات الأساسية
    price_kwh = st.session_state.get("price_kwh", 0.18) # Ensure price_kwh is available
    
    cons_kwh = [b/price_kwh for b in monthly_bills]
    total_cons = sum(cons_kwh)
    daily_avg = (total_cons/12)/30
    
    req_sys = (daily_avg/sun_hours)*1.15
    max_sys = roof_area/7
    final_sys = min(req_sys, max_sys)
    
    panels = int((final_sys*1000)/450)
    if panels < 1: panels = 1
    actual_sys = (panels*450)/1000
    
    # التكاليف
    solar_cost = actual_sys * cost_kw
    batt_cost = 0
    batt_size = 0
    if want_battery:
        load_hourly = daily_avg / 24
        batt_size = load_hourly * batt_hours
        batt_cost = batt_size * batt_cost_unit
    
    total_invest = solar_cost + batt_cost
    
    # 2. المحاكاة الزمنية
    yearly_prod = actual_sys * sun_hours * 365 * 0.9
    savings = min(yearly_prod, total_cons) * price_kwh
    
    roi = ((savings*25 - total_invest)/total_invest)*100
    payback = total_invest/savings if savings > 0 else 25
    
    # المحاكاة لـ 25 سنة (للرسم البياني)
    years_range = range(1, 26)
    cumulative_cash_flow = []
    cumulative_val = -total_invest
    current_price_sim = price_kwh
    yearly_prod_sim = yearly_prod
    
    for year in years_range:
        net_savings = (min(yearly_prod_sim, total_cons) * current_price_sim) - (total_invest * 0.01)
        cumulative_val += net_savings
        cumulative_cash_flow.append(cumulative_val)
        current_price_sim *= (1 + inflation_rate)
        yearly_prod_sim *= (1 - degradation_rate)
    
    # --- العرض ---
    st.subheader(t["results"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("حجم النظام", f"{actual_sys:.2f} kWp")
    c2.metric("عدد الألواح", f"{panels}")
    cost_txt = f"{total_invest:,.0f} ريال"
    if want_battery: cost_txt += " (+Batt)"
    c3.metric("التكلفة الكلية", cost_txt)
    c4.metric("التوفير السنوي", f"{savings:,.0f} ريال")
    
    # --- قسم الذكاء الاصطناعي (AI Opinion) ---
    st.markdown("---")
    st.subheader(t["ai_opinion"])
    
    if roi > 250: advice_text = f"**مشروع ممتاز جداً! (تصنيف A+)** 🚀 العائد الاستثماري يتجاوز {roi:.0f}%، وينصح بالتعاقد الفوري."
    elif roi > 100: advice_text = f"**مشروع مجدي (تصنيف B)** ✅ فترة الاسترداد ({payback:.1f} سنوات) قياسية. ينصح بالتركيز على جودة الألواح."
    else: advice_text = f"**الجدوى منخفضة (تصنيف C)** ⚠️ فترة الاسترداد طويلة ({payback:.1f} سنوات). ينصح بمراجعة الاستهلاك أو تقديم خصم."
        
    st.info(advice_text, icon="🤖")

    st.markdown("---")
    
    # 1. الرسم البياني للاحمال والإنتاج (Fixing the key error here)
    fig = go.Figure()
    months_display = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'] if language == "العربية" else ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    
    prod_monthly = [yearly_prod/12 * (1.1 if i in [2,3,9,10] else 0.95) for i in range(12)]
    
    fig.add_trace(go.Bar(x=months_display, y=prod_monthly, name='إنتاج الطاقة' if language=="العربية" else 'Solar Production', marker_color='#FBC02D'))
    fig.add_trace(go.Scatter(x=months_display, y=cons_kwh, name='استهلاك العميل' if language=="العربية" else 'Client Consumption', line=dict(color='#D32F2F', width=3)))
    
    # Line 276 is now fixed by ensuring 'chart_title' is in 't'
    fig.update_layout(title=t["chart_title"], yaxis_title="kWh") 
    st.plotly_chart(fig, use_container_width=True)
    
    # 2. الرسم البياني للتدفق النقدي
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=list(years_range), y=cumulative_cash_flow, fill='tozeroy', name='Cumulative Savings' if language=="English" else 'التوفير التراكمي', line=dict(color='#2E7D32')))
    fig2.update_layout(title=t["chart_cashflow"], xaxis_title="Year", yaxis_title="SAR" if language=="English" else "ريال", height=400)
    fig2.add_hline(y=0, line_dash="dash", line_color="red")
    st.plotly_chart(fig2, use_container_width=True)

    # تفصيل السعر
    st.subheader(t["breakdown"])
    breakdown = pd.DataFrame({
        "البند": ["الألواح الشمسية", "العواكس (Inverters)", "الهيكل والتركيب", "البطاريات"],
        "التكلفة (ريال)": [f"{solar_cost*0.45:,.0f}", f"{solar_cost*0.15:,.0f}", f"{solar_cost*0.40:,.0f}", f"{batt_cost:,.0f}"]
    })
    st.table(breakdown)
    
    # --- PDF ---
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
        pdf.set_fill_color(30, 30, 30)
        pdf.rect(0, 0, 210, 35, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(20)
        pdf.cell(190, 15, txt=txt(COMPANY_NAME), ln=True, align='C') 
        pdf.set_font_size(12)
        pdf.cell(190, 8, txt=txt(REPORT_TITLE), ln=True, align='C')
        pdf.ln(15)
        
        pdf.set_text_color(0, 0, 0)
        
        def row(k, v):
            pdf.cell(100, 8, txt=txt(k), border=1, align='R')
            pdf.cell(90, 8, txt=txt(str(v)), border=1, ln=True, align='C')
            
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(190, 8, txt=txt("ملخص الدراسة"), ln=True, fill=True, align='R')
        
        lat, lng = st.session_state['coords']
        loc_str = f"{lat:.5f}, {lng:.5f}" if lat!=0 else "غير محدد"
        
        row("الموقع والإحداثيات", f"{location_key} ({loc_str})")
        row("إجمالي الاستهلاك السنوي", f"{int(total_cons):,} kWh")
        row("حجم النظام المقترح", f"{actual_sys:.2f} kWp")
        row("التكلفة الاستثمارية", f"{total_invest:,.0f} SAR")
        row("التوفير السنوي المتوقع", f"{savings:,.0f} SAR")
        row("فترة استرداد رأس المال", f"{payback:.1f} Years")
        
        if want_battery: row("نظام البطاريات", f"{batt_size:.1f} kWh")

        pdf.ln(5)
        # إضافة توصية الذكاء الاصطناعي للتقرير
        pdf.set_text_color(0, 100, 0)
        recomm = f"توصية النظام الذكي: هذا المشروع يحقق عائداً استثمارياً بنسبة {roi:.0f}%، وينصح بتنفيذه."
        pdf.multi_cell(190, 8, txt=txt(recomm), border=1, align='R')
        
        return pdf.output(dest='S').encode('latin-1')

    st.download_button(t["download_pdf"], create_pdf(), "Solar_Report.pdf", "application/pdf", type="primary")

else:
    st.info("System Ready. Draw roof area on map and enter data.")
