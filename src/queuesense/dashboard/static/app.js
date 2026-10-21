// QueueSense Dashboard — App Controller
// Bridges three-scene.js with benchmark charts and live KPI updates

// ─── Fallback Benchmark Data (reconciled Stage 3/5 values) ──
const FALLBACK_BENCHMARK = {
  controllers: [
    {
      controller_id: 'A',
      controller_name: 'Controller A (Fixed-Time)',
      throughput_mean: 952.4,
      throughput_std: 54.2,
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
      throughput_std: 48.7,
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
      throughput_std: 52.3,
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
      throughput_std: 49.8,
      delay_mean: 38.5,
      delay_std: 6.7,
      delay_p95: 52.3,
      queue_mean: 1.8,
      queue_p95: 4.2,
      spillback_mean: 0,
    },
  ],
};

// ─── Normalized Benchmark ───────────────────────────────────
function normalizeBenchmark(raw) {
  const data = (raw && raw.controllers && Array.isArray(raw.controllers)) ? raw : FALLBACK_BENCHMARK;
  const controllers = data.controllers || FALLBACK_BENCHMARK.controllers;

  return controllers.map(function (c) {
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

// ─── Chart.js Instances ─────────────────────────────────────
let delayChart = null;
let throughputChart = null;

// ─── Color Palette ───────────────────────────────────────────
function getControllerColor(name) {
  const colors = {
    'A': '#4f96ff',
    'B': '#22c55e',
    'C': '#ffb800',
    'D': '#ff2e4c',
  };
  if (name.includes('Controller A') || name.includes('Fixed-Time')) return colors.A;
  if (name.includes('Controller B') || name.includes('Actuated')) return colors.B;
  if (name.includes('Controller C') || name.includes('Queue-Pressure')) return colors.C;
  if (name.includes('Controller D') || name.includes('QueueSense')) return colors.D;
  return '#4f96ff';
}

// ─── Fetch Benchmark Data ───────────────────────────────────
async function fetchBenchmark(scenario) {
  try {
    const url = scenario ? `/api/benchmark/${scenario}` : '/api/benchmark';
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (e) {
    console.warn('Using fallback benchmark data:', e.message);
    return FALLBACK_BENCHMARK;
  }
}

// ─── Render Charts ─────────────────────────────────────────
function renderCharts(benchmarkData) {
  const controllers = normalizeBenchmark(benchmarkData);
  const ctx = document.getElementById('chartDelay');
  const ctxTp = document.getElementById('chartThroughput');

  if (!ctx || !ctxTp) return;

  const labels = controllers.map(c => {
    return c.id;
  });

  const delayData = controllers.map(c => c.delay_mean);
  const tpData = controllers.map(c => c.throughput_mean);
  const delayErr = controllers.map(c => c.delay_std);
  const tpErr = controllers.map(c => c.throughput_std);
  const bgColors = controllers.map(c => getControllerColor(c.name));

  // Destroy existing charts
  if (delayChart) delayChart.destroy();
  if (throughputChart) throughputChart.destroy();

  // Delay Chart
  delayChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Avg Delay (s)',
        data: delayData,
        backgroundColor: bgColors,
        borderColor: bgColors,
        borderWidth: 0,
        barThickness: 40,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 18, 21, 0.95)',
          titleColor: '#e8e8ec',
          bodyColor: '#b8b8c8',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          cornerRadius: 8,
          callbacks: {
            label: function (ctx) {
              const idx = ctx.dataIndex;
              const c = controllers[idx];
              return `Delay: ${c.delay_mean.toFixed(1)}s (±${c.delay_std.toFixed(1)}) | p95: ${c.delay_p95.toFixed(1)}s`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: '#9ca3af',
            font: { size: 12, family: 'Inter, sans-serif' },
          },
          beginAtZero: true,
        },
        y: {
          grid: { display: false },
          ticks: {
            color: '#b8b8c8',
            font: { size: 13, weight: 600, family: 'Inter, sans-serif' },
          },
        },
      },
      animation: {
        duration: 1200,
        easing: 'power3.out',
      },
    },
  });

  // Throughput Chart
  throughputChart = new Chart(ctxTp, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Throughput (veh/hr)',
        data: tpData,
        backgroundColor: bgColors,
        borderColor: bgColors,
        borderWidth: 0,
        barThickness: 40,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 18, 21, 0.95)',
          titleColor: '#e8e8ec',
          bodyColor: '#b8b8c8',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          cornerRadius: 8,
          callbacks: {
            label: function (ctx) {
              const idx = ctx.dataIndex;
              const c = controllers[idx];
              return `Throughput: ${c.throughput_mean.toFixed(1)} (±${c.throughput_std.toFixed(1)}) | Queue: ${c.queue_mean.toFixed(1)} PCU`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: '#9ca3af',
            font: { size: 12, family: 'Inter, sans-serif' },
          },
          beginAtZero: true,
        },
        y: {
          grid: { display: false },
          ticks: {
            color: '#b8b8c8',
            font: { size: 13, weight: 600, family: 'Inter, sans-serif' },
          },
        },
      },
      animation: {
        duration: 1200,
        easing: 'power3.out',
      },
    },
  });

  // Update metric cards
  updateMetricCards(controllers);
}

