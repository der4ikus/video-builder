# Настройки голоса
DEFAULT_VOICE = "am_santa"  # Голос по умолчанию (поддерживает смешивание)
DEFAULT_SPEED = 0.75         # Скорость речи

# Рабочая папка (для API режима используется текущая директория)
STORY_FOLDER = "."   # Текущая папка для API режима

# Настройки видео
TARGET_DURATION_MINUTES = 20    # Целевая длительность видео в минутах
TARGET_FPS = 16                 # Целевой FPS
TARGET_RESOLUTION = "1920:1080" # Целевое разрешение

# Настройки фоновой музыки
BG_AUDIO_VOLUME = 0.3           # Громкость фоновой музыки (0.0-1.0)
BG_AUDIO_FOLDER = "bg_audio"    # Папка с фоновой музыкой

# Настройки фоновых изображений
BG_IMAGE_FOLDER = "bg_image"    # Папка с фоновыми изображениями
BG_IMAGE_POSITION = "center"    # Позиция по умолчанию: center

# Дополнительные настройки
AUTO_PLAY = False           # Автоматически воспроизводить после создания
OUTPUT_FORMAT = "wav"       # Формат выходных файлов
ENCODING = "utf-8"          # Кодировка текстовых файлов

# Настройки логирования
LOG_LEVEL = "INFO"          # Уровень логирования: DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

# Примеры смешанных голосов:
# "af_sarah:60,am_adam:40" - 60% женский + 40% мужской
# "af_bella:80,af_sarah:20" - 80% теплый + 20% универсальный
# "am_michael:70,bm_daniel:30" - 70% американский + 30% британский
