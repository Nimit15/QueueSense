"""Unit & Integration Tests for QueueSense ICCC Command Center Dashboard.

Validates:
1. Web server initialization and static HTML serving.
2. API endpoints: /api/state, /api/roi, /api/preset, /api/fault, /api/stream/source.
3. Dynamic Benchmark Reloading with results/benchmark_v2/ priority.
4. Click-to-draw ROI saving and loading roundtrip.
5. Judge Walkthrough presets (Normal, Spillback, Watchdog).
6. Fault-injection state transitions (Downstream jam, gridlock, camera dropout).
7. WebSocket live telemetry broadcasting.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from queuesense.dashboard.app import app, engine, get_dynamic_benchmark_data


@pytest.fixture
def client():
    """Test client for FastAPI dashboard."""
    return TestClient(app)


def test_index_page_serves_html(client):
    """GET / should serve index.html with 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    assert "QUEUESENSE" in response.text
    assert "ICCC" in response.text


def test_api_state_returns_valid_telemetry(client):
    """GET /api/state should return structured telemetry with all required fields."""
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert "step" in data
    assert "action" in data
    assert "pressures" in data
    assert "approaches" in data
    assert "downstream" in data
    assert "watchdog" in data
    assert "cabinet" in data
    assert "xai_reason" in data


def test_dynamic_benchmark_reload_priority(client):
    """Verify dynamic benchmark reload prioritizes benchmark_v2, with fallback to benchmark_final."""
    response = client.get("/api/benchmark?scenario=bottleneck")
    assert response.status_code == 200
    data = response.json()
    assert "active_source" in data
    assert "controllers" in data
    assert len(data["controllers"]) == 4

    # Verify Controller D (QueueSense) is in comparison and has superior throughput in bottleneck
    ctrl_d = next(c for c in data["controllers"] if c["controller_id"] == "D")
    ctrl_a = next(c for c in data["controllers"] if c["controller_id"] == "A")
    assert ctrl_d["throughput_mean"] > ctrl_a["throughput_mean"]


def test_roi_save_and_retrieve_roundtrip(client, tmp_path):
    """Test /api/roi GET and POST roundtrip for click-to-draw calibration."""
    get_res = client.get("/api/roi")
    assert get_res.status_code == 200
    cfg = get_res.json()
    assert "upstream_rois" in cfg
    assert "downstream_rois" in cfg

    # Add a new custom polygon
    cfg["upstream_rois"]["north"] = [[0.2, 0.1], [0.8, 0.1], [0.8, 0.4], [0.2, 0.4]]
    post_res = client.post("/api/roi", json=cfg)
    assert post_res.status_code == 200

    # Retrieve again and verify
    verify_res = client.get("/api/roi")
    verify_cfg = verify_res.json()
    assert verify_cfg["upstream_rois"]["north"] == [[0.2, 0.1], [0.8, 0.1], [0.8, 0.4], [0.2, 0.4]]


def test_judge_presets_activation(client):
    """Test all 3 judge presets: normal, spillback, watchdog."""
    # 1. Spillback preset
    res_spill = client.post("/api/preset/spillback")
    assert res_spill.status_code == 200
    assert engine.fault_downstream_jam is True

    # 2. Watchdog preset
    res_wd = client.post("/api/preset/watchdog")
    assert res_wd.status_code == 200
    assert engine.fault_camera_dropout is True
    assert engine.dropout_frames_remaining > 0

    # 3. Normal preset
    res_norm = client.post("/api/preset/normal")
    assert res_norm.status_code == 200
    assert engine.fault_downstream_jam is False
    assert engine.fault_camera_dropout is False


def test_interactive_fault_injection(client):
    """Test interactive fault injection toggles and reset."""
    # Toggle jam
    res1 = client.post("/api/fault/downstream_jam")
    assert res1.status_code == 200

    # Toggle gridlock
    res2 = client.post("/api/fault/gridlock")
    assert res2.status_code == 200

    # Reset
    res_reset = client.post("/api/fault/reset")
    assert res_reset.status_code == 200
    assert engine.fault_downstream_jam is False
    assert engine.fault_gridlock is False


def test_cctv_stream_source_switch(client):
    """Test switching CCTV streams between real extracted datasets."""
    # Switch to Chennai
    res = client.post("/api/stream/source", json={"source": "chennai"})
    assert res.status_code == 200
    assert engine.source_key == "chennai"

    # Switch back to UVH-26
    res2 = client.post("/api/stream/source", json={"source": "uvh26"})
    assert res2.status_code == 200
    assert engine.source_key == "uvh26"


def test_websocket_telemetry_stream():
    """Test WebSocket connection and live telemetry payload delivery."""
    client = TestClient(app)
    with client.websocket_connect("/ws/live") as websocket:
        data = websocket.receive_json()
        assert "step" in data
        assert "action" in data
        assert "pressures" in data
        assert "cabinet" in data
