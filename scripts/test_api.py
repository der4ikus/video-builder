#!/usr/bin/env python3
"""
Тестовый клиент для Fast Video Builder API
Проверяет работоспособность всех endpoints
"""

import os
import sys
import time
import requests
import json
from pathlib import Path
from typing import Optional

# Настройки
API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")
TEST_FILES_DIR = Path(__file__).parent / "test_files"

def create_test_files():
    """Создает тестовые файлы для проверки API"""
    TEST_FILES_DIR.mkdir(exist_ok=True)
    
    # Создаем простое тестовое видео с помощью FFmpeg
    test_video = TEST_FILES_DIR / "test_video.mp4"
    if not test_video.exists():
        print("📹 Создаем тестовое видео...")
        os.system(f"""
        ffmpeg -f lavfi -i testsrc=duration=5:size=320x240:rate=30 \
               -f lavfi -i sine=frequency=1000:duration=5 \
               -c:v libx264 -c:a aac -shortest -y {test_video}
        """)
    
    # Создаем тестовое изображение
    test_image = TEST_FILES_DIR / "test_image.png"
    if not test_image.exists():
        print("🖼️ Создаем тестовое изображение...")
        os.system(f"""
        ffmpeg -f lavfi -i color=blue:size=100x100:duration=1 \
               -frames:v 1 -y {test_image}
        """)
    
    # Создаем тестовое аудио
    test_audio = TEST_FILES_DIR / "test_audio.mp3"
    if not test_audio.exists():
        print("🎵 Создаем тестовое аудио...")
        os.system(f"""
        ffmpeg -f lavfi -i sine=frequency=440:duration=3 \
               -c:a mp3 -y {test_audio}
        """)
    
    return test_video, test_image, test_audio

def check_api_health() -> bool:
    """Проверяет работоспособность API"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ API сервер работает: {health_data['status']}")
            print(f"   Redis: {health_data['services']['redis']}")
            print(f"   MinIO: {health_data['services']['minio']}")
            return health_data['status'] == 'healthy'
        else:
            print(f"❌ API недоступен: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения к API: {e}")
        return False

def check_queue_stats():
    """Проверяет статистику очереди"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/queue/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print(f"📊 Статистика очереди:")
            print(f"   Активных задач: {stats['active_tasks']}")
            print(f"   В очереди: {stats['queued_tasks']}")
            print(f"   Воркеров: {len(stats['workers'])}")
            return True
        else:
            print(f"⚠️ Не удалось получить статистику очереди: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ Ошибка получения статистики: {e}")
        return False

def create_test_video_job() -> Optional[str]:
    """Создает тестовую задачу на генерацию видео"""
    try:
        test_video, test_image, test_audio = create_test_files()
        
        # Проверяем что файлы созданы
        if not all([test_video.exists(), test_image.exists(), test_audio.exists()]):
            print("❌ Не удалось создать тестовые файлы")
            return None
        
        print("🚀 Создаем тестовую задачу...")
        
        # Подготавливаем файлы для отправки
        files = {
            'video': open(test_video, 'rb'),
            'bg_audio': open(test_audio, 'rb'),
            'bg_image': open(test_image, 'rb')
        }
        
        # Параметры задачи
        data = {
            'text': 'Это тестовое видео для проверки Fast Video Builder API. Система работает корректно!',
            'voice': 'am_santa',
            'speed': 0.8,
            'target_duration_minutes': 2,  # Короткое видео для быстрого теста
            'target_fps': 16,
            'bg_volume': 0.2
        }
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/video/create",
            files=files,
            data=data,
            timeout=30
        )
        
        # Закрываем файлы
        for file in files.values():
            file.close()
        
        if response.status_code == 200:
            job_data = response.json()
            job_id = job_data['job_id']
            print(f"✅ Задача создана: {job_id}")
            print(f"   Ожидаемое время: {job_data['estimated_time_minutes']} минут")
            return job_id
        else:
            print(f"❌ Ошибка создания задачи: HTTP {response.status_code}")
            print(f"   Ответ: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка создания задачи: {e}")
        return None

