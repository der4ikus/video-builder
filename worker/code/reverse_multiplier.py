#!/usr/bin/env python3
"""
Реверсный умножитель видео - адаптированная версия для Docker API
Создание длинных видео с эффектом "туда-обратно"
"""

import os
import subprocess
import glob
import json
import tempfile
import shutil
import logging
import argparse
from pathlib import Path
from typing import Optional, List
import sys
from colorama import init, Fore, Style
from config import TARGET_DURATION_MINUTES, TARGET_FPS, TARGET_RESOLUTION, LOG_LEVEL, LOG_DATE_FORMAT

# Инициализация colorama
init(autoreset=True)

def setup_logging():
    """Настройка логирования с цветами"""
    class ColoredFormatter(logging.Formatter):
        COLORS = {
            'DEBUG': Fore.CYAN,
            'INFO': Fore.GREEN,
            'WARNING': Fore.YELLOW,
            'ERROR': Fore.RED,
            'CRITICAL': Fore.MAGENTA
        }
        
        def format(self, record):
            color = self.COLORS.get(record.levelname, '')
            record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
            return super().format(record)
    
    logger = logging.getLogger('VideoMultiplier')
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = ColoredFormatter(f"{Fore.WHITE}%(asctime)s{Style.RESET_ALL} - %(name)s - %(levelname)s - %(message)s", LOG_DATE_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

logger = setup_logging()

def check_ffmpeg():
    """Проверяет наличие FFmpeg"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_nvenc_support():
    """Проверяет поддержку NVENC"""
    try:
        result = subprocess.run([
            'ffmpeg', '-hide_banner', '-encoders'
        ], capture_output=True, text=True)
        
        return 'h264_nvenc' in result.stdout
    except:
        return False

def get_video_duration(filename: str) -> Optional[float]:
    """Получает длительность видео в секундах с помощью FFprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            filename
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return duration
        else:
            return None
            
    except Exception as e:
        logger.error(f"Ошибка при получении длительности видео: {e}")
        return None

def calculate_reverse_pairs(original_duration_seconds: float, target_duration_seconds: float) -> int:
    """Рассчитывает количество пар (оригинал+реверс) для достижения целевой длительности"""
    # В реверсном режиме одна пара = 2x длительность исходного видео
    pair_duration = original_duration_seconds * 2
    repeat_count = int(target_duration_seconds / pair_duration)
    
    # Минимум 1 пара
    if repeat_count < 1:
        repeat_count = 1
    
    return repeat_count

def multiply_video_reverse(input_filename: str, output_file_path: str, repeat_count: int, target_fps: int):
    """Реверсное умножение видео: [Оригинал][Реверс][Оригинал][Реверс]..."""
    
    if not os.path.exists(input_filename):
        logger.error(f"Файл '{input_filename}' не найден!")
        return False
    
    # Проверяем поддержку NVENC
    nvenc_available = check_nvenc_support()
    
    if nvenc_available:
        logger.info("✅ NVENC поддерживается - используем аппаратное ускорение")
        video_codec = 'h264_nvenc'
        codec_params = ['-preset', 'fast', '-crf', '23']
    else:
        logger.info("⚠️  NVENC не поддерживается - используем программное кодирование")
        video_codec = 'libx264'
        codec_params = ['-preset', 'fast', '-crf', '23']
    
    logger.info(f"🔄 РЕВЕРСНОЕ умножение видео: {input_filename}")
    logger.info("Схема: [Оригинал][Реверс][Оригинал][Реверс]...")
    
    # Создаем временные файлы
    temp_dir = tempfile.gettempdir()
    temp_original = os.path.join(temp_dir, f"temp_original_{os.getpid()}.mp4")
    temp_reverse = os.path.join(temp_dir, f"temp_reverse_{os.getpid()}.mp4")
    concat_file = os.path.join(temp_dir, f"concat_list_reverse_{os.getpid()}.txt")
    
    try:
        logger.info(f"Создаем {repeat_count} пар (оригинал+реверс) с FPS {target_fps}...")
        
        # Шаг 1: Создаем оригинал в нужном размере БЕЗ АУДИО
        logger.info("Шаг 1/3: Подготавливаем оригинал...")
        original_cmd = [
            'ffmpeg',
            '-i', input_filename,
            '-vf', f'scale={TARGET_RESOLUTION}:force_original_aspect_ratio=increase,crop={TARGET_RESOLUTION}',
            '-c:v', video_codec,
        ] + codec_params + [
            '-an',  # Убираем аудиодорожку
            '-y',
            temp_original
        ]
        
        result = subprocess.run(original_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"❌ Ошибка создания оригинала: {result.stderr}")
            return False
        
        # Шаг 2: Создаем реверс БЕЗ АУДИО
        logger.info("Шаг 2/3: Создаем реверсную версию...")
        reverse_cmd = [
            'ffmpeg',
            '-i', temp_original,
            '-vf', 'reverse',
            '-c:v', video_codec,
        ] + codec_params + [
            '-an',  # Убираем аудиодорожку
            '-y',
            temp_reverse
        ]
        
        result = subprocess.run(reverse_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"❌ Ошибка создания реверса: {result.stderr}")
            return False
        
        # Шаг 3: Создаем список для склеивания
        logger.info("Шаг 3/3: Склеиваем пары...")
        
        abs_temp_original = os.path.abspath(temp_original)
        abs_temp_reverse = os.path.abspath(temp_reverse)
        
        with open(concat_file, 'w', encoding='utf-8') as f:
            for i in range(repeat_count):
                escaped_original = abs_temp_original.replace('\\', '/').replace("'", "\\'")
                escaped_reverse = abs_temp_reverse.replace('\\', '/').replace("'", "\\'")
                f.write(f"file '{escaped_original}'\n")
                f.write(f"file '{escaped_reverse}'\n")
        
        # Финальная склейка
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-r', str(target_fps),
            '-c:v', video_codec,
        ] + codec_params + [
            '-an',  # Убираем аудиодорожку
            '-movflags', '+faststart',
            '-y',
            output_file_path
        ]
        
        logger.info("Выполняем финальную склейку...")
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ Готово! Результат: {output_file_path}")
            return True
        else:
            logger.error(f"❌ Ошибка FFmpeg: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False
    
    finally:
        # Удаляем временные файлы
        for temp_file in [temp_original, temp_reverse, concat_file]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл {temp_file}: {e}")

def main():
    """Основная функция для реверсного умножения видео"""
    parser = argparse.ArgumentParser(description="Реверсный умножитель видео (Docker версия)")
    parser.add_argument("--input", required=True, help="Путь к входному видеофайлу")
    parser.add_argument("--duration", type=float, required=True, help="Целевая длительность в секундах")
    parser.add_argument("--fps", type=int, default=TARGET_FPS, help="Целевой FPS")
    parser.add_argument("--output", required=True, help="Путь к выходному файлу")
    
    args = parser.parse_args()
    
    if not check_ffmpeg():
        logger.error("FFmpeg не найден в PATH")
        return 1
    
    if not Path(args.input).exists():
        logger.error(f"Входной файл не найден: {args.input}")
        return 1
    
    # Получаем длительность исходного видео
    original_duration = get_video_duration(args.input)
    if original_duration is None:
        logger.error("Не удалось получить длительность видео")
        return 1
    
    # Рассчитываем количество пар для достижения нужной длительности
    repeat_count = calculate_reverse_pairs(original_duration, args.duration)
    
    logger.info(f"Создаем {repeat_count} пар для достижения {args.duration:.1f} сек")
    
    success = multiply_video_reverse(
        input_filename=args.input,
        output_file_path=args.output,
        repeat_count=repeat_count,
        target_fps=args.fps
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
