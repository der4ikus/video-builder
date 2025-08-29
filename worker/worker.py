#!/usr/bin/env python3
"""
Fast Video Builder - GPU Worker
Обрабатывает задачи генерации видео на GPU с использованием Celery
"""

import os
import sys
import subprocess
import logging
import json
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import torch
from celery import Celery
from minio import Minio
import urllib.request
from minio.error import S3Error

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Настройки из переменных окружения
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MINIO_URL = os.getenv("MINIO_URL", "minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "1"))
GPU_MEMORY_LIMIT = int(os.getenv("GPU_MEMORY_LIMIT", "6144"))

# Инициализация Celery
celery_app = Celery('video_worker', broker=REDIS_URL)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 час максимум на задачу
    task_soft_time_limit=3300,  # 55 минут мягкий лимит
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10,
)

# Инициализация MinIO
minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ROOT_USER,
    secret_key=MINIO_ROOT_PASSWORD,
    secure=False
)

BUCKET_NAME = "videos"

def setup_gpu():
    """Настройка GPU и проверка доступности"""
    try:
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory // (1024**3)
            
            logger.info(f"GPU доступен: {gpu_name} ({gpu_memory}GB VRAM)")
            logger.info(f"Количество GPU: {gpu_count}")
            
            # Устанавливаем лимит памяти если нужно
            if GPU_MEMORY_LIMIT < gpu_memory * 1024:
                torch.cuda.set_per_process_memory_fraction(GPU_MEMORY_LIMIT / (gpu_memory * 1024))
                logger.info(f"Установлен лимит GPU памяти: {GPU_MEMORY_LIMIT}MB")
            
            return True
        else:
            logger.warning("GPU недоступен, работаем на CPU")
            return False
    except Exception as e:
        logger.error(f"Ошибка настройки GPU: {e}")
        return False

def get_audio_duration(audio_file: str) -> Optional[float]:
    """Получает длительность аудиофайла в секундах"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', str(audio_file)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        logger.error(f"Ошибка получения длительности аудио: {e}")
        return None

def get_video_info(video_path: str) -> Dict[str, Any]:
    """Получает информацию о видеофайле"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Информация о формате
        format_info = data.get('format', {})
        duration = float(format_info.get('duration', 0))
        size_bytes = int(format_info.get('size', 0))
        size_mb = size_bytes / (1024 * 1024)
        
        # Информация о видеопотоке
        video_stream = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break
        
        info = {
            "duration": duration,
            "size_mb": round(size_mb, 2),
            "size_bytes": size_bytes
        }
        
        if video_stream:
            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)
            fps_str = video_stream.get('r_frame_rate', '0/1')
            
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den) if float(den) != 0 else 0
            else:
                fps = float(fps_str)
            
            info.update({
                "width": width,
                "height": height,
                "fps": round(fps, 2),
                "codec": video_stream.get('codec_name', 'unknown')
            })
        
        return info
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о видео: {e}")
        return {"error": str(e)}

def upload_to_minio(video_path: str, job_id: str) -> str:
    """Загружает готовое видео в MinIO и возвращает URL"""
    try:
        object_name = f"{job_id}/final_video.mp4"
        
        # Загружаем файл
        minio_client.fput_object(BUCKET_NAME, object_name, video_path)
        
        # Генерируем временную ссылку для скачивания (24 часа)
        download_url = minio_client.presigned_get_object(
            BUCKET_NAME, object_name, expires=timedelta(hours=24)
        )
        
        logger.info(f"Видео загружено в MinIO: {object_name}")
        return download_url
        
    except Exception as e:
        logger.error(f"Ошибка загрузки в MinIO: {e}")
        raise

def download_tts_models():
    """Скачивает модели TTS если их нет"""
    models_dir = Path("/app/models")
    code_dir = Path("/app/code")
    
    models = {
        "kokoro-v1.0.onnx": "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx",
        "voices-v1.0.bin": "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin"
    }
    
    for filename, url in models.items():
        model_path = code_dir / filename
        if not model_path.exists():
            logger.info(f"Скачиваем модель {filename}...")
            try:
                models_dir.mkdir(exist_ok=True)
                temp_path = models_dir / filename
                urllib.request.urlretrieve(url, temp_path)
                shutil.copy2(temp_path, model_path)
                logger.info(f"Модель {filename} скачана")
            except Exception as e:
                logger.error(f"Ошибка скачивания {filename}: {e}")

