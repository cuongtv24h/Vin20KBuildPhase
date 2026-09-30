#!/usr/bin/env bash
set -e

echo "=== [P-096] Bắt đầu tự động cập nhật và triển khai ==="

# 1. Pull code mới nhất
echo ">>> Pulling latest code from origin/develop..."
git pull origin develop

# 2. Cập nhật backend dependencies
echo ">>> Installing/Updating Python dependencies..."
if [ -d ".venv" ]; then
    .venv/bin/pip install -r requirements.txt
fi

# 3. Build Frontend
echo ">>> Building Frontend production bundles..."
cd frontend
npm install
npm run build
cd ..

# 4. Đảm bảo thư mục logs tồn tại
mkdir -p logs

# 5. Khởi động hoặc reload PM2 backend
echo ">>> Reloading PM2 backend service..."
if command -v pm2 >/dev/null 2>&1; then
    pm2 reload deploy/ecosystem.config.cjs || pm2 start deploy/ecosystem.config.cjs
    pm2 save
fi

# 6. Kiểm tra và reload Nginx
echo ">>> Reloading Nginx..."
if command -v nginx >/dev/null 2>&1; then
    sudo nginx -t && sudo systemctl reload nginx
fi

echo "=== [P-096] Triển khai thành công! ==="
