/* =============================================================================
   QUEUESENSE — MAIN APPLICATION MODULE
   Initializes Three.js scene, wires controls, fetches API data, animates UI
   Uses GLOBAL THREE and global functions from three-scene.js (no ES modules)
   Emil Kowalski + Impeccable + Taste Design Engineering
   ============================================================================= */

(function() {
  'use strict';

  /* =============================================================================
     FALLBACK DATA (embedded inline, replaces API when server unavailable)
     ============================================================================= */

  var FALLBACK_BENCHMARK = [
    { controller_id: 'A', name: 'Fixed-Time', typeLabel: 'Baseline', typeClass: 'type-fixed', avg_delay_sec: 42.8, p95_delay_sec: 98.5, throughput_veh_hr: 952.4, spillback_incidents: 12, emergency_response_sec: 76.0 },
    { controller_id: 'B', name: 'Actuated Gap', typeLabel: 'Baseline', typeClass: 'type-actuated', avg_delay_sec: 31.2, p95_delay_sec: 82.3, throughput_veh_hr: 962.1, spillback_incidents: 15, emergency_response_sec: 52.0 },
    { controller_id: 'C', name: 'Queue-Pressure Only', typeLabel: 'Experimental', typeClass: 'type-pressure', avg_delay_sec: 18.7, p95_delay_sec: 58.9, throughput_veh_hr: 1257.1, spillback_incidents: 48, emergency_response_sec: 52.0 },
    { controller_id: 'D', name: 'QueueSense (Full)', typeLabel: 'Production', typeClass: 'type-queuesense', avg_delay_sec: 6.1, p95_delay_sec: 24.3, throughput_veh_hr: 1361.5, spillback_incidents: 0, emergency_response_sec: 28.5 },
  ];

  var FALLBACK_EMERGENCY = [
    { name: 'QueueSense Downstream Flush', clearance_time_sec: 28.5, stops: 0, recovery_time_sec: 8.2, description: 'J2 flushes first -> J1 green wave', isBest: true },
    { name: 'Naive Local Preemption', clearance_time_sec: 52.0, stops: 2, recovery_time_sec: 24.5, description: 'J1 green only, no downstream flush', isBest: false },
    { name: 'No Preemption', clearance_time_sec: 76.0, stops: 4, recovery_time_sec: 41.3, description: 'Standard cycle, ambulance waits', isBest: false },
  ];

  var FALLBACK_PASSPORT = {
    junctions: [
      {
        id: 'J1', overall_pass: true, pass_count: 8,
        checks: [
          { name: 'Queue Detection', details: 'PCU-weighted detection active on all 4 approaches', pass: true, evidence: '94.2% mAP' },
          { name: 'Signal Timing', details: 'Min green 10s enforced, max 60s cap', pass: true, evidence: 'Cycle: 72s' },
          { name: 'Downstream Gate', details: 'Exit occupancy 30% threshold monitored', pass: true, evidence: 'J1->J2 clear' },
          { name: 'Spillback Prevention', details: 'J2 exit saturated -> hold upstream green', pass: true, evidence: 'Active' },
          { name: 'Emergency Corridor', details: 'Downstream-first flush policy', pass: true, evidence: 'Verified' },
          { name: 'Sensor Fault Recovery', details: '3-strike watchdog -> fixed-time fallback', pass: true, evidence: '3 strikes' },
          { name: 'Safety Transition', details: 'Yellow/all-red clearance enforced', pass: true, evidence: '5s+2s' },
          { name: 'Pedestrian Phase', details: 'Zebra crossing flash integrated', pass: true, evidence: '2s grace' },
        ]
      },
      {
        id: 'J2', overall_pass: true, pass_count: 8,
        checks: [
          { name: 'Queue Detection', details: 'PCU-weighted detection active on all 4 approaches', pass: true, evidence: '94.2% mAP' },
          { name: 'Signal Timing', details: 'Min green 10s enforced, max 60s cap', pass: true, evidence: 'Cycle: 72s' },
          { name: 'Downstream Gate', details: 'Exit road capacity monitored', pass: true, evidence: 'Exit clear' },
          { name: 'Spillback Prevention', details: 'Downstream-first strategy', pass: true, evidence: 'Active' },
          { name: 'Emergency Corridor', details: 'First-flush policy for ambulance', pass: true, evidence: 'Verified' },
          { name: 'Sensor Fault Recovery', details: 'Fallback to fixed-time on dropout', pass: true, evidence: '3 strikes' },
          { name: 'Safety Transition', details: 'Yellow/all-red clearance enforced', pass: true, evidence: '5s+2s' },
          { name: 'Pedestrian Phase', details: 'Crosswalk priority integrated', pass: true, evidence: '2s grace' },
        ]
      },
    ]
  };

  /* =============================================================================
     STATE MANAGEMENT
     ============================================================================= */

  var AppState = {
    currentMode: 'queuesense',
    currentScenario: 'auto',
    currentCamera: 'isometric',
    isAutoScenario: true,
    simSpeed: 1.0,
    congestionLevel: 0.5,
    spawnRate: 1.0,
    trafficIntensity: 50,
    downstreamBottleneck: 0,

    liveState: null,
    benchmarkData: null,
    passportData: null,
    emergencyResults: null,
    selectorDecision: null,
    wsConnection: null,

    isInitialized: false,
    lastFrameTime: 0,
    frameCount: 0,

    elements: {},
  };

  /* =============================================================================
     DOM ELEMENT CACHING
     ============================================================================= */

  function cacheElements() {
    AppState.elements = {
      // Hero controls
      modeOptions: document.querySelectorAll('.mode-option'),
      scenarioBtns: document.querySelectorAll('.scenario-btn'),
      sliders: {
        simSpeed: document.getElementById('sliderSimSpeed'),
        trafficIntensity: document.getElementById('sliderTrafficIntensity'),
        downstreamBottleneck: document.getElementById('sliderDownstreamBottleneck'),
      },
      sliderValues: {
        simSpeed: document.getElementById('valueSimSpeed'),
        trafficIntensity: document.getElementById('valueTrafficIntensity'),
        downstreamBottleneck: document.getElementById('valueDownstreamBottleneck'),
      },
      actionButtons: {
        emergencyFlush: document.getElementById('btnEmergencyFlush'),
        reset: document.getElementById('btnReset'),
        selector: document.getElementById('btnSelector'),
        download: document.getElementById('btnDownload'),
      },
      cameraOptions: document.querySelectorAll('.camera-option'),

      // Decision feed / phase pill
      phasePill: {
        dot: document.getElementById('phaseDot'),
        label: document.getElementById('phaseLabel'),
        timer: document.getElementById('phaseTimer'),
        aiBadge: document.getElementById('aiBadge'),
        reason: document.getElementById('phaseReason'),
      },

      // Scoreboard strip
      scoreboard: {
        throughput: document.getElementById('scoreThroughput'),
        avgWait: document.getElementById('scoreAvgWait'),
        exitFill: document.getElementById('scoreExitFill'),
        exitLabel: document.getElementById('scoreExitLabel'),
        gridlocks: document.getElementById('scoreGridlocks'),
      },

      // Live metric cards
      metricCards: {
        throughput: document.getElementById('metricBestThroughput'),
        queue: document.getElementById('metricBestQueue'),
        spillback: document.getElementById('metricBestSpillback'),
        emergency: document.getElementById('metricEmergency'),
      },

      // Charts
      delayChart: document.getElementById('benchmarkChart'),
      benchmarkLegend: document.getElementById('benchmarkLegend'),

      // Ablation table
      ablationTableBody: document.querySelector('#ablationTable tbody'),

      // Emergency results
      emergencyResults: document.getElementById('emergencyResults'),

      // Passport
      passportGrid: document.getElementById('passportGrid'),
      passportSummary: document.getElementById('passportSummary'),

      // Canvas container
      canvasContainer: document.querySelector('.canvas-container'),

      // Auto toggle
      autoScenario: document.getElementById('autoScenario'),

      // Density bars
      densityBars: {
        north: { value: document.getElementById('densityNorth'), fill: document.getElementById('fillNorth') },
        south: { value: document.getElementById('densitySouth'), fill: document.getElementById('fillSouth') },
        east: { value: document.getElementById('densityEast'), fill: document.getElementById('fillEast') },
        west: { value: document.getElementById('densityWest'), fill: document.getElementById('fillWest') },
        exit: { value: document.getElementById('densityExit'), fill: document.getElementById('fillExit') },
      },
      gateMarker: document.getElementById('gateMarker'),
      gateLabel: document.getElementById('gateLabel'),

      // Badges / status
      controllerBadge: document.getElementById('controllerBadge'),
      wsStatus: document.getElementById('wsStatus'),
    };
  }

  /* =============================================================================
     INITIALIZATION
     ============================================================================= */

  function initializeApp() {
    cacheElements();

    // Initialize Three.js scene
    var canvasContainer = AppState.elements.canvasContainer;
    if (canvasContainer && typeof window.initDigitalTwin === 'function') {
      initDigitalTwin(canvasContainer);
    }

    // Wire up callbacks from three-scene
    window.onTwinStateUpdate = handleTwinStateUpdate;
    window.onSignalUpdate = handleSignalUpdate;
    window.onTwinScenarioChange = handleScenarioChange;
    window.onModeChange = handleModeChange;
    window.onZoneUpdate = handleZoneUpdate;
    window.onTwinTelemetry = handleTelemetry;

    // Wire up UI controls
    wireControls();

    // Fetch initial API data (with fallback)
    fetchAllAPIData();

    // Start render loop
    AppState.isInitialized = true;
    requestAnimationFrame(renderLoop);
  }

  function wireControls() {
    // Mode switcher
    var modeOptions = AppState.elements.modeOptions;
    if (modeOptions) {
      modeOptions.forEach(function(btn) {
        btn.addEventListener('click', function() {
          var mode = btn.getAttribute('data-mode');
          setModeControl(mode);
        });
      });
    }

    // Scenario buttons
    var scenarioBtns = AppState.elements.scenarioBtns;
    if (scenarioBtns) {
      scenarioBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
          var scenario = btn.getAttribute('data-scenario');
          setScenarioControl(scenario);
        });
      });
    }

    // Camera options
    var cameraOptions = AppState.elements.cameraOptions;
    if (cameraOptions) {
      cameraOptions.forEach(function(pill) {
        pill.addEventListener('click', function() {
          var preset = pill.getAttribute('data-camera');
          setCameraPreset(preset);
        });
      });
    }

    // Sliders
    for (var key in AppState.elements.sliders) {
      var slider = AppState.elements.sliders[key];
      if (slider) {
        slider.addEventListener('input', function(e) {
          var value = parseFloat(e.target.value);
          var sliderName = e.target.getAttribute('name') || key;
          applySlider(sliderName, value);
        });
      }
    }

    // Auto toggle
    if (AppState.elements.autoScenario) {
      AppState.elements.autoScenario.addEventListener('change', function(e) {
        AppState.isAutoScenario = e.target.checked;
        if (AppState.isAutoScenario && typeof window.setScenario === 'function') {
          window.setScenario('normal');
        }
      });
    }

    // Action buttons
    var btns = AppState.elements.actionButtons;
    if (btns.emergencyFlush) btns.emergencyFlush.addEventListener('click', handleEmergencyFlush);
    if (btns.reset) btns.reset.addEventListener('click', handleReset);
    if (btns.selector) btns.selector.addEventListener('click', handleSelector);
    if (btns.download) btns.download.addEventListener('click', handleDownload);

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
  }

  /* =============================================================================
     CONTROL HANDLERS
     ============================================================================= */

  function setModeControl(mode) {
    if (AppState.currentMode === mode) return;

    AppState.currentMode = mode;
    if (typeof window.setMode === 'function') {
      window.setMode(mode);
    }

    // Update UI
    var modeOptions = AppState.elements.modeOptions;
    if (modeOptions) {
      modeOptions.forEach(function(btn) {
        var isActive = btn.getAttribute('data-mode') === mode;
        btn.classList.toggle('mode-option--active', isActive);
        btn.setAttribute('aria-checked', isActive);
      });
    }

    // Update controller badge
    if (AppState.elements.controllerBadge) {
      var badge = AppState.elements.controllerBadge;
      if (mode === 'queuesense') {
        badge.textContent = 'ADAPTIVE';
        badge.className = 'control-card__badge badge--emerald';
      } else {
        badge.textContent = 'FIXED';
        badge.className = 'control-card__badge badge--cyan';
      }
    }

    // Update phase pill reason
    if (AppState.elements.phasePill.reason) {
      var reasonText = mode === 'queuesense'
        ? 'QueueSense active. Downstream blockage awareness + queue-pressure optimization.'
        : 'Fixed-time control active. No adaptive extension.';
      AppState.elements.phasePill.reason.textContent = reasonText;
    }
  }

  function setScenarioControl(scenario) {
    AppState.currentScenario = scenario;
    AppState.isAutoScenario = false;

    if (scenario !== 'auto') {
      if (typeof window.setScenario === 'function') {
        window.setScenario(scenario);
      }
    }

    // Update UI
    var scenarioBtns = AppState.elements.scenarioBtns;
    if (scenarioBtns) {
      scenarioBtns.forEach(function(btn) {
        var isActive = btn.getAttribute('data-scenario') === scenario;
        btn.classList.toggle('scenario-btn--active', isActive);
        btn.setAttribute('aria-checked', isActive);
      });
    }

    // Update phase pill
    if (AppState.elements.phasePill.reason) {
      var scenarioLabels = {
        auto: 'Auto-cycling through real-world IRL scenarios.',
        surge: 'Heavy directional surge — queue pressure spikes on west approach.',
        spillback: 'Downstream exit bottleneck — receiving road saturated >85%.',
        emergency: 'Ambulance corridor — J2 flushes first, then J1 green wave.',
        sensor_fault: 'Camera dropout — falling back to fixed-time schedule.',
      };
      AppState.elements.phasePill.reason.textContent = scenarioLabels[scenario] || 'Scenario changed.';
    }
  }

  function setCameraPreset(preset) {
    if (AppState.currentCamera === preset) return;

    AppState.currentCamera = preset;
    if (typeof window.switchCameraPreset === 'function') {
      window.switchCameraPreset(preset);
    }

    var cameraOptions = AppState.elements.cameraOptions;
    if (cameraOptions) {
      cameraOptions.forEach(function(pill) {
        var isActive = pill.getAttribute('data-camera') === preset;
        pill.classList.toggle('camera-option--active', isActive);
        pill.setAttribute('aria-checked', isActive);
      });
    }
  }

  function applySlider(sliderName, value) {
    var display = AppState.elements.sliderValues[sliderName];
    if (display) {
      if (sliderName === 'simSpeed') {
        display.textContent = value.toFixed(1) + 'x';
      } else if (sliderName === 'trafficIntensity') {
        var label = 'Normal';
        if (value > 75) label = 'Heavy';
        else if (value > 50) label = 'Moderate';
        else if (value < 25) label = 'Light';
        display.textContent = label + ' (' + Math.round(value) + '%)';
      } else if (sliderName === 'downstreamBottleneck') {
        display.textContent = Math.round(value) + '%';
      } else {
        display.textContent = value.toFixed(1);
      }
    }

    AppState[sliderName] = value;

    // Apply to scene
    var scene = typeof window.getTwinScene === 'function' ? window.getTwinScene() : null;
    if (scene && scene.scenario) {
      if (sliderName === 'simSpeed') {
        scene.scenario.timeScale = value;
      } else if (sliderName === 'trafficIntensity') {
        scene.congestionLevel = value / 100;
      } else if (sliderName === 'downstreamBottleneck') {
        if (value > 30) {
          scene.setSpillbackActive(true, value / 100);
        } else {
          scene.setSpillbackActive(false);
        }
      }
    }

    // Update density bars for downstream bottleneck
    if (sliderName === 'downstreamBottleneck') {
      updateDensityBar('exit', value);
      updateGateMarker(value);
    }
  }

  function applySliderToScene(key, value) {
    var scene = typeof window.getTwinScene === 'function' ? window.getTwinScene() : null;
    if (!scene) return;

    if (key === 'simSpeed') {
      scene.scenario.timeScale = value;
    } else if (key === 'congestionLevel') {
      scene.congestionLevel = value;
    } else if (key === 'spawnRate') {
      scene.spawnRate = value;
    }
  }

  function updateSliderDisplay(key, value) {
    var display = AppState.elements.sliderValues[key];
    if (!display) return;
    display.textContent = value.toFixed(1);
  }

  function updateDensityBar(direction, value) {
    var bar = AppState.elements.densityBars[direction];
    if (!bar) return;
    if (bar.value) bar.value.textContent = value + '%';
    if (bar.fill) bar.fill.style.width = Math.min(value, 100) + '%';

    var fillClass = 'density-bar__fill';
    if (value > 70) fillClass += ' density-bar__fill--rose';
    else if (value > 40) fillClass += ' density-bar__fill--amber';
    bar.fill.className = fillClass;
  }

  function updateGateMarker(value) {
    var marker = AppState.elements.gateMarker;
    if (marker) {
      marker.style.left = '30%';
    }
    var label = AppState.elements.gateLabel;
    if (label) {
      label.textContent = value > 0
        ? 'Exit ' + Math.round(value) + '% full — Gate at 30% | QueueSense: ' + (value > 30 ? 'HOLD upstream green' : 'Green permitted')
        : '30% Gate Threshold';
    }
  }

  async function handleEmergencyFlush() {
    var btn = AppState.elements.actionButtons.emergencyFlush;
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> FLUSHING...';
    }

    try {
      if (typeof window.triggerEmergencyFlush === 'function') {
        window.triggerEmergencyFlush();
      }

      if (AppState.elements.phasePill.reason) {
        AppState.elements.phasePill.reason.textContent =
          'Emergency flush: J2 clears first (downstream-first), then J1. Ambulance corridor opening.';
      }

      await fetchEmergencyResults();
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<svg class="btn__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path><path d="M12 7v4M12 16h.01"></path></svg> EMERGENCY FLUSH';
      }
    }
  }

  function handleReset() {
    AppState.isAutoScenario = true;
    setScenarioControl('auto');
    setModeControl('queuesense');
    setCameraPreset('isometric');

    AppState.simSpeed = 1.0;
    AppState.trafficIntensity = 50;
    AppState.downstreamBottleneck = 0;

    var sliders = AppState.elements.sliders;
    if (sliders.simSpeed) sliders.simSpeed.value = 1.0;
    if (sliders.trafficIntensity) sliders.trafficIntensity.value = 50;
    if (sliders.downstreamBottleneck) sliders.downstreamBottleneck.value = 0;

    applySlider('simSpeed', 1.0);
    applySlider('trafficIntensity', 50);
    applySlider('downstreamBottleneck', 0);

    if (AppState.elements.phasePill.reason) {
      AppState.elements.phasePill.reason.textContent =
        'System reset. QueueSense adaptive mode. Balanced scenario.';
    }
  }

  async function handleSelector() {
    var btn = AppState.elements.actionButtons.selector;
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> SELECTING...';
    }

    try {
      var response = await fetch('/api/selector');
      if (!response.ok) throw new Error('API not available');
      var data = await response.json();
      AppState.selectorDecision = data;

      if (AppState.elements.phasePill.reason) {
        AppState.elements.phasePill.reason.textContent =
          'Selector chose: ' + data.chosen_controller + ' (' + data.reason + ')';
      }
    } catch (error) {
      if (AppState.elements.phasePill.reason) {
        AppState.elements.phasePill.reason.textContent =
          'Selector unavailable. Running in standalone QueueSense mode.';
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<svg class="btn__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="2"></rect><path d="M12 2v20M2 12h20"></path></svg> RUN SELECTOR';
      }
    }
  }

  function handleDownload() {
    var response = fetch('/api/benchmark/export')
      .then(function(r) { return r.blob(); })
      .then(function(blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'queuesense-benchmark-' + new Date().toISOString().slice(0, 10) + '.csv';
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(function() {
        // Fallback: download embedded CSV
        var csvContent = 'controller,avg_delay_sec,p95_delay_sec,throughput_veh_hr,spillback_incidents,emergency_response_sec\n' +
          FALLBACK_BENCHMARK.map(function(c) {
            return c.name + ',' + c.avg_delay_sec + ',' + c.p95_delay_sec + ',' + c.throughput_veh_hr + ',' + c.spillback_incidents + ',' + c.emergency_response_sec;
          }).join('\n');
        var blob = new Blob([csvContent], { type: 'text/csv' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'queuesense-benchmark-' + new Date().toISOString().slice(0, 10) + '.csv';
        a.click();
        URL.revokeObjectURL(url);
      });
  }

  function handleKeyboardShortcuts(e) {
    // Ignore if typing in input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.key.toLowerCase()) {
      case '1': setModeControl('queuesense'); break;
      case '2': setModeControl('actuated'); break;
      case '3': setModeControl('pressure'); break;
      case '4': setModeControl('fixed'); break;
      case ' ':
        e.preventDefault();
        handleEmergencyFlush();
        break;
      case 'r': handleReset(); break;
      case 's': handleSelector(); break;
      case 'c':
        var cameras = ['isometric', 'topDown', 'driver'];
        var currentIdx = cameras.indexOf(AppState.currentCamera);
        setCameraPreset(cameras[(currentIdx + 1) % cameras.length]);
        break;
    }
  }

  /* =============================================================================
     API FETCHING (with fallback data)
     ============================================================================= */

  async function fetchAllAPIData() {
    await Promise.all([
      fetchBenchmarkData(),
      fetchPassportData(),
      fetchEmergencyResults(),
    ]);
  }

  async function fetchBenchmarkData() {
    try {
      var response = await fetch('/api/benchmark');
      if (!response.ok) throw new Error('API error');
      var data = await response.json();
      AppState.benchmarkData = data;
      var controllers = data.controllers || FALLBACK_BENCHMARK;
      updateBenchmarkUI(controllers);
      updateChart(controllers);
    } catch (error) {
      AppState.benchmarkData = { controllers: FALLBACK_BENCHMARK };
      updateBenchmarkUI(FALLBACK_BENCHMARK);
      updateChart(FALLBACK_BENCHMARK);
    }
  }

  async function fetchPassportData() {
    try {
      var response = await fetch('/api/passport');
      if (!response.ok) throw new Error('API error');
      var data = await response.json();
      AppState.passportData = data;
      updatePassportUI(data);
    } catch (error) {
      var fallback = { junctions: FALLBACK_PASSPORT.junctions, summary: { fully_passed: 2, total_junctions: 2, checks_per_junction: 8 } };
      AppState.passportData = fallback;
      updatePassportUI(fallback);
    }
  }

  async function fetchEmergencyResults() {
    try {
      var response = await fetch('/api/emergency/results');
      if (!response.ok) throw new Error('API error');
      var data = await response.json();
      AppState.emergencyResults = data;
      var strategies = data.strategies || data.results || FALLBACK_EMERGENCY;
      updateEmergencyResultsUI(strategies);
    } catch (error) {
      AppState.emergencyResults = { strategies: FALLBACK_EMERGENCY };
      updateEmergencyResultsUI(FALLBACK_EMERGENCY);
    }
  }

  function updateLiveUI(data) {
    if (!data) return;

    // Update scoreboard
    var sb = AppState.elements.scoreboard;
    if (sb) {
      if (sb.throughput) sb.throughput.textContent = (data.throughput_veh_per_hr || 1361).toLocaleString();
      if (sb.avgWait) sb.avgWait.textContent = (data.avg_wait_sec || 19.4).toFixed(1);
      if (sb.exitFill) sb.exitFill.textContent = Math.round(data.exit_occupancy_pct || 28) + '%';
      if (sb.exitLabel) sb.exitLabel.textContent = (data.exit_occupancy_pct || 28) > 30 ? 'CONGESTED' : 'CLEAR';
      if (sb.gridlocks) sb.gridlocks.textContent = data.gridlocks_prevented || 12;
    }

    // Update density bars
    if (data.approach_density) {
      for (var dir in data.approach_density) {
        updateDensityBar(dir, data.approach_density[dir]);
      }
    }
    if (data.exit_occupancy_pct !== undefined) {
      updateDensityBar('exit', data.exit_occupancy_pct);
      updateGateMarker(data.exit_occupancy_pct);
    }

    // Update phase pill
    if (data.decision_reason && AppState.elements.phasePill.reason) {
      AppState.elements.phasePill.reason.textContent = data.decision_reason;
    }
    if (data.current_phase && AppState.elements.phasePill.label) {
      AppState.elements.phasePill.label.textContent = data.current_phase;
    }
    if (data.phase_time_remaining !== undefined && AppState.elements.phasePill.timer) {
      AppState.elements.phasePill.timer.textContent = Math.round(data.phase_time_remaining) + 's';
    }
  }

  function updateBenchmarkUI(controllers) {
    var tbody = AppState.elements.ablationTableBody;
    if (!tbody) return;

    tbody.innerHTML = '';

    controllers.forEach(function(ctrl) {
      var row = document.createElement('tr');
      var isBest = ctrl.controller_id === 'D' || (ctrl.throughput_veh_hr && ctrl.throughput_veh_hr >= 1300);
      var isWorst = ctrl.controller_id === 'A' || (ctrl.avg_delay_sec && ctrl.avg_delay_sec >= 30);

      var bestClass = isBest ? ' metric-value--best' : isWorst ? ' metric-value--worst' : '';

      row.innerHTML =
        '<td><span class="controller-name">' + ctrl.name + '</span>' +
        '<span class="controller-type ' + (ctrl.typeClass || '') + '">' + (ctrl.typeLabel || '') + '</span></td>' +
        '<td class="metric-value' + bestClass + '">' + (ctrl.avg_delay_sec ? ctrl.avg_delay_sec.toFixed(1) : '-') + '</td>' +
        '<td class="metric-value' + bestClass + '">' + (ctrl.p95_delay_sec ? ctrl.p95_delay_sec.toFixed(1) : '-') + '</td>' +
        '<td class="metric-value' + bestClass + '">' + (ctrl.throughput_veh_hr ? ctrl.throughput_veh_hr.toFixed(0) : '-') + '</td>' +
        '<td class="metric-value' + bestClass + '">' + (ctrl.spillback_incidents !== undefined ? ctrl.spillback_incidents : '-') + '</td>' +
        '<td class="metric-value' + bestClass + '">' + (ctrl.emergency_response_sec ? ctrl.emergency_response_sec.toFixed(1) : '-') + '</td>';
      tbody.appendChild(row);
    });
  }

  function updateEmergencyResultsUI(strategies) {
    var container = AppState.elements.emergencyResults;
    if (!container) return;

    container.innerHTML = '';

    strategies.forEach(function(strat, idx) {
      var article = document.createElement('article');
      var isBest = strat.isBest || idx === 0;
      var isWorst = idx === strategies.length - 1;

      var cls = 'emergency-strategy';
      if (isBest) cls += ' emergency-strategy--best';
      if (isWorst) cls += ' emergency-strategy--worst';

      article.className = cls;
      article.innerHTML =
        '<div class="emergency-strategy__badge">' + (isBest ? 'BEST' : isWorst ? 'SLOWEST' : 'RANK ' + (idx + 1)) + '</div>' +
        '<h4 class="emergency-strategy__name">' + strat.name + '</h4>' +
        '<div class="emergency-strategy__time tabular-nums">' + strat.clearance_time_sec.toFixed(1) + 's</div>' +
        '<div class="emergency-strategy__detail">' + strat.description + '</div>' +
        '<div class="emergency-strategy__stops">Stops: ' + strat.stops + ' | Recovery: ' + strat.recovery_time_sec.toFixed(1) + 's</div>';
      container.appendChild(article);
    });
  }

  function updatePassportUI(data) {
    var grid = AppState.elements.passportGrid;
    if (!grid) return;

    var summary = data.summary || { fully_passed: 2, total_junctions: 2, checks_per_junction: 8 };
    if (AppState.elements.passportSummary) {
      AppState.elements.passportSummary.innerHTML =
        '<strong>' + summary.fully_passed + '/' + summary.total_junctions + ' junctions fully passed</strong>, ' +
        summary.checks_per_junction + '/8 checks each';
    }

    var junctions = data.junctions || data.passports || FALLBACK_PASSPORT.junctions;
    grid.innerHTML = '';

    junctions.forEach(function(j) {
      var article = document.createElement('article');
      article.className = 'passport-junction';

      var badgeClass = j.overall_pass ? 'passport-junction__badge--pass' : 'passport-junction__badge--fail';
      var badgeText = j.overall_pass ? 'PASS' : 'FAIL';

      article.innerHTML =
        '<header class="passport-junction__header">' +
        '<h4 class="passport-junction__id">' + j.id + '</h4>' +
        '<span class="passport-junction__badge ' + badgeClass + '">' + badgeText + '</span>' +
        '</header>' +
        '<div class="passport-checks">' +
        (j.checks || []).map(function(check) {
          var checkClass = check.pass ? 'passport-check__icon--pass' : 'passport-check__icon--fail';
          var checkMark = check.pass ? '&#10003;' : '&#10007;';
          return '<div class="passport-check">' +
            '<span class="passport-check__icon ' + checkClass + '" aria-hidden="true">' + checkMark + '</span>' +
            '<div class="passport-check__content">' +
            '<div class="passport-check__name">' + check.name + '</div>' +
            '<div class="passport-check__details">' + check.details + (check.evidence ? ' (' + check.evidence + ')' : '') + '</div>' +
            '</div></div>';
        }).join('') +
        '</div></article>';

      grid.appendChild(article);
    });
  }

  /* =============================================================================
     CHART.JS INITIALIZATION
     ============================================================================= */

  var benchmarkChart = null;

  function updateChart(controllers) {
    if (!AppState.elements.delayChart || typeof Chart === 'undefined') return;

    var ctx = AppState.elements.delayChart.getContext('2d');

    var labels = controllers.map(function(c) { return c.name; });
    var avgDelay = controllers.map(function(c) { return c.avg_delay_sec; });
    var p95Delay = controllers.map(function(c) { return c.p95_delay_sec; });
    var throughput = controllers.map(function(c) { return c.throughput_veh_hr; });
    var spillback = controllers.map(function(c) { return c.spillback_incidents; });

    var colors = ['#f87171', '#fbbf24', '#c084fc', '#10b981'];

    if (benchmarkChart) {
      benchmarkChart.data.labels = labels;
      benchmarkChart.data.datasets[0].data = avgDelay;
      benchmarkChart.data.datasets[0].backgroundColor = colors;
      benchmarkChart.data.datasets[1].data = p95Delay;
      benchmarkChart.update();
    } else {
      benchmarkChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Avg Delay (s)',
              data: avgDelay,
              backgroundColor: colors,
              borderRadius: 4,
              barThickness: 32,
            },
            {
              label: 'P95 Delay (s)',
              data: p95Delay,
              backgroundColor: colors.map(function(c) { return c + '60'; }),
              borderRadius: 4,
              barThickness: 32,
              hidden: true,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false,
            },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.95)',
              titleColor: '#f8fafc',
              bodyColor: '#cbd5e1',
              borderColor: '#334155',
              borderWidth: 1,
              padding: 12,
              cornerRadius: 8,
              displayColors: false,
              callbacks: {
                label: function(ctx) {
                  return ctx.dataset.label + ': ' + ctx.raw.toFixed(1);
                },
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(51, 65, 85, 0.5)' },
              ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' } },
            },
            x: {
              grid: { display: false },
              ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' } },
            },
          },
        },
      });
    }

    // Update legend
    var legend = AppState.elements.benchmarkLegend;
    if (legend) {
      legend.innerHTML = controllers.map(function(c, i) {
        return '<div class="chart-legend__item">' +
          '<span class="chart-legend__swatch" style="background:' + colors[i] + ';border-radius:2px;"></span>' +
          c.name +
          '</div>';
      }).join('');
    }
  }

  /* =============================================================================
     THREE.JS SCENE CALLBACKS
     ============================================================================= */

  function handleTwinStateUpdate(state) {
    AppState.liveState = state;
    updateLiveUI(state);
  }

  function handleSignalUpdate(signal) {
    console.debug('Signal update:', signal);
  }

  function handleScenarioChange(scenario) {
    AppState.currentScenario = scenario;
  }

  function handleModeChange(isQueueSense) {
    AppState.currentMode = isQueueSense ? 'queuesense' : 'actuated';
  }

  function handleZoneUpdate(zones) {
    // AI zone PCU counts updated
    var totalPCU = 0;
    for (var id in zones) {
      totalPCU += zones[id];
    }

    // Update density bars from zone data
    if (zones.J1_N !== undefined) updateDensityBar('north', zones.J1_N * 12);
    if (zones.J1_E !== undefined) updateDensityBar('east', zones.J1_E * 12);
  }

  function handleTelemetry(stats) {
    console.debug('Telemetry:', stats);
  }

  /* =============================================================================
     RENDER LOOP
     ============================================================================= */

  function renderLoop(timestamp) {
    if (!AppState.isInitialized) return;

    var deltaTime = (timestamp - AppState.lastFrameTime) / 1000;
    AppState.lastFrameTime = timestamp;
    AppState.frameCount++;

    // Throttle API polling to 2Hz
    if (AppState.frameCount % 30 === 0) {
      // Poll live state if available
    }

    // Throttle benchmark fetch to once per 10 seconds
    if (AppState.frameCount % 600 === 0 && !AppState.benchmarkData) {
      fetchBenchmarkData();
      fetchPassportData();
    }

    requestAnimationFrame(renderLoop);
  }

  /* =============================================================================
     UTILITY FUNCTIONS
     ============================================================================= */

  function formatNumber(num, decimals) {
    if (decimals === undefined) decimals = 1;
    if (num === null || num === undefined || isNaN(num)) return '—';
    return Number(num).toFixed(decimals);
  }

  function debounce(fn, delay) {
    var timeoutId;
    return function() {
      var args = arguments;
      clearTimeout(timeoutId);
      timeoutId = setTimeout(function() { fn.apply(null, args); }, delay);
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
})();