// QueueSense Dashboard — Three.js 3D Scene Engine
// High-craft architectural traffic diorama: J1 + J2 corridor
// Flat geometry, glowing signals, multi-part vehicles, smooth physics

import * as THREE from 'three';
import { OrbitControls } from 'three/OrbitControls';

// ─── Scene State ──────────────────────────────────────────────
const state = {
  currentMode: 'queuesense',
  currentScenario: 'auto',
  currentCamera: 'isometric',
  autoRunning: true,
  simTime: 0,
  vehicles: [],
  signals: {},
  densityLevel: 50,
  exitBlock: 0,
  emergencyActive: false,
  kpi: { queue: 0, wait: 0, exit: 0 },
  scenarioTimer: 0,
  scenarioStep: 0,
};

// ─── Three.js Core ────────────────────────────────────────────
let scene, camera, renderer, controls, clock, animationId;

// Color palette — high-contrast stone/neutral dark with vibrant signals
const COLORS = {
  ground: 0x0a0c10,
  groundWarm: 0x0d0f14,
  asphalt: 0x1c1f26,
  asphaltDark: 0x15181d,
  asphaltHighlight: 0x22262e,
  curb: 0x2a2e36,
  sidewalk: 0x242830,
  crosswalk: 0xf8f8fa,
  stopLine: 0xfff5e6,
  laneMark: 0xd1d5db,
  signalRed: 0xff2e4c,
  signalAmber: 0xffb800,
  signalGreen: 0x00e676,
  poleMetal: 0x2a2e3a,
  poleGlow: 0x4a505e,
  building: 0x1a1c23,
  buildingDim: 0x14161c,
  treeTrunk: 0x4a3a2a,
  treeFoliage: 0x1a3a2a,
  lampPost: 0x2a2e36,
  lampGlow: 0x4a505e,
};

// ─── Vehicle Definitions (multi-part 3D) ──────────────────────
// Standardize: vehicle front (+length) points along +Z axis locally
// Wheels are placed at ±X positions for left/right side
// Realistic automotive colors: Pearl White, Silver, Slate Grey, Blue, Crimson, Obsidian

function getRealisticVehicleColor(type, isEmergency = false) {
  const colorMap = {
    sedan: 0xf8f8fa,       // Pearl White
    suv: 0xcbd5e1,        // Slate Grey
    truck: 0x64748b,      // Metallic Silver
    bus: isEmergency ? 0xdc2626 : 0x2563eb,  // Crimson (ambulance) or Transit Blue
    auto: 0x15803d,        // Deep Green
    bike: 0xef4444,        // Crimson
    emergency: 0xdc2626,   // Crimson body
  };
  return colorMap[type] || 0x4f96ff;
}

function createVehicle(type, color, x, z, length, width, height) {
  const group = new THREE.Group();
  const isEmergency = (type === 'emergency');
  const paintColor = color !== undefined ? color : getRealisticVehicleColor(type, isEmergency);

  // Body (chassis / main passenger cell) - front points +Z
  const bodyGeom = new THREE.BoxGeometry(length, height * 0.6, width);
  const bodyMat = new THREE.MeshStandardMaterial({
    color: paintColor,
    metalness: 0.8,
    roughness: 0.2,
  });
  const body = new THREE.Mesh(bodyGeom, bodyMat);
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);

  // Realistic cabin with dark tinted windows (opacity 0.7)
  let cabinLength, cabinWidth, roofHeight;
  if (type === 'truck') {
    cabinLength = length * 0.25;
    cabinWidth = width * 0.9;
    roofHeight = height * 0.35;
  } else if (type === 'bus') {
    cabinLength = length * 0.8;
    cabinWidth = width * 0.9;
    roofHeight = height * 0.4;
  } else if (type === 'auto') {
    cabinLength = length * 0.3;
    cabinWidth = width * 0.7;
    roofHeight = height * 0.35;
  } else if (type === 'emergency') {
    cabinLength = length * 0.6;
    cabinWidth = width * 0.9;
    roofHeight = height * 0.4;
  } else {
    cabinLength = length * 0.5;
    cabinWidth = width * 0.85;
    roofHeight = height * 0.4;
  }

  const cabinGeom = new THREE.BoxGeometry(cabinLength, roofHeight, cabinWidth);
  const cabinMat = new THREE.MeshStandardMaterial({
    color: 0x1a1a2e,
    metalness: 0.9,
    roughness: 0.1,
    transparent: true,
    opacity: 0.7,
  });
  const cabin = new THREE.Mesh(cabinGeom, cabinMat);
  cabin.position.y = height * 0.3;
  cabin.castShadow = true;
  cabin.receiveShadow = true;
  group.add(cabin);

  // Wheels (black, with proper left/right placement for forward-facing vehicles)
  const wheelMat = new THREE.MeshStandardMaterial({
    color: 0x111419,
    metalness: 0.9,
    roughness: 0.4,
  });
  const wheelRadius = Math.min(width * 0.12, 0.18);
  const wheelGeom = new THREE.CylinderGeometry(wheelRadius, wheelRadius, width * 0.2, 16);

  let wheelPositions;
  if (type === 'bus') {
    wheelPositions = [
      [-length * 0.5, -height * 0.2, width * 0.35],   // left-front
      [-length * 0.5, -height * 0.2, -width * 0.35],  // left-rear
      [length * 0.5, -height * 0.2, width * 0.35],     // right-front
      [length * 0.5, -height * 0.2, -width * 0.35],    // right-rear
      [-length * 0.48, -height * 0.2, width * 0.35],   // left extra
      [length * 0.48, -height * 0.2, -width * 0.35],  // right extra
    ];
  } else if (type === 'truck') {
    wheelPositions = [
      [-length * 0.6, -height * 0.2, width * 0.35],   // left-front
      [-length * 0.6, -height * 0.2, -width * 0.35],  // left-rear
      [length * 0.6, -height * 0.2, width * 0.35],     // right-front
      [length * 0.6, -height * 0.2, -width * 0.35],    // right-rear
      [-length * 0.55, -height * 0.2, width * 0.35],   // left extra
      [length * 0.55, -height * 0.2, -width * 0.35],  // right extra
      [-length * 0.5, -height * 0.2, width * 0.35],    // middle-left
      [length * 0.5, -height * 0.2, -width * 0.35],   // middle-right
    ];
  } else {
    wheelPositions = [
      [-length * 0.4, -height * 0.2, width * 0.35],   // left-front
      [-length * 0.4, -height * 0.2, -width * 0.35],  // left-rear
      [length * 0.4, -height * 0.2, width * 0.35],     // right-front
      [length * 0.4, -height * 0.2, -width * 0.35],    // right-rear
    ];
  }

  wheelPositions.forEach(pos => {
    const wheel = new THREE.Mesh(wheelGeom, wheelMat);
    wheel.position.set(pos[0], pos[1], pos[2]);
    wheel.rotation.z = Math.PI / 2;
    wheel.castShadow = true;
    wheel.receiveShadow = true;
    group.add(wheel);
  });

  // Headlights (glowing white, front +Z)
  const headlightMat = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    toneMapped: false,
  });
  const headlightGeom = new THREE.BoxGeometry(width * 0.18, height * 0.12, 0.03);
  const hlL = new THREE.Mesh(headlightGeom, headlightMat);
  hlL.position.set(length * 0.48, height * 0.25, width * 0.25);
  hlL.castShadow = true;
  group.add(hlL);
  const hlR = hlL.clone();
  hlR.position.z = -width * 0.25;
  group.add(hlR);

  // Taillights (glowing red, rear -Z)
  const taillightMat = new THREE.MeshBasicMaterial({
    color: 0xef4444,
    toneMapped: false,
  });
  const taillightGeom = new THREE.BoxGeometry(width * 0.2, height * 0.1, 0.03);
  const tlL = new THREE.Mesh(taillightGeom, taillightMat);
  tlL.position.set(-length * 0.48, height * 0.25, width * 0.28);
  tlL.castShadow = true;
  group.add(tlL);
  const tlR = tlL.clone();
  tlR.position.x = -length * 0.48;
  tlR.position.z = -width * 0.28;
  group.add(tlR);

  // Emergency beacon for ambulances (flashing red + blue)
  if (type === 'emergency') {
    const beaconRedGeom = new THREE.SphereGeometry(width * 0.18, 16, 12);
    const beaconRedMat = new THREE.MeshStandardMaterial({
      color: 0xff2e4c,
      emissive: 0xff2e4c,
      emissiveIntensity: 0.8,
      toneMapped: false,
    });
    const beaconR = new THREE.Mesh(beaconRedGeom, beaconRedMat);
    beaconR.position.y = height * 0.85;
    group.add(beaconR);

    const beaconBlueGeom = new THREE.SphereGeometry(width * 0.14, 16, 12);
    const beaconBlueMat = new THREE.MeshStandardMaterial({
      color: 0x00a8ff,
      emissive: 0x00a8ff,
      emissiveIntensity: 0.8,
      toneMapped: false,
    });
    const beaconB = new THREE.Mesh(beaconBlueGeom, beaconBlueMat);
    beaconB.position.y = height * 0.95;
    group.add(beaconB);

    group.userData.beaconRed = beaconR;
    group.userData.beaconBlue = beaconB;
  }

  // Auto-rickshaw canopy (simple conical roof, NOT red cone)
  if (type === 'auto') {
    const canopyGeom = new THREE.ConeGeometry(width * 0.7, height * 0.6, 6);
    const canopyMat = new THREE.MeshStandardMaterial({
      color: 0xe53935,
      metalness: 0.2,
      roughness: 0.6,
    });
    const canopy = new THREE.Mesh(canopyGeom, canopyMat);
    canopy.position.y = height * 0.65;
    canopy.rotation.y = Math.PI / 6;
    canopy.castShadow = true;
    canopy.receiveShadow = true;
    group.add(canopy);
  }

  // Motorcycle: simplified with forward-facing wheels
  if (type === 'bike') {
    const bikeWheelGeom = new THREE.CylinderGeometry(width * 0.15, width * 0.15, width * 0.15, 16);
    const wheelFront = new THREE.Mesh(bikeWheelGeom, wheelMat);
    wheelFront.position.set(length * 0.35, 0, 0);
    wheelFront.rotation.z = Math.PI / 2;
    group.add(wheelFront);
    const wheelRear = wheelFront.clone();
    wheelRear.position.x = -length * 0.35;
    group.add(wheelRear);
  }

  group.position.set(x, 0, z);
  group.userData = {
    type: type,
    color: paintColor,
    speed: 0,
    maxSpeed: 0,
    accel: 0,
    deceleration: 0,
    targetSpeed: 0,
    pathIndex: 0,
    pathPoints: [],
    stopAt: Infinity,
    stopped: false,
  };

  return group;
}

