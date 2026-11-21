#!/usr/bin/env bash
# تجهيز Hostinger VPS (Ubuntu 22.04/24.04) لتشغيل لعبة الشفرة
# الاستخدام (كـ root):  bash setup-vps.sh example.com https://github.com/USER/REPO.git
set -euo pipefail

DOMAIN="${1:?اكتب الدومين، مثال: bash setup-vps.sh example.com REPO_URL}"
REPO="${2:?اكتب رابط الريبو}"
BRANCH="${3:-main}"
APP_DIR=/opt/shifra-repo

echo "==> تحديث النظام وتثبيت الأدوات"
apt-get update -y
apt-get install -y curl git nginx ufw certbot python3-certbot-nginx

echo "==> تثبيت Node.js 22"
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1)" != "v22" ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi
npm install -g pm2

echo "==> تنزيل الكود"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH" && git -C "$APP_DIR" checkout "$BRANCH" && git -C "$APP_DIR" pull origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO" "$APP_DIR"
fi
cd "$APP_DIR/shifra"
npm ci --omit=dev

echo "==> تشغيل اللعبة بـ PM2"
pm2 startOrReload ecosystem.config.cjs
pm2 save
pm2 startup systemd -u root --hp /root || true

echo "==> إعداد Nginx"
sed "s/example.com/$DOMAIN/g" deploy/nginx.conf > /etc/nginx/sites-available/shifra
ln -sf /etc/nginx/sites-available/shifra /etc/nginx/sites-enabled/shifra
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> الجدار الناري"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "==> شهادة SSL (HTTPS)"
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect \
  || certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect

echo "✅ تم! افتح https://$DOMAIN"
