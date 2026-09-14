"""Canonical immutable event records and trajectory invariants."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    return value

@dataclass(frozen=True)
class TrajectoryEvent:
    seq: int
    kind: str
    actor: str
    payload: Mapping[str, Any]
    parent_seq_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.seq < 1:
            raise ValueError("seq must be a positive integer")
        object.__setattr__(self, "payload", _freeze(dict(self.payload)))
        object.__setattr__(self, "parent_seq_ids", tuple(self.parent_seq_ids))

@dataclass(frozen=True)
class Trajectory:
    trajectory_id: str
    family: int
    events: tuple[TrajectoryEvent, ...]
    last_safe_intervention_seq: int | None
    main_task_success: bool
    side_task_success: bool
    matched_control_id: str

def assert_contiguous(events: Sequence[TrajectoryEvent]) -> None:
    seqs = [event.seq for event in events]
    if seqs != list(range(1, len(events) + 1)):
        raise ValueError(f"sequence IDs must be unique and contiguous from 1; got {seqs}")
    known = set(seqs)
    for event in events:
        if any(parent not in known or parent >= event.seq for parent in event.parent_seq_ids):
            raise ValueError(f"invalid parent IDs at seq {event.seq}")

def prefix(events: Sequence[TrajectoryEvent], end_seq: int) -> tuple[TrajectoryEvent, ...]:
    return tuple(event for event in events if event.seq <= end_seq)
