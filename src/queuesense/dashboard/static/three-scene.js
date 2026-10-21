// QueueSense 3D Scene — Multi-part vehicle models with lighting
// No flat BoxGeometry: every vehicle is a rich THREE.Group with real proportions

(function() {
  'use strict';

  // --- Scene setup ---
  const container = document.getElementById('scene-container');
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0a0e);

  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 2000);
  camera.position.set(40, 30, 45);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  container.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.enablePan = false;
  controls.minDistance = 20;
  controls.maxDistance = 120;
  controls.maxPolarAngle = Math.PI / 2.2;

  // --- Lighting ---
  const ambient = new THREE.AmbientLight(0x404060, 1.5);
  scene.add(ambient);

  const hemi = new THREE.HemisphereLight(0x888888, 0x333333, 0.6);
  hemi.position.set(0, 50, 0);
  scene.add(hemi);

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
  dirLight.position.set(30, 50, 20);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.width = 1024;
  dirLight.shadow.mapSize.height = 1024;
  dirLight.shadow.camera.near = 1;
  dirLight.shadow.camera.far = 200;
  dirLight.shadow.camera.left = -40;
  dirLight.shadow.camera.right = 40;
  dirLight.shadow.camera.top = 40;
  dirLight.shadow.camera.bottom = -40;
  scene.add(dirLight);

  // --- Ground / Road ---
  const groundGeo = new THREE.PlaneGeometry(200, 200);
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x1a1a1e,
    roughness: 0.9,
    metalness: 0.1
  });
  const ground = new THREE.Mesh(groundGeo, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // Road markings
  const lineMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6 });
  const dashGeo = new THREE.PlaneGeometry(4, 0.15);
  for (let i = -90; i < 90; i += 12) {
    const dash1 = new THREE.Mesh(dashGeo, lineMat);
    dash1.rotation.x = -Math.PI / 2;
    dash1.position.set(i, 0.01, -1.5);
    scene.add(dash1);
    const dash2 = new THREE.Mesh(dashGeo, lineMat);
    dash2.rotation.x = -Math.PI / 2;
    dash2.position.set(i, 0.01, 1.5);
    scene.add(dash2);
  }

  // --- Materials ---
  const MATS = {
    car_body: new THREE.MeshStandardMaterial({ color: 0x00e5ff, roughness: 0.3, metalness: 0.6 }),
    car_body_red: new THREE.MeshStandardMaterial({ color: 0xff3e3e, roughness: 0.25, metalness: 0.7 }),
    car_body_blue: new THREE.MeshStandardMaterial({ color: 0x4a90ff, roughness: 0.3, metalness: 0.6 }),
    car_body_white: new THREE.MeshStandardMaterial({ color: 0xf5f5f7, roughness: 0.3, metalness: 0.8 }),
    car_body_black: new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.2, metalness: 0.9 }),
    car_body_silver: new THREE.MeshStandardMaterial({ color: 0xc0c0c0, roughness: 0.2, metalness: 0.9 }),
    car_body_orange: new THREE.MeshStandardMaterial({ color: 0xff8c00, roughness: 0.3, metalness: 0.5 }),
    truck_body: new THREE.MeshStandardMaterial({ color: 0x8b4513, roughness: 0.5, metalness: 0.3 }),
    truck_metal: new THREE.MeshStandardMaterial({ color: 0x808080, roughness: 0.2, metalness: 0.9 }),
    bus_body: new THREE.MeshStandardMaterial({ color: 0x4a90ff, roughness: 0.4, metalness: 0.4 }),
    bus_window: new THREE.MeshPhysicalMaterial({ color: 0xa0c8f0, transparent: true, opacity: 0.7, roughness: 0.1, metalness: 0.8 }),
    auto_body: new THREE.MeshStandardMaterial({ color: 0xffff00, roughness: 0.3, metalness: 0.4 }),
    bike_body: new THREE.MeshStandardMaterial({ color: 0xff3e3e, roughness: 0.25, metalness: 0.7 }),
    bike_wheel: new THREE.MeshStandardMaterial({ color: 0x202020, roughness: 0.8, metalness: 0.2 }),
    glass_dark: new THREE.MeshPhysicalMaterial({ color: 0x0a0a1a, transparent: true, opacity: 0.55, roughness: 0.05, metalness: 0.9, transmission: 0.9 }),
    wheel_rubber: new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.95, metalness: 0.0 }),
    wheel_metal: new THREE.MeshStandardMaterial({ color: 0x333333, roughness: 0.4, metalness: 0.8 }),
    signal_green: new THREE.MeshStandardMaterial({ color: 0x00ff88, emissive: 0x00ff88, emissiveIntensity: 0.8 }),
    signal_yellow: new THREE.MeshStandardMaterial({ color: 0xffff00, emissive: 0xffff00, emissiveIntensity: 0.8 }),
    signal_red: new THREE.MeshStandardMaterial({ color: 0xff4444, emissive: 0xff4444, emissiveIntensity: 0.8 }),
    signal_dark: new THREE.MeshStandardMaterial({ color: 0x1a1a1a, emissive: 0x111111, emissiveIntensity: 0.1 }),
    pole_metal: new THREE.MeshStandardMaterial({ color: 0x2a2a3a, roughness: 0.3, metalness: 0.9 }),
    countdown_led: new THREE.MeshBasicMaterial({ color: 0xff4444, toneMapped: false }),
    road_text: new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.8, toneMapped: false }),
    cross_hatch: new THREE.MeshBasicMaterial({ color: 0x3a3a4a, transparent: true, opacity: 0.4, toneMapped: false }),
  };

  // --- Vehicle Factory (multi-part THREE.Group models) ---
  function createCar(colorMat, length = 4.5, width = 1.8, height = 1.4) {
    const group = new THREE.Group();

    // Chassis (main body)
    const chassisGeo = new THREE.BoxGeometry(length * 0.92, height * 0.5, width);
    const chassis = new THREE.Mesh(chassisGeo, colorMat);
    chassis.position.y = height * 0.4;
    chassis.castShadow = true;
    chassis.receiveShadow = true;
    group.add(chassis);

    // Cabin (rear passenger section)
    const cabinGeo = new THREE.BoxGeometry(length * 0.5, height * 0.45, width * 0.85);
    const cabin = new THREE.Mesh(cabinGeo, colorMat);
    cabin.position.set(-length * 0.15, height * 0.75, 0);
    cabin.castShadow = true;
    group.add(cabin);

    // Hood (front)
    const hoodGeo = new THREE.BoxGeometry(length * 0.25, height * 0.3, width * 0.9);
    const hood = new THREE.Mesh(hoodGeo, colorMat);
    hood.position.set(length * 0.4, height * 0.55, 0);
    hood.castShadow = true;
    group.add(hood);

    // Windshield
    const windshieldGeo = new THREE.PlaneGeometry(length * 0.35, height * 0.35);
    const windshield = new THREE.Mesh(windshieldGeo, MATS.glass_dark);
    windshield.rotation.y = Math.PI / 2;
    windshield.position.set(-length * 0.15, height * 0.85, 0);
    windshield.castShadow = true;
    group.add(windshield);

    // Wheels (4)
    const wheelGeo = new THREE.CylinderGeometry(width * 0.18, width * 0.18, width * 0.25, 32);
    wheelGeo.rotateX(Math.PI / 2);
    const wheelPositions = [
      [-length * 0.32, height * 0.25, width * 0.55],
      [-length * 0.32, height * 0.25, -width * 0.55],
      [length * 0.3, height * 0.25, width * 0.55],
      [length * 0.3, height * 0.25, -width * 0.55],
    ];
    for (const pos of wheelPositions) {
      const wheel = new THREE.Mesh(wheelGeo, MATS.wheel_rubber);
      wheel.position.set(pos[0], pos[1], pos[2]);
      wheel.castShadow = true;
      wheel.receiveShadow = true;
      group.add(wheel);
    }

    // Headlights (2)
    const lightGeo = new THREE.SphereGeometry(width * 0.08, 16, 16);
    const headLight1 = new THREE.Mesh(lightGeo, MATS.signal_red);
    headLight1.position.set(length * 0.45, height * 0.55, width * 0.35);
    const headLight2 = new THREE.Mesh(lightGeo, MATS.signal_red);
    headLight2.position.set(length * 0.45, height * 0.55, -width * 0.35);
    group.add(headLight1, headLight2);

    // Brake lights (2)
    const brake1 = new THREE.Mesh(lightGeo, MATS.signal_red);
    brake1.position.set(-length * 0.45, height * 0.55, width * 0.2);
    brake1.material.emissiveIntensity = 0;
    const brake2 = new THREE.Mesh(lightGeo, MATS.signal_red);
    brake2.position.set(-length * 0.45, height * 0.55, -width * 0.2);
    brake2.material.emissiveIntensity = 0;
    group.add(brake1, brake2);

    // Store references for animation
    group.userData = { type: 'car', headlights: [headLight1, headLight2], brakeLights: [brake1, brake2], wheels: [] };

    // Store wheel references
    let wheelIdx = 0;
    group.traverse(function(child) {
      if (child.geometry && child.geometry.type === 'CylinderGeometry') {
        group.userData.wheels.push(child);
      }
    });

    return group;
  }

  // --- Truck ---
  function createTruck(colorMat) {
    const group = new THREE.Group();

    // Cab (forward control)
    const cabGeo = new THREE.BoxGeometry(3, 2.2, 2.4);
    const cab = new THREE.Mesh(cabGeo, MATS.truck_metal);
    cab.position.y = 1.8;
    cab.castShadow = true;
    group.add(cab);

    // Cab windshield
    const windGeo = new THREE.PlaneGeometry(2, 1.2);
    const windshield = new THREE.Mesh(windGeo, MATS.glass_dark);
    windshield.rotation.y = Math.PI / 2;
    windshield.position.set(0, 2.8, 0);
    windshield.castShadow = true;
    group.add(windshield);

    // Trailer
    const trailerGeo = new THREE.BoxGeometry(5, 1.2, 2.4);
    const trailer = new THREE.Mesh(trailerGeo, colorMat);
    trailer.position.set(-4.5, 1.4, 0);
    trailer.castShadow = true;
    group.add(trailer);

    // Trailer sides
    const sideGeo = new THREE.BoxGeometry(5, 0.8, 0.2);
    const side1 = new THREE.Mesh(sideGeo, colorMat);
    side1.position.set(-4.5, 2.2, 1.1);
    side1.castShadow = true;
    const side2 = new THREE.Mesh(sideGeo, colorMat);
    side2.position.set(-4.5, 2.2, -1.1);
    side2.castShadow = true;
    group.add(side1, side2);

    // Wheels (6: 2 for cab, 4 for trailer)
    const wheelGeo = new THREE.CylinderGeometry(0.4, 0.4, 0.35, 32);
    wheelGeo.rotateX(Math.PI / 2);
    const wheelPositions = [
      [1.2, 0.7, 1.3], [1.2, 0.7, -1.3],  // cab front
      [1.2, 0.7, 0],   // cab rear
      [-2.5, 0.7, 1.3], [-2.5, 0.7, -1.3], // trailer mid
      [-6.2, 0.7, 0],   // trailer rear
    ];
    for (const pos of wheelPositions) {
      const wheel = new THREE.Mesh(wheelGeo, MATS.wheel_rubber);
      wheel.position.set(pos[0], pos[1], pos[2]);
      wheel.castShadow = true;
      group.add(wheel);
    }

    // Headlights
    const lightGeo = new THREE.SphereGeometry(0.2, 16, 16);
    const hl1 = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl1.position.set(1.5, 1.8, 0.5);
    const hl2 = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl2.position.set(1.5, 1.8, -0.5);
    group.add(hl1, hl2);

    // Brake lights
    const bl1 = new THREE.Mesh(lightGeo, MATS.signal_red);
    bl1.position.set(-6.8, 1.7, 0.3);
    bl1.material.emissiveIntensity = 0;
    const bl2 = new THREE.Mesh(lightGeo, MATS.signal_red);
    bl2.position.set(-6.8, 1.7, -0.3);
    bl2.material.emissiveIntensity = 0;
    group.add(bl1, bl2);

    group.userData = { type: 'truck', headlights: [hl1, hl2], brakeLights: [bl1, bl2] };
    return group;
  }

  // --- Bus ---
  function createBus(colorMat) {
    const group = new THREE.Group();

    // Main coach body
    const bodyGeo = new THREE.BoxGeometry(9, 2.8, 2.6);
    const body = new THREE.Mesh(bodyGeo, colorMat);
    body.position.y = 2.2;
    body.castShadow = true;
    group.add(body);

    // Front windshield
    const windGeo = new THREE.PlaneGeometry(3, 2.2);
    const windshield = new THREE.Mesh(windGeo, MATS.glass_dark);
    windshield.rotation.y = Math.PI / 2;
    windshield.position.set(-3.2, 3, 0);
    windshield.castShadow = true;
    group.add(windshield);

    // AC unit on roof
    const acGeo = new THREE.BoxGeometry(4, 0.6, 1.2);
    const acUnit = new THREE.Mesh(acGeo, MATS.truck_metal);
    acUnit.position.set(1.5, 3.8, 0);
    acUnit.castShadow = true;
    group.add(acUnit);

    // Side windows
    const winGeo = new THREE.BoxGeometry(5, 1.2, 0.05);
    const winMat = new THREE.MeshPhysicalMaterial({ color: 0xa0c8f0, transparent: true, opacity: 0.6, roughness: 0.1, metalness: 0.8 });
    const win1 = new THREE.Mesh(winGeo, winMat);
    win1.position.set(1, 3.4, 1.3);
    win1.castShadow = true;
    const win2 = new THREE.Mesh(winGeo, winMat);
    win2.position.set(-1.5, 3.4, 1.3);
    win2.castShadow = true;
    group.add(win1, win2);

    // Wheels (6)
    const wheelGeo = new THREE.CylinderGeometry(0.45, 0.45, 0.4, 32);
    wheelGeo.rotateX(Math.PI / 2);
    const wheelPositions = [
      [-3.8, 0.8, 1.4], [-3.8, 0.8, -1.4],  // front axle
      [0.5, 0.8, 1.4], [0.5, 0.8, -1.4],    // mid axle
      [3.5, 0.8, 1.4], [3.5, 0.8, -1.4],    // rear axle
    ];
    for (const pos of wheelPositions) {
      const wheel = new THREE.Mesh(wheelGeo, MATS.wheel_rubber);
      wheel.position.set(pos[0], pos[1], pos[2]);
      wheel.castShadow = true;
      group.add(wheel);
    }

    // Headlights
    const lightGeo = new THREE.SphereGeometry(0.25, 16, 16);
    const hl1 = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl1.position.set(-4.3, 2.4, 0.4);
    const hl2 = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl2.position.set(-4.3, 2.4, -0.4);
    group.add(hl1, hl2);

    // Brake lights
    const bl1 = new THREE.Mesh(lightGeo, MATS.signal_red);
    bl1.position.set(4.3, 2.3, 0.3);
    bl1.material.emissiveIntensity = 0;
    const bl2 = new THREE.Mesh(lightGeo, MATS.signal_red);
    bl2.position.set(4.3, 2.3, -0.3);
    bl2.material.emissiveIntensity = 0;
    group.add(bl1, bl2);

    group.userData = { type: 'bus', headlights: [hl1, hl2], brakeLights: [bl1, bl2] };
    return group;
  }

  // --- Auto-rickshaw (3-wheeler) ---
  function createAutoRickshaw(colorMat) {
    const group = new THREE.Group();

    // Main cabin
    const cabinGeo = new THREE.BoxGeometry(2.2, 1.4, 1.3);
    const cabin = new THREE.Mesh(cabinGeo, colorMat);
    cabin.position.y = 1.0;
    cabin.castShadow = true;
    group.add(cabin);

    // Rear passenger cabin
    const rearGeo = new THREE.SphereGeometry(0.8, 16, 16);
    const rear = new THREE.Mesh(rearGeo, colorMat);
    rear.position.set(0.9, 1.0, 0);
    rear.castShadow = true;
    group.add(rear);

    // Front cabin (driver)
    const frontGeo = new THREE.BoxGeometry(1, 1.2, 1.2);
    const front = new THREE.Mesh(frontGeo, colorMat);
    front.position.set(-1.3, 1.0, 0);
    front.castShadow = true;
    group.add(front);

    // Wheels (3)
    const wheelGeo = new THREE.CylinderGeometry(0.3, 0.3, 0.3, 24);
    wheelGeo.rotateX(Math.PI / 2);
    const wheelPositions = [
      [-0.9, 0.4, 1.0],  // front left
      [-0.9, 0.4, -1.0], // front right
      [1.1, 0.4, 0],     // rear
    ];
    for (const pos of wheelPositions) {
      const wheel = new THREE.Mesh(wheelGeo, MATS.wheel_rubber);
      wheel.position.set(pos[0], pos[1], pos[2]);
      wheel.castShadow = true;
      group.add(wheel);
    }

    // Headlight
    const lightGeo = new THREE.SphereGeometry(0.15, 12, 12);
    const hl1 = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl1.position.set(-1.6, 1.0, 0.25);
    const hl2 = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl2.position.set(-1.6, 1.0, -0.25);
    group.add(hl1, hl2);

    group.userData = { type: 'auto' };
    return group;
  }

  // --- Bike/Motorcycle ---
  function createBike(colorMat) {
    const group = new THREE.Group();

    // Frame
    const segCount = 8;
    const frameGeo = new THREE.CylinderGeometry(0.05, 0.05, 2.0, segCount);
    const frame = new THREE.Mesh(frameGeo, MATS.bike_wheel);
    frame.rotation.z = Math.PI / 2;
    frame.position.y = 0.6;
    frame.castShadow = true;
    group.add(frame);

  // Fuel tank
    const tankGeo = new THREE.SphereGeometry(0.25, 16, 16);
    const tank = new THREE.Mesh(tankGeo, colorMat);
    tank.position.set(-0.2, 0.65, 0);
    tank.castShadow = true;
    group.add(tank);

    // Wheels (2 large)
    const wheelGeo = new THREE.CylinderGeometry(0.3, 0.3, 0.12, 32);
    wheelGeo.rotateX(Math.PI / 2);
    const wheel1 = new THREE.Mesh(wheelGeo, MATS.wheel_rubber);
    wheel1.position.set(0.6, 0.4, 0);
    wheel1.castShadow = true;
    wheel1.receiveShadow = true;
    group.add(wheel1);
    const wheel2 = new THREE.Mesh(wheelGeo, MATS.wheel_rubber);
    wheel2.position.set(-0.6, 0.4, 0);
    wheel2.castShadow = true;
    wheel2.receiveShadow = true;
    group.add(wheel2);

    // Headlight
    const lightGeo = new THREE.SphereGeometry(0.12, 12, 12);
    const hl = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl.position.set(0.9, 0.5, 0);
    group.add(hl);

    group.userData = { type: 'bike' };
    return group;
  }

  // --- Ambulance ---
  function createAmbulance() {
    const group = new THREE.Group();

    // Main body (white)
    const bodyGeo = new THREE.BoxGeometry(5, 2.2, 2.2);
    const body = new THREE.Mesh(bodyGeo, MATS.car_body_white);
    body.position.y = 1.6;
    body.castShadow = true;
    group.add(body);

    // Cabin front (white rounded)
    const cabinGeo = new THREE.BoxGeometry(1.5, 2, 2.2);
    const cabin = new THREE.Mesh(cabinGeo, MATS.car_body_white);
    cabin.position.set(-2.6, 1.7, 0);
    cabin.castShadow = true;
    group.add(cabin);

    // Windshield
    const windGeo = new THREE.PlaneGeometry(1.2, 1.2);
    const windshield = new THREE.Mesh(windGeo, MATS.glass_dark);
    windshield.rotation.y = Math.PI / 2;
    windshield.position.set(-2.6, 2.2, 0);
    windshield.castShadow = true;
    group.add(windshield);

    // Red cross on doors
    function makeRedCross() {
      const crossMat = new THREE.MeshBasicMaterial({ color: 0xff3e3e, transparent: true, opacity: 0.9, toneMapped: false });
      const crossGroup = new THREE.Group();
      const hBarGeo = new THREE.BoxGeometry(0.15, 0.5, 0.05);
      const vBarGeo = new THREE.BoxGeometry(0.15, 1.0, 0.05);
      const hBar = new THREE.Mesh(hBarGeo, crossMat);
      const vBar = new THREE.Mesh(vBarGeo, crossMat);
      crossGroup.add(hBar, vBar);
      return crossGroup;
    }
    const cross1 = makeRedCross();
    cross1.position.set(-0.8, 1.6, 1.11);
    group.add(cross1);
    const cross2 = makeRedCross();
    cross2.position.set(-0.8, 1.6, -1.11);
    group.add(cross2);

    // Flashing light bar on roof
    const lightBarGeo = new THREE.BoxGeometry(3, 0.25, 0.6);
    const lightBar = new THREE.Mesh(lightBarGeo, MATS.pole_metal);
    lightBar.position.y = 3.0;
    lightBar.castShadow = true;
    group.add(lightBar);

    // Point lights on light bar (flashing)
    const flashLight1 = new THREE.PointLight(0xff3e3e, 0, 8);
    flashLight1.position.set(-1, 3.1, 0);
    scene.add(flashLight1);
    const flashLight2 = new THREE.PointLight(0x00e5ff, 0, 8);
    flashLight2.position.set(1, 3.1, 0);
    scene.add(flashLight2);

    // Wheels (4)
    const wheelGeo = new THREE.CylinderGeometry(0.35, 0.35, 0.3, 28);
    wheelGeo.rotateX(Math.PI / 2);
    const wheelPositions = [
      [-1.6, 0.8, 1.2], [-1.6, 0.8, -1.2], [1.5, 0.8, 1.2], [1.5, 0.8, -1.2]
    ];
    for (const pos of wheelPositions) {
      const wheel = new THREE.Mesh(wheelGeo, MATS.wheel_rubber);
      wheel.position.set(pos[0], pos[1], pos[2]);
      wheel.castShadow = true;
      group.add(wheel);
    }

    // Headlights
    const lightGeo = new THREE.SphereGeometry(0.18, 16, 16);
    const hl1 = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl1.position.set(-3.4, 1.8, 0.3);
    const hl2 = new THREE.Mesh(lightGeo, MATS.signal_red);
    hl2.position.set(-3.4, 1.8, -0.3);
    group.add(hl1, hl2);

    group.userData = { type: 'ambulance', flashLights: [flashLight1, flashLight2], flashState: 0 };
    return group;
  }

  // --- Traffic Signal Pole ---
  function createSignalPole(x, z) {
    const group = new THREE.Group();

    // Cantilever pole
    const poleGeo = new THREE.CylinderGeometry(0.12, 0.18, 12, 16);
    const pole = new THREE.Mesh(poleGeo, MATS.pole_metal);
    pole.position.set(x, 6, z);
    pole.castShadow = true;
    pole.receiveShadow = true;
    group.add(pole);

    // Arm
    const armGeo = new THREE.CylinderGeometry(0.1, 0.1, 8, 12);
    const arm = new THREE.Mesh(armGeo, MATS.pole_metal);
    arm.rotation.z = Math.PI / 2;
    arm.position.set(x, 11.5, z);
    arm.castShadow = true;
    group.add(arm);

    // Signal box
    const boxGeo = new THREE.BoxGeometry(0.8, 2.4, 0.4);
    const box = new THREE.Mesh(boxGeo, MATS.pole_metal);
    box.position.set(x + 4, 11.5, z);
    box.castShadow = true;
    group.add(box);

    // Signal bulbs (3: red, yellow, green)
    const bulbGeo = new THREE.SphereGeometry(0.25, 16, 16);
    const redBulb = new THREE.Mesh(bulbGeo, MATS.signal_dark);
    redBulb.position.set(x + 4, 12.4, z);
    const yellowBulb = new THREE.Mesh(bulbGeo, MATS.signal_dark);
    yellowBulb.position.set(x + 4, 11.3, z);
    const greenBulb = new THREE.Mesh(bulbGeo, MATS.signal_dark);
    greenBulb.position.set(x + 4, 10.2, z);
    group.add(redBulb, yellowBulb, greenBulb);

    // Countdown display (floating plane)
    const displayGeo = new THREE.PlaneGeometry(1.2, 0.5);
    const display = new THREE.Mesh(displayGeo, new THREE.MeshBasicMaterial({
      color: 0x0a0a0e,
      transparent: true,
      opacity: 0.9,
      toneMapped: false
    }));
    display.position.set(x + 4, 8.8, z);
    display.rotation.y = Math.PI / 2;
    group.add(display);

    // Countdown number using sprite-like plane
    const numberGeo = new THREE.PlaneGeometry(0.6, 0.35);
    const number = new THREE.Mesh(numberGeo, MATS.countdown_led);
    number.position.set(x + 4, 8.8, z + 0.01);
    number.rotation.y = Math.PI / 2;
    group.add(number);

    group.userData = {
      bulbs: { red: redBulb, yellow: yellowBulb, green: greenBulb },
      countdown: number,
      countdownValue: 30,
      phase: 'red'
    };

    return group;
  }

  // --- Intersection ---
  function createIntersection() {
    const group = new THREE.Group();

    // Road cross
    const asphaltGeo = new THREE.PlaneGeometry(60, 60);
    const asphaltMat = new THREE.MeshStandardMaterial({ color: 0x1a1a1e, roughness: 0.9, metalness: 0.1 });
    const asphalt = new THREE.Mesh(asphaltGeo, asphaltMat);
    asphalt.rotation.x = -Math.PI / 2;
    asphalt.receiveShadow = true;
    group.add(asphalt);

    // Road strips (4 directions)
    const stripMat = new THREE.MeshStandardMaterial({ color: 0x15151b, roughness: 0.9, metalness: 0.1 });
    const stripGeo = new THREE.BoxGeometry(8, 0.05, 6);

    // South approach (coming from top, going down)
    const stripS = new THREE.Mesh(stripGeo, stripMat);
    stripS.rotation.x = -Math.PI / 2;
    stripS.position.set(0, 0.02, -20);
    stripS.receiveShadow = true;
    group.add(stripS);

    // North approach
    const stripN = new THREE.Mesh(stripGeo, stripMat);
    stripN.rotation.x = -Math.PI / 2;
    stripN.position.set(0, 0.02, 20);
    stripN.receiveShadow = true;
    group.add(stripN);

    // West approach
    const stripW = new THREE.Mesh(stripGeo, stripMat);
    stripW.rotation.x = -Math.PI / 2;
    stripW.rotation.z = Math.PI / 2;
    stripW.position.set(-20, 0.02, 0);
    stripW.receiveShadow = true;
    group.add(stripW);

    // East approach
    const stripE = new THREE.Mesh(stripGeo, stripMat);
    stripE.rotation.x = -Math.PI / 2;
    stripE.rotation.z = Math.PI / 2;
    stripE.position.set(20, 0.02, 0);
    stripE.receiveShadow = true;
    group.add(stripE);

    // Stop lines
    const stopLineMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.8, toneMapped: false });
    const stopLineGeo = new THREE.PlaneGeometry(6, 0.1);
    const stopLine1 = new THREE.Mesh(stopLineGeo, stopLineMat);
    stopLine1.rotation.x = -Math.PI / 2;
    stopLine1.position.set(0, 0.01, -6);
    group.add(stopLine1);
    const stopLine2 = new THREE.Mesh(stopLineGeo, stopLineMat);
    stopLine2.rotation.x = -Math.PI / 2;
    stopLine2.position.set(0, 0.01, 6);
    group.add(stopLine2);
    const stopLine3 = new THREE.Mesh(stopLineGeo, stopLineMat);
    stopLine3.rotation.x = -Math.PI / 2;
    stopLine3.rotation.z = Math.PI / 2;
    stopLine3.position.set(-6, 0.01, 0);
    group.add(stopLine3);
    const stopLine4 = new THREE.Mesh(stopLineGeo, stopLineMat);
    stopLine4.rotation.x = -Math.PI / 2;
    stopLine4.rotation.z = Math.PI / 2;
    stopLine4.position.set(6, 0.01, 0);
    group.add(stopLine4);

    // Crosswalk markings (zebra)
    const crossMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6, toneMapped: false });
    const crossGeo = new THREE.PlaneGeometry(1, 0.4);
    for (let i = -2; i <= 2; i++) {
      // NS crosswalk
      const cw1 = new THREE.Mesh(crossGeo, crossMat);
      cw1.rotation.x = -Math.PI / 2;
      cw1.position.set(i * 1.2, 0.02, 0);
      group.add(cw1);

      // EW crosswalk
      const cw2 = new THREE.Mesh(crossGeo, crossMat);
      cw2.rotation.x = -Math.PI / 2;
      cw2.rotation.z = Math.PI / 2;
      cw2.position.set(0, 0.02, i * 1.2);
      group.add(cw2);
    }

    // Sidewalks
    const sidewalkGeo = new THREE.PlaneGeometry(60, 4);
    const sidewalkMat = new THREE.MeshStandardMaterial({ color: 0x2a2a3a, roughness: 0.95, metalness: 0.1 });
    const sw1 = new THREE.Mesh(sidewalkGeo, sidewalkMat);
    sw1.rotation.x = -Math.PI / 2;
    sw1.position.set(0, 0.01, -32);
    sw1.receiveShadow = true;
    group.add(sw1);
    const sw2 = new THREE.Mesh(sidewalkGeo, sidewalkMat);
    sw2.rotation.x = -Math.PI / 2;
    sw2.position.set(0, 0.01, 32);
    sw2.receiveShadow = true;
    group.add(sw2);
    const sw3 = new THREE.Mesh(sidewalkGeo, sidewalkMat);
    sw3.rotation.x = -Math.PI / 2;
    sw3.rotation.z = Math.PI / 2;
    sw3.position.set(-32, 0.01, 0);
    sw3.receiveShadow = true;
    group.add(sw3);
    const sw4 = new THREE.Mesh(sidewalkGeo, sidewalkMat);
    sw4.rotation.x = -Math.PI / 2;
    sw4.rotation.z = Math.PI / 2;
    sw4.position.set(32, 0.01, 0);
    sw4.receiveShadow = true;
    group.add(sw4);

    // Signal poles at each approach
    const poleN = createSignalPole(0, 8);
    group.add(poleN);
    const poleS = createSignalPole(0, -8);
    group.add(poleS);
    const poleE = createSignalPole(8, 0);
    group.add(poleE);
    const poleW = createSignalPole(-8, 0);
    group.add(poleW);

    group.userData = { poles: [poleN, poleS, poleE, poleW] };
    return group;
  }

  // --- Vehicle fleet ---
  const vehicleColors = [MATS.car_body_blue, MATS.car_body, MATS.car_body_red, MATS.car_body_silver, MATS.car_body_orange, MATS.car_body_black];
  const vehicles = [];
  const vehicleSpeeds = {};

  function spawnVehicles(scenario) {
    // Clear existing
    while (vehicles.length > 0) {
      const v = vehicles.pop();
      v.parent.remove(v);
    }

    const positions = [
      { start: [-30, 0.5, -15], dir: new THREE.Vector3(1, 0, 0), count: 4 },
      { start: [-30, 0.5, 20], dir: new THREE.Vector3(1, 0, 0), count: 3 },
      { start: [20, 0.5, -25], dir: new THREE.Vector3(0, 0, 1), count: 2 },
      { start: [30, 0.5, 0], dir: new THREE.Vector3(-1, 0, 0), count: 3 },
    ];

    let counts = [4, 3, 2, 3];
    if (scenario === 'surge') {
      counts = [8, 6, 2, 4];
    } else if (scenario === 'spillback') {
      counts = [5, 4, 3, 3];
    } else if (scenario === 'emergency') {
      counts = [3, 2, 2, 2];
    }

    let vi = 0;
    for (let approach = 0; approach < positions.length; approach++) {
      for (let i = 0; i < counts[approach]; i++) {
        let vehicle;
        const typeRand = Math.random();
        if (scenario === 'emergency' && vi === 0) {
          vehicle = createAmbulance();
        } else if (typeRand < 0.05) {
          vehicle = createAutoRickshaw(vehicleColors[Math.floor(Math.random() * vehicleColors.length)]);
        } else if (typeRand < 0.1) {
          vehicle = createBike(vehicleColors[Math.floor(Math.random() * vehicleColors.length)]);
        } else if (typeRand < 0.15) {
          vehicle = createBus(MATS.bus_body);
        } else if (typeRand < 0.2) {
          vehicle = createTruck(MATS.truck_body);
        } else {
          vehicle = createCar(vehicleColors[Math.floor(Math.random() * vehicleColors.length)]);
        }

        const p = positions[approach];
        vehicle.position.copy(p.start);
        vehicle.userData.id = vi;
        vehicle.userData.approach = approach;
        vehicle.userData.baseSpeed = 0.3 + Math.random() * 0.5;
        vehicle.userData.stopped = false;
        vehicle.userData.waitTime = 0;

        // Set initial heading
        vehicle.lookAt(vehicle.position.clone().add(p.dir));
        vehicle.userData.direction = p.dir.clone();

        scene.add(vehicle);
        vehicles.push(vehicle);
        vehicleSpeeds[vi] = vehicle.userData.baseSpeed;
        vi++;
      }
    }
  }

  // --- Animation state ---
  const state = {
    scenario: 'auto',
    mode: 'queuesense',
    camera: 'isometric',
    autoCycle: true,
    time: 0,
    step: 0,
    signalPhase: 'ns_green',
    phaseTimer: 0,
    downstreamBlockage: 0,
    density: 0.5,
  };

  // --- Create intersection ---
  const intersection = createIntersection();
  scene.add(intersection);
  spawnVehicles('auto');

  // --- Signal timing ---
  const PHASE_CYCLE = 60; // seconds for a full cycle
  const PHASE_GREEN_NS = 20; // NS green
  const PHASE_YELLOW_NS = 4;  // NS yellow
  const PHASE_GREEN_EW = 20; // EW green
  const PHASE_YELLOW_EW = 4;  // EW yellow
  const PHASE_ALL_RED = 4;    // all-red clearance

  function updateSignals(delta) {
    state.phaseTimer += delta;
    const cycle = state.phaseTimer % PHASE_CYCLE;

    const poles = intersection.userData.pols || intersection.userData.poles;
    let currentPhase = 'red';

    if (cycle < PHASE_GREEN_NS) {
      currentPhase = 'ns_green';
    } else if (cycle < PHASE_GREEN_NS + PHASE_YELLOW_NS) {
      currentPhase = 'ns_yellow';
    } else if (cycle < PHASE_GREEN_NS + PHASE_YELLOW_NS + PHASE_ALL_RED) {
      currentPhase = 'all_red';
    } else if (cycle < PHASE_GREEN_NS + PHASE_YELLOW_NS + PHASE_ALL_RED + PHASE_GREEN_EW) {
      currentPhase = 'ew_green';
    } else if (cycle < PHASE_GREEN_NS + PHASE_YELLOW_NS + PHASE_ALL_RED + PHASE_GREEN_EW + PHASE_YELLOW_EW) {
      currentPhase = 'ew_yellow';
    }

    // In queuesense mode, adjust phase durations based on queue pressure
    if (state.mode === 'queuesense') {
      // Simple adaptive: extend green for direction with more vehicles
      let nsCount = 0, ewCount = 0;
      for (const v of vehicles) {
        const angle = Math.atan2(v.userData.direction.z, v.userData.direction.x);
        if (Math.abs(angle) < Math.PI / 4 || Math.abs(angle - Math.PI) < Math.PI / 4) {
          nsCount++;
        } else {
          ewCount++;
        }
      }
      if (nsCount > ewCount * 1.5 && cycle < PHASE_GREEN_NS + 5) {
        // Extend NS green
        currentPhase = cycle < PHASE_GREEN_NS + 8 ? 'ns_green' : 'ns_yellow';
      }
    }

    // Update all poles
    for (const pole of poles) {
      const bulbs = pole.userData.bulbs;
      const isNS = (pole.position.z !== 0); // N/S poles
      const isEW = (pole.position.x !== 0); // E/W poles

      // Reset all
      bulbs.red.material = MATS.signal_dark;
      bulbs.yellow.material = MATS.signal_dark;
      bulbs.green.material = MATS.signal_dark;

      if (isNS) {
        if (currentPhase === 'ns_green' || currentPhase === 'all_red') {
          bulbs.green.material = MATS.signal_green;
        } else if (currentPhase === 'ns_yellow') {
          bulbs.yellow.material = MATS.signal_yellow;
        } else if (currentPhase === 'ew_green' || currentPhase === 'ew_yellow' || currentPhase === 'red') {
          bulbs.red.material = MATS.signal_red;
        }
      }

      if (isEW) {
        if (currentPhase === 'ew_green' || currentPhase === 'all_red') {
          bulbs.green.material = MATS.signal_green;
        } else if (currentPhase === 'ew_yellow') {
          bulbs.yellow.material = MATS.signal_yellow;
        } else if (currentPhase === 'ns_green' || currentPhase === 'ns_yellow' || currentPhase === 'red') {
          bulbs.red.material = MATS.signal_red;
        }
      }

      // Countdown
      let remaining = 0;
      if (currentPhase === 'ns_green' || currentPhase === 'ew_green') {
        remaining = Math.max(0, Math.floor(PHASE_GREEN_NS - cycle));
        pole.userData.countdown.material = new THREE.MeshBasicMaterial({
          color: 0xff4444, transparent: true, opacity: 0.9, toneMapped: false
        });
      } else {
        remaining = 0;
        pole.userData.countdown.material = new THREE.MeshBasicMaterial({
          color: 0xffaa00, transparent: true, opacity: 0.6, toneMapped: false
        });
      }
      pole.userData.countdownValue = remaining;
    }

    state.signalPhase = currentPhase;
  }

  // --- Vehicle movement ---
  function getGreenDirection() {
    const phase = state.signalPhase;
    if (phase === 'ns_green' || phase === 'ns_yellow') return 'ns';
    if (phase === 'ew_green' || phase === 'ew_yellow') return 'ew';
    return 'all_red';
  }

  function isVehicleStopped(vehicle) {
    const approach = vehicle.userData.approach;
    // North approach (approach 0,1) is NS direction
    // West approach (2) is EW direction, East approach (3) is EW direction
    const green = getGreenDirection();

    if (green === 'all_red') return true;

    if (approach === 0 || approach === 1) {
      // Coming from south going north — NS direction
      // They go through the intersection on NS green
      return green === 'ew';
    } else {
      // Coming from west going east, or east going west — EW direction
      return green === 'ns';
    }
  }

  function updateVehicles(delta) {
    for (const vehicle of vehicles) {
      const stopped = isVehicleStopped(vehicle);
      vehicle.userData.stopped = stopped;

      if (stopped) {
        vehicle.userData.waitTime += delta;
        vehicle.userData.currentSpeed = 0;

        // Brake lights on
        if (vehicle.userData.brakeLights && vehicle.userData.brakeLights) {
          for (const bl of vehicle.userData.brakeLights) {
            bl.material.emissiveIntensity = 0.5;
          }
        }
      } else {
        vehicle.userData.waitTime = 0;
        vehicle.userData.currentSpeed = vehicle.userData.baseSpeed * 0.5;

        // Brake lights off
        if (vehicle.userData.brakeLights) {
          for (const bl of vehicle.userData.brakeLights) {
            bl.material.emissiveIntensity = 0;
          }
        }
      }

      // Move the vehicle
      const speed = vehicle.userData.currentSpeed || 0;
      if (speed > 0) {
        const moveVec = vehicle.userData.direction.clone().multiplyScalar(speed * delta * 60);
        vehicle.position.add(moveVec);

        // Rotate wheels for cars/trucks/buses
        if (vehicle.userData.wheels) {
          for (const w of vehicle.userData.wheels) {
            w.rotation.z += (speed * delta * 60) / 0.4;
          }
        }
      }

      // Ambulance flashing lights
      if (vehicle.userData.type === 'ambulance') {
        vehicle.userData.flashState += delta * 4;
        if (vehicle.userData.flashState > 1) vehicle.userData.flashState = 0;
        const on = vehicle.userData.flashState < 0.5;
        if (vehicle.userData.flashLights) {
          vehicle.userData.flashLights[0].intensity = on ? 1.0 : 0;
          vehicle.userData.flashLights[1].intensity = on ? 0 : 1.0;
        }
      }

      // Reset vehicles that go off screen
      const pos = vehicle.position;
      if (Math.abs(pos.x) > 40 || Math.abs(pos.z) > 40) {
        // Respawn at original approach start
        vehicle.userData.stopped = false;
        vehicle.userData.waitTime = 0;
        const approach = vehicle.userData.approach;
        const posMap = [
          { p: new THREE.Vector3(-30, 0.5, -15), d: new THREE.Vector3(1, 0, 0) },
          { p: new THREE.Vector3(-30, 0.5, 20), d: new THREE.Vector3(1, 0, 0) },
          { p: new THREE.Vector3(20, 0.5, -25), d: new THREE.Vector3(0, 0, 1) },
          { p: new THREE.Vector3(30, 0.5, 0), d: new THREE.Vector3(-1, 0, 0) },
        ];
        const pm = posMap[approach];
        vehicle.position.copy(pm.p);
        vehicle.userData.direction = pm.d.clone();
        vehicle.lookAt(vehicle.position.clone().add(pm.d));
      }

      // Reset vehicle if too far past intersection on EW approaches
      if (pos.x > 40) {
        vehicle.position.set(-32, 0.5, pos.z);
        vehicle.userData.direction = new THREE.Vector3(1, 0, 0);
        vehicle.lookAt(vehicle.position.clone().add(vehicle.userData.direction));
      }
    }
  }

  // --- Render loop ---
  let lastTime = performance.now();
  function animate() {
    requestAnimationFrame(animate);

    const now = performance.now();
    const delta = Math.min((now - lastTime) / 1000, 0.05);
    lastTime = now;

    updateSignals(delta);
    updateVehicles(delta);

    // Update countdown timer text on signal poles
    for (const pole of intersection.userData.poles) {
      // Countdown is visual, the number mesh is just a placeholder
      // In a real implementation this would use a canvas texture
    }

    controls.update();
    renderer.render(scene, camera);
  }

  // --- Window resize ---
  window.addEventListener('resize', onWindowResize);
  function onWindowResize() {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  }

  // --- Public API ---
  window.QueueSense3D = {
    setScenario: function(s) {
      state.scenario = s;
      spawnVehicles(s);
    },
    setMode: function(m) {
      state.mode = m;
    },
    setCamera: function(c) {
      state.camera = c;
      switch (c) {
        case 'isometric':
          animateCamera(40, 30, 45, 0, 0, 0);
          break;
        case 'top':
          animateCamera(0, 45, 0.01, 0, 0, 0);
          break;
        case 'follow':
          animateCamera(0, 5, 15, 0, 0, 0);
          break;
      }
    },
    setDensity: function(d) {
      state.density = d / 100;
    },
    setDownstreamBlockage: function(b) {
      state.downstreamBlockage = b / 100;
    },
    setAutoCycle: function(v) {
      state.autoCycle = v;
    },
    updateReason: function(text) {
      const reasonEl = document.getElementById('reasonText');
      if (reasonEl) reasonEl.textContent = text;
    },
    animateCamera: animateCamera,
    getState: function() { return state; },
  };

  function animateCamera(tx, ty, tz, lx, ly, lz) {
    // Simple camera animation
    const start = { x: camera.position.x, y: camera.position.y, z: camera.position.z };
    const target = { x: tx, y: ty, z: tz };
    const lookStart = { x: controls.target.x, y: controls.target.y, z: controls.target.z };
    const lookTarget = { x: lx, y: ly, z: lz };

    let progress = 0;
    const duration = 1.5;
    const interval = 16;
    const step = interval / (duration * 1000);

    function stepAnim() {
      progress += step;
      if (progress > 1) progress = 1;
      camera.position.lerpVectors(
        new THREE.Vector3(start.x, start.y, start.z),
        new THREE.Vector3(target.x, target.y, target.z),
        progress
      );
      controls.target.lerpVectors(
        new THREE.Vector3(lookStart.x, lookStart.y, lookStart.z),
        new THREE.Vector3(lookTarget.x, lookTarget.y, lookTarget.z),
        progress
      );
      controls.update();
      if (progress < 1) {
        requestAnimationFrame(stepAnim);
      }
    }
    stepAnim();
  }

  // Start animation
  animate();

  // Export for global access
  window.__threeScene = {
    scene: scene,
    camera: camera,
    renderer: renderer,
    controls: controls,
    vehicles: vehicles,
    intersection: intersection,
    spawnVehicles: spawnVehicles,
    createCar: createCar,
    createTruck: createTruck,
    createBus: createBus,
    createAutoRickshaw: createAutoRickshaw,
    createBike: createBike,
    createAmbulance: createAmbulance,
    createSignalPole: createSignalPole,
    createIntersection: createIntersection,
  };

})();
