// QueueSense Dashboard — Three.js 3D Scene Engine
// High-craft architectural traffic diorama for J1 + J2 corridor
// Built from scratch: flat geometry, glowing signals, multi-part vehicles, smooth physics

(function () {
  'use strict';

  // ─── Scene State ──────────────────────────────────────────────
  const SceneState = {
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
  };

  // ─── Three.js Core ────────────────────────────────────────────
  let scene, camera, renderer, controls, clock, animationId;
  const state = SceneState;

  // Color palette — high-contrast stone/neutral dark with vibrant signals
  const COLORS = {
    ground: 0x0a0c10,
    asphalt: 0x1c1f26,
    asphaltDark: 0x15181d,
    curb: 0x2a2e36,
    sidewalk: 0x242830,
    crosswalk: 0xf8f8fa,
    laneMark: 0xd1d5db,
    stopLine: 0xfff5e6,
    signalRed: 0xff2e4c,
    signalAmber: 0xffb800,
    signalGreen: 0x00e676,
    vehicleA: 0x4f96ff,   // blue-white
    vehicleB: 0x22c55e,
    vehicleC: 0xffb800,
    vehicleD: 0xff2e4c,
    vehicleEmergency: 0xff4444,
    poleMetal: 0x2a2e3a,
    poleGlow: 0x4a505e,
  };

  // ─── Vehicle Definitions (multi-part 3D) ─────────────────────
  // Each vehicle is a group of meshes parented together for articulated movement.

  function createVehicle(type, color, x, z, length, width, height) {
    const group = new THREE.Group();

    const paintColor = color !== undefined ? color : (0x4f96ff + Math.random() * 0x808080);

    // Body (chassis / main passenger cell)
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

    // Roof / cabin
    const roofHeight = height * 0.4;
    const cabinGeom = type === 'truck'
      ? new THREE.BoxGeometry(length * 0.4, roofHeight, width * 0.9)
      : new THREE.BoxGeometry(length * 0.5, roofHeight, width * 0.85);
    const cabinMat = new THREE.MeshStandardMaterial({
      color: 0x1a1a2e,  // dark glass
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

    // Wheels — 4 cylinders
    const wheelMat = new THREE.MeshStandardMaterial({
      color: 0x111419,
      metalness: 0.9,
      roughness: 0.4,
    });
    const wheelGeom = new THREE.CylinderGeometry(width * 0.12, width * 0.12, width * 0.2, 16);
    const wheelPositions = [
      [-length * 0.35, -height * 0.2, width * 0.35],
      [-length * 0.35, -height * 0.2, -width * 0.35],
      [length * 0.35, -height * 0.2, width * 0.35],
      [length * 0.35, -height * 0.2, -width * 0.35],
    ];
    // For trucks, rear wheels are dual
    if (type === 'truck') {
      wheelPositions.push(
        [length * 0.42, -height * 0.2, width * 0.35],
        [length * 0.42, -height * 0.2, -width * 0.35]
      );
    }

    wheelPositions.forEach(pos => {
      const wheel = new THREE.Mesh(wheelGeom, wheelMat);
      wheel.position.set(pos[0], pos[1], pos[2]);
      wheel.rotation.z = Math.PI / 2;
      wheel.castShadow = true;
      wheel.receiveShadow = true;
      group.add(wheel);
    });

    // Front/rear lights
    const lightMat = new THREE.MeshStandardMaterial({
      color: type === 'emergency' ? COLORS.vehicleEmergency : paintColor,
      emissive: type === 'emergency' ? COLORS.vehicleEmergency : paintColor,
      emissiveIntensity: type === 'emergency' ? 0.8 : 0.3,
      toneMapped: false,
    });
    const lightGeom = new THREE.BoxGeometry(width * 0.15, height * 0.12, 0.02);
    const frontLightL = new THREE.Mesh(lightGeom, lightMat);
    frontLightL.position.set(length * 0.48, height * 0.25, width * 0.25);
    group.add(frontLightL);
    const frontLightR = frontLightL.clone();
    frontLightR.position.x = frontLightL.position.x;
    frontLightR.position.z = -width * 0.25;
    group.add(frontLightR);
    const rearLightL = frontLightL.clone();
    rearLightL.position.set(-length * 0.48, height * 0.25, width * 0.25);
    rearLightL.material.color.setHex(type === 'emergency' ? COLORS.vehicleEmergency : 0xef4444);
    rearLightL.material.emissive.setHex(type === 'emergency' ? COLORS.vehicleEmergency : 0xef4444);
    rearLightL.material.emissiveIntensity = type === 'emergency' ? 0.8 : 0.4;
    group.add(rearLightL);
    const rearLightR = rearLightL.clone();
    rearLightR.position.z = -width * 0.25;
    group.add(rearLightR);

    // Emergency beacon for ambulances
    if (type === 'emergency') {
      const beaconGeom = new THREE.SphereGeometry(width * 0.25, 16, 12);
      const beaconMat = new THREE.MeshStandardMaterial({
        color: COLORS.vehicleEmergency,
        emissive: COLORS.vehicleEmergency,
        emissiveIntensity: 1.0,
        toneMapped: false,
      });
      const beacon = new THREE.Mesh(beaconGeom, beaconMat);
      beacon.position.y = height * 0.8;
      group.add(beacon);
      group.userData.beacon = beacon;
    }

    // For auto-rickshaw: add a distinct canopy
    if (type === 'auto') {
      const canopyGeom = new THREE.ConeGeometry(width * 0.7, height * 0.6, 6);
      const canopyMat = new THREE.MeshStandardMaterial({
        color: 0xe53935,  // auto-rickshaw red
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

    // For bus: add distinct side windows strip
    if (type === 'bus') {
      const windowMat = new THREE.MeshStandardMaterial({
        color: 0x87ceeb,
        transparent: true,
        opacity: 0.6,
        metalness: 0.8,
        roughness: 0.1,
      });
      // Just adjust the cabin opacity for buses
      cabin.material.opacity = 0.5;
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

  // ─── Signal Group (glowing traffic lights) ────────────────────

  function createSignalGroup(name, x, z, axis) {
    const group = new THREE.Group();

    // Pole
    const poleMat = new THREE.MeshStandardMaterial({
      color: COLORS.poleMetal,
      metalness: 0.6,
      roughness: 0.7,
    });

    const poleGeom = new THREE.CylinderGeometry(0.12, 0.15, 4.0, 12);
    const pole = new THREE.Mesh(poleGeom, poleMat);
    pole.castShadow = true;
    pole.receiveShadow = true;
    group.add(pole);

    // Cantilever arm (horizontal)
    const armGeom = new THREE.BoxGeometry(axis === 'ns' ? 2.0 : 2.0, 0.1, 0.15);
    const arm = new THREE.Mesh(armGeom, poleMat);
    arm.position.y = 2.5;
    if (axis === 'ns') {
      arm.position.z = -1.2;  // point east/west
    } else {
      arm.position.x = 1.2;  // point north/south
    }
    arm.castShadow = true;
    arm.receiveShadow = true;
    group.add(arm);

    // Signal housing (box)
    const housingGeom = new THREE.BoxGeometry(0.35, 0.85, 0.25);
    const housingMat = new THREE.MeshStandardMaterial({
      color: 0x0e1013,
      metalness: 0.2,
      roughness: 0.4,
    });
    const housing = new THREE.Mesh(housingGeom, housingMat);
    housing.position.y = 2.5;
    if (axis === 'ns') {
      housing.position.z = -1.8;
    } else {
      housing.position.x = 1.8;
    }
    housing.castShadow = true;
    housing.receiveShadow = true;
    group.add(housing);

    // Three signal bulbs
    const bulbPositions = [
      { y: 2.85, color: COLORS.signalRed, key: 'red' },
      { y: 2.55, color: COLORS.signalAmber, key: 'amber' },
      { y: 2.25, color: COLORS.signalGreen, key: 'green' },
    ];

    bulbPositions.forEach(bp => {
      const bulbGeom = new THREE.SphereGeometry(0.09, 16, 12);
      const emissiveColor = bp.color;
      const bulbMat = new THREE.MeshBasicMaterial({
        color: bp.color,
        emissive: emissiveColor,
        emissiveIntensity: 0,  // off by default, lit when active
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
    const barMat = new THREE.MeshBasicMaterial({
      color: color,
      emissive: color,
      emissiveIntensity: 0,
      toneMapped: false,
    });
    const barGeom = new THREE.BoxGeometry(0.3, 0.08, axis === 'ns' ? 8.0 : 6.0);

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

  // ─── Build the Intersection ───────────────────────────────────

  function buildIntersection() {
    // Ground plane
    const groundGeom = new THREE.PlaneGeometry(80, 80);
    const groundMat = new THREE.MeshStandardMaterial({
      color: COLORS.ground,
      metalness: 0.0,
      roughness: 0.9,
    });
    const ground = new THREE.Mesh(groundGeom, groundMat);
    ground.rotation.x = -Math.PI / 2;  // FLAT — no vertical walls
    ground.receiveShadow = true;
    scene.add(ground);

    // ─── Road surfaces (all flat) ──────────────────────────────
    const roadWidthNS = 7.0;
    const roadWidthEW = 7.0;
    const roadLength = 60;

    // North-South road
    const roadGeomNS = new THREE.PlaneGeometry(roadWidthNS, roadLength);
    const roadMatNS = new THREE.MeshStandardMaterial({
      color: COLORS.asphalt,
      metalness: 0.0,
      roughness: 0.95,
    });
    const roadNS = new THREE.Mesh(roadGeomNS, roadMatNS);
    roadNS.rotation.x = -Math.PI / 2;  // FLAT
    roadNS.position.y = 0.01;
    roadNS.position.set(0, 0.01, 0);
    roadNS.receiveShadow = true;
    scene.add(roadNS);

    // East-West road
    const roadGeomEW = new THREE.PlaneGeometry(roadWidthEW, roadLength);
    const roadMatEW = new THREE.MeshStandardMaterial({
      color: COLORS.asphalt,
      metalness: 0.0,
      roughness: 0.95,
    });
    const roadEW = new THREE.Mesh(roadGeomEW, roadMatEW);
    roadEW.rotation.x = -Math.PI / 2;  // FLAT
    roadEW.position.y = 0.01;
    roadEW.receiveShadow = true;
    scene.add(roadEW);

    // ─── Sidewalks (high-contrast) ─────────────────────────────
    const sidewalkWidth = 4.0;

    function createSidewalk(x, z, rotX, width, length, color) {
      const geom = new THREE.PlaneGeometry(width, length);
      const mat = new THREE.MeshStandardMaterial({
        color: color === undefined ? COLORS.sidewalk : color,
        metalness: 0.05,
        roughness: 0.9,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.rotation.x = -Math.PI / 2 + rotX;  // FLAT or slightly tilted curb
      mesh.position.set(x, 0.02, z);
      mesh.receiveShadow = true;
      scene.add(mesh);
      return mesh;
    }

    // 8 sidewalk slabs (4 per road, one on each side)
    // NS road sides
    createSidewalk(roadWidthNS / 2 + sidewalkWidth / 2, 0, 0, sidewalkWidth, roadLength);
    createSidewalk(-roadWidthNS / 2 - sidewalkWidth / 2, 0, 0, sidewalkWidth, roadLength);
    // EW road sides
    createSidewalk(0, roadWidthEW / 2 + sidewalkWidth / 2, 0, roadLength, sidewalkWidth);
    createSidewalk(0, -roadWidthEW / 2 - sidewalkWidth / 2, 0, roadLength, sidewalkWidth);

    // ─── Curb strips (chamfered transition) ───────────────────
    const curbMat = new THREE.MeshStandardMaterial({
      color: COLORS.curb,
      metalness: 0.1,
      roughness: 0.8,
    });

    function createCurb(x, z, w, l) {
      const geom = new THREE.BoxGeometry(w, 0.15, l);
      const mesh = new THREE.Mesh(geom, curbMat);
      mesh.position.set(x, 0.15 / 2, z);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      scene.add(mesh);
      return mesh;
    }

    // Curbs along road edges
    createCurb(roadWidthNS / 2 + 0.05, 0, 0.1, roadLength);
    createCurb(-roadWidthNS / 2 - 0.05, 0, 0.1, roadLength);
    createCurb(0, roadWidthEW / 2 + 0.05, roadLength, 0.1);
    createCurb(0, -roadWidthEW / 2 - 0.05, roadLength, 0.1);

    // ─── Lane markings ──────────────────────────────────────
    const laneMarkMat = new THREE.MeshStandardMaterial({
      color: COLORS.laneMark,
      metalness: 0.0,
      roughness: 0.5,
    });

    function createDashedLine(axis, start, length, segments, gap, color) {
      const group = new THREE.Group();
      const segLen = (length - (segments - 1) * gap) / segments;
      const geom = new THREE.PlaneGeometry(0.1, segLen);
      const mat = new THREE.MeshStandardMaterial({
        color: color || COLORS.laneMark,
        metalness: 0.0,
        roughness: 0.5,
        side: THREE.DoubleSide,
      });

      for (let i = 0; i < segments; i++) {
        const mesh = new THREE.Mesh(geom, mat);
        mesh.rotation.x = -Math.PI / 2;  // FLAT
        if (axis === 'ns') {
          mesh.position.set(start + i * (segLen + gap), 0.02, 0);
        } else {
          mesh.position.set(0, 0.02, start + i * (segLen + gap));
        }
        group.add(mesh);
      }
      scene.add(group);
      return group;
    }

    // Center dashed lines for each road
    createDashedLine('ns', -roadWidthNS / 2 + 0.15, roadLength, 20, 0.3, COLORS.laneMark);
    createDashedLine('ew', -roadWidthEW / 2 + 0.15, roadLength, 15, 0.3, COLORS.laneMark);

    // ─── Zebra Crosswalks (all flat, high-contrast) ──────────
    function createZebraCrosswalk(x, z, rotationY, length, widthBetween) {
      const group = new THREE.Group();
      const stripes = 12;
      const stripeWidth = (roadWidthNS - widthBetween) / stripes;
      const stripeLength = 2.5;

      const stripeMat = new THREE.MeshStandardMaterial({
        color: COLORS.crosswalk,
        metalness: 0.0,
        roughness: 0.6,
        side: THREE.DoubleSide,
      });

      for (let i = 0; i < stripes; i++) {
        const geom = new THREE.PlaneGeometry(stripeLength, stripeWidth);
        const stripe = new THREE.Mesh(geom, stripeMat);
        stripe.rotation.x = -Math.PI / 2;  // FLAT — no walls
        stripe.rotation.y = rotationY;
        stripe.position.y = 0.03;
        const offset = -length / 2 + widthBetween / 2 + stripeWidth / 2 + i * stripeWidth;
        if (rotationY === 0) {
          // NS road, EW crosswalk
          stripe.position.set(offset, 0.03, z);
        } else {
          // EW road, NS crosswalk
          stripe.position.set(x, 0.03, offset);
        }
        group.add(stripe);
      }
      scene.add(group);
      return group;
    }

    // 4 zebra crosswalks at the intersection
    const crossLength = roadWidthNS;
    createZebraCrosswalk(0, roadWidthEW / 2 + 0.3, 0, crossLength, 0.3);
    createZebraCrosswalk(0, -roadWidthEW / 2 - 0.3, Math.PI, crossLength, 0.3);
    createZebraCrosswalk(roadWidthNS / 2 + 0.3, 0, Math.PI / 2, crossLength, 0.3);
    createZebraCrosswalk(-roadWidthNS / 2 - 0.3, 0, -Math.PI / 2, crossLength, 0.3);

    // ─── Stop lines (glowing, on ground) ────────────────────
    state.signals.stopBars = {};

    const stopBarNS_N = createGroundStopBars('ns', roadWidthEW / 2 + 0.1, COLORS.signalGreen, 1, 0);
    stop_bar_set_position(stopBarNS_N, 0, roadWidthEW / 2 - 0.3);
    scene.add(stopBarNS_N);
    state.signals.stopBars.north = stopBarNS_N;

    const stopBarNS_S = createGroundStopBars('ns', -roadWidthEW / 2 - 0.1, COLORS.signalGreen, 1, 0);
    stop_bar_set_position(stopBarNS_S, 0, -roadWidthEW / 2 + 0.3);
    scene.add(stopBarNS_S);
    state.signals.stopBars.south = stopBarNS_S;

    const stopBarEW_E = createGroundStopBars('ew', roadWidthNS / 2 + 0.1, COLORS.signalGreen, 1, 0);
    stop_bar_set_position(stopBarEW_E, roadWidthNS / 2 - 0.3, 0);
    scene.add(stopBarEW_E);
    state.signals.stopBars.east = stopBarEW_E;

    const stopBarEW_W = createGroundStopBars('ew', -roadWidthNS / 2 - 0.1, COLORS.signalGreen, 1, 0);
    stop_bar_set_position(stopBarEW_W, -roadWidthNS / 2 + 0.3, 0);
    scene.add(stopBarEW_W);
    state.signals.stopBars.west = stopBarEW_W;

    // ─── Traffic Signal Poles ─────────────────────────────────
    state.signals.groups = {};

    // North approach: NS direction signals
    const sigN = createSignalGroup('north', 0, -roadWidthEW / 2 - 1.5, 'ns');
    scene.add(sigN);
    state.signals.groups.north = sigN;

    // South approach
    const sigS = createSignalGroup('south', 0, roadWidthEW / 2 + 1.5, 'ns');
    scene.add(sigS);
    state.signals.groups.south = sigS;

    // East approach: EW direction signals
    const sigE = createSignalGroup('east', roadWidthNS / 2 + 1.5, 0, 'ew');
    scene.add(sigE);
    state.signals.groups.east = sigE;

    // West approach
    const sigW = createSignalGroup('west', -roadWidthNS / 2 - 1.5, 0, 'ew');
    scene.add(sigW);
    state.signals.groups.west = sigW;

    // ─── Junction 2 (downstream) ──────────────────────────────
    // A smaller downstream junction 30 units away along NS axis
    const j2Distance = 30;

    const roadJ2 = new THREE.Mesh(roadGeomNS.clone(), roadMatNS.clone());
    roadJ2.rotation.x = -Math.PI / 2;  // FLAT
    roadJ2.position.set(0, 0.01, j2Distance);
    roadJ2.receiveShadow = true;
    scene.add(roadJ2);

    // J2 signal
    const sigJ2 = createSignalGroup('j2_downstream', 0, j2Distance + roadWidthEW / 2 + 1.5, 'ns');
    scene.add(sigJ2);
    state.signals.groups.j2 = sigJ2;

    // ─── Ambient & Lighting ───────────────────────────────────
    const ambient = new THREE.AmbientLight(0x404060, 1.8);
    scene.add(ambient);

    const dirLight = new THREE.DirectionalLight(0xffffff, 2.0);
    dirLight.position.set(20, 40, 15);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 100;
    dirLight.shadow.camera.left = -40;
    dirLight.shadow.camera.right = 40;
    dirLight.shadow.camera.top = 40;
    dirLight.shadow.camera.bottom = -40;
    scene.add(dirLight);

    // ─── Fog for depth ───────────────────────────────────────
    scene.fog = new THREE.FogExp2(0x0a0c10, 0.003);
  }

  // Helper: adjust stop bar group position without moving individual mesh z
  function stop_bar_set_position(group, x, z) {
    group.position.x = x;
    group.position.z = z;
  }

  // ─── Vehicle Spawning & Physics ─────────────────────────────

  function spawnVehicle(axis, direction, type) {
    const roadWidth = 7.0;
    const laneOffset = direction === 'N' || direction === 'E' ? -roadWidth / 2 + 0.8 : roadWidth / 2 - 0.8;

    let x, z, rotY;
    if (axis === 'ns') {
      x = laneOffset;
      z = direction === 'N' ? 35 : -35;
      rotY = direction === 'N' ? Math.PI : 0;
    } else {
      z = laneOffset;
      x = direction === 'E' ? 35 : -35;
      rotY = direction === 'E' ? -Math.PI / 2 : Math.PI / 2;
    }

    const types = ['sedan', 'sedan', 'sedan', 'suv', 'truck', 'bus', 'auto', 'bike'];
    const colors = [COLORS.vehicleA, 0xff6b6b, 0x4ecdc4, 0xff9f43, 0x54a0ff, 0x22c55e];
    const t = type || types[Math.floor(Math.random() * types.length)];
    const c = colors[Math.floor(Math.random() * colors.length)];

    const lengths = {
      sedan: [4.0, 1.7, 1.5],
      suv: [4.5, 1.9, 1.7],
      truck: [7.0, 2.2, 2.2],
      bus: [9.0, 2.5, 3.0],
      auto: [2.8, 1.0, 1.5],
      bike: [1.8, 0.7, 1.2],
    };
    const dims = lengths[t];

    const vehicle = createVehicle(t, c, x, z, dims[0], dims[1], dims[2]);
    vehicle.rotation.y = rotY;
    vehicle.userData.speed = 0;
    vehicle.userData.maxSpeed = (t === 'truck' || t === 'bus') ? 8 + Math.random() * 4 : 12 + Math.random() * 6;
    vehicle.userData.accel = (t === 'truck' || t === 'bus') ? 1.5 : 2.5;
    vehicle.userData.deceleration = (t === 'bike') ? 4.0 : 5.5;
    vehicle.userData.targetSpeed = vehicle.userData.maxSpeed;
    vehicle.userData.axis = axis;
    vehicle.userData.direction = direction;

    // Build path points for the vehicle to follow
    const pathPoints = buildPath(axis, direction, rotY);
    vehicle.userData.pathPoints = pathPoints;
    vehicle.userData.pathIndex = 0;

    scene.add(vehicle);
    state.vehicles.push(vehicle);
    vehicle.name = `vehicle_${state.vehicles.length}`;

    return vehicle;
  }

  function buildPath(axis, direction, rotY) {
    // Build a simple curved path through the intersection
    const points = [];
    const roadW = 3.5;

    if (axis === 'ns' && direction === 'N') {
      // Coming from south, going north
      for (let i = 0; i <= 10; i++) {
        const t = i / 10;
        const z = -30 + t * 60;
        // Slight curve as they approach intersection center
        const x = -roadW + (Math.sin(t * Math.PI) * 0.3);
        points.push(new THREE.Vector3(x, 0, z));
      }
    } else if (axis === 'ns' && direction === 'S') {
      for (let i = 0; i <= 10; i++) {
        const t = i / 10;
        const z = 30 - t * 60;
        const x = roadW + (Math.sin(t * Math.PI) * 0.3);
        points.push(new THREE.Vector3(x, 0, z));
      }
    } else if (axis === 'ew' && direction === 'E') {
      for (let i = 0; i <= 10; i++) {
        const t = i / 10;
        const x = -30 + t * 60;
        const z = -roadW + (Math.sin(t * Math.PI) * 0.3);
        points.push(new THREE.Vector3(x, 0, z));
      }
    } else {
      // EW, direction W
      for (let i = 0; i <= 10; i++) {
        const t = i / 10;
        const x = 30 - t * 60;
        const z = roadW + (Math.sin(t * Math.PI) * 0.3);
        points.push(new THREE.Vector3(x, 0, z));
      }
    }

    return points;
  }

  // ─── Physics Update Loop ────────────────────────────────────

  function updateVehicles(delta) {
    const stopThreshold = 0.05;

    state.vehicles.forEach((vehicle, idx) => {
      // Check if vehicle should stop at the stop line
      const stopLine = getStopLineForVehicle(vehicle);
      const distToStop = distanceToStopLine(vehicle, stopLine);

      // Check signal state
      const signalKey = getSignalKeyForVehicle(vehicle);

      if (distToStop < 5 && !isSignalGreen(signalKey)) {
        vehicle.userData.targetSpeed = 0;
        vehicle.userData.stopped = true;
      } else if (distToStop < 8 && !isSignalGreen(signalKey)) {
        // Begin deceleration
        vehicle.userData.targetSpeed = Math.max(vehicle.userData.targetSpeed * 0.7, 0);
      } else if (distToStop > 10) {
        vehicle.userData.stopped = false;
        vehicle.userData.targetSpeed = vehicle.userData.maxSpeed;
      }

      // Smooth acceleration/deceleration
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

      // Move vehicle along its path
      if (vehicle.userData.speed > 0.001 || !vehicle.userData.stopped) {
        const moveDist = vehicle.userData.speed * delta;
        const currentPoint = vehicle.userData.pathPoints[
          Math.min(vehicle.userData.pathIndex, vehicle.userData.pathPoints.length - 1)
        ];

        // Move along path
        vehicle.userData.pathIndex += moveDist / 2.0; // path segment length heuristic
        if (vehicle.userData.pathIndex >= vehicle.userData.pathPoints.length - 1) {
          // Vehicle has left the visible area
          vehicle.userData.pathIndex = 0;
          // Respawn at origin
          const roadW = 3.5;
          if (vehicle.userData.direction === 'N') {
            vehicle.position.set(-roadW, 0, -35);
          } else if (vehicle.userData.direction === 'S') {
            vehicle.position.set(roadW, 0, 35);
          } else if (vehicle.userData.direction === 'E') {
            vehicle.position.set(-35, 0, -roadW);
          } else {
            vehicle.position.set(35, 0, roadW);
          }
          return;
        }

        const targetPoint = vehicle.userData.pathPoints[
          Math.min(Math.floor(vehicle.userData.pathIndex), vehicle.userData.pathPoints.length - 1)
        ];
        vehicle.position.lerp(targetPoint, 0.02);
      }

      // Update emergency beacon flash
      if (vehicle.userData.type === 'emergency' && vehicle.userData.beacon) {
        const intensity = Math.sin(state.simTime * 10) * 0.5 + 0.5;
        vehicle.userData.beacon.material.emissiveIntensity = 0.5 + intensity * 0.5;
      }
    });

    // Remove vehicles that are too far
    if (state.vehicles.length > 50) {
      const excess = state.vehicles.splice(0, state.vehicles.length - 50);
      excess.forEach(v => scene.remove(v));
    }
  }

  function getStopLineForVehicle(vehicle) {
    const d = vehicle.userData.direction;
    if (d === 'N' || d === 'S') return { axis: 'ns', dir: d };
    return { axis: 'ew', dir: d };
  }

  function distanceToStopLine(vehicle, stopLine) {
    const pos = vehicle.position;
    let stopZ = 0, stopX = 0;

    if (stopLine.axis === 'ns') {
      stopZ = stopLine.dir === 'N' ? 3.5 : -3.5;
      return Math.abs(pos.z - stopZ);
    } else {
      stopX = stopLine.dir === 'E' ? 3.5 : -3.5;
      return Math.abs(pos.x - stopX);
    }
  }

  function getSignalKeyForVehicle(vehicle) {
    const d = vehicle.userData.direction;
    if (d === 'N') return 'north';
    if (d === 'S') return 'south';
    if (d === 'E') return 'east';
    return 'west';
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
    ns_yellow: 3,
    all_red: 2,
    ew_green: 25,
    ew_yellow: 3,
  };

  function updateSignals(delta) {
    signalTimer += delta;

    if (state.currentMode === 'queuesense') {
      // QueueSense: adaptive timing based on density
      const densityFactor = state.densityLevel / 50;
      const cycle = SIGNAL_CYCLE;

      if (signalPhase === 0 && signalTimer > cycle.ns_green * (0.8 + densityFactor * 0.4)) {
        setSignalPhase(1);
      } else if (signalPhase === 1 && signalTimer > cycle.ns_yellow) {
        setSignalPhase(2);
      } else if (signalPhase === 2 && signalTimer > cycle.all_red) {
        setSignalPhase(3);
      } else if (signalPhase === 3 && signalTimer > cycle.ew_green * (0.8 + densityFactor * 0.4)) {
        setSignalPhase(4);
      } else if (signalPhase === 4 && signalTimer > cycle.ew_yellow) {
        setSignalPhase(0);
        signalTimer = 0;
      }
    } else {
      // Traditional fixed-time
      const cycle = SIGNAL_CYCLE;
      if (signalPhase === 0 && signalTimer > cycle.ns_green) {
        setSignalPhase(1);
      } else if (signalPhase === 1 && signalTimer > cycle.ns_yellow) {
        setSignalPhase(2);
      } else if (signalPhase === 2 && signalTimer > cycle.all_red) {
        setSignalPhase(3);
      } else if (signalPhase === 3 && signalTimer > cycle.ew_green) {
        setSignalPhase(4);
      } else if (signalPhase === 4 && signalTimer > cycle.ew_yellow) {
        setSignalPhase(0);
        signalTimer = 0;
      }
    }
  }

  function setSignalPhase(phase) {
    if (phase === signalPhase) return;
    signalPhase = phase;
    signalTimer = 0;

    // NS signals: groups north, south, j2
    // EW signals: groups east, west
    const nsSignals = ['north', 'south', 'j2'];
    const ewSignals = ['east', 'west'];

    nsSignals.forEach(key => {
      const group = state.signals.groups[key];
      if (!group) return;
      if (phase === 0) {
        setBulb(group, 'green');
      } else if (phase === 1) {
        setBulb(group, 'amber');
      } else if (phase === 2 || phase === 4) {
        setBulb(group, 'red');
      } else if (phase === 3) {
        setBulb(group, 'green');
      }
    });

    ewSignals.forEach(key => {
      const group = state.signals.groups[key];
      if (!group) return;
      if (phase === 0 || phase === 1 || phase === 2) {
        setBulb(group, 'red');
      } else if (phase === 3) {
        setBulb(group, 'green');
      } else if (phase === 4) {
        setBulb(group, 'amber');
      }
    });

    // Update ground stop bars
    updateGroundStopBars(phase);
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

    // NS stop bars
    if (state.signals.stopBars.north) {
      const intensity = nsGreen ? 0 : 1;
      setStopBarEmissive(state.signals.stopBars.north, intensity);
    }
    if (state.signals.stopBars.south) {
      const intensity = nsGreen ? 0 : 1;
      setStopBarEmissive(state.signals.stopBars.south, intensity);
    }

    // EW stop bars
    if (state.signals.stopBars.east) {
      const intensity = ewGreen ? 0 : 1;
      setStopBarEmissive(state.signals.stopBars.east, intensity);
    }
    if (state.signals.stopBars.west) {
      const intensity = ewGreen ? 0 : 1;
      setStopBarEmissive(state.signals.stopBars.west, intensity);
    }
  }

  function setStopBarEmissive(group, intensity) {
    if (group.userData.bars) {
      group.userData.bars.forEach(bar => {
        bar.material.emissiveIntensity = intensity;
      });
    }
  }

  // ─── Spawn Logic ────────────────────────────────────────────

  let spawnTimer = 0;

  function updateSpawning(delta) {
    if (!state.autoRunning) return;

    spawnTimer += delta;
    const baseRate = 0.5; // vehicles per second at density 50
    const rate = baseRate * (state.densityLevel / 50);

    if (spawnTimer > 1 / rate) {
      spawnTimer = 0;

      // Spawn from all 4 approaches
      if (Math.random() < 0.5) {
        if (Math.random() < 0.5) {
          spawnVehicle('ns', 'N', null);
        } else {
          spawnVehicle('ns', 'S', null);
        }
      } else {
        if (Math.random() < 0.5) {
          spawnVehicle('ew', 'E', null);
        } else {
          spawnVehicle('ew', 'W', null);
        }
      }
    }

    // Emergency vehicle spawn (rare)
    if (state.emergencyActive && Math.random() < 0.02) {
      spawnVehicle('ns', 'S', 'emergency');
    }
  }

  // ─── KPI Updates ────────────────────────────────────────────

  function updateKPIs(delta) {
    const stopped = state.vehicles.filter(v => v.userData.stopped).length;
    const active = state.vehicles.length;
    const totalStops = stopped;
    const waitTime = totalStops > 0 ? totalStops * (1 - Math.cos(state.simTime * 0.5)) * 0.1 : 0;

    state.kpi.queue = Math.round(totalStops * 1.5);
    state.kpi.wait = waitTime > 0.1 ? Math.round(waitTime * 10) / 10 : 0;

    if (state.exitBlock > 0) {
      state.kpi.exit = state.exitBlock;
    } else {
      state.kpi.exit = Math.round(Math.sin(state.simTime * 0.3) * 10 + 20);
    }

    // Emit KPI updates to app.js
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
    updateKPIs(delta * timeScale);

    if (controls && controls.update) {
      controls.update();
    }

    renderer.render(scene, camera);
  }

  // ─── Camera Setup ─────────────────────────────────────────

  function setupCamera() {
    const fov = 45;
    const aspect = window.innerWidth / window.innerHeight;
    const near = 0.1;
    const far = 200;

    camera = new THREE.PerspectiveCamera(fov, aspect, near, far);

    if (state.currentCamera === 'isometric') {
      camera.position.set(30, 28, 30);
      camera.lookAt(0, 2, 0);
    } else if (state.currentCamera === 'top') {
      camera.position.set(0, 45, 0.01);
      camera.lookAt(0, 0, 0);
      camera.rotation.order = 'YXZ';
      camera.rotation.y = 0;
      camera.rotation.x = -Math.PI / 2;
    } else if (state.currentCamera === 'follow') {
      camera.position.set(0, 12, 22);
      camera.lookAt(0, 2, 0);
    }
  }

  function switchCamera(preset) {
    state.currentCamera = preset;

    const targets = {
      isometric: { pos: { x: 30, y: 28, z: 30 }, look: { x: 0, y: 2, z: 0 } },
      top: { pos: { x: 0, y: 45, z: 0.01 }, look: { x: 0, y: 0, z: 0 } },
      follow: { pos: { x: 0, y: 12, z: 22 }, look: { x: 0, y: 2, z: 0 } },
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

    controls.target.set(target.look.x, target.look.y, target.look.z);
    controls.update();
  }

  // ─── Scenario Handling ─────────────────────────────────────

  function applyScenario(scenario) {
    state.currentScenario = scenario;
    state.vehicles.forEach(v => {
      scene.remove(v);
    });
    state.vehicles = [];
    state.simTime = 0;
    signalTimer = 0;
    signalPhase = 0;

    switch (scenario) {
      case 'auto':
        state.densityLevel = 50;
        state.exitBlock = 0;
        setSignalPhase(0);
        break;
      case 'surge':
        state.densityLevel = 85;
        setSignalPhase(0);
        setTimeout(() => {
          state.densityLevel = 100;
        }, 15000);
        break;
      case 'spillback':
        state.densityLevel = 70;
        state.exitBlock = 40;
        setSignalPhase(0);
        break;
      case 'emergency':
        state.densityLevel = 50;
        state.emergencyActive = true;
        setTimeout(() => {
          state.emergencyActive = false;
          state.densityLevel = 50;
        }, 20000);
        break;
    }

    // Update AI reasoning text
    const reasonText = document.getElementById('reasonText');
    if (reasonText) {
      const reasons = {
        auto: 'Monitoring balanced traffic across all approaches. NS phase active.',
        surge: 'Density surge detected. QueueSense AI extending NS green by 4.7s.',
        spillback: 'Exit congestion detected (40%). Suppressing EW arrivals, clearing NS queue.',
        emergency: 'AMBULANCE DETECTED — activating emergency corridor on NS approach.',
      };
      reasonText.textContent = reasons[scenario] || reasons.auto;
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

    // Renderer
    renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.outputEncoding = THREE.sRGBEncoding;
    container.appendChild(renderer.domElement);

    // Camera
    setupCamera();

    // Controls
    if (typeof THREE.OrbitControls !== 'undefined') {
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.minDistance = 15;
      controls.maxDistance = 80;
      controls.maxPolarAngle = Math.PI / 2;
      controls.target.set(0, 2, 0);
      controls.update();
    }

    // Build intersection
    buildIntersection();

    // Initialize signals
    setSignalPhase(0);

    // Spawn initial vehicles
    for (let i = 0; i < 6; i++) {
      setTimeout(() => {
        const axes = ['ns', 'ew'];
        const dirs = ['N', 'S', 'E', 'W'];
        const axis = axes[Math.floor(Math.random() * 2)];
        const dir = dirs[Math.floor(Math.random() * 4)];
        spawnVehicle(axis, dir);
      }, i * 800);
    }

    // Window resize
    window.addEventListener('resize', onWindowResize);

    // Start animation
    animate();

    // Expose to global scope
    window.QueueSense = {
      scene: scene,
      camera: camera,
      renderer: renderer,
      state: state,
      switchCamera: switchCamera,
      applyScenario: applyScenario,
      setMode: function (mode) {
        state.currentMode = mode;
      },
      setDensity: function (level) {
        state.densityLevel = level;
      },
      setExitBlock: function (level) {
        state.exitBlock = level;
      },
      triggerEmergency: function () {
        state.emergencyActive = true;
        setTimeout(() => {
          state.emergencyActive = false;
        }, 15000);
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
})();