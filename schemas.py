"""Pydantic models for WebSocket messages and game state."""

from pydantic import BaseModel, Field


# --- Room status constants ---
ROOM_STATUS_WAITING = "waiting"
ROOM_STATUS_PLAYING = "playing"
ROOM_STATUS_FINISHED = "finished"


# --- Room / player state (for responses) ---

class PlayerInfo(BaseModel):
    """Public player info sent to clients."""
    username: str


# --- Client → Server messages ---

class GuessPayload(BaseModel):
    """Payload when client sends a guess."""
    guess: int = Field(..., ge=1, description="Guess (positive integer)")


# --- Server → Client messages ---

class PlayerJoinedPayload(BaseModel):
    username: str
    player_count: int


class GuessResultPayload(BaseModel):
    username: str
    guess: int
    result: str  # "too_high" | "too_low" | "correct"
    attempts: int


class GameWonPayload(BaseModel):
    username: str
    secret: int
    attempts: int


class PlayerLeftPayload(BaseModel):
    username: str
    player_count: int


class ErrorPayload(BaseModel):
    code: str
    message: str


class RoomStatePayload(BaseModel):
    """Current room state sent on join."""
    room_id: str
    status: str
    players: list[str]
    max_number: int
