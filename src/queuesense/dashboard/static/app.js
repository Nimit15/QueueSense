/* =============================================================================
   QUEUESENSE — MAIN APPLICATION MODULE
   Initializes Three.js scene, wires controls, fetches API data, animates UI
   Emil Kowalski + Impeccable + Taste Design Engineering
   ============================================================================= */

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { initDigitalTwin, getTwinScene, switchCameraPreset, setScenario, setMode, triggerEmergencyFlush } from './three-scene.js';

/* =============================================================================
   STATE MANAGEMENT
   ============================================================================= */

const AppState = {
  // Control state
  currentMode: 'queuesense',
  currentScenario: 'normal',
  currentCamera: 'isometric',
  isAutoScenario: true,
  simSpeed: 1.0,
  congestionLevel: 0.5,
  spawnRate: 1.0,

  // API state
  liveState: null,
  benchmarkData: null,
  passportData: null,
  emergencyResults: null,
  selectorDecision: null,
  wsConnection: null,

  // UI state
  isInitialized: false,
  lastFrameTime: 0,
  frameCount: 0,

  // Elements cache
  elements: {},
};

/* =============================================================================
   DOM ELEMENT CACHING
   ============================================================================= */

function cacheElements() {
  AppState.elements = {
    // Hero controls
    modeSwitcher: document.querySelectorAll('.mode-option'),
    scenarioPills: document.querySelectorAll('.scenario-pill'),
    sliders: {
      simSpeed: document.getElementById('slider-sim-speed'),
      congestion: document.getElementById('slider-congestion'),
      spawnRate: document.getElementById('slider-spawn-rate'),
    },
    sliderValues: {
      simSpeed: document.getElementById('value-sim-speed'),
      congestion: document.getElementById('value-congestion'),
      spawnRate: document.getElementById('value-spawn-rate'),
    },
    actionButtons: {
      emergencyFlush: document.getElementById('btn-emergency-flush'),
      reset: document.getElementById('btn-reset'),
      selector: document.getElementById('btn-selector'),
      download: document.getElementById('btn-download'),
    },
    cameraPills: document.querySelectorAll('.camera-pill'),

    // Decision feed
    decisionFeed: {
      reason: document.getElementById('decision-reason'),
      status: document.getElementById('decision-status'),
      meta: document.getElementById('decision-meta'),
    },

    // Scoreboard
    scoreboard: {
      throughput: document.getElementById('score-throughput'),
      queueLength: document.getElementById('score-queue'),
      spillback: document.getElementById('score-spillback'),
      emergency: document.getElementById('score-emergency'),
    },

    // Charts (placeholders for Chart.js)
    charts: {
      delayChart: document.getElementById('delay-chart'),
    },

    // Metric cards
    metricCards: {
      throughput: document.getElementById('metric-throughput'),
      queue: document.getElementById('metric-queue'),
      spillback: document.getElementById('metric-spillback'),
      emergency: document.getElementById('metric-emergency'),
    },

    // Ablation table
    ablationTable: document.getElementById('ablation-table'),

    // Emergency results
    emergencyResults: document.getElementById('emergency-results'),

    // Passport
    passportGrid: document.getElementById('passport-grid'),

    // Canvas container
    canvasContainer: document.querySelector('.hero__canvas-container'),

    // Status indicators
    liveIndicator: document.getElementById('live-indicator'),
    wsStatus: document.getElementById('ws-status'),
  };
}

/* =============================================================================
   INITIALIZATION
   ============================================================================= */

async function initializeApp() {
  cacheElements();

  // Initialize Three.js scene
  const canvasContainer = AppState.elements.canvasContainer;
  if (!canvasContainer) {
    console.error('Canvas container not found');
    return;
  }

  initDigitalTwin(canvasContainer);

  // Wire up callbacks from three-scene
  window.onTwinStateUpdate = handleTwinStateUpdate;
  window.onSignalUpdate = handleSignalUpdate;
  window.onScenarioChange = handleScenarioChange;
  window.onModeChange = handleModeChange;
  window.onZoneUpdate = handleZoneUpdate;
  window.onTwinTelemetry = handleTelemetry;

  // Wire up UI controls
  wireControls();

  // Connect WebSocket for live state
  connectWebSocket();

  // Fetch initial API data
  await fetchAllAPIData();

  // Start render loop
  AppState.isInitialized = true;
  requestAnimationFrame(renderLoop);

  // Mark live indicator as active
  updateLiveIndicator(true);
}

