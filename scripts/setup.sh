#!/bin/bash
# Автоматическая настройка Fast Video Builder на GPU сервере

set -e

echo "🚀 Fast Video Builder - Автоматическая настройка"
echo "================================================"

# Проверяем что мы в правильной папке
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Ошибка: docker-compose.yml не найден"
    echo "Убедитесь что вы находитесь в папке gpu-server"
    exit 1
fi

# Проверяем Docker
echo "🔍 Проверяем Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не найден. Устанавливаем..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
else
    echo "✅ Docker найден"
fi

# Проверяем Docker Compose
echo "🔍 Проверяем Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не найден. Устанавливаем..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "✅ Docker Compose найден"
fi

# Проверяем NVIDIA Docker
echo "🔍 Проверяем NVIDIA Docker..."
if ! docker run --rm --gpus all nvidia/cuda:11.8-runtime-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "⚠️  NVIDIA Docker не настроен. Настраиваем..."
    
    # Устанавливаем NVIDIA Container Runtime
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
    apt update && apt install -y nvidia-docker2
    systemctl restart docker
    
    echo "✅ NVIDIA Docker настроен"
else
    echo "✅ NVIDIA Docker работает"
fi

# Создаем .env файл если его нет
if [ ! -f ".env" ]; then
    echo "📝 Создаем .env файл..."
    cp env.example .env
    echo "✅ Файл .env создан из env.example"
else
    echo "✅ Файл .env уже существует"
fi

# Создаем папки для моделей
echo "📁 Создаем папки..."
mkdir -p models
mkdir -p /tmp/video_jobs

# Скачиваем модели TTS если их нет
echo "📥 Проверяем модели TTS..."
if [ ! -f "models/kokoro-v1.0.onnx" ]; then
    echo "Скачиваем kokoro-v1.0.onnx..."
    wget -O models/kokoro-v1.0.onnx https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
fi

if [ ! -f "models/voices-v1.0.bin" ]; then
    echo "Скачиваем voices-v1.0.bin..."
    wget -O models/voices-v1.0.bin https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin
fi

echo "✅ Модели готовы"

# Копируем модели в worker
echo "📋 Копируем модели в worker..."
cp models/* worker/code/ 2>/dev/null || true

# Проверяем GPU
echo "🎮 Проверяем GPU..."
if nvidia-smi &> /dev/null; then
    echo "✅ GPU доступен:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits
else
    echo "⚠️  GPU не найден или драйверы не установлены"
fi

# Собираем образы
echo "🔨 Собираем Docker образы..."
docker-compose build

echo ""
echo "🎉 Настройка завершена!"
echo ""
echo "Следующие шаги:"
echo "1. Запустите сервисы: ./scripts/start.sh"
echo "2. Протестируйте API: python3 scripts/test_api.py"
echo "3. Откройте документацию: http://localhost:8000/docs"
echo ""
