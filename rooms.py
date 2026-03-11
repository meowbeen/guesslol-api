"""Room and player management."""

import logging
import random
from dataclasses import dataclass, field

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Default upper bound for secret number
DEFAULT_MAX_NUMBER = 100


@dataclass
class Player:
    """A player in a room (has WebSocket and game state)."""
    username: str
    ws: WebSocket
    attempts: int = 0


@dataclass
class Room:
    """A game room: players, secret number, status."""
    room_id: str
    max_number: int = DEFAULT_MAX_NUMBER
    players: list[Player] = field(default_factory=list)
    secret_number: int = 0
    status: str = "waiting"

    def __post_init__(self) -> None:
        if self.secret_number == 0:
            self.secret_number = random.randint(1, self.max_number)

    def player_usernames(self) -> list[str]:
        return [p.username for p in self.players]

    def remove_player(self, player: Player) -> None:
        self.players = [p for p in self.players if p is not player]
        logger.info("Player %s left room %s; %d players left", player.username, self.room_id, len(self.players))


# In-memory room store (can be replaced with Redis later)
rooms: dict[str, Room] = {}


def create_room(room_id: str, max_number: int = DEFAULT_MAX_NUMBER) -> Room:
    """Create a new room and register it."""
    room = Room(room_id=room_id, max_number=max_number)
    rooms[room_id] = room
    logger.info("Created room %s (max_number=%d)", room_id, max_number)
    return room


def get_room(room_id: str) -> Room | None:
    """Get room by id, or None if not found."""
    return rooms.get(room_id)


def get_or_create_room(room_id: str, max_number: int = DEFAULT_MAX_NUMBER) -> Room:
    """Get existing room or create one."""
    room = get_room(room_id)
    if room is None:
        room = create_room(room_id, max_number)
    return room


def delete_room_if_empty(room_id: str) -> None:
    """Remove room from store if it has no players."""
    room = rooms.get(room_id)
    if room and not room.players:
        del rooms[room_id]
        logger.info("Deleted empty room %s", room_id)


def reset_room(room: Room) -> None:
    """Reset room for a new game (new secret, same players)."""
    room.secret_number = random.randint(1, room.max_number)
    room.status = "waiting"
    for p in room.players:
        p.attempts = 0
    logger.info("Room %s reset; new secret in [1, %d]", room.room_id, room.max_number)
