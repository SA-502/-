# مصمم أنظمة الطاقة الشمسية — المرحلة الأولى (MVP)

تطبيق ويب داخلي لتصميم أنظمة الطاقة الشمسية على صور الأقمار الصناعية، وحساب الإنتاج الساعي، وإصدار دراسة وعرض سعر PDF بالعربية والإنجليزية. المواصفات الكاملة في [`SPEC.md`](SPEC.md).

## ما تشمله هذه المرحلة

| الجزء | الموجود |
| --- | --- |
| العملاء والمشاريع | بحث وفلترة بالحالة، إدخال الاستهلاك بالـ kWh أو بالفواتير (تُحوَّل حسب الشرائح) أو بمتوسط الفاتورة |
| المصمم 2D | رسم السطح/الأرض والعوائق على صور Esri، تحريك الرؤوس، الارتداد، توزيع تلقائي (صفوف مائلة أو ملاصقة)، فراغ صفوف تلقائي يمنع التظليل 9–15 يوم 21 ديسمبر، حد أقصى للألواح «حسب الاستهلاك»، حذف وإضافة الألواح يدويًا، نسخ متعددة للتصميم |
| المحاكاة | pvlib ساعية 8760 ساعة على سنة PVGIS النموذجية: Perez + Albedo، زاوية السقوط، اتساخ شهري، حرارة Faiman، PVWatts، خسائر DC/AC، قص الانفرتر، مخطط خسائر. بدون تظليل في هذه المرحلة |
| المالية | شرائح التعرفة + ضريبة 15%، صافي الفوترة (استهلاك ذاتي ساعي على نمط حمل حسب نوع العميل، رصيد الفائض يُخصم من الفاتورة ويُرحَّل ولا يُصرف)، 25 سنة: صافي القيمة الحالية، العائد الداخلي، الاسترداد، LCOE |
| عرض السعر والتقرير | ألواح + انفرتر + هيكل + بنود قائمة الأسعار + بنود إضافية وخصم؛ PDF عربي RTL أو إنجليزي، محفوظ في قاعدة البيانات |
| الإدارة | قاعدة المكونات، قائمة الأسعار، التعرفة، المستخدمون بثلاثة أدوار (مهندس، مبيعات، مدير) |

## الهيكل

```
backend/    FastAPI + SQLAlchemy/GeoAlchemy2 + pvlib + WeasyPrint
  app/api/        نقاط الـ API
  app/services/   الحسابات: simulation, tariffs, finance, pricing, pvgis, report
  migrations/     Alembic
  tests/          pytest (الحسابات + تدفق الـ API كامل على PostGIS)
frontend/   React + TypeScript + Vite + MapLibre + Turf.js
  src/geometry/   الارتداد والتوزيع التلقائي (مع اختبارات vitest)
  src/pages/      الشاشات
legacy/     تطبيق Streamlit القديم للمرجع فقط
docker-compose.yml   db (PostGIS) + api + web (nginx) + backup يومي
```

## التشغيل على الخادم (Docker Compose)

```bash
cp .env.example .env      # عدّل كلمات المرور وبيانات الشركة
docker compose up -d --build
```

التطبيق على `http://SERVER:8080` (غيّر `WEB_PORT`). أول تشغيل ينشئ الجداول والمدير من `SOLAR_ADMIN_EMAIL` و`SOLAR_ADMIN_PASSWORD`، ومكونات وأسعار «مثال» للتجربة (أوقفها بـ `SOLAR_SEED_SAMPLES=false`). النسخ الاحتياطية اليومية في مجلد `backups/`، والاسترجاع:

```bash
docker compose exec -T db pg_restore -U solar -d solar --clean < backups/solar-YYYYMMDD-HHMM.dump
```

للنطاق مع HTTPS ضع التطبيق خلف الـ reverse proxy الموجود (مثل Nginx أو Traefik بجانب n8n) ووجّهه إلى المنفذ `WEB_PORT`.

### النشر الحالي على Hostinger VPS

التطبيق منشور على `https://solar.srv2082532.hstgr.cloud` عبر مدير Docker في hPanel، خلف Traefik الخاص بـ n8n. مدير Docker لا يبني الصور، لذلك فيه مشروعان:

- **`solar-build`** ([`deploy/hostinger/build-images.yml`](deploy/hostinger/build-images.yml)): يسحب الكود من GitHub (الفرع في `GIT_REF`) ويبني الصورتين `solar-api` و`solar-web` ثم يتوقف.
- **`solar`** ([`deploy/hostinger/docker-compose.yml`](deploy/hostinger/docker-compose.yml)): قاعدة البيانات والخادم والواجهة والنسخ الاحتياطي. الأسرار في متغيرات المشروع داخل مدير Docker، وليست في المستودع.

**للتحديث بعد أي تعديل على الكود:** من hPanel ← Docker Manager، أعد تشغيل `solar-build` وانتظر `BUILD DONE` في السجلات، ثم أعد تشغيل `solar`.

الخادم يحتاج الوصول إلى `re.jrc.ec.europa.eu` (PVGIS) و`server.arcgisonline.com` (الصور) و`nominatim.openstreetmap.org` (البحث عن العناوين). بيانات الطقس تُحفظ لكل موقع (دقة ≈ 1 كم) فلا تُطلب مرتين.

## التطوير محليًا

```bash
# قاعدة البيانات
docker compose up -d db        # أو PostgreSQL محلي مع PostGIS

# الخادم
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export SOLAR_DATABASE_URL=postgresql+psycopg://solar:PASSWORD@localhost:5432/solar
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload          # توثيق الـ API: http://localhost:8000/api/docs

# الواجهة
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

## الاختبارات

```bash
cd backend && pytest          # اختبارات الـ API تحتاج قاعدة solar_test (SOLAR_DATABASE_URL)، وتُتخطى بدونها
cd frontend && npm test && npm run typecheck
```

## قيم يجب مراجعتها قبل الاعتماد

- **التعرفة** (شاشة الأسعار والتعرفة): السكني 0.18/0.30، الزراعي 0.16/0.20، الصناعي 0.18، الحكومي 0.32 من جدول الشركة السعودية للكهرباء منذ 2018. التجاري 0.22/0.32 حسب تقارير 2026. سعر الفائض 0.07 سكني و0.05 لغيره حسب مقترح هيئة تنظيم الكهرباء.
- **أسعار المكونات والبنود**: كلها أمثلة.
- **الافتراضات**: اتساخ 4% شهريًا، عدم تطابق 2%، أسلاك DC 1.5%، تدهور أولي 1.5%، أسلاك AC 1%، تراجع سنوي 0.5%، صيانة 1%، معدل خصم 6%. كلها قابلة للتعديل لكل محاكاة أو دراسة.

## المراحل القادمة

2. المحاكاة الكاملة (نموذج الدايود الواحد، منحنيات الانفرتر) ومقارنة 5 مشاريع مع PVsyst/HelioScope.
3. العارض 3D والتظليل لكل لوح (العوائق وارتفاعاتها محفوظة من الآن).
4. السلاسل الكهربائية والتحقق من الجهد (`modules_layout.string_id` جاهز).
5. التكامل مع n8n وتصدير المحاسبة.
