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
PAGE_TITLE = "النظام الذكي للطاقة الشمسية"
COMPANY_NAME = "شركة حلول الطاقة المتقدمة"
REPORT_TITLE = "عرض فني ومالي - Technical Proposal"
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

# --- النصوص والترجمة ---
translations = {
    "English": {
        "sidebar_title": "Client Inputs",
        "map_title": "📍 High-Res Site Survey",
        "area_calc": "Drawn Area (m²)",
        "input_mode": "Bill Input Method",
        "mode_12m": "12-Month Bills (Exact)",
        "mode_avg": "Average Bill (Simple)",
        "bill_avg": "Avg Monthly Bill (SAR)",
        "area": "Usable Roof Area (m²)",
        "city": "City",
        "calculate": "Analyze Project",
        "results": "Project Analysis",
        "breakdown": "Cost Breakdown",
        "ai_opinion": "🤖 AI Smart Recommendation",
        "download_pdf": "Download Official Report"
    },
    "العربية": {
        "sidebar_title": "بيانات العميل",
        "map_title": "📍 معاينة الموقع (أقمار صناعية دقيقة)",
        "area_calc": "المساحة المرسومة (م²)",
        "input_mode": "طريقة إدخال الفواتير",
        "mode_12m": "فواتير 12 شهر (دقيق)",
        "mode_avg": "متوسط الفاتورة (سريع)",
        "bill_avg": "متوسط الفاتورة الشهرية (ريال)",
        "area": "مساحة السطح الصافية (م²)",
        "city": "المدينة",
        "calculate": "بدء التحليل الشامل",
        "results": "نتائج الدراسة",
        "breakdown": "تفاصيل التكلفة",
        "ai_opinion": "🤖 رأي المستشار الذكي (AI)",
        "download_pdf": "تحميل التقرير الرسمي (PDF)"
    }
}

