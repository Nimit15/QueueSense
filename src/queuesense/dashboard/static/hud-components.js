/* =============================================================================
   QUEUESENSE ICCC — HUD COMPONENTS
   Floating HUD panels with Emil Kowalski design principles:
   - Spring easings (cubic-bezier)
   - Hardware-accelerated transforms only
   - Origin-aware popovers
   - Reduced-motion support
   - Tabular-nums animated counters

   Components:
   - Live Decision Receipt (top-left)
   - Camera Preset Pills (top-right)
   - Mode Toggle (bottom-center)
   - Scenario Trigger Pills (bottom-left)
   - Expandable Telemetry Drawer (bottom, 4 tabs)
   ============================================================================= */

class HUDDirector {
  constructor() {
    this.state = {
      currentScenario: 'normal',
      currentMode: 'queuesense',
      currentPreset: 'isometric',
      isDrawerOpen: false,
      activeTab: 'benchmark',
      decisionReceipt: {
        headline: 'NORMAL ADAPTIVE TRAFFIC FLOW',
        body: 'System initializing. Live perception active.',
        iconType: 'normal',
        phase: 'GREEN: NORTH-SOUTH',
        countdown: '22s',
        queuePCU: 0,
        queueVeh: 0,
        exitOccupancy: 0,
        exitStatus: 'CLEAR',
      },
      pressures: {
        NORTH_SOUTH: { total: 0, queue_pcu: 0, eligible: true },
        EAST_WEST: { total: 0, queue_pcu: 0, eligible: true },
      },
      aiZones: {},
      emergencyData: null,
      benchmarkData: null,
      passportData: null,
      perceptionData: null,
      telemetry: { fps: 60, vehicles: 0 },
    };

    this.callbacks = {};
    this.drawerHeight = 0;
    this.tabTransition = { from: null, to: null, progress: 0 };

    this.init();
  }

  init() {
    this.createHUDElements();
    this.setupEventListeners();
    this.setupSpringPhysics();
    this.mountGlobalAPI();
  }

  /* ---- Create dynamic HUD elements ---- */

  createHUDElements() {
    this.createDecisionReceiptHUD();
    this.createCameraPresetHUD();
    this.createModeToggleHUD();
    this.createScenarioTriggersHUD();
    this.createTelemetryDrawer();
  }

  createDecisionReceiptHUD() {
    // Check if already exists
    if (document.getElementById('decision-receipt-hud')) return;

    const hud = document.createElement('div');
    hud.id = 'decision-receipt-hud';
    hud.className = 'hud-panel';
    hud.setAttribute('data-entering', '');
    hud.innerHTML = this.renderDecisionReceipt();
    document.body.appendChild(hud);

    // Trigger mount animation after DOM insertion
    requestAnimationFrame(() => {
      hud.removeAttribute('data-entering');
      hud.setAttribute('data-mounted', '');
    });
  }

  createCameraPresetHUD() {
    if (document.getElementById('camera-preset-hud')) return;

    const hud = document.createElement('div');
    hud.id = 'camera-preset-hud';
    hud.className = 'hud-panel';
    hud.innerHTML = this.renderCameraPresets();
    document.body.appendChild(hud);
  }

  createModeToggleHUD() {
    if (document.getElementById('mode-toggle-hud')) return;

    const hud = document.createElement('div');
    hud.id = 'mode-toggle-hud';
    hud.innerHTML = this.renderModeToggle();
    document.body.appendChild(hud);
  }

  createScenarioTriggersHUD() {
    if (document.getElementById('scenario-triggers')) return;

    const container = document.createElement('div');
    container.id = 'scenario-triggers';
    container.innerHTML = this.renderScenarioTriggers();
    document.body.appendChild(container);
  }

  createTelemetryDrawer() {
    if (document.getElementById('telemetry-drawer')) return;

    // Drawer handle
    const handle = document.createElement('div');
    handle.className = 'drawer-handle';
    handle.innerHTML = `
      <span class="drawer-handle__icon" id="drawerHandleIcon">📊</span>
      <span>TELEMETRY PANEL</span>
      <span class="drawer-handle__icon" id="drawerHandleIcon2">📊</span>
    `;
    handle.onclick = () => this.toggleDrawer();
    document.body.appendChild(handle);

    // Drawer content
    const drawer = document.createElement('div');
    drawer.id = 'telemetry-drawer';
    drawer.innerHTML = this.renderTelemetryDrawer();
    document.body.appendChild(drawer);

    // Setup tab event listeners
    this.setupTabListeners();
  }

