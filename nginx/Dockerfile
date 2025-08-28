FROM nginx:alpine

# Копируем конфигурацию
COPY nginx.conf /etc/nginx/nginx.conf

# Создаем пользователя для безопасности
RUN adduser -D -s /bin/sh nginx || true

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
