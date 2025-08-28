#!/usr/bin/env python3
"""
Финальный сборщик видео - адаптированная версия для Docker API
Склейка аудио и видео с наложениями
"""

import os
import subprocess
import json
import sys
import logging
import argparse
from pathlib import Path
from colorama import init, Fore, Style
from config import LOG_LEVEL, LOG_DATE_FORMAT, BG_AUDIO_VOLUME

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
    
    logger = logging.getLogger('VideoAssembler')
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
    """Проверяет поддержку NVENC кодеков"""
    try:
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        output = result.stdout
        
        h264_nvenc = 'h264_nvenc' in output
        hevc_nvenc = 'hevc_nvenc' in output
        
        return h264_nvenc, hevc_nvenc
    except:
        return False, False

def get_audio_duration(audio_file):
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

def assemble_video(audio_file, video_file, output_file, use_nvenc=True):
    """Склеивает аудио и видео с обрезкой видео под длину аудио"""
    
    logger.info(f"Сборка видео: {Path(audio_file).name} + {Path(video_file).name}")
    
    # Получаем длительность аудио
    audio_duration = get_audio_duration(audio_file)
    if audio_duration is None:
        return False
    
    logger.info(f"Длительность аудио: {audio_duration:.2f} сек")
    
    # Выбираем кодек
    if use_nvenc:
        h264_nvenc, hevc_nvenc = check_nvenc_support()
        if h264_nvenc:
            video_codec = 'h264_nvenc'
            logger.info(f"Используем аппаратное ускорение: {video_codec}")
        elif hevc_nvenc:
            video_codec = 'hevc_nvenc'
            logger.info(f"Используем аппаратное ускорение: {video_codec}")
        else:
            video_codec = 'libx264'
            logger.info(f"NVENC недоступен, используем: {video_codec}")
    else:
        video_codec = 'libx264'
        logger.info(f"Используем программный кодек: {video_codec}")
    
    # Команда FFmpeg для склейки с обрезкой видео
    cmd = [
        'ffmpeg', '-y',  # перезаписать выходной файл
        '-i', str(video_file),  # входное видео
        '-i', str(audio_file),  # входное аудио
        '-t', str(audio_duration),  # обрезать до длительности аудио
        '-c:v', video_codec,  # видео кодек
        '-c:a', 'aac',  # аудио кодек
        '-map', '0:v:0',  # взять видео из первого файла
        '-map', '1:a:0',  # взять аудио из второго файла
        '-shortest',  # остановить когда закончится самый короткий поток
        str(output_file)
    ]
    
    logger.info("Запуск FFmpeg...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Сборка завершена успешно: {Path(output_file).name}")
            return True
        else:
            logger.error(f"Ошибка FFmpeg: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка выполнения FFmpeg: {e}")
        return False