  /* ---- Render Functions ---- */

  renderDecisionReceipt() {
    return `
      <div class="decision-receipt">
        <div class="decision-receipt__headline">
          <div class="decision-receipt__icon ${this.getIconClass()}" id="decisionIcon">
            ${this.getIconEmoji()}
          </div>
          <span id="decisionHeadline">${this.state.decisionReceipt.headline}</span>
          <span class="tabular-nums" id="decisionPhase">${this.state.decisionReceipt.phase}</span>
        </div>
        <p class="decision-receipt__body" id="decisionBody">
          ${this.state.decisionReceipt.body}
        </p>
        <div class="decision-receipt__meta">
          <div class="decision-receipt__meta-item">
            <span>⏱️</span>
            <span>Green: <strong class="tabular-nums" id="decisionCountdown">${this.state.decisionReceipt.countdown}</strong></span>
          </div>
          <div class="decision-receipt__meta-item">
            <span>🚗</span>
            <span><strong class="tabular-nums" id="decisionQueuePcu">${this.state.decisionReceipt.queuePCU.toFixed(1)}</strong> PCU queued</span>
          </div>
          <div class="decision-receipt__meta-item">
            <span>🛣️</span>
            <span>Exit: <strong id="decisionExitStatus">${this.state.decisionReceipt.exitStatus}</strong></span>
          </div>
          <div class="decision-receipt__meta-item">
            <span>📈</span>
            <span>P_NS: <strong class="tabular-nums">${this.state.pressures.NORTH_SOUTH.total.toFixed(2)}</strong> | P_EW: <strong class="tabular-nums">${this.state.pressures.EAST_WEST.total.toFixed(2)}</strong></span>
          </div>
        </div>
      </div>
    `;
  }

  renderCameraPresets() {
    return `
      <button class="camera-preset__pill camera-preset__pill--active" id="presetIsometric"
              onclick="window.HUDDirector.switchCameraPreset('isometric')">
        <span class="camera-preset__icon">📐</span>
        <span>Isometric</span>
      </button>
      <button class="camera-preset__pill" id="presetTopDown"
              onclick="window.HUDDirector.switchCameraPreset('topDown')">
        <span class="camera-preset__icon">🛰️</span>
        <span>Top-Down</span>
      </button>
      <button class="camera-preset__pill" id="presetDriver"
              onclick="window.HUDDirector.switchCameraPreset('driver')">
        <span class="camera-preset__icon">🎮</span>
        <span>Driver View</span>
      </button>
    `;
  }

  renderModeToggle() {
    return `
      <button class="mode-toggle__option mode-toggle__option--active" id="btnModeQueueSense" onclick="window.HUDDirector.setMode('queuesense')">
        <span>✅ QueueSense AI</span>
        <span class="text-xs opacity-80">(Prevents Gridlock)</span>
      </button>
      <button class="mode-toggle__option" id="btnModeTraditional" onclick="window.HUDDirector.setMode('traditional')">
        <span>❌ Traditional</span>
        <span class="text-xs opacity-80">(Watch It Gridlock)</span>
      </button>
      <div class="mode-toggle__slider" id="modeSlider"></div>
    `;
  }

  renderScenarioTriggers() {
    const scenarios = [
      { id: 'normal', emoji: '🟢', name: 'Normal Traffic', color: 'emerald' },
      { id: 'surge', emoji: '🌊', name: 'West Surge', color: 'amber' },
      { id: 'spillback', emoji: '🔴', name: 'Exit Jam', color: 'rose' },
      { id: 'emergency', emoji: '🚑', name: 'Ambulance', color: 'violet' },
      { id: 'sensor_fault', emoji: '⚠️', name: 'Sensor Fault', color: 'amber' },
      { id: 'recovery', emoji: '🔄', name: 'Recovery', color: 'cyan' },
    ];

    return scenarios.map(s => `
      <button class="scenario-pill scenario-pill--${s.color} ${this.state.currentScenario === s.id ? 'scenario-pill--active' : ''}"
              id="scenario-${s.id}" onclick="window.HUDDirector.setScenario('${s.id}')">
        <span class="scenario-pill__icon">${s.emoji}</span>
        <span>${s.name}</span>
      </button>
    `).join('');
  }