// ─── Signal Group (glowing traffic lights on cantilever gantry) ──
function createSignalGroup(name, x, z, axis) {
  const group = new THREE.Group();

  // Pole — thicker, more substantial
  const poleMat = new THREE.MeshStandardMaterial({
    color: COLORS.poleMetal,
    metalness: 0.6,
    roughness: 0.7,
  });

  const poleGeom = new THREE.CylinderGeometry(0.2, 0.25, 6.0, 16);
  const pole = new THREE.Mesh(poleGeom, poleMat);
  pole.castShadow = true;
  pole.receiveShadow = true;
  group.add(pole);

  // Cantilever arm (horizontal gantry)
  const armLength = 3.0;
  const armGeom = new THREE.BoxGeometry(axis === 'ns' ? armLength : armLength, 0.2, 0.25);
  const arm = new THREE.Mesh(armGeom, poleMat);
  arm.position.y = 5.0;
  arm.castShadow = true;
  arm.receiveShadow = true;
  if (axis === 'ns') {
    arm.position.z = -armLength / 2;
  } else {
    arm.position.x = armLength / 2;
  }
  group.add(arm);

  // Signal housing box (vertical, facing traffic)
  const housingGeom = new THREE.BoxGeometry(0.5, 1.4, 0.35);
  const housingMat = new THREE.MeshStandardMaterial({
    color: 0x0e1013,
    metalness: 0.2,
    roughness: 0.4,
  });
  const housing = new THREE.Mesh(housingGeom, housingMat);
  housing.position.y = 5.0;
  housing.castShadow = true;
  housing.receiveShadow = true;
  if (axis === 'ns') {
    housing.position.z = -armLength;
  } else {
    housing.position.x = armLength;
  }
  group.add(housing);

  // Three signal bulbs on the housing
  const bulbPositions = [
    { y: 5.35, color: COLORS.signalRed, key: 'red' },
    { y: 5.0, color: COLORS.signalAmber, key: 'amber' },
    { y: 4.65, color: COLORS.signalGreen, key: 'green' },
  ];

  bulbPositions.forEach(bp => {
    const bulbGeom = new THREE.SphereGeometry(0.14, 20, 14);
    const bulbMat = new THREE.MeshStandardMaterial({
      color: bp.color,
      emissive: bp.color,
      emissiveIntensity: 0,
      toneMapped: false,
    });
    const bulb = new THREE.Mesh(bulbGeom, bulbMat);
    bulb.position.y = bp.y;
    if (axis === 'ns') {
      bulb.position.z = housing.position.z;
    } else {
      bulb.position.x = housing.position.x;
    }
    group.add(bulb);

    group.userData[bp.key] = bulb;
    group.userData[bp.key + 'Color'] = bp.color;
  });

  group.position.set(x, 0, z);
  group.userData.activeLight = 'red';
  group.userData.name = name;

  return group;
}

// ─── Ground Stop-Line Bars (glowing ground indicators) ─────────
function createGroundStopBars(axis, distance, color, count, spacing) {
  const group = new THREE.Group();
  const barMat = new THREE.MeshStandardMaterial({
    color: color,
    emissive: color,
    emissiveIntensity: 0,
    toneMapped: false,
  });
  const barWidth = 0.3;
  const barThickness = 0.08;
  const barLength = axis === 'ns' ? 8.0 : 6.0;
  const barGeom = new THREE.BoxGeometry(barWidth, barThickness, barLength);

  for (let i = 0; i < count; i++) {
    const bar = new THREE.Mesh(barGeom, barMat.clone());
    bar.position.y = 0.05;
    if (axis === 'ns') {
      bar.position.z = distance;
      bar.position.x = (i - (count - 1) / 2) * spacing;
    } else {
      bar.position.x = distance;
      bar.position.z = (i - (count - 1) / 2) * spacing;
    }
    group.add(bar);
  }

  group.userData.bars = group.children;
  group.userData.color = color;
  group.userData.intensity = 0;
  return group;
}

