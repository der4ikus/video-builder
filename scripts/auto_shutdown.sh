#!/bin/bash
# Автоматическое выключение сервера при простое
# Для экономии средств на Vast.ai

IDLE_THRESHOLD=1800  # 30 минут простоя в секундах
LOG_FILE="/var/log/auto_shutdown.log"

# Функция логирования
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Проверяем активность API
check_api_activity() {
    # Проверяем есть ли активные задачи
    active_tasks=$(curl -s http://localhost:8000/api/v1/queue/stats 2>/dev/null | \
                  python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('active_tasks', 0))" 2>/dev/null || echo "0")
    
    queued_tasks=$(curl -s http://localhost:8000/api/v1/queue/stats 2>/dev/null | \
                  python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('queued_tasks', 0))" 2>/dev/null || echo "0")
    
    total_tasks=$((active_tasks + queued_tasks))
    echo "$total_tasks"
}

# Проверяем использование GPU
check_gpu_usage() {
    if command -v nvidia-smi &> /dev/null; then
        gpu_util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1 | tr -d ' ')
        echo "${gpu_util:-0}"
    else
        echo "0"
    fi
}

# Проверяем активные SSH соединения
check_ssh_connections() {
    ssh_count=$(who | wc -l)
    echo "$ssh_count"
}

# Основная логика
main() {
    # Файл для хранения времени последней активности
    LAST_ACTIVITY_FILE="/tmp/last_activity"
    
    # Проверяем активность
    api_tasks=$(check_api_activity)
    gpu_usage=$(check_gpu_usage)
    ssh_connections=$(check_ssh_connections)
    
    # Определяем есть ли активность
    is_active=false
    
    if [ "$api_tasks" -gt 0 ]; then
        log "Активность: $api_tasks задач в очереди"
        is_active=true
    fi
    
    if [ "$gpu_usage" -gt 10 ]; then
        log "Активность: GPU использование ${gpu_usage}%"
        is_active=true
    fi
    
    if [ "$ssh_connections" -gt 0 ]; then
        log "Активность: $ssh_connections SSH соединений"
        is_active=true
    fi
    
    # Обновляем время последней активности
    if [ "$is_active" = true ]; then
        echo "$(date +%s)" > "$LAST_ACTIVITY_FILE"
        exit 0
    fi
    
    # Проверяем как давно была активность
    if [ -f "$LAST_ACTIVITY_FILE" ]; then
        last_activity=$(cat "$LAST_ACTIVITY_FILE")
        current_time=$(date +%s)
        idle_time=$((current_time - last_activity))
        
        log "Простой: ${idle_time} секунд (лимит: ${IDLE_THRESHOLD})"
        
        if [ "$idle_time" -gt "$IDLE_THRESHOLD" ]; then
            log "ВНИМАНИЕ: Превышен лимит простоя, выключаем сервер"
            
            # Останавливаем сервисы
            cd /app 2>/dev/null || cd /root
            docker-compose down 2>/dev/null || true
            
            # Выключаем сервер (для Vast.ai)
            log "Выключение сервера..."
            shutdown -h now
        fi
    else
        # Первый запуск - создаем файл
        echo "$(date +%s)" > "$LAST_ACTIVITY_FILE"
        log "Инициализация мониторинга простоя"
    fi
}

# Запускаем только если не запущен другой экземпляр
LOCK_FILE="/tmp/auto_shutdown.lock"
if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE")
    if ps -p "$pid" > /dev/null 2>&1; then
        exit 0  # Другой экземпляр уже работает
    fi
fi

# Создаем lock файл
echo $$ > "$LOCK_FILE"

# Удаляем lock файл при выходе
trap 'rm -f "$LOCK_FILE"' EXIT

# Запускаем основную логику
main