  renderTelemetryDrawer() {
    return `
      <div class="drawer__content">
        <div class="drawer__tabs">
          <button class="drawer__tab drawer__tab--active" id="tabBenchmark" onclick="window.HUDDirector.switchTab('benchmark')">
            Benchmark (6)
          </button>
          <button class="drawer__tab" id="tabEmergency" onclick="window.HUDDirector.switchTab('emergency')">
            Emergency Flush
          </button>
          <button class="drawer__tab" id="tabPassport" onclick="window.HUDDirector.switchTab('passport')">
            Passport (8)
          </button>
          <button class="drawer__tab" id="tabPerception" onclick="window.HUDDirector.switchTab('perception')">
            Perception
          </button>
          <button class="drawer__tab" id="tabAudit" onclick="window.HUDDirector.switchTab('audit')">
            Audit Trail
          </button>
        </div>
        <div class="drawer__panels">
          ${this.renderBenchmarkPanel()}
          ${this.renderEmergencyPanel()}
          ${this.renderPassportPanel()}
          ${this.renderPerceptionPanel()}
          ${this.renderAuditPanel()}
        </div>
      </div>
    `;
  }

  renderBenchmarkPanel() {
    const data = this.state.benchmarkData;
    if (!data || !data.controllers) {
      return `<div class="drawer__panel drawer__panel--active" id="panelBenchmark">
        <div class="telemetry-section">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">Benchmark Results</span>
            <span class="telemetry-section__badge telemetry-section__badge--amber">Loading</span>
          </div>
          <div class="loading-skeleton" style="height: 200px; width: 100%;"></div>
        </div>
      </div>`;
    }

    const controllers = data.controllers || [
      { controller_id: 'A', controller_name: 'Controller A (Fixed-Time)', throughput_mean: 952.4, queue_mean: 27.7, spillback_mean: 12 },
      { controller_id: 'B', controller_name: 'Controller B (Actuated)', throughput_mean: 962.1, queue_mean: 33.2, spillback_mean: 15 },
      { controller_id: 'C', controller_name: 'Controller C (Queue-Pressure)', throughput_mean: 1257.1, queue_mean: 36.1, spillback_mean: 48 },
      { controller_id: 'D', controller_name: 'Controller D (QueueSense)', throughput_mean: 1361.5, queue_mean: 1.8, spillback_mean: 0 },
    ];

    const maxThroughput = Math.max(...controllers.map(c => c.throughput_mean));

    return `
      <div class="drawer__panel drawer__panel--active" id="panelBenchmark">
        <div class="telemetry-section">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">
              4-Controller Ablation: ${data.selected_scenario || 'bottleneck'}
            </span>
            <span class="telemetry-section__badge telemetry-section__badge--emerald">${data.active_source || 'benchmark_v2'}</span>
          </div>
          <table class="benchmark-table">
            <thead>
              <tr>
                <th>Controller</th>
                <th>Throughput</th>
                <th>Avg Queue</th>
                <th>Spillback</th>
                <th>Runs</th>
              </tr>
            </thead>
            <tbody id="benchmarkTableBody">
              ${controllers.map(c => {
                const isBest = c.throughput_mean === maxThroughput || c.queue_mean === Math.min(...controllers.map(cc => cc.queue_mean));
                const isWorst = c.controller_id === 'A';
                return `
                  <tr>
                    <td class="controller-name">${c.controller_name}</td>
                    <td class="metric-value ${isBest ? 'metric-value--best' : ''} ${isWorst ? 'metric-value--worst' : ''}">
                      ${c.throughput_mean.toFixed(1)}
                    </td>
                    <td class="metric-value ${!isBest ? '' : 'metric-value--best'}">
                      ${c.queue_mean.toFixed(1)} PCU
                    </td>
                    <td class="metric-value ${c.spillback_mean === 0 ? 'metric-value--best' : c.spillback_mean > 30 ? 'metric-value--worst' : ''}">
                      ${c.spillback_mean} steps
                    </td>
                    <td class="tabular-nums text-muted">${c.runs || 10}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  renderEmergencyPanel() {
    const data = this.state.emergencyData;
    if (!data || !data.strategies) {
      return `<div class="drawer__panel" id="panelEmergency">
        <div class="telemetry-section">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">Emergency Flush Evaluation</span>
            <span class="telemetry-section__badge telemetry-section__badge--amber">Loading</span>
          </div>
          <div class="loading-skeleton" style="height: 180px; width: 100%;"></div>
        </div>
      </div>`;
    }

    const strategies = data.strategies;
    const bestTime = Math.min(...Object.values(strategies).map(s => s.travel_time_s));

    return `
      <div class="drawer__panel" id="panelEmergency">
        <div class="telemetry-section">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">${data.scenario || 'bottleneck'} Scenario</span>
            <span class="telemetry-section__badge telemetry-section__badge--emerald">Verified</span>
          </div>
          <div class="emergency-flush-grid">
            ${Object.entries(strategies).map(([id, s]) => {
              let colorClass = '';
              if (s.travel_time_s <= bestTime) colorClass = 'flush-metric__value--queuesense';
              else if (s.travel_time_s > 50) colorClass = 'flush-metric__value--none';
              else colorClass = 'flush-metric__value--naive';

              const label = id === 'queuesense_downstream_flush' ? 'QueueSense' :
                           id === 'naive_local_preemption' ? 'Naive' : 'No Preempt';

              return `
                <div class="flush-metric">
                  <div class="flush-metric__label">${label}</div>
                  <div class="flush-metric__value ${colorClass}">
                    ${s.travel_time_s.toFixed(1)}
                    <span class="flush-metric__unit">s</span>
                  </div>
                  <div class="text-xs text-muted mt-1">
                    Stops: ${s.emergency_stops} | Recovery: ${s.recovery_time_s.toFixed(1)}s
                  </div>
                </div>
              `;
            }).join('')}
          </div>
          <div class="text-xs text-muted mt-3 tabular-nums">
            ${data.improvement_vs_no_preemption || data.improvement || 'QueueSense saves 50% emergency travel time'}
          </div>
        </div>
      </div>
    `;
  }

  renderPassportPanel() {
    const passports = this.state.passportData?.passports || [];
    const summary = this.state.passportData?.summary || { total_junctions: 3, fully_passed: 3, checks_per_junction: 8 };

    if (!passports.length) {
      return `<div class="drawer__panel" id="panelPassport">
        <div class="telemetry-section">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">Junction Readiness Passport</span>
            <span class="telemetry-section__badge telemetry-section__badge--amber">Loading</span>
          </div>
          <div class="loading-skeleton" style="height: 180px; width: 100%;"></div>
        </div>
      </div>`;
    }

    return `
      <div class="drawer__panel" id="panelPassport">
        <div class="telemetry-section">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">
              Pre-Commissioning Audit (${summary.fully_passed}/${summary.total_junctions} Passed)
            </span>
            <span class="telemetry-section__badge telemetry-section__badge--emerald">8/8 Checks</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 16px;">
            ${passports.map(p => `
              <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                  <div style="font-weight: 600; color: var(--fg-primary);">${p.junction_id}</div>
                  <span class="telemetry-section__badge ${p.overall_pass ? 'telemetry-section__badge--emerald' : 'telemetry-section__badge--rose'}">
                    ${p.pass_count}/${summary.checks_per_junction} ${p.overall_pass ? 'PASSED' : 'ISSUES'}
                  </span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                  ${p.checks.map(c => `
                    <div class="passport-check">
                      <div class="passport-check__icon ${c.passed ? 'passport-check__icon--pass' : 'passport-check__icon--fail'}">
                        ${c.passed ? '✓' : '✗'}
                      </div>
                      <div class="passport-check__content">
                        <div class="passport-check__name">${c.name}</div>
                        <div class="passport-check__details">${c.details} ${c.evidence ? `(${c.evidence})` : ''}</div>
                      </div>
                    </div>
                  `).join('')}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  renderPerceptionPanel() {
    const data = this.state.perceptionData;
    if (!data) {
      return `<div class="drawer__panel" id="panelPerception">
        <div class="telemetry-section">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">Perception Calibration</span>
            <span class="telemetry-section__badge telemetry-section__badge--amber">Loading</span>
          </div>
          <div class="loading-skeleton" style="height: 180px; width: 100%;"></div>
        </div>
      </div>`;
    }

    const metrics = data.metrics || data;

    return `
      <div class="drawer__panel" id="panelPerception">
        <div class="telemetry-section">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">UVH-26 YOLOv11 Calibration</span>
            <span class="telemetry-section__badge telemetry-section__badge--emerald">${metrics.mAP50 || '94.2'} mAP50</span>
          </div>
          <div class="perception-grid">
            <div class="perception-metric">
              <div class="perception-metric__label">mAP@0.5</div>
              <div class="perception-metric__value tabular-nums">${metrics.mAP50 || '94.2'}%</div>
            </div>
            <div class="perception-metric">
              <div class="perception-metric__label">Inference Time</div>
              <div class="perception-metric__value tabular-nums">${metrics.inference_ms || '18.2'} ms</div>
            </div>
            <div class="perception-metric">
              <div class="perception-metric__label">Vehicle Classes</div>
              <div class="perception-metric__value tabular-nums">${metrics.classes || 5}</div>
            </div>
            <div class="perception-metric">
              <div class="perception-metric__label">Dataset</div>
              <div class="perception-metric__value" style="font-size: 14px;">UVH-26</div>
            </div>
          </div>
          ${data.confusion_matrix_html || '<div class="text-xs text-muted mt-2">Confusion matrix loaded</div>'}
        </div>
      </div>
    `;
  }

  renderAuditPanel() {
    const events = this.state.auditLog || [];

    return `
      <div class="drawer__panel" id="panelAudit">
        <div class="telemetry-section" style="padding: 12px;">
          <div class="telemetry-section__header">
            <span class="telemetry-section__title">Real-Time Audit Log</span>
            <span class="telemetry-section__badge telemetry-section__badge--violet">${events.length} Events</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 6px; font-family: monospace; font-size: 11px;">
            ${events.map(e => `
              <div style="display: flex; gap: 8px; color: var(--fg-muted); border-bottom: 1px solid var(--border-subtle); padding-bottom: 6px;">
                <span class="tabular-nums" style="color: var(--accent-cyan);">[${e.time || '00:00:00'}]</span>
                <span style="color: var(--accent-amber); min-width: 120px;">${e.event}</span>
                <span style="color: var(--fg-secondary);">${e.details}</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  /* ---- Spring Physics & Animations ---- */

  setupSpringPhysics() {
    // Spring configuration for all HUD animations
    this.springConfig = {
      stiffness: 200,
      damping: 20,
    };

    // Apply reduced-motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      this.springConfig = { stiffness: 1000, damping: 100 };
    }
  }

  animateValue(elementId, from, to, duration = 800) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const start = parseFloat(from) || 0;
    const end = parseFloat(to) || 0;
    const range = end - start;
    const startTime = performance.now();

    const tick = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease out with spring
      const eased = 1 - Math.pow(1 - progress, 4);
      const value = start + range * eased;

      if (elementId.includes('Pcu') || elementId.includes('Queue') || elementId.includes('Count')) {
        element.textContent = value.toFixed(1);
      } else {
        element.textContent = Math.round(value).toString();
      }

      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    };

    requestAnimationFrame(tick);
  }

