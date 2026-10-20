#!/usr/bin/env python3
"""
QueueSense ICCC Smart Traffic Command Center Launcher

Starts the FastAPI server with all Stage 5 endpoints:
- /api/benchmark - 6-controller benchmark data (A, B, C, D1, D2, S)
- /api/emergency-flush - Emergency flush evaluation results
- /api/perception - Perception calibration evaluation results
- /api/passport - Junction Readiness Passport audit results
- /api/selector/* - Controller S (ContextAwareSelector) endpoints
- /video/feed - MJPEG annotated camera stream
- /ws/live - WebSocket real-time telemetry

Usage:
    python run_command_center.py --port 8000
    python run_command_center.py --host 0.0.0.0 --port 8000
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn
from queuesense.dashboard.app import app


def main():
    parser = argparse.ArgumentParser(
        description="QueueSense ICCC Smart Traffic Command Center",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_command_center.py --port 8000
  python run_command_center.py --host 0.0.0.0 --port 8000 --reload

API Endpoints:
  GET  /                    - Main ICCC Command Center UI
  GET  /api/state           - Real-time perception & controller state
  GET  /api/benchmark       - Dynamic benchmark data (6 controllers)
  GET  /api/emergency-flush - Emergency flush evaluation (Stage 3)
  GET  /api/perception      - Perception calibration (Stage 3)
  GET  /api/passport        - Junction Readiness Passport (Stage 5)
  GET  /api/selector/status - Controller S 4-regime status
  GET  /api/selector/receipts - DecisionReceipt audit trail
  GET  /video/feed          - MJPEG annotated video stream
  WS   /ws/live             - WebSocket real-time telemetry
        """
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level (default: info)"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("QueueSense ICCC Smart Traffic Command Center")
    print("=" * 70)
    print(f"Starting server on http://{args.host}:{args.port}")
    print()
    print("Available endpoints:")
    print("  GET  /                      - ICCC Command Center UI")
    print("  GET  /api/state             - Real-time telemetry")
    print("  GET  /api/benchmark         - 6-controller benchmark")
    print("  GET  /api/emergency-flush   - Emergency flush eval")
    print("  GET  /api/perception        - Perception calibration")
    print("  GET  /api/passport          - Junction Readiness Passport")
    print("  GET  /api/selector/status   - Controller S 4-regime")
    print("  GET  /video/feed            - MJPEG camera stream")
    print("  WS   /ws/live               - WebSocket telemetry")
    print("=" * 70)

    uvicorn.run(
        "queuesense.dashboard.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()