# QueueSense
Adaptive traffic signal controller for Indian mixed traffic.

## Project Goal
Develop a low-cost, Edge-AI retrofit for traffic signals that uses queue-pressure and downstream blockage detection to optimize signal timing.

## Architecture
- Perception: YOLOv11n + Tracking
- State Estimation: Queue length, PCU-weighted flow, downstream availability
- Control: Queue-pressure + spillback-aware phase selection
- Safety: Min/max green, pedestrian protection, fixed-time fallback

## Status
- Initial environment setup.
- SUMO simulation baseline and controller logic pending.
