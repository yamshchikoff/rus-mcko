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

На ВМ создаётся отдельный `compose.yml` на уровень выше репозитория — с Traefik и HTTPS.

Структура на ВМ:

```
~/rus-mcko/
  compose.yml            # деплойный композ
  traefik/
    traefik.yml          # конфиг Traefik
    data/                # сертификаты (авто)
  app/                   # git clone репозитория
```

1. ВМ с Ubuntu 24.04, статический IP, домен (A-запись → IP).
2. Установи Docker:
   ```bash
   sudo apt update && sudo apt install -y docker.io
   sudo usermod -aG docker $USER
   # выйди и зайди заново
   ```
3. Создай деплойную структуру:
   ```bash
   mkdir -p ~/rus-mcko/traefik/data
   cd ~/rus-mcko
   git clone <repo-url> app
   ```
4. Создай `compose.yml`:
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
5. Создай `traefik/traefik.yml` (замени `me@yamshchikov.ru` и домен):
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
   cd ~/rus-mcko
   docker compose up -d
   ```
7. Открой порты 80 и 443 в группе безопасности Яндекс.Облака.

Сервис будет доступен по `https://rusrobotrain.ru`. Traefik сам получит и будет обновлять сертификат Let's Encrypt.

## Стек

- Фронтенд: статический HTML/CSS/JS
- Бэкенд: Python (http.server)
- Модель: deepseek-v4-pro (Anthropic-совместимый API)