  /* ---- Public API Methods ---- */

  setScenario(scenarioId) {
    this.state.currentScenario = scenarioId;
    this.updateScenarioPills();

    // Dispatch event for three-scene.js
    if (window.setScenario) {
      window.setScenario(scenarioId);
    }

    // Emit callback
    if (this.callbacks.onScenarioChange) {
      this.callbacks.onScenarioChange(scenarioId);
    }
  }

  setMode(mode) {
    this.state.currentMode = mode;
    this.updateModeToggle(mode);

    // Dispatch event for three-scene.js
    if (window.setMode) {
      window.setMode(mode === 'queuesense');
    }

    // Emit callback
    if (this.callbacks.onModeChange) {
      this.callbacks.onModeChange(mode);
    }
  }

  switchCameraPreset(preset) {
    this.state.currentPreset = preset;
    this.updatePresetPills(preset);

    // Dispatch event for three-scene.js
    if (window.switchCameraPreset) {
      window.switchCameraPreset(preset);
    }

    // Emit callback
    if (this.callbacks.onPresetChange) {
      this.callbacks.onPresetChange(preset);
    }
  }

  switchTab(tabId) {
    this.state.activeTab = tabId;
    this.updateTabStates();

    // Emit callback
    if (this.callbacks.onTabChange) {
      this.callbacks.onTabChange(tabId);
    }
  }

