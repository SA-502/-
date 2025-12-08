import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
import numpy_financial as npf
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from shapely.geometry import shape
import math

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Solar Engineering Tool", layout="wide", page_icon="🛰️")

# --- دالة حساب المساحة ---
def calculate_area_m2(geojson_geometry):
    if geojson_geometry is None:
        return 0.0
    geom = shape(geojson_geometry)
    center_lat = geom.centroid.y
    lat_to_m = 111132.92
    lon_to_m = 40075000 * math.cos(math.radians(center_lat)) / 360
    new_coords = []
    if geom.geom_type == 'Polygon':
        coords = list(geom.exterior.coords)
        for x, y in coords:
            new_coords.append((x * lon_to_m, y * lat_to_m))
    else:
        return 0.0
    from shapely.geometry import Polygon
    poly_m = Polygon(new_coords)
    return poly_m.area

# --- النصوص والترجمة ---
translations = {
    "English": {
        "title": "⚡ Solar Sales & Engineering Tool (Satellite)",
        "sidebar_title": "Client Data Entry",
        "map_title": "📍 Site Survey (Satellite View)",
        "coords": "Selected Coordinates",
        "area_calc": "Calculated Roof Area",
        "input_mode": "Input Method",
        "mode_avg": "Simple Average Bill",
        "mode_12m": "Detailed 12-Month Bills",
        "bill_avg": "Average Monthly Bill (SAR)",
        "area": "Roof Area (m²)",
        "cost_per_kw": "System Cost/kW (SAR)",
        "city": "Region / City",
        "price_kwh": "Tariff Rate (SAR/kWh)",
        "inflation": "Electricity Inflation (%)",
        "degradation": "Panel Degradation (%)",
        "battery_section": "🔋 Storage / Off-grid Options",
        "add_battery": "Include Batteries?",
        "battery_hours": "Backup Hours",
        "battery_cost": "Battery Cost (SAR/kWh)",
        "calculate": "Run Analysis",
        "results": "Technical & Financial Analysis",
        "breakdown": "Cost Breakdown (Internal)",
        "system_size": "Proposed System Size",
        "panels": "Panels Qty (450W)",
        "cost": "Total CAPEX",
        "savings": "Annual Savings (Year 1)",
        "roi": "ROI (25 Years)",
        "payback": "Payback Period",
        "npv": "NPV (Project Value)",
        "co2": "CO2 Avoided",
        "chart_title": "Load Profile vs Solar Generation",
        "chart_cashflow": "Cumulative Cash Flow",
        "download_pdf": "Export Client Report (PDF)",
        "currency": "SAR",
        "panels_count": "Panels",
        "rec_title": "System Specifications"
    },
    "العربية": {
        "title": "⚡ نظام مبيعات وهندسة الطاقة الشمسية (أقمار صناعية)",
        "sidebar_title": "إدخال بيانات العميل",
        "map_title": "📍 معاينة الموقع (صور فضائية)",
        "coords": "الإحداثيات المختارة",
        "area_calc": "مساحة الرسم المحسوبة",
        "input_mode": "طريقة الإدخال",
        "mode_avg": "فاتورة متوسطة (تقريبي)",
        "mode_12m": "فواتير 12 شهر (دقيق)",
        "bill_avg": "متوسط الفاتورة (ريال)",
        "area": "المساحة المتاحة (م²)",
        "cost_per_kw": "تكلفة الكيلوواط (ريال)",
        "city": "المنطقة / المدينة",
        "price_kwh": "سعر الشريحة (ريال/kWh)",
        "inflation": "التضخم المتوقع (%)",
        "degradation": "تناقص الألواح (%)",
        "battery_section": "🔋 خيارات البطاريات",
        "add_battery": "إضافة بطاريات للنظام؟",
        "battery_hours": "ساعات التخزين المطلوبة",
        "battery_cost": "تكلفة البطارية (ريال/kWh)",
        "calculate": "إجراء التحليل",
        "results": "التحليل الفني والمالي",
        "breakdown": "تفاصيل التكلفة (داخلي)",
        "system_size": "حجم المحطة المقترح",
        "panels": "عدد الألواح (450W)",
        "cost": "التكلفة الرأسمالية (CAPEX)",
        "savings": "التوفير (السنة الأولى)",
        "roi": "العائد الاستثماري (ROI)",
        "payback": "فترة الاسترداد",
        "npv": "صافي القيمة الحالية (NPV)",
        "co2": "توفير الكربون",
        "chart_title": "تحليل الأحمال مقابل الإنتاج",
        "chart_cashflow": "التدفق النقدي التراكمي",
        "download_pdf": "تصدير تقرير العميل (PDF)",
        "currency": "ر.س",
        "panels_count": "لوح",
        "rec_title": "مواصفات النظام المقترح"
    }
}

