"""Unit tests for NetworkCoordinator and MultiJunctionSimulationRunner."""

import pytest
from queuesense.state import ApproachState, TrafficState
from queuesense.network.coordinator import NetworkCoordinator
from queuesense.network.state import JunctionState
from queuesense.controllers.base import Phase


def test_coordinator_initialization():
    coordinator = NetworkCoordinator(["J1", "J2", "J3"])
    assert coordinator.junction_ids == ["J1", "J2", "J3"]
    assert "art_east_1" in coordinator.link_lengths


def test_coordinator_travel_time_estimation():
    coordinator = NetworkCoordinator(["J1", "J2", "J3"], speed_limit=13.9)
    tt = coordinator.estimate_travel_time("art_east_1")
    # 276.6 / 13.9 ~ 19.9s
    assert 19.0 < tt < 21.0


def test_coordinator_predict_arrivals_and_recommendation():
    coordinator = NetworkCoordinator(["J1", "J2", "J3"])

    # Setup J1 state with incoming arrival rate
    j1_approaches = {
        "west": ApproachState(queue_count=5.0, mean_wait_seconds=10.0, arrival_rate=120.0, downstream_available=True)
    }
    j1_state = JunctionState(
        junction_id="J1",
        timestamp=100.0,
        approaches=j1_approaches,
        phase=Phase.EAST_WEST,
        all_valid=True,
        downstream_blocked=False,
    )
    coordinator.update_junction_state(j1_state)

    # Setup J2 state
    j2_approaches = {
        "west": ApproachState(queue_count=2.0, mean_wait_seconds=5.0, arrival_rate=30.0, downstream_available=True)
    }
    j2_state = JunctionState(
        junction_id="J2",
        timestamp=100.0,
        approaches=j2_approaches,
        phase=Phase.EAST_WEST,
        all_valid=True,
        downstream_blocked=False,
    )
    coordinator.update_junction_state(j2_state)

    # Predicted arrivals at J2 from J1
    pred = coordinator.predict_arrivals("J1", "J2", "art_east_1")
    assert pred > 0.0

    # Recommendations
    recs = coordinator.generate_recommendations()
    assert "J1" in recs
    assert "J2" in recs
    # J2 should receive an extend_green recommendation due to predicted platoon
    assert recs["J2"]["extend_green"] is True
    assert "Coordinator: Predicted platoon arrival" in recs["J2"]["reason"]


def test_coordinator_downstream_blockage_suppression():
    coordinator = NetworkCoordinator(["J1", "J2", "J3"])

    # Setup J2 state with downstream blocked
    j2_state = JunctionState(
        junction_id="J2",
        timestamp=100.0,
        approaches={},
        phase=Phase.EAST_WEST,
        all_valid=True,
        downstream_blocked=True,
    )
    coordinator.update_junction_state(j2_state)

    recs = coordinator.generate_recommendations()
    assert recs["J2"]["extend_green"] is False
    assert "downstream exit blocked" in recs["J2"]["reason"]