function wireControls() {
  // Mode switcher
  AppState.elements.modeSwitcher.forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      setModeControl(mode);
    });
  });

  // Scenario pills
  AppState.elements.scenarioPills.forEach(pill => {
    pill.addEventListener('click', () => {
      const scenario = pill.dataset.scenario;
      setScenarioControl(scenario);
    });
  });

  // Sliders
  Object.entries(AppState.elements.sliders).forEach(([key, slider]) => {
    if (slider) {
      slider.addEventListener('input', (e) => {
        const value = parseFloat(e.target.value);
        AppState[key] = value;
        updateSliderDisplay(key, value);
        applySliderToScene(key, value);
      });
    }
  });

  // Action buttons
  const { emergencyFlush, reset, selector, download } = AppState.elements.actionButtons;
  if (emergencyFlush) emergencyFlush.addEventListener('click', () => handleEmergencyFlush());
  if (reset) reset.addEventListener('click', () => handleReset());
  if (selector) selector.addEventListener('click', () => handleSelector());
  if (download) download.addEventListener('click', () => handleDownload());

  // Camera pills
  AppState.elements.cameraPills.forEach(pill => {
    pill.addEventListener('click', () => {
      const preset = pill.dataset.camera;
      setCameraPreset(preset);
    });
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', handleKeyboardShortcuts);
}

/* =============================================================================
   CONTROL HANDLERS
   ============================================================================= */

function setModeControl(mode) {
  if (AppState.currentMode === mode) return;

  AppState.currentMode = mode;
  setMode(mode);

  // Update UI
  AppState.elements.modeSwitcher.forEach(btn => {
    btn.classList.toggle('mode-option--active', btn.dataset.mode === mode);
  });

  // Update decision feed
  updateDecisionFeed({
    reason: mode === 'queuesense'
      ? 'QueueSense adaptive control active. Downstream blockage awareness + queue-pressure optimization.'
      : 'Traditional fixed-time actuated control. Gap-based induction loop logic, no spillback awareness.',
    status: { text: mode === 'queuesense' ? 'ADAPTIVE' : 'FIXED', class: mode === 'queuesense' ? 'badge--emerald' : 'badge--cyan' },
    meta: [
      { label: 'Mode', value: mode === 'queuesense' ? 'QueueSense (D)' : 'Actuated (B)' },
      { label: 'Downstream Awareness', value: mode === 'queuesense' ? 'ON' : 'OFF' },
      { label: 'Safety Supervisor', value: 'ACTIVE' },
    ],
  });
}

function setScenarioControl(scenario) {
  if (AppState.currentScenario === scenario) return;

  AppState.currentScenario = scenario;
  AppState.isAutoScenario = false;
  setScenario(scenario);

  // Update UI
  AppState.elements.scenarioPills.forEach(pill => {
    pill.classList.toggle('scenario-pill--active', pill.dataset.scenario === scenario);
  });

  // Update scenario pill visual states
  AppState.elements.scenarioPills.forEach(pill => {
    pill.classList.remove('scenario-pill--emerald', 'scenario-pill--amber', 'scenario-pill--rose', 'scenario-pill--violet', 'scenario-pill--cyan');
    if (pill.dataset.scenario === scenario) {
      const colors = {
        normal: 'emerald',
        surge: 'amber',
        spillback: 'rose',
        bottleneck: 'violet',
        emergency: 'cyan',
        sensor_fault: 'rose',
      };
      pill.classList.add(`scenario-pill--${colors[scenario] || 'emerald'}`);
    }
  });

  // Update decision feed
  const scenarioLabels = {
    normal: 'Balanced demand across all approaches. Fixed-time plan optimal.',
    surge: 'Peak hour surge on north approach. Queue pressure spikes 300%.',
    spillback: 'Downstream bottleneck on J1→J2 link. Receiving road saturated >85%.',
    bottleneck: 'Severe bottleneck at J2 exit. Spillback propagating to J1.',
    emergency: 'Ambulance detected on south approach. Emergency flush activated.',
    sensor_fault: 'Camera dropout on east approach. Falling back to fixed-time schedule.',
  };

  updateDecisionFeed({
    reason: scenarioLabels[scenario] || 'Scenario changed.',
    status: { text: 'SCENARIO', class: 'badge--cyan' },
    meta: [
      { label: 'Scenario', value: scenario.replace('_', ' ').toUpperCase() },
      { label: 'Auto-cycle', value: AppState.isAutoScenario ? 'ON' : 'OFF' },
    ],
  });
}

function setCameraPreset(preset) {
  if (AppState.currentCamera === preset) return;

  AppState.currentCamera = preset;
  switchCameraPreset(preset);

  // Update UI
  AppState.elements.cameraPills.forEach(pill => {
    pill.classList.toggle('camera-pill--active', pill.dataset.camera === preset);
  });
}

function updateSliderDisplay(key, value) {
  const display = AppState.elements.sliderValues[key];
  if (!display) return;

  const formats = {
    simSpeed: (v) => `${v.toFixed(1)}x`,
    congestion: (v) => `${Math.round(v * 100)}%`,
    spawnRate: (v) => `${v.toFixed(1)}x`,
  };

  display.textContent = formats[key] ? formats[key](value) : value;
}

function applySliderToScene(key, value) {
  const scene = getTwinScene();
  if (!scene) return;

  switch (key) {
    case 'simSpeed':
      // Modify scenario time scale
      scene.timeScale = value;
      break;
    case 'congestion':
      // Modify traffic density
      scene.congestionLevel = value;
      break;
    case 'spawnRate':
      // Modify spawn rate
      scene.spawnRate = value;
      break;
  }
}

async function handleEmergencyFlush() {
  const btn = AppState.elements.actionButtons.emergencyFlush;
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="btn__icon">⏳</span> FLUSHING...';
  }

  try {
    triggerEmergencyFlush();

    updateDecisionFeed({
      reason: 'Emergency flush triggered. J2 clears first (downstream-first), then J1. Ambulance corridor opening.',
      status: { text: 'EMERGENCY', class: 'badge--rose' },
      meta: [
        { label: 'Strategy', value: 'Downstream-First Clear' },
        { label: 'Priority', value: 'Ambulance (South→North)' },
        { label: 'J2 Clear Time', value: '~8.2s' },
        { label: 'J1 Clear Time', value: '~12.7s' },
      ],
    });

    // Fetch emergency results
    await fetchEmergencyResults();
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span class="btn__icon">🚑</span> EMERGENCY FLUSH';
    }
  }
}

