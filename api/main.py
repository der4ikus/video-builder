#!/usr/bin/env python3
"""
Fast Video Builder API Server
Принимает запросы на создание видео и отправляет их в очередь для обработки на GPU
"""

import os
import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import aiofiles
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
from minio import Minio
from minio.error import S3Error
import magic

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI(
    title="Fast Video Builder API",
    description="GPU-powered video generation service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройки из переменных окружения
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MINIO_URL = os.getenv("MINIO_URL", "minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "500")) * 1024 * 1024  # 500MB в байтах
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "3600"))  # 1 час

# Инициализация Celery
celery_app = Celery('video_api', broker=REDIS_URL)

# Инициализация MinIO
minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ROOT_USER,
    secret_key=MINIO_ROOT_PASSWORD,
    secure=False
)

# Убеждаемся что bucket существует
BUCKET_NAME = "videos"
try:
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)
        logger.info(f"Создан bucket: {BUCKET_NAME}")
except Exception as e:
    logger.error(f"Ошибка создания bucket: {e}")

# Поддерживаемые форматы файлов
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
SUPPORTED_AUDIO_FORMATS = {'.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg'}
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}

def validate_file_type(file: UploadFile, allowed_formats: set) -> bool:
    """Проверяет тип файла по расширению и MIME"""
    if not file.filename:
        return False
    
    # Проверка расширения
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_formats:
        return False
    
    return True

def get_file_size(file: UploadFile) -> int:
    """Получает размер файла"""
    file.file.seek(0, 2)  # Перемещаемся в конец файла
    size = file.file.tell()
    file.file.seek(0)  # Возвращаемся в начало
    return size

async def save_uploaded_file(job_dir: Path, file: UploadFile, filename: str) -> str:
    """Сохраняет загруженный файл"""
    file_path = job_dir / filename
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Сбрасываем позицию файла для повторного использования
    await file.seek(0)
    
    return str(file_path)

async def cleanup_job_directory(job_dir: Path):
    """Очищает временную папку задачи"""
    try:
        if job_dir.exists():
            import shutil
            shutil.rmtree(job_dir)
            logger.debug(f"Очищена папка: {job_dir}")
    except Exception as e:
        logger.warning(f"Не удалось очистить {job_dir}: {e}")

@app.get("/")
async def root():
    """Перенаправление на документацию"""
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health_check():
    """Проверка работоспособности сервиса"""
    try:
        # Проверяем Redis
        celery_app.control.ping(timeout=1)
        redis_status = "ok"
    except Exception:
        redis_status = "error"
    
    try:
        # Проверяем MinIO
        minio_client.bucket_exists(BUCKET_NAME)
        minio_status = "ok"
    except Exception:
        minio_status = "error"
    
    status = "healthy" if redis_status == "ok" and minio_status == "ok" else "unhealthy"
    
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "redis": redis_status,
            "minio": minio_status
        }
    }