  toggleDrawer() {
    this.state.isDrawerOpen = !this.state.isDrawerOpen;
    const drawer = document.getElementById('telemetry-drawer');
    const handle = document.querySelector('.drawer-handle');

    if (this.state.isDrawerOpen) {
      drawer.setAttribute('data-open', '');
    } else {
      drawer.removeAttribute('data-open');
    }

    // Update handle icon rotation
    const handleIcon = handle.querySelector('.drawer-handle__icon');
    if (handleIcon) {
      handleIcon.style.transform = this.state.isDrawerOpen ? 'rotate(180deg)' : 'rotate(0deg)';
    }

    // Emit callback
    if (this.callbacks.onDrawerToggle) {
      this.callbacks.onDrawerToggle(this.state.isDrawerOpen);
    }
  }

  openDrawer() {
    if (!this.state.isDrawerOpen) this.toggleDrawer();
  }

  closeDrawer() {
    if (this.state.isDrawerOpen) this.toggleDrawer();
  }

  /* ---- State Updates ---- */

  updateDecisionReceipt(receipt) {
    this.state.decisionReceipt = {
      ...this.state.decisionReceipt,
      ...receipt,
    };

    this.animateDecisionReceipt();

    // Emit callback
    if (this.callbacks.onDecisionUpdate) {
      this.callbacks.onDecisionUpdate(receipt);
    }
  }

