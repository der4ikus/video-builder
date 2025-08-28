#!/bin/bash
# Валидация установки Fast Video Builder

set -e

echo "🔍 Fast Video Builder - Валидация установки"
echo "==========================================="

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Счетчики
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0

# Функции для тестирования
test_command() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    echo -n "  Testing $name... "
    
    if eval "$command" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

test_file() {
    local name="$1"
    local file="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    echo -n "  Checking $name... "
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} (not found: $file)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

test_directory() {
    local name="$1"
    local dir="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    echo -n "  Checking $name... "
    
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} (not found: $dir)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

test_service() {
    local name="$1"
    local service="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    echo -n "  Testing $name... "
    
    if docker-compose ps | grep -q "$service.*Up"; then
        echo -e "${GREEN}✓${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Проверяем что мы в правильной папке
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Ошибка: docker-compose.yml не найден${NC}"
    echo "Запустите скрипт из папки с Fast Video Builder"
    exit 1
fi

echo ""
echo "🔧 Проверка системных зависимостей"
echo "=================================="

test_command "Docker" "docker --version"
test_command "Docker Compose" "docker-compose --version"
test_command "FFmpeg" "ffmpeg -version"
test_command "Python 3" "python3 --version"
test_command "curl" "curl --version"
test_command "wget" "wget --version"

echo ""
echo "🎮 Проверка GPU"
echo "==============="

if command -v nvidia-smi >/dev/null 2>&1; then
    test_command "NVIDIA GPU" "nvidia-smi"
    test_command "NVIDIA Docker" "docker run --rm --gpus all nvidia/cuda:11.8-runtime-ubuntu22.04 nvidia-smi"
    
    # Показываем информацию о GPU
    echo ""
    echo "  GPU информация:"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | while read line; do
        echo "    $line"
    done
else
    echo -e "  ${YELLOW}⚠ NVIDIA GPU не найден${NC}"
fi

echo ""
echo "📁 Проверка файловой структуры"
echo "=============================="

test_directory "API папка" "api"
test_directory "Worker папка" "worker"
test_directory "Scripts папка" "scripts"
test_directory "Nginx папка" "nginx"

test_file "Docker Compose" "docker-compose.yml"
test_file "Environment example" "env.example"
test_file "API Dockerfile" "api/Dockerfile"
test_file "Worker Dockerfile" "worker/Dockerfile"
test_file "API main.py" "api/main.py"
test_file "Worker main" "worker/worker.py"

echo ""
echo "🔧 Проверка скриптов"
echo "==================="

test_file "Setup script" "scripts/setup.sh"
test_file "Start script" "scripts/start.sh"
test_file "Monitor script" "scripts/monitor.sh"
test_file "Test script" "scripts/test_api.py"
test_file "Install script" "install.sh"

# Проверяем права доступа
for script in scripts/*.sh install.sh; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            echo -e "  ${GREEN}✓${NC} $script executable"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "  ${RED}✗${NC} $script not executable"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
    fi
done

echo ""
echo "⚙️ Проверка конфигурации"
echo "======================="

if [ -f ".env" ]; then
    test_file "Environment file" ".env"
    
    # Проверяем ключевые переменные
    echo "  Checking environment variables:"
    
    source .env 2>/dev/null || true
    
    vars=("REDIS_URL" "MINIO_ROOT_USER" "API_PORT" "WORKER_REPLICAS")
    for var in "${vars[@]}"; do
        if [ -n "${!var}" ]; then
            echo -e "    ${GREEN}✓${NC} $var=${!var}"
        else
            echo -e "    ${RED}✗${NC} $var not set"
        fi
    done
else
    echo -e "  ${YELLOW}⚠ .env file not found (will use defaults)${NC}"
fi

echo ""
echo "🐳 Проверка Docker образов"
echo "========================="

# Проверяем существование образов
images=("redis:7-alpine" "minio/minio:latest")
for image in "${images[@]}"; do
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -n "  Checking $image... "
    
    if docker images | grep -q "${image%:*}"; then
        echo -e "${GREEN}✓${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠${NC} (will be pulled on start)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi
done

# Проверяем собранные образы
if docker images | grep -q "fast.*video.*builder"; then
    echo -e "  ${GREEN}✓${NC} Custom images built"
else
    echo -e "  ${YELLOW}⚠${NC} Custom images not built (run docker-compose build)"
fi

echo ""
echo "🚀 Проверка сервисов (если запущены)"
echo "==================================="

if docker-compose ps >/dev/null 2>&1; then
    services=("redis" "minio" "api" "worker")
    
    for service in "${services[@]}"; do
        test_service "$service service" "$service"
    done
    
    # Проверяем API доступность
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -n "  Testing API endpoint... "
    
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        
        # Получаем статус API
        api_status=$(curl -s http://localhost:8000/health | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        echo "    API Status: $api_status"
        
    else
        echo -e "${RED}✗${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
else
    echo -e "  ${YELLOW}⚠ Services not running${NC}"
    echo "  Run './scripts/start.sh' to start services"
fi

echo ""
echo "📊 Результаты валидации"
echo "======================"

echo "  Всего тестов: $TESTS_TOTAL"
echo -e "  Пройдено: ${GREEN}$TESTS_PASSED${NC}"
echo -e "  Провалено: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 Все проверки пройдены успешно!${NC}"
    echo -e "${GREEN}✅ Fast Video Builder готов к работе${NC}"
    
    echo ""
    echo "🚀 Следующие шаги:"
    echo "  1. Запустите сервисы: ./scripts/start.sh"
    echo "  2. Протестируйте API: python3 scripts/test_api.py"
    echo "  3. Откройте документацию: http://localhost:8000/docs"
    
    exit 0
else
    echo ""
    echo -e "${RED}❌ Обнаружены проблемы в установке${NC}"
    echo ""
    echo "🔧 Рекомендации по исправлению:"
    
    if [ $TESTS_FAILED -gt 5 ]; then
        echo "  - Запустите полную переустановку: ./install.sh"
    else
        echo "  - Проверьте отсутствующие зависимости"
        echo "  - Запустите настройку: ./scripts/setup.sh"
    fi
    
    echo "  - Проверьте логи: docker-compose logs"
    echo "  - Обратитесь к документации: README.md"
    
    exit 1
fi