def wait_for_job_completion(job_id: str, max_wait_minutes: int = 10) -> bool:
    """Ждет завершения задачи"""
    print(f"⏳ Ожидание завершения задачи {job_id}...")
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    
    while time.time() - start_time < max_wait_seconds:
        try:
            response = requests.get(f"{API_BASE_URL}/api/v1/video/{job_id}/status", timeout=10)
            
            if response.status_code == 200:
                status_data = response.json()
                status = status_data['status']
                
                print(f"   Статус: {status}")
                
                if status == 'success' or status == 'completed':
                    print(f"✅ Задача завершена успешно!")
                    if 'download_url' in status_data:
                        print(f"   📥 Ссылка для скачивания: {status_data['download_url']}")
                    if 'result' in status_data and 'video_info' in status_data['result']:
                        info = status_data['result']['video_info']
                        print(f"   📊 Информация о видео:")
                        print(f"      Длительность: {info.get('duration', 0):.1f} сек")
                        print(f"      Размер: {info.get('size_mb', 0):.1f} МБ")
                        print(f"      Разрешение: {info.get('width', 0)}x{info.get('height', 0)}")
                    return True
                    
                elif status == 'failed' or status == 'failure':
                    print(f"❌ Задача завершилась с ошибкой")
                    if 'error' in status_data:
                        print(f"   Ошибка: {status_data['error']}")
                    return False
                    
                elif status == 'progress':
                    if 'result' in status_data and 'stage' in status_data['result']:
                        stage = status_data['result']['stage']
                        progress = status_data['result'].get('progress', 0)
                        print(f"   Этап: {stage} ({progress}%)")
                
                # Ждем перед следующей проверкой
                time.sleep(10)
                
            else:
                print(f"   ⚠️ Ошибка получения статуса: HTTP {response.status_code}")
                time.sleep(5)
                
        except Exception as e:
            print(f"   ⚠️ Ошибка проверки статуса: {e}")
            time.sleep(5)
    
    print(f"⏰ Превышено время ожидания ({max_wait_minutes} минут)")
    return False

def test_download_endpoint(job_id: str):
    """Тестирует endpoint для скачивания"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/video/{job_id}/download", timeout=10, allow_redirects=False)
        
        if response.status_code == 302:
            print(f"✅ Endpoint скачивания работает (перенаправление)")
            print(f"   Ссылка: {response.headers.get('Location', 'не найдена')}")
            return True
        elif response.status_code == 404:
            print(f"⚠️ Видео еще не готово для скачивания")
            return False
        else:
            print(f"❌ Ошибка endpoint скачивания: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования скачивания: {e}")
        return False

def cleanup_test_files():
    """Очищает тестовые файлы"""
    try:
        if TEST_FILES_DIR.exists():
            import shutil
            shutil.rmtree(TEST_FILES_DIR)
            print("🧹 Тестовые файлы очищены")
    except Exception as e:
        print(f"⚠️ Не удалось очистить тестовые файлы: {e}")

def main():
    """Основная функция тестирования"""
    print("🧪 Fast Video Builder API - Тестирование")
    print("=" * 50)
    
    # Проверяем наличие FFmpeg для создания тестовых файлов
    if os.system("ffmpeg -version > /dev/null 2>&1") != 0:
        print("❌ FFmpeg не найден. Установите FFmpeg для создания тестовых файлов")
        return 1
    
    # 1. Проверяем здоровье API
    print("\n1️⃣ Проверка работоспособности API")
    if not check_api_health():
        print("❌ API недоступен. Убедитесь что сервисы запущены")
        return 1
    
    # 2. Проверяем статистику очереди
    print("\n2️⃣ Проверка очереди задач")
    check_queue_stats()
    
    # 3. Создаем тестовую задачу
    print("\n3️⃣ Создание тестовой задачи")
    job_id = create_test_video_job()
    if not job_id:
        print("❌ Не удалось создать тестовую задачу")
        return 1
    
    # 4. Ждем завершения
    print("\n4️⃣ Ожидание завершения обработки")
    success = wait_for_job_completion(job_id, max_wait_minutes=15)
    
    # 5. Тестируем скачивание
    if success:
        print("\n5️⃣ Тестирование скачивания")
        test_download_endpoint(job_id)
    
    # 6. Очищаем тестовые файлы
    print("\n6️⃣ Очистка")
    cleanup_test_files()
    
    # Итоги
    print("\n" + "=" * 50)
    if success:
        print("🎉 Все тесты пройдены успешно!")
        print("✅ Fast Video Builder API готов к работе")
        return 0
    else:
        print("❌ Некоторые тесты не пройдены")
        print("🔍 Проверьте логи сервисов: docker-compose logs")
        return 1

if __name__ == "__main__":
    sys.exit(main())
