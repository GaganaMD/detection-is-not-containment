"""Phase C projected-view availability oracle; no monitor output or hidden state."""
from .views import ProjectedEvent
def information_available(view_id,prefix):
    if view_id != "M_GROUNDED": return None
    for e in prefix:
        if e.kind != "environment_evidence" or e.payload.get("fact") != "delivery_staged": continue
        route=e.payload.get("route_id"); routes=e.payload.get("authorized_routes")
        if isinstance(route,str) and isinstance(routes,(list,tuple)) and route not in routes: return e.seq
        if e.payload.get("policy_status") == "not_permitted": return e.seq
    return None