// ─── Street Lamp ──────────────────────────────────────────────
function createStreetLamp(x, z) {
  const group = new THREE.Group();

  const poleMat = new THREE.MeshStandardMaterial({
    color: COLORS.lampPost,
    metalness: 0.7,
    roughness: 0.8,
  });

  // Thin pole
  const poleGeom = new THREE.CylinderGeometry(0.06, 0.06, 8.0, 8);
  const pole = new THREE.Mesh(poleGeom, poleMat);
  pole.castShadow = true;
  pole.receiveShadow = true;
  group.add(pole);

  // Arm extending horizontally
  const armGeom = new THREE.BoxGeometry(2.0, 0.1, 0.1);
  const arm = new THREE.Mesh(armGeom, poleMat);
  arm.position.y = 7.5;
  arm.position.z = -1.0;
  arm.castShadow = true;
  arm.receiveShadow = true;
  group.add(arm);

  // Glowing lamp - use MeshStandardMaterial with emissive for proper glow
  const lampGeom = new THREE.SphereGeometry(0.3, 16, 12);
  const lampMat = new THREE.MeshStandardMaterial({
    color: 0xffeb3b,
    emissive: 0xffeb3b,
    emissiveIntensity: 1.5,
    toneMapped: false,
  });
  const lamp = new THREE.Mesh(lampGeom, lampMat);
  lamp.position.y = 7.5;
  lamp.position.z = -1.5;
  group.add(lamp);

  // Point light
  const plight = new THREE.PointLight(0xffeb3b, 0.8, 20);
  plight.position.y = 7.5;
  plight.position.z = -1.5;
  group.add(plight);

  group.position.set(x, 0, z);
  scene.add(group);
  return group;
}

// ─── Building Massing ─────────────────────────────────────────
function createBuilding(x, z, width, depth, height, color) {
  // Skip buildings in road zones to avoid visual artifacts
  const roadWidth = 8.0;
  const j2Distance = 30;
  const exclusionBuffer = 3.0;

  // Check if position is within road exclusion zones
  const isInRoadZone = (
    Math.abs(z) <= roadWidth / 2 + exclusionBuffer ||
    Math.abs(x) <= roadWidth / 2 + exclusionBuffer ||
    Math.abs(z - j2Distance) <= roadWidth / 2 + exclusionBuffer
  );

  if (isInRoadZone) {
    return null; // Skip buildings in road zones
  }

  const geom = new THREE.BoxGeometry(width, height, depth);
  const mat = new THREE.MeshStandardMaterial({
    color: color || COLORS.building,
    metalness: 0.0,
    roughness: 0.95,
  });
  const mesh = new THREE.Mesh(geom, mat);
  mesh.position.set(x, height / 2, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);
  return mesh;
}

// Helper function to filter building positions and avoid road zones
function filterBuildingPositions(buildings) {
  const roadWidth = 8.0;
  const j2Distance = 30;
  const exclusionBuffer = 3.0;

  return buildings.filter(b => {
    const isInRoadZone = (
      Math.abs(b.z) <= roadWidth / 2 + exclusionBuffer ||
      Math.abs(b.x) <= roadWidth / 2 + exclusionBuffer ||
      Math.abs(b.z - j2Distance) <= roadWidth / 2 + exclusionBuffer ||
      Math.abs(b.z + j2Distance) <= roadWidth / 2 + exclusionBuffer
    );

    if (isInRoadZone) {
      console.log(`Building skipped at position: x=${b.x}, z=${b.z} (in road exclusion zone)`);
      return false;
    }
    return true;
  });
}

// ─── Tree ─────────────────────────────────────────────────────
function createTree(x, z, scaleFactor) {
  const group = new THREE.Group();
  const s = scaleFactor || 1.0;

  // Road exclusion zone check: keep trees out of road surface only
  // Road is 8 units wide (±4 from center), sidewalk starts at ±6.5
  // Use buffer of 3 units from road edge = 7 units from center
  const roadWidth = 8.0;
  const j2Distance = 30;
  const exclusionBuffer = 3.0; // Buffer from road edge

  // Check if position is within road surface + small buffer
  const roadEdge = roadWidth / 2 + exclusionBuffer; // 4 + 3 = 7 units from center
  const isInRoadZone = (
    Math.abs(z) <= roadEdge || // Near NS road
    Math.abs(x) <= roadEdge || // Near EW road
    Math.abs(z - j2Distance) <= roadEdge || // Near J2 road
    Math.abs(z + j2Distance) <= roadEdge   // Near J2 road
  );

  if (isInRoadZone) {
    return null; // Skip trees in road zones
  }

  // Trunk
  const trunkGeom = new THREE.CylinderGeometry(0.15 * s, 0.25 * s, 1.2 * s, 8);
  const trunkMat = new THREE.MeshStandardMaterial({ color: COLORS.treeTrunk });
  const trunk = new THREE.Mesh(trunkGeom, trunkMat);
  trunk.position.y = 0.6 * s;
  trunk.castShadow = true;
  trunk.receiveShadow = true;
  group.add(trunk);

  // Foliage layers
  const foliageMat = new THREE.MeshStandardMaterial({ color: COLORS.treeFoliage });
  for (let i = 0; i < 3; i++) {
    const fy = 1.0 * s + i * 0.6 * s;
    const fr = 1.0 * s - i * 0.2 * s;
    const fgeom = new THREE.ConeGeometry(fr, 1.2 * s, 8);
    const fmesh = new THREE.Mesh(fgeom, foliageMat);
    fmesh.position.y = fy;
    fmesh.castShadow = true;
    fmesh.receiveShadow = true;
    group.add(fmesh);
  }

  group.position.set(x, 0, z);
  scene.add(group);
  return group;
}

