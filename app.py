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
        "logo_upload": "Upload Company Logo",
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
        "logo_upload": "رفع شعار الشركة (Logo)",
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
    language = st.radio("", ["العربية", "English"], horizontal=True)
    t = translations[language]
    curr = t["currency"]
    
    # --- قسم الشعار الجديد ---
    uploaded_logo = st.file_uploader(t["logo_upload"], type=['png', 'jpg', 'jpeg'])
    if uploaded_logo is not None:
        st.image(uploaded_logo, width=150)
    else:
        # صورة افتراضية في حال عدم رفع شعار
        st.image("https://cdn-icons-png.flaticon.com/512/861/861059.png", width=80)
        
    st.markdown("### Saudi Solar Tool")
    st.divider()
    
    st.subheader(t["sidebar_title"])
    monthly_bill = st.number_input(t['bill'], value=1500.0, step=100.0)
    
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


# --- المحرك الرئيسي (تمت إزالة زر run_calc ليصبح تفاعلياً دائماً) ---

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
    
    mon_prod = actual_system_kw * sun_hours * 30 * 0.9
    prod_curve = [mon_prod * (1 + (i-6)*0.1) if i<6 else mon_prod * (1 - (i-6)*0.1) for i in range(12)] 
    cons_curve = [monthly_consumption_kwh] * 12
    months_labels = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
    
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(x=months_labels, y=prod_curve, name='الإنتاج الشمسي', marker_color='#FDD835'))
    fig_bar.add_trace(go.Scatter(x=months_labels, y=cons_curve, name='استهلاكك الحالي', line=dict(color='#1565C0', width=3)))
    fig_bar.update_layout(title=t["chart_title"], yaxis_title="kWh", height=400)
    st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    k1, k2, k3 = st.columns(3)
    k1.metric(t["payback"], f"{payback_years:.1f} Years")
    k2.metric(t["roi"], f"{roi_percent:,.0f}%")
    k3.metric(t["npv"], f"{npv_value:,.0f} {curr}")
    
    fig_cf = go.Figure()
    fig_cf.add_trace(go.Scatter(x=list(years_range), y=cumulative_cash_flow, fill='tozeroy', 
                                mode='lines', name='التدفق التراكمي', line=dict(color='#43A047', width=3)))
    fig_cf.add_hline(y=0, line_dash="dash", line_color="red")
    fig_cf.update_layout(xaxis_title="السنوات", yaxis_title=curr, hovermode="x unified", height=400)
    st.plotly_chart(fig_cf, use_container_width=True)

with tab3:
    st.markdown(f"### 📄 {t['download_pdf']}")
    
    def create_saudi_pdf():
        pdf = FPDF()
        pdf.add_page()
        font_path = 'Amiri-Regular.ttf'
        if os.path.exists(font_path):
            pdf.add_font('Amiri', '', font_path, uni=True)
            pdf.set_font('Amiri', '', 12)
        else:
            pdf.set_font("Arial", size=12)

        def txt(text):
            if language == "العربية" and os.path.exists(font_path):
                return get_display(arabic_reshaper.reshape(text))
            return text

        # الترويسة مع الشعار (إذا تم رفعه)
        pdf.set_fill_color(245, 245, 245)
        pdf.rect(0, 0, 210, 40, 'F')
        
        # إضافة الشعار للPDF إذا وجد
        if uploaded_logo is not None:
            # حفظ الشعار مؤقتاً
            with open("temp_logo.png", "wb") as f:
                f.write(uploaded_logo.getbuffer())
            pdf.image("temp_logo.png", 10, 5, 30)
            
        pdf.set_xy(0, 10)
        pdf.set_font_size(22)
        pdf.cell(210, 15, txt=txt(t["title"]), ln=True, align='C')
        pdf.set_font_size(10)
        pdf.cell(210, 5, txt=txt("تقرير جدوى فني ومالي - Technical & Financial Proposal"), ln=True, align='C')
        pdf.ln(20)

        def table_row(label, value):
            pdf.set_font('Amiri', '', 12)
            pdf.cell(100, 8, txt=txt(label), border=1, align='R' if language=="العربية" else 'L')
            pdf.set_font('Amiri', '', 12) 
            pdf.cell(90, 8, txt=txt(str(value)), border=1, ln=True, align='C')

        # 1. بيانات الموقع والمشروع
        pdf.set_fill_color(46, 125, 50) 
        pdf.set_text_color(255, 255, 255)
        pdf.set_font_size(14)
        pdf.cell(190, 10, txt=txt("1. ملخص المشروع والموقع"), ln=True, fill=True, align='R')
        pdf.set_text_color(0, 0, 0)
        
        table_row(t["city"], location_key.split('/')[0])
        table_row(t["bill"], f"{monthly_bill} {curr}")
        table_row(t["area"], f"{roof_area} m2")
        pdf.ln(5)

        # 2. المواصفات الفنية
        pdf.set_fill_color(46, 125, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, txt=txt("2. المواصفات الفنية للنظام"), ln=True, fill=True, align='R')
        pdf.set_text_color(0, 0, 0)
        
        table_row(t["system_size"], f"{actual_system_kw:.2f} kW")
        table_row(t["panels"], f"{num_panels}")
        table_row("إنتاج السنة الأولى", f"{int(yearly_production_kwh):,} kWh")
        pdf.ln(5)

        # 3. التحليل المالي
        pdf.set_fill_color(46, 125, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, txt=txt("3. المؤشرات المالية والاقتصادية"), ln=True, fill=True, align='R')
        pdf.set_text_color(0, 0, 0)
        
        table_row(t["cost"], f"{total_investment:,.0f} {curr}")
        table_row(t["savings_1st"], f"{first_year_savings:,.0f} {curr}")
        table_row(t["payback"], f"{payback_years:.1f} Years")
        table_row(t["roi"], f"{roi_percent:,.0f}%")
        table_row("إجمالي التوفير (25 سنة)", f"{total_savings_25y:,.0f} {curr}")

        # 4. التوصيات
        pdf.ln(10)
        pdf.set_text_color(46, 125, 50)
        pdf.set_font_size(14)
        pdf.cell(190, 8, txt=txt(t["rec_title"]), ln=True, align='R')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font_size(11)
        
        recs = [
            "- ينصح باستخدام ألواح من نوع Mono-PERC لكفاءة أعلى في أجواء المملكة.",
            "- يجب التأكد من تنظيف الألواح مرتين شهرياً بسبب الغبار.",
            "- النظام يغطي معظم استهلاكك ويوفر عائداً ممتازاً مقارنة بالبنك.",
            f"- العائد البيئي يعادل زراعة {int(co2_tons * 5)} شجرة تقريباً."
        ]
        for r in recs:
            pdf.cell(190, 6, txt=txt(r), ln=True, align='R')

        return pdf.output(dest='S').encode('latin-1')

    pdf_data = create_saudi_pdf()
    st.download_button(label="📥 " + t["download_pdf"], data=pdf_data, file_name="Saudi_Solar_Study.pdf", mime="application/pdf", type="primary", use_container_width=True)
