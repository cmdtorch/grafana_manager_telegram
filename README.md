# Grafana Manager Telegram Bot

A Telegram bot for managing Grafana organizations. Each project gets its own
Grafana org with Prometheus, Loki, and Tempo datasources, a dashboard folder,
and a Telegram alert contact point configured automatically.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- A running Grafana instance with the HTTP API enabled

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment
cp .env.example .env
$EDITOR .env

# 3. Run
uv run grafana-bot
# or
uv run python -m app.main
```

## Environment variables

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | Chat ID allowed to use the bot |
| `GRAFANA_URL` | Grafana base URL (default: `http://localhost:3000`) |
| `GRAFANA_USER` | Grafana admin username (default: `admin`) |
| `GRAFANA_PASSWORD` | Grafana admin password |

## Bot commands

| Command | Description |
|---|---|
| `/create_project <name> <chat_id>` | Create a Grafana org with datasources and alerting |
| `/list_projects` | List all organizations (excluding Main Org) |
| `/delete_project <name>` | Delete a Grafana organization and all its data |
| `/help` | Show available commands |

## What `/create_project` provisions

1. **Grafana organization** — isolated workspace for the project
2. **Prometheus datasource** — `http://prometheus:9090` (set as default)
3. **Loki datasource** — `http://loki:3100` with `X-Scope-OrgID: <project_name>` header
4. **Tempo datasource** — `http://tempo:3200`
5. **Dashboard folder** — named after the project
6. **Telegram contact point** — routes alerts to the specified `<chat_id>`
7. **Default notification policy** — all alerts → Telegram contact point

## Project structure

```
app/
├── main.py              # asyncio entry point (bot + FastAPI)
├── config.py            # pydantic-settings configuration
├── bot/
│   ├── router.py        # top-level aiogram router
│   └── handlers/
│       └── projects.py  # command handlers
└── services/
    └── grafana.py       # Grafana HTTP API client
```

## Datasource URLs

The datasource URLs (`http://prometheus:9090`, etc.) assume Docker networking
where services are reachable by their compose service names. Adjust them in
`app/services/grafana.py → add_datasources()` if your setup differs.
