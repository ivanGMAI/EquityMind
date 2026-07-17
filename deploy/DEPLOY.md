# Деплой EquityMind на сервер (рядом с foodize)

Схема та же, что у foodize на этом сервере: контейнеры публикуют порты только
на `127.0.0.1`, хостовый nginx терминирует TLS поддомена и проксирует на
loopback.

```
Интернет ──HTTPS──> хостовый nginx (443, certbot)
                        │  proxy_pass 127.0.0.1:5180
                        ▼
              equitymind-frontend (nginx-unprivileged :8080)
                        │  /api/* -> api:8000 (docker-сеть)
                        ▼
                equitymind-api (uvicorn :8000)
```

## Занятые порты на сервере

| Порт (loopback) | Кто |
|---|---|
| 8000, 8080, 5173, 5174 | foodize |
| 3000, 9090 | мониторинг foodize (grafana/prometheus) |
| **5180** | **equitymind-frontend** |
| **8020** | **equitymind-api** (отладка; наружу не проксируется) |

## Шаги

### 1. DNS

A-запись поддомена (имя скажет владелец) → IP сервера. Проверить:
`dig +short equitymind.EXAMPLE.RU`

### 2. Код на сервер

```bash
ssh <user>@<server>
cd /opt   # или где лежит foodize — кладём рядом
git clone <repo-url> equitymind && cd equitymind
```

### 3. Секреты

```bash
cp .env.example .env
nano .env   # минимум: ANTHROPIC_API_KEY или OPENROUTER_API_KEY
```

`.env` не коммитится (в .gitignore) и не попадает в образ (.dockerignore) —
он подключается только через `env_file` в compose.

### 4. Запуск контейнеров

```bash
docker compose -f docker-compose.prod.yaml up -d --build
# проверка:
curl -s http://127.0.0.1:8020/api/health   # {"status":"ok",...}
curl -sI http://127.0.0.1:5180/ | head -1  # HTTP/1.1 200 OK
docker compose -f docker-compose.prod.yaml ps   # оба healthy
```

### 5. Хостовый nginx

```bash
sudo cp deploy/nginx/equitymind.conf /etc/nginx/sites-available/equitymind.conf
sudo sed -i 's/equitymind.EXAMPLE.RU/<реальный-поддомен>/g' /etc/nginx/sites-available/equitymind.conf
sudo ln -s /etc/nginx/sites-available/equitymind.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 6. TLS (certbot уже стоит для foodize)

```bash
sudo certbot --nginx -d <реальный-поддомен>
```

Certbot сам допишет 443-блок и редирект с http.

### 7. Проверка

- `https://<поддомен>/` — открывается интерфейс
- `https://<поддомен>/api/health` — `{"status":"ok"}`
- Запустить анализ пары тикеров end-to-end

## Обновление версии

```bash
cd /opt/equitymind
git pull
docker compose -f docker-compose.prod.yaml up -d --build
```

Кэш цен и отчёты живут в bind-mount'ах (`.equitymind_cache/`, `reports/`)
и переживают пересборку.

## Заметки

- **Ограничение по сети сервера:** ghcr.io может быть недоступен (как и с
  локальной машины) — Dockerfile уже ставит uv с PyPI, ничего с ghcr.io
  не тянется. Базовые образы — с Docker Hub.
- **Jobs в памяти:** результаты анализа живут в памяти процесса api и
  пропадают при рестарте контейнера. Для текущего сценария (демо/один
  пользователь) это ок; для многопользовательского прода — Redis.
- **Ресурсы:** лимиты в compose скромные (api 1.5 CPU / 1G), чтобы не
  толкаться с foodize. Если сервер слабый и анализы тормозят — поднять.
- **Стриминг данных:** yfinance с российских IP может не работать —
  источник «Мосбиржа» (moex) основной для прода.
