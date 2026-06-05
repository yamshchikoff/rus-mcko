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

## Разработка

```bash
python3 src/tutor/server.py --port 8080
```

Открыть `http://localhost:8080`, ввести API-ключ DeepSeek.

### Docker (только HTTP)

```bash
docker compose up -d
```

Сервис на `http://localhost`. Сборка и запуск в один шаг.

## Деплой на Яндекс.Облако

Размещается в `/srv/rus-mcko-deploy/`, запускается от root.

Структура:

```
/srv/rus-mcko-deploy/
  compose.yml            # деплойный композ
  traefik/
    traefik.yml          # конфиг Traefik
    data/                # сертификаты (авто)
  app/                   # git clone репозитория
```

Порядок развёртывания:

1. ВМ с Ubuntu 24.04, статический IP, домен (A-запись → IP).
2. Установи Docker (все команды от root):
   ```bash
   apt update && apt install -y docker.io
   ```
3. Создай структуру и склонируй репо:
   ```bash
   mkdir -p /srv/rus-mcko-deploy/traefik/data
   cd /srv/rus-mcko-deploy
   git clone <repo-url> app
   ```
4. Создай `/srv/rus-mcko-deploy/compose.yml`:
   ```yaml
   services:
     traefik:
       image: traefik:v3.7
       restart: always
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - /var/run/docker.sock:/var/run/docker.sock:ro
         - ./traefik/traefik.yml:/etc/traefik/traefik.yml:ro
         - ./traefik/data:/data

     app:
       build: ./app
       restart: always
       labels:
         - "traefik.enable=true"
         - "traefik.http.routers.app.rule=Host(`rusrobotrain.ru`)"
         - "traefik.http.routers.app.entrypoints=websecure"
         - "traefik.http.routers.app.tls.certresolver=letsencrypt"
         - "traefik.http.services.app.loadbalancer.server.port=8080"
   ```
5. Создай `/srv/rus-mcko-deploy/traefik/traefik.yml`:
   ```yaml
   entryPoints:
     web:
       address: ":80"
       http:
         redirections:
           entryPoint:
             to: websecure
             scheme: https
             permanent: true
     websecure:
       address: ":443"

   certificatesResolvers:
     letsencrypt:
       acme:
         email: me@yamshchikov.ru
         storage: /data/acme.json
         httpChallenge:
           entryPoint: web

   providers:
     docker:
       exposedByDefault: false
   ```
6. Запусти:
   ```bash
   cd /srv/rus-mcko-deploy
   docker compose up -d
   ```
7. Открой порты 80 и 443 в группе безопасности Яндекс.Облака.

Сервис будет доступен по `https://rusrobotrain.ru`. Traefik сам получит и будет обновлять сертификат Let's Encrypt.

## Стек

- Фронтенд: статический HTML/CSS/JS
- Бэкенд: Python (http.server)
- Модель: deepseek-v4-pro (Anthropic-совместимый API)
