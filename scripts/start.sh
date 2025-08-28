#!/bin/bash
# Запуск Fast Video Builder сервисов

set -e

echo "🚀 Запуск Fast Video Builder"
echo "============================"

# Проверяем что мы в правильной папке
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Ошибка: docker-compose.yml не найден"
    echo "Убедитесь что вы находитесь в папке gpu-server"
    exit 1
fi

# Проверяем .env файл
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден. Запустите сначала ./scripts/setup.sh"
    exit 1
fi

# Загружаем переменные окружения
source .env

echo "📋 Конфигурация:"
echo "  - Воркеров: ${WORKER_REPLICAS:-4}"
echo "  - API порт: ${API_PORT:-8000}"
echo "  - GPU лимит: ${GPU_MEMORY_LIMIT:-6144}MB"

# Останавливаем старые контейнеры если есть
echo "🛑 Останавливаем старые контейнеры..."
docker-compose down 2>/dev/null || true

# Очищаем старые временные файлы
echo "🧹 Очищаем временные файлы..."
rm -rf /tmp/video_jobs/* 2>/dev/null || true

# Запускаем сервисы
echo "▶️  Запускаем сервисы..."
docker-compose up -d

# Ждем пока сервисы запустятся
echo "⏳ Ждем запуска сервисов..."
sleep 10

# Проверяем статус
echo "📊 Статус сервисов:"
docker-compose ps

# Проверяем здоровье API
echo ""
echo "🔍 Проверяем API..."
for i in {1..30}; do
    if curl -s http://localhost:${API_PORT:-8000}/health > /dev/null; then
        echo "✅ API сервер запущен"
        break
    else
        echo "⏳ Ждем API сервер... ($i/30)"
        sleep 2
    fi
done

# Показываем логи воркеров
echo ""
echo "📝 Логи воркеров (последние 10 строк):"
docker-compose logs --tail=10 worker

echo ""
echo "🎉 Сервисы запущены!"
echo ""
echo "🌐 Доступные URL:"
echo "  - API документация: http://localhost:${API_PORT:-8000}/docs"
echo "  - Статус API: http://localhost:${API_PORT:-8000}/health"
echo "  - MinIO консоль: http://localhost:9001 (admin/admin123)"
echo ""
echo "📊 Полезные команды:"
echo "  - Логи: docker-compose logs -f"
echo "  - Статус: docker-compose ps"
echo "  - Остановка: docker-compose down"
echo "  - Мониторинг GPU: watch -n 1 nvidia-smi"
echo ""
