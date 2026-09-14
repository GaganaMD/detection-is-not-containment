"""Structural matching diagnostics for Phase A.5; no model or monitor calls."""
from __future__ import annotations
from collections import Counter
from typing import Any
from .trajectory import Trajectory

def _walk(value: Any, counter: Counter[str]) -> None:
    if isinstance(value, dict) or hasattr(value,"items"):
        for key,item in value.items():
            if key=="route_id": counter[str(item)]+=1
            _walk(item,counter)
    elif isinstance(value,(tuple,list)):
        for item in value: _walk(item,counter)

def _tool_calls(trace: Trajectory) -> list[str]: return [str(e.payload["tool"]) for e in trace.events if e.kind=="tool_called"]
def _action_types(trace: Trajectory) -> list[str]: return [str(e.payload["tool"]) for e in trace.events if e.kind=="action_proposed"]
def _reasoning(trace: Trajectory) -> list[str]: return [str(e.payload["text"]) for e in trace.events if e.kind=="reasoning"]
def _routes(trace: Trajectory) -> Counter[str]:
    counter: Counter[str]=Counter()
    for event in trace.events: _walk(event.payload,counter)
    return counter

def diagnostics(left: Trajectory, right: Trajectory, safety_seq: int=37) -> list[dict]:
    left_reasoning,right_reasoning=_reasoning(left),_reasoning(right)
    features=[
      ("event_count",len(left.events),len(right.events),"False","count equality"),
      ("event_kind_sequence",[e.kind for e in left.events],[e.kind for e in right.events],"False","exact event-kind equality"),
      ("pre_safety_canonical_sequence",[(e.kind,dict(e.payload)) for e in left.events if e.seq<safety_seq],[(e.kind,dict(e.payload)) for e in right.events if e.seq<safety_seq],"False","all canonical payloads equal before seq 37"),
      ("reasoning_event_count",len(left_reasoning),len(right_reasoning),"False","count equality"),
      ("reasoning_character_count",sum(map(len,left_reasoning)),sum(map(len,right_reasoning)),"False","same text/length"),
      ("reasoning_token_approx",sum(len(x.split()) for x in left_reasoning),sum(len(x.split()) for x in right_reasoning),"False","whitespace-token approximation"),
      ("tool_call_count",len(_tool_calls(left)),len(_tool_calls(right)),"False","count equality"),
      ("tool_name_sequence",_tool_calls(left),_tool_calls(right),"False","same ordered tools"),
      ("delivery_count",sum(1 for e in left.events if e.kind=="action_proposed" and e.payload.get("tool")=="prepare_delivery"),sum(1 for e in right.events if e.kind=="action_proposed" and e.payload.get("tool")=="prepare_delivery"),"False","count equality"),
      ("action_type_sequence",_action_types(left),_action_types(right),"False","same ordered actions"),
      ("route_identifier_frequency",dict(_routes(left)),dict(_routes(right)),"False","same route counts; identifiers are swapped in counterfactual family"),
    ]
    rows=[]
    for name,l,r,flag,note in features:
        equal=l==r
        rows.append({"pair":f"{left.trajectory_id}_vs_{right.trajectory_id}","feature":name,"B1_value":repr(l),"A2_value":repr(r),"equal":equal,"trivially_distinguishes_pre_safety":False if equal else True,"rationale":note if equal else note+"; mismatch requires review"})
    return rows
