#!/bin/bash
# ============================================================
# ExecVision AI — деплой на Timeweb Cloud (5.42.101.207)
# Использование: bash deploy/deploy.sh
# ============================================================
set -e

SERVER="root@5.42.101.207"
APP_DIR="/var/www/hr.axioma-ai.ru"
SERVICE="execvision"

echo ""
echo "  ExecVision AI → hr.axioma-ai.ru"
echo "  Сервер: 5.42.101.207 (Timeweb Cloud, Ubuntu 24.04)"
echo ""

# --- 1. Синхронизируем файлы ---
echo "  → Копируем файлы..."
ssh "$SERVER" "mkdir -p $APP_DIR"
rsync -az --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='data/*.db' \
  --exclude='.env' \
  ./ "$SERVER:$APP_DIR/"

# --- 2. .env на сервере (если не существует — создаём шаблон) ---
echo "  → Проверяем .env..."
ssh "$SERVER" "
  if [ ! -f $APP_DIR/.env ]; then
    cat > $APP_DIR/.env << 'EOF'
YANDEX_SPEECH_KEY=
YANDEX_FOLDER_ID=
TTS_SERVER_PORT=8081
TTS_SERVER_HOST=127.0.0.1
EOF
    echo '  ⚠ Заполни $APP_DIR/.env на сервере: YANDEX_SPEECH_KEY и YANDEX_FOLDER_ID'
  else
    echo '  ✓ .env уже есть'
  fi
"

# --- 3. Python venv и зависимости ---
echo "  → Устанавливаем зависимости..."
ssh "$SERVER" "
  cd $APP_DIR
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet fastapi uvicorn[standard] httpx python-dotenv
"

# --- 4. Лог-директория ---
ssh "$SERVER" "mkdir -p /var/log/execvision && chown www-data:www-data /var/log/execvision 2>/dev/null || true"

# --- 5. systemd сервис ---
echo "  → Запускаем systemd сервис..."
ssh "$SERVER" "
  cp $APP_DIR/deploy/execvision.service /etc/systemd/system/$SERVICE.service
  systemctl daemon-reload
  systemctl enable $SERVICE
  systemctl restart $SERVICE
  sleep 2
  systemctl is-active $SERVICE && echo '  ✓ Сервис запущен' || (echo '  ✗ Ошибка! Лог:' && journalctl -u $SERVICE -n 10 --no-pager && exit 1)
"

# --- 6. Caddy: добавляем hr.axioma-ai.ru если ещё нет ---
echo "  → Настраиваем Caddy..."
ssh "$SERVER" "
  if grep -q 'hr.axioma-ai.ru' /etc/caddy/Caddyfile; then
    echo '  ✓ Caddy уже настроен'
  else
    echo '' >> /etc/caddy/Caddyfile
    cat $APP_DIR/deploy/Caddyfile >> /etc/caddy/Caddyfile
    caddy reload --config /etc/caddy/Caddyfile
    echo '  ✓ Caddy обновлён — hr.axioma-ai.ru добавлен'
  fi
"

# --- 7. Финальная проверка ---
echo "  → Проверяем..."
sleep 3
ssh "$SERVER" "curl -s http://localhost:8081/health"

echo ""
echo "  ✓ Деплой завершён!"
echo "  → https://hr.axioma-ai.ru"
echo ""