function updateMetricCards(controllers) {
  // Best queue
  const bestQueue = Math.min(...controllers.map(c => c.queue_mean));
  const bestQueueEl = document.getElementById('metricBestQueue');
  if (bestQueueEl) bestQueueEl.textContent = bestQueue.toFixed(1);

  // Best spillback
  const bestSpillback = Math.min(...controllers.map(c => c.spillback_mean));
  const bestSpillEl = document.getElementById('metricBestSpillback');
  if (bestSpillEl) bestSpillEl.textContent = bestSpillback.toString();

  // Emergency transit time (fixed from reconciled data)
  const emergencyEl = document.getElementById('metricEmergency');
  if (emergencyEl) emergencyEl.textContent = '28.5s';

  // Best throughput
  const bestTp = Math.max(...controllers.map(c => c.throughput_mean));
  const bestTpEl = document.getElementById('metricBestThroughput');
  if (bestTpEl) bestTpEl.textContent = Math.round(bestTp).toLocaleString();
}

// ─── Initialize App ─────────────────────────────────────────
function initApp() {
  // Load benchmark data
  fetchBenchmark().then(renderCharts).catch(console.error);

  // Wire up UI controls
  setupControls();

  // Setup KPI callback from three-scene.js
  setupKPICallback();

  // Initial timeline progress
  let timelineProgress = 0;
  const timelineBar = document.getElementById('timelineProgress');
  if (timelineBar) {
    setInterval(() => {
      timelineProgress = (timelineProgress + 0.3) % 100;
      if (timelineBar) timelineBar.style.transform = `scaleX(${timelineProgress / 100})`;
    }, 300);
  }
}

// ─── UI Controls ───────────────────────────────────────────
function setupControls() {
  // Mode switches (desktop nav)
  const modeQS = document.getElementById('modeQS');
  const modeTrad = document.getElementById('modeTrad');
  if (modeQS) {
    modeQS.addEventListener('click', () => setMode('queuesense'));
  }
  if (modeTrad) {
    modeTrad.addEventListener('click', () => setMode('traditional'));
  }

  // Mode switches (hero pill)
  const modeQS2 = document.getElementById('modeQS2');
  const modeTrad2 = document.getElementById('modeTrad2');
  if (modeQS2) {
    modeQS2.addEventListener('click', () => setMode('queuesense'));
  }
  if (modeTrad2) {
    modeTrad2.addEventListener('click', () => setMode('traditional'));
  }

  // Camera switches
  const camIso = document.getElementById('camIso');
  const camTop = document.getElementById('camTop');
  const camFollow = document.getElementById('camFollow');
  if (camIso) camIso.addEventListener('click', () => switchCamera('isometric'));
  if (camTop) camTop.addEventListener('click', () => switchCamera('top'));
  if (camFollow) camFollow.addEventListener('click', () => switchCamera('corridor'));

  // Scenario buttons
  const scenarioBtns = document.querySelectorAll('[data-scenario]');
  scenarioBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const scenario = btn.getAttribute('data-scenario');
      setScenario(scenario);
    });
  });

  // Density slider
  const sliderDensity = document.getElementById('sliderDensity');
  const valDensity = document.getElementById('valDensity');
  if (sliderDensity) {
    sliderDensity.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      const labels = ['Idle', 'Light', 'Normal', 'Moderate', 'Heavy', 'Surge'];
      const labelIdx = Math.min(5, Math.floor(val / 20));
      if (valDensity) valDensity.textContent = labels[labelIdx] || 'Normal';
      if (window.QueueSense) window.QueueSense.setDensity(val);
    });
  }

  // Exit block slider
  const sliderExit = document.getElementById('sliderExit');
  const valExit = document.getElementById('valExit');
  if (sliderExit) {
    sliderExit.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      if (valExit) valExit.textContent = `${val}%`;
      if (window.QueueSense) window.QueueSense.setExitBlock(val);
    });
  }

  // Auto-cycle toggle
  const autoToggle = document.getElementById('autoToggle');
  if (autoToggle) {
    autoToggle.addEventListener('click', () => {
      autoToggle.classList.toggle('active');
      if (window.QueueSense) window.QueueSense.setAutoRunning(autoToggle.classList.contains('active'));
    });
  }

  // Emergency button
  const btnAmbulance = document.getElementById('btnAmbulance');
  if (btnAmbulance) {
    btnAmbulance.addEventListener('click', () => {
      if (window.QueueSense) window.QueueSense.triggerEmergency();
    });
  }

  // Reset view button
  const btnReset = document.getElementById('btnReset');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      if (window.QueueSense) window.QueueSense.resetView();
    });
  }
}

