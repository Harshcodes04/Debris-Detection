"""Tests for the ML package.

The backend suite covers the API. Nothing covered ml/ itself, which is where the
geometry and the bookkeeping live - the parts that are arithmetically right and
still wrong at the edges. That is the class of bug these look for: a port list
that only covers one coast, a registry that marks a wreck as removed, a risk
score that leaves the range when nothing is known.

Run from the repository root:

    pytest tests
"""

from __future__ import annotations

import pytest

from ml.contract import CLASSES, ContractError, Detection, validate_result
from ml.enrich import PORTS, enrich_detection, haversine_km, nearest_port
from ml.heatmap import build as build_heatmap, to_geojson
from ml.recovery import (
    INSPECT_FIRST,
    NOT_RECOVERABLE,
    ON_SITE_HOURS,
    day_plan,
    plan_recovery,
)
from ml.registry import MISSES_TO_GONE, Entry, Registry
from ml.risk import HARM, score_detection
from ml.survey import ALTITUDE_FRACTION_OF_RANGE, synthetic_track


def payload(**overrides) -> dict:
    base = {
        "image_id": "x",
        "width": 100,
        "height": 100,
        "processing_ms": 5,
        "detections": [{"class": "wreck", "confidence": 0.5, "bbox": [1, 1, 10, 10]}],
    }
    base.update(overrides)
    return base


class Context:
    """Stand-in for ml.enrich.Context, so these tests never touch the network."""

    def __init__(self, depth_m=None, biodiversity=None, nearest_port=None):
        self.depth_m = depth_m
        self.biodiversity = biodiversity
        self.nearest_port = nearest_port


# --- contract --------------------------------------------------------------

def test_valid_payload_is_accepted():
    validate_result(payload())


@pytest.mark.parametrize("detection", [
    {"class": "debris", "confidence": 0.5, "bbox": [1, 1, 10, 10]},   # not a class
    {"class": "wreck", "confidence": 1.4, "bbox": [1, 1, 10, 10]},    # out of range
    {"class": "wreck", "confidence": 0.5, "bbox": [90, 90, 50, 50]},  # past the edge
    {"class": "wreck", "confidence": 0.5, "bbox": [1, 1, 0, 10]},     # zero width
])
def test_off_contract_payloads_are_rejected(detection):
    with pytest.raises(ContractError):
        validate_result(payload(detections=[detection]))


def test_detection_survives_a_round_trip():
    d = Detection(cls="net", confidence=0.4, bbox=[1, 2, 3, 4])
    assert Detection.from_dict(d.to_dict()) == d


# --- enrichment ------------------------------------------------------------

def test_simulated_coordinates_are_refused():
    """A real depth for a place the sonar never saw is worse than no depth."""
    assert enrich_detection(12.92, 74.60, navigation_is_real=False) is None


def test_missing_coordinates_are_handled():
    assert enrich_detection(None, None, navigation_is_real=True) is None


def test_every_port_sits_within_the_indian_eez():
    outside = [n for n, (lat, lon) in PORTS.items()
               if not (6.0 <= lat <= 24.0 and 68.0 <= lon <= 94.0)]
    assert not outside


def test_no_two_ports_share_a_position():
    seen: dict[tuple[float, float], str] = {}
    for name, coords in PORTS.items():
        assert coords not in seen, f"{name} duplicates {seen.get(coords)}"
        seen[coords] = name


def test_each_port_is_its_own_nearest():
    """Catches a coordinate typo that would silently misroute a whole coast."""
    wrong = [n for n, (lat, lon) in PORTS.items() if nearest_port(lat, lon)["port"] != n]
    assert not wrong


def test_coasts_are_covered_not_just_karnataka():
    east = nearest_port(13.05, 80.35)["port"]        # off Chennai
    west = nearest_port(22.60, 69.60)["port"]        # Gulf of Kachchh
    assert east == "Chennai"
    assert nearest_port(13.05, 80.35)["distance_km"] < 50
    assert west != "Karwar"


def test_haversine_matches_a_known_distance():
    assert 590 < haversine_km((12.92, 74.80), (13.10, 80.30)) < 610


# --- risk ------------------------------------------------------------------

def test_every_contract_class_has_a_harm_weight():
    assert not [c for c in CLASSES if c not in HARM]


def test_score_stays_in_range_without_any_context():
    risk = score_detection("net", 0.5, None)
    assert 0.0 <= risk.score <= 1.0
    assert risk.band in {"HIGH", "MEDIUM", "LOW"}


def test_a_shallow_net_outranks_a_deep_wreck():
    net = score_detection("net", 0.95, Context(depth_m=8))
    wreck = score_detection("wreck", 0.30, Context(depth_m=90))
    assert net.score > wreck.score


def test_an_unknown_class_does_not_crash():
    assert 0.0 <= score_detection("something_new", 0.5, None).score <= 1.0


# --- recovery --------------------------------------------------------------