@app.post("/api/v1/video/create")
async def create_video(
    background_tasks: BackgroundTasks,
    
    # Обязательные параметры
    text: str = Form(..., description="Текст для озвучки", max_length=5000),
    video: UploadFile = File(..., description="Исходное видео для умножения"),
    
    # Настройки TTS
    voice: str = Form("am_santa", description="Голос для TTS"),
    speed: float = Form(0.75, description="Скорость речи (0.5-2.0)", ge=0.5, le=2.0),
    
    # Настройки видео
    target_duration_minutes: int = Form(20, description="Целевая длительность в минутах", ge=1, le=60),
    target_fps: int = Form(16, description="Целевой FPS", ge=10, le=60),
    
    # Опциональные файлы
    bg_audio: Optional[UploadFile] = File(None, description="Фоновая музыка"),
    bg_image: Optional[UploadFile] = File(None, description="Картинка для наложения"),
    bg_volume: float = Form(0.3, description="Громкость фона (0.0-1.0)", ge=0.0, le=1.0),
):
    """Создает новую задачу на генерацию видео"""
    
    # Валидация основного видео
    if not validate_file_type(video, SUPPORTED_VIDEO_FORMATS):
        raise HTTPException(
            status_code=400, 
            detail=f"Неподдерживаемый формат видео. Поддерживаются: {', '.join(SUPPORTED_VIDEO_FORMATS)}"
        )
    
    video_size = get_file_size(video)
    if video_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Размер видео слишком большой. Максимум: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Валидация фоновых файлов
    if bg_audio and not validate_file_type(bg_audio, SUPPORTED_AUDIO_FORMATS):
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат аудио. Поддерживаются: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
        )
    
    if bg_image and not validate_file_type(bg_image, SUPPORTED_IMAGE_FORMATS):
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат изображения. Поддерживаются: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
        )
    
    # Создаем уникальную задачу
    job_id = str(uuid.uuid4())
    job_dir = Path(f"/tmp/video_jobs/{job_id}")
    job_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Сохраняем файлы
        saved_files = {}
        
        # Основное видео
        video_ext = Path(video.filename).suffix.lower()
        saved_files['video'] = await save_uploaded_file(
            job_dir, video, f"source_video{video_ext}"
        )
        
        # Фоновая музыка
        if bg_audio and bg_audio.filename:
            audio_ext = Path(bg_audio.filename).suffix.lower()
            saved_files['bg_audio'] = await save_uploaded_file(
                job_dir, bg_audio, f"bg_audio{audio_ext}"
            )
        
        # Фоновое изображение
        if bg_image and bg_image.filename:
            image_ext = Path(bg_image.filename).suffix.lower()
            saved_files['bg_image'] = await save_uploaded_file(
                job_dir, bg_image, f"bg_image{image_ext}"
            )
        
        # Сохраняем текст
        text_file = job_dir / "input.txt"
        async with aiofiles.open(text_file, 'w', encoding='utf-8') as f:
            await f.write(text)
        saved_files['text'] = str(text_file)
        
        # Создаем конфигурацию задачи
        task_config = {
            "job_id": job_id,
            "job_dir": str(job_dir),
            "files": saved_files,
            "tts_config": {
                "voice": voice,
                "speed": speed,
                "text": text
            },
            "video_config": {
                "target_duration_minutes": target_duration_minutes,
                "target_fps": target_fps
            },
            "background_config": {
                "bg_volume": bg_volume,
                "has_bg_audio": 'bg_audio' in saved_files,
                "has_bg_image": 'bg_image' in saved_files
            },
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Отправляем задачу в очередь
        celery_app.send_task(
            'process_video_pipeline',
            args=[task_config],
            task_id=job_id
        )
        
        # Планируем очистку через час если задача не завершится
        background_tasks.add_task(
            cleanup_job_after_delay, 
            job_dir, 
            delay_seconds=CLEANUP_INTERVAL
        )
        
        logger.info(f"Создана задача {job_id}: {text[:50]}...")
        
        return {
            "job_id": job_id,
            "status": "queued",
            "estimated_time_minutes": max(3, target_duration_minutes // 4),
            "config": {
                "voice": voice,
                "speed": speed,
                "target_duration": target_duration_minutes,
                "target_fps": target_fps,
                "has_bg_audio": 'bg_audio' in saved_files,
                "has_bg_image": 'bg_image' in saved_files
            },
            "created_at": task_config["created_at"]
        }
        
    except Exception as e:
        # Очищаем при ошибке
        await cleanup_job_directory(job_dir)
        logger.error(f"Ошибка создания задачи: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания задачи: {str(e)}")

@app.get("/api/v1/video/{job_id}/status")
async def get_video_status(job_id: str):
    """Получает статус задачи по ID"""
    try:
        result = celery_app.AsyncResult(job_id)
        
        response = {
            "job_id": job_id,
            "status": result.status.lower() if result.status else "unknown",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if result.status == "SUCCESS":
            response["result"] = result.result
            if "download_url" in result.result:
                response["download_url"] = result.result["download_url"]
        elif result.status == "FAILURE":
            response["error"] = str(result.result)
        elif result.status == "PENDING":
            response["status"] = "queued"
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статуса")

@app.get("/api/v1/video/{job_id}/download")
async def download_video(job_id: str):
    """Перенаправляет на скачивание готового видео"""
    try:
        result = celery_app.AsyncResult(job_id)
        
        if result.status != "SUCCESS":
            raise HTTPException(
                status_code=404, 
                detail="Видео еще не готово или задача не найдена"
            )
        
        if "download_url" not in result.result:
            raise HTTPException(
                status_code=404,
                detail="URL для скачивания не найден"
            )
        
        return RedirectResponse(url=result.result["download_url"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка скачивания {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения файла")

@app.get("/api/v1/queue/stats")
async def get_queue_stats():
    """Получает статистику очереди задач"""
    try:
        inspect = celery_app.control.inspect()
        
        # Активные задачи
        active = inspect.active()
        active_count = sum(len(tasks) for tasks in (active or {}).values())
        
        # Задачи в очереди
        reserved = inspect.reserved()
        reserved_count = sum(len(tasks) for tasks in (reserved.values() if reserved else []))
        
        return {
            "active_tasks": active_count,
            "queued_tasks": reserved_count,
            "workers": list((active or {}).keys()),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {
            "active_tasks": 0,
            "queued_tasks": 0,
            "workers": [],
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

async def cleanup_job_after_delay(job_dir: Path, delay_seconds: int):
    """Очищает папку задачи через указанное время"""
    await asyncio.sleep(delay_seconds)
    await cleanup_job_directory(job_dir)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
