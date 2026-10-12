# QueueSense Architecture

## 1. Overview
QueueSense is an Edge-AI traffic signal controller.

## 2. Components
- **Vision Module:** Processes camera feeds to detect and track vehicles.
- **State Estimator:** Aggregates vision data into approach metrics (queue, PCU weight, downstream blockage).
- **Controller Logic:** Evaluates phases based on queue pressure and spillback constraints.
- **Safety Supervisor:** Enforces safety constraints (min/max green, transitions).

## 3. Data Flow
Camera Input -> YOLO Detection -> Tracker -> Approach Metrics -> Controller -> Safety Supervisor -> Signal Commands (SUMO/Physical Relays)
