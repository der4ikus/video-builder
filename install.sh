#!/bin/bash
# 🚀 Fast Video Builder - Автоматическая установка

set -e

# Настраиваем неинтерактивный режим глобально
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export APT_LISTCHANGES_FRONTEND=none

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Fast Video Builder GPU Server - Автоматическая установка${NC}"
echo "=============================================================="

# Получаем URL репозитория из переменной окружения или используем по умолчанию
REPO_URL="${REPO_URL:-https://github.com/der4ikus/video-builder.git}"
INSTALL_DIR="/app/fast-video-builder"

# Проверяем root права
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите от имени root: sudo bash${NC}"
    exit 1
fi

echo -e "${BLUE}📦 Обновление системы...${NC}"
# Обновляем только список пакетов, без upgrade системы
apt-get update -y

echo -e "${BLUE}🔧 Установка зависимостей...${NC}"
# Устанавливаем только необходимые пакеты без обновления системы
apt-get install -y --no-install-recommends curl wget git python3 python3-pip ffmpeg htop nano

# Проверяем Docker (должен быть в vastai/base-image)
if ! command -v docker &> /dev/null; then
    echo -e "${BLUE}🐳 Установка Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# Проверяем Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${BLUE}🔧 Установка Docker Compose...${NC}"
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# NVIDIA поддержка уже есть в vastai/base-image
echo -e "${BLUE}🎮 GPU поддержка из vastai/base-image${NC}"

# Клонирование репозитория
echo -e "${BLUE}📥 Скачивание Fast Video Builder...${NC}"
rm -rf "$INSTALL_DIR"
git clone "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Создание .env файла
echo -e "${BLUE}⚙️ Настройка конфигурации...${NC}"
if [ ! -f ".env" ]; then
    cp env.example .env
fi

# Скачивание моделей TTS
echo -e "${BLUE}🤖 Скачивание моделей TTS...${NC}"
mkdir -p models
cd models

if [ ! -f "kokoro-v1.0.onnx" ]; then
    wget -q --show-progress https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
fi

if [ ! -f "voices-v1.0.bin" ]; then
    wget -q --show-progress https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin
fi

# Копирование моделей в worker
cp *.onnx *.bin ../worker/code/ 2>/dev/null || true

cd "$INSTALL_DIR"

# Права доступа
chmod +x scripts/*.sh
chmod +x install.sh

# Создание папок
mkdir -p /tmp/video_jobs
chmod 777 /tmp/video_jobs

# Сборка образов
echo -e "${BLUE}🔨 Сборка Docker образов...${NC}"
docker-compose build

# Создание алиасов
echo -e "${BLUE}🔧 Настройка команд...${NC}"
cat >> /root/.bashrc << 'EOF'

# Fast Video Builder
alias fvb-start='cd /app/fast-video-builder && docker-compose up -d'
alias fvb-stop='cd /app/fast-video-builder && docker-compose down'
alias fvb-logs='cd /app/fast-video-builder && docker-compose logs -f'
alias fvb-status='cd /app/fast-video-builder && docker-compose ps'
EOF

# Получение IP
EXTERNAL_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")

echo ""
echo -e "${GREEN}🎉 Установка завершена!${NC}"
echo ""
echo -e "${GREEN}🚀 Запуск сервисов:${NC} cd $INSTALL_DIR && ./scripts/start.sh"
echo -e "${GREEN}🧪 Тестирование:${NC} python3 scripts/test_api.py"
echo -e "${GREEN}📖 Документация:${NC} http://$EXTERNAL_IP:8000/docs"
echo ""

# Опциональный запуск
read -p "Запустить сервисы сейчас? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./scripts/start.sh
fi

echo -e "${GREEN}✅ Fast Video Builder готов к работе!${NC}"
