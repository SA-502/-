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
PAGE_TITLE = "نظام الطاقة الشمسية (SEC Exact)"
COMPANY_NAME = "شركة حلول الطاقة المتقدمة"
REPORT_TITLE = "عرض فني ومالي - SEC Tariff Logic"
# ==========================================

st.set_page_config(page_title=PAGE_TITLE, layout="wide", page_icon="⚡")

# --- ثوابت التعرفة السعودية (SEC) ---
# الأسعار بدون ضريبة
BASE_RATE_T1 = 0.18
BASE_RATE_T2 = 0.30
METER_FEE_BASE = 10.0 # رسوم العداد

# الضريبة
VAT = 0.15

# الأسعار شاملة الضريبة (للحساب السريع)
RATE_T1_VAT = BASE_RATE_T1 * (1 + VAT) # 0.207
RATE_T2_VAT = BASE_RATE_T2 * (1 + VAT) # 0.345
METER_FEE_VAT = METER_FEE_BASE * (1 + VAT) # 11.5

# حد الشريحة الأولى (6000 واط)
TIER1_LIMIT_KWH = 6000
TIER1_COST_VAT = TIER1_LIMIT_KWH * RATE_T1_VAT # 1242 ريال تكلفة أول 6000

# --- دوال مساعدة ---
def fmt(num):
    return f"{int(num):,}"

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

# 🔥 محرك العكسي: من فاتورة (ريال) إلى استهلاك (كيلوواط) 🔥
def get_kwh_from_bill_exact(bill_sar_with_vat):
    # 1. خصم رسوم العداد أولاً
    bill_energy_only = bill_sar_with_vat - METER_FEE_VAT
    
    if bill_energy_only <= 0: return 0
    
    # 2. حساب الكيلوواط بناءً على الشرائح
    if bill_energy_only <= TIER1_COST_VAT:
        # العميل في الشريحة الأولى فقط
        return bill_energy_only / RATE_T1_VAT
    else:
        # العميل دخل الشريحة الثانية
        remainder_money = bill_energy_only - TIER1_COST_VAT
        kwh_tier2 = remainder_money / RATE_T2_VAT
        return TIER1_LIMIT_KWH + kwh_tier2

# 🔥 محرك الأمامي: من استهلاك (كيلوواط) إلى فاتورة (ريال) 🔥
def calculate_bill_sar_exact(kwh):
    energy_cost = 0
    if kwh <= TIER1_LIMIT_KWH:
        energy_cost = kwh * RATE_T1_VAT
    else:
        energy_cost = (TIER1_LIMIT_KWH * RATE_T1_VAT) + ((kwh - TIER1_LIMIT_KWH) * RATE_T2_VAT)
    
    return energy_cost + METER_FEE_VAT # إعادة إضافة رسوم العداد