// ─── State Setters ─────────────────────────────────────────
function setMode(mode) {
  if (window.QueueSense) {
    window.QueueSense.setMode(mode);
  }

  // Update nav buttons
  const modeQS = document.getElementById('modeQS');
  const modeTrad = document.getElementById('modeTrad');
  const modeQS2 = document.getElementById('modeQS2');
  const modeTrad2 = document.getElementById('modeTrad2');

  if (mode === 'queuesense') {
    modeQS?.classList.add('active');
    modeTrad?.classList.remove('active');
    modeQS2?.classList.add('mode-pill-btn--active');
    modeTrad2?.classList.remove('mode-pill-btn--active');
  } else {
    modeQS?.classList.remove('active');
    modeTrad?.classList.add('active');
    modeQS2?.classList.remove('mode-pill-btn--active');
    modeTrad2?.classList.add('mode-pill-btn--active');
  }
}

function setScenario(scenario) {
  if (window.QueueSense) {
    window.QueueSense.setScenario(scenario);
  }

  // Update scenario buttons
  const scenarioBtns = document.querySelectorAll('[data-scenario]');
  scenarioBtns.forEach(btn => {
    btn.classList.remove('scenario-btn--active');
    if (btn.getAttribute('data-scenario') === scenario) {
      btn.classList.add('scenario-btn--active');
    }
  });

  // Update timeline label
  const label = document.getElementById('scenarioLabel');
  if (label) {
    const labels = {
      auto: 'Normal Flow',
      surge: 'Density Surge',
      spillback: 'Exit Jam',
      emergency: 'Ambulance',
    };
    label.textContent = labels[scenario] || 'Normal Flow';
  }
}

function switchCamera(preset) {
  if (window.QueueSense) {
    window.QueueSense.switchCamera(preset);
  }

  // Update camera buttons
  const camBtns = document.querySelectorAll('.cam-btn');
  camBtns.forEach(btn => {
    btn.classList.remove('cam-btn--active');
    if (btn.getAttribute('data-cam') === preset) {
      btn.classList.add('cam-btn--active');
    }
  });
}

// ─── KPI Callback ──────────────────────────────────────────
function setupKPICallback() {
  if (window.QueueSense) {
    window.QueueSense.onKPIUpdate = function (kpi) {
      const kpiQueue = document.getElementById('kpiQueue');
      const kpiWait = document.getElementById('kpiWait');
      const kpiExit = document.getElementById('kpiExit');

      if (kpiQueue) kpiQueue.textContent = Math.round(kpi.queue).toString();
      if (kpiWait) kpiWait.textContent = kpi.wait.toFixed(1);
      if (kpiExit) kpiExit.textContent = Math.round(kpi.exit).toString() + '%';
    };
  }
}

// ─── Initialize When DOM Ready ────────────────────────────
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

// ─── Expose for debugging ─────────────────────────────────
window.QueueSenseApp = {
  normalizeBenchmark: normalizeBenchmark,
  fetchBenchmark: fetchBenchmark,
  renderCharts: renderCharts,
  FALLBACK_BENCHMARK: FALLBACK_BENCHMARK,
};