def test_every_contract_class_has_an_on_site_estimate():
    assert not [c for c in CLASSES if c not in ON_SITE_HOURS]


@pytest.mark.parametrize("depth,expected", [
    (5, "diver"), (25, "diver"), (45, "ROV"), (120, "ROV"),
])
def test_depth_chooses_the_method(depth, expected):
    assert expected in plan_recovery("H1", "net", depth_m=depth, transit_hours=1.0).method


def test_a_wreck_is_not_a_recovery_job():
    assert plan_recovery("H1", "wreck", depth_m=20, transit_hours=1.0).recoverable is False


def test_an_unidentified_object_is_inspected_before_it_is_lifted():
    plan = plan_recovery("H1", "unidentified", depth_m=20, transit_hours=1.0)
    assert plan.recoverable is False
    assert "identify" in plan.method
    assert any("ordnance" in n for n in plan.notes)


def test_a_day_plan_fits_inside_the_day():
    plans = [(plan_recovery(f"H{i}", "net", depth_m=10, transit_hours=0.5), 0.8)
             for i in range(6)]
    result = day_plan(plans, hours_available=8.0)
    assert result["hours_planned"] <= 8.0
    assert result["deferred"] == len(plans) - len(result["items"])


def test_nothing_to_recover_is_not_an_error():
    assert day_plan([], hours_available=8.0)["items"] == []


def test_classes_that_cannot_be_recovered_never_reach_a_crew():
    for cls in NOT_RECOVERABLE | INSPECT_FIRST:
        plan = plan_recovery("H1", cls, depth_m=20, transit_hours=1.0)
        assert day_plan([(plan, 0.9)], hours_available=8.0)["items"] == []


# --- registry --------------------------------------------------------------

def detection(lat: float, lon: float, cls: str = "net") -> dict:
    return {"class": cls, "confidence": 0.5, "bbox": [0, 0, 5, 5], "lat": lat, "lon": lon}


def test_the_same_object_seen_twice_is_one_entry():
    reg = Registry()
    reg.reconcile([detection(12.9231, 74.6012)], survey="S1")
    reg.reconcile([detection(12.9231, 74.6012)], survey="S2")
    assert len(reg.entries) == 1
    assert reg.entries[0].times_seen == 2


def test_objects_a_kilometre_apart_stay_separate():
    reg = Registry()
    reg.reconcile([detection(12.9231, 74.6012)], survey="S1")
    reg.reconcile([detection(12.9331, 74.6112)], survey="S2")
    assert len(reg.entries) == 2


def test_a_wreck_is_never_presumed_removed():
    """Wrecks do not drift, so a missed sighting is a miss, not a removal."""
    reg = Registry()
    reg.reconcile([detection(12.9231, 74.6012, cls="wreck")], survey="S1")
    for i in range(MISSES_TO_GONE + 2):
        reg.reconcile([], survey=f"S{i + 2}")
    assert reg.entries[0].status != "gone"


def test_gear_that_stops_appearing_is_marked_gone():
    reg = Registry()
    reg.reconcile([detection(12.9231, 74.6012)], survey="S1")
    for i in range(MISSES_TO_GONE + 1):
        reg.reconcile([], survey=f"S{i + 2}")
    assert reg.entries[0].status == "gone"


def test_detections_without_a_position_are_not_recorded():
    reg = Registry()
    reg.reconcile([detection(None, None)], survey="S1")
    assert reg.entries == []


# --- survey geometry -------------------------------------------------------

def test_altitude_follows_the_range():
    """Pinned at 12 m, a 13 m range gave an 8 degree grazing angle and sizes
    two and a half times too small."""
    nav = synthetic_track(10, slant_range_m=13.0)
    assert nav[0].altitude_m == pytest.approx(13.0 * ALTITUDE_FRACTION_OF_RANGE)


def test_the_long_standing_default_has_not_moved():
    assert synthetic_track(10, slant_range_m=75.0)[0].altitude_m == pytest.approx(12.0)


def test_an_altitude_above_the_range_images_nothing():
    with pytest.raises(ValueError):
        synthetic_track(10, slant_range_m=13.0, altitude_m=20.0)


# --- heatmap ---------------------------------------------------------------

def test_an_empty_heatmap_is_still_valid_geojson():
    geo = to_geojson(build_heatmap([]))
    assert geo["type"] == "FeatureCollection"
    assert geo["features"] == []


def test_heatmap_polygons_are_closed_and_in_range():
    entries = [Entry(hazard_id=f"H{i}", cls="net", lat=12.9231 + i * 0.0001,
                     lon=74.6012, first_seen="2026-01-10", last_seen="2026-09-01")
               for i in range(5)]
    for feature in to_geojson(build_heatmap(entries))["features"]:
        ring = feature["geometry"]["coordinates"][0]
        assert ring[0] == ring[-1], "polygon ring is not closed"
        for lon, lat in ring:
            assert -180 <= lon <= 180 and -90 <= lat <= 90