# --- القائمة الجانبية ---
with st.sidebar:
    language = st.radio("Language / اللغة", ["العربية", "English"])
    t = translations[language]
    curr = t["currency"]
    
    st.header(t["sidebar_title"])

    # --- خريطة الأقمار الصناعية (Satellite Map) ---
    if 'calculated_area' not in st.session_state:
        st.session_state['calculated_area'] = 0.0
    if 'coords' not in st.session_state:
        st.session_state['coords'] = (0.0, 0.0)

    with st.expander(t["map_title"], expanded=True):
        default_location = [24.7136, 46.6753] # الرياض
        
        # استخدام Esri World Imagery (صور أقمار صناعية عالية الدقة)
        m = folium.Map(location=default_location, zoom_start=18, max_zoom=21)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Esri Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        # إضافة خيار التبديل لأسماء الشوارع (Hybrid) إن أمكن أو الاكتفاء بالساتلايت
        
        draw = Draw(
            export=False,
            position='topleft',
            draw_options={'polyline': False, 'circle': False, 'marker': True, 'circlemarker': False, 'polygon': True},
            edit_options={'edit': True}
        )
        draw.add_to(m)
        
        map_output = st_folium(m, height=400, width=280)
        
        drawn_area = 0.0
        if map_output and 'last_active_drawing' in map_output and map_output['last_active_drawing']:
            drawing = map_output['last_active_drawing']
            geometry = drawing['geometry']
            
            if geometry['type'] == 'Polygon':
                drawn_area = calculate_area_m2(geometry)
                st.session_state['calculated_area'] = drawn_area
                st.success(f"{t['area_calc']}: {drawn_area:.2f} m²")
            elif geometry['type'] == 'Point':
                coords = geometry['coordinates']
                st.session_state['coords'] = (coords[1], coords[0])
                st.info(f"{t['coords']}: {coords[1]:.4f}, {coords[0]:.4f}")

    st.divider()
    
    input_method = st.radio(t["input_mode"], [t["mode_12m"], t["mode_avg"]])
    monthly_bills_input = []
    
    if input_method == t["mode_12m"]:
        months_en = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        months_ar = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
        months_labels = months_ar if language == "العربية" else months_en
        cols = st.columns(3)
        for i, m_label in enumerate(months_labels):
            with cols[i % 3]:
                default_val = 2000.0 if i in [5,6,7,8] else 800.0
                val = st.number_input(f"{m_label}", min_value=0.0, value=default_val, key=f"m_{i}")
                monthly_bills_input.append(val)
    else:
        avg_bill = st.number_input(t["bill_avg"], min_value=0.0, value=1500.0, step=100.0)
        monthly_bills_input = [avg_bill] * 12

    st.divider()
    
    saudi_cities = {
        "الرياض (5.8h)": 5.8, "جدة (6.0h)": 6.0, "الدمام (5.6h)": 5.6,
        "مكة (6.2h)": 6.2, "المدينة (6.3h)": 6.3, "أبها (5.9h)": 5.9,
        "تبوك (6.1h)": 6.1, "حائل (6.0h)": 6.0, "جازان (5.9h)": 5.9,
        "نجران (6.4h)": 6.4, "القصيم (5.8h)": 5.8, "الطائف (5.9h)": 5.9
    }
    location_key = st.selectbox(t["city"], list(saudi_cities.keys()))
    sun_hours = saudi_cities[location_key]
    
    default_area = 400.0
    if st.session_state['calculated_area'] > 0:
        default_area = st.session_state['calculated_area']
        
    roof_area = st.number_input(t["area"], min_value=10.0, value=default_area, help="يتم تحديثها تلقائياً عند الرسم على الخريطة")
    
    price_per_kwh = st.number_input(t["price_kwh"], min_value=0.01, value=0.18, format="%.3f")
    cost_per_kw = st.number_input(t["cost_per_kw"], min_value=1000.0, value=3000.0)

    st.markdown("---")
    st.subheader(t["battery_section"])
    want_batteries = st.checkbox(t["add_battery"])
    battery_cost_total = 0.0
    battery_size_kwh = 0.0
    
    if want_batteries:
        backup_hours = st.slider(t["battery_hours"], 1, 12, 4)
        cost_battery_unit = st.number_input(t["battery_cost"], value=1500.0)
    
    st.markdown("---")
    with st.expander("Engineering Parameters"):
        inflation_rate = st.slider(t["inflation"], 0.0, 10.0, 3.0, 0.1) / 100
        degradation_rate = st.slider(t["degradation"], 0.0, 2.0, 0.5, 0.1) / 100
        discount_rate = 0.05
    
    run_calc = st.button(t["calculate"], type="primary")

