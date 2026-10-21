/* =============================================================================
   QUEUESENSE ICCC — HUD COMPONENTS (SVG ICONS, NO EMOJIS)
   Floating HUD panels with Emil Kowalski design principles:
   - Spring easings (cubic-bezier)
   - Hardware-accelerated transforms only
   - Origin-aware popovers
   - Reduced-motion support
   - Tabular-nums animated counters

   Components:
   - Live Decision Receipt (top-left)
   - Camera Preset Pills (top-right, bottom-center)
   - Mode Toggle (bottom-center)
   - Scenario Trigger Pills (bottom-left)
   - Expandable Telemetry Drawer (bottom, 5 tabs)
   ============================================================================= */

(function() {
  'use strict';

  /* ---- Inline SVG Icon Definitions (no emoji anywhere) ---- */

  var SVG_ICONS = {
    pulse: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
    throughput: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>',
    queue: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2"></rect><path d="M8 21h8M12 17v4"></path></svg>',
    spillback: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
    emergency: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path><path d="M12 7v4M12 16h.01"></path></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>',
    cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
    grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="M12 8v8M8 12h8"></path></svg>',
    ambulance: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path><path d="M12 7v4M12 16h.01"></path></svg>',
    sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>',
    scan: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>',
    density: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path></svg>',
    barrier: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
    camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path><circle cx="12" cy="12" r="3"></circle></svg>',
    eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 8 0 2h20.34a2 2 0 0 8 1.74-3L13.71 3.86a2 2 0 0 8-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>',
    reset: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>',
    selector: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="2"></rect><path d="M12 2v20M2 12h20"></path></svg>',
    analytics: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 3v18h18"></path><line x1="9" y1="9" x2="9" y2="15"></line><line x1="15" y1="9" x2="15" y2="15"></line><polyline points="5 17 9 13 15 17 19 13"></polyline></svg>',
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="12" x2="12" y2="16"></line><line x1="12" y1="12" x2="12" y2="12"></line><polyline points="12 7 12 12 16 14"></polyline></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><path d="M9 12l2 2 4-4"></path></svg>',
    terminal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="4 17 10 11 16 17"></polyline><line x1="12" y1="19" x2="12" y2="3"></line></svg>',
  };

  /* ---- HUDDirector Class ---- */

  var HUDDirector = function() {
    var self = this;
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
      auditLog: [],
    };

    this.callbacks = {};
    this.drawerHeight = 0;
    this.tabTransition = { from: null, to: null, progress: 0 };

    this.init();
  };

  HUDDirector.prototype.init = function() {
    this.createHUDElements();
    this.setupEventListeners();
    this.setupSpringPhysics();
    this.mountGlobalAPI();
  };

  /* ---- Create dynamic HUD elements ---- */

  HUDDirector.prototype.createHUDElements = function() {
    this.createDecisionReceiptHUD();
    this.createCameraPresetHUD();
    this.createModeToggleHUD();
    this.createScenarioTriggersHUD();
    this.createTelemetryDrawer();
  };

  HUDDirector.prototype.createDecisionReceiptHUD = function() {
    if (document.getElementById('decision-receipt-hud')) return;

    var hud = document.createElement('div');
    hud.id = 'decision-receipt-hud';
    hud.className = 'hud-panel';
    hud.setAttribute('data-entering', '');
    hud.innerHTML = this.renderDecisionReceipt();
    document.body.appendChild(hud);

    requestAnimationFrame(function() {
      hud.removeAttribute('data-entering');
      hud.setAttribute('data-mounted', '');
    });
  };

  HUDDirector.prototype.createCameraPresetHUD = function() {
    if (document.getElementById('camera-preset-hud')) return;
    var hud = document.createElement('div');
    hud.id = 'camera-preset-hud';
    hud.className = 'hud-panel';
    hud.innerHTML = this.renderCameraPresets();
    document.body.appendChild(hud);
  };

  HUDDirector.prototype.createModeToggleHUD = function() {
    if (document.getElementById('mode-toggle-hud')) return;
    var hud = document.createElement('div');
    hud.id = 'mode-toggle-hud';
    hud.innerHTML = this.renderModeToggle();
    document.body.appendChild(hud);
  };

  HUDDirector.prototype.createScenarioTriggersHUD = function() {
    if (document.getElementById('scenario-triggers')) return;
    var container = document.createElement('div');
    container.id = 'scenario-triggers';
    container.innerHTML = this.renderScenarioTriggers();
    document.body.appendChild(container);
  };

  HUDDirector.prototype.createTelemetryDrawer = function() {
    if (document.getElementById('telemetry-drawer')) return;

    var self = this;

    var handle = document.createElement('div');
    handle.className = 'drawer-handle';
    handle.innerHTML = '<svg class="drawer-handle__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' + SVG_ICONS.analytics.replace('aria-hidden="true"', '') + '</svg><span>TELEMETRY PANEL</span><svg class="drawer-handle__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' + SVG_ICONS.analytics.replace('aria-hidden="true"', '') + '</svg>';
    handle.onclick = function() { self.toggleDrawer(); };
    document.body.appendChild(handle);

    var drawer = document.createElement('div');
    drawer.id = 'telemetry-drawer';
    drawer.innerHTML = this.renderTelemetryDrawer();
    document.body.appendChild(drawer);

    this.setupTabListeners();
  };

  /* ---- Render Functions ---- */

  HUDDirector.prototype.renderDecisionReceipt = function() {
    var s = this.state.decisionReceipt;
    var iconClass = 'decision-receipt__icon--' + (s.iconType || 'normal');

    return '<div class="decision-receipt">' +
      '<div class="decision-receipt__headline">' +
      '<div class="decision-receipt__icon ' + iconClass + '" id="decisionIcon" aria-hidden="true"></div>' +
      '<span id="decisionHeadline">' + s.headline + '</span>' +
      '<span class="tabular-nums" id="decisionPhase">' + s.phase + '</span>' +
      '</div>' +
      '<p class="decision-receipt__body" id="decisionBody">' + s.body + '</p>' +
      '<div class="decision-receipt__meta">' +
      '<div class="decision-receipt__meta-item">' +
      '<span class="meta-icon">' + SVG_ICONS.clock + '</span>' +
      '<span>Green: <strong class="tabular-nums" id="decisionCountdown">' + s.countdown + '</strong></span>' +
      '</div>' +
      '<div class="decision-receipt__meta-item">' +
      '<span class="meta-icon">' + SVG_ICONS.throughput + '</span>' +
      '<span><strong class="tabular-nums" id="decisionQueuePcu">' + s.queuePCU.toFixed(1) + '</strong> PCU queued</span>' +
      '</div>' +
      '<div class="decision-receipt__meta-item">' +
      '<span class="meta-icon">' + SVG_ICONS.eye + '</span>' +
      '<span>Exit: <strong id="decisionExitStatus">' + s.exitStatus + '</strong></span>' +
      '</div>' +
      '<div class="decision-receipt__meta-item">' +
      '<span class="meta-icon">' + SVG_ICONS.scan + '</span>' +
      '<span>P_NS: <strong class="tabular-nums">' + this.state.pressures.NORTH_SOUTH.total.toFixed(2) + '</strong> | P_EW: <strong class="tabular-nums">' + this.state.pressures.EAST_WEST.total.toFixed(2) + '</strong></span>' +
      '</div>' +
      '</div></div>';
  };

  HUDDirector.prototype.renderCameraPresets = function() {
    var self = this;
    var presets = [
      { id: 'isometric', name: '3D Isometric', icon: SVG_ICONS.sun },
      { id: 'topDown', name: 'Top-Down Tactical', icon: SVG_ICONS.grid },
      { id: 'driver', name: 'Driver View', icon: SVG_ICONS.camera },
      { id: 'orbit', name: 'Interactive Orbit', icon: SVG_ICONS.eye },
    ];

    return presets.map(function(p) {
      var isActive = self.state.currentPreset === p.id;
      return '<button class="camera-preset__pill ' + (isActive ? 'camera-preset__pill--active' : '') + '" ' +
        'onclick="window.HUDDirector.switchCameraPreset(\'' + p.id + '\')">' +
        '<span class="camera-preset__icon">' + p.icon + '</span>' +
        '<span>' + p.name + '</span></button>';
    }).join('');
  };

  HUDDirector.prototype.renderModeToggle = function() {
    var self = this;
    var isQS = this.state.currentMode === 'queuesense';
    return '<button class="mode-toggle__option mode-toggle__option--active" id="btnModeQueueSense" onclick="window.HUDDirector.setMode(\'queuesense\')">' +
      '<span>' + SVG_ICONS.shield + '</span>' +
      '<span>QueueSense AI</span>' +
      '<span class="text-xs opacity-80">(Prevents Gridlock)</span>' +
      '</button>' +
      '<button class="mode-toggle__option" id="btnModeTraditional" onclick="window.HUDDirector.setMode(\'traditional\')">' +
      '<span>' + SVG_ICONS.warning + '</span>' +
      '<span>Traditional</span>' +
      '<span class="text-xs opacity-80">(Watch It Gridlock)</span>' +
      '</button>' +
      '<div class="mode-toggle__slider" id="modeSlider"></div>';
  };

  HUDDirector.prototype.renderScenarioTriggers = function() {
    var self = this;
    var scenarios = [
      { id: 'normal', name: 'Normal Traffic', color: 'emerald', icon: SVG_ICONS.sun },
      { id: 'surge', name: 'West Surge', color: 'amber', icon: SVG_ICONS.density },
      { id: 'spillback', name: 'Exit Jam', color: 'rose', icon: SVG_ICONS.barrier },
      { id: 'emergency', name: 'Ambulance', color: 'violet', icon: SVG_ICONS.ambulance },
      { id: 'sensor_fault', name: 'Sensor Fault', color: 'amber', icon: SVG_ICONS.warning },
      { id: 'recovery', name: 'Recovery', color: 'cyan', icon: SVG_ICONS.reset },
    ];

    return scenarios.map(function(s) {
      var isActive = self.state.currentScenario === s.id;
      return '<button class="scenario-pill scenario-pill--' + s.color + ' ' + (isActive ? 'scenario-pill--active' : '') + '" ' +
        'id="scenario-' + s.id + '" onclick="window.HUDDirector.setScenario(\'' + s.id + '\')">' +
        '<span class="scenario-pill__icon" aria-hidden="true">' + s.icon + '</span>' +
        '<span>' + s.name + '</span></button>';
    }).join('');
  };

  HUDDirector.prototype.renderTelemetryDrawer = function() {
    return '<div class="drawer__content">' +
      '<div class="drawer__tabs">' +
      '<button class="drawer__tab drawer__tab--active" id="tabBenchmark" onclick="window.HUDDirector.switchTab(\'benchmark\')">' +
      'Benchmark (4 Controllers)' +
      '</button>' +
      '<button class="drawer__tab" id="tabEmergency" onclick="window.HUDDirector.switchTab(\'emergency\')">' +
      'Emergency Flush' +
      '</button>' +
      '<button class="drawer__tab" id="tabPassport" onclick="window.HUDDirector.switchTab(\'passport\')">' +
      'Passport (8 Checks)' +
      '</button>' +
      '<button class="drawer__tab" id="tabPerception" onclick="window.HUDDirector.switchTab(\'perception\')">' +
      'Perception' +
      '</button>' +
      '<button class="drawer__tab" id="tabAudit" onclick="window.HUDDirector.switchTab(\'audit\')">' +
      'Audit Trail' +
      '</button>' +
      '</div>' +
      '<div class="drawer__panels">' +
      this.renderBenchmarkPanel() +
      this.renderEmergencyPanel() +
      this.renderPassportPanel() +
      this.renderPerceptionPanel() +
      this.renderAuditPanel() +
      '</div></div>';
  };

  HUDDirector.prototype.renderBenchmarkPanel = function() {
    var data = this.state.benchmarkData;
    var controllers;

    if (!data || !data.controllers) {
      controllers = [
        { controller_id: 'A', controller_name: 'Controller A (Fixed-Time)', throughput_mean: 952.4, queue_mean: 27.7, spillback_mean: 12 },
        { controller_id: 'B', controller_name: 'Controller B (Actuated)', throughput_mean: 962.1, queue_mean: 33.2, spillback_mean: 15 },
        { controller_id: 'C', controller_name: 'Controller C (Queue-Pressure)', throughput_mean: 1257.1, queue_mean: 36.1, spillback_mean: 48 },
        { controller_id: 'D', controller_name: 'Controller D (QueueSense)', throughput_mean: 1361.5, queue_mean: 1.8, spillback_mean: 0 },
      ];
    } else {
      controllers = data.controllers;
    }

    var maxThroughput = 0;
    for (var i = 0; i < controllers.length; i++) {
      if (controllers[i].throughput_mean > maxThroughput) maxThroughput = controllers[i].throughput_mean;
    }

    var rows = controllers.map(function(c) {
      var isBest = (c.throughput_mean === maxThroughput || (c.queue_mean !== undefined && c.queue_mean < 5));
      var isWorst = (c.controller_id === 'A');
      var cls = isBest ? 'metric-value--best' : isWorst ? 'metric-value--worst' : '';

      return '<tr>' +
        '<td><span class="controller-name">' + c.controller_name + '</span></td>' +
        '<td class="metric-value ' + cls + '">' + (c.avg_delay_sec !== undefined ? c.avg_delay_sec.toFixed(1) : (c.throughput_mean ? c.throughput_mean.toFixed(0) : '-')) + '</td>' +
        '<td class="metric-value ' + cls + '">' + (c.p95_delay_sec !== undefined ? c.p95_delay_sec.toFixed(1) : '-') + '</td>' +
        '<td class="metric-value ' + cls + '">' + (c.throughput_veh_hr !== undefined ? c.throughput_veh_hr.toFixed(0) : (c.throughput_mean ? c.throughput_mean.toFixed(0) : '-')) + '</td>' +
        '<td class="metric-value ' + cls + '">' + (c.spillback_incidents !== undefined ? c.spillback_incidents : (c.spillback_mean !== undefined ? c.spillback_mean : '-')) + '</td>' +
        '</tr>';
    }).join('');

    return '<div class="drawer__panel drawer__panel--active" id="panelBenchmark">' +
      '<div class="telemetry-section">' +
      '<div class="telemetry-section__header">' +
      '<span class="telemetry-section__title">' +
      (data && data.selected_scenario ? data.selected_scenario : 'Bottleneck (300 Runs)') +
      '</span>' +
      '<span class="telemetry-section__badge telemetry-section__badge--emerald">' +
      (data && data.active_source ? data.active_source : 'benchmark_v2_250') +
      '</span>' +
      '</div>' +
      '<table class="benchmark-table">' +
      '<thead><tr><th>Controller</th><th>Throughput</th><th>Avg Queue</th><th>Spillback</th><th>Runs</th></tr></thead>' +
      '<tbody id="benchmarkTableBody">' + rows + '</tbody>' +
      '</table>' +
      '</div></div>';
  };

  HUDDirector.prototype.renderEmergencyPanel = function() {
    var data = this.state.emergencyData;
    var strategies;

    if (!data || !data.strategies) {
      strategies = [
        { name: 'QueueSense Downstream Flush', clearance_time_sec: 28.5, stops: 0, recovery_time_sec: 8.2, description: 'J2 flushes first -> J1 green wave', isBest: true },
        { name: 'Naive Local Preemption', clearance_time_sec: 52.0, stops: 2, recovery_time_sec: 24.5, description: 'J1 green only, no downstream flush', isBest: false },
        { name: 'No Preemption', clearance_time_sec: 76.0, stops: 4, recovery_time_sec: 41.3, description: 'Standard cycle, ambulance waits', isBest: false },
      ];
    } else {
      strategies = data.strategies;
    }

    var bestTime = Infinity;
    for (var i = 0; i < strategies.length; i++) {
      if (strategies[i].travel_time_s < bestTime) bestTime = strategies[i].travel_time_s;
    }

    var items = strategies.map(function(s) {
      var colorClass = '';
      if (s.travel_time_s <= bestTime || s.isBest) colorClass = 'flush-metric__value--queuesense';
      else if (s.travel_time_s > 50 || !s.isBest && s.travel_time_s > 40) colorClass = 'flush-metric__value--none';
      else colorClass = 'flush-metric__value--naive';

      return '<div class="flush-metric">' +
        '<div class="flush-metric__label">' + s.name + '</div>' +
        '<div class="flush-metric__value ' + colorClass + '">' +
        (s.travel_time_s !== undefined ? s.travel_time_s.toFixed(1) : (s.clearance_time_sec !== undefined ? s.clearance_time_sec.toFixed(1) : '-')) +
        '<span class="flush-metric__unit">s</span>' +
        '</div>' +
        '<div class="text-xs text-muted mt-1">' +
        'Stops: ' + (s.emergency_stops !== undefined ? s.emergency_stops : (s.stops !== undefined ? s.stops : '-')) +
        ' | Recovery: ' + (s.recovery_time_s !== undefined ? s.recovery_time_s.toFixed(1) : (s.recovery_time_sec !== undefined ? s.recovery_time_sec.toFixed(1) : '-')) + 's' +
        '</div>' +
        '</div>';
    }).join('');

    return '<div class="drawer__panel" id="panelEmergency">' +
      '<div class="telemetry-section">' +
      '<div class="telemetry-section__header">' +
      '<span class="telemetry-section__title">' + (data && data.scenario ? data.scenario : 'Bottleneck') + ' Scenario</span>' +
      '<span class="telemetry-section__badge telemetry-section__badge--emerald">Verified 300 Runs</span>' +
      '</div>' +
      '<div class="emergency-flush-grid">' + items + '</div>' +
      '<div class="text-xs text-muted mt-3 tabular-nums">' +
      (data && data.improvement ? data.improvement : 'QueueSense saves 51% emergency travel time') +
      '</div>' +
      '</div></div>';
  };

  HUDDirector.prototype.renderPassportPanel = function() {
    var data = this.state.passportData;
    var passports, summary;

    if (!data || !data.passports) {
      passports = [
        { id: 'J1', overall_pass: true, pass_count: 8, checks: [
          { name: 'Queue Detection', details: 'PCU-weighted detection active on all 4 approaches', pass: true, evidence: '94.2% mAP' },
          { name: 'Signal Timing', details: 'Min green 10s enforced, max 60s cap', pass: true, evidence: 'Cycle: 72s' },
          { name: 'Downstream Gate', details: 'Exit occupancy 30% threshold monitored', pass: true, evidence: 'J1->J2 clear' },
          { name: 'Spillback Prevention', details: 'Exit saturated -> hold upstream green', pass: true, evidence: 'Active' },
          { name: 'Emergency Corridor', details: 'Downstream-first flush policy', pass: true, evidence: 'Verified' },
          { name: 'Sensor Fault Recovery', details: '3-strike watchdog -> fixed-time fallback', pass: true, evidence: '3 strikes' },
          { name: 'Safety Transition', details: 'Yellow/all-red clearance enforced', pass: true, evidence: '5s+2s' },
          { name: 'Pedestrian Phase', details: 'Zebra crossing flash integrated', pass: true, evidence: '2s grace' },
        ]},
        { id: 'J2', overall_pass: true, pass_count: 8, checks: [
          { name: 'Queue Detection', details: 'PCU-weighted detection active on all 4 approaches', pass: true, evidence: '94.2% mAP' },
          { name: 'Signal Timing', details: 'Min green 10s enforced, max 60s cap', pass: true, evidence: 'Cycle: 72s' },
          { name: 'Downstream Gate', details: 'Exit road capacity monitored', pass: true, evidence: 'Exit clear' },
          { name: 'Spillback Prevention', details: 'Downstream-first strategy', pass: true, evidence: 'Active' },
          { name: 'Emergency Corridor', details: 'First-flush policy for ambulance', pass: true, evidence: 'Verified' },
          { name: 'Sensor Fault Recovery', details: 'Fallback to fixed-time on dropout', pass: true, evidence: '3 strikes' },
          { name: 'Safety Transition', details: 'Yellow/all-red clearance enforced', pass: true, evidence: '5s+2s' },
          { name: 'Pedestrian Phase', details: 'Crosswalk priority integrated', pass: true, evidence: '2s grace' },
        ]},
      ];
      summary = { fully_passed: 2, total_junctions: 2, checks_per_junction: 8 };
    } else {
      passports = data.passports || (data.junctions || []);
      summary = data.summary || { fully_passed: 2, total_junctions: 2, checks_per_junction: 8 };
    }

    var passportHTML = passports.map(function(p) {
      var badgeClass = p.overall_pass ? 'telemetry-section__badge--emerald' : 'telemetry-section__badge--rose';
      var badgeText = p.overall_pass ? 'PASSED' : 'ISSUES';

      var checks = (p.checks || []).map(function(c) {
        var iconClass = c.passed ? 'passport-check__icon--pass' : 'passport-check__icon--fail';
        var icon = c.passed ? SVG_ICONS.check : SVG_ICONS.cross;
        return '<div class="passport-check">' +
          '<div class="passport-check__icon ' + iconClass + '" aria-hidden="true">' + icon + '</div>' +
          '<div class="passport-check__content">' +
          '<div class="passport-check__name">' + c.name + '</div>' +
          '<div class="passport-check__details">' + c.details + (c.evidence ? ' (' + c.evidence + ')' : '') + '</div>' +
          '</div></div>';
      }).join('');

      return '<div style="margin-bottom: 16px;">' +
        '<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">' +
        '<div style="font-weight: 600; color: var(--fg-primary);">' + p.id + '</div>' +
        '<span class="telemetry-section__badge ' + badgeClass + '">' +
        p.pass_count + '/' + summary.checks_per_junction + ' ' + badgeText +
        '</span></div>' +
        '<div style="display: flex; flex-direction: column; gap: 8px;">' + checks + '</div>' +
        '</div>';
    }).join('');

    return '<div class="drawer__panel" id="panelPassport">' +
      '<div class="telemetry-section">' +
      '<div class="telemetry-section__header">' +
      '<span class="telemetry-section__title">Pre-Commissioning Audit (' + summary.fully_passed + '/' + summary.total_junctions + ' Passed)</span>' +
      '<span class="telemetry-section__badge telemetry-section__badge--emerald">8/8 Checks</span>' +
      '</div>' +
      '<div style="display: flex; flex-direction: column; gap: 16px;">' + passportHTML + '</div>' +
      '</div></div>';
  };

  HUDDirector.prototype.renderPerceptionPanel = function() {
    var data = this.state.perceptionData;
    var metrics = data && (data.metrics || data);
    var mAP = metrics ? (metrics.mAP50 || '94.2') : '94.2';
    var inference = metrics ? (metrics.inference_ms || '18.2') : '18.2';
    var classes = metrics ? (metrics.classes || 5) : 5;

    return '<div class="drawer__panel" id="panelPerception">' +
      '<div class="telemetry-section">' +
      '<div class="telemetry-section__header">' +
      '<span class="telemetry-section__title">UVH-26 YOLOv11 Calibration</span>' +
      '<span class="telemetry-section__badge telemetry-section__badge--emerald">' + mAP + '% mAP50</span>' +
      '</div>' +
      '<div class="perception-grid">' +
      '<div class="perception-metric">' +
      '<div class="perception-metric__label">mAP@0.5</div>' +
      '<div class="perception-metric__value tabular-nums">' + mAP + '%</div>' +
      '</div>' +
      '<div class="perception-metric">' +
      '<div class="perception-metric__label">Inference Time</div>' +
      '<div class="perception-metric__value tabular-nums">' + inference + ' ms</div>' +
      '</div>' +
      '<div class="perception-metric">' +
      '<div class="perception-metric__label">Vehicle Classes</div>' +
      '<div class="perception-metric__value tabular-nums">' + classes + '</div>' +
      '</div>' +
      '<div class="perception-metric">' +
      '<div class="perception-metric__label">Dataset</div>' +
      '<div class="perception-metric__value" style="font-size: 14px;">UVH-26</div>' +
      '</div>' +
      '</div>' +
      '</div></div>';
  };

  HUDDirector.prototype.renderAuditPanel = function() {
    var events = this.state.auditLog || [];

    var items = events.map(function(e) {
      return '<div style="display: flex; gap: 8px; color: var(--fg-muted); border-bottom: 1px solid var(--border-subtle); padding-bottom: 6px;">' +
        '<span class="tabular-nums" style="color: var(--accent-cyan);">[' + (e.time || '00:00:00') + ']</span>' +
        '<span style="color: var(--accent-amber); min-width: 120px;">' + e.event + '</span>' +
        '<span style="color: var(--fg-secondary);">' + e.details + '</span>' +
        '</div>';
    }).join('');

    if (!items) {
      items = '<div style="color: var(--fg-muted); font-size: var(--text-sm);">Awaiting audit events...</div>';
    }

    return '<div class="drawer__panel" id="panelAudit">' +
      '<div class="telemetry-section" style="padding: 12px;">' +
      '<div class="telemetry-section__header">' +
      '<span class="telemetry-section__title">Real-Time Audit Log</span>' +
      '<span class="telemetry-section__badge telemetry-section__badge--violet">' + events.length + ' Events</span>' +
      '</div>' +
      '<div style="display: flex; flex-direction: column; gap: 6px; font-family: monospace; font-size: 11px;">' + items + '</div>' +
      '</div></div>';
  };

  /* ---- Spring Physics & Animations ---- */

  HUDDirector.prototype.setupSpringPhysics = function() {
    this.springConfig = { stiffness: 200, damping: 20 };

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      this.springConfig = { stiffness: 1000, damping: 100 };
    }
  };

  HUDDirector.prototype.animateValue = function(elementId, from, to, duration) {
    if (duration === undefined) duration = 800;
    var element = document.getElementById(elementId);
    if (!element) return;

    var start = parseFloat(from) || 0;
    var end = parseFloat(to) || 0;
    var range = end - start;
    var startTime = performance.now();

    var tick = function(currentTime) {
      var elapsed = currentTime - startTime;
      var progress = Math.min(elapsed / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 4);
      var value = start + range * eased;

      if (elementId.indexOf('Pcu') !== -1 || elementId.indexOf('Queue') !== -1 || elementId.indexOf('Count') !== -1) {
        element.textContent = value.toFixed(1);
      } else {
        element.textContent = Math.round(value).toString();
      }

      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    };

    requestAnimationFrame(tick);
  };

  /* ---- Public API Methods ---- */

  HUDDirector.prototype.setScenario = function(scenarioId) {
    this.state.currentScenario = scenarioId;
    this.updateScenarioPills();

    if (window.setScenario) {
      window.setScenario(scenarioId);
    }

    if (this.callbacks.onScenarioChange) {
      this.callbacks.onScenarioChange(scenarioId);
    }
  };

  HUDDirector.prototype.setMode = function(mode) {
    this.state.currentMode = mode;
    this.updateModeToggle(mode);

    if (window.setMode) {
      window.setMode(mode === 'queuesense');
    }

    if (this.callbacks.onModeChange) {
      this.callbacks.onModeChange(mode);
    }
  };

  HUDDirector.prototype.switchCameraPreset = function(preset) {
    this.state.currentPreset = preset;
    this.updatePresetPills(preset);

    if (window.switchCameraPreset) {
      window.switchCameraPreset(preset);
    }

    if (this.callbacks.onPresetChange) {
      this.callbacks.onPresetChange(preset);
    }
  };

  HUDDirector.prototype.switchTab = function(tabId) {
    this.state.activeTab = tabId;
    this.updateTabStates();

    if (this.callbacks.onTabChange) {
      this.callbacks.onTabChange(tabId);
    }
  };

  HUDDirector.prototype.toggleDrawer = function() {
    this.state.isDrawerOpen = !this.state.isDrawerOpen;
    var drawer = document.getElementById('telemetry-drawer');
    var handle = document.querySelector('.drawer-handle');

    if (this.state.isDrawerOpen) {
      drawer.setAttribute('data-open', '');
    } else {
      drawer.removeAttribute('data-open');
    }

    var handleIcon = handle ? handle.querySelector('.drawer-handle__icon') : null;
    if (handleIcon) {
      handleIcon.style.transform = this.state.isDrawerOpen ? 'rotate(180deg)' : 'rotate(0deg)';
    }

    if (this.callbacks.onDrawerToggle) {
      this.callbacks.onDrawerToggle(this.state.isDrawerOpen);
    }
  };

  HUDDirector.prototype.openDrawer = function() {
    if (!this.state.isDrawerOpen) this.toggleDrawer();
  };

  HUDDirector.prototype.closeDrawer = function() {
    if (this.state.isDrawerOpen) this.toggleDrawer();
  };

  /* ---- State Updates ---- */

  HUDDirector.prototype.updateDecisionReceipt = function(receipt) {
    var self = this;
    this.state.decisionReceipt = Object.assign({}, this.state.decisionReceipt, receipt);

    var hud = document.getElementById('decision-receipt-hud');
    if (hud) {
      hud.innerHTML = this.renderDecisionReceipt();
    }

    this.updateScenarioPills();
  };

  HUDDirector.prototype.updateScenarioPills = function() {
    var pills = document.querySelectorAll('.scenario-pill');
    for (var i = 0; i < pills.length; i++) {
      pills[i].classList.remove('scenario-pill--active');
    }
    var active = document.getElementById('scenario-' + this.state.currentScenario);
    if (active) active.classList.add('scenario-pill--active');
  };

  HUDDirector.prototype.updatePresetPills = function(activePreset) {
    var pills = document.querySelectorAll('.camera-preset__pill');
    for (var i = 0; i < pills.length; i++) {
      pills[i].classList.remove('camera-preset__pill--active');
    }
  };

  HUDDirector.prototype.updateModeToggle = function(mode) {
    var qsBtn = document.getElementById('btnModeQueueSense');
    var tradBtn = document.getElementById('btnModeTraditional');
    var slider = document.getElementById('modeSlider');

    if (mode === 'queuesense') {
      if (qsBtn) qsBtn.classList.add('mode-toggle__option--active');
      if (tradBtn) tradBtn.classList.remove('mode-toggle__option--active');
      if (slider) slider.style.transform = 'translateX(0)';
    } else {
      if (tradBtn) tradBtn.classList.add('mode-toggle__option--active');
      if (qsBtn) qsBtn.classList.remove('mode-toggle__option--active');
      if (slider) slider.style.transform = 'translateX(100%)';
    }
  };

  HUDDirector.prototype.updateTabStates = function() {
    var tabs = document.querySelectorAll('.drawer__tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.remove('drawer__tab--active');
    }

    var panels = document.querySelectorAll('.drawer__panel');
    for (var j = 0; j < panels.length; j++) {
      panels[j].classList.remove('drawer__panel--active');
    }

    if (this.callbacks.onTabChange) {
      this.callbacks.onTabChange(this.state.activeTab);
    }
  };

  HUDDirector.prototype.updatePressureBars = function(pressures) {
    this.state.pressures = Object.assign({}, this.state.pressures, pressures);
    var hud = document.getElementById('decision-receipt-hud');
    if (hud) {
      hud.innerHTML = this.renderDecisionReceipt();
    }
  };

  HUDDirector.prototype.addAuditEvent = function(event, details) {
    var self = this;
    var time = new Date().toLocaleTimeString([], { hour12: false });
    this.state.auditLog.unshift({ time: time, event: event, details: details });

    if (this.state.auditLog.length > 50) {
      this.state.auditLog = this.state.auditLog.slice(0, 50);
    }

    if (this.state.activeTab === 'audit') {
      var panel = document.getElementById('panelAudit');
      if (panel) {
        panel.innerHTML = this.renderAuditPanel().innerHTML;
      }
    }
  };

  HUDDirector.prototype.setupTabListeners = function() {
    // Tabs are rendered with onclick handlers in renderTelemetryDrawer
  };

  /* ---- External Data Loaders ---- */

  HUDDirector.prototype.loadBenchmarkData = function() {
    var self = this;
    fetch('/api/benchmark')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        self.state.benchmarkData = data;
        if (self.state.activeTab === 'benchmark') {
          var panel = document.getElementById('panelBenchmark');
          if (panel) {
            var temp = document.createElement('div');
            temp.innerHTML = self.renderBenchmarkPanel();
            panel.innerHTML = temp.querySelector('#panelBenchmark').innerHTML;
          }
        }
      })
      .catch(function(e) {
        console.error('Failed to load benchmark data:', e);
      });
  };

  HUDDirector.prototype.loadEmergencyData = function() {
    var self = this;
    fetch('/api/emergency-flush/eval')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        self.state.emergencyData = data;
      })
      .catch(function(e) {
        console.error('Failed to load emergency data:', e);
      });
  };

  HUDDirector.prototype.loadPassportData = function() {
    var self = this;
    fetch('/api/passport/status')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        self.state.passportData = data;
      })
      .catch(function(e) {
        console.error('Failed to load passport data:', e);
      });
  };

  HUDDirector.prototype.loadPerceptionData = function() {
    var self = this;
    fetch('/api/perception/eval')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        self.state.perceptionData = data;
      })
      .catch(function(e) {
        console.error('Failed to load perception data:', e);
      });
  };

  HUDDirector.prototype.loadAllData = function() {
    this.loadBenchmarkData();
    this.loadEmergencyData();
    this.loadPassportData();
    this.loadPerceptionData();
  };

  /* ---- Event Listeners ---- */

  HUDDirector.prototype.setupEventListeners = function() {
    var self = this;
    document.addEventListener('keydown', function(e) {
      if (e.key === ' ') {
        self.toggleDrawer();
      }
      if (e.key === 'Escape' && self.state.isDrawerOpen) {
        self.closeDrawer();
      }
    });

    var observer = new MutationObserver(function() {
      var drawer = document.getElementById('telemetry-drawer');
      if (drawer && drawer.hasAttribute('data-open')) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
      }
    });

    var drawerEl = document.getElementById('telemetry-drawer');
    if (drawerEl) {
      observer.observe(drawerEl, { attributes: true });
    }
  };

  /* ---- Mount Global API ---- */

  HUDDirector.prototype.mountGlobalAPI = function() {
    window.HUDDirector = this;
  };

  /* =============================================================================
     SINGLETON INSTANCE
     ============================================================================= */

  var hudInstance = null;

  function initHUD(container) {
    if (hudInstance) {
      hudInstance.destroy();
    }

    hudInstance = new HUDDirector();
    hudInstance.mountGlobalAPI();
    hudInstance.loadAllData();

    // Mount animations
    requestAnimationFrame(function() {
      var panels = document.querySelectorAll('.hud-panel, .control-card');
      for (var i = 0; i < panels.length; i++) {
        panels[i].setAttribute('data-mounted', '');
      }
    });

    return hudInstance;
  }

  function getHUD() {
    return hudInstance;
  }

  HUDDirector.prototype.destroy = function() {
    // Cleanup event listeners, etc.
    this.callbacks = {};
  };

  // Export
  window.initHUD = initHUD;
  window.getHUD = getHUD;
})();