def add_background_music(video_file, bg_audio_file, output_file, video_duration, bg_volume=None):
    """Добавляет фоновую музыку к видео"""
    
    if bg_volume is None:
        bg_volume = BG_AUDIO_VOLUME
    
    logger.info(f"Наложение фоновой музыки: {Path(bg_audio_file).name} (громкость: {bg_volume})")
    
    # Команда FFmpeg для наложения фоновой музыки
    cmd = [
        'ffmpeg', '-y',  # перезаписать выходной файл
        '-i', str(video_file),  # входное видео с основным аудио
        '-i', str(bg_audio_file),  # фоновая музыка
        '-filter_complex', 
        f'[1:a]volume={bg_volume}[bg];[0:a][bg]amix=inputs=2:duration=first[audio]',
        '-map', '0:v',  # взять видео из первого файла
        '-map', '[audio]',  # взять смешанное аудио
        '-c:v', 'copy',  # копировать видео без перекодирования
        '-c:a', 'aac',  # кодек для аудио
        '-t', str(video_duration),  # обрезать до длительности видео
        str(output_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Фоновая музыка добавлена: {Path(output_file).name}")
            return True
        else:
            logger.error(f"Ошибка наложения фона: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при наложении фона: {e}")
        return False

def add_background_image(video_file, bg_image_file, output_file, video_duration):
    """Добавляет фоновое изображение к видео (по центру)"""
    
    logger.info(f"Наложение фонового изображения: {Path(bg_image_file).name}")
    
    # Команда FFmpeg для наложения изображения по центру
    cmd = [
        'ffmpeg', '-y',  # перезаписать выходной файл
        '-i', str(video_file),  # входное видео
        '-i', str(bg_image_file),  # фоновое изображение
        '-filter_complex', 
        '[0:v][1:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2',
        '-c:a', 'copy',  # копировать аудио без перекодирования
        '-t', str(video_duration),  # обрезать до длительности видео
        str(output_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Изображение наложено успешно: {Path(output_file).name}")
            return True
        else:
            logger.error(f"Ошибка FFmpeg при наложении изображения: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при наложении изображения: {e}")
        return False

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Финальный сборщик видео (Docker версия)")
    parser.add_argument("--audio", required=True, help="Путь к аудиофайлу")
    parser.add_argument("--video", required=True, help="Путь к видеофайлу")
    parser.add_argument("--output", required=True, help="Путь к выходному файлу")
    parser.add_argument("--bg-audio", help="Путь к фоновой музыке")
    parser.add_argument("--bg-volume", type=float, default=0.3, help="Громкость фона")
    parser.add_argument("--bg-image", help="Путь к фоновому изображению")
    
    args = parser.parse_args()
    
    if not check_ffmpeg():
        logger.error("FFmpeg не найден")
        return 1
    
    audio_file = Path(args.audio)
    video_file = Path(args.video)
    output_file = Path(args.output)
    
    if not audio_file.exists():
        logger.error(f"Аудиофайл не найден: {audio_file}")
        return 1
    
    if not video_file.exists():
        logger.error(f"Видеофайл не найден: {video_file}")
        return 1
    
    # Получаем длительность аудио для синхронизации
    audio_duration = get_audio_duration(audio_file)
    if audio_duration is None:
        logger.error("Не удалось получить длительность аудио")
        return 1
    
    h264_nvenc, hevc_nvenc = check_nvenc_support()
    use_nvenc = h264_nvenc or hevc_nvenc
    
    # Этап 1: Основная сборка (аудио + видео)
    temp_output = output_file.with_suffix('.temp.mp4')
    success = assemble_video(audio_file, video_file, temp_output, use_nvenc)
    
    if not success:
        logger.error("Ошибка при основной сборке видео")
        return 1
    
    current_video = temp_output
    
    # Этап 2: Добавляем фоновую музыку если указана
    if args.bg_audio:
        bg_audio_file = Path(args.bg_audio)
        if bg_audio_file.exists():
            logger.info("Добавление фоновой музыки")
            temp_audio = output_file.with_suffix('.audio.mp4')
            bg_success = add_background_music(current_video, bg_audio_file, temp_audio, audio_duration, args.bg_volume)
            
            if bg_success:
                logger.info("Фоновая музыка добавлена")
                try:
                    current_video.unlink()
                except:
                    pass
                current_video = temp_audio
            else:
                logger.error("Ошибка наложения фоновой музыки")
        else:
            logger.warning(f"Фоновая музыка не найдена: {bg_audio_file}")
    
    # Этап 3: Добавляем фоновое изображение если указано
    if args.bg_image:
        bg_image_file = Path(args.bg_image)
        if bg_image_file.exists():
            logger.info("Добавление фонового изображения")
            temp_image = output_file.with_suffix('.image.mp4')
            img_success = add_background_image(current_video, bg_image_file, temp_image, audio_duration)
            
            if img_success:
                logger.info("Фоновое изображение добавлено")
                try:
                    current_video.unlink()
                except:
                    pass
                current_video = temp_image
            else:
                logger.error("Ошибка наложения фонового изображения")
        else:
            logger.warning(f"Фоновое изображение не найдено: {bg_image_file}")
    
    # Финальный этап: Переименовываем в итоговый файл
    try:
        current_video.rename(output_file)
        logger.info(f"Сборка завершена: {output_file.name}")
        return 0
    except Exception as e:
        logger.error(f"Ошибка переименования файла: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
