## Guess LOL – Multiplayer Number Guessing (FastAPI)

This is a tiny backend for a multiplayer “guess the number” game, built with **FastAPI** and **WebSockets**.

I’m building this as a **teaching project** while mentoring a friend. The goal is:

- **Discipline**: ship small things regularly.
- **Confidence**: take something simple and make it feel cool.
- **Fast dopamine**: a game you can actually play with other people.

She’s doing the classic “guess a number” game in **Python CLI**. I’m doing the same idea but as a **websocket-powered backend** that we can hook a frontend to.

---

## What this backend does

- Hosts **rooms** where multiple players can connect.
- Each room has a **secret number**.
- Players send **guesses over WebSocket**.
- Server replies with `"too_low"`, `"too_high"` or `"correct"`.
- When someone guesses correctly, the server announces the **winner** and the room can be **reset** for another round.

All the actual “is the guess correct?” logic is cleanly separated in `game_engine.py`, and room / player management lives in `rooms.py`.

---

## Tech stack

- **Python 3.13+**
- **FastAPI** – API + WebSocket server
- **Uvicorn** – ASGI server
- **Pydantic v2** – request/response models and validation

---

## Running it locally

From the project root:

```bash
# Install dependencies (via uv, already configured)
uv sync

# Start the dev server
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## WebSocket API (quick version)

Endpoint:

- `ws://localhost:8000/ws/{room_id}/{username}`

Messages are always JSON:

```json
{
  "type": "<message_type>",
  "payload": { "...": "..." }
}
```

### Client → Server

- **Guess a number**

```json
{
  "type": "guess",
  "payload": { "guess": 42 }
}
```

- **Reset game** (after someone won)

```json
{
  "type": "reset",
  "payload": {}
}
```

### Server → Client (examples)

- `room_state` – initial room info and after reset  
- `guess_result` – every guess result  
- `game_won` – who won + the secret number  
- `player_joined` / `player_left` – room roster updates  
- `error` – structured errors with `code` + `message`

There’s a more detailed contract for the frontend in `docs/frontend-integration.md`.

---

## Rough project structure

```text
guesslol-backend/
  ├─ main.py              # FastAPI app + WebSocket endpoint
  ├─ rooms.py             # Room & player management
  ├─ game_engine.py       # Pure guess logic
  ├─ schemas.py           # Pydantic models / payloads
  └─ docs/
       └─ frontend-integration.md  # How the frontend should talk to this
```

---

## Ideas for future upgrades

- Add a **nice frontend** (using the docs in `docs/`) so multiple people can play in browser.
- Show **leaderboards** per room (fewest attempts, fastest guess, etc.).
- Persist rooms in **Redis** instead of in-memory for scaling.
- Add **authentication** or simple “avatars”/colors for players.

For now, the goal is simple: a small, fun backend that feels good to build and easy to reason about.

