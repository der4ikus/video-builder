#!/bin/bash
# Мониторинг Fast Video Builder сервисов

echo "📊 Fast Video Builder - Мониторинг"
echo "=================================="

# Функция для отображения статуса сервисов
show_services() {
    echo ""
    echo "🐳 Статус Docker контейнеров:"
    docker-compose ps
}

# Функция для отображения статистики GPU
show_gpu() {
    echo ""
    echo "🎮 Статистика GPU:"
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits | \
        while IFS=',' read -r name util mem_used mem_total temp; do
            echo "  GPU: $name"
            echo "  Использование: ${util}%"
            echo "  Память: ${mem_used}MB / ${mem_total}MB"
            echo "  Температура: ${temp}°C"
        done
    else
        echo "  ⚠️ nvidia-smi недоступен"
    fi
}

# Функция для отображения статистики API
show_api_stats() {
    echo ""
    echo "🌐 Статистика API:"
    
    # Проверяем здоровье
    if curl -s http://localhost:8000/health > /dev/null; then
        health=$(curl -s http://localhost:8000/health | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Статус: {data['status']}, Redis: {data['services']['redis']}, MinIO: {data['services']['minio']}\")")
        echo "  $health"
        
        # Статистика очереди
        queue_stats=$(curl -s http://localhost:8000/api/v1/queue/stats | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Активных задач: {data['active_tasks']}, В очереди: {data['queued_tasks']}, Воркеров: {len(data['workers'])}\")" 2>/dev/null || echo "Не удалось получить статистику очереди")
        echo "  $queue_stats"
    else
        echo "  ❌ API недоступен"
    fi
}

# Функция для отображения использования ресурсов
show_resources() {
    echo ""
    echo "💾 Использование ресурсов:"
    
    # CPU и память
    echo "  CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
    echo "  RAM: $(free -h | awk '/^Mem:/ {printf "%.1f/%.1f GB (%.0f%%)", $3/1024/1024/1024, $2/1024/1024/1024, $3/$2*100}')"
    
    # Диск
    echo "  Диск: $(df -h / | awk 'NR==2 {print $3"/"$2" ("$5")"}')"
    
    # Временные файлы
    temp_size=$(du -sh /tmp/video_jobs 2>/dev/null | cut -f1 || echo "0")
    temp_count=$(find /tmp/video_jobs -type d -name "*-*-*-*-*" 2>/dev/null | wc -l || echo "0")
    echo "  Временные файлы: $temp_size ($temp_count задач)"
}

# Функция для отображения логов
show_logs() {
    echo ""
    echo "📝 Последние логи (10 строк):"
    echo "--- API ---"
    docker-compose logs --tail=5 api | tail -5
    echo "--- Worker ---"
    docker-compose logs --tail=5 worker | tail -5
}

# Основной цикл мониторинга
if [ "$1" = "--watch" ] || [ "$1" = "-w" ]; then
    # Режим непрерывного мониторинга
    while true; do
        clear
        echo "📊 Fast Video Builder - Мониторинг (обновление каждые 5 сек)"
        echo "=================================="
        echo "Нажмите Ctrl+C для выхода"
        
        show_services
        show_gpu
        show_api_stats
        show_resources
        
        sleep 5
    done
else
    # Однократный показ статистики
    show_services
    show_gpu
    show_api_stats
    show_resources
    show_logs
    
    echo ""
    echo "💡 Полезные команды:"
    echo "  Непрерывный мониторинг: $0 --watch"
    echo "  Логи в реальном времени: docker-compose logs -f"
    echo "  Мониторинг GPU: watch -n 1 nvidia-smi"
    echo "  Статистика Docker: docker stats"
fi
