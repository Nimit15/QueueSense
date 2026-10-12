# Controller Design & Algorithmic Formulation

## 1. Objective
Optimize signal phase selection and duration to minimize average delay, reduce 95th-percentile waiting time, and eliminate gridlock caused by downstream spillback in mixed Indian traffic.

---

## 2. Mathematical Formulation

### 2.1 Approach Pressure Score ($P_i$)
For each approach movement $i \in \{\text{North}, \text{South}, \text{East}, \text{West}\}$:

$$P_i = \alpha \cdot \hat{Q}_i + \beta \cdot \hat{W}_i + \gamma \cdot \hat{A}_i$$

Where:
- $\hat{Q}_i$: Normalized queue burden. Calculated as $\sum_{k} \text{PCU}_k$ for all stopped vehicles on approach $i$, normalized by maximum storage capacity of the link.
  - PCU factors (IRC 106 calibrated guidelines): Two-wheelers = 0.5, Auto-rickshaws = 1.2, Cars = 1.0, Buses/Trucks = 3.0.
- $\hat{W}_i$: Normalized waiting time. Ratio of maximum vehicle waiting time on approach $i$ to the starvation cap $W_{\max}$.
- $\hat{A}_i$: Normalized arrival rate. Vehicle arrivals crossing the virtual upstream detector line per minute, normalized by saturation flow.
- Weights: $\alpha, \beta, \gamma \ge 0$ such that $\alpha + \beta + \gamma = 1$. Default values: $\alpha = 0.4$, $\beta = 0.4$, $\gamma = 0.2$.

### 2.2 Downstream Blockage Constraint (Spillback Awareness)
Let $O_{i,\text{down}}$ be the spatial occupancy of the receiving road for movement $i$:

$$\text{Eligible}(i) = \begin{cases} 
\text{True} & \text{if } O_{i,\text{down}} < \theta_{\text{spillback}} \\
\text{False} & \text{if } O_{i,\text{down}} \ge \theta_{\text{spillback}}
\end{cases}$$

Default threshold: $\theta_{\text{spillback}} = 0.85$ (85% road occupancy).

If $\text{Eligible}(i) = \text{False}$, movement $i$ is barred from receiving green, regardless of how high $P_i$ is, preventing vehicles from entering an intersection they cannot exit.

### 2.3 Starvation Guard (Fairness Constraint)
If any approach exceeds maximum waiting threshold $W_{\max}$ (default 90s) AND its downstream exit is eligible, its priority is boosted to override normal queue ranking:
$$P_i \leftarrow P_i + \Omega_{\text{starve}}$$

### 2.4 All-Exits Blocked Policy
If all candidate approaches have blocked downstream exits ($O_{i,\text{down}} \ge \theta_{\text{spillback}}$):
1. Log critical gridlock warning.
2. Hold all conflicting entries at red or service permissible non-blocking turns (e.g. free slip lanes or pedestrian crossings).
3. Wait for downstream clearance before releasing fresh vehicle queues.

---

## 3. Safety Supervisor State Machine

```
   [ GREEN PHASE ] 
          │  (Decision: End Green after T_min and criteria met)
          ▼
   [ YELLOW CLEARANCE ] (Duration: 3 - 5 seconds fixed)
          │
          ▼
   [ ALL-RED CLEARANCE ] (Duration: 1 - 2 seconds fixed)
          │
          ▼
   [ NEXT GREEN PHASE ] (Duration: Minimum 10s, Maximum 60s)
```

### Safety Rules:
1. **Minimum Green Time ($T_{\min} = 10\text{s}$):** Phase cannot terminate before 10 seconds, even if queues clear.
2. **Maximum Green Time ($T_{\max} = 60\text{s}$):** Phase must terminate after 60 seconds to prevent lane starvation.
3. **Clearance Enforced:** No green phase can start without passing through yellow and all-red clearance intervals.
4. **Heartbeat & Watchdog Fallback:** If `TrafficState.measurement_valid` is `False` for more than 3 consecutive updates (e.g. camera offline, severe occlusions), controller immediately reverts to the pre-programmed fixed-time signal plan.
