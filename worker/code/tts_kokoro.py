#!/usr/bin/env python3
"""
Kokoro TTS - Простая озвучка текста
Адаптированная версия для работы в Docker контейнере
"""

import os
import sys
import argparse
import subprocess
import tempfile
import requests
import glob
import shutil
import logging
from pathlib import Path
from colorama import init, Fore, Style
from config import *

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
    
    logger = logging.getLogger('TTS')
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = ColoredFormatter(f"{Fore.WHITE}%(asctime)s{Style.RESET_ALL} - %(name)s - %(levelname)s - %(message)s", LOG_DATE_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

logger = setup_logging()

def check_models():
    """Проверяет наличие моделей TTS"""
    model_files = ["kokoro-v1.0.onnx", "voices-v1.0.bin"]
    
    for filename in model_files:
        if not Path(filename).exists():
            logger.error(f"Модель не найдена: {filename}")
            return False
    
    return True

def validate_voice(voice_input):
    """Проверяет и возвращает голос как есть (поддерживает смешанные голоса)"""
    if not voice_input:
        return DEFAULT_VOICE
    
    # Проверяем, является ли это смешанным голосом (содержит запятую и двоеточие)
    if ',' in voice_input and ':' in voice_input:
        logger.debug(f"Обнаружен смешанный голос: {voice_input}")
        return voice_input
    
    # Обычный голос - возвращаем как есть
    return voice_input

def validate_speed(speed_input):
    """Проверяет и преобразует скорость в числовое значение"""
    if speed_input is None:
        return DEFAULT_SPEED
    
    try:
        return float(speed_input)
    except (ValueError, TypeError):
        logger.warning(f"Некорректная скорость '{speed_input}', используется {DEFAULT_SPEED}")
        return DEFAULT_SPEED

def text_to_speech(text, voice, output_file, speed):
    """
    Преобразует текст в речь с помощью kokoro-tts
    
    Args:
        text (str): Текст для озвучки
        voice (str): Голос для использования
        output_file (str): Имя выходного файла
        speed (float): Скорость речи
    """
    try:
        # Проверяем модели
        if not check_models():
            return False
        
        # Создаем временный файл с текстом
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(text)
            temp_input = temp_file.name
        
        try:
            # Запускаем kokoro-tts через python -m
            cmd = [
                sys.executable, '-m', 'kokoro_tts',
                temp_input,
                output_file,
                '--voice', voice,
                '--speed', str(speed)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                logger.debug(f"Аудио сохранено: {Path(output_file).name}, голос: {voice}, скорость: {speed}x")
                return True
            else:
                logger.error(f"Ошибка kokoro-tts: {result.stderr}")
                return False
                
        finally:
            # Удаляем временный файл
            try:
                os.unlink(temp_input)
            except:
                pass
        
    except FileNotFoundError:
        logger.error("kokoro-tts не найден. Убедитесь что пакет kokoro-tts установлен")
        return False
    except Exception as e:
        logger.error(f"Ошибка при генерации аудио: {e}")
        return False

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(
        description="Kokoro TTS - Озвучка текста (Docker версия)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python tts_kokoro.py --text "Привет мир!" --output audio.wav
  python tts_kokoro.py --text "Тест" --voice am_adam --speed 1.5
        """
    )
    
    parser.add_argument("--text", required=True, help="Текст для озвучки")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Голос (по умолчанию из config.py)")
    parser.add_argument("--speed", type=float, default=DEFAULT_SPEED, help="Скорость речи")
    parser.add_argument("--output", default="output.wav", help="Выходной файл")
    
    args = parser.parse_args()
    
    # Валидация параметров
    voice = validate_voice(args.voice)
    speed = validate_speed(args.speed)
    
    logger.info(f"Генерируем аудио: голос={voice}, скорость={speed}x")
    logger.debug(f"Текст: {args.text[:50]}{'...' if len(args.text) > 50 else ''}")
    
    # Генерируем аудио
    success = text_to_speech(args.text, voice, args.output, speed)
    
    if success:
        logger.info(f"Готово! Файл: {args.output}")
        return 0
    else:
        logger.error("Не удалось создать аудио файл")
        return 1

if __name__ == "__main__":
    sys.exit(main())
