"""Recovery prioritisation: which hazard to go and get first.

A detection list tells you where gear is. A recovery operation has finite boat
days and needs an order. This scores each hazard on four axes and explains the
score, because an unexplained number is not something anyone will act on.

    harm         what the object does if left - ghost gear keeps fishing
    ecology      how much life is around it, from OBIS records
    access       how reachable it is - depth and distance from port
    certainty    how confident the detector was

Deliberately a transparent rule, not a learned model. There is no training data
for "recovery priority", and a scoring function whose reasoning you can read
and argue with is worth more here than a number nobody can question.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

# What the object does if it is left where it is. Ghost gear scores highest
# because it keeps killing: an abandoned pot re-baits itself with whatever it
# caught last and carries on for years. A wreck is inert by comparison, though
# it may leak fuel and it snags nets.
HARM = {
    "crab_pot": 1.0,      # actively fishing, indefinitely
    "net": 1.0,           # same, and entangles larger animals
    "tyre": 0.5,          # leaches, smothers benthos, does not trap
    "plastic_debris": 0.5,
    "drum": 0.7,          # possible contents
    "ship": 0.4,          # inert, but snags gear and may leak
    "wreck": 0.4,
    "aircraft": 0.4,
    "unidentified": 0.6,  # unknown is not the same as harmless
}

BANDS = ((0.70, "HIGH"), (0.45, "MEDIUM"), (0.0, "LOW"))


@dataclass
class Risk:
    score: float
    band: str
    reasons: list[str]
    components: dict


def _ecology(bio: dict | None) -> tuple[float, str]:
    """Species richness nearby, normalised. OBIS counts partly reflect survey
    effort rather than true richness, so this ranks sites relatively."""
    if not bio or bio.get("species") is None:
        return 0.5, "no biodiversity data - assumed median"
    n = bio["species"]
    # 60 species in a 5 km box is rich for a coastal survey square
    score = min(n / 60.0, 1.0)
    return score, f"{n} species recorded within {bio.get('radius_km', 5)} km"


def _access(depth_m: float | None, port: dict | None) -> tuple[float, str]:
    """Reachability. Shallow and close scores high - it can be recovered soon."""
    if depth_m is None:
        return 0.5, "depth unknown - assumed median"
    if depth_m <= 30:
        d_score, d_txt = 1.0, f"{depth_m:.0f} m - within diver range"
    elif depth_m <= 60:
        d_score, d_txt = 0.6, f"{depth_m:.0f} m - technical dive or ROV"
    else:
        d_score, d_txt = 0.25, f"{depth_m:.0f} m - ROV only"

    if port and port.get("transit_hours") is not None:
        h = port["transit_hours"]
        p_score = 1.0 if h <= 2 else 0.6 if h <= 6 else 0.3
        d_txt += f", {h:.1f} h from {port['port']}"
    else:
        p_score = 0.5
    return (d_score + p_score) / 2, d_txt


def score_detection(cls: str, confidence: float, context) -> Risk:
    """Score one hazard. `context` is an ml.enrich.Context, or None."""
    bio = getattr(context, "biodiversity", None)
    depth = getattr(context, "depth_m", None)
    port = getattr(context, "nearest_port", None)

    harm = HARM.get(cls, 0.6)
    eco, eco_txt = _ecology(bio)
    acc, acc_txt = _access(depth, port)
    cert = float(confidence)

    # Harm and ecology decide whether it matters; access decides whether it can
    # be dealt with soon; certainty discounts the whole thing if the detection
    # is shaky. Weights are a judgement call, not a fitted result.
    total = 0.35 * harm + 0.25 * eco + 0.20 * acc + 0.20 * cert
    band = next(name for cut, name in BANDS if total >= cut)

    reasons = [
        f"{cls}: harm weight {harm:.2f}"
        + (" - continues fishing while it remains" if harm >= 1.0 else ""),
        f"ecology: {eco_txt}",
        f"access: {acc_txt}",
        f"detector confidence {cert:.0%}"
        + (" - low, verify before tasking a vessel" if cert < 0.4 else ""),
    ]
    return Risk(
        score=round(total, 3),
        band=band,
        reasons=reasons,
        components={"harm": round(harm, 2), "ecology": round(eco, 2),
                    "access": round(acc, 2), "certainty": round(cert, 2)},
    )


def to_dict(r: Risk | None) -> dict | None:
    return asdict(r) if r else None


def rank(scored: list[tuple[str, Risk]]) -> list[tuple[str, Risk]]:
    """Highest risk first - the order a recovery vessel should work in."""
    return sorted(scored, key=lambda kv: kv[1].score, reverse=True)
