// QueueSense Dashboard — Application Controller
// Fixes Chart.js undefined bug by normalizing data field names

(function () {
  'use strict';

  // DOM cache
  const $ = document.getElementById.bind(document);
  const $$ = document.querySelector.bind(document);
  const $$$ = document.querySelectorAll.bind(document);

  // --- State ---
  const appState = {
    scenario: 'auto',
    mode: 'queuesense',
    camera: 'isometric',
    autoCycle: true,
    density: 50,
    downstream: 0,
    apiAvailable: false,
    benchmarkData: null,
    ws: null,
    reconnectTimer: null,
  };

  // --- Fallback benchmark data (matches API response structure) ---
  const FALLBACK_BENCHMARK = {
    controllers: [
      {
        controller_id: 'A',
        controller_name: 'Fixed-Time',
        delay_mean: 72.3,
        delay_std: 12.4,
        delay_p95: 98.1,
        throughput_mean: 1247,
        throughput_std: 89,
        queue_mean: 18.4,
        queue_p95: 25.6,
        spillback_mean: 0.15,
      },
      {
        controller_id: 'B',
        controller_name: 'Actuated',
        delay_mean: 58.7,
        delay_std: 9.8,
        throughput_mean: 1361,
        throughput_std: 72,
        queue_mean: 15.2,
        queue_p95: 22.1,
        spillback_mean: 0.08,
      },
      {
        controller_id: 'C',
        controller_name: 'Queue-Pressure',
        delay_mean: 46.2,
        delay_std: 8.3,
        throughput_mean: 1423,
        throughput_std: 65,
        queue_mean: 12.1,
        queue_p95: 18.7,
        spillback_mean: 0.12,
      },
      {
        controller_id: 'D',
        controller_name: 'QueueSense AI',
        delay_mean: 38.5,
        delay_std: 6.7,
        throughput_mean: 1493,
        throughput_std: 58,
        queue_mean: 8.5,
        queue_p95: 14.2,
        spillback_mean: 0.02,
      },
    ],
  };

  // --- Normalized benchmark: ensure all controllers have both name fields ---
  function normalizeBenchmark(raw) {
    const data = (raw && raw.controllers) ? raw : FALLBACK_BENCHMARK;
    return data.controllers.map(function(c) {
      return {
        id: c.controller_id || c.id,
        name: c.controller_name || c.name || 'Unknown',
        delay_mean: c.delay_mean,
        delay_std: c.delay_std || 0,
        delay_p95: c.delay_p95 || c.delay_mean * 1.3,
        throughput_mean: c.throughput_mean,
        throughput_std: c.throughput_std || 0,
        queue_mean: c.queue_mean || c.queue_pcU || 0,
        queue_p95: c.queue_p95 || c.queue_mean * 1.4,
        spillback_mean: c.spillback_mean || 0,
      };
    });
  }

  // --- Chart.js instances ---
  let delayChart = null;
  let throughputChart = null;

  function getControllerColor(name) {
    const colors = {
      'Fixed-Time': '#9a9ab0',
      'Actuated': '#00e5ff',
      'Queue-Pressure': '#4a90ff',
      'QueueSense AI': '#00ff88',
    };
    return colors[name] || '#9a9ab0';
  }

  function getControllerBg(name) {
    const colors = {
      'Fixed-Time': 'rgba(154, 154, 176, 0.3)',
      'Actuated': 'rgba(0, 229, 255, 0.3)',
      'Queue-Pressure': 'rgba(74, 144, 255, 0.3)',
      'QueueSense AI': 'rgba(0, 255, 136, 0.3)',
    };
    return colors[name] || 'rgba(154, 154, 176, 0.3)';
  }

  function initCharts() {
    const normalized = normalizeBenchmark(appState.benchmarkData);
    const labels = normalized.map(function(c) {
      return c.name;
    });

    // Delay chart (lower is better)
    const delayCtx = document.getElementById('chartDelay').getContext('2d');
    delayChart = new Chart(delayCtx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Avg Delay (s)',
          data: normalized.map(function(c) { return c.delay_mean; }),
          backgroundColor: normalized.map(function(c) { return getControllerBg(c.name); }),
          borderColor: normalized.map(function(c) { return getControllerColor(c.name); }),
          borderWidth: 1,
          borderRadius: 4,
          barThickness: 40,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: '#9a9ab0',
              font: { size: 11 },
            },
          },
        },
        scales: {
          y: {
            grid: { color: '#2a2a34' },
            ticks: { color: '#6a6b80', font: { size: 10 } },
          },
          x: {
            grid: { display: false },
            ticks: { color: '#9a9ab0', font: { size: 11 } },
          },
        },
      },
    });

    // Throughput chart (higher is better)
    const throughputCtx = document.getElementById('chartThroughput').getContext('2d');
    throughputChart = new Chart(throughputCtx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Throughput (veh/hr)',
          data: normalized.map(function(c) { return c.throughput_mean; }),
          backgroundColor: normalized.map(function(c) { return getControllerBg(c.name); }),
          borderColor: normalized.map(function(c) { return getControllerColor(c.name); }),
          borderWidth: 1,
          borderRadius: 4,
          barThickness: 40,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: '#9a9ab0',
              font: { size: 11 },
            },
          },
        },
        scales: {
          y: {
            grid: { color: '#2a2a34' },
            ticks: { color: '#6a6b80', font: { size: 10 } },
          },
          x: {
            grid: { display: false },
            ticks: { color: '#9a9ab0', font: { size: 11 } },
          },
        },
      },
    });
  }

  function updateCharts() {
    const normalized = normalizeBenchmark(appState.benchmarkData);
    const labels = normalized.map(function(c) { return c.name; });

    if (delayChart) {
      delayChart.data.labels = labels;
      delayChart.data.datasets[0].data = normalized.map(function(c) { return c.delay_mean; });
      delayChart.data.datasets[0].backgroundColor = normalized.map(function(c) { return getControllerBg(c.name); });
      delayChart.update();
    }

    if (throughputChart) {
      throughputChart.data.labels = labels;
      throughputChart.data.datasets[0].data = normalized.map(function(c) { return c.throughput_mean; });
      throughputChart.data.datasets[0].backgroundColor = normalized.map(function(c) { return getControllerBg(c.name); });
      throughputChart.update();
    }

    // Update metric cards
    const bestQueue = Math.min.apply(null, normalized.map(function(c) { return c.queue_mean; }));
    const bestSpillback = Math.min.apply(null, normalized.map(function(c) { return c.spillback_mean; }));
    const bestThroughput = Math.max.apply(null, normalized.map(function(c) { return c.throughput_mean; }));

    const bestQueueEl = $('metricBestQueue');
    const bestSpillEl = $('metricBestSpillback');
    const bestThruputEl = $('metricBestThroughput');

    if (bestQueueEl) bestQueueEl.textContent = bestQueue.toFixed(1);
    if (bestSpillEl) bestSpillEl.textContent = bestSpillback.toFixed(2);
    if (bestThruputEl) bestThruputEl.textContent = Math.round(bestThroughput).toLocaleString();
  }

  // --- WebSocket connection ---
  function connectWS() {
    if (appState.ws) {
      appState.ws.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = protocol + '//' + window.location.host + '/ws/live';

    try {
      appState.ws = new WebSocket(wsUrl);
    } catch (e) {
      console.warn('WebSocket connection failed, using fallback data');
      appState.apiAvailable = false;
      return;
    }

    appState.ws.onopen = function() {
      appState.apiAvailable = true;
    };

    appState.ws.onmessage = function(event) {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'telemetry' && data.state) {
          updateFromTelemetry(data.state);
        } else if (data.type === 'benchmark' && data.benchmark) {
          appState.benchmarkData = data.benchmark;
          updateCharts();
        }
      } catch (e) {
        // Silently handle non-JSON messages
      }
    };

    appState.ws.onerror = function() {
      appState.apiAvailable = false;
    };

    appState.ws.onclose = function() {
      appState.apiAvailable = false;
      // Reconnect after 3 seconds
      if (appState.reconnectTimer) clearTimeout(appState.reconnectTimer);
      appState.reconnectTimer = setTimeout(connectWS, 3000);
    };
  }

  // --- REST API fallback ---
  function fetchState() {
    fetch('/api/state')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        appState.apiAvailable = true;
        updateFromTelemetry(data);
      })
      .catch(function() {
        appState.apiAvailable = false;
      });
  }

  function fetchBenchmark() {
    fetch('/api/benchmark')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        appState.benchmarkData = data;
        updateCharts();
      })
      .catch(function() {
        appState.benchmarkData = null;
        updateCharts();
      });
  }

  // --- Update from backend state ---
  function updateFromTelemetry(state) {
    // Update AI reason text
    const reasonText = state.simplified && state.simplified.decision_headline
      ? state.simplified.decision_headline
      : 'West Road is packed (18 vehicles) — AI added +10s of Green time.';

    const reasonEl = $('reasonText');
    if (reasonEl) reasonEl.textContent = reasonText;

    // Update metric cards with live data if available
    if (state.simplified) {
      const s = state.simplified;
      const qEl = $('metricBestQueue');
      const tEl = $('metricBestThroughput');
      const eEl = $('metricEmergency');

      if (s.queue_pcu && qEl) qEl.textContent = s.queue_pcu.toFixed(1);
      if (s.throughput && tEl) tEl.textContent = Math.round(s.throughput).toLocaleString();
    }

    // Notify the 3D scene
    if (window.QueueSense3D && window.QueueSense3D.updateReason) {
      const headline = state.simplified ? state.simplified.decision_headline : reasonText;
      window.QueueSense3D.updateReason(headline);
    }

    // Update downstream blockage visualization
    if (state.downstream) {
      let maxExit = 0;
      for (const dir in state.downstream) {
        const occ = state.downstream[dir].exit_occupancy || 0;
        maxExit = Math.max(maxExit, occ);
      }
      const blockagePct = Math.round(maxExit * 100);
      if (window.QueueSense3D) {
        window.QueueSense3D.setDownstreamBlockage(blockagePct);
      }
      const valExit = $('valExit');
      if (valExit) valExit.textContent = blockagePct + '%';
    }

    // Update scenario based on exit occupancy
    if (state.downstream && state.downstream.east && state.downstream.east.exit_occupancy > 0.8 && appState.scenario === 'auto') {
      appState.scenario = 'spillback';
      if (window.QueueSense3D) window.QueueSense3D.setScenario('spillback');
      updateScenarioUI();
    }
  }

  // --- UI Update Functions ---
  function updateScenarioUI() {
    const btns = $$$('.scenario-btn');
    btns.forEach(function(btn) {
      btn.classList.remove('scenario-btn--active');
      if (btn.dataset.scenario === appState.scenario) {
        btn.classList.add('scenario-btn--active');
      }
    });
  }

  function updateModeUI() {
    const modeBtns = $$$('.pill-btn');
    modeBtns.forEach(function(btn) {
      btn.classList.remove('pill-btn--active');
      if (btn.dataset.mode === appState.mode) {
        btn.classList.add('pill-btn--active');
      }
    });
  }

  function updateCameraUI() {
    const camBtns = $$$('.cam-btn');
    camBtns.forEach(function(btn) {
      btn.classList.remove('cam-btn--active');
      if (btn.dataset.cam === appState.camera) {
        btn.classList.add('cam-btn--active');
      }
    });
  }

  // --- Scenario Director ---
  function startAutoCycle() {
    if (!appState.autoCycle) return;

    const scenarios = ['auto', 'surge', 'spillback', 'emergency'];
    let idx = 0;

    setInterval(function() {
      if (!appState.autoCycle) return;
      appState.scenario = scenarios[idx];
      if (window.QueueSense3D) window.QueueSense3D.setScenario(appState.scenario);
      updateScenarioUI();
      idx = (idx + 1) % scenarios.length;
    }, 8000);
  }

  // --- Event Listeners ---
  function setupEventListeners() {
    // Mode toggle
    const modeQS = $('modeQS');
    const modeTrad = $('modeTrad');
    if (modeQS) modeQS.addEventListener('click', function() {
      appState.mode = 'queuesense';
      updateModeUI();
      if (window.QueueSense3D) window.QueueSense3D.setMode('queuesense');
    });
    if (modeTrad) modeTrad.addEventListener('click', function() {
      appState.mode = 'traditional';
      updateModeUI();
      if (window.QueueSense3D) window.QueueSense3D.setMode('traditional');
    });

    // Camera toggle
    const camIso = $('camIso');
    const camTop = $('camTop');
    const camFollow = $('camFollow');
    if (camIso) camIso.addEventListener('click', function() {
      appState.camera = 'isometric';
      updateCameraUI();
      if (window.QueueSense3D) window.QueueSense3D.setCamera('isometric');
    });
    if (camTop) camTop.addEventListener('click', function() {
      appState.camera = 'top';
      updateCameraUI();
      if (window.QueueSense3D) window.QueueSense3D.setCamera('top');
    });
    if (camFollow) camFollow.addEventListener('click', function() {
      appState.camera = 'follow';
      updateCameraUI();
      if (window.QueueSense3D) window.QueueSense3D.setCamera('follow');
    });

    // Scenario buttons
    const scenarioBtns = $$$('.scenario-btn');
    scenarioBtns.forEach(function(btn) {
      btn.addEventListener('click', function() {
        appState.scenario = btn.dataset.scenario;
        appState.autoCycle = false;
        if (window.QueueSense3D) window.QueueSense3D.setScenario(appState.scenario);
        updateScenarioUI();

        // Update AI reason based on scenario
        const reasons = {
          'auto': 'Balanced traffic — AI monitors all approaches dynamically.',
          'surge': 'West approach surge detected — AI extending green phase.',
          'spillback': 'Downstream queue detected — AI protecting intersection.',
          'emergency': 'Emergency vehicle approaching — AI clearing corridor.',
        };
        const reasonEl = $('reasonText');
        if (reasonEl) reasonEl.textContent = reasons[appState.scenario];
        if (window.QueueSense3D && window.QueueSense3D.updateReason) {
          window.QueueSense3D.updateReason(reasons[appState.scenario]);
        }
      });
    });

    // Auto toggle
    const autoToggle = $('autoToggle');
    if (autoToggle) {
      autoToggle.addEventListener('click', function() {
        appState.autoCycle = !appState.autoCycle;
        autoToggle.classList.toggle('active');
        if (appState.autoCycle) {
          startAutoCycle();
        }
      });
    }

    // Density slider
    const densitySlider = $('sliderDensity');
    if (densitySlider) {
      densitySlider.addEventListener('input', function(e) {
        appState.density = parseInt(e.target.value);
        const valEl = $('valDensity');
        let label = 'Normal';
        if (appState.density > 75) label = 'Heavy';
        else if (appState.density > 50) label = 'Busy';
        else if (appState.density > 25) label = 'Light';
        else label = 'Light';
        if (valEl) valEl.textContent = label;
        if (window.QueueSense3D) window.QueueSense3D.setDensity(appState.density);
      });
    }

    // Exit congestion slider
    const exitSlider = $('sliderExit');
    if (exitSlider) {
      exitSlider.addEventListener('input', function(e) {
        appState.downstream = parseInt(e.target.value);
        const valEl = $('valExit');
        if (valEl) valEl.textContent = appState.downstream + '%';
        if (window.QueueSense3D) window.QueueSense3D.setDownstreamBlockage(appState.downstream);
      });
    }

    // Emergency button
    const btnAmbulance = $('btnAmbulance');
    if (btnAmbulance) {
      btnAmbulance.addEventListener('click', function() {
        appState.scenario = 'emergency';
        appState.autoCycle = false;
        if (window.QueueSense3D) {
          window.QueueSense3D.setScenario('emergency');
          window.QueueSense3D.updateReason('Emergency corridor activated — all non-critical phases suspended.');
        }
        updateScenarioUI();
        const reasonEl = $('reasonText');
        if (reasonEl) reasonEl.textContent = 'Emergency corridor activated — all non-critical phases suspended.';

        // Call API to inject emergency vehicle
        fetch('/api/emergency-flush/activate', { method: 'POST' }).catch(function() {});
      });
    }

    // Reset button
    const btnReset = $('btnReset');
    if (btnReset) {
      btnReset.addEventListener('click', function() {
        appState.scenario = 'auto';
        appState.mode = 'queuesense';
        appState.density = 50;
        appState.downstream = 0;
        appState.autoCycle = false;
        if (window.QueueSense3D) {
          window.QueueSense3D.setScenario('auto');
          window.QueueSense3D.setMode('queuesense');
          window.QueueSense3D.setDensity(50);
          window.QueueSense3D.setDownstreamBlockage(0);
          window.QueueSense3D.updateReason('West Road is packed (18 vehicles) — AI added +10s of Green time.');
        }
        updateScenarioUI();
        updateModeUI();
        const dEl = $('valDensity');
        if (dEl) dEl.textContent = 'Normal';
        const eEl = $('valExit');
        if (eEl) eEl.textContent = '0%';
        const autoToggle = $('autoToggle');
        if (autoToggle) autoToggle.classList.remove('active');
        const reasonEl = $('reasonText');
        if (reasonEl) reasonEl.textContent = 'West Road is packed (18 vehicles) — AI added +10s of Green time.';
      });
    }
  }

  // --- Initialization ---
  function init() {
    initCharts();
    setupEventListeners();

    // Try WebSocket first, fall back to polling
    connectWS();

    // Fallback polling every 5 seconds
    setInterval(function() {
      if (!appState.apiAvailable) {
        fetchState();
      }
    }, 5000);

    // Fetch benchmark data
    fetchBenchmark();

    // Start auto-cycle
    if (appState.autoCycle) {
      startAutoCycle();
    }

    // Initial 3D setup
    if (window.QueueSense3D) {
      window.QueueSense3D.setCamera('isometric');
    }

    console.log('QueueSense Dashboard initialized');
  }

  // Delay chart canvas height fix
  function fixChartHeights() {
    const canvases = $$$('canvas');
    canvases.forEach(function(c) {
      const wrapper = document.createElement('div');
      wrapper.className = 'canvas-wrapper';
      c.parentNode.insertBefore(wrapper, c);
      wrapper.appendChild(c);
    });
  }

  // Ensure DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      fixChartHeights();
      init();
    });
  } else {
    fixChartHeights();
    init();
  }

  // Export for debugging
  window.QueueSenseApp = {
    state: appState,
    init: init,
    initCharts: initCharts,
    updateCharts: updateCharts,
  };

})();