async function handleReset() {
  AppState.isAutoScenario = true;
  setScenarioControl('normal');
  setModeControl('queuesense');
  setCameraPreset('isometric');

  // Reset sliders
  AppState.simSpeed = 1.0;
  AppState.congestionLevel = 0.5;
  AppState.spawnRate = 1.0;
  AppState.elements.sliders.simSpeed.value = 1.0;
  AppState.elements.sliders.congestion.value = 0.5;
  AppState.elements.sliders.spawnRate.value = 1.0;
  updateSliderDisplay('simSpeed', 1.0);
  updateSliderDisplay('congestion', 0.5);
  updateSliderDisplay('spawnRate', 1.0);

  updateDecisionFeed({
    reason: 'System reset to defaults. QueueSense adaptive mode. Balanced scenario. Auto-cycling enabled.',
    status: { text: 'RESET', class: 'badge--emerald' },
    meta: [
      { label: 'Mode', value: 'QueueSense (D)' },
      { label: 'Scenario', value: 'BALANCED' },
      { label: 'Auto-cycle', value: 'ON' },
    ],
  });
}

async function handleSelector() {
  const btn = AppState.elements.actionButtons.selector;
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="btn__icon">⏳</span> SELECTING...';
  }

  try {
    const response = await fetch('/api/selector');
    const data = await response.json();
    AppState.selectorDecision = data;

    updateDecisionFeed({
      reason: `Selector chose: ${data.chosen_controller} (${data.reason})`,
      status: { text: 'SELECTOR', class: 'badge--violet' },
      meta: [
        { label: 'Chosen', value: data.chosen_controller },
        { label: 'Confidence', value: `${Math.round(data.confidence * 100)}%` },
        { label: 'Reason', value: data.reason },
      ],
    });
  } catch (error) {
    console.error('Selector failed:', error);
    updateDecisionFeed({
      reason: 'Selector unavailable. Running in standalone mode.',
      status: { text: 'OFFLINE', class: 'badge--rose' },
    });
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span class="btn__icon">🤖</span> RUN SELECTOR';
    }
  }
}