# --- القائمة الجانبية ---
with st.sidebar:
    language = st.radio("Language / اللغة", ["العربية", "English"])
    t = translations[language]
    
    st.header(t["sidebar_title"])

    # --- خريطة جوجل عالية الدقة (Google Satellite Hybrid) ---
    if 'calculated_area' not in st.session_state: st.session_state['calculated_area'] = 0.0
    if 'coords' not in st.session_state: st.session_state['coords'] = (0.0, 0.0)

    with st.expander(t["map_title"], expanded=True):
        default_location = [24.7136, 46.6753] # الرياض
        
        # استخدام رابط خرائط جوجل الأصلي (يسمح بزووم عالي)
        google_tiles = 'http://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}'
        
        m = folium.Map(location=default_location, zoom_start=18, max_zoom=22, tiles=None)
        folium.TileLayer(
            tiles=google_tiles,
            attr='Google',
            name='Google Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        Fullscreen().add_to(m)
        
        draw = Draw(
            export=False,
            position='topleft',
            draw_options={'polyline':False,'rectangle':False,'circle':False,'marker':True,'circlemarker':False,'polygon':True},
            edit_options={'edit': True}
        )
        draw.add_to(m)
        
        st.caption("استخدم 'المضلع' (الخماسي) لرسم السطح بدقة وتفادي العوائق.")
        map_output = st_folium(m, height=400, width=300)
        
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
    
    # المدخلات
    saudi_cities = {"الرياض":5.8, "جدة":6.0, "الدمام":5.6, "مكة":6.2, "المدينة":6.3, "أبها":5.9, "تبوك":6.1, "حائل":6.0, "جازان":5.9, "القصيم":5.8}
    location_key = st.selectbox(t["city"], list(saudi_cities.keys()))
    sun_hours = saudi_cities[location_key]
    
    # المساحة من الخريطة
    default_area = st.session_state['calculated_area'] if st.session_state['calculated_area'] > 0 else 300.0
    roof_area = st.number_input(t["area"], value=float(default_area))
    
    # الفواتير
    input_method = st.radio(t["input_mode"], [t["mode_12m"], t["mode_avg"]])
    monthly_bills = []
    if input_method == t["mode_12m"]:
        months = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
        cols = st.columns(3)
        for i, m in enumerate(months):
            with cols[i%3]:
                val = st.number_input(m, value=(2000.0 if i in [5,6,7,8] else 800.0), key=i)
                monthly_bills.append(val)
    else:
        val = st.number_input(t["bill_avg"], value=1500.0)
        monthly_bills = [val]*12
        
    price_kwh = st.number_input("سعر الكيلوواط", value=0.18, format="%.3f")
    cost_kw = st.number_input("تكلفة النظام/kW", value=3000.0)
    
    run_calc = st.button(t["calculate"], type="primary")

# --- المحرك الرئيسي ---
st.title(PAGE_TITLE)

if run_calc:
    # الحسابات
    cons_kwh = [b/price_kwh for b in monthly_bills]
    total_cons = sum(cons_kwh)
    daily_avg = (total_cons/12)/30
    
    req_sys = (daily_avg/sun_hours)*1.1
    max_sys = roof_area/7
    final_sys = min(req_sys, max_sys)
    
    panels = int((final_sys*1000)/450)
    if panels < 1: panels = 1
    actual_sys = (panels*450)/1000
    
    investment = actual_sys * cost_kw
    yearly_prod = actual_sys * sun_hours * 365 * 0.9
    savings = min(yearly_prod, total_cons) * price_kwh
    roi = ((savings*25 - investment)/investment)*100
    payback = investment/savings if savings > 0 else 25
    
    # --- العرض ---
    st.subheader(t["results"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("حجم النظام", f"{actual_system_kw:.2f} kWp" if 'actual_system_kw' in locals() else f"{actual_sys:.2f} kWp")
    c2.metric("عدد الألواح", f"{panels}")
    c3.metric("التكلفة", f"{investment:,.0f} ريال")
    c4.metric("التوفير السنوي", f"{savings:,.0f} ريال")
    
    # --- قسم الذكاء الاصطناعي (Simulation) ---
    st.markdown("---")
    st.subheader(t["ai_opinion"])
    
    # منطق بسيط يحاكي تحليل الذكاء الاصطناعي
    advice_color = "green"
    advice_text = ""
    
    if roi > 400:
        advice_text = f"""
        **تحليل استثماري ممتاز!** 🚀
        بناءً على البيانات، هذا المشروع يعتبر **فرصة ذهبية**. العائد الاستثماري يتجاوز {roi:.0f}% وهو أعلى بكثير من العقار أو الأسهم.
        - **نقطة القوة:** استهلاك العميل مرتفع وسعر النظام مناسب جداً.
        - **التوصية:** اغلق الصفقة فوراً، العميل سيسترد ماله في {payback:.1f} سنوات فقط.
        """
    elif roi > 100:
        advice_text = f"""
        **مشروع مجدي اقتصادياً** ✅
        النظام يغطي الاحتياج بشكل جيد. فترة الاسترداد ({payback:.1f} سنوات) تعتبر قياسية في السوق السعودي.
        - **نصيحة للمبيعات:** ركز مع العميل على توفير الفواتير الصيفية، حيث سيلمس الفرق الأكبر.
        """
        advice_color = "blue"
    else:
        advice_text = f"""
        **تنبيه: الجدوى منخفضة** ⚠️
        فترة الاسترداد طويلة ({payback:.1f} سنوات). قد يكون استهلاك العميل قليل جداً أو سعر النظام مرتفع.
        - **الحل:** حاول تقليل حجم النظام ليغطي فقط الشريحة العليا من الاستهلاك، أو قدم خصماً لزيادة الجاذبية.
        """
        advice_color = "orange"
        
    st.info(advice_text, icon="🤖")

    st.markdown("---")
    
    # الرسم البياني
    fig = go.Figure()
    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    # توزيع الإنتاج (تقريبي)
    prod_monthly = [yearly_prod/12 * (1.1 if i in [2,3,9,10] else 0.95) for i in range(12)]
    
    fig.add_trace(go.Bar(x=months, y=prod_monthly, name='إنتاج الطاقة', marker_color='#FBC02D'))
    fig.add_trace(go.Scatter(x=months, y=cons_kwh, name='استهلاك العميل', line=dict(color='#D32F2F', width=3)))
    st.plotly_chart(fig, use_container_width=True)
    
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
        pdf.cell(190, 15, txt=txt(COMPANY_NAME), ln=True, align='C') # اسم الشركة المتغير
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
        row("التكلفة الاستثمارية", f"{investment:,.0f} SAR")
        row("التوفير السنوي المتوقع", f"{savings:,.0f} SAR")
        row("فترة استرداد رأس المال", f"{payback:.1f} Years")
        
        pdf.ln(5)
        # إضافة توصية الذكاء الاصطناعي للتقرير
        pdf.set_text_color(0, 100, 0)
        pdf.multi_cell(190, 8, txt=txt(f"توصية المستشار الذكي: هذا المشروع يحقق عائداً استثمارياً بنسبة {roi:.0f}%، وينصح بتنفيذه نظراً لارتفاع استهلاك العميل وملاءمة مساحة السطح."), border=1, align='R')
        
        return pdf.output(dest='S').encode('latin-1')

    st.download_button(t["download_pdf"], create_pdf(), "Solar_Report.pdf", "application/pdf", type="primary")