def cleanup_job_directory(job_dir: Path):
    """Безопасная очистка временной папки"""
    try:
        if job_dir.exists() and job_dir.is_dir():
            shutil.rmtree(job_dir)
            logger.debug(f"Очищена временная папка: {job_dir}")
    except Exception as e:
        logger.warning(f"Не удалось очистить {job_dir}: {e}")

def run_tts_stage(task_config: Dict[str, Any]) -> Dict[str, Any]:
    """Запускает TTS с переданными параметрами"""
    try:
        tts_config = task_config['tts_config']
        
        # Адаптируем tts_kokoro.py для работы с аргументами
        cmd = [
            sys.executable, "/app/code/tts_kokoro.py",
            "--text", tts_config['text'],
            "--voice", tts_config['voice'],
            "--speed", str(tts_config['speed']),
            "--output", "generated_audio.wav"
        ]
        
        logger.info(f"Запуск TTS: голос={tts_config['voice']}, скорость={tts_config['speed']}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Проверяем что файл создался
        audio_file = Path("generated_audio.wav")
        if audio_file.exists():
            duration = get_audio_duration(str(audio_file))
            logger.info(f"TTS завершен: {audio_file.name}, длительность: {duration:.1f}с")
            return {"success": True, "audio_file": str(audio_file), "duration": duration}
        else:
            return {"success": False, "error": "Audio file not created"}
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка TTS процесса: {e.stderr}")
        return {"success": False, "error": f"TTS process failed: {e.stderr}"}
    except Exception as e:
        logger.error(f"Ошибка TTS: {e}")
        return {"success": False, "error": str(e)}

def run_video_multiplication(task_config: Dict[str, Any], audio_duration: float) -> Dict[str, Any]:
    """Умножает исходное видео под длину аудио"""
    try:
        source_video = task_config['files']['video']
        video_config = task_config['video_config']
        
        # Адаптируем reverse_multiplier.py
        cmd = [
            sys.executable, "/app/code/reverse_multiplier.py",
            "--input", source_video,
            "--duration", str(audio_duration),
            "--fps", str(video_config['target_fps']),
            "--output", "multiplied_video.mp4"
        ]
        
        logger.info(f"Умножение видео: длительность={audio_duration:.1f}с, FPS={video_config['target_fps']}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        multiplied_video = Path("multiplied_video.mp4")
        if multiplied_video.exists():
            logger.info(f"Видео умножено: {multiplied_video.name}")
            return {"success": True, "video_file": str(multiplied_video)}
        else:
            return {"success": False, "error": "Multiplied video not created"}
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка умножения видео: {e.stderr}")
        return {"success": False, "error": f"Video multiplication failed: {e.stderr}"}
    except Exception as e:
        logger.error(f"Ошибка умножения видео: {e}")
        return {"success": False, "error": str(e)}

def run_final_assembly(task_config: Dict[str, Any], audio_file: str, video_file: str) -> Dict[str, Any]:
    """Финальная сборка с наложениями"""
    try:
        bg_config = task_config['background_config']
        files = task_config['files']
        
        # Адаптируем video_assembler.py
        cmd = [
            sys.executable, "/app/code/video_assembler.py",
            "--audio", audio_file,
            "--video", video_file,
            "--output", "final_video.mp4"
        ]
        
        # Добавляем фоновые файлы если есть
        if bg_config['has_bg_audio'] and 'bg_audio' in files:
            cmd.extend(["--bg-audio", files['bg_audio']])
            cmd.extend(["--bg-volume", str(bg_config['bg_volume'])])
        
        if bg_config['has_bg_image'] and 'bg_image' in files:
            cmd.extend(["--bg-image", files['bg_image']])
        
        logger.info("Финальная сборка видео")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        final_video = Path("final_video.mp4")
        if final_video.exists():
            logger.info(f"Сборка завершена: {final_video.name}")
            return {"success": True, "final_video": str(final_video)}
        else:
            return {"success": False, "error": "Final video not created"}
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка сборки: {e.stderr}")
        return {"success": False, "error": f"Assembly failed: {e.stderr}"}
    except Exception as e:
        logger.error(f"Ошибка сборки: {e}")
        return {"success": False, "error": str(e)}

@celery_app.task(name='process_video_pipeline', bind=True)
def process_video_pipeline(self, task_config: Dict[str, Any]):
    """Основная задача обработки видео"""
    job_id = task_config['job_id']
    job_dir = Path(task_config['job_dir'])
    
    # Обновляем статус
    self.update_state(state='PROGRESS', meta={'stage': 'starting', 'progress': 0})
    
    try:
        logger.info(f"Начинаем обработку задачи {job_id}")
        
        # Устанавливаем рабочую директорию
        os.chdir(job_dir)
        
        # Этап 1: TTS - генерация аудио (25% прогресса)
        self.update_state(state='PROGRESS', meta={'stage': 'tts', 'progress': 10})
        logger.info("Этап 1: Генерация аудио (TTS)")
        
        audio_result = run_tts_stage(task_config)
        if not audio_result['success']:
            return {"status": "failed", "error": f"TTS failed: {audio_result['error']}"}
        
        # Этап 2: Умножение видео под длину аудио (50% прогресса)
        self.update_state(state='PROGRESS', meta={'stage': 'video_multiplication', 'progress': 35})
        logger.info("Этап 2: Умножение видео")
        
        video_result = run_video_multiplication(task_config, audio_result['duration'])
        if not video_result['success']:
            return {"status": "failed", "error": f"Video multiplication failed: {video_result['error']}"}
        
        # Этап 3: Финальная сборка с наложениями (75% прогресса)
        self.update_state(state='PROGRESS', meta={'stage': 'assembly', 'progress': 60})
        logger.info("Этап 3: Финальная сборка")
        
        assembly_result = run_final_assembly(task_config, audio_result['audio_file'], video_result['video_file'])
        if not assembly_result['success']:
            return {"status": "failed", "error": f"Assembly failed: {assembly_result['error']}"}
        
        # Этап 4: Загрузка в облако (90% прогресса)
        self.update_state(state='PROGRESS', meta={'stage': 'upload', 'progress': 85})
        logger.info("Этап 4: Загрузка результата")
        
        download_url = upload_to_minio(assembly_result['final_video'], job_id)
        
        # Получаем информацию о готовом файле
        video_info = get_video_info(assembly_result['final_video'])
        
        # Завершение (100% прогресса)
        self.update_state(state='PROGRESS', meta={'stage': 'completed', 'progress': 100})
        
        result = {
            "status": "completed",
            "download_url": download_url,
            "video_info": video_info,
            "processing_time": time.time() - self.request.time_start if hasattr(self.request, 'time_start') else 0,
            "job_id": job_id
        }
        
        logger.info(f"Задача {job_id} завершена успешно")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка обработки {job_id}: {e}")
        return {"status": "failed", "error": str(e), "job_id": job_id}
    
    finally:
        # Очистка временных файлов
        try:
            cleanup_job_directory(job_dir)
        except Exception as e:
            logger.warning(f"Ошибка очистки {job_dir}: {e}")

@celery_app.task(name='health_check')
def health_check():
    """Проверка работоспособности воркера"""
    try:
        gpu_available = torch.cuda.is_available() if 'torch' in sys.modules else False
        
        return {
            "status": "healthy",
            "gpu_available": gpu_available,
            "timestamp": datetime.utcnow().isoformat(),
            "worker_id": os.getenv("HOSTNAME", "unknown")
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

if __name__ == "__main__":
    # Скачиваем модели при первом запуске
    download_tts_models()
    
    # Настройка GPU при запуске
    setup_gpu()
    
    # Запуск Celery worker
    logger.info("Запуск GPU Worker для Fast Video Builder")
    logger.info(f"Redis: {REDIS_URL}")
    logger.info(f"MinIO: {MINIO_URL}")
    logger.info(f"Concurrency: {WORKER_CONCURRENCY}")
    
    celery_app.start([
        'worker',
        '--loglevel=info',
        f'--concurrency={WORKER_CONCURRENCY}',
        '--pool=solo',  # Для GPU задач лучше использовать solo pool
    ])
