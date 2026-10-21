// QueueSense Dashboard — Application Controller
// Complete interaction logic with emil-kowalski micro-interactions

(function () {
  'use strict';

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
    autoCycleTimer: null,
    scenarioCycleIndex: 0,
  };

  // --- Fallback Benchmark Data (matches Stage 3/5 reconciled data) ---
  const FALLBACK_BENCHMARK = {
    controllers: [
      {
        controller_id: 'A',
        controller_name: 'Controller A (Fixed-Time)',
        throughput_mean: 952.4,
        throughput_std: 5.4,
        delay_mean: 105.3,
        delay_std: 12.4,
        delay_p95: 128.1,
        queue_mean: 27.7,
        queue_p95: 38.2,
        spillback_mean: 12,
      },
      {
        controller_id: 'B',
        controller_name: 'Controller B (Actuated)',
        throughput_mean: 962.1,
        throughput_std: 5.1,
        delay_mean: 98.7,
        delay_std: 9.8,
        delay_p95: 118.0,
        queue_mean: 33.2,
        queue_p95: 42.1,
        spillback_mean: 15,
      },
      {
        controller_id: 'C',
        controller_name: 'Controller C (Queue-Pressure)',
        throughput_mean: 1257.1,
        throughput_std: 2.9,
        delay_mean: 50.6,
        delay_std: 8.3,
        delay_p95: 63.5,
        queue_mean: 36.1,
        queue_p95: 48.7,
        spillback_mean: 48,
      },
      {
        controller_id: 'D',
        controller_name: 'Controller D (QueueSense)',
        throughput_mean: 1361.5,
        throughput_std: 2.9,
        delay_mean: 38.5,
        delay_std: 6.7,
        delay_p95: 52.3,
        queue_mean: 1.8,
        queue_p95: 4.2,
        spillback_mean: 0,
      },
    ],
  };

  // --- Normalized Benchmark ---
  function normalizeBenchmark(raw) {
    const data = (raw && raw.controllers && Array.isArray(raw.controllers)) ? raw : FALLBACK_BENCHMARK;
    const controllers = data.controllers || FALLBACK_BENCHMARK.controllers;

    return controllers.map(function(c) {
      const name = c.controller_name || c.name || 'Unknown';
      const id = c.controller_id || c.id || name;
      const throughputMean = (typeof c.throughput_mean === 'number') ? c.throughput_mean : 0;
      const delayMean = (typeof c.delay_mean === 'number') ? c.delay_mean : Math.round(100 * (1 - throughputMean / 1800) + 30);
      const queueMean = (typeof c.queue_mean === 'number') ? c.queue_mean : (c.queue_pcu || 0);

      return {
        id: id,
        name: name,
        delay_mean: delayMean,
        delay_std: (typeof c.delay_std === 'number') ? c.delay_std : (delayMean * 0.15),
        delay_p95: (typeof c.delay_p95 === 'number') ? c.delay_p95 : Math.round(delayMean * 1.3),
        throughput_mean: throughputMean,
        throughput_std: (typeof c.throughput_std === 'number') ? c.throughput_std : (throughputMean * 0.05),
        queue_mean: queueMean,
        queue_p95: (typeof c.queue_p95 === 'number') ? c.queue_p95 : Math.round(queueMean * 1.4),
        spillback_mean: (typeof c.spillback_mean === 'number') ? c.spillback_mean : 0,
      };
    });
  }

  // --- Chart.js Instances ---
  let delayChart = null;
  let throughputChart = null;

  // --- Color Palette (neutral, no neon) ---
  function getControllerColor(name) {
    const colors = {
      'Controller A (Fixed-Time)':       '#9ca3af',
      'Controller B (Actuated)':         '#60a5fa',
      'Controller C (Queue-Pressure)':   '#f59e0b',
      'Controller D (QueueSense)':       '#22c55e',
    };
    return colors[name] || '#9ca3af';
  }

  function getControllerBg(name) {
    const color = getControllerColor(name);
    const r = parseInt(color.slice(1, 3), 16);
    const g = parseInt(color.slice(3, 5), 16);
    const b = parseInt(color.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, 0.25)`;
  }

  // --- Chart.js Options ---
  function getChartOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a1e23',
          titleColor: '#e8e8ec',
          bodyColor: '#b8b8c8',
          borderColor: '#3a3a46',
          borderWidth: 1,
          cornerRadius: 6,
          displayColors: false,
        },
      },
      scales: {
        y: {
          grid: { color: '#2a2a34', drawBorder: false },
          ticks: { color: '#6a6b80', font: { size: 10 }, padding: 4 },
          beginAtZero: true,
        },
        x: {
          grid: { display: false },
          ticks: { color: '#9a9ab0', font: { size: 11 }, padding: 4 },
        },
      },
      animation: {
        duration: 600,
        easing: 'easeOutQuart',
      },
    };
  }

  function initCharts() {
    const normalized = normalizeBenchmark(appState.benchmarkData);
    const labels = normalized.map(function(c) { return c.name; });

    const colors = normalized.map(function(c) { return getControllerColor(c.name); });
    const bgColors = normalized.map(function(c) { return getControllerBg(c.name); });

    // Delay Chart
    const delayCtx = document.getElementById('chartDelay');
    if (delayCtx) {
      const ctx = delayCtx.getContext('2d');
      delayChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Avg Delay (s)',
            data: normalized.map(function(c) { return Math.round(c.delay_mean); }),
            backgroundColor: bgColors,
            borderColor: colors,
            borderWidth: 1,
            borderRadius: 4,
            barThickness: 40,
          }],
        },
        options: getChartOptions(),
      });
    }

    // Throughput Chart
    const throughputCtx = document.getElementById('chartThroughput');
    if (throughputCtx) {
      const ctx2 = throughputCtx.getContext('2d');
      throughputChart = new Chart(ctx2, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Throughput (veh/hr)',
            data: normalized.map(function(c) { return Math.round(c.throughput_mean); }),
            backgroundColor: bgColors,
            borderColor: colors,
            borderWidth: 1,
            borderRadius: 4,
            barThickness: 40,
          }],
        },
        options: getChartOptions(),
      });
    }
  }

  function updateCharts() {
    const normalized = normalizeBenchmark(appState.benchmarkData);
    const labels = normalized.map(function(c) { return c.name; });
    const colors = normalized.map(function(c) { return getControllerColor(c.name); });
    const bgColors = normalized.map(function(c) { return getControllerBg(c.name); });

    if (delayChart) {
      delayChart.data.labels = labels;
      delayChart.data.datasets[0].data = normalized.map(function(c) { return Math.round(c.delay_mean); });
      delayChart.data.datasets[0].backgroundColor = bgColors;
      delayChart.data.datasets[0].borderColor = colors;
      delayChart.update();
    }

    if (throughputChart) {
      throughputChart.data.labels = labels;
      throughputChart.data.datasets[0].data = normalized.map(function(c) { return Math.round(c.throughput_mean); });
      throughputChart.data.datasets[0].backgroundColor = bgColors;
      throughputChart.data.datasets[0].borderColor = colors;
      throughputChart.update();
    }

    // Update metric cards
    const bestQueue = Math.min.apply(null, normalized.map(function(c) { return c.queue_mean; }));
    const bestSpillback = Math.min.apply(null, normalized.map(function(c) { return c.spillback_mean; }));
    const bestThroughput = Math.max.apply(null, normalized.map(function(c) { return c.throughput_mean; }));
    const bestDelay = Math.min.apply(null, normalized.map(function(c) { return c.delay_mean; }));

    const bestQueueEl = document.getElementById('metricBestQueue');
    const bestSpillEl = document.getElementById('metricBestSpillback');
    const bestThruputEl = document.getElementById('metricBestThroughput');
    const emergencyEl = document.getElementById('metricEmergency');

    if (bestQueueEl) bestQueueEl.textContent = bestQueue.toFixed(1);
    if (bestSpillEl) bestSpillEl.textContent = bestSpillback.toFixed(0);
    if (bestThruputEl) bestThruputEl.textContent = Math.round(bestThroughput).toLocaleString();
    if (emergencyEl) emergencyEl.textContent = bestDelay.toFixed(1) + 's';
  }

  // --- WebSocket Connection ---
  function connectWS() {
    if (appState.ws) {
      appState.ws.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = protocol + '//' + window.location.host + '/ws/live';

    try {
      appState.ws = new WebSocket(wsUrl);
    } catch (e) {
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
        // Silently handle non-JSON
      }
    };

    appState.ws.onerror = function() {
      appState.apiAvailable = false;
    };

    appState.ws.onclose = function() {
      appState.apiAvailable = false;
      if (appState.reconnectTimer) clearTimeout(appState.reconnectTimer);
      appState.reconnectTimer = setTimeout(connectWS, 3000);
    };
  }

  // --- REST API Fallback ---
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

  // --- Update from Backend State ---
  function updateFromTelemetry(stateData) {
    let reasonText = 'Monitoring balanced traffic across all approaches.';

    if (stateData.simplified && stateData.simplified.decision_headline) {
      reasonText = stateData.simplified.decision_headline;
    }

    const reasonEl = document.getElementById('reasonText');
    if (reasonEl) reasonEl.textContent = reasonText;

    // Update live KPIs
    if (stateData.simplified) {
      const s = stateData.simplified;
      const queueEl = document.getElementById('kpiQueue');
      const waitEl = document.getElementById('kpiWait');
      const exitEl = document.getElementById('kpiExit');

      if (s.queue_pcu && queueEl) queueEl.textContent = s.queue_pcu.toFixed(1);
      if (s.throughput && waitEl) waitEl.textContent = Math.round(s.throughput);
      if (s.exit_fill_pct !== undefined && exitEl) exitEl.textContent = s.exit_fill_pct + '%';
    }

    // Notify 3D scene
    if (window.QueueSense3D && typeof window.QueueSense3D.updateReason === 'function') {
      const headline = stateData.simplified ? stateData.simplified.decision_headline : reasonText;
      window.QueueSense3D.updateReason(headline);
    }

    // Update downstream blockage
    if (stateData.downstream) {
      let maxExit = 0;
      for (const dir in stateData.downstream) {
        const occ = stateData.downstream[dir].exit_occupancy || 0;
        if (occ > maxExit) maxExit = occ;
      }
      const blockagePct = Math.round(maxExit * 100);
      if (window.QueueSense3D) {
        window.QueueSense3D.setDownstreamBlockage(blockagePct);
      }
      const valExit = document.getElementById('valExit');
      if (valExit) valExit.textContent = blockagePct + '%';
    }
  }

  // --- UI Update Functions ---
  function updateScenarioUI() {
    const btns = document.querySelectorAll('.scenario-btn');
    btns.forEach(function(btn) {
      btn.classList.remove('scenario-btn--active');
      if (btn.dataset.scenario === appState.scenario) {
        btn.classList.add('scenario-btn--active');
      }
    });
  }

  function updateModeUI() {
    const modeBtns = document.querySelectorAll('.pill-btn, .mode-pill-btn');
    modeBtns.forEach(function(btn) {
      btn.classList.remove('pill-btn--active', 'mode-pill-btn--active');
      if (btn.dataset.mode === appState.mode) {
        if (btn.classList.contains('mode-pill-btn')) {
          btn.classList.add('mode-pill-btn--active');
        } else {
          btn.classList.add('pill-btn--active');
        }
      }
    });
  }

  function updateCameraUI() {
    const camBtns = document.querySelectorAll('.cam-btn');
    camBtns.forEach(function(btn) {
      btn.classList.remove('cam-btn--active');
      if (btn.dataset.cam === appState.camera) {
        btn.classList.add('cam-btn--active');
      }
    });
  }

  function updateAutoToggleUI() {
    const toggle = document.getElementById('autoToggle');
    if (toggle) {
      toggle.classList.toggle('active', appState.autoCycle);
    }
  }

  function updateTimeline(scenario) {
    const timelineMap = {
      'auto': 'Dynamic Density Detection',
      'surge': 'Density Surge — Green Extension',
      'spillback': 'Exit Jam — Spillback Prevention',
      'emergency': 'Ambulance — Emergency Corridor',
    };
    const label = document.getElementById('scenarioLabel');
    if (label) label.textContent = timelineMap[scenario] || timelineMap.auto;
  }

  // --- Scenario Director ---
  function startAutoCycle() {
    if (appState.autoCycleTimer) {
      clearInterval(appState.autoCycleTimer);
    }

    const scenarios = ['auto', 'surge', 'spillback', 'emergency'];
    appState.scenarioCycleIndex = scenarios.indexOf(appState.scenario);
    if (appState.scenarioCycleIndex === -1) appState.scenarioCycleIndex = 0;

    appState.autoCycleTimer = setInterval(function() {
      if (!appState.autoCycle) return;
      appState.scenarioCycleIndex = (appState.scenarioCycleIndex + 1) % scenarios.length;
      appState.scenario = scenarios[appState.scenarioCycleIndex];
      if (window.QueueSense3D) window.QueueSense3D.setScenario(appState.scenario);
      updateScenarioUI();
      updateTimeline(appState.scenario);

      const reasons = {
        'auto':       'Monitoring balanced traffic across all approaches.',
        'surge':      'West approach surge detected — AI extending green phase.',
        'spillback':  'Downstream queue detected — AI protecting intersection.',
        'emergency':  'Emergency vehicle approaching — AI clearing corridor.',
      };
      const reasonText = reasons[appState.scenario] || reasons.auto;
      const reasonEl = document.getElementById('reasonText');
      if (reasonEl) reasonEl.textContent = reasonText;
      if (window.QueueSense3D && typeof window.QueueSense3D.updateReason === 'function') {
        window.QueueSense3D.updateReason(reasonText);
      }
    }, 8000);
  }

  function stopAutoCycle() {
    if (appState.autoCycleTimer) {
      clearInterval(appState.autoCycleTimer);
      appState.autoCycleTimer = null;
    }
  }

  // --- Event Listeners ---
  function setupEventListeners() {
    // Mode toggles (both navbar and hero)
    const modeButtons = document.querySelectorAll('[data-mode]');
    modeButtons.forEach(function(btn) {
      btn.addEventListener('click', function() {
        appState.mode = btn.dataset.mode;
        updateModeUI();
        if (window.QueueSense3D) window.QueueSense3D.setMode(appState.mode);
      });
    });

    // Camera toggle
    const camButtons = document.querySelectorAll('.cam-btn');
    camButtons.forEach(function(btn) {
      btn.addEventListener('click', function() {
        appState.camera = btn.dataset.cam;
        updateCameraUI();
        if (window.QueueSense3D) window.QueueSense3D.setCamera(appState.camera);
      });
    });

    // Scenario buttons
    const scenarioBtns = document.querySelectorAll('.scenario-btn');
    scenarioBtns.forEach(function(btn) {
      btn.addEventListener('click', function() {
        appState.scenario = btn.dataset.scenario;
        appState.autoCycle = false;
        updateAutoToggleUI();
        stopAutoCycle();
        if (window.QueueSense3D) window.QueueSense3D.setScenario(appState.scenario);
        updateScenarioUI();
        updateTimeline(appState.scenario);

        const reasons = {
          'auto':       'Monitoring balanced traffic across all approaches.',
          'surge':      'West approach surge detected — AI extending green phase.',
          'spillback':  'Downstream queue detected — AI protecting intersection.',
          'emergency':  'Emergency vehicle approaching — AI clearing corridor.',
        };
        const reasonText = reasons[appState.scenario] || reasons.auto;
        const reasonEl = document.getElementById('reasonText');
        if (reasonEl) reasonEl.textContent = reasonText;
        if (window.QueueSense3D && typeof window.QueueSense3D.updateReason === 'function') {
          window.QueueSense3D.updateReason(reasonText);
        }
      });
    });

    // Auto toggle
    const autoToggle = document.getElementById('autoToggle');
    if (autoToggle) {
      autoToggle.addEventListener('click', function() {
        appState.autoCycle = !appState.autoCycle;
        updateAutoToggleUI();
        if (appState.autoCycle) {
          startAutoCycle();
        } else {
          stopAutoCycle();
        }
      });
    }

    // Density slider
    const densitySlider = document.getElementById('sliderDensity');
    if (densitySlider) {
      densitySlider.addEventListener('input', function(e) {
        appState.density = parseInt(e.target.value, 10);
        const valEl = document.getElementById('valDensity');
        const labels = ['Light', 'Light', 'Normal', 'Busy', 'Heavy'];
        const idx = Math.min(Math.floor(appState.density / 25), 4);
        if (valEl) valEl.textContent = labels[idx];
        if (window.QueueSense3D) window.QueueSense3D.setDensity(appState.density);
      });
    }

    // Exit congestion slider
    const exitSlider = document.getElementById('sliderExit');
    if (exitSlider) {
      exitSlider.addEventListener('input', function(e) {
        appState.downstream = parseInt(e.target.value, 10);
        const valEl = document.getElementById('valExit');
        if (valEl) valEl.textContent = appState.downstream + '%';
        if (window.QueueSense3D) window.QueueSense3D.setDownstreamBlockage(appState.downstream);
      });
    }

    // Emergency button
    const btnAmbulance = document.getElementById('btnAmbulance');
    if (btnAmbulance) {
      btnAmbulance.addEventListener('click', function() {
        appState.scenario = 'emergency';
        appState.autoCycle = false;
        updateAutoToggleUI();
        stopAutoCycle();
        if (window.QueueSense3D) {
          window.QueueSense3D.setScenario('emergency');
          window.QueueSense3D.updateReason('Emergency corridor activated — all non-critical phases suspended.');
        }
        updateScenarioUI();
        updateTimeline('emergency');
        const reasonEl = document.getElementById('reasonText');
        if (reasonEl) reasonEl.textContent = 'Emergency corridor activated — all non-critical phases suspended.';

        fetch('/api/emergency-flush/activate', { method: 'POST' }).catch(function() {});
      });
    }

    // Reset button
    const btnReset = document.getElementById('btnReset');
    if (btnReset) {
      btnReset.addEventListener('click', function() {
        appState.scenario = 'auto';
        appState.mode = 'queuesense';
        appState.density = 50;
        appState.downstream = 0;
        appState.autoCycle = false;
        updateAutoToggleUI();
        stopAutoCycle();
        if (window.QueueSense3D) {
          window.QueueSense3D.setScenario('auto');
          window.QueueSense3D.setMode('queuesense');
          window.QueueSense3D.setDensity(50);
          window.QueueSense3D.setDownstreamBlockage(0);
          window.QueueSense3D.updateReason('Monitoring balanced traffic across all approaches.');
        }
        updateScenarioUI();
        updateModeUI();
        updateTimeline('auto');
        const dEl = document.getElementById('valDensity');
        if (dEl) dEl.textContent = 'Normal';
        const eEl = document.getElementById('valExit');
        if (eEl) eEl.textContent = '0%';
        const densityS = document.getElementById('sliderDensity');
        if (densityS) densityS.value = 50;
        const exitS = document.getElementById('sliderExit');
        if (exitS) exitS.value = 0;
        const reasonEl = document.getElementById('reasonText');
        if (reasonEl) reasonEl.textContent = 'Monitoring balanced traffic across all approaches.';
      });
    }
  }

  // --- Initialization ---
  function init() {
    initCharts();
    setupEventListeners();

    connectWS();

    // REST polling fallback
    setInterval(function() {
      if (!appState.apiAvailable) {
        fetchState();
      }
    }, 5000);

    fetchBenchmark();

    if (appState.autoCycle) {
      startAutoCycle();
    }

    if (window.QueueSense3D) {
      window.QueueSense3D.setCamera('isometric');
    }

    updateTimeline('auto');
    console.log('[QueueSense] Dashboard initialized');
  }

  // --- Ensure DOM is ready ---
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // --- Public API ---
  window.QueueSenseApp = {
    state: appState,
    init: init,
    initCharts: initCharts,
    updateCharts: updateCharts,
  };
})();