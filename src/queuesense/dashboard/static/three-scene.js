/* =============================================================================
   QUEUESENSE ICCC — 3D LIVING DIGITAL TWIN
   Three.js WebGL corridor scene: J1 -> J1_to_J2 -> J2
   Emil Kowalski Design Engineering Principles Applied
   =============================================================================

   Architecture:
   - Scene: J1 Intersection, J1_to_J2 Link (60m), J2 Intersection
   - Camera Presets: Isometric (orbit), Top-Down (ortho), Driver Follow (perspective)
   - Vehicles: InstancedMesh for 60 FPS with 50+ vehicles
   - Signal Heads: 3-bulb LED with bloom glow, smooth phase transitions
   - AI Detection Zones: Cyan scan volumes, PCU counters, green extension badges
   - Scenario Engine: autonomous cycling with manual trigger override
   ============================================================================= */

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/effects/EffectComposer.js';
import { RenderPass } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/effects/RenderPass.js';
import { UnrealBloomPass } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/effects/UnrealBloomPass.js';
import { ShaderPass } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/effects/ShaderPass.js';
import { FXAAShader } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/shaders/FXAAShader.js';

/* =============================================================================
   CONSTANTS & CONFIGURATION
   ============================================================================= */

const CORRIDOR_LENGTH = 60;        // meters, J1 center to J2 center
const ROAD_WIDTH = 16;             // meters, total road width
const LANE_WIDTH = 4;              // meters per lane
const NUM_LANES = 4;               // 2 each direction

const JUNCTION_SIZE = 8;          // meters, intersection box
const LANE_MARKING_WIDTH = 0.15;
const CROSSWALK_WIDTH = 3;

const MAX_VEHICLES = 80;

// PCU weights per vehicle class (IRC:SP-41)
const PCU_WEIGHTS = {
  car: 1.0,
  bus: 2.2,
  auto: 1.0,
  bike: 0.5,
  truck: 2.0,
};

// Vehicle colors by class
const VEHICLE_COLORS = {
  car: 0x3b82f6,
  bus: 0x10b981,
  auto: 0xf59e0b,
  bike: 0x8b5cf6,
  truck: 0xef4444,
};

// Corridor positions (meters)
const J1_POSITION = 0;      // J1 center
const J2_POSITION = 60;    // J2 center
const CORRIDOR_LENGTH_TOTAL = 120; // total road length (start to end)

/* =============================================================================
   MAIN SCENE CLASS
   ============================================================================= */

class DigitalTwinScene {
  constructor(canvasContainer) {
    this.container = canvasContainer;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.composer = null;
    this.controls = null;
    this.clock = new THREE.Clock();

    // Vehicle system
    this.vehicleMeshes = [];
    this.vehicleInstances = [];
    this.vehicleTemplate = null;
    this.vehicleGroup = new THREE.Group();

    // Signal system
    this.signalGroups = {};
    this.signalState = {
      J1: { NS: 'green', EW: 'red', yellow: 0, allRed: false },
      J2: { NS: 'green', EW: 'red', yellow: 0, allRed: false },
    };

    // AI detection zones
    this.aiZones = {};
    this.spillbackZone = null;

    // Lighting
    this.lights = {};

    // Camera presets
    this.currentPreset = 'isometric';
    this.cameraPresets = {};

    // Scenario engine
    this.scenario = {
      name: 'normal',
      time: 0,
      phase: 'running',
      transitionTimer: 0,
    };
    this.isQueueSenseMode = true;

    // Stats
    this.frameCount = 0;
    this.lastTime = 0;

    // Callback for external state updates
    this.onStateUpdate = null;

    this.init();
  }

  /* ---- Initialization ---- */

  init() {
    this.createScene();
    this.createRenderer();
    this.createLights();
    this.createCameraPresets();
    this.createRoads();
    this.createJunctions();
    this.createSignals();
    this.createVehicles();
    this.createAIZones();
    this.createSpillbackVisual();
    this.setupEventListeners();
    this.animate();
  }

