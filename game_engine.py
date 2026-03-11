from typing import Literal

GuessResult = Literal["too_high", "too_low", "correct"]


def evaluate_guess(secret: int, guess: int) -> GuessResult:
    """Compare guess to secret number. Returns result string."""
    if guess > secret:
        return "too_high"
    if guess < secret:
        return "too_low"
    return "correct"
