"""Pure observation projections from canonical events; no ground-truth labels are exposed."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Sequence
from .trajectory import TrajectoryEvent

VIEW_IDS = ("M_ACTION", "M_COT_ACTION", "M_GROUNDED")
ACTION_KINDS = {"action_proposed", "tool_called", "tool_result"}

@dataclass(frozen=True)
class ProjectedEvent:
    seq: int
    kind: str
    actor: str
    payload: dict[str, Any]
    parent_seq_ids: tuple[int, ...]

def project(view_id: str, events: Sequence[TrajectoryEvent]) -> tuple[ProjectedEvent, ...]:
    if view_id not in VIEW_IDS:
        raise ValueError(view_id)
    output = []
    for event in events:
        include = event.kind in ACTION_KINDS
        if view_id in {"M_COT_ACTION", "M_GROUNDED"} and event.kind == "reasoning":
            include = True
        if view_id == "M_GROUNDED" and event.kind == "environment_evidence":
            include = True
        if not include:
            continue
        payload = dict(event.payload)
        # Only grounded observation receives policy/effect evidence, and only from environment_evidence.
        if event.kind != "environment_evidence":
            payload.pop("policy_status", None)
            payload.pop("prohibited_effect", None)
        output.append(ProjectedEvent(event.seq, event.kind, event.actor, payload, event.parent_seq_ids))
    return tuple(output)
