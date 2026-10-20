from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.controllers.base import Phase

c = QueueSenseController(
    alpha=0.4, beta=0.4, gamma=0.2,
    spillback_threshold=0.85, max_wait=90.0
)

state = TrafficState(
    timestamp=0.0,
    approaches={
        'north': ApproachState(
            queue_count=5, mean_wait_seconds=10, arrival_rate=10,
            downstream_available=True, measurement_valid=True,
        ),
        'south': ApproachState(
            queue_count=3, mean_wait_seconds=5, arrival_rate=8,
            downstream_available=True, measurement_valid=True,
        ),
        'east': ApproachState(
            queue_count=4, mean_wait_seconds=8, arrival_rate=12,
            downstream_available=True, measurement_valid=True,
        ),
        'west': ApproachState(
            queue_count=2, mean_wait_seconds=3, arrival_rate=6,
            downstream_available=True, measurement_valid=True,
        ),
    },
    all_valid=True,
)

print(f"Initial state: {c.state}, elapsed: {c.elapsed}")

# Run 10 steps � elapsed should be 10.0 after 10 steps
# With current state, NORTH_SOUTH has higher pressure, so controller selects NORTH_SOUTH
# and holds it for min_green due to safety supervisor
for i in range(10):
    action = c.step(state, step_length=1.0)
    print(f"Step {i+1}: phase={action['phase']}, elapsed={c.elapsed}")
    assert action["phase"] == Phase.NORTH_SOUTH

# The 11th step satisfies min_green and transitions to YELLOW_CLEARANCE
action = c.step(state, step_length=1.0)
print(f"Step 11: phase={action['phase']}, elapsed={c.elapsed}")
# Phase should be YELLOW_CLEARANCE when min_green is satisfied
print(f"Expected YELLOW_CLEARANCE, got {action['phase']}")