FROM ubuntu:22.04

# Устанавливаем системные зависимости включая CUDA toolkit
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    wget \
    nvidia-cuda-toolkit \
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

# Скачиваем модели TTS (если они не включены в образ)
RUN if [ ! -f /app/models/kokoro-v1.0.onnx ]; then \
    echo "Downloading TTS models..." && \
    wget -O /app/models/kokoro-v1.0.onnx https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx && \
    wget -O /app/models/voices-v1.0.bin https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin; \
    fi

# Копируем модели в рабочую папку кода
RUN cp /app/models/* /app/code/ 2>/dev/null || true

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 worker && chown -R worker:worker /app /tmp/video_jobs
USER worker

# Устанавливаем переменные окружения для CUDA
ENV NVIDIA_VISIBLE_DEVICES=all
ENV CUDA_VISIBLE_DEVICES=0

# Прогреваем GPU и проверяем доступность
RUN python3 -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU count:', torch.cuda.device_count())" || echo "GPU check failed, continuing..."

# Healthcheck
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD python3 -c "from celery import Celery; app = Celery('video_worker', broker='${REDIS_URL}'); result = app.control.ping(timeout=1); print('Worker healthy' if result else 'Worker unhealthy')" || exit 1

# Запускаем Celery worker
CMD ["python3", "worker.py"]
