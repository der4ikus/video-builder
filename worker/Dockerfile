FROM nvidia/cuda:11.8-runtime-ubuntu22.04

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем requirements и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаем папки для моделей и временных файлов
RUN mkdir -p /app/models /tmp/video_jobs

# Модели TTS будут скачаны при первом запуске
# (убираем из Docker build для ускорения)

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 worker && chown -R worker:worker /app /tmp/video_jobs
USER worker

# Устанавливаем переменные окружения для CUDA
ENV NVIDIA_VISIBLE_DEVICES=all
ENV CUDA_VISIBLE_DEVICES=0

# GPU проверка будет при запуске контейнера

# Healthcheck
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD python3 -c "from celery import Celery; app = Celery('video_worker', broker='${REDIS_URL}'); result = app.control.ping(timeout=1); print('Worker healthy' if result else 'Worker unhealthy')" || exit 1

# Запускаем Celery worker
CMD ["python3", "worker.py"]