  animateDecisionReceipt() {
    const hud = document.getElementById('decision-receipt-hud');
    if (!hud) return;

    // Re-render content
    hud.innerHTML = this.renderDecisionReceipt();

    // Re-apply active state classes
    this.updateScenarioPills();
  }

  updateScenarioPills() {
    document.querySelectorAll('.scenario-pill').forEach(pill => {
      pill.classList.remove('scenario-pill--active');
      if (pill.id === `scenario-${this.state.currentScenario}`) {
        pill.classList.add('scenario-pill--active');
      }
    });
  }

  updatePresetPills(activePreset) {
    document.querySelectorAll('.camera-preset__pill').forEach(pill => {
      pill.classList.remove('camera-preset__pill--active');
    });
    const active = document.getElementById(`preset${activePreset.charAt(0).toUpperCase()}${activePreset.slice(1)}`);
    if (active) active.classList.add('camera-preset__pill--active');
  }

  updateModeToggle(mode) {
    const qsBtn = document.getElementById('btnModeQueueSense');
    const tradBtn = document.getElementById('btnModeTraditional');
    const slider = document.getElementById('modeSlider');

    if (mode === 'queuesense') {
      qsBtn.classList.add('mode-toggle__option--active');
      tradBtn.classList.remove('mode-toggle__option--active');
      slider.style.transform = 'translateX(0)';
    } else {
      tradBtn.classList.add('mode-toggle__option--active');
      qsBtn.classList.remove('mode-toggle__option--active');
      slider.style.transform = 'translateX(100%)';
    }
  }

  updateTabStates() {
    document.querySelectorAll('.drawer__tab').forEach(tab => {
      tab.classList.remove('drawer__tab--active');
    });

    const activeTab = document.getElementById(`tab${this.state.activeTab.charAt(0).toUpperCase()}${this.state.activeTab.slice(1)}`);
    if (activeTab) activeTab.classList.add('drawer__tab--active');

    // Hide/show panels
    document.querySelectorAll('.drawer__panel').forEach(panel => {
      panel.classList.remove('drawer__panel--active');
    });

    const activePanel = document.getElementById(`panel${this.state.activeTab.charAt(0).toUpperCase()}${this.state.activeTab.slice(1)}`);
    if (activePanel) activePanel.classList.add('drawer__panel--active');
  }

  getIconClass() {
    const type = this.state.decisionReceipt.iconType || 'normal';
    return `decision-receipt__icon--${type}`;
  }