function handleDownload() {
  // Trigger download of benchmark CSV
  const link = document.createElement('a');
  link.href = '/api/benchmark/export';
  link.download = `queuesense-benchmark-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
}

function handleKeyboardShortcuts(e) {
  // Ignore if typing in input
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

  switch (e.key.toLowerCase()) {
    case '1':
      setModeControl('queuesense');
      break;
    case '2':
      setModeControl('actuated');
      break;
    case '3':
      setModeControl('pressure');
      break;
    case '4':
      setModeControl('fixed');
      break;
    case ' ':
      e.preventDefault();
      handleEmergencyFlush();
      break;
    case 'r':
      handleReset();
      break;
    case 's':
      handleSelector();
      break;
    case 'c':
      // Cycle camera
      const cameras = ['isometric', 'topDown', 'driver'];
      const currentIdx = cameras.indexOf(AppState.currentCamera);
      setCameraPreset(cameras[(currentIdx + 1) % cameras.length]);
      break;
  }
}

/* =============================================================================
   DECISION FEED
   ============================================================================= */

function updateDecisionFeed(data) {
  const { reason, status, meta } = data;

  if (AppState.elements.decisionFeed.reason) {
    AppState.elements.decisionFeed.reason.textContent = reason;
  }

  if (AppState.elements.decisionFeed.status) {
    AppState.elements.decisionFeed.status.textContent = status.text;
    AppState.elements.decisionFeed.status.className = `decision-feed__status ${status.class}`;
  }

  if (AppState.elements.decisionFeed.meta) {
    AppState.elements.decisionFeed.meta.innerHTML = meta.map(item =>
      `<span class="decision-feed__meta-item"><strong>${item.label}:</strong> ${item.value}</span>`
    ).join('');
  }
}

/* =============================================================================
   SCOREBOARD
   ============================================================================= */

function updateScoreboard(data) {
  const sb = AppState.elements.scoreboard;
  if (!sb) return;

  if (data.throughput !== undefined) sb.throughput.textContent = data.throughput.toFixed(1);
  if (data.queueLength !== undefined) sb.queueLength.textContent = data.queueLength.toFixed(1);
  if (data.spillback !== undefined) sb.spillback.textContent = data.spillback.toFixed(1);
  if (data.emergency !== undefined) sb.emergency.textContent = data.emergency.toFixed(1);
}

/* =============================================================================
   API FETCHING
   ============================================================================= */

async function fetchAllAPIData() {
  try {
    await Promise.all([
      fetchLiveState(),
      fetchBenchmarkData(),
      fetchPassportData(),
      fetchEmergencyResults(),
    ]);
  } catch (error) {
    console.error('API fetch error:', error);
  }
}

async function fetchLiveState() {
  try {
    const response = await fetch('/api/state');
    const data = await response.json();
    AppState.liveState = data;
    updateLiveUI(data);
  } catch (error) {
    console.error('Live state fetch failed:', error);
  }
}

async function fetchBenchmarkData() {
  try {
    const response = await fetch('/api/benchmark');
    const data = await response.json();
    AppState.benchmarkData = data;
    updateBenchmarkUI(data);
  } catch (error) {
    console.error('Benchmark fetch failed:', error);
  }
}

async function fetchPassportData() {
  try {
    const response = await fetch('/api/passport');
    const data = await response.json();
    AppState.passportData = data;
    updatePassportUI(data);
  } catch (error) {
    console.error('Passport fetch failed:', error);
  }
}

async function fetchEmergencyResults() {
  try {
    const response = await fetch('/api/emergency/results');
    const data = await response.json();
    AppState.emergencyResults = data;
    updateEmergencyResultsUI(data);
  } catch (error) {
    console.error('Emergency results fetch failed:', error);
  }
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  AppState.wsConnection = new WebSocket(wsUrl);

  AppState.wsConnection.onopen = () => {
    updateWSStatus('connected');
  };

  AppState.wsConnection.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'state') {
        AppState.liveState = data.payload;
        updateLiveUI(data.payload);
      }
    } catch (e) {
      console.error('WS message parse error:', e);
    }
  };

  AppState.wsConnection.onclose = () => {
    updateWSStatus('disconnected');
    // Reconnect after 3 seconds
    setTimeout(connectWebSocket, 3000);
  };

  AppState.wsConnection.onerror = (error) => {
    console.error('WS error:', error);
    updateWSStatus('error');
  };
}

function updateWSStatus(status) {
  const el = AppState.elements.wsStatus;
  if (!el) return;

  const statusConfig = {
    connected: { text: 'LIVE', class: 'badge--emerald' },
    disconnected: { text: 'RECONNECTING...', class: 'badge--amber' },
    error: { text: 'ERROR', class: 'badge--rose' },
  };

  const config = statusConfig[status] || statusConfig.disconnected;
  el.textContent = config.text;
  el.className = `badge ${config.class}`;
}

function updateLiveIndicator(isLive) {
  const el = AppState.elements.liveIndicator;
  if (!el) return;

  if (isLive) {
    el.classList.add('live');
    el.textContent = 'LIVE';
  } else {
    el.classList.remove('live');
    el.textContent = 'OFFLINE';
  }
}

/* =============================================================================
   UI UPDATES FROM API
   ============================================================================= */

function updateLiveUI(data) {
  if (!data) return;

  // Update scoreboard with live data
  updateScoreboard({
    throughput: data.throughput_veh_per_hr || 0,
    queueLength: data.avg_queue_length_m || 0,
    spillback: data.spillback_risk_pct || 0,
    emergency: data.emergency_response_sec || 0,
  });

  // Update metric cards
  updateMetricCards(data);

  // Update decision feed if we have a reason
  if (data.decision_reason) {
    updateDecisionFeed({
      reason: data.decision_reason,
      status: { text: 'LIVE', class: 'badge--emerald' },
      meta: [
        { label: 'Phase', value: data.current_phase || 'UNKNOWN' },
        { label: 'Cycle', value: `${data.cycle_time_remaining || 0}s` },
        { label: 'Active', value: data.active_approach || 'NONE' },
      ],
    });
  }
}

function updateMetricCards(data) {
  const cards = AppState.elements.metricCards;
  if (!cards) return;

  if (cards.throughput) {
    cards.throughput.querySelector('.metric-card__value').textContent =
      (data.throughput_veh_per_hr || 0).toFixed(0);
    cards.throughput.querySelector('.metric-card__detail').textContent =
      `vs fixed-time: ${((data.throughput_veh_per_hr || 0) / 1800 * 100 - 100).toFixed(1)}%`;
  }

  if (cards.queue) {
    cards.queue.querySelector('.metric-card__value').textContent =
      (data.avg_queue_length_m || 0).toFixed(1);
    cards.queue.querySelector('.metric-card__detail').textContent =
      `95th pct: ${(data.p95_queue_length_m || 0).toFixed(1)}m`;
  }

  if (cards.spillback) {
    cards.spillback.querySelector('.metric-card__value').textContent =
      (data.spillback_risk_pct || 0).toFixed(1);
    cards.spillback.querySelector('.metric-card__detail').textContent =
      data.spillback_active ? 'ACTIVE' : 'Clear';
  }

  if (cards.emergency) {
    cards.emergency.querySelector('.metric-card__value').textContent =
      (data.emergency_response_sec || 0).toFixed(1);
    cards.emergency.querySelector('.metric-card__detail').textContent =
      'Downstream-first policy';
  }
}

function updateBenchmarkUI(data) {
  if (!data || !AppState.elements.ablationTable) return;

  const tbody = AppState.elements.ablationTable.querySelector('tbody');
  if (!tbody) return;

  // Clear existing rows
  tbody.innerHTML = '';

  // Render rows from benchmark data
  const controllers = data.controllers || [];
  controllers.forEach((ctrl, idx) => {
    const row = document.createElement('tr');
    const isBest = idx === 0;
    const isWorst = idx === controllers.length - 1;

    row.innerHTML = `
      <td>
        <span class="controller-name">${ctrl.name}</span>
        <span class="controller-type ${ctrl.typeClass || ''}">${ctrl.typeLabel}</span>
      </td>
      <td class="metric-value ${isBest ? 'metric-value--best' : isWorst ? 'metric-value--worst' : ''}">${ctrl.avg_delay_sec?.toFixed(1) || '—'}</td>
      <td class="metric-value ${isBest ? 'metric-value--best' : isWorst ? 'metric-value--worst' : ''}">${ctrl.p95_delay_sec?.toFixed(1) || '—'}</td>
      <td class="metric-value ${isBest ? 'metric-value--best' : isWorst ? 'metric-value--worst' : ''}">${ctrl.throughput_veh_hr?.toFixed(0) || '—'}</td>
      <td class="metric-value ${isBest ? 'metric-value--best' : isWorst ? 'metric-value--worst' : ''}">${ctrl.spillback_incidents || '—'}</td>
      <td class="metric-value ${isBest ? 'metric-value--best' : isWorst ? 'metric-value--worst' : ''}">${ctrl.emergency_response_sec?.toFixed(1) || '—'}</td>
    `;
    tbody.appendChild(row);
  });
}

function updateEmergencyResultsUI(data) {
  if (!data || !AppState.elements.emergencyResults) return;

  const container = AppState.elements.emergencyResults;
  const strategies = data.strategies || [];

  container.innerHTML = strategies.map((strat, idx) => `
    <article class="emergency-strategy ${idx === 0 ? 'emergency-strategy--best' : idx === strategies.length - 1 ? 'emergency-strategy--worst' : ''}">
      <span class="emergency-strategy__badge">${idx === 0 ? 'BEST' : idx === strategies.length - 1 ? 'SLOWEST' : `RANK ${idx + 1}`}</span>
      <h4 class="emergency-strategy__name">${strat.name}</h4>
      <div class="emergency-strategy__time ${idx === 0 ? '' : ''}">${strat.clearance_time_sec?.toFixed(1) || '—'}s</div>
      <div class="emergency-strategy__detail">${strat.description || ''}</div>
      <div class="emergency-strategy__stops">Stops: ${strat.stops || '—'}</div>
    </article>
  `).join('');
}

function updatePassportUI(data) {
  if (!data || !AppState.elements.passportGrid) return;

  const container = AppState.elements.passportGrid;
  const junctions = data.junctions || [];

  container.innerHTML = junctions.map(j => `
    <article class="passport-junction">
      <header class="passport-junction__header">
        <h4 class="passport-junction__id">${j.id}</h4>
        <span class="passport-junction__badge passport-junction__badge--${j.overall_pass ? 'pass' : 'fail'}">
          ${j.overall_pass ? 'PASS' : 'FAIL'}
        </span>
      </header>
      <div class="passport-checks">
        ${(j.checks || []).map(check => `
          <div class="passport-check">
            <span class="passport-check__icon passport-check__icon--${check.pass ? 'pass' : 'fail'}">
              ${check.pass ? '✓' : '✗'}
            </span>
            <div class="passport-check__content">
              <div class="passport-check__name">${check.name}</div>
              <div class="passport-check__details">${check.details}</div>
            </div>
          </div>
        `).join('')}
      </div>
    </article>
  `).join('');
}

/* =============================================================================
   THREE.JS SCENE CALLBACKS
   ============================================================================= */

function handleTwinStateUpdate(state) {
  // Called from three-scene when state changes
  AppState.liveState = state;
  updateLiveUI(state);
}

function handleSignalUpdate(signal) {
  // Signal phase changed
  console.debug('Signal update:', signal);
}

function handleScenarioChange(scenario) {
  AppState.currentScenario = scenario;
  // Update scenario pills if auto-cycling
  if (AppState.isAutoScenario) {
    AppState.elements.scenarioPills.forEach(pill => {
      pill.classList.toggle('scenario-pill--active', pill.dataset.scenario === scenario);
    });
  }
}

function handleModeChange(isQueueSense) {
  AppState.currentMode = isQueueSense ? 'queuesense' : 'actuated';
  AppState.elements.modeSwitcher.forEach(btn => {
    btn.classList.toggle('mode-option--active', btn.dataset.mode === AppState.currentMode);
  });
}

function handleZoneUpdate(zones) {
  // AI zone PCU counts updated
  // Could update decision feed meta
}

function handleTelemetry(stats) {
  // Performance telemetry from scene
  console.debug('Telemetry:', stats);
}

/* =============================================================================
   RENDER LOOP
   ============================================================================= */

function renderLoop(timestamp) {
  if (!AppState.isInitialized) return;

  const deltaTime = (timestamp - AppState.lastFrameTime) / 1000;
  AppState.lastFrameTime = timestamp;
  AppState.frameCount++;

  // Throttle API polling to 2Hz
  if (AppState.frameCount % 30 === 0) {
    fetchLiveState();
  }

  // Throttle benchmark fetch to once per 10 seconds
  if (AppState.frameCount % 600 === 0) {
    fetchBenchmarkData();
    fetchPassportData();
  }

  requestAnimationFrame(renderLoop);
}

/* =============================================================================
   UTILITY FUNCTIONS
   ============================================================================= */

function formatNumber(num, decimals = 1) {
  if (num === null || num === undefined || isNaN(num)) return '—';
  return Number(num).toFixed(decimals);
}

function debounce(fn, delay) {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

/* =============================================================================
   ENTRY POINT
   ============================================================================= */

// Initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeApp);
} else {
  initializeApp();
}

// Export for debugging
window.AppState = AppState;
window.initializeApp = initializeApp;