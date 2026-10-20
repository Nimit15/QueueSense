"""Trace Controller D phase execution path."""
from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.controllers.base import Phase

# Create Controller D
c = QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0)

# Verify the config
print("=== Controller Config ===")
print(f"min_green={c.config.min_green}")
print(f"max_green={c.config.max_green}")
print(f"yellow_duration={c.config.yellow_duration}")
print(f"all_red_duration={c.config.all_red_duration}")
print(f"fixed_cycle={c.config.fixed_cycle}")

# Verify the controller state after init
print("\n=== Initial State ===")
print(f"state={c.state}")
print(f"elapsed={c.elapsed}")
print(f"_clearance_origin={c._clearance_origin}")

# Now let me trace a complete step cycle with all-clear condition
print("\n=== Phase Trace: All Clear, Starting from NORTH_SOUTH ===")
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

# Step 1: should select EAST_WEST (lower pressure: east has lower queue/wait/arrival than north)
action = c.step(state, step_length=1.0)
phase_name = action['phase'].name
duration = action['duration']
reason = action['reason']
print(f"Step 1: phase={phase_name}, duration={duration:.1f}s, reason={reason}")

# Check state after step
print(f"  After step - controller state: {c.state}, elapsed: {c.elapsed}")
print(f"  Action phase matches controller state: {action['phase'] == c.state}")

# Step 2: Now in EAST_WEST, should continue or end based on pressure
action = c.step(state, step_length=1.0)
phase_name = action['phase'].name
duration = action['duration']
reason = action['reason']
print(f"\nStep 2: phase={phase_name}, duration={duration:.1f}s, reason={reason}")
print(f"  After step - controller state: {c.state}, elapsed: {c.elapsed}")

# Step 3: Continue tracing
action = c.step(state, step_length=1.0)
phase_name = action['phase'].name
duration = action['duration']
reason = action['reason']
print(f"\nStep 3: phase={phase_name}, duration={duration:.1f}s, reason={reason}")
print(f"  After step - controller state: {c.state}, elapsed: {c.elapsed}")

# Step 4: One more step
action = c.step(state, step_length=1.0)
phase_name = action['phase'].name
duration = action['duration']
reason = action['reason']
print(f"\nStep 4: phase={phase_name}, duration={duration:.1f}s, reason={reason}")
print(f"  After step - controller state: {c.state}, elapsed: {c.elapsed}")

# Now test: what if we have all-exits-blocked?
print("\n=== Test: All-Exits-Blocked ===")
state_blocked = TrafficState(
    timestamp=0.0,
    approaches={
        'north': ApproachState(queue_count=5, mean_wait_seconds=10, arrival_rate=10, downstream_available=False, measurement_valid=True),
        'south': ApproachState(queue_count=3, mean_wait_seconds=5, arrival_rate=8, downstream_available=False, measurement_valid=True),
        'east': ApproachState(queue_count=4, mean_wait_seconds=8, arrival_rate=12, downstream_available=False, measurement_valid=True),
        'west': ApproachState(queue_count=2, mean_wait_seconds=3, arrival_rate=6, downstream_available=False, measurement_valid=True),
    },
    all_valid=True,
)

action = c.step(state_blocked, step_length=1.0)
phase_name = action['phase'].name
duration = action['duration']
reason = action['reason']
print(f"All-blocked Step 1: phase={phase_name}, duration={duration:.1f}s, reason={reason}")
print(f"  After step - controller state: {c.state}, elapsed: {c.elapsed}")

action = c.step(state_blocked, step_length=1.0)
phase_name = action['phase'].name
duration = action['duration']
reason = action['reason']
print(f"All-blocked Step 2: phase={phase_name}, duration={duration:.1f}s, reason={reason}")
print(f"  After step - controller state: {c.state}, elapsed: {c.elapsed}")

action = c.step(state_blocked, step_length=1.0)
phase_name = action['phase'].name
duration = action['duration']
reason = action['reason']
print(f"All-blocked Step 3: phase={phase_name}, duration={duration:.1f}s, reason={reason}")
print(f"  After step - controller state: {c.state}, elapsed: {c.elapsed}")

# Now test recovery: make exits available after blockage
print("\n=== Test: Recovery After Blockage ===")
state_clear = TrafficState(
    timestamp=0.0,
    approaches={
        'north': ApproachState(queue_count=5, mean_wait_seconds=10, arrival_rate=10, downstream_available=True, measurement_valid=True),
        'south': ApproachState(queue_count=3, mean_wait_seconds=5, arrival_rate=8, downstream_available=True, measurement_valid=True),
        'east': ApproachState(queue_count=4, mean_wait_seconds=8, arrival_rate=12, downstream_available=True, measurement_valid=True),
        'west': ApproachState(queue_count=2, mean_wait_seconds=3, arrival_rate=6, downstream_available=True, measurement_valid=True),
    },
    all_valid=True,
)

for i in range(5):
    action = c.step(state_clear, step_length=1.0)
    phase_name = action['phase'].name
    duration = action['duration']
    reason = action['reason']
    print(f"Recovery Step {i+1}: phase={phase_name}, duration={duration:.1f}s, reason={reason}")
    print(f"  After step - controller state: {c.state}, elapsed: {c.elapsed}")