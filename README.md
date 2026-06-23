# SSH Terminal Web App

Минималистичный SSH-терминал в браузере. Работает на телефоне и десктопе.

## Установка

```bash
pip install fastapi uvicorn paramiko websockets
```

## Запуск

```bash
cd sshterminal
python main.py
```

Открой в браузере: **http://localhost:8000**

С телефона в той же сети: **http://<IP-машины>:8000**

## Возможности

- 🔐 Аутентификация по паролю или приватному ключу (RSA / Ed25519 / ECDSA)
- 📱 Адаптивный интерфейс — работает на мобильном
- 🖥️ Полноценный xterm.js терминал с цветами и Unicode
- 🗂️ Несколько вкладок одновременно
- 💾 История последних подключений (localStorage)
- ⌨️ Мобильная панель быстрых клавиш (Ctrl+C, Tab, Esc, стрелки…)
- 📐 Auto-resize PTY при изменении размера окна

## Структура

```
sshterminal/
├── main.py      # FastAPI + WebSocket + Paramiko
└── index.html   # Фронтенд (xterm.js)
```