# --- النصوص ---
translations = {
    "English": {
        "sidebar_title": "Project Inputs", "map_title": "📍 Site Survey", "area_calc": "Area (m²)",
        "input_mode": "Bill Input", "mode_12m": "12-Month Bills", "mode_avg": "Average Bill",
        "bill_avg": "Avg Bill (SAR - Inc VAT)", "area": "Roof Area (m²)", "panel_type": "Panel Type",
        "city": "City", "battery_section": "🔋 Storage & Finance", "add_battery": "Batteries?", "add_finance": "Finance?",
        "battery_hours": "Backup Hours", "calculate": "Run Analysis", "results": "Results", 
        "breakdown": "Cost Breakdown", "ai_opinion": "🤖 Smart Analysis", "download_pdf": "Download PDF", 
        "chart_title": "Consumption vs Production", "chart_cashflow": "Cash Flow", "currency": "SAR", 
        "panels_count": "Panels", "finance_years": "Years", "interest": "Interest %", "monthly_inst": "Installment",
        "vat_note": "Calculations include 15% VAT & Meter Fee"
    },
    "العربية": {
        "sidebar_title": "مدخلات المشروع", "map_title": "📍 معاينة الموقع (أقمار صناعية)", "area_calc": "المساحة المرسومة (م²)",
        "input_mode": "طريقة إدخال الفواتير", "mode_12m": "إدخال 12 فاتورة (دقيق)", "mode_avg": "متوسط الفاتورة (تقديري)",
        "bill_avg": "متوسط الفاتورة (شامل الضريبة)", "area": "مساحة السطح (م²)", "panel_type": "نوع الألواح",
        "city": "المدينة", "battery_section": "🔋 التخزين والتمويل", "add_battery": "إضافة بطاريات؟", "add_finance": "تمويل بنكي؟",
        "battery_hours": "ساعات التشغيل الليلي", "calculate": "بدء التحليل الشامل", "results": "نتائج الدراسة", 
        "breakdown": "تفاصيل التكلفة", "ai_opinion": "🤖 رأي المستشار الذكي", "download_pdf": "تحميل التقرير الرسمي (PDF)", 
        "chart_title": "تحليل الأحمال مقابل الإنتاج", "chart_cashflow": "تحليل التدفق النقدي", "currency": "ر.س", 
        "panels_count": "لوح", "finance_years": "مدة التمويل (سنوات)", "interest": "نسبة الفائدة (%)", "monthly_inst": "القسط الشهري",
        "vat_note": "* دقة عالية: خصم رسوم العداد (11.5 ريال) وحساب الضريبة 15%."
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
        map_output = st_folium(m, height=300, width=280)
        
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
    input_method = st.radio(t["input_mode"], [t["mode_12m"], t["mode_avg"]])
    monthly_bills_sar = []
    
    if input_method == t["mode_12m"]:
        months_display = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'] if language == "العربية" else ['Jan','Feb','...']
        cols = st.columns(3)
        for i, m in enumerate(months_display):
            with cols[i%3]:
                def_val = 2000.0 if i in [5,6,7,8] else 800.0
                val = st.number_input(m, value=def_val, key=i)
                monthly_bills_sar.append(val)
    else: 
        avg_val = st.number_input(t["bill_avg"], value=1500.0, step=100.0)
        factors = [0.6, 0.7, 0.8, 1.1, 1.4, 1.5, 1.5, 1.5, 1.3, 1.0, 0.8, 0.7]
        avg_factor = sum(factors) / 12
        monthly_bills_sar = [avg_val * (f / avg_factor) for f in factors]

    # --- لوحة التحقق من الحسابات (Debug Panel) ---
    with st.expander("🔍 تحقق من دقة الحسابات (Debug)", expanded=False):
        st.caption("هنا نوضح كيف تم تحويل الريال إلى كيلوواط:")
        test_bill = monthly_bills_sar[0]
        test_kwh = get_kwh_from_bill_exact(test_bill)
        st.write(f"مثال (يناير): فاتورة {test_bill:,.0f} ريال")
        st.write(f"- خصم رسوم العداد: {test_bill} - 11.5 = {test_bill-11.5:.1f} ريال")
        st.write(f"- تحويل إلى كيلوواط: {int(test_kwh):,} kWh")

    # 3. المواصفات
    saudi_cities = {"الرياض":5.8, "جدة":6.0, "الدمام":5.6, "مكة":6.2, "المدينة":6.3, "أبها":5.9, "تبوك":6.1, "حائل":6.0, "جازان":5.9, "القصيم":5.8}
    location_key = st.selectbox(t["city"], list(saudi_cities.keys()))
    sun_hours = saudi_cities[location_key]
    
    default_area = st.session_state['calculated_area'] if st.session_state['calculated_area'] > 0 else 300.0
    roof_area = st.number_input(t["area"], value=float(default_area))
    
    panel_options = { "Jinko Tiger Pro 545W": 545, "Longi Hi-MO 5 550W": 550, "Trina Vertex 550W": 550, "Generic 450W": 450 }
    panel_choice = st.selectbox(t["panel_type"], list(panel_options.keys()))
    panel_wattage = panel_options[panel_choice]
    
    cost_kw = st.number_input("سعر النظام (SAR/kW)", value=3000.0)
    
    # 4. التخزين والتمويل
    st.markdown("---")
    with st.expander(t["battery_section"], expanded=True):
        want_battery = st.checkbox(t["add_battery"])
        batt_cost_unit = 1500.0
        batt_hours = 0
        if want_battery:
            batt_hours = st.slider(t["battery_hours"], 1, 12, 4)
            batt_cost_unit = st.number_input("سعر البطارية (SAR/kWh)", value=1500.0)
            
        want_finance = st.checkbox(t["add_finance"])
        finance_years = 5
        interest_rate = 3.5
        if want_finance:
            finance_years = st.slider(t["finance_years"], 1, 10, 5)
            interest_rate = st.number_input(t["interest"], value=3.5)

    st.caption(t["vat_note"])
    run_calc = st.button(t["calculate"], type="primary")

# --- المحرك الرئيسي ---
st.title(PAGE_TITLE)

if run_calc:
    # 1. تحليل الأحمال (دقيق جداً)
    cons_kwh = [get_kwh_from_bill_exact(b) for b in monthly_bills_sar]
    total_cons_kwh = sum(cons_kwh)
    daily_avg_kwh = (total_cons_kwh/12)/30
    
    # Sizing
    req_sys = (daily_avg_kwh/sun_hours)*1.15
    max_sys = roof_area/7
    final_sys = min(req_sys, max_sys)
    
    panels = int((final_sys*1000)/panel_wattage)
    if panels < 1: panels = 1
    actual_sys = (panels*panel_wattage)/1000
    
    # التكاليف
    solar_cost = actual_sys * cost_kw
    batt_size = 0
    batt_cost = 0
    if want_battery:
        load_hourly = daily_avg_kwh / 24
        batt_size = load_hourly * batt_hours
        batt_cost = batt_size * batt_cost_unit
    
    total_invest = solar_cost + batt_cost
    
    # التمويل
    monthly_installment = 0
    total_finance_cost = total_invest
    if want_finance:
        r = (interest_rate / 100) / 12
        n = finance_years * 12
        if r > 0: monthly_installment = total_invest * (r * (1 + r)**n) / ((1 + r)**n - 1)
        else: monthly_installment = total_invest / n
        total_finance_cost = monthly_installment * n

    # 2. المحاكاة
    prod_curve_kwh = []
    total_prod_year = 0
    mon_prod_base = actual_sys * sun_hours * 30 * 0.80 
    
    for i in range(12):
        temp_factor = 0.85 if i in [5, 6, 7, 8] else 1.0 
        monthly_gen = mon_prod_base * temp_factor
        prod_curve_kwh.append(monthly_gen)
        total_prod_year += monthly_gen

    # حساب التوفير المالي (الفرق في الفاتورة النهائية)
    total_bill_before = sum(monthly_bills_sar)
    total_bill_after = 0
    
    for i in range(12):
        # الاستهلاك الجديد = القديم - الطاقة الشمسية
        # إذا كان بالسالب (تصدير)، نحسبه صفر لأن العدادات الحديثة لا ترجع للخلف (صافي قياس يحتاج إجراءات أخرى، نفترض استهلاك ذاتي)
        net_cons = max(0, cons_kwh[i] - prod_curve_kwh[i])
        total_bill_after += calculate_bill_sar_exact(net_cons)
        
    annual_savings_y1 = total_bill_before - total_bill_after
    
    # التحليل المالي
    years_range = range(1, 26)
    cash_flow = []
    cumulative_cash_flow = []
    cumulative_val = -total_invest if not want_finance else 0 
    
    inflation_rate = 0.03
    degradation_rate = 0.005
    current_savings_sim = annual_savings_y1
    
    for year in years_range:
        yearly_outflow = (monthly_installment * 12) if (want_finance and year <= finance_years) else 0
        net_cash = current_savings_sim - (total_invest * 0.01) - yearly_outflow
        cash_flow.append(net_cash)
        cumulative_val += net_cash
        cumulative_cash_flow.append(cumulative_val)
        current_savings_sim *= (1 + inflation_rate)

    roi = ((sum(cash_flow) / (total_finance_cost if want_finance else total_invest)) * 100)
    payback_years = 0
    for i, val in enumerate(cumulative_cash_flow):
        if val >= 0:
            payback_years = i + 1
            break
    if payback_years == 0: payback_years = 25
    
    npv_value = npf.npv(0.05, [-total_invest if not want_finance else 0] + cash_flow)

    # --- النتائج ---
    st.subheader(t["results"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("حجم النظام (kWp)", f"{actual_sys:.2f}")
    c2.metric("عدد الألواح", f"{panels}", f"{panel_choice.split()[0]}")
    c3.metric("التكلفة (كاش)", f"{fmt(total_invest)} {curr}")
    c4.metric("التوفير السنوي (فعلي)", f"{fmt(annual_savings_y1)} {curr}", help="تم حساب الشرائح بدقة عالية")
    
    if want_finance:
        st.markdown("---")
        st.markdown(f"##### 🏦 **تحليل التمويل ({finance_years} سنوات)**")
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("القسط الشهري", f"{fmt(monthly_installment)} {curr}", delta_color="inverse")
        monthly_save = annual_savings_y1 / 12
        fc2.metric("متوسط التوفير الشهري", f"{fmt(monthly_save)} {curr}")
        diff = monthly_save - monthly_installment
        fc3.metric("صافي التدفق الشهري", f"{fmt(diff)} {curr}", delta=("إيجابي" if diff > 0 else "سلبي"), delta_color="normal")

    st.markdown("---")
    f1, f2, f3 = st.columns(3)
    f1.metric("العائد (ROI)", f"{int(roi)}%")
    f2.metric("الاسترداد (Payback)", f"{payback_years} Years")
    f3.metric("صافي القيمة (NPV)", f"{fmt(npv_value)} {curr}")

    # --- الذكاء الاصطناعي ---
    st.markdown("---")
    st.subheader(t["ai_opinion"])
    
    tier2_usage = any(k > 6000 for k in cons_kwh)
    
    advice = ""
    if tier2_usage:
        advice = f"🚀 **فرصة ممتازة (A+):** العميل يستهلك في الشريحة الثانية (34 هللة)، مما يجعل التوفير مضاعفاً! الاسترداد سريع ({payback_years} سنوات)."
    elif want_finance and monthly_installment < (annual_savings_y1/12):
        advice = f"💎 **تدفق إيجابي:** القسط البنكي أقل من التوفير، العميل يربح كاش فوراً."
    else:
        advice = f"✅ **مشروع جيد:** النظام يغطي الاستهلاك بسعر الشريحة الأولى (20 هللة). استثمار آمن طويل الأمد."
        
    st.info(advice, icon="🤖")

    # --- الرسوم البيانية ---
    st.markdown("---")
    fig = go.Figure()
    months_ar = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
    fig.add_trace(go.Bar(x=months_ar, y=prod_curve_kwh, name='الإنتاج الشمسي', marker_color='#FBC02D'))
    fig.add_trace(go.Scatter(x=months_ar, y=cons_kwh, name='استهلاك العميل', line=dict(color='#D32F2F', width=3)))
    fig.update_layout(title=t["chart_title"], yaxis_title="kWh")
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

        pdf.set_fill_color(230, 230, 230)
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt("1. المواصفات الفنية"), ln=True, fill=True, align='R')
        pdf.set_font_size(12)
        
        lat, lng = st.session_state['coords']
        loc_str = f"{lat:.5f}, {lng:.5f}" if lat!=0 else "-"
        row("الموقع والإحداثيات", f"{location_key} ({loc_str})")
        row("حجم النظام المقترح", f"{actual_sys:.2f} kWp")
        row("موديل الألواح", f"{panel_choice}")
        row("إجمالي الاستهلاك السنوي", f"{fmt(total_cons_kwh)} kWh")
        row("الإنتاج المتوقع (السنة 1)", f"{fmt(total_prod_year)} kWh")
        pdf.ln(5)

        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt("2. التحليل المالي (شامل 15% ضريبة)"), ln=True, fill=True, align='R')
        pdf.set_font_size(12)
        row("إجمالي التكلفة (CAPEX)", f"{fmt(total_invest)} {curr}")
        row("التوفير السنوي (Year 1)", f"{fmt(annual_savings_y1)} {curr}")
        row("صافي القيمة الحالية (NPV)", f"{fmt(npv_value)} {curr}")
        row("فترة استرداد رأس المال", f"{payback_years:.1f} Years")
        
        if want_finance:
            pdf.ln(5)
            pdf.set_font_size(14)
            pdf.cell(190, 10, txt=txt("3. خيار التمويل البنكي"), ln=True, fill=True, align='R')
            pdf.set_font_size(12)
            row("القسط الشهري", f"{fmt(monthly_installment)} {curr}")
            row("صافي التدفق الشهري", f"{fmt(monthly_save - monthly_installment)} {curr}")

        pdf.ln(10)
        clean_advice = advice.replace('🚀', '').replace('✅', '').replace('💎', '').replace('🤖', '').replace('**', '')
        pdf.set_text_color(0, 100, 0)
        pdf.multi_cell(190, 6, txt=txt("توصية المستشار: " + clean_advice), border=1, align='R')

        return pdf.output(dest='S').encode('latin-1')

    st.download_button(t["download_pdf"], create_pdf(), "Solar_Report.pdf", "application/pdf", type="primary")

else:
    st.info("النظام جاهز. الرجاء تحديد الموقع على الخريطة.")
