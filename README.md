# ⚡ CodexFlight Bot

Telegram bot que controla **Codex** (OpenAI) a través de su App Server via WebSocket JSON-RPC 2.0.

Basado en [GooseFlight Bot](https://github.com/jpalmae/gooseflight-bot) — misma arquitectura, diferente agente.

## Arquitectura

```
┌─────────────┐  polling   ┌────────────────────┐  WebSocket  ┌──────────────────┐
│   Telegram   │◄────────►│  codexflight-bot    │◄──────────►│  codex app-server │
│   Bot API    │  messages │  (aiogram 3.x)     │  JSON-RPC   │  (ws://...)       │
└─────────────┘           └────────┬───────────┘             └────────┬─────────┘
                                   │                                   │
                                   │ SQLite                            │ HTTP
                                   ▼                                   ▼
                            ┌──────────────┐                    ┌──────────────┐
                            │  bot.sqlite  │                    │  OpenAI API  │
                            └──────────────┘                    └──────────────┘
```

## Requisitos

- Python 3.12+
- Codex CLI con app-server (`codex app-server`)
- Telegram Bot Token

## Configuración

```bash
cp .env.example .env
# Editar .env con tus valores
```

### Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | — |
| `AUTHORIZED_USER_ID` | ID del usuario autorizado | — |
| `CODEX_WS_URL` | WebSocket URL del Codex App Server | `ws://localhost:8295` |
| `CODEX_SANDBOX` | Sandbox mode | `danger-full-access` |
| `CODEX_APPROVAL_POLICY` | Política de aprobaciones | `never` |
| `CODEX_PERSONALITY` | Personalidad del agente | `pragmatic` |
| `CODEX_MODEL` | Modelo a usar (vacío = default) | — |
| `CODEX_BASE_INSTRUCTIONS` | Instrucciones adicionales | — |

## Uso

### Local

```bash
# 1. Iniciar Codex App Server
codex app-server --listen ws://localhost:8295

# 2. En otra terminal, iniciar el bot
python -m app.main
```

### Docker

```bash
# Crear secret
mkdir -p secrets
echo "tu-token" > secrets/telegram_token.txt

# Levantar
docker compose up -d
```

## Comandos

| Comando | Descripción |
|---|---|
| `/start` | Iniciar bot y verificar conexión |
| `/help` | Manual de uso |
| `/status` | Estado del servidor y thread actual |
| `/new` | Crear nueva sesión (nuevo thread) |
| `/current` | Ver thread activo |
| `/threads` | Listar todos los threads |
| `/stop` | Detener respuesta en curso |

## Protocolo

El bot se comunica con Codex App Server mediante **JSON-RPC 2.0 sobre WebSocket**:

1. `thread/start` — Crea un nuevo thread con configuración
2. `turn/start` — Envía un mensaje y recibe streaming de respuesta
3. `turn/interrupt` — Detiene la respuesta actual
4. `thread/list` — Lista threads existentes

Los eventos de streaming llegan como notificaciones:
- `agentMessage/delta` — Texto incremental de la respuesta
- `turn/completed` — Turno completado
- `item/guardianApprovalReviewStarted` — Solicitud de aprobación

## Licencia

MIT
