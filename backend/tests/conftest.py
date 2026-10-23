import os

# قاعدة اختبار منفصلة؛ يجب ضبطها قبل استيراد app.db
os.environ.setdefault("SOLAR_DATABASE_URL", "postgresql+psycopg://solar:solar@localhost:5432/solar_test")
os.environ.setdefault("SOLAR_JWT_SECRET", "test-secret-key-with-enough-length-for-hs256")
os.environ.setdefault("SOLAR_ADMIN_EMAIL", "admin@test.sa")
os.environ.setdefault("SOLAR_ADMIN_PASSWORD", "admin-pass-123")