  createScene() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x090d16);
    this.scene.fog = new THREE.FogExp2(0x090d16, 0.002);

    // Add to container
    this.container.appendChild(this.renderer ? null : document.createElement('div'));
  }

  createRenderer() {
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
      stencil: false,
    });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setAnimationLoop(() => this.animate());
    this.renderer.outputEncoding = THREE.sRGBEncoding;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.container.appendChild(this.renderer.domElement);
    this.container.id = 'three-canvas';
    this.container.appendChild(document.createElement('div')).remove();

    // Post-processing
    this.setupPostProcessing();
  }

  setupPostProcessing() {
    const width = window.innerWidth;
    const height = window.innerHeight;

    this.composer = new EffectComposer(this.renderer);
    this.composer.setSize(width, height);

    // Render pass
    const renderPass = new RenderPass(this.scene, this.camera);
    this.composer.addPass(renderPass);

    // Bloom pass for signal glow
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(width, height),
      1.5,   // strength
      0.4,   // radius
      0.85,  // threshold
    );
    this.composer.addPass(bloomPass);
    this.bloomPass = bloomPass;

    // FXAA
    const fxaaPass = new ShaderPass(FXAAShader);
    const pixelRatio = window.devicePixelRatio;
    fxaaPass.material.uniforms['resolution'].value.set(1 / (width * pixelRatio), 1 / (height * pixelRatio));
    this.composer.addPass(fxaaPass);
  }

  createLights() {
    // Ambient light
    const ambient = new THREE.AmbientLight(0x404060, 1.5);
    this.scene.add(ambient);

    // Directional light (sun)
    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    sun.position.set(20, 40, 15);
    sun.castShadow = true;
    sun.shadow.mapSize.width = 2048;
    sun.shadow.mapSize.height = 2048;
    sun.shadow.camera.near = 0.5;
    sun.shadow.camera.far = 100;
    sun.shadow.camera.left = -30;
    sun.shadow.camera.right = 30;
    sun.shadow.camera.top = 30;
    sun.shadow.camera.bottom = -30;
    sun.shadow.bias = -0.0001;
    this.scene.add(sun);
    this.lights.sun = sun;

    // Hemisphere light for sky gradient
    const hemi = new THREE.HemisphereLight(0x4a6fa5, 0x1a1a2e, 0.4);
    this.scene.add(hemi);

    // Junction pool lights
    this.createJunctionPoolLights();
  }

  createJunctionPoolLights() {
    // Soft pool lights at each junction
    for (const [jid, zPos] of Object.entries({ J1: 0, J2: CORRIDOR_LENGTH })) {
      const poolLight = new THREE.PointLight(0x10b981, 0.5, 15);
      poolLight.position.set(0, 8, zPos);
      this.scene.add(poolLight);
    }
  }

  createCameraPresets() {
    const aspect = window.innerWidth / window.innerHeight;

    // Isometric
    this.cameraPresets.isometric = new THREE.PerspectiveCamera(35, aspect, 0.1, 200);
    this.cameraPresets.isometric.position.set(-25, 20, 40);
    this.cameraPresets.isometric.lookAt(0, 0, 30);

    // Top-Down
    this.cameraPresets.topDown = new THREE.OrthographicCamera(
      -CORRIDOR_LENGTH_TOTAL / 2,
      CORRIDOR_LENGTH_TOTAL / 2,
      ROAD_WIDTH * 1.5,
      -ROAD_WIDTH * 1.5,
      0.1,
      200
    );
    this.cameraPresets.topDown.position.set(0, 35, CORRIDOR_LENGTH / 2);
    this.cameraPresets.topDown.lookAt(0, 0, CORRIDOR_LENGTH / 2);
    this.cameraPresets.topDown.rotation.x = -Math.PI / 2;

    // Driver View (follows ambulance along corridor)
    this.cameraPresets.driver = new THREE.PerspectiveCamera(50, aspect, 0.1, 200);
    this.cameraPresets.driver.position.set(0, 2, 0);
    this.cameraPresets.driver.lookAt(0, 0, 10);

    // Default to isometric
    this.camera = this.cameraPresets.isometric.clone();

    // Orbit controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.minDistance = 10;
    this.controls.maxDistance = 80;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.1;

    // Disable controls for top-down and driver view
    this.updateControlsForPreset(this.currentPreset);
  }

  updateControlsForPreset(preset) {
    if (preset === 'isometric') {
      this.controls.enabled = true;
      this.controls.target.set(0, 0, CORRIDOR_LENGTH / 2);
    } else {
      this.controls.enabled = false;
    }
  }

  switchCameraPreset(presetName) {
    this.currentPreset = presetName;
    const target = this.cameraPresets[presetName];

    if (target.isOrthographicCamera) {
      this.camera = target.clone();
      this.camera.rotation.copy(target.rotation);
      this.camera.position.copy(target.position);
    } else {
      this.camera = target.clone();
    }

    this.updateControlsForPreset(presetName);
    this.composer.passes[0].camera = this.camera;

    // Emit event
    if (this.onPresetChange) {
      this.onPresetChange(presetName);
    }
  }

  /* ---- Road & Junction Geometry ---- */

  createRoads() {
    // Main road (asphalt)
    const roadGeometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL, ROAD_WIDTH * 2.5);
    const roadMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a2e,
      roughness: 0.9,
      metalness: 0.1,
    });
    const road = new THREE.Mesh(roadGeometry, roadMaterial);
    road.rotation.x = -Math.PI / 2;
    road.receiveShadow = true;
    this.scene.add(road);

    // Road edges (curbs)
    const curbGeometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL, 0.5);
    const curbMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a3e,
      roughness: 0.8,
    });

    // North side curb
    const curbN = new THREE.Mesh(curbGeometry, curbMaterial);
    curbN.rotation.x = -Math.PI / 2;
    curbN.position.set(0, 0.01, ROAD_WIDTH + 0.25);
    curbN.receiveShadow = true;
    this.scene.add(curbN);

    // South side curb
    const curbS = curbN.clone();
    curbS.position.set(0, 0.01, -(ROAD_WIDTH + 0.25));
    this.scene.add(curbS);

    // Lane markings (dashed center line)
    this.createLaneMarkings();

    // Side lines
    this.createSideLines();

    // Background (grass/verge)
    this.createBackground();
  }

  createLaneMarkings() {
    const laneCount = NUM_LANES;
    const laneWidthMeters = ROAD_WIDTH / laneCount;

    // Center dashed line (North-South traffic)
    const centerLineGeometry = new THREE.PlaneGeometry(0.1, CORRIDOR_LENGTH_TOTAL);
    const centerLineMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.3,
    });

    // Dashed line using InstancedMesh
    const dashGeometry = new THREE.PlaneGeometry(0.1, 2);
    const dashMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.8,
      emissive: 0xffffff,
      emissiveIntensity: 0.2,
    });

    for (let i = 0; i < laneCount - 1; i++) {
      const offset = -ROAD_WIDTH / 2 + laneWidthMeters * (i + 1);
      for (let z = 0; z < CORRIDOR_LENGTH_TOTAL; z += 4) {
        const dash = new THREE.Mesh(dashGeometry, dashMaterial);
        dash.rotation.x = -Math.PI / 2;
        dash.position.set(0, 0.02, z - CORRIDOR_LENGTH_TOTAL / 2);
        dash.position.x = offset; // Offset to lane divider position
        // Actually position based on lane boundary
        dash.position.x = offset - ROAD_WIDTH / 2 - ROAD_WIDTH / 2;
        // Let me recalculate
        dash.position.x = -ROAD_WIDTH / 2 + laneWidthMeters * (i + 1);
        this.scene.add(dash);
      }
    }

    // Solid center line
    const centerLine = new THREE.Mesh(centerLineGeometry, centerLineMaterial);
    centerLine.rotation.x = -Math.PI / 2;
    centerLine.position.y = 0.01;
    this.scene.add(centerLine);
  }

  createSideLines() {
    const lineGeometry = new THREE.PlaneGeometry(0.1, CORRIDOR_LENGTH_TOTAL);
    const lineMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.5,
    });

    const leftLine = new THREE.Mesh(lineGeometry, lineMaterial);
    leftLine.rotation.x = -Math.PI / 2;
    leftLine.position.set(-ROAD_WIDTH / 2 - 0.05, 0.02, 0);
    this.scene.add(leftLine);

    const rightLine = leftLine.clone();
    rightLine.position.set(ROAD_WIDTH / 2 + 0.05, 0.02, 0);
    this.scene.add(rightLine);
  }

  createBackground() {
    // Ground plane (green verge)
    const groundGeometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL + 20, ROAD_WIDTH * 4);
    const groundMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f2020,
      roughness: 1.0,
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.position.z = 0;
    ground.receiveShadow = true;
    this.scene.add(ground);

    // Skybox (gradient)
    this.createSkybox();
  }

  createSkybox() {
    const vertexShader = `
      varying vec3 vWorldPosition;
      void main() {
        vec4 worldPosition = modelMatrix * vec4(position, 1.0);
        vWorldPosition = worldPosition.xyz;
        gl_Position = projectionMatrix * worldPosition;
      }
    `;

    const fragmentShader = `
      uniform vec3 topColor;
      uniform vec3 bottomColor;
      uniform float offset;
      uniform float exponent;
      varying vec3 vWorldPosition;
      void main() {
        float height = normalize(vWorldPosition).y;
        float factor = exp(-height * exponent + offset);
        gl_FragColor = mix(bottomColor, topColor, factor);
      }
    `;

    const skyGeometry = new THREE.SphereGeometry(150, 32, 32);
    skyGeometry.scale(-1, 1, 1);
    const skyMaterial = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        topColor: { value: new THREE.Color(0x090d16) },
        bottomColor: { value: new THREE.Color(0x090d16) },
        offset: { value: 0.7 },
        exponent: { value: 0.6 },
      },
      side: THREE.BackSide,
    });
    const skyMesh = new THREE.Mesh(skyGeometry, skyMaterial);
    this.scene.add(skyMesh);
  }

  /* ---- Junction Creation ---- */

  createJunctions() {
    // J1 Junction
    this.createJunction('J1', J1_POSITION);
    // J2 Junction
    this.createJunction('J2', J2_POSITION);

    // Junction labels
    this.createJunctionLabels();
  }

  createJunction(jid, zPos) {
    // Yellow hatched KEEP CLEAR box
    const junctionGeometry = new THREE.PlaneGeometry(JUNCTION_SIZE, JUNCTION_SIZE);
    const junctionTexture = this.createHatchTexture();
    const junctionMaterial = new THREE.MeshStandardMaterial({
      map: junctionTexture,
      color: 0x422008,
      roughness: 0.8,
      transparent: true,
      opacity: 0.7,
    });

    const junction = new THREE.Mesh(junctionGeometry, junctionMaterial);
    junction.rotation.x = -Math.PI / 2;
    junction.position.set(0, 0.03, zPos);
    junction.receiveShadow = true;
    this.scene.add(junction);

    // Junction boundaries (raised curb)
    const curbGeometry = new THREE.RingGeometry(JUNCTION_SIZE / 2, JUNCTION_SIZE / 2 + 0.3, 4);
    const curbMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a3e,
      roughness: 0.7,
    });

    // Four corner curbs
    const corners = [
      [-JUNCTION_SIZE / 2 - 0.15, 0, -JUNCTION_SIZE / 2 - 0.15],
      [JUNCTION_SIZE / 2 + 0.15, 0, -JUNCTION_SIZE / 2 - 0.15],
      [JUNCTION_SIZE / 2 + 0.15, 0, JUNCTION_SIZE / 2 + 0.15],
      [-JUNCTION_SIZE / 2 - 0.15, 0, JUNCTION_SIZE / 2 + 0.15],
    ];

    corners.forEach((pos, i) => {
      const curb = new THREE.Mesh(curbGeometry, curbMaterial);
      curb.position.set(pos[0], 0.05, pos[2]);
      curb.rotation.x = -Math.PI / 2;
      curb.castShadow = true;
      curb.receiveShadow = true;
      this.scene.add(curb);
    });

    // Zebra crossings
    this.createZebraCrossings(jid, zPos);

    // Save junction group for signal placement
    this.signalGroups[jid] = {
      zPos,
      group: new THREE.Group(),
    };
    this.junctionZ = { ...this.junctionZ, [jid]: zPos };
  }

  createHatchTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#422008';
    ctx.fillRect(0, 0, 64, 64);

    ctx.strokeStyle = '#1a1a3e';
    ctx.lineWidth = 3;
    ctx.beginPath();
    for (let i = 0; i < 64; i += 8) {
      ctx.moveTo(i, 0);
      ctx.lineTo(i - 64, 64);
    }
    ctx.stroke();

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(JUNCTION_SIZE / 16, JUNCTION_SIZE / 16);
    return texture;
  }

  createZebraCrossings(jid, zPos) {
    const zebraGeometry = new THREE.PlaneGeometry(2, 1.5);
    const zebraMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.8,
      emissive: 0xffffff,
      emissiveIntensity: 0.5,
    });

    // Zebra crossings on each approach
    const offsets = [
      [0, 0.01, -JUNCTION_SIZE / 2 - 0.75], // South approach
      [0, 0.01, JUNCTION_SIZE / 2 + 0.75],  // North approach
      [-JUNCTION_SIZE / 2 - 1.0, 0.01, 0],  // West approach
      [JUNCTION_SIZE / 2 + 1.0, 0.01, 0],   // East approach
    ];

    offsets.forEach((offset) => {
      const zebra = new THREE.Mesh(zebraGeometry, zebraMaterial);
      zebra.rotation.x = -Math.PI / 2;
      zebra.position.set(offset[0] + zPos, offset[1], offset[2] + zPos);
      // Actually position relative to junction
      zebra.position.set(offset[0], offset[1], zPos + (jid === 'J1' ? offset[2] : offset[2]));
      this.scene.add(zebra);
    });
  }

  createJunctionLabels() {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 256;
    canvas.height = 64;

    ctx.font = '24px monospace';
    ctx.fillStyle = '#10b981';
    ctx.textAlign = 'center';
    ctx.fillText('J1', 128, 32);

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(10, 3, 1);
    sprite.position.set(-ROAD_WIDTH / 2 - 4, 8, J1_POSITION);
    this.scene.add(sprite);

    // J2 label
    const canvas2 = canvas.cloneNode(true);
    const ctx2 = canvas2.getContext('2d');
    ctx2.font = '24px monospace';
    ctx2.fillStyle = '#10b981';
    ctx2.textAlign = 'center';
    ctx2.fillText('J2', 128, 32);

    const texture2 = new THREE.CanvasTexture(canvas2);
    const material2 = new THREE.SpriteMaterial({ map: texture2, transparent: true });
    const sprite2 = new THREE.Sprite(material2);
    sprite2.scale.set(10, 3, 1);
    sprite2.position.set(-ROAD_WIDTH / 2 - 4, 8, J2_POSITION);
    this.scene.add(sprite2);
  }

  /* ---- Signal Heads ---- */

  createSignals() {
    this.createSignalAtJunction('J1', J1_POSITION);
    this.createSignalAtJunction('J2', J2_POSITION);
  }

  createSignalAtJunction(jid, zPos) {
    const group = new THREE.Group();
    group.name = jid;

    // 8 signal positions (one per approach corner)
    const signalPositions = [
      // North approaches
      { pos: new THREE.Vector3(-ROAD_WIDTH / 2 - 0.5, 4, zPos - JUNCTION_SIZE / 2), dir: 'north', name: 'NS_N' },
      { pos: new THREE.Vector3(ROAD_WIDTH / 2 + 0.5, 4, zPos - JUNCTION_SIZE / 2), dir: 'north', name: 'NS_E' },
      // South approaches
      { pos: new THREE.Vector3(-ROAD_WIDTH / 2 - 0.5, 4, zPos + JUNCTION_SIZE / 2), dir: 'south', name: 'NS_N' },
      { pos: new THREE.Vector3(ROAD_WIDTH / 2 + 0.5, 4, zPos + JUNCTION_SIZE / 2), dir: 'south', name: 'NS_E' },
      // East approaches
      { pos: new THREE.Vector3(zPos - JUNCTION_SIZE / 2, 4, -ROAD_WIDTH / 2 - 0.5), dir: 'east', name: 'EW_W' },
      { pos: new THREE.Vector3(zPos + JUNCTION_SIZE / 2, 4, -ROAD_WIDTH / 2 - 0.5), dir: 'east', name: 'EW_E' },
      // West approaches
      { pos: new THREE.Vector3(zPos - JUNCTION_SIZE / 2, 4, ROAD_WIDTH / 2 + 0.5), dir: 'west', name: 'EW_W' },
      { pos: new THREE.Vector3(zPos + JUNCTION_SIZE / 2, 4, ROAD_WIDTH / 2 + 0.5), dir: 'west', name: 'EW_E' },
    ];

    // For simplicity, place 4 signal poles at cardinal directions
    const directions = [
      { pos: [0, 4, zPos - ROAD_WIDTH - 2], rot: [0, 0, 0], name: 'NS_approach' },
      { pos: [0, 4, zPos + ROAD_WIDTH + 2], rot: [0, Math.PI, 0], name: 'NS_approach_opposite' },
      { pos: [-ROAD_WIDTH - 2, 4, zPos], rot: [0, 0, Math.PI / 2], name: 'EW_approach' },
      { pos: [ROAD_WIDTH + 2, 4, zPos], rot: [0, -Math.PI / 2, 0], name: 'EW_approach_opposite' },
    ];

    directions.forEach((dir) => {
      const signal = this.createSignalHead(dir.pos, dir.rot, jid, dir.name);
      group.add(signal);
    });

    this.scene.add(group);
    this.signalGroups[jid].group = group;
  }

  createSignalHead(position, rotation, junctionId, approach) {
    const group = new THREE.Group();
    group.position.set(...position);
    group.rotation.set(...rotation);

    // Signal pole
    const poleGeometry = new THREE.CylinderGeometry(0.15, 0.2, 6, 8);
    const poleMaterial = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.8,
      roughness: 0.3,
    });
    const pole = new THREE.Mesh(poleGeometry, poleMaterial);
    pole.castShadow = true;
    pole.receiveShadow = true;
    group.add(pole);

    // Signal box
    const boxGeometry = new THREE.BoxGeometry(0.8, 1.2, 0.5);
    const boxMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      metalness: 0.5,
      roughness: 0.4,
    });
    const box = new THREE.Mesh(boxGeometry, boxMaterial);
    box.position.set(0, 5, 0);
    box.castShadow = true;
    group.add(box);

    // 3 LED bulbs: Red, Yellow, Green
    const bulbGeometry = new THREECylinderGeometry(0.25, 0.25, 0.3, 32);
    // Actually let me use SphereGeometry for bulbs
    const sphereGeometry = new THREE.SphereGeometry(0.22, 16, 16);

    const bulbPositions = [
      { y: 0.25, color: 0xff0000, name: 'red' },
      { y: 0, color: 0xffff00, name: 'yellow' },
      { y: -0.25, color: 0x00ff00, name: 'green' },
    ];

    bulbPositions.forEach((bp) => {
      const emissiveColor = bp.color === 0xff0000 ? new THREE.Color(0.5, 0, 0) :
                           bp.color === 0xffff00 ? new THREE.Color(0.5, 0.5, 0) :
                           new THREE.Color(0, 0.5, 0);

      const bulbMaterial = new THREE.MeshStandardMaterial({
        color: bp.color,
        emissive: emissiveColor,
        emissiveIntensity: 0,
        transparent: true,
        opacity: 0.3,
      });

      const bulb = new THREE.Mesh(sphereGeometry, bulbMaterial);
      bulb.position.set(0, bp.y, 0.35);
      bulb.userData = { color: bp.color, name: bp.name, junctionId, approach };
      group.add(bulb);

      // Store reference for animation
      if (!group.userData.bulbs) group.userData.bulbs = {};
      group.userData.bulbs[bp.name] = bulb;
    });

    // Signal housing (clear cover)
    const coverGeometry = new THREE.BoxGeometry(0.7, 1, 0.1);
    const coverMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x101020,
      transparent: true,
      opacity: 0.3,
      roughness: 0.1,
      metalness: 0.1,
      transmission: 0.5,
    });
    const cover = new THREE.Mesh(coverGeometry, coverMaterial);
    cover.position.set(0, 0, 0.55);
    group.add(cover);

    return group;
  }

  updateSignalColor(junctionId, direction, color) {
    const group = this.signalGroups[junctionId]?.group;
    if (!group) return;

    group.children.forEach((signal) => {
      if (signal.userData.bulbs) {
        Object.entries(signal.userData.bulbs).forEach(([name, bulb]) => {
          const bulbMat = bulb.material;
          if (name === color) {
            bulbMat.emissive Intensity = 0.8;
            bulbMat.opacity = 1;
            // Spring-like glow
            bulb.scale.setScalar(1.1);
          } else {
            bulbMat.emissiveIntensity = 0;
            bulbMat.opacity = 0.3;
            bulb.scale.setScalar(1);
          }

          // Update emissive color based on which is active
          if (name === 'red' && color === 'red') {
            bulbMat.emissive = new THREE.Color(0.6, 0.1, 0.1);
            bulbMat.color.set(0xff4444);
          } else if (name === 'yellow' && color === 'yellow') {
            bulbMat.emissive = new THREE.Color(0.6, 0.6, 0.1);
            bulbMat.color.set(0xffff44);
          } else if (name === 'green' && color === 'green') {
            bulbMat.emissive = new THREE.Color(0.1, 0.6, 0.1);
            bulbMat.color.set(0x44ff44);
          } else if (name !== color) {
            bulbMat.emissive.setHex(0x000000);
            bulbMat.color.set(0x333333);
            bulbMat.opacity = 0.15;
          }
        });
      }
    });
  }

  /* ---- Vehicle System ---- */

  createVehicles() {
    // Create instanced mesh for each vehicle class
    this.vehicleGroup = new THREE.Group();
    this.scene.add(this.vehicleGroup);

    // Vehicle templates (InstancedMesh for performance)
    this.createVehicleInstance('car', 20);
    this.createVehicleInstance('bus', 5);
    this.createVehicleInstance('auto', 15);
    this.createVehicleInstance('bike', 20);
    this.createVehicleInstance('truck', 5);

    // Populate with initial vehicles
    this.populateVehicles();
  }

  createVehicleInstance(classType, count) {
    const geometry = this.getVehicleGeometry(classType);
    const color = VEHICLE_COLORS[classType];

    const material = new THREE.MeshStandardMaterial({
      color: color,
      roughness: 0.4,
      metalness: 0.6,
      transparent: classType === 'bike',
      opacity: classType === 'bike' ? 0.8 : 1,
    });

    const instanced = new THREE.InstancedMesh(geometry, material, count);
    instanced.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    instanced.frustumCulled = false;
    instanced.userData = { classType, count, color };

    this.vehicleGroup.add(instanced);
    this.vehicleInstances[classType] = { mesh: instanced, instances: [] };
  }

  getVehicleGeometry(classType) {
    let geometry;

    switch (classType) {
      case 'car':
        geometry = new THREE.BoxGeometry(1.2, 0.5, 2.0);
        break;
      case 'bus':
        geometry = new THREE.BoxGeometry(2.8, 0.7, 8.0);
        break;
      case 'auto':
        geometry = new THREE.BoxGeometry(0.8, 0.6, 1.6);
        break;
      case 'bike':
        geometry = new THREE.BoxGeometry(0.4, 0.3, 0.8);
        break;
      case 'truck':
        geometry = new THREE.BoxGeometry(2.0, 0.8, 5.0);
        break;
      default:
        geometry = new THREE.BoxGeometry(1.0, 0.5, 1.5);
    }

    // Add rounded edges
    const roundedGeometry = new THREE.BufferGeometryUtils ?
      THREE.BufferGeometryUtils.toCreasedNormals(geometry) : geometry;

    return geometry;
  }

  populateVehicles() {
    // Place vehicles along the corridor in traffic
    const now = Date.now();
    const timeOfDay = (now / 1000) % 1;

    // North-South lanes (Z direction)
    for (let lane = 0; lane < 2; lane++) {
      const laneX = -ROAD_WIDTH / 4 + (lane - 0.5) * (ROAD_WIDTH / 2);
      const count = 8 + Math.floor(Math.random() * 6);
      for (let i = 0; i < count; i++) {
        const z = (i / count) * CORRIDOR_LENGTH_TOTAL - CORRIDOR_LENGTH_TOTAL / 2;
        if (z < J1_POSITION - JUNCTION_SIZE || z > J1_POSITION + JUNCTION_SIZE) {
          this.addVehicleInstance('car', laneX, z, 0, 0, Math.random() * 0.1 - 0.05);
        }
      }
    }

    // East-West lanes (X direction) at junctions
    for (const zPos of [J1_POSITION, J2_POSITION]) {
      const count = 4 + Math.floor(Math.random() * 4);
      for (let i = 0; i < count; i++) {
        const x = (i / count) * ROAD_WIDTH - ROAD_WIDTH / 2;
        if (x < -JUNCTION_SIZE || x > JUNCTION_SIZE) {
          const laneZ = -ROAD_WIDTH / 4 + Math.random() * 2;
          this.addVehicleInstance('auto', x, zPos + laneZ, 0, 0, Math.PI / 2);
        }
      }

      // Add some buses
      if (Math.random() > 0.5) {
        const x = -JUNCTION_SIZE - 5 - Math.random() * 3;
        this.addVehicleInstance('bus', x, zPos, 0, 0, Math.PI / 2);
      }
    }

    // Add bikes
    for (let i = 0; i < 10; i++) {
      const z = Math.random() * CORRIDOR_LENGTH_TOTAL - CORRIDOR_LENGTH_TOTAL / 2;
      const x = -ROAD_WIDTH / 2 + Math.random() * ROAD_WIDTH;
      this.addVehicleInstance('bike', x, z, 0, 0, Math.random() > 0.5 ? 0 : Math.PI);
    }

    // Add trucks
    for (let i = 0; i < 3; i++) {
      const z = 10 + i * 15;
      if (z < CORRIDOR_LENGTH_TOTAL - 10) {
        this.addVehicleInstance('truck', ROAD_WIDTH / 4, z, 0, 0, 0);
      }
    }
  }

  addVehicleInstance(classType, x, z, y, tilt, rotation, speed = 0.02) {
    const instance = this.vehicleInstances[classType];
    if (!instance || !instance.instances) return;

    const instanceId = instance.instances.length;
    if (instanceId >= instance.count) return;

    const dummy = new THREE.Object3D();
    dummy.position.set(x, y + (classType === 'bike' ? 0.2 : 0.15), z);
    dummy.rotation.y = rotation;
    dummy.updateMatrix();

    instance.mesh.setMatrixAt(instanceId, dummy.matrix);

    const vehicleData = {
      id: `${classType}_${instanceId}_${Date.now()}`,
      classType,
      x,
      z,
      y,
      rotationY: rotation,
      speed: speed * (0.5 + Math.random() * 0.5),
      targetX: x,
      targetZ: z,
      targetRotation: rotation,
      instanceId,
      dummy,
    };

    instance.instances.push(vehicleData);
    instance.mesh.instanceMatrix.needsUpdate = true;

    return vehicleData;
  }

  updateVehicles(deltaTime) {
    Object.entries(this.vehicleInstances).forEach(([classType, instance]) => {
      if (!instance.instances) return;

      instance.instances.forEach((v, idx) => {
        // Move vehicles along traffic flow
        const speed = v.speed * (this.scenario.name === 'surge' ? 2 : 1);

        if (v.rotationY < Math.PI / 4 || v.rotationY > Math.PI * 6 / 4) {
          // NS movement (Z direction)
          v.targetZ += speed * deltaTime * 60;
          if (v.targetZ > CORRIDOR_LENGTH_TOTAL / 2) {
            v.targetZ = -CORRIDOR_LENGTH_TOTAL / 2;
          }
        } else {
          // EW movement (X direction)
          v.targetX += speed * deltaTime * 60;
          if (Math.abs(v.targetX) > ROAD_WIDTH / 2 + 2) {
            v.targetX = -ROAD_WIDTH / 2 - 2;
          }
        }

        // Check if stopped at red light
        this.applyTrafficLightLogic(v, deltaTime);

        // Update position
        v.dummy.position.lerp(
          new THREE.Vector3(v.targetX, v.y + (v.classType === 'bike' ? 0.2 : 0.15), v.targetZ),
          0.1
        );
        v.dummy.rotation.y = THREE.MathUtils.damp(v.dummy.rotation.y, v.targetRotation, 2, deltaTime);
        v.dummy.updateMatrix();
        instance.mesh.setMatrixAt(v.instanceId, v.dummy.matrix);
      });

      instance.mesh.instanceMatrix.needsUpdate = true;
    });
  }

  applyTrafficLightLogic(vehicle, deltaTime) {
    const z = vehicle.z;
    const x = vehicle.x;

    // Check if vehicle is near J1 or J2
    for (const jid of ['J1', 'J2']) {
      const zPos = jid === 'J1' ? J1_POSITION : J2_POSITION;
      const distToJunction = Math.abs(z - zPos);

      if (distToJunction < JUNCTION_SIZE * 1.5) {
        const direction = z < zPos ? 'north' : 'south';
        const approach = direction === 'north' ? 'south' : 'north';
        const signal = this.signalState[jid];

        // NS traffic (Z direction) should stop when EW is green
        const isStopped = vehicle.rotationY < Math.PI / 4;
        const shouldStop = signal.EW === 'green' || signal.EW === 'yellow';

        if (isStopped && shouldStop) {
          vehicle.targetZ = z; // Hold position
          vehicle.speed = 0;
        } else if (vehicle.speed === 0) {
          vehicle.speed = 0.02 * (0.5 + Math.random() * 0.5);
        }
      }
    }
  }

  /* ---- AI Detection Zones ---- */

  createAIZones() {
    // Detection zone at J1 approach (North)
    this.createAIDetectionZone('J1_N', new THREE.Vector3(0, 2, J1_POSITION - 10), 'north');

    // Detection zone at J1 approach (East)
    this.createAIDetectionZone('J1_E', new THREE.Vector3(-10, 2, J1_POSITION), 'east');

    // Detection zone at J2 approach
    this.createAIDetectionZone('J2_N', new THREE.Vector3(0, 2, J2_POSITION - 10), 'north');

    // Downstream exit zone
    this.createAIDetectionZone('exit_east', new THREE.Vector3(0, 1, J2_POSITION + 15), 'exit');
  }

  createAIDetectionZone(zoneId, position, direction) {
    const geometry = new THREE.RingGeometry(6, 8, 32);
    const material = new THREE.MeshStandardMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0.2,
      side: THREE.DoubleSide,
      emissive: 0x06b6d4,
      emissiveIntensity: 0.3,
    });

    const zone = new THREE.Mesh(geometry, material);
    zone.position.copy(position);

    if (direction === 'north' || direction === 'south') {
      zone.rotation.x = Math.PI / 2;
    } else if (direction === 'east' || direction === 'west') {
      zone.rotation.z = Math.PI / 2;
    }

    zone.userData = { zoneId, direction, pcuCount: 0 };
    this.scene.add(zone);
    this.aiZones[zoneId] = zone;

    // Scan line animation
    this.animateScanLine(zone, direction);
  }

  animateScanLine(zone, direction) {
    const geometry = new THREE.PlaneGeometry(8, 0.2);
    const material = new THREE.MeshStandardMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0.6,
      emissive: 0x06b6d4,
      emissiveIntensity: 0.5,
    });

    const scanLine = new THREE.Mesh(geometry, material);
    zone.add(scanLine);

    // Animate scan
    const animate = () => {
      if (this.scenario.phase !== 'running') return;

      const elapsed = this.clock.getElapsedTime();
      const sweep = (Math.sin(elapsed * 0.5) * 0.5 + 0.5) * 6;

      if (direction === 'north' || direction === 'south') {
        scanLine.position.z = sweep - 3;
      } else {
        scanLine.position.x = sweep - 3;
      }

      requestAnimationFrame(animate);
    };
    animate();
  }

  /* ---- Spillback Visualization ---- */

  createSpillbackVisual() {
    // Crimson zone overlay on J1_to_J2 link
    const geometry = new THREE.PlaneGeometry(10, ROAD_WIDTH * 2.5);
    const material = new THREE.MeshStandardMaterial({
      color: 0x7f1d1d,
      transparent: true,
      opacity: 0,
      emissive: 0x7f1d1d,
      emissiveIntensity: 0,
      side: THREE.DoubleSide,
    });

    this.spillbackZone = new THREE.Mesh(geometry, material);
    this.spillbackZone.rotation.x = -Math.PI / 2;
    this.spillbackZone.position.set(0, 0.05, CORRIDOR_LENGTH / 2);
    this.scene.add(this.spillbackZone);
  }

  setSpillbackActive(active, occupancy = 0) {
    if (!this.spillbackZone) return;

    const material = this.spillbackZone.material;
    if (active) {
      material.opacity = 0.4 + occupancy * 0.3;
      material.emissiveIntensity = 0.3 + occupancy * 0.2;
    } else {
      material.opacity = 0;
      material.emissiveIntensity = 0;
    }
  }

  /* ---- Signal Timing & Phase Updates ---- */

  updateSignalPhase(junctionId, direction, color, duration = 0) {
    this.signalState[junctionId][direction] = color;
    this.updateSignalColor(junctionId, direction, color);

    // Emit signal timing for external consumption
    if (this.onSignalUpdate) {
      this.onSignalUpdate({
        junction: junctionId,
        direction,
        color,
        duration,
      });
    }
  }

  /* ---- Scenario Engine ---- */

  setScenario(scenarioName) {
    this.scenario.name = scenarioName;
    this.scenario.time = 0;
    this.scenario.phase = 'running';

    switch (scenarioName) {
      case 'normal':
        this.setSpillbackActive(false);
        this.updateSignalPhase('J1', 'NS', 'green');
        this.updateSignalPhase('J1', 'EW', 'red');
        this.updateSignalPhase('J2', 'NS', 'green');
        this.updateSignalPhase('J2', 'EW', 'red');
        break;

      case 'surge':
        this.setSpillbackActive(false);
        this.updateSignalPhase('J1', 'NS', 'green');
        this.updateSignalPhase('J1', 'EW', 'red');
        this.updateSignalPhase('J2', 'NS', 'green');
        this.updateSignalPhase('J2', 'EW', 'red');
        // Add surge vehicles
        this.spawnSurgeVehicles();
        break;

      case 'spillback':
        this.setSpillbackActive(true, 0.85);
        this.updateSignalPhase('J1', 'NS', 'green');
        this.updateSignalPhase('J1', 'EW', 'red'); // EW blocked
        this.updateSignalPhase('J2', 'NS', 'green');
        this.updateSignalPhase('J2', 'EW', 'red');
        break;

      case 'bottleneck':
        this.setSpillbackActive(true, 0.92);
        this.updateSignalPhase('J1', 'NS', 'green');
        this.updateSignalPhase('J1', 'EW', 'yellow');
        this.updateSignalPhase('J2', 'NS', 'green');
        this.updateSignalPhase('J2', 'EW', 'red');
        break;

      case 'emergency':
        // Emergency ambulance corridor
        this.setSpillbackActive(false);
        this.updateSignalPhase('J1', 'NS', 'green');
        this.updateSignalPhase('J1', 'EW', 'red');
        this.updateSignalPhase('J2', 'NS', 'green');
        this.updateSignalPhase('J2', 'EW', 'red');
        // J2 flushes first, then J1 (downstream-first)
        this.spawnAmbulance();
        break;

      case 'sensor_fault':
        // Simulate camera dropout, fallback to fixed-time
        this.updateSignalPhase('J1', 'NS', 'yellow');
        this.updateSignalPhase('J1', 'EW', 'red');
        this.updateSignalPhase('J2', 'NS', 'yellow');
        this.updateSignalPhase('J2', 'EW', 'red');
        break;
    }

    if (this.onScenarioChange) {
      this.onScenarioChange(scenarioName);
    }
  }

  spawnSurgeVehicles() {
    // Add extra vehicles for surge scenario
    for (let i = 0; i < 15; i++) {
      const z = Math.random() * 20 - 10 + J1_POSITION;
      this.addVehicleInstance('car', ROAD_WIDTH / 4 + 1, z, 0, 0, 0, 0.05);
    }
    for (let i = 0; i < 5; i++) {
      const z = Math.random() * 15 + J1_POSITION;
      this.addVehicleInstance('bus', ROAD_WIDTH / 4 + 1, z, 0, 0, 0, 0.04);
    }
  }

  spawnAmbulance() {
    // Add a prominent ambulance (emergency vehicle)
    const geometry = new THREE.BoxGeometry(1.0, 0.6, 2.5);
    const material = new THREE.MeshStandardMaterial({
      color: 0xef4444,
      emissive: 0xef4444,
      emissiveIntensity: 0.5,
    });

    const ambulance = new THREE.Mesh(geometry, material);
    ambulance.position.set(0, 0.5, J1_POSITION - 15);
    ambulance.rotation.y = 0;
    ambulance.userData = { type: 'ambulance', corridorPos: 0 };
    this.scene.add(ambulance);
    this.ambulance = ambulance;

    // Add flashing lights
    const lightGeometry = new THREE.SphereGeometry(0.2, 8, 8);
    const redLight = new THREE.Mesh(lightGeometry, new THREE.MeshBasicMaterial({ color: 0xff0000 }));
    redLight.position.set(-0.5, 0.8, 0);
    ambulance.add(redLight);

    const blueLight = new THREE.Mesh(lightGeometry, new THREE.MeshBasicMaterial({ color: 0x0000ff }));
    blueLight.position.set(0.5, 0.8, 0);
    ambulance.add(blueLight);

    this.ambulanceLights = { red: redLight, blue: blueLight, ambulance };
  }

  updateAmbulance(deltaTime) {
    if (!this.ambulance) return;

    const speed = 0.5 * deltaTime * 60;
    this.ambulance.position.z += speed;

    // Flash lights
    const elapsed = this.clock.getElapsedTime();
    if (this.ambulanceLights) {
      const intensity = Math.abs(Math.sin(elapsed * 10)) * 0.5 + 0.5;
      this.ambulanceLights.red.material.emissiveIntensity = intensity;
      this.ambulanceLights.blue.material.emissiveIntensity = intensity;
    }

    // Check if ambulance reached J2
    if (this.ambulance.position.z > J2_POSITION + 5) {
      this.ambulance = null;
      this.ambulanceLights = null;
      this.setScenario('recovery');
    }
  }

  /* ---- Mode Toggle ---- */

  setMode(mode) {
    this.isQueueSenseMode = mode === 'queuesense';

    // Update scene appearance
    if (this.isQueueSenseMode) {
      // QueueSense: show AI zones, clean traffic flow
      Object.values(this.aiZones).forEach(zone => {
        zone.visible = true;
      });
      this.setSpillbackActive(this.scenario.name === 'spillback' || this.scenario.name === 'bottleneck');
    } else {
      // Traditional: hide AI zones, show gridlock on congested scenarios
      Object.values(this.aiZones).forEach(zone => {
        zone.visible = false;
      });

      if (this.scenario.name === 'spillback' || this.scenario.name === 'bottleneck') {
        this.setGridlockVisualization(true);
      } else {
        this.setGridlockVisualization(false);
      }
    }

    if (this.onModeChange) {
      this.onModeChange(this.isQueueSenseMode);
    }
  }

  setGridlockVisualization(active) {
    // Visual gridlock: red overlay on entire corridor
    const overlayMaterial = active ? this.getGridlockOverlay() : null;

    // Change vehicle speeds
    Object.values(this.vehicleInstances).forEach(instance => {
      if (instance.instances) {
        instance.instances.forEach(v => {
          v.speed = v.speed * (active ? 0.3 : 3);
        });
      }
    });
  }

  getGridlockOverlay() {
    const geometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL, ROAD_WIDTH * 3);
    const material = new THREE.MeshStandardMaterial({
      color: 0x7f1d1d,
      transparent: true,
      opacity: 0.3,
      side: THREE.DoubleSide,
      depthWrite: false,
    });

    const overlay = new THREE.Mesh(geometry, material);
    overlay.rotation.x = -Math.PI / 2;
    overlay.position.y = 0.02;
    this.scene.add(overlay);
    this.gridlockOverlay = overlay;
    return material;
  }

  /* ---- Autonomous Scenario Cycling ---- */

  updateScenarioEngine(deltaTime) {
    this.scenario.time += deltaTime;
    this.scenario.transitionTimer += deltaTime;

    // Auto-cycle scenarios in normal mode (if not manually set)
    if (this.scenario.phase === 'running') {
      const durations = {
        normal: 30,
        surge: 20,
        spillback: 25,
        emergency: 15,
        recovery: 15,
        sensor_fault: 10,
      };

      const duration = durations[this.scenario.name] || 15;

      if (this.scenario.transitionTimer > duration) {
        const nextScenario = this.getNextScenario();
        this.setScenario(nextScenario);
        this.scenario.transitionTimer = 0;
      }
    }

    // Update PCU counts in AI zones
    this.updateZonePCUs();

    // Update signal timing
    this.updateSignalCycle(deltaTime);

    // Flash pedestrian crossing
    this.updatePedestrianFlash(deltaTime);
  }

  getNextScenario() {
    const sequence = ['normal', 'surge', 'spillback', 'emergency', 'recovery', 'normal'];
    const currentIndex = sequence.indexOf(this.scenario.name);
    return sequence[(currentIndex + 1) % sequence.length];
  }

  updateZonePCUs() {
    Object.values(this.aiZones).forEach(zone => {
      const count = Math.floor(Math.random() * 8) + 1;
      zone.userData.pcuCount = count;

      // Update zone opacity based on PCU count
      const material = zone.material;
      const intensity = Math.min(count / 12, 1);
      material.opacity = 0.2 + intensity * 0.3;
      material.emissiveIntensity = 0.3 + intensity * 0.4;
    });

    if (this.onZoneUpdate) {
      this.onZoneUpdate(Object.fromEntries(
        Object.entries(this.aiZones).map(([id, zone]) => [id, zone.userData.pcuCount])
      ));
    }
  }

  updateSignalCycle(deltaTime) {
    // Simulate signal phase timing
    this.signalTime = (this.signalTime || 0) + deltaTime;

    if (this.signalTime > 30) {
      this.signalTime = 0;

      const states = this.signalState;
      for (const jid of Object.keys(states)) {
        const state = states[jid];
        if (state.NS === 'green') {
          this.updateSignalPhase(jid, 'NS', 'yellow', 5);
        } else if (state.NS === 'yellow') {
          this.updateSignalPhase(jid, 'NS', 'red');
          this.updateSignalPhase(jid, 'EW', 'green', 25);
        } else if (state.EW === 'green') {
          this.updateSignalPhase(jid, 'EW', 'yellow', 5);
        } else if (state.EW === 'yellow') {
          this.updateSignalPhase(jid, 'EW', 'red');
          this.updateSignalPhase(jid, 'NS', 'green', 25);
        }
      }
    }
  }

  updatePedestrianFlash(deltaTime) {
    // Flash pedestrian crossing at J2
    const elapsed = this.clock.getElapsedTime();
    if (Math.floor(elapsed) % 2 === 0 && this.pedestrianCrossing) {
      this.pedestrianCrossing.material.emissiveIntensity = Math.abs(Math.sin(elapsed * 3)) * 0.5;
    }
  }

  /* ---- Animation Loop ---- */

  animate() {
    const deltaTime = Math.min(this.clock.getDelta(), 0.1);
    this.frameCount++;

    // Update controls
    if (this.controls && this.controls.enabled) {
      this.controls.update();
    }

    // Update vehicles
    this.updateVehicles(deltaTime);

    // Update ambulance if active
    if (this.ambulance) {
      this.updateAmbulance(deltaTime);
    }

    // Update scenario engine
    this.updateScenarioEngine(deltaTime);

    // Update bloom pass for signal glow
    if (this.bloomPass) {
      this.bloomPass.strength = this.isQueueSenseMode ? 1.2 : 0.6;
    }

    // Render
    if (this.composer) {
      this.composer.render();
    } else {
      this.renderer.render(this.scene, this.camera);
    }

    // Performance telemetry
    if (this.frameCount % 60 === 0 && this.onTelemetry) {
      this.onTelemetry({
        fps: Math.round(1 / deltaTime),
        vehicles: this.getTotalVehicleCount(),
        scenario: this.scenario.name,
        mode: this.isQueueSenseMode ? 'queuesense' : 'traditional',
      });
    }
  }

  getTotalVehicleCount() {
    let total = 0;
    Object.values(this.vehicleInstances).forEach(instance => {
      if (instance.instances) {
        total += instance.instances.length;
      }
    });
    return total;
  }

  /* ---- Event Listeners ---- */

  setupEventListeners() {
    window.addEventListener('resize', () => this.onWindowResize());

    // Expose globally for external control
    window.digitalTwinScene = this;
  }

  onWindowResize() {
    const width = window.innerWidth;
    const height = window.innerHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(window.devicePixelRatio);

    if (this.composer) {
      this.composer.setSize(width, height);
    }
  }

  /* ---- Public API ---- */

  destroy() {
    this.controls?.dispose();
    this.renderer?.dispose();
    this.composer?.dispose();
    this.scene?.clear();

    if (this.container.contains(this.renderer.domElement)) {
      this.container.removeChild(this.renderer.domElement);
    }
  }
}

