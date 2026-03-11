## Frontend Integration Guide (Guess LOL)

This document explains how a frontend (React, Vue, plain JS, etc.) should integrate with the Guess LOL FastAPI WebSocket backend.

The backend WebSocket endpoint is:

- **URL**: `ws://<BACKEND_HOST>:8000/ws/{room_id}/{username}`

Replace:
- **`<BACKEND_HOST>`**: e.g. `localhost` during local dev or your deployed domain.
- **`{room_id}`**: any room identifier string (e.g. `room-1`, `abc123`).
- **`{username}`**: display name for the player (must not contain `/` or `\`).

---

## 1. WebSocket Connection Lifecycle

- **Open connection** when the player joins a room (after they choose a username + room ID).
- **Keep one WebSocket per browser tab**; reuse it for all game actions (guesses, reset).
- **Close connection** when navigating away or unmounting the game view.

Example with plain JavaScript:

```js
const roomId = "room-1";
const username = "alice";
const socket = new WebSocket(`ws://localhost:8000/ws/${roomId}/${encodeURIComponent(username)}`);

socket.onopen = () => {
  console.log("Connected to Guess LOL backend");
};

socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("Received:", message);
};

socket.onclose = () => {
  console.log("Disconnected from Guess LOL backend");
};

socket.onerror = (err) => {
  console.error("WebSocket error", err);
};
```

In a framework (e.g. React), create the socket in an effect (`useEffect`) and clean it up in the return function.

---

## 2. Message Protocol Overview

All messages are JSON with this shape:

```json
{
  "type": "<message_type>",
  "payload": { "...": "..." }
}
```

### 2.1 Client → Server

- **Guess**

```json
{
  "type": "guess",
  "payload": {
    "guess": 42
  }
}
```

- **Reset game** (only valid when the room status is `finished`)

```json
{
  "type": "reset",
  "payload": {}
}
```

- **Start game** (optional – moves room from `waiting` to `playing` so everyone knows the round has begun; if you don’t send this, the first guess also starts the game)

```json
{
  "type": "start",
  "payload": {}
}
```

### 2.2 Server → Client

The backend may send these message types:

- **`room_state`** – Current room snapshot (sent on join and after reset)
- **`player_joined`** – A player joined the room
- **`guess_result`** – Result of any player's guess
- **`game_won`** – A player guessed correctly
- **`player_left`** – A player disconnected
- **`error`** – Something went wrong (invalid payload, game already finished, etc.)

Example message:

```json
{
  "type": "guess_result",
  "payload": {
    "username": "alice",
    "guess": 42,
    "result": "too_low",
    "attempts": 3
  }
}
```

---

## 3. Detailed Server Message Shapes

### 3.1 `room_state`

Sent when you connect or after a reset:

```json
{
  "type": "room_state",
  "payload": {
    "room_id": "room-1",
    "status": "waiting", // "waiting" | "playing" | "finished"
    "players": ["alice", "bob"],
    "max_number": 100
  }
}
```

Use this to:
- Initialize or update local room UI.
- Decide whether to show the input for guesses or a "waiting for reset" view.

### 3.2 `player_joined`

```json
{
  "type": "player_joined",
  "payload": {
    "username": "bob",
    "player_count": 2
  }
}
```

Update the player list and optionally show a toast/notification.

### 3.3 `guess_result`

```json
{
  "type": "guess_result",
  "payload": {
    "username": "alice",
    "guess": 42,
    "result": "too_low", // "too_low" | "too_high" | "correct"
    "attempts": 3
  }
}
```

Recommended UX:
- Show a line in the game log (`alice guessed 42 → too_low`).
- If `username` is the local user, emphasize it visually (e.g. bold, color).

### 3.4 `game_won`

```json
{
  "type": "game_won",
  "payload": {
    "username": "alice",
    "secret": 73,
    "attempts": 5
  }
}
```

Recommended UX:
- Show a prominent banner (`alice won! Secret was 73`).
- Disable the guess input.
- Show a `Play again` button that sends a `reset` message.

### 3.5 `player_left`

```json
{
  "type": "player_left",
  "payload": {
    "username": "bob",
    "player_count": 1
  }
}
```

Update the player list and optionally show a small notification.

### 3.6 `error`

```json
{
  "type": "error",
  "payload": {
    "code": "invalid_guess",
    "message": "Guess must be between 1 and 100"
  }
}
```

Frontend should surface `payload.message` to the user in a non-intrusive way (toast, inline error).

Possible error codes include (non-exhaustive):
- `invalid_username`
- `invalid_json`
- `invalid_guess`
- `game_finished`
- `reset_not_allowed`
- `unknown_type`

---

## 4. Example Frontend State Shape

Recommended minimal state for a single-room view:

```ts
type RoomStatus = "waiting" | "playing" | "finished";