# --- المحرك الرئيسي ---
st.title(t["title"])

if run_calc:
    # 1. تحليل الاستهلاك
    cons_curve_kwh = [bill / price_per_kwh if price_per_kwh > 0 else 0 for bill in monthly_bills_input]
    total_yearly_consumption = sum(cons_curve_kwh)
    avg_monthly_consumption = total_yearly_consumption / 12
    
    # 2. الحسابات
    daily_avg_consumption = avg_monthly_consumption / 30
    required_system_kw = (daily_avg_consumption / sun_hours) * 1.1
    max_system_by_area = roof_area / 7
    final_system_kw = min(required_system_kw, max_system_by_area)
    
    panel_wattage = 450
    num_panels = int((final_system_kw * 1000) / panel_wattage)
    if num_panels < 1: num_panels = 1
    actual_system_kw = (num_panels * panel_wattage) / 1000
    
    solar_investment = actual_system_kw * cost_per_kw
    
    if want_batteries:
        load_per_hour = daily_avg_consumption / 24
        battery_size_kwh = load_per_hour * backup_hours
        battery_cost_total = battery_size_kwh * cost_battery_unit
    else:
        battery_size_kwh = 0
        battery_cost_total = 0
        
    total_investment = solar_investment + battery_cost_total
    
    # 3. المحاكاة
    years_range = range(1, 26)
    cash_flow = []
    cumulative_cash_flow = []
    cumulative_val = -total_investment
    current_price = price_per_kwh
    yearly_prod = actual_system_kw * sun_hours * 365 * 0.9
    
    mon_prod_avg = yearly_prod / 12
    prod_curve_kwh = []
    for i in range(12):
        if i in [5, 6, 7, 8]: efficiency_factor = 0.94
        elif i in [2, 3, 9, 10]: efficiency_factor = 1.05
        else: efficiency_factor = 1.0
        prod_curve_kwh.append(mon_prod_avg * efficiency_factor)
        
    scale = yearly_prod / sum(prod_curve_kwh)
    prod_curve_kwh = [x * scale for x in prod_curve_kwh]

    for year in years_range:
        useful_production = min(yearly_prod, total_yearly_consumption)
        savings = useful_production * current_price
        om_cost = total_investment * 0.01
        net_savings = savings - om_cost
        cash_flow.append(net_savings)
        cumulative_val += net_savings
        cumulative_cash_flow.append(cumulative_val)
        current_price *= (1 + inflation_rate)
        yearly_prod *= (1 - degradation_rate)
        
    annual_savings_y1 = cash_flow[0] + (total_investment * 0.01)
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
    cost_label = t["cost"]
    if want_batteries: cost_label += " (+Batt)"
    c3.metric(cost_label, f"{total_investment:,.0f} {curr}")
    c4.metric(t["savings"], f"{annual_savings_y1:,.0f} {curr}")
    
    c5, c6, c7 = st.columns(3)
    c5.metric(t["roi"], f"{roi_percent:.0f}%")
    c6.metric(t["payback"], f"{payback_years:.1f} Years")
    c7.metric(t["npv"], f"{npv_value:,.0f} {curr}")
    
    st.divider()
    st.subheader(t["breakdown"])
    solar_panels_cost = solar_investment * 0.45
    inverter_cost = solar_investment * 0.15
    structure_cost = solar_investment * 0.20
    installation_cost = solar_investment * 0.20
    
    breakdown_data = {
        "Item": ["Solar Panels", "Inverters", "Mounting Structure", "Installation & BOS", "Battery Storage"],
        "Cost (SAR)": [solar_panels_cost, inverter_cost, structure_cost, installation_cost, battery_cost_total]
    }
    df_breakdown = pd.DataFrame(breakdown_data)
    df_breakdown["Cost (SAR)"] = df_breakdown["Cost (SAR)"].apply(lambda x: f"{x:,.0f}")
    st.table(df_breakdown)

    months_en = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    months_ar = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
    months_lbl = months_ar if language == "العربية" else months_en

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=months_lbl, y=cons_curve_kwh, name='Client Consumption', line=dict(color='#D32F2F', width=3)))
    fig1.add_trace(go.Bar(x=months_lbl, y=prod_curve_kwh, name='Solar Production', marker_color='#FBC02D'))
    fig1.update_layout(title=t["chart_title"], yaxis_title="kWh", height=450)
    st.plotly_chart(fig1, use_container_width=True)
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=list(years_range), y=cumulative_cash_flow, fill='tozeroy', name='Net Cumulative', line=dict(color='#2E7D32')))
    fig2.update_layout(title=t["chart_cashflow"], xaxis_title="Year", yaxis_title=curr, height=400)
    fig2.add_hline(y=0, line_dash="dash", line_color="red")
    st.plotly_chart(fig2, use_container_width=True)

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

        pdf.set_fill_color(50, 50, 50)
        pdf.rect(0, 0, 210, 30, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(18)
        pdf.cell(190, 15, txt=txt(t["title"]), ln=True, align='C')
        pdf.set_font_size(10)
        pdf.cell(190, 5, txt=txt("Solar PV Feasibility Study - Technical Report"), ln=True, align='C')
        pdf.ln(15)
        pdf.set_text_color(0, 0, 0)
        
        def table_row(label, value):
            pdf.set_font('Amiri', '', 11)
            pdf.cell(110, 7, txt=txt(label), border=1, align='R' if language=="العربية" else 'L')
            pdf.set_font('Amiri', '', 11)
            pdf.cell(80, 7, txt=txt(str(value)), border=1, ln=True, align='C')

        pdf.set_fill_color(220, 220, 220)
        pdf.set_font_size(12)
        pdf.cell(190, 8, txt=txt("1. Client & Location Data"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        table_row(t["city"], location_key.split('/')[0])
        lat, lng = st.session_state['coords']
        if lat != 0.0: table_row("Map Coordinates", f"{lat:.5f}, {lng:.5f}")
        else: table_row("Map Coordinates", "Not Selected")
        table_row("Total Annual Consumption", f"{int(total_yearly_consumption):,} kWh")
        table_row(t["area"], f"{roof_area:.1f} m2")
        pdf.ln(4)

        pdf.cell(190, 8, txt=txt("2. System Specifications"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        table_row(t["system_size"], f"{actual_system_kw:.2f} kWp")
        table_row(t["panels"], f"{num_panels}")
        table_row("Annual Generation (Yr1)", f"{int(yearly_prod):,} kWh")
        if want_batteries: table_row("Storage Capacity", f"{battery_size_kwh:.1f} kWh")
        pdf.ln(4)
        
        pdf.cell(190, 8, txt=txt("3. Financial Indicators"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        table_row(t["cost"], f"{total_investment:,.0f} {curr}")
        table_row(t["savings"], f"{annual_savings_y1:,.0f} {curr}")
        table_row(t["payback"], f"{payback_years:.1f} Years")
        table_row(t["roi"], f"{roi_percent:.1f}%")
        pdf.ln(4)

        pdf.cell(190, 8, txt=txt("5. Quotation Cost Structure"), ln=True, fill=True, align='R' if language=="العربية" else 'L')
        table_row("PV Panels", f"{solar_panels_cost:,.0f} {curr}")
        table_row("Inverters", f"{inverter_cost:,.0f} {curr}")
        table_row("Structure & Installation", f"{(structure_cost+installation_cost):,.0f} {curr}")
        if want_batteries: table_row("Batteries", f"{battery_cost_total:,.0f} {curr}")
        table_row("TOTAL CAPEX", f"{total_investment:,.0f} {curr}")

        return pdf.output(dest='S').encode('latin-1')

    pdf_data = create_pro_pdf()
    st.download_button(label=t["download_pdf"], data=pdf_data, file_name="Solar_Feasibility_Report.pdf", mime="application/pdf", type="primary")

else:
    st.info("System Ready. Use Satellite Map to draw roof area.")