/* =============================================================================
   INITIALIZATION
   ============================================================================= */

let twinScene = null;

export function initDigitalTwin(canvasContainer) {
  twinScene = new DigitalTwinScene(canvasContainer);

  // Wire up callbacks for external UI updates
  twinScene.onStateUpdate = (state) => {
    if (window.onTwinStateUpdate) {
      window.onTwinStateUpdate(state);
    }
  };

  twinScene.onSignalUpdate = (signal) => {
    if (window.onSignalUpdate) {
      window.onSignalUpdate(signal);
    }
  };

  twinScene.onScenarioChange = (scenario) => {
    if (window.onScenarioChange) {
      window.onScenarioChange(scenario);
    }
  };

  twinScene.onModeChange = (isQueueSense) => {
    if (window.onModeChange) {
      window.onModeChange(isQueueSense);
    }
  };

  twinScene.onZoneUpdate = (zones) => {
    if (window.onZoneUpdate) {
      window.onZoneUpdate(zones);
    }
  };

  twinScene.onTelemetry = (stats) => {
    if (window.onTwinTelemetry) {
      window.onTwinTelemetry(stats);
    }
  };

  return twinScene;
}

export function getTwinScene() {
  return twinScene;
}

export function switchCameraPreset(preset) {
  twinScene?.switchCameraPreset(preset);
}

export function setScenario(scenario) {
  twinScene?.setScenario(scenario);
}

export function setMode(mode) {
  twinScene?.setMode(mode);
}

export function triggerEmergencyFlush() {
  twinScene?.setScenario('emergency');
}

export function setSpillbackActive(active, occupancy = 0.85) {
  twinScene?.setSpillbackActive(active, occupancy);
}

export function updateSignalPhase(junctionId, direction, color, duration = 0) {
  twinScene?.updateSignalPhase(junctionId, direction, color, duration);
}