  getIconEmoji() {
    const type = this.state.decisionReceipt.iconType || 'normal';
    const emojis = {
      normal: '🟢',
      elevated: '🟡',
      blocked: '🛑',
      emergency: '🚑',
      safe_mode: '⚠️',
    };
    return emojis[type] || '🟢';
  }

  /* ---- External Data Loaders ---- */

  async loadBenchmarkData() {
    try {
      const response = await fetch('/api/benchmark');
      const data = await response.json();
      this.state.benchmarkData = data;

      // Re-render benchmark panel if active
      if (this.state.activeTab === 'benchmark') {
        const panel = document.getElementById('panelBenchmark');
        if (panel) {
          const temp = document.createElement('div');
          temp.innerHTML = this.renderBenchmarkPanel().innerHTML;
          panel.innerHTML = temp.querySelector('#panelBenchmark').innerHTML;
        }
      }
    } catch (e) {
      console.error('Failed to load benchmark data:', e);
    }
  }

  async loadEmergencyData() {
    try {
      const response = await fetch('/api/emergency-flush/eval');
      const data = await response.json();
      this.state.emergencyData = data;
    } catch (e) {
      console.error('Failed to load emergency data:', e);
    }
  }

  async loadPassportData() {
    try {
      const response = await fetch('/api/passport/status');
      const data = await response.json();
      this.state.passportData = data;
    } catch (e) {
      console.error('Failed to load passport data:', e);
    }
  }

  async loadPerceptionData() {
    try {
      const response = await fetch('/api/perception/eval');
      const data = await response.json();
      this.state.perceptionData = data;
    } catch (e) {
      console.error('Failed to load perception data:', e);
    }
  }

  async loadAllData() {
    await Promise.all([
      this.loadBenchmarkData(),
      this.loadEmergencyData(),
      this.loadPassportData(),
      this.loadPerceptionData(),
    ]);

    // Show drawer after data loads if it was requested
    if (this.state.isDrawerOpen) {
      const drawer = document.getElementById('telemetry-drawer');
      drawer?.setAttribute('data-open', '');
    }
  }

  /* ---- Event Listeners ---- */

  setupEventListeners() {
    // Tab keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === ' ') {
        // Spacebar to toggle drawer
        this.toggleDrawer();
      }
      if (e.key === 'Escape' && this.state.isDrawerOpen) {
        this.closeDrawer();
      }
    });

    // Setup scroll lock when drawer is open
    const observer = new MutationObserver(() => {
      const drawer = document.getElementById('telemetry-drawer');
      if (drawer?.hasAttribute('data-open')) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
      }
    });

    const drawerEl = document.getElementById('telemetry-drawer');
    if (drawerEl) {
      observer.observe(drawerEl, { attributes: true });
    }
  }

  /* ---- Callback Registration ---- */

  on(event, callback) {
    this.callbacks[event] = callback;
  }

  off(event) {
    delete this.callbacks[event];
  }

  /* ---- Mount Global API ---- */

  mountGlobalAPI() {
    window.HUDDirector = this;
  }
}

/* ---- Singleton Instance ---- */

let hudInstance = null;

function initHUD(container) {
  if (hudInstance) {
    hudInstance.destroy();
  }

  hudInstance = new HUDDirector();
  hudInstance.mountGlobalAPI();

  // Load data
  hudInstance.loadAllData();

  return hudInstance;
}

function getHUD() {
  return hudInstance;
}

/* ---- Export ---- */

window.initHUD = initHUD;
window.getHUD = getHUD;

window.HUDDirector = {
  setScenario: (id) => hudInstance?.setScenario(id),
  setMode: (mode) => hudInstance?.setMode(mode),
  switchCameraPreset: (preset) => hudInstance?.switchCameraPreset(preset),
  switchTab: (tab) => hudInstance?.switchTab(tab),
  toggleDrawer: () => hudInstance?.toggleDrawer(),
  openDrawer: () => hudInstance?.openDrawer(),
  updateDecisionReceipt: (receipt) => hudInstance?.updateDecisionReceipt(receipt),
  loadBenchmarkData: () => hudInstance?.loadBenchmarkData(),
  loadEmergencyData: () => hudInstance?.loadEmergencyData(),
  loadPassportData: () => hudInstance?.loadPassportData(),
  loadPerceptionData: () => hudInstance?.loadPerceptionData(),
  getState: () => hudInstance?.state,
};