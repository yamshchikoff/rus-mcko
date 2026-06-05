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
docker build -t rus-mcko .
docker run -d --restart always -p 80:8080 rus-mcko
```

### Деплой на Яндекс.Облако

**Способ 1 — сборка прямо на ВМ (проще):**

1. Подними ВМ с Ubuntu 24.04 и зайди по SSH.
2. Установи Docker на ВМ:
   ```bash
   sudo apt update && sudo apt install -y docker.io
   sudo usermod -aG docker $USER
   # выйди и зайди заново
   ```
3. Склонируй репозиторий, собери и запусти:
   ```bash
   git clone <repo-url> rus-mcko
   cd rus-mcko
   docker build -t rus-mcko .
   docker run -d --restart always -p 80:8080 rus-mcko
   ```

**Способ 2 — через Yandex Container Registry:**

1. Установи Docker на локальной машине и на ВМ.
2. Создай реестр в Yandex Cloud: Container Registry → Create registry.
3. Настрой аутентификацию и запушь образ:
   ```bash
   docker tag rus-mcko cr.yandex/<registry-id>/rus-mcko
   docker push cr.yandex/<registry-id>/rus-mcko
   ```
4. На ВМ — скачай и запусти:
   ```bash
   docker run -d --restart always -p 80:8080 cr.yandex/<registry-id>/rus-mcko
   ```

**Способ 3 — перенос файлом:**

```bash
# на локальной машине
docker save rus-mcko | gzip > rus-mcko.tar.gz
scp rus-mcko.tar.gz user@vm:~/

# на ВМ
gunzip -c rus-mcko.tar.gz | docker load
docker run -d --restart always -p 80:8080 rus-mcko
```

Сервис будет доступен на порту 80 (HTTP). Ученику нужно открыть страницу в браузере и ввести API-ключ DeepSeek.

## Стек

- Фронтенд: статический HTML/CSS/JS
- Бэкенд: Python (http.server)
- Модель: deepseek-v4-pro (Anthropic-совместимый API)
