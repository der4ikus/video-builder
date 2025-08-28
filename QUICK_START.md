# ⚡ Быстрый старт для чайников

## 🎯 Что это?

Fast Video Builder - это API для создания видео с озвучкой на GPU сервере.
Вы загружаете текст и видео, получаете готовое видео с озвучкой.

## 🚀 Запуск за 5 минут

### 1. Подключитесь к серверу Vast.ai
```bash
ssh -p ПОРТ root@ssh.vast.ai
```

### 2. Скачайте проект
```bash
cd /app
# Если у вас есть архив:
wget https://your-server.com/gpu-server.zip
unzip gpu-server.zip

# Или создайте файлы вручную (см. SETUP_GUIDE.md)
```

### 3. Автоматическая настройка
```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

### 4. Запуск сервисов
```bash
./scripts/start.sh
```

### 5. Тестирование
```bash
python3 scripts/test_api.py
```

## 🌐 Использование API

### Создание видео:
```bash
curl -X POST "http://YOUR_IP:8000/api/v1/video/create" \
  -F "text=Привет! Это тестовое видео." \
  -F "voice=am_santa" \
  -F "speed=0.8" \
  -F "video=@your_video.mp4" \
  -F "bg_audio=@background.mp3" \
  -F "target_duration_minutes=5"
```

### Проверка статуса:
```bash
curl "http://YOUR_IP:8000/api/v1/video/JOB_ID/status"
```

### Скачивание результата:
```bash
curl -L "http://YOUR_IP:8000/api/v1/video/JOB_ID/download" -o result.mp4
```

## 📊 Мониторинг

```bash
# Статус сервисов
./scripts/monitor.sh

# Непрерывный мониторинг
./scripts/monitor.sh --watch

# Логи
docker-compose logs -f

# GPU статистика
watch -n 1 nvidia-smi
```

## 🛑 Управление

```bash
# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Масштабирование воркеров
docker-compose up --scale worker=6 -d

# Очистка
docker system prune -f
```

## 💰 Экономия средств

### Автоматическое выключение при простое:
```bash
# Добавить в crontab
crontab -e

# Добавить строку (проверка каждые 5 минут):
*/5 * * * * /app/scripts/auto_shutdown.sh
```

### Мониторинг затрат:
- Проверяйте баланс в консоли Vast.ai
- Используйте Spot instances для экономии
- Выключайте сервер когда не используете

## 🔧 Настройка производительности

### Для RTX 3090 (24GB):
```bash
# В .env файле:
WORKER_REPLICAS=4
GPU_MEMORY_LIMIT=6144
```

### Для RTX 4090 (24GB):
```bash
# В .env файле:
WORKER_REPLICAS=6
GPU_MEMORY_LIMIT=4096
```

### Для экономии (стабильнее):
```bash
# В .env файле:
WORKER_REPLICAS=2
GPU_MEMORY_LIMIT=8192
```

## 🆘 Решение проблем

### "CUDA out of memory":
```bash
# Уменьшите воркеров
docker-compose up --scale worker=2 -d
```

### "Port already in use":
```bash
# Найдите процесс
lsof -i :8000
kill -9 PID
```

### "No space left":
```bash
# Очистите Docker
docker system prune -a -f
# Очистите временные файлы
rm -rf /tmp/video_jobs/*
```

### API недоступен:
```bash
# Проверьте статус
docker-compose ps
# Перезапустите
docker-compose restart api
```

## 📞 Поддержка

- Документация API: `http://YOUR_IP:8000/docs`
- Логи: `docker-compose logs`
- Мониторинг: `./scripts/monitor.sh`
- Тестирование: `python3 scripts/test_api.py`

## 🎉 Готово!

Ваш GPU сервер готов к работе!
API доступен по адресу: `http://YOUR_IP:8000`
