"""Interview session timing rules resolved from launch configuration."""
from __future__ import annotations

from dataclasses import dataclass

from backend.app.models.launched_interview import LaunchedInterview

DEFAULT_SILENCE_SUBMIT_SECONDS = 10
DEFAULT_PAUSE_DURATION_SECONDS = 10
DEFAULT_MAX_PAUSES_PER_INTERVIEW = 3


@dataclass(frozen=True)
class InterviewSessionConfig:
    silence_submit_seconds: int = DEFAULT_SILENCE_SUBMIT_SECONDS
    pause_duration_seconds: int = DEFAULT_PAUSE_DURATION_SECONDS
    max_pauses_per_interview: int = DEFAULT_MAX_PAUSES_PER_INTERVIEW
    auto_advance_enabled: bool = True

    @property
    def silence_submit_ms(self) -> int:
        return self.silence_submit_seconds * 1000

    @property
    def pause_duration_ms(self) -> int:
        return self.pause_duration_seconds * 1000


def _clamp_int(value: int | None, *, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def resolve_session_config(launch: LaunchedInterview | None) -> InterviewSessionConfig:
    if not launch:
        return InterviewSessionConfig()

    return InterviewSessionConfig(
        silence_submit_seconds=_clamp_int(
            getattr(launch, "silence_submit_seconds", None),
            default=DEFAULT_SILENCE_SUBMIT_SECONDS,
            minimum=5,
            maximum=30,
        ),
        pause_duration_seconds=_clamp_int(
            getattr(launch, "pause_duration_seconds", None),
            default=DEFAULT_PAUSE_DURATION_SECONDS,
            minimum=5,
            maximum=60,
        ),
        max_pauses_per_interview=_clamp_int(
            getattr(launch, "max_pauses_per_interview", None),
            default=DEFAULT_MAX_PAUSES_PER_INTERVIEW,
            minimum=0,
            maximum=10,
        ),
    )
