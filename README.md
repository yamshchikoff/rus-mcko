# Тренажёр ВПР — Русский язык, 7 класс

Тренировочные контрольные работы в формате ВПР для подготовки к переписыванию.

## Бета-версия

Первый релиз: **[v0.1.0-beta](https://gitflic.ru/ferris/rus-mcko/-/tags/v0.1.0-beta)**

## Возможности

- 15 реальных вариантов ВПР × 7 заданий (К1–К7)
- Таймер 45 минут с паузой и авто-восстановлением после перезагрузки
- ИИ-проверка ответов по официальным критериям с обратной связью
- ИИ-репетитор с опорой на учебник (Баранов, Ладыженская, 2022)
- Таблица прогресса 15×7, сохранение в браузере

## Запуск

```bash
python3 src/tutor/server.py --port 8080
```

Открыть `http://localhost:8080`, ввести API-ключ DeepSeek.

## Docker

```bash
# Сборка и запуск (HTTP + HTTPS)
docker compose up -d

# или без HTTPS — только HTTP на порту 80
docker build -t rus-mcko .
docker run -d --restart always -p 80:8080 rus-mcko
```

При запуске через `docker compose` Caddy автоматически получает сертификат Let's Encrypt для домена, указанного в `Caddyfile`. Замени `rusrobotrain.ru` на свой домен.

### Деплой на Яндекс.Облако

1. Подними ВМ с Ubuntu 24.04, зарезервируй статический IP, привяжи домен (A-запись → IP).
2. Установи Docker:
   ```bash
   sudo apt update && sudo apt install -y docker.io
   sudo usermod -aG docker $USER
   # выйди и зайди заново
   ```
3. Склонируй репозиторий, пропиши свой домен в `Caddyfile` и запусти:
   ```bash
   git clone <repo-url> rus-mcko
   cd rus-mcko
   docker compose up -d
   ```

Сервис будет доступен по `https://<домен>`. Caddy сам получит и будет обновлять сертификат Let's Encrypt.

## Стек

- Фронтенд: статический HTML/CSS/JS
- Бэкенд: Python (http.server)
- Модель: deepseek-v4-pro (Anthropic-совместимый API)