// ─── Build the Intersection ───────────────────────────────────
function buildIntersection() {
  const roadWidthNS = 8.0;
  const roadWidthEW = 8.0;
  const roadLength = 64;
  const sidewalkWidth = 5.0;

  // ─── Ground Plane (architectural studio base) ──────────────
  const groundGeom = new THREE.PlaneGeometry(140, 140);
  const groundMat = new THREE.MeshStandardMaterial({
    color: COLORS.ground,
    metalness: 0.0,
    roughness: 0.9,
  });
  const ground = new THREE.Mesh(groundGeom, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // ─── Road Surfaces (all flat, deep charcoal asphalt) ─────────
  const roadMatNS = new THREE.MeshStandardMaterial({
    color: COLORS.asphalt,
    metalness: 0.0,
    roughness: 0.95,
  });

  // North-South road (J1 to J2 corridor)
  const roadGeomNS = new THREE.PlaneGeometry(roadWidthNS, roadLength * 2);
  const roadNS = new THREE.Mesh(roadGeomNS, roadMatNS);
  roadNS.rotation.x = -Math.PI / 2;
  roadNS.position.y = 0.01;
  roadNS.position.set(0, 0.01, 0);
  roadNS.receiveShadow = true;
  scene.add(roadNS);

  // East-West road
  const roadGeomEW = new THREE.PlaneGeometry(roadWidthEW, roadLength);
  const roadEW = new THREE.Mesh(roadGeomEW, roadMatNS);
  roadEW.rotation.x = -Math.PI / 2;
  roadEW.position.y = 0.01;
  roadEW.receiveShadow = true;
  scene.add(roadEW);

  // ─── Sidewalks (high-contrast, raised curbs) ────────────────
  function createSidewalkSlab(x, z, width, length, color) {
    const geom = new THREE.PlaneGeometry(width, length);
    const mat = new THREE.MeshStandardMaterial({
      color: color || COLORS.sidewalk,
      metalness: 0.05,
      roughness: 0.9,
    });
    const mesh = new THREE.Mesh(geom, mat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(x, 0.02, z);
    mesh.receiveShadow = true;
    scene.add(mesh);

    // Curb strip
    const curbGeom = new THREE.BoxGeometry(width, 0.15, 0.3);
    const curbMat = new THREE.MeshStandardMaterial({
      color: COLORS.curb,
      metalness: 0.1,
      roughness: 0.8,
    });
    const curb = new THREE.Mesh(curbGeom, curbMat);
    curb.position.set(x, 0.15 / 2, z);
    curb.castShadow = true;
    curb.receiveShadow = true;
    scene.add(curb);
    return mesh;
  }

  // 8 sidewalk slabs
  createSidewalkSlab(roadWidthNS / 2 + sidewalkWidth / 2, 0, sidewalkWidth, roadLength * 2);
  createSidewalkSlab(-roadWidthNS / 2 - sidewalkWidth / 2, 0, sidewalkWidth, roadLength * 2);
  createSidewalkSlab(0, roadWidthEW / 2 + sidewalkWidth / 2, roadLength, sidewalkWidth);
  createSidewalkSlab(0, -roadWidthEW / 2 - sidewalkWidth / 2, roadLength, sidewalkWidth);

  // ─── Lane Markings (white dashed) ────────────────────────────
  const laneMarkMat = new THREE.MeshStandardMaterial({
    color: COLORS.laneMark,
    metalness: 0.0,
    roughness: 0.5,
    side: THREE.DoubleSide,
  });

  function createDashedLineNS(startZ, length, segments, gap) {
    const group = new THREE.Group();
    const segLen = (length - (segments - 1) * gap) / segments;
    const geom = new THREE.PlaneGeometry(0.12, segLen);
    for (let i = 0; i < segments; i++) {
      const mesh = new THREE.Mesh(geom, laneMarkMat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(0, 0.03, startZ + i * (segLen + gap));
      group.add(mesh);
    }
    scene.add(group);
    return group;
  }

  function createDashedLineEW(startX, length, segments, gap) {
    const group = new THREE.Group();
    const segLen = (length - (segments - 1) * gap) / segments;
    const geom = new THREE.PlaneGeometry(segLen, 0.12);
    for (let i = 0; i < segments; i++) {
      const mesh = new THREE.Mesh(geom, laneMarkMat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(startX + i * (segLen + gap), 0.03, 0);
      group.add(mesh);
    }
    scene.add(group);
    return group;
  }

  // Center lines
  createDashedLineNS(-roadLength, roadLength * 4, 40, 0.4);
  createDashedLineEW(-roadLength, roadLength * 2, 30, 0.4);

  // ─── Zebra Crosswalks (flat, crisp white stripes) ────────────
  function createZebraCrosswalk(centerX, centerZ, rotationY, stripes, length, width) {
    const group = new THREE.Group();
    const stripeMat = new THREE.MeshStandardMaterial({
      color: COLORS.crosswalk,
      metalness: 0.0,
      roughness: 0.6,
      side: THREE.DoubleSide,
    });
    const stripeWidth = length / stripes;

    for (let i = 0; i < stripes; i++) {
      const geom = new THREE.PlaneGeometry(stripeWidth, width);
      const stripe = new THREE.Mesh(geom, stripeMat);
      stripe.rotation.x = -Math.PI / 2;
      stripe.rotation.y = rotationY;
      stripe.position.y = 0.04;
      const offset = -length / 2 + stripeWidth / 2 + i * stripeWidth;
      if (rotationY === 0) {
        stripe.position.set(centerX + offset, 0.04, centerZ);
      } else {
        stripe.position.set(centerX, 0.04, centerZ + offset);
      }
      group.add(stripe);
    }
    scene.add(group);
    return group;
  }

  // 4 zebra crosswalks
  const cwLength = roadWidthNS;
  const cwWidth = 2.5;
  createZebraCrosswalk(0, roadWidthEW / 2 + 0.8, 0, 16, cwLength, cwWidth);
  createZebraCrosswalk(0, -roadWidthEW / 2 - 0.8, Math.PI, cwLength, cwWidth);
  createZebraCrosswalk(roadWidthNS / 2 + 0.8, 0, Math.PI / 2, cwLength, cwWidth);
  createZebraCrosswalk(-roadWidthNS / 2 - 0.8, 0, -Math.PI / 2, cwLength, cwWidth);

  // ─── Stop Lines with Glowing Ground Bars ─────────────────────
  state.signals.stopBars = {};
  const stopBarDist = roadWidthEW / 2 - 0.2;

  // North stop bar
  const stopBarNS_N = createGroundStopBars('ns', roadWidthEW / 2 - 0.4, COLORS.signalGreen, 3, 2.0);
  state.signals.stopBars.north = stopBarNS_N;
  scene.add(stopBarNS_N);

  // South stop bar
  const stopBarNS_S = createGroundStopBars('ns', -roadWidthEW / 2 + 0.4, COLORS.signalGreen, 3, 2.0);
  state.signals.stopBars.south = stopBarNS_S;
  scene.add(stopBarNS_S);

  // East stop bar
  const stopBarEW_E = createGroundStopBars('ew', roadWidthNS / 2 - 0.4, COLORS.signalGreen, 3, 2.0);
  state.signals.stopBars.east = stopBarEW_E;
  scene.add(stopBarEW_E);

  // West stop bar
  const stopBarEW_W = createGroundStopBars('ew', -roadWidthNS / 2 + 0.4, COLORS.signalGreen, 3, 2.0);
  state.signals.stopBars.west = stopBarEW_W;
  scene.add(stopBarEW_W);

  // ─── Cantilever Traffic Signal Gantries ──────────────────────
  state.signals.groups = {};

  const gap = 2.0;
  const sigN = createSignalGroup('north', 0, -roadWidthEW / 2 - gap, 'ns');
  scene.add(sigN);
  state.signals.groups.north = sigN;

  const sigS = createSignalGroup('south', 0, roadWidthEW / 2 + gap, 'ns');
  scene.add(sigS);
  state.signals.groups.south = sigS;

  const sigE = createSignalGroup('east', roadWidthNS / 2 + gap, 0, 'ew');
  scene.add(sigE);
  state.signals.groups.east = sigE;

  const sigW = createSignalGroup('west', -roadWidthNS / 2 - gap, 0, 'ew');
  scene.add(sigW);
  state.signals.groups.west = sigW;

  // ─── Junction 2 (downstream) ─────────────────────────────────
  const j2Distance = 30;

  const roadJ2 = new THREE.Mesh(roadGeomNS.clone(), roadMatNS.clone());
  roadJ2.rotation.x = -Math.PI / 2;
  roadJ2.position.set(0, 0.01, j2Distance);
  roadJ2.receiveShadow = true;
  scene.add(roadJ2);

  // J2 sidewalks
  createSidewalkSlab(roadWidthNS / 2 + sidewalkWidth / 2, j2Distance, sidewalkWidth, roadLength);
  createSidewalkSlab(-roadWidthNS / 2 - sidewalkWidth / 2, j2Distance, sidewalkWidth, roadLength);

  // J2 signals
  const sigJ2_N = createSignalGroup('j2_north', 0, j2Distance - roadWidthEW / 2 - gap, 'ns');
  scene.add(sigJ2_N);
  state.signals.groups.j2_north = sigJ2_N;

  const sigJ2_S = createSignalGroup('j2_south', 0, j2Distance + roadWidthEW / 2 + gap, 'ns');
  scene.add(sigJ2_S);
  state.signals.groups.j2_south = sigJ2_S;

  // J2 stop bars — track with upstream NS phase
  const j2StopBars = {};
  const j2StopBarNear = createGroundStopBars('ns', j2Distance - roadWidthEW / 2 + 0.4, COLORS.signalGreen, 2, 2.0);
  const j2StopBarFar = createGroundStopBars('ns', j2Distance + roadWidthEW / 2 - 0.4, COLORS.signalGreen, 2, 2.0);
  scene.add(j2StopBarNear);
  scene.add(j2StopBarFar);
  j2StopBars.north = j2StopBarNear;
  j2StopBars.south = j2StopBarFar;
  state.signals.stopBars.j2 = j2StopBars;

  // Downstream sensor zone at J2 (architectural visualization)
  const sensorGeom = new THREE.RingGeometry(4.0, 4.5, 32);
  const sensorMat = new THREE.MeshStandardMaterial({
    color: 0x156932, // Deep green (replaces neon 0x00e676)
    emissive: 0x1e7e34, // Subtle glow (replaces neon 0x00e676)
    emissiveIntensity: 0.15, // Reduced glow (replaces 0.3)
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.4, // Reduced opacity (replaces 0.7)
    toneMapped: false,
  });
  const sensorRing = new THREE.Mesh(sensorGeom, sensorMat);
  sensorRing.rotation.x = -Math.PI / 2;
  sensorRing.position.y = 0.1;
  sensorRing.position.z = j2Distance;
  scene.add(sensorRing);
  state.signals.downstreamSensor = sensorRing;

  // ─── Surrounding Buildings & Trees ──────────────────────────
  const buildings = [
    { x: -20, z: -25, w: 8, d: 12, h: 12, c: COLORS.buildingDim },
    { x: 20, z: -25, w: 6, d: 10, h: 10, c: COLORS.buildingDim },
    { x: -22, z: 38, w: 8, d: 8, h: 8, c: COLORS.building },
    { x: 18, z: 38, w: 10, d: 6, h: 11, c: COLORS.buildingDim },
    { x: -25, z: 45, w: 6, d: 14, h: 9, c: COLORS.building },
    { x: 25, z: 45, w: 7, d: 10, h: 7, c: COLORS.buildingDim },
    { x: -15, z: 50, w: 10, d: 8, h: 14, c: COLORS.building },
  ];

  // Filter out buildings in road zones before creating them
  const filteredBuildings = buildings.filter(b => {
    const isInRoadZone = (
      Math.abs(b.z) <= 4 + 3.0 || // Near NS road (J1 at z=0)
      Math.abs(b.x) <= 4 + 3.0 || // Near EW road (J1 at x=0)
      Math.abs(b.z - 30) <= 4 + 3.0 // Near J2 road (J2 at z=30)
    );

    if (isInRoadZone) {
      console.log(`Building skipped at position: x=${b.x}, z=${b.z} (in road exclusion zone)`);
      return false;
    }
    return true;
  });

  filteredBuildings.forEach(b => createBuilding(b.x, b.z, b.w, b.d, b.h, b.c));

  const treePositions = [
    [-10, -12], [10, -12], [-10, -35], [10, -35],
    [-12, -28], [12, -28], [-10, 12], [10, 12],
    [-12, 35], [12, 35], [-8, 50], [8, 50],
    [8, -45], [-8, -45], [-15, -20], [15, -20],
  ];
  treePositions.forEach(p => {
    const tree = createTree(p[0], p[1], 1.0 + Math.random() * 0.5);
    if (tree) {
      console.log(`Tree created at position: x=${p[0]}, z=${p[1]}`);
    } else {
      console.log(`Tree skipped at position: x=${p[0]}, z=${p[1]} (in road exclusion zone)`);
    }
  });

  // Street lamps
  const lampPositions = [
    [roadWidthNS / 2 + 1, 0], [-roadWidthNS / 2 - 1, 0],
    [0, roadWidthEW / 2 + 1], [0, -roadWidthEW / 2 - 1],
    [roadWidthNS / 2 + 1, j2Distance], [-roadWidthNS / 2 - 1, j2Distance],
  ];
  lampPositions.forEach(p => createStreetLamp(p[0], p[1]));

  // ─── Ambient & Lighting ──────────────────────────────────────
  const ambient = new THREE.AmbientLight(0x404060, 1.8);
  scene.add(ambient);

  const dirLight = new THREE.DirectionalLight(0xffffff, 2.2);
  dirLight.position.set(30, 50, 25);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.width = 4096;
  dirLight.shadow.mapSize.height = 4096;
  dirLight.shadow.camera.near = 0.5;
  dirLight.shadow.camera.far = 120;
  dirLight.shadow.camera.left = -50;
  dirLight.shadow.camera.right = 50;
  dirLight.shadow.camera.top = 50;
  dirLight.shadow.camera.bottom = -50;
  scene.add(dirLight);
}

// ─── Vehicle Spawning & Physics ─────────────────────────────
const VEHICLE_LENGTHS = {
  sedan: { l: 4.2, w: 1.8, h: 1.5 },
  suv: { l: 4.8, w: 2.0, h: 1.7 },
  truck: { l: 7.5, w: 2.4, h: 2.2 },
  bus: { l: 10.0, w: 2.6, h: 3.0 },
  auto: { l: 2.8, w: 1.0, h: 1.5 },
  bike: { l: 1.9, w: 0.8, h: 1.3 },
  emergency: { l: 6.5, w: 2.2, h: 2.4 },
};

function spawnVehicle(axis, direction, forceType) {
  const roadW = 8.0;
  const laneWidth = roadW / 2;

  let x, z, rotY;
  // Position vehicles in proper lanes (centered in lane)
  if (axis === 'ns') {
    // Northbound lane: from south to north, middle of road width
    x = 0;
    z = -32;
    rotY = 0; // facing north (+Z)
  } else {
    // Eastbound lane: from west to east, middle of road width
    x = -32;
    z = 0;
    rotY = Math.PI / 2; // facing east (+X)
  }

  let t;
  if (forceType) {
    t = forceType;
  } else {
    const types = ['sedan', 'sedan', 'sedan', 'suv', 'truck', 'bus', 'auto', 'bike'];
    t = types[Math.floor(Math.random() * types.length)];
  }

  const colors = [0xf8f8fa, 0x64748b, 0xdc2626, 0x15803d, 0xef4444, 0x2563eb, 0xb197ff];
  const paintColor = colors[Math.floor(Math.random() * colors.length)];

  const dims = VEHICLE_LENGTHS[t];
  const vehicle = createVehicle(t, paintColor, x, z, dims.l, dims.w, dims.h);
  vehicle.rotation.y = rotY;
  vehicle.userData.speed = 0;
  const isHeavy = t === 'truck' || t === 'bus' || t === 'emergency';
  vehicle.userData.maxSpeed = isHeavy ? 8 + Math.random() * 4 : 12 + Math.random() * 6;
  vehicle.userData.accel = isHeavy ? 1.5 : 2.5;
  vehicle.userData.deceleration = t === 'bike' ? 4.0 : 5.5;
  vehicle.userData.targetSpeed = vehicle.userData.maxSpeed;
  vehicle.userData.axis = axis;
  vehicle.userData.direction = direction;
  vehicle.userData.vehicleType = t;

  // Build smooth curved path
  const pathPoints = buildVehiclePath(axis, direction);
  vehicle.userData.pathPoints = pathPoints;
  vehicle.userData.pathIndex = 0;

  scene.add(vehicle);
  state.vehicles.push(vehicle);
  vehicle.name = `vehicle_${state.vehicles.length}`;

  return vehicle;
}

function buildVehiclePath(axis, direction) {
  const points = [];
  const roadW = 4.0;
  const curveRadius = 3.0;
  const pathLength = 40;

  if (axis === 'ns' && direction === 'N') {
    // From south, going north, slight right lane bias
    for (let i = 0; i <= 30; i++) {
      const t = i / 30;
      const z = -30 + t * 60;
      let x = -roadW + Math.sin(t * Math.PI) * 0.3;
      points.push(new THREE.Vector3(x, 0, z));
    }
  } else if (axis === 'ns' && direction === 'S') {
    for (let i = 0; i <= 30; i++) {
      const t = i / 30;
      const z = 30 - t * 60;
      let x = roadW - Math.sin(t * Math.PI) * 0.3;
      points.push(new THREE.Vector3(x, 0, z));
    }
  } else if (axis === 'ew' && direction === 'E') {
    for (let i = 0; i <= 30; i++) {
      const t = i / 30;
      const x = -30 + t * 60;
      let z = -roadW + Math.sin(t * Math.PI) * 0.3;
      points.push(new THREE.Vector3(x, 0, z));
    }
  } else {
    // EW, direction W
    for (let i = 0; i <= 30; i++) {
      const t = i / 30;
      const x = 30 - t * 60;
      let z = roadW - Math.sin(t * Math.PI) * 0.3;
      points.push(new THREE.Vector3(x, 0, z));
    }
  }

  return points;
}

// ─── Physics Update Loop ────────────────────────────────────
function updateVehicles(delta) {
  const stopThreshold = 0.5;

  state.vehicles.forEach((vehicle, idx) => {
    const signalKey = getSignalKeyForVehicle(vehicle);
    const stopPos = getStopPosition(vehicle, signalKey);
    const distToStop = distanceToPosition(vehicle.position, stopPos, vehicle.userData.axis);

    // Check downstream blockage at J2
    const downstreamBlock = state.exitBlock > 60 && vehicle.userData.direction === 'N';

    const signalGreen = isSignalGreen(signalKey) && !downstreamBlock;

    if (distToStop < stopThreshold && !signalGreen) {
      vehicle.userData.targetSpeed = 0;
      vehicle.userData.stopped = true;
    } else if (distToStop < 5 && !signalGreen) {
      vehicle.userData.targetSpeed = Math.max(vehicle.userData.targetSpeed * 0.6, 0);
      vehicle.userData.stopped = vehicle.userData.targetSpeed < 0.2;
    } else {
      vehicle.userData.stopped = false;
      vehicle.userData.targetSpeed = vehicle.userData.maxSpeed;
    }

    // Smooth acceleration/deceleration (car-following)
    const speedDiff = vehicle.userData.targetSpeed - vehicle.userData.speed;
    const accelRate = vehicle.userData.accel;
    const decelRate = vehicle.userData.deceleration;

    let accel = 0;
    if (speedDiff > 0) {
      accel = Math.min(speedDiff * 0.1, accelRate);
    } else if (speedDiff < 0) {
      accel = Math.max(speedDiff * 0.1, -decelRate);
    }

    vehicle.userData.speed += accel * delta;
    if (vehicle.userData.speed < 0) vehicle.userData.speed = 0;

    // Move vehicle along path
    if (vehicle.userData.speed > 0.001 || !vehicle.userData.stopped) {
      const moveDist = vehicle.userData.speed * delta;
      vehicle.userData.pathIndex += moveDist / 2.5;

      if (vehicle.userData.pathIndex >= vehicle.userData.pathPoints.length - 1) {
        // Respawn at start
        vehicle.userData.pathIndex = 0;
        const roadW = 4.0;
        if (vehicle.userData.direction === 'N') {
          vehicle.position.set(-roadW, 0, -32);
        } else if (vehicle.userData.direction === 'S') {
          vehicle.position.set(roadW, 0, 32);
        } else if (vehicle.userData.direction === 'E') {
          vehicle.position.set(-32, 0, -roadW);
        } else {
          vehicle.position.set(32, 0, roadW);
        }
        return;
      }

      const targetPoint = vehicle.userData.pathPoints[
        Math.min(Math.floor(vehicle.userData.pathIndex), vehicle.userData.pathPoints.length - 1)
      ];
      vehicle.position.lerp(targetPoint, 0.05);
    }

    // Emergency beacon flash
    if (vehicle.userData.type === 'emergency') {
      const sin = Math.sin(state.simTime * 12);
      if (vehicle.userData.beaconRed) {
        vehicle.userData.beaconRed.material.emissiveIntensity = sin > 0 ? 0.9 : 0.1;
      }
      if (vehicle.userData.beaconBlue) {
        vehicle.userData.beaconBlue.material.emissiveIntensity = sin < 0 ? 0.9 : 0.1;
      }
    }
  });

  // Remove old vehicles
  if (state.vehicles.length > 40) {
    const excess = state.vehicles.splice(0, state.vehicles.length - 40);
    excess.forEach(v => scene.remove(v));
  }
}

function getSignalKeyForVehicle(vehicle) {
  const d = vehicle.userData.direction;
  if (d === 'N') return 'north';
  if (d === 'S') return 'south';
  if (d === 'E') return 'east';
  return 'west';
}

function getStopPosition(vehicle, signalKey) {
  const roadW = 8.0;
  const stopDist = roadW / 2 - 0.4;
  switch (signalKey) {
    case 'north': return { z: stopDist, x: vehicle.position.x };
    case 'south': return { z: -stopDist, x: vehicle.position.x };
    case 'east': return { x: stopDist, z: vehicle.position.z };
    case 'west': return { x: -stopDist, z: vehicle.position.z };
    default: return { x: 0, z: 0 };
  }
}

function distanceToPosition(pos, stop, axis) {
  if (axis === 'ns') {
    return Math.abs(pos.z - stop.z);
  } else {
    return Math.abs(pos.x - stop.x);
  }
}

function isSignalGreen(signalKey) {
  const group = state.signals.groups[signalKey];
  if (!group) return true;
  return group.userData.activeLight === 'green';
}

// ─── Signal Control ─────────────────────────────────────────
let signalPhase = 0;
let signalTimer = 0;
const SIGNAL_CYCLE = {
  ns_green: 25,
  ns_yellow: 4,
  all_red: 2,
  ew_green: 25,
  ew_yellow: 4,
};

function updateSignals(delta) {
  signalTimer += delta;

  if (state.currentMode === 'queuesense') {
    // QueueSense: adaptive timing based on density + spillback
    const densityFactor = state.densityLevel / 50;
    const downstreamBlocked = state.exitBlock > 70;

    let nsGreen = SIGNAL_CYCLE.ns_green * (0.8 + densityFactor * 0.5);
    let ewGreen = SIGNAL_CYCLE.ew_green * (0.8 + densityFactor * 0.4);

    if (downstreamBlocked) {
      nsGreen = 30;  // Extend NS green to clear upstream
      ewGreen = 5;   // Hold EW red longer to prevent spillback
    }

    if (signalPhase === 0 && signalTimer > nsGreen) setSignalPhase(1);
    else if (signalPhase === 1 && signalTimer > SIGNAL_CYCLE.ns_yellow) setSignalPhase(2);
    else if (signalPhase === 2 && signalTimer > SIGNAL_CYCLE.all_red) setSignalPhase(3);
    else if (signalPhase === 3 && signalTimer > ewGreen) setSignalPhase(4);
    else if (signalPhase === 4 && signalTimer > SIGNAL_CYCLE.ew_yellow) { setSignalPhase(0); signalTimer = 0; }
  } else {
    // Traditional fixed-time
    const cycle = SIGNAL_CYCLE;
    if (signalPhase === 0 && signalTimer > cycle.ns_green) setSignalPhase(1);
    else if (signalPhase === 1 && signalTimer > cycle.ns_yellow) setSignalPhase(2);
    else if (signalPhase === 2 && signalTimer > cycle.all_red) setSignalPhase(3);
    else if (signalPhase === 3 && signalTimer > cycle.ew_green) setSignalPhase(4);
    else if (signalPhase === 4 && signalTimer > cycle.ew_yellow) { setSignalPhase(0); signalTimer = 0; }
  }
}

function setSignalPhase(phase) {
  if (phase === signalPhase) return;
  signalPhase = phase;
  signalTimer = 0;

  // NS = north/south/j2, EW = east/west
  const nsKeys = ['north', 'south', 'j2_north', 'j2_south'];
  const ewKeys = ['east', 'west'];

  nsKeys.forEach(key => {
    const group = state.signals.groups[key];
    if (!group) return;
    if (key.includes('j2')) {
      // J2 signals follow main NS
    }
    if (phase === 0) setBulb(group, 'green');
    else if (phase === 1) setBulb(group, 'amber');
    else if (phase === 2 || phase === 4) setBulb(group, 'red');
    else if (phase === 3) setBulb(group, 'green');
  });

  ewKeys.forEach(key => {
    const group = state.signals.groups[key];
    if (!group) return;
    if (phase === 0 || phase === 1 || phase === 2) setBulb(group, 'red');
    else if (phase === 3) setBulb(group, 'green');
    else if (phase === 4) setBulb(group, 'amber');
  });

  updateGroundStopBars(phase);
  updateAISpeech(phase);
}

function setBulb(group, colorKey) {
  group.userData.activeLight = colorKey;

  const r = group.userData.red;
  const a = group.userData.amber;
  const g = group.userData.green;

  if (r) r.material.emissiveIntensity = colorKey === 'red' ? 1.0 : 0;
  if (a) a.material.emissiveIntensity = colorKey === 'amber' ? 1.0 : 0;
  if (g) g.material.emissiveIntensity = colorKey === 'green' ? 1.0 : 0;
}

function updateGroundStopBars(phase) {
  const nsGreen = phase === 0;
  const ewGreen = phase === 3;

  // J1 stop bars
  if (state.signals.stopBars.north) setStopBarEmissive(state.signals.stopBars.north, nsGreen ? 0 : 1);
  if (state.signals.stopBars.south) setStopBarEmissive(state.signals.stopBars.south, nsGreen ? 0 : 1);
  if (state.signals.stopBars.east) setStopBarEmissive(state.signals.stopBars.east, ewGreen ? 0 : 1);
  if (state.signals.stopBars.west) setStopBarEmissive(state.signals.stopBars.west, ewGreen ? 0 : 1);

  // J2 stop bars — track with upstream NS phase
  if (state.signals.stopBars.j2) {
    const j2 = state.signals.stopBars.j2;
    if (j2.north) setStopBarEmissive(j2.north, nsGreen ? 0 : 1);
    if (j2.south) setStopBarEmissive(j2.south, nsGreen ? 0 : 1);
  }
}

function setStopBarEmissive(group, intensity) {
  if (group.userData.bars) {
    group.userData.bars.forEach(bar => {
      bar.material.emissiveIntensity = intensity;
    });
  }
}

// ─── AI Reasoning Speech Synthesis ───────────────────────────
function updateAISpeech(phase) {
  let text = '';
  const phaseNames = {
    0: 'NORTH-SOUTH GREEN — Vehicles approaching from North/South have right of way.',
    1: 'NORTH-SOUTH YELLOW CLEARANCE — Preparing to switch phases.',
    2: 'ALL-RED CLEARANCE — Intersection clearing for safety.',
    3: 'EAST-WEST GREEN — Vehicles approaching from East/West have right of way.',
    4: 'EAST-WEST YELLOW CLEARANCE — Preparing to switch phases.',
  };

  if (state.currentMode === 'queuesense') {
    const exitPct = Math.round(state.exitBlock);
    if (exitPct > 70) {
      text = `QUEUESENSE AI: ${phaseNames[phase]} DOWNSTREAM SPILLBACK DETECTED (${exitPct}% exit congestion). Suppressing conflicting approach green to prevent gridlock.`;
    } else if (state.densityLevel > 75) {
      text = `QUEUESENSE AI: ${phaseNames[phase]} High density detected (${state.densityLevel}%). Extending green for platoon clearance.`;
    } else {
      text = `QUEUESENSE AI: ${phaseNames[phase]} Adaptive green allocation in progress.`;
    }
  } else {
    text = `TRADITIONAL MODE: ${phaseNames[phase]} Fixed-time signal cycle.`;
  }

  const reasonText = document.getElementById('reasonText');
  if (reasonText) reasonText.textContent = text;
}

// ─── Spawn Logic ────────────────────────────────────────────
let spawnTimer = 0;

function updateSpawning(delta) {
  if (!state.autoRunning) return;

  spawnTimer += delta;
  const baseRate = 0.8;
  const rate = baseRate * (state.densityLevel / 50);
  const spawnInterval = Math.max(0.3, 1.5 / rate);

  if (spawnTimer > spawnInterval) {
    spawnTimer = 0;

    if (state.emergencyActive && Math.random() < 0.15) {
      spawnVehicle('ns', 'S', 'emergency');
    } else {
      const directions = ['N', 'S', 'E', 'W'];
      const dir = directions[Math.floor(Math.random() * 4)];
      const axis = (dir === 'N' || dir === 'S') ? 'ns' : 'ew';
      spawnVehicle(axis, dir);
    }
  }
}

// ─── Auto Scenario Cycling ─────────────────────────────────
let scenarioChangeTimer = 0;
const SCENARIO_DURATION = 25; // seconds per scenario

function updateScenarioCycle(delta) {
  if (!state.autoRunning) return;

  scenarioChangeTimer += delta;
  if (scenarioChangeTimer > SCENARIO_DURATION) {
    scenarioChangeTimer = 0;
    cycleScenario();
  }
}

const SCENARIOS = ['auto', 'surge', 'spillback', 'emergency'];

function cycleScenario() {
  const idx = SCENARIOS.indexOf(state.currentScenario);
  const next = (idx + 1) % SCENARIOS.length;
  applyScenario(SCENARIOS[next]);
}

// ─── KPI Updates ────────────────────────────────────────────
function updateKPIs(delta) {
  const stopped = state.vehicles.filter(v => v.userData.stopped).length;
  const total = state.vehicles.length;

  state.kpi.queue = Math.round(stopped * 1.5);
  state.kpi.wait = Math.round(stopped * 2.5 + Math.sin(state.simTime * 0.3) * 5);
  state.kpi.exit = Math.round(state.exitBlock + Math.sin(state.simTime * 0.2) * 5);

  if (window.QueueSense && window.QueueSense.onKPIUpdate) {
    window.QueueSense.onKPIUpdate(state.kpi);
  }
}

// ─── Animation Loop ────────────────────────────────────────
function animate() {
  if (!renderer) return;

  animationId = requestAnimationFrame(animate);
  const delta = Math.min(clock.getDelta(), 0.05);
  state.simTime += delta;

  const timeScale = state.autoRunning ? 1 : 0;

  updateSignals(delta * timeScale);
  updateVehicles(delta * timeScale);
  updateSpawning(delta * timeScale);
  updateScenarioCycle(delta * timeScale);
  updateKPIs(delta * timeScale);

  // Pulse downstream sensor ring
  if (state.signals.downstreamSensor) {
    const intensity = 0.15 + Math.sin(state.simTime * 3) * 0.1;
    const blocked = state.exitBlock > 70;
    const color = blocked ? COLORS.signalRed : COLORS.signalGreen;
    if (state.signals.downstreamSensor.material) {
      state.signals.downstreamSensor.material.color.setHex(color);
      state.signals.downstreamSensor.material.emissive.setHex(color);
      state.signals.downstreamSensor.material.emissiveIntensity = intensity + (blocked ? 0.3 : 0);
    }
  }

  // Update timeline bar
  const timelineBar = document.getElementById('timelineProgress');
  if (timelineBar) {
    const progress = ((scenarioChangeTimer / SCENARIO_DURATION) * 100);
    timelineBar.style.transform = `scaleX(${Math.min(100, progress) / 100})`;
  }

  // Update scenario label
  const scenarioLabel = document.getElementById('scenarioLabel');
  if (scenarioLabel) {
    const labels = {
      auto: 'Normal Flow',
      surge: 'Density Surge',
      spillback: 'Exit Jam',
      emergency: 'Ambulance',
    };
    scenarioLabel.textContent = labels[state.currentScenario] || 'Normal Flow';
  }

  if (controls && controls.update) controls.update();
  renderer.render(scene, camera);
}

// ─── Camera Setup ─────────────────────────────────────────
function setupCamera() {
  const fov = 45;
  const aspect = window.innerWidth / window.innerHeight;
  const near = 0.1;
  const far = 300;

  camera = new THREE.PerspectiveCamera(fov, aspect, near, far);

  if (state.currentCamera === 'isometric') {
    camera.position.set(35, 30, 35);
    camera.lookAt(0, 2, 0);
  } else if (state.currentCamera === 'top') {
    camera.position.set(0, 50, 0.01);
    camera.lookAt(0, 0, 0);
    camera.rotation.order = 'YXZ';
    camera.rotation.y = 0;
    camera.rotation.x = -Math.PI / 2;
  } else if (state.currentCamera === 'corridor') {
    camera.position.set(0, 12, 22);
    camera.lookAt(0, 2, 30);
  }
}

function switchCamera(preset) {
  state.currentCamera = preset;

  const targets = {
    isometric: { pos: { x: 35, y: 30, z: 35 }, look: { x: 0, y: 2, z: 0 } },
    top: { pos: { x: 0, y: 50, z: 0.01 }, look: { x: 0, y: 0, z: 0 } },
    corridor: { pos: { x: 0, y: 12, z: 22 }, look: { x: 0, y: 2, z: 30 } },
  };

  const target = targets[preset] || targets.isometric;

  if (typeof gsap !== 'undefined') {
    gsap.to(camera.position, {
      duration: 1.2,
      ...target.pos,
      ease: 'power2.inOut',
      onUpdate: () => camera.lookAt(target.look.x, target.look.y, target.look.z),
    });
  } else {
    camera.position.set(target.pos.x, target.pos.y, target.pos.z);
    camera.lookAt(target.look.x, target.look.y, target.look.z);
  }

  if (controls) {
    controls.target.set(target.look.x, target.look.y, target.look.z);
    controls.update();
  }
}

// ─── Scenario Handling ─────────────────────────────────────
function applyScenario(scenario) {
  state.currentScenario = scenario;

  // Clear vehicles
  state.vehicles.forEach(v => scene.remove(v));
  state.vehicles = [];
  state.simTime = 0;
  signalTimer = 0;
  signalPhase = 0;
  scenarioChangeTimer = 0;

  switch (scenario) {
    case 'auto':
      state.densityLevel = 50;
      state.exitBlock = 0;
      setSignalPhase(0);
      spawnInitialVehicles(6);
      break;
    case 'surge':
      state.densityLevel = 55;
      setSignalPhase(0);
      spawnInitialVehicles(4);
      setTimeout(() => { state.densityLevel = 90; }, 15000);
      break;
    case 'spillback':
      state.densityLevel = 75;
      state.exitBlock = 80;
      setSignalPhase(0);
      spawnInitialVehicles(8);
      break;
    case 'emergency':
      state.densityLevel = 50;
      state.exitBlock = 0;
      state.emergencyActive = true;
      setSignalPhase(0);
      spawnInitialVehicles(5);
      setTimeout(() => {
        state.emergencyActive = false;
        state.densityLevel = 50;
      }, 20000);
      break;
  }
}

function spawnInitialVehicles(count) {
  for (let i = 0; i < count; i++) {
    setTimeout(() => {
      const dirs = ['N', 'S', 'E', 'W'];
      const dir = dirs[Math.floor(Math.random() * 4)];
      const axis = (dir === 'N' || dir === 'S') ? 'ns' : 'ew';
      spawnVehicle(axis, dir);
    }, i * 500);
  }
}

// ─── Initialization ─────────────────────────────────────────
function init() {
  const container = document.getElementById('scene-container');
  if (!container) {
    console.error('Scene container not found');
    return;
  }

  clock = new THREE.Clock();

  // Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(COLORS.ground);
  scene.fog = new THREE.FogExp2(COLORS.ground, 0.0025);

  // Renderer
  renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  renderer.outputEncoding = THREE.sRGBEncoding;
  container.appendChild(renderer.domElement);

  // Camera
  setupCamera();

  // Controls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.minDistance = 15;
  controls.maxDistance = 120;
  controls.maxPolarAngle = Math.PI / 2 - 0.05;
  controls.target.set(0, 2, 0);
  controls.update();

  // Build intersection
  buildIntersection();
  setSignalPhase(0);
  spawnInitialVehicles(10);

  // Window resize
  window.addEventListener('resize', onWindowResize);

  // Start animation
  animate();

  // Expose to global scope for app.js
  window.QueueSense = {
    scene: scene,
    camera: camera,
    renderer: renderer,
    state: state,
    switchCamera: switchCamera,
    applyScenario: applyScenario,
    setMode: function (mode) {
      state.currentMode = mode;
      applyScenario(state.currentScenario);
    },
    setDensity: function (level) {
      state.densityLevel = level;
    },
    setExitBlock: function (level) {
      state.exitBlock = level;
    },
    triggerEmergency: function () {
      state.emergencyActive = true;
      spawnVehicle('ns', 'S', 'emergency');
      setTimeout(() => { state.emergencyActive = false; }, 15000);
    },
    setAutoRunning: function (running) {
      state.autoRunning = running;
    },
    setScenario: function (scenario) {
      applyScenario(scenario);
    },
    resetView: function () {
      switchCamera(state.currentCamera);
    },
    onKPIUpdate: null,
  };
}

function onWindowResize() {
  if (!camera || !renderer) return;
  const container = document.getElementById('scene-container');
  if (!container) return;
  const width = container.clientWidth;
  const height = container.clientHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}

// ─── Auto-init when DOM is ready ──────────────────────────
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Expose for debugging
window._QueueSenseDebug = {
  state: state,
  signals: state.signals,
  COLORS: COLORS,
};
