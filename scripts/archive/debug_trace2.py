"""Detailed trace of elapsed accumulation issue."""
from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.controllers.base import Phase

c = QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0)

print("=== Test: Elapsed accumulation across steps ===")
state = TrafficState(
    timestamp=0.0,
    approaches={
        'north': ApproachState(queue_count=5, mean_wait_seconds=10, arrival_rate=10, downstream_available=True, measurement_valid=True),
        'south': ApproachState(queue_count=3, mean_wait_seconds=5, arrival_rate=8, downstream_available=True, measurement_valid=True),
        'east': ApproachState(queue_count=4, mean_wait_seconds=8, arrival_rate=12, downstream_available=True, measurement_valid=True),
        'west': ApproachState(queue_count=2, mean_wait_seconds=3, arrival_rate=6, downstream_available=True, measurement_valid=True),
    },
    all_valid=True,
)

# Run 15 steps and track elapsed
for i in range(15):
    action = c.step(state, step_length=1.0)
    phase_name = action['phase'].name
    duration = action['duration']
    reason = action['reason']
    elapsed = c.elapsed
    print(f"Step {i+1:2d}: phase={phase_name:12s}, duration={duration:5.1f}s, "
          f"elapsed={elapsed:4.1f}, reason={reason[:40]}")

print("\n=== Conclusion: elapsed stays at 1.0 because it resets each step ===")
print("min_green=10s is NEVER enforced in normal operation.")