interface GuessEntry {
  username: string;
  guess: number;
  result: "too_low" | "too_high" | "correct";
  attempts: number;
}

interface GameState {
  connected: boolean;
  roomId: string;
  username: string;
  status: RoomStatus;
  players: string[];
  maxNumber: number;
  guesses: GuessEntry[];
  winner?: {
    username: string;
    secret: number;
    attempts: number;
  };
  lastError?: {
    code: string;
    message: string;
  };
}
```

Each `onmessage`:
- Parse JSON.
- Switch on `message.type`.
- Update the `GameState` accordingly.

---

## 5. Example React Hook (Pseudo-Implementation)

This is a minimalist sketch of a React hook managing the socket and state.

```tsx
import { useEffect, useRef, useState } from "react";

export function useGuessLol(roomId: string, username: string) {
  const [state, setState] = useState<GameState>({
    connected: false,
    roomId,
    username,
    status: "waiting",
    players: [],
    maxNumber: 100,
    guesses: [],
  });

  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/${roomId}/${encodeURIComponent(username)}`);
    socketRef.current = ws;

    ws.onopen = () => {
      setState((s) => ({ ...s, connected: true }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      switch (msg.type) {
        case "room_state":
          setState((s) => ({
            ...s,
            status: msg.payload.status,
            players: msg.payload.players,
            maxNumber: msg.payload.max_number,
          }));
          break;
        case "player_joined":
          setState((s) => ({
            ...s,
            players: [...s.players, msg.payload.username],
          }));
          break;
        case "guess_result":
          setState((s) => ({
            ...s,
            guesses: [
              ...s.guesses,
              {
                username: msg.payload.username,
                guess: msg.payload.guess,
                result: msg.payload.result,
                attempts: msg.payload.attempts,
              },
            ],
          }));
          break;
        case "game_won":
          setState((s) => ({
            ...s,
            status: "finished",
            winner: {
              username: msg.payload.username,
              secret: msg.payload.secret,
              attempts: msg.payload.attempts,
            },
          }));
          break;
        case "player_left":
          setState((s) => ({
            ...s,
            players: s.players.filter((p) => p !== msg.payload.username),
          }));
          break;
        case "error":
          setState((s) => ({
            ...s,
            lastError: {
              code: msg.payload.code,
              message: msg.payload.message,
            },
          }));
          break;
      }
    };

    ws.onclose = () => {
      setState((s) => ({ ...s, connected: false }));
    };

    return () => {
      ws.close();
    };
  }, [roomId, username]);

  const sendGuess = (guess: number) => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "guess", payload: { guess } }));
  };

  const sendReset = () => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "reset", payload: {} }));
  };

  return { state, sendGuess, sendReset };
}
```

The UI component can then:
- Use `state.status` to decide what controls to show.
- Render `state.guesses` as a scrolling log.
- Disable inputs when `!state.connected` or `state.status === "finished"`.

---

## 6. Local Development Setup

- **Backend**: run from the project root:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- **Frontend**:
  - Use `ws://localhost:8000` as the WebSocket base URL.
  - If running from a different origin (e.g. `http://localhost:5173`), it is already allowed by the backend CORS settings. You only need to ensure that deployed environments use the correct backend host/domain.

With this contract, you can implement the frontend in any framework while keeping the backend protocol stable.

