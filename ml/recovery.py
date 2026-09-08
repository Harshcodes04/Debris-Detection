"""Retrieval planning: how long each hazard takes to recover, and in what order.

Risk says what matters. This says what it costs, which is the other half of any
real recovery decision - a high-risk target three hours away in 70 m of water
may still lose to two easy ones nearby.

Time breaks into three parts:

    transit     distance to the site, from the nearest port, at vessel speed
    setup       positioning, anchoring, putting a diver or ROV in the water,
                and the depth-dependent parts: descent, and decompression on
                the way back up
    on-site     actually freeing and lifting the object, which depends on what
                it is and how long it has been down there

The numbers below are planning estimates, not measured field data. They come
from the shape of the operation - a diver at 45 m has a fraction of the bottom
time they have at 15 m, and gear that has been down two years is grown over and
snagged. Anyone deploying this should replace them with their own crew's times.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

# Hours on site once the team is in the water, by object type.
ON_SITE_HOURS = {
    "crab_pot": 0.5,    # small, liftable by hand, usually one line to cut
    "net": 2.5,         # may be spread over tens of metres and snagged
    "tyre": 0.6,
    "plastic_debris": 0.4,
    "drum": 1.5,        # heavy, and contents unknown until inspected
    "ship": 0.0,        # not recoverable - survey and mark only
    "wreck": 0.0,
    "aircraft": 0.0,
    "unidentified": 1.0,
}

NOT_RECOVERABLE = {"ship", "wreck", "aircraft"}

SETUP_HOURS = 0.75      # positioning and getting into the water, any site


@dataclass
class Plan:
    hazard_id: str
    cls: str
    recoverable: bool
    method: str
    transit_hours: float | None
    setup_hours: float
    on_site_hours: float
    total_hours: float | None
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _method_and_penalty(depth_m: float | None) -> tuple[str, float, list[str]]:
    """Recovery method and the extra hours depth costs."""
    if depth_m is None:
        return "unknown", 0.5, ["depth unknown - allow contingency"]
    if depth_m <= 18:
        return "diver", 0.25, [f"{depth_m:.0f} m - no decompression obligation"]
    if depth_m <= 30:
        return "diver", 0.75, [f"{depth_m:.0f} m - limited bottom time, "
                               f"decompression stops on ascent"]
    if depth_m <= 60:
        return "technical diver or ROV", 2.0, [
            f"{depth_m:.0f} m - technical dive with staged decompression, "
            f"or ROV; ROV is the safer call"]
    return "ROV", 1.5, [f"{depth_m:.0f} m - beyond safe diving depth, ROV only"]


def _age_penalty(age_days: int | None) -> tuple[float, list[str]]:
    """Gear that has sat longer is grown over, buried and snagged."""
    if not age_days or age_days < 180:
        return 0.0, []
    if age_days < 730:
        return 0.5, [f"on the seabed ~{age_days // 30} months - "
                     f"expect fouling and partial burial"]
    return 1.25, [f"on the seabed over {age_days // 365} years - "
                  f"heavily fouled, may need cutting free"]


def plan_recovery(hazard_id: str, cls: str, *, depth_m: float | None = None,
                  transit_hours: float | None = None,
                  age_days: int | None = None) -> Plan:
    """Estimate the time to recover one hazard."""
    notes: list[str] = []

    if cls in NOT_RECOVERABLE:
        return Plan(hazard_id=hazard_id, cls=cls, recoverable=False,
                    method="survey and mark", transit_hours=transit_hours,
                    setup_hours=0.0, on_site_hours=0.0, total_hours=None,
                    notes=[f"a {cls} is not recoverable by a cleanup crew - "
                           f"record the position and mark it as a snag hazard"])

    method, depth_extra, depth_notes = _method_and_penalty(depth_m)
    age_extra, age_notes = _age_penalty(age_days)
    notes += depth_notes + age_notes

    on_site = ON_SITE_HOURS.get(cls, 1.0) + depth_extra + age_extra
    total = None if transit_hours is None else round(
        transit_hours * 2 + SETUP_HOURS + on_site, 2)   # transit is round trip
    if transit_hours is None:
        notes.append("no transit estimate - needs a real position")

    return Plan(hazard_id=hazard_id, cls=cls, recoverable=True, method=method,
                transit_hours=transit_hours, setup_hours=SETUP_HOURS,
                on_site_hours=round(on_site, 2), total_hours=total, notes=notes)


def day_plan(plans: list[tuple[Plan, float]], hours_available: float = 8.0
             ) -> dict:
    """Pack a working day: highest risk per hour first.

    `plans` pairs each Plan with its risk score. Ordering by risk alone sends a
    crew three hours out for one item; ordering by risk-per-hour clears more of
    what matters. Transit is charged once for the day rather than per item,
    since the vessel makes one trip.
    """
    recoverable = [(p, r) for p, r in plans if p.recoverable and p.total_hours]
    ranked = sorted(recoverable,
                    key=lambda pr: pr[1] / max(pr[0].total_hours, 0.1),
                    reverse=True)

    chosen, spent = [], 0.0
    transit_charged = False
    for p, risk in ranked:
        cost = p.setup_hours + p.on_site_hours
        if not transit_charged:
            cost += (p.transit_hours or 0) * 2
        if spent + cost > hours_available:
            continue
        chosen.append({"hazard_id": p.hazard_id, "class": p.cls,
                       "method": p.method, "hours": round(cost, 2),
                       "risk": round(risk, 3)})
        spent += cost
        transit_charged = True

    return {
        "hours_available": hours_available,
        "hours_planned": round(spent, 2),
        "items": chosen,
        "deferred": len(recoverable) - len(chosen),
        "note": "ordered by risk per hour, not risk alone - a crew clears more "
                "of what matters that way. Transit charged once for the day.",
    }
