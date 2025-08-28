# 📋 Пошаговая инструкция для развертывания на Vast.ai

## 🎯 Цель
Развернуть Fast Video Builder API на RTX 3090 через Vast.ai за ~$0.15-0.25/час

## 📝 Что вам понадобится

- Аккаунт на [Vast.ai](https://vast.ai)
- $10-20 на балансе для тестирования
- Базовые знания терминала Linux

---

## 🚀 Шаг 1: Регистрация на Vast.ai

1. Идите на [vast.ai](https://vast.ai)
2. Нажмите **"Sign Up"**
3. Подтвердите email
4. Пополните баланс на $10-20 для начала

---

## 💰 Шаг 2: Поиск RTX 3090

1. Войдите в [консоль Vast.ai](https://console.vast.ai)
2. Нажмите **"Create"** → **"New Instance"**
3. В фильтрах установите:
   ```
   GPU Model: RTX 3090 или RTX 3090 Ti
   RAM: минимум 32GB
   Storage: минимум 100GB
   Price: до $0.25/hour
   Reliability: >95%
   ```
4. Отсортируйте по цене (по возрастанию)
5. Выберите самый дешевый вариант

---

## 🐳 Шаг 3: Создание инстанса

1. Нажмите **"Rent"** на выбранной машине
2. В настройках укажите:
   ```
   Image: pytorch/pytorch:latest
   или
   Image: nvidia/cuda:11.8-runtime-ubuntu22.04
   
   Disk Space: 100GB
   
   On-start script: (оставьте пустым)
   ```
3. Нажмите **"Create Instance"**
4. Ждите 2-3 минуты пока инстанс запустится

---

## 🔌 Шаг 4: Подключение к серверу

1. В консоли Vast.ai найдите ваш инстанс
2. Нажмите **"Connect"**
3. Скопируйте SSH команду, например:
   ```bash
   ssh -p 12345 root@ssh.vast.ai
   ```
4. Выполните команду в терминале
5. При первом подключении введите **"yes"**

---

## 📦 Шаг 5: Установка зависимостей

Выполните команды по порядку:

```bash
# Обновляем систему
apt update && apt upgrade -y

# Устанавливаем Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Устанавливаем Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Устанавливаем NVIDIA Container Runtime
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
apt update && apt install -y nvidia-docker2
systemctl restart docker

# Проверяем GPU
nvidia-smi
docker run --rm --gpus all nvidia/cuda:11.8-runtime-ubuntu22.04 nvidia-smi
```

---

## 📁 Шаг 6: Загрузка проекта

```bash
# Создаем рабочую папку
mkdir /app && cd /app

# Загружаем файлы проекта (выберите один способ)

# Способ 1: Если у вас есть Git репозиторий
git clone https://github.com/your-username/fast-video-builder-gpu.git .

# Способ 2: Загрузка через wget (если файлы на сервере)
wget https://your-server.com/gpu-server.zip
unzip gpu-server.zip

# Способ 3: Создание файлов вручную (см. следующий шаг)
```

---

## ✏️ Шаг 7: Создание файлов вручную

Если у вас нет готового архива, создайте файлы:

```bash
# Создаем структуру
mkdir -p /app/{api,worker/code,nginx,scripts,models}

# Создаем основные файлы (содержимое будет в следующих шагах)
touch /app/docker-compose.yml
touch /app/.env
touch /app/api/main.py
touch /app/worker/worker.py
# ... и так далее
```

**Содержимое файлов смотрите в разделах ниже ⬇️**

---

## 🔧 Шаг 8: Настройка переменных

Создайте файл `/app/.env`:

```bash
cat > /app/.env << 'EOF'
# Redis настройки
REDIS_URL=redis://redis:6379

# MinIO настройки
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_URL=minio:9000

# Worker настройки
WORKER_CONCURRENCY=4
GPU_MEMORY_LIMIT=6144

# API настройки
API_HOST=0.0.0.0
API_PORT=8000
MAX_FILE_SIZE=500MB
CLEANUP_INTERVAL=3600

# Видео настройки
DEFAULT_TARGET_FPS=16
DEFAULT_RESOLUTION=1920:1080
MAX_DURATION_MINUTES=30
EOF
```

---

## 🐳 Шаг 9: Запуск сервисов

```bash
# Переходим в папку проекта
cd /app

# Собираем и запускаем контейнеры
docker-compose up --build -d

# Проверяем статус
docker-compose ps

# Смотрим логи
docker-compose logs -f
```

Должны запуститься сервисы:
- ✅ `redis` - очередь задач
- ✅ `minio` - файловое хранилище  
- ✅ `api` - API сервер
- ✅ `worker_1`, `worker_2`, etc. - обработчики

---

## 🧪 Шаг 10: Тестирование

```bash
# Проверяем здоровье API
curl http://localhost:8000/health

# Запускаем тестовый скрипт
python3 scripts/test_api.py
```

Если все работает, увидите:
```
✅ API сервер доступен
✅ Создана тестовая задача: abc-123-def
⏳ Ожидание завершения...
✅ Видео готово! URL: http://localhost:9000/...
```

---

## 🌐 Шаг 11: Настройка доступа извне

Чтобы обращаться к API с вашего компьютера:

```bash
# Узнаем внешний IP
curl ifconfig.me

# Открываем порты в файрволе (если нужно)
ufw allow 8000
ufw allow 9000
```

Теперь API доступен по адресу: `http://YOUR_IP:8000`

---

## 📊 Шаг 12: Мониторинг

```bash
# Мониторинг GPU
watch -n 1 nvidia-smi

# Мониторинг контейнеров
docker stats

# Логи воркеров
docker-compose logs -f worker

# Очередь задач
docker-compose exec redis redis-cli monitor
```

---

## 💡 Полезные команды

```bash
# Перезапуск сервисов
docker-compose restart

# Остановка
docker-compose down

# Масштабирование воркеров
docker-compose up --scale worker=6 -d

# Очистка логов
docker system prune -f

# Обновление кода
docker-compose down
docker-compose up --build -d
```

---

## 🚨 Решение проблем

### Проблема: "CUDA out of memory"
```bash
# Уменьшите количество воркеров
docker-compose up --scale worker=2 -d
```

### Проблема: "Port already in use"
```bash
# Найдите процесс
lsof -i :8000
# Убейте процесс
kill -9 PID
```

### Проблема: "No space left on device"
```bash
# Очистите Docker
docker system prune -a -f
# Очистите логи
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

---

## 💰 Управление затратами

### Автоматическое выключение при простое:
```bash
# Добавьте в crontab
crontab -e

# Добавьте строку (выключение через 30 мин простоя)
*/5 * * * * /app/scripts/auto_shutdown.sh
```

### Мониторинг затрат:
- Проверяйте баланс в консоли Vast.ai
- Настройте уведомления при низком балансе
- Используйте `Spot instances` для экономии

---

## 🎉 Готово!

Ваш GPU сервер готов к работе!

**Следующие шаги:**
1. Интегрируйте API в ваше приложение
2. Настройте автомасштабирование
3. Добавьте мониторинг и алерты
4. Оптимизируйте под вашу нагрузку

**Поддержка:**
- Логи: `docker-compose logs`
- Мониторинг: `nvidia-smi`, `docker stats`
- Тестирование: `python scripts/test_api.py`
