"""
Guess LOL Backend — FastAPI WebSocket server for multiplayer number guessing.

Protocol: JSON messages.
- Client → Server: {"type": "guess", "payload": {"guess": <int>}}
- Server → Client: {"type": "<event>", "payload": {...}}
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from game_engine import evaluate_guess
from rooms import (
    Player,
    get_or_create_room,
    delete_room_if_empty,
    reset_room,
)
from schemas import (
    GuessPayload,
    RoomStatePayload,
    PlayerJoinedPayload,
    GuessResultPayload,
    GameWonPayload,
    PlayerLeftPayload,
    ErrorPayload,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- Message type constants (server → client) ---
MSG_ROOM_STATE = "room_state"
MSG_PLAYER_JOINED = "player_joined"
MSG_GUESS_RESULT = "guess_result"
MSG_GAME_WON = "game_won"
MSG_PLAYER_LEFT = "player_left"
MSG_ERROR = "error"

# Client → server
MSG_GUESS = "guess"
MSG_RESET = "reset"
MSG_START = "start"


async def _broadcast_json(players: list[Player], msg_type: str, payload: dict) -> None:
    """Send the same JSON message to all players in the list. Skip failed sends."""
    body = {"type": msg_type, "payload": payload}
    text = json.dumps(body)
    for p in players:
        try:
            await p.ws.send_text(text)
        except Exception as e:
            logger.warning("Failed to send to %s: %s", p.username, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: startup/shutdown logging."""
    logger.info("Starting Guess LOL backend")
    yield
    logger.info("Shutting down Guess LOL backend")


app = FastAPI(
    title="Guess LOL API",
    description="WebSocket server for multiplayer number guessing",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production to your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check for load balancers / monitoring."""
    return {"status": "ok"}


@app.websocket("/ws/{room_id}/{username}")
async def websocket_endpoint(ws: WebSocket, room_id: str, username: str):
    await ws.accept()

    # Validate username (non-empty, no path-like chars)
    if not username or "/" in username or "\\" in username:
        await ws.send_text(
            json.dumps({
                "type": MSG_ERROR,
                "payload": {"code": "invalid_username", "message": "Invalid username"},
            })
        )
        await ws.close()
        return

    room = get_or_create_room(room_id)
    player = Player(username=username, ws=ws)
    room.players.append(player)

    # Notify this client of current room state
    await ws.send_text(
        json.dumps({
            "type": MSG_ROOM_STATE,
            "payload": RoomStatePayload(
                room_id=room.room_id,
                status=room.status,
                players=room.player_usernames(),
                max_number=room.max_number,
            ).model_dump(),
        })
    )

    # Notify everyone (including joiner) that this player joined
    await _broadcast_json(
        room.players,
        MSG_PLAYER_JOINED,
        PlayerJoinedPayload(username=username, player_count=len(room.players)).model_dump(),
    )

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(
                    json.dumps({
                        "type": MSG_ERROR,
                        "payload": ErrorPayload(code="invalid_json", message="Invalid JSON").model_dump(),
                    })
                )
                continue

            msg_type = data.get("type")
            payload = data.get("payload") or {}

            if msg_type == MSG_GUESS:
                if room.status == "waiting":
                    room.status = "playing"
                if room.status == "finished":
                    await ws.send_text(
                        json.dumps({
                            "type": MSG_ERROR,
                            "payload": ErrorPayload(
                                code="game_finished",
                                message="Game is finished; request a reset to play again",
                            ).model_dump(),
                        })
                    )
                    continue

                try:
                    guess_payload = GuessPayload(**payload)
                except Exception as e:
                    await ws.send_text(
                        json.dumps({
                            "type": MSG_ERROR,
                            "payload": ErrorPayload(
                                code="invalid_guess",
                                message=str(e),
                            ).model_dump(),
                        })
                    )
                    continue

                guess = guess_payload.guess
                if guess < 1 or guess > room.max_number:
                    await ws.send_text(
                        json.dumps({
                            "type": MSG_ERROR,
                            "payload": ErrorPayload(
                                code="invalid_guess",
                                message=f"Guess must be between 1 and {room.max_number}",
                            ).model_dump(),
                        })
                    )
                    continue

                player.attempts += 1
                result = evaluate_guess(room.secret_number, guess)

                await _broadcast_json(
                    room.players,
                    MSG_GUESS_RESULT,
                    GuessResultPayload(
                        username=username,
                        guess=guess,
                        result=result,
                        attempts=player.attempts,
                    ).model_dump(),
                )

                if result == "correct":
                    room.status = "finished"
                    await _broadcast_json(
                        room.players,
                        MSG_GAME_WON,
                        GameWonPayload(
                            username=username,
                            secret=room.secret_number,
                            attempts=player.attempts,
                        ).model_dump(),
                    )
                    break

            elif msg_type == MSG_RESET:
                if room.status != "finished":
                    await ws.send_text(
                        json.dumps({
                            "type": MSG_ERROR,
                            "payload": ErrorPayload(
                                code="reset_not_allowed",
                                message="Can only reset when game is finished",
                            ).model_dump(),
                        })
                    )
                    continue
                reset_room(room)
                await _broadcast_json(
                    room.players,
                    MSG_ROOM_STATE,
                    RoomStatePayload(
                        room_id=room.room_id,
                        status=room.status,
                        players=room.player_usernames(),
                        max_number=room.max_number,
                    ).model_dump(),
                )

            elif msg_type == MSG_START:
                if room.status == "waiting":
                    room.status = "playing"
                    await _broadcast_json(
                        room.players,
                        MSG_ROOM_STATE,
                        RoomStatePayload(
                            room_id=room.room_id,
                            status=room.status,
                            players=room.player_usernames(),
                            max_number=room.max_number,
                        ).model_dump(),
                    )
                # If already playing or finished, no-op (no error)

            else:
                await ws.send_text(
                    json.dumps({
                        "type": MSG_ERROR,
                        "payload": ErrorPayload(
                            code="unknown_type",
                            message=f"Unknown message type: {msg_type!r}",
                        ).model_dump(),
                    })
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s in room %s", username, room_id)
    except Exception as e:
        logger.exception("Error in WebSocket for %s: %s", username, e)
    finally:
        room.remove_player(player)
        await _broadcast_json(
            room.players,
            MSG_PLAYER_LEFT,
            PlayerLeftPayload(username=username, player_count=len(room.players)).model_dump(),
        )
        delete_room_if_empty(room_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
