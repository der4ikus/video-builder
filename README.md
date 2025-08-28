# 🚀 Fast Video Builder GPU Server

**GPU-powered API для создания видео с TTS озвучкой**

## ⚡ Автоматическая установка одной командой

```bash
curl -sSL https://raw.githubusercontent.com/der4ikus/video-builder/main/install.sh | sudo bash
```

## 🎯 Что умеет

- 🎤 **TTS озвучка** - 50+ голосов (Kokoro TTS)
- 🎬 **Умножение видео** - создание длинных роликов
- 🎵 **Фоновая музыка** - автоматическое наложение
- 🖼️ **Наложение изображений** - водяные знаки
- ⚡ **GPU ускорение** - NVENC для быстрой обработки
- 💰 **Экономия** - автовыключение при простое

## 📊 Производительность RTX 3090

- **4-6 воркеров** одновременно
- **3-5 минут** на 15-минутное видео
- **~$0.15-0.25/час** на Vast.ai

## 🌐 API Пример

```python
import requests

files = {'video': open('source.mp4', 'rb')}
data = {
    'text': 'Привет! Это тестовое видео.',
    'voice': 'am_santa',
    'speed': 0.8
}

response = requests.post('http://your-server:8000/api/v1/video/create', 
                        files=files, data=data)
job_id = response.json()['job_id']
```

## 🛠️ Ручная установка

```bash
git clone https://github.com/der4ikus/video-builder.git
cd video-builder
chmod +x scripts/*.sh
./scripts/setup.sh
./scripts/start.sh
```

## 📚 Документация

- 📖 [Подробная инструкция](SETUP_GUIDE.md)
- ⚡ [Быстрый старт](QUICK_START.md)
- 🏗️ [Структура проекта](FILE_STRUCTURE.md)

## 🎭 Доступные голоса TTS

- **🇺🇸 Английские**: am_santa, am_adam, af_sarah, af_bella
- **🇬🇧 Британские**: bm_daniel, bf_emma, bm_george
- **🇪🇸 Испанские**: em_alex, ef_dora
- **🇫🇷 Французские**: ff_siwis
- **🇯🇵 Японские**: jf_alpha, jm_kumo

## 💰 Экономия на Vast.ai

- 🔍 **Spot instances** - до 50% экономии
- ⏰ **Автовыключение** - экономия 60-80%
- 📊 **Мониторинг** - отслеживание ресурсов

## 🔧 Требования

- **GPU**: NVIDIA с 8GB+ VRAM (RTX 3090/4090 рекомендуется)
- **RAM**: 16GB+ (32GB+ рекомендуется)
- **OS**: Ubuntu 20.04+ / Debian 11+
- **Storage**: 100GB+ SSD

## 📄 Лицензия

MIT License

---

⭐ **Поставьте звезду, если проект полезен!** ⭐