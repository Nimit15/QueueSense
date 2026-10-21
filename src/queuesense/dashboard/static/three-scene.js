/* =============================================================================
   QUEUESENSE ICCC — 3D LIVING DIGITAL TWIN
   Three.js WebGL corridor scene: J1 -> J1_to_J2 -> J2
   Uses GLOBAL THREE (loaded via UMD script tag). NO ES modules.

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

(function() {
  'use strict';

  var CORRIDOR_LENGTH = 60;
  var ROAD_WIDTH = 16;
  var LANE_WIDTH = 4;
  var NUM_LANES = 4;
  var JUNCTION_SIZE = 8;
  var LANE_MARKING_WIDTH = 0.15;
  var CROSSWALK_WIDTH = 3;
  var MAX_VEHICLES = 80;

  var PCU_WEIGHTS = {
    car: 1.0,
    bus: 2.2,
    auto: 1.0,
    bike: 0.5,
    truck: 2.0,
  };

  var VEHICLE_COLORS = {
    car: 0x3b82f6,
    bus: 0x10b981,
    auto: 0xf59e0b,
    bike: 0x8b5cf6,
    truck: 0xef4444,
  };

  var J1_POSITION = 0;
  var J2_POSITION = 60;
  var CORRIDOR_LENGTH_TOTAL = 120;

  var DigitalTwinScene = function(canvasContainer) {
    var self = this;
    this.container = canvasContainer;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.clock = new THREE.Clock();
    this.vehicleMeshes = [];
    this.vehicleInstances = [];
    this.vehicleTemplate = null;
    this.vehicleGroup = new THREE.Group();
    this.signalGroups = {};
    this.signalState = {
      J1: { NS: 'green', EW: 'red', yellow: 0, allRed: false },
      J2: { NS: 'green', EW: 'red', yellow: 0, allRed: false },
    };
    this.aiZones = {};
    this.spillbackZone = null;
    this.lights = {};
    this.currentPreset = 'isometric';
    this.cameraPresets = {};
    this.scenario = {
      name: 'normal',
      time: 0,
      phase: 'running',
      transitionTimer: 0,
    };
    this.isQueueSenseMode = true;
    this.frameCount = 0;
    this.lastTime = 0;
    this.onStateUpdate = null;
    this.onSignalUpdate = null;
    this.onScenarioChange = null;
    this.onModeChange = null;
    this.onZoneUpdate = null;
    this.onTelemetry = null;

    this.init();
  };

  DigitalTwinScene.prototype.init = function() {
    this.createRenderer();
    this.createScene();
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
  };

  DigitalTwinScene.prototype.createRenderer = function() {
    var self = this;
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
      stencil: false,
    });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.outputEncoding = THREE.sRGBEncoding;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.container.appendChild(this.renderer.domElement);
    this.container.id = 'three-canvas';
  };

  DigitalTwinScene.prototype.createScene = function() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x090d16);
    this.scene.fog = new THREE.FogExp2(0x090d16, 0.002);
  };

  DigitalTwinScene.prototype.createLights = function() {
    var ambient = new THREE.AmbientLight(0x404060, 1.5);
    this.scene.add(ambient);

    var sun = new THREE.DirectionalLight(0xffffff, 1.0);
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

    var hemi = new THREE.HemisphereLight(0x4a6fa5, 0x1a1a2e, 0.4);
    this.scene.add(hemi);

    this.createJunctionPoolLights();
  };

  DigitalTwinScene.prototype.createJunctionPoolLights = function() {
    var positions = { J1: J1_POSITION, J2: J2_POSITION };
    for (var jid in positions) {
      var zPos = positions[jid];
      var poolLight = new THREE.PointLight(0x10b981, 0.5, 15);
      poolLight.position.set(0, 8, zPos);
      this.scene.add(poolLight);
    }
  };

  DigitalTwinScene.prototype.createCameraPresets = function() {
    var self = this;
    var aspect = this.container.clientWidth / this.container.clientHeight;

    this.cameraPresets.isometric = new THREE.PerspectiveCamera(35, aspect, 0.1, 200);
    this.cameraPresets.isometric.position.set(-25, 20, 40);
    this.cameraPresets.isometric.lookAt(0, 0, 30);

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

    this.cameraPresets.driver = new THREE.PerspectiveCamera(50, aspect, 0.1, 200);
    this.cameraPresets.driver.position.set(0, 2, 0);
    this.cameraPresets.driver.lookAt(0, 0, 10);

    this.camera = this.cameraPresets.isometric.clone();

    // OrbitControls (available as THREE.OrbitControls from CDN)
    if (typeof THREE.OrbitControls !== 'undefined') {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.minDistance = 10;
      this.controls.maxDistance = 80;
      this.controls.maxPolarAngle = Math.PI / 2 - 0.1;
    }

    this.updateControlsForPreset(this.currentPreset);
  };

  DigitalTwinScene.prototype.updateControlsForPreset = function(preset) {
    if (preset === 'isometric' && this.controls) {
      this.controls.enabled = true;
      this.controls.target.set(0, 0, CORRIDOR_LENGTH / 2);
    } else if (this.controls) {
      this.controls.enabled = false;
    }
  };

  DigitalTwinScene.prototype.switchCameraPreset = function(presetName) {
    var target = this.cameraPresets[presetName];
    if (!target) return;

    this.currentPreset = presetName;
    if (target.isOrthographicCamera) {
      this.camera = target.clone();
      this.camera.rotation.copy(target.rotation);
      this.camera.position.copy(target.position);
    } else {
      this.camera = target.clone();
    }

    this.updateControlsForPreset(presetName);

    if (this.onPresetChange) {
      this.onPresetChange(presetName);
    }
  };

  DigitalTwinScene.prototype.createRoads = function() {
    var roadGeometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL, ROAD_WIDTH * 2.5);
    var roadMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a2e,
      roughness: 0.9,
      metalness: 0.1,
    });
    var road = new THREE.Mesh(roadGeometry, roadMaterial);
    road.rotation.x = -Math.PI / 2;
    road.receiveShadow = true;
    this.scene.add(road);

    var curbGeometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL, 0.5);
    var curbMaterial = new THREE.MeshStandardMaterial({ color: 0x1a1a3e, roughness: 0.8 });

    var curbN = new THREE.Mesh(curbGeometry, curbMaterial);
    curbN.rotation.x = -Math.PI / 2;
    curbN.position.set(0, 0.01, ROAD_WIDTH + 0.25);
    curbN.receiveShadow = true;
    this.scene.add(curbN);

    var curbS = curbN.clone();
    curbS.position.set(0, 0.01, -(ROAD_WIDTH + 0.25));
    this.scene.add(curbS);

    this.createLaneMarkings();
    this.createSideLines();
    this.createBackground();
  };

  DigitalTwinScene.prototype.createLaneMarkings = function() {
    var laneCount = NUM_LANES;
    var laneWidthMeters = ROAD_WIDTH / laneCount;
    var centerLineGeometry = new THREE.PlaneGeometry(0.1, CORRIDOR_LENGTH_TOTAL);
    var centerLineMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff, transparent: true, opacity: 0.3,
    });

    var dashGeometry = new THREE.PlaneGeometry(0.1, 2);
    var dashMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff, transparent: true, opacity: 0.8,
      emissive: 0xffffff, emissiveIntensity: 0.2,
    });

    for (var i = 0; i < laneCount - 1; i++) {
      var offset = -ROAD_WIDTH / 2 + laneWidthMeters * (i + 1);
      for (var z = 0; z < CORRIDOR_LENGTH_TOTAL; z += 4) {
        var dash = new THREE.Mesh(dashGeometry, dashMaterial);
        dash.rotation.x = -Math.PI / 2;
        dash.position.set(offset, 0.02, z - CORRIDOR_LENGTH_TOTAL / 2);
        this.scene.add(dash);
      }
    }

    var centerLine = new THREE.Mesh(centerLineGeometry, centerLineMaterial);
    centerLine.rotation.x = -Math.PI / 2;
    centerLine.position.y = 0.01;
    this.scene.add(centerLine);
  };

  DigitalTwinScene.prototype.createSideLines = function() {
    var lineGeometry = new THREE.PlaneGeometry(0.1, CORRIDOR_LENGTH_TOTAL);
    var lineMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff, transparent: true, opacity: 0.5,
    });

    var leftLine = new THREE.Mesh(lineGeometry, lineMaterial);
    leftLine.rotation.x = -Math.PI / 2;
    leftLine.position.set(-ROAD_WIDTH / 2 - 0.05, 0.02, 0);
    this.scene.add(leftLine);

    var rightLine = leftLine.clone();
    rightLine.position.set(ROAD_WIDTH / 2 + 0.05, 0.02, 0);
    this.scene.add(rightLine);
  };

  DigitalTwinScene.prototype.createBackground = function() {
    var groundGeometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL + 20, ROAD_WIDTH * 4);
    var groundMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f2020, roughness: 1.0,
    });
    var ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);

    // Simple atmospheric fog planes instead of skybox shader (avoids WebGL2 shader issues with Three.js r128)
    var fogGeometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL + 40, 40);
    var fogMaterial = new THREE.MeshStandardMaterial({
      color: 0x090d16,
      transparent: true,
      opacity: 0.3,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    var fogPlane = new THREE.Mesh(fogGeometry, fogMaterial);
    fogPlane.rotation.x = -Math.PI / 2;
    fogPlane.position.y = 5;
    this.scene.add(fogPlane);
  };

  DigitalTwinScene.prototype.createJunctions = function() {
    this.createJunction('J1', J1_POSITION);
    this.createJunction('J2', J2_POSITION);
    this.createJunctionLabels();
  };

  DigitalTwinScene.prototype.createJunction = function(jid, zPos) {
    var self = this;
    var junctionGeometry = new THREE.PlaneGeometry(JUNCTION_SIZE, JUNCTION_SIZE);
    var junctionTexture = this.createHatchTexture();
    var junctionMaterial = new THREE.MeshStandardMaterial({
      map: junctionTexture,
      color: 0x422008,
      roughness: 0.8,
      transparent: true,
      opacity: 0.7,
    });

    var junction = new THREE.Mesh(junctionGeometry, junctionMaterial);
    junction.rotation.x = -Math.PI / 2;
    junction.position.set(0, 0.03, zPos);
    junction.receiveShadow = true;
    this.scene.add(junction);

    var curbGeometry = new THREE.RingGeometry(JUNCTION_SIZE / 2, JUNCTION_SIZE / 2 + 0.3, 4);
    var curbMaterial = new THREE.MeshStandardMaterial({ color: 0x1a1a3e, roughness: 0.7 });

    var corners = [
      [-JUNCTION_SIZE / 2 - 0.15, 0, -JUNCTION_SIZE / 2 - 0.15],
      [JUNCTION_SIZE / 2 + 0.15, 0, -JUNCTION_SIZE / 2 - 0.15],
      [JUNCTION_SIZE / 2 + 0.15, 0, JUNCTION_SIZE / 2 + 0.15],
      [-JUNCTION_SIZE / 2 - 0.15, 0, JUNCTION_SIZE / 2 + 0.15],
    ];

    for (var i = 0; i < corners.length; i++) {
      var pos = corners[i];
      var curb = new THREE.Mesh(curbGeometry, curbMaterial);
      curb.position.set(pos[0], 0.05, pos[2]);
      curb.rotation.x = -Math.PI / 2;
      curb.castShadow = true;
      curb.receiveShadow = true;
      this.scene.add(curb);
    }

    this.createZebraCrossings(jid, zPos);

    this.signalGroups[jid] = {
      zPos: zPos,
      group: new THREE.Group(),
    };
  };

  DigitalTwinScene.prototype.createHatchTexture = function() {
    var canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    var ctx = canvas.getContext('2d');

    ctx.fillStyle = '#422008';
    ctx.fillRect(0, 0, 64, 64);

    ctx.strokeStyle = '#1a1a3e';
    ctx.lineWidth = 3;
    ctx.beginPath();
    for (var i = 0; i < 64; i += 8) {
      ctx.moveTo(i, 0);
      ctx.lineTo(i - 64, 64);
    }
    ctx.stroke();

    var texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(JUNCTION_SIZE / 16, JUNCTION_SIZE / 16);
    return texture;
  };

  DigitalTwinScene.prototype.createZebraCrossings = function(jid, zPos) {
    var zebraGeometry = new THREE.PlaneGeometry(2, 1.5);
    var zebraMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff, transparent: true, opacity: 0.8,
      emissive: 0xffffff, emissiveIntensity: 0.5,
    });

    var offsets = [
      [0, 0.01, -JUNCTION_SIZE / 2 - 0.75],
      [0, 0.01, JUNCTION_SIZE / 2 + 0.75],
      [-JUNCTION_SIZE / 2 - 1.0, 0.01, 0],
      [JUNCTION_SIZE / 2 + 1.0, 0.01, 0],
    ];

    for (var i = 0; i < offsets.length; i++) {
      var offset = offsets[i];
      var zebra = new THREE.Mesh(zebraGeometry, zebraMaterial);
      zebra.rotation.x = -Math.PI / 2;
      zebra.position.set(offset[0], offset[1], zPos);
      this.scene.add(zebra);
    }
  };

  DigitalTwinScene.prototype.createJunctionLabels = function() {
    var canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    var ctx = canvas.getContext('2d');
    ctx.font = '24px monospace';
    ctx.fillStyle = '#10b981';
    ctx.textAlign = 'center';
    ctx.fillText('J1', 128, 32);

    var texture = new THREE.CanvasTexture(canvas);
    var material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    var sprite = new THREE.Sprite(material);
    sprite.scale.set(10, 3, 1);
    sprite.position.set(-ROAD_WIDTH / 2 - 4, 8, J1_POSITION);
    this.scene.add(sprite);

    var canvas2 = document.createElement('canvas');
    canvas2.width = 256;
    canvas2.height = 64;
    var ctx2 = canvas2.getContext('2d');
    ctx2.font = '24px monospace';
    ctx2.fillStyle = '#10b981';
    ctx2.textAlign = 'center';
    ctx2.fillText('J2', 128, 32);

    var texture2 = new THREE.CanvasTexture(canvas2);
    var material2 = new THREE.SpriteMaterial({ map: texture2, transparent: true });
    var sprite2 = new THREE.Sprite(material2);
    sprite2.scale.set(10, 3, 1);
    sprite2.position.set(-ROAD_WIDTH / 2 - 4, 8, J2_POSITION);
    this.scene.add(sprite2);
  };

  DigitalTwinScene.prototype.createSignals = function() {
    this.createSignalAtJunction('J1', J1_POSITION);
    this.createSignalAtJunction('J2', J2_POSITION);
  };

  DigitalTwinScene.prototype.createSignalAtJunction = function(jid, zPos) {
    var group = new THREE.Group();
    group.name = jid;

    var directions = [
      { pos: [0, 4, zPos - ROAD_WIDTH - 2], rot: [0, 0, 0], name: 'NS_approach' },
      { pos: [0, 4, zPos + ROAD_WIDTH + 2], rot: [0, Math.PI, 0], name: 'NS_approach_opposite' },
      { pos: [-ROAD_WIDTH - 2, 4, zPos], rot: [0, 0, Math.PI / 2], name: 'EW_approach' },
      { pos: [ROAD_WIDTH + 2, 4, zPos], rot: [0, -Math.PI / 2, 0], name: 'EW_approach_opposite' },
    ];

    for (var i = 0; i < directions.length; i++) {
      var dir = directions[i];
      var signal = this.createSignalHead(dir.pos, dir.rot, jid, dir.name);
      group.add(signal);
    }

    this.scene.add(group);
    this.signalGroups[jid].group = group;
  };

  DigitalTwinScene.prototype.createSignalHead = function(position, rotation, junctionId, approach) {
    var group = new THREE.Group();
    group.position.set(position[0], position[1], position[2]);
    group.rotation.set(rotation[0], rotation[1], rotation[2]);

    var poleGeometry = new THREE.CylinderGeometry(0.15, 0.2, 6, 8);
    var poleMaterial = new THREE.MeshStandardMaterial({
      color: 0x1e293b, metalness: 0.8, roughness: 0.3,
    });
    var pole = new THREE.Mesh(poleGeometry, poleMaterial);
    pole.castShadow = true;
    pole.receiveShadow = true;
    group.add(pole);

    var boxGeometry = new THREE.BoxGeometry(0.8, 1.2, 0.5);
    var boxMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f172a, metalness: 0.5, roughness: 0.4,
    });
    var box = new THREE.Mesh(boxGeometry, boxMaterial);
    box.position.set(0, 5, 0);
    box.castShadow = true;
    group.add(box);

    var sphereGeometry = new THREE.SphereGeometry(0.22, 16, 16);

    var bulbPositions = [
      { y: 0.25, color: 0xff0000, name: 'red' },
      { y: 0, color: 0xffff00, name: 'yellow' },
      { y: -0.25, color: 0x00ff00, name: 'green' },
    ];

    for (var i = 0; i < bulbPositions.length; i++) {
      var bp = bulbPositions[i];
      var emissiveColor = bp.color === 0xff0000 ? new THREE.Color(0.5, 0, 0) :
                          bp.color === 0xffff00 ? new THREE.Color(0.5, 0.5, 0) :
                          new THREE.Color(0, 0.5, 0);

      var bulbMaterial = new THREE.MeshStandardMaterial({
        color: bp.color,
        emissive: emissiveColor,
        emissiveIntensity: 0,
        transparent: true,
        opacity: 0.3,
      });

      var bulb = new THREE.Mesh(sphereGeometry, bulbMaterial);
      bulb.position.set(0, bp.y, 0.35);
      bulb.userData = { color: bp.color, name: bp.name, junctionId: junctionId, approach: approach };
      group.add(bulb);

      if (!group.userData.bulbs) group.userData.bulbs = {};
      group.userData.bulbs[bp.name] = bulb;
    }

    var coverGeometry = new THREE.BoxGeometry(0.7, 1, 0.1);
    var coverMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x101020, transparent: true, opacity: 0.3,
      roughness: 0.1, metalness: 0.1, transmission: 0.5,
    });
    var cover = new THREE.Mesh(coverGeometry, coverMaterial);
    cover.position.set(0, 0, 0.55);
    group.add(cover);

    return group;
  };

  DigitalTwinScene.prototype.updateSignalColor = function(junctionId, direction, color) {
    var group = this.signalGroups[junctionId] && this.signalGroups[junctionId].group;
    if (!group) return;

    for (var i = 0; i < group.children.length; i++) {
      var signal = group.children[i];
      if (signal.userData && signal.userData.bulbs) {
        var bulbs = signal.userData.bulbs;
        for (var name in bulbs) {
          var bulb = bulbs[name];
          var bulbMat = bulb.material;
          if (name === color) {
            bulbMat.emissiveIntensity = 0.8;
            bulbMat.opacity = 1;
            bulb.scale.setScalar(1.1);
          } else {
            bulbMat.emissiveIntensity = 0;
            bulbMat.opacity = 0.3;
            bulb.scale.setScalar(1);
          }

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
        }
      }
    }
  };

  DigitalTwinScene.prototype.createVehicles = function() {
    this.vehicleGroup = new THREE.Group();
    this.scene.add(this.vehicleGroup);

    this.createVehicleInstance('car', 20);
    this.createVehicleInstance('bus', 5);
    this.createVehicleInstance('auto', 15);
    this.createVehicleInstance('bike', 20);
    this.createVehicleInstance('truck', 5);

    this.populateVehicles();
  };

  DigitalTwinScene.prototype.createVehicleInstance = function(classType, count) {
    var geometry = this.getVehicleGeometry(classType);
    var color = VEHICLE_COLORS[classType];

    var material = new THREE.MeshStandardMaterial({
      color: color,
      roughness: 0.4,
      metalness: 0.6,
      transparent: classType === 'bike',
      opacity: classType === 'bike' ? 0.8 : 1,
    });

    var instanced = new THREE.InstancedMesh(geometry, material, count);
    instanced.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    instanced.frustumCulled = false;
    instanced.userData = { classType: classType, count: count, color: color };

    this.vehicleGroup.add(instanced);
    this.vehicleInstances[classType] = { mesh: instanced, instances: [] };
  };

  DigitalTwinScene.prototype.getVehicleGeometry = function(classType) {
    var geometry;
    switch (classType) {
      case 'car': geometry = new THREE.BoxGeometry(1.2, 0.5, 2.0); break;
      case 'bus': geometry = new THREE.BoxGeometry(2.8, 0.7, 8.0); break;
      case 'auto': geometry = new THREE.BoxGeometry(0.8, 0.6, 1.6); break;
      case 'bike': geometry = new THREE.BoxGeometry(0.4, 0.3, 0.8); break;
      case 'truck': geometry = new THREE.BoxGeometry(2.0, 0.8, 5.0); break;
      default: geometry = new THREE.BoxGeometry(1.0, 0.5, 1.5);
    }

    if (THREE.BufferGeometryUtils) {
      return THREE.BufferGeometryUtils.toCreasedNormals(geometry);
    }
    return geometry;
  };

  DigitalTwinScene.prototype.populateVehicles = function() {
    for (var lane = 0; lane < 2; lane++) {
      var laneX = -ROAD_WIDTH / 4 + (lane - 0.5) * (ROAD_WIDTH / 2);
      var count = 8 + Math.floor(Math.random() * 6);
      for (var i = 0; i < count; i++) {
        var z = (i / count) * CORRIDOR_LENGTH_TOTAL - CORRIDOR_LENGTH_TOTAL / 2;
        if (z < J1_POSITION - JUNCTION_SIZE || z > J1_POSITION + JUNCTION_SIZE) {
          this.addVehicleInstance('car', laneX, z, 0, 0, Math.random() * 0.1 - 0.05);
        }
      }
    }

    for (var zi = 0; zi < [J1_POSITION, J2_POSITION].length; zi++) {
      var zPos = [J1_POSITION, J2_POSITION][zi];
      var c = 4 + Math.floor(Math.random() * 4);
      for (var j = 0; j < c; j++) {
        var x = (j / c) * ROAD_WIDTH - ROAD_WIDTH / 2;
        if (x < -JUNCTION_SIZE || x > JUNCTION_SIZE) {
          var laneZ = -ROAD_WIDTH / 4 + Math.random() * 2;
          this.addVehicleInstance('auto', x, zPos + laneZ, 0, 0, Math.PI / 2);
        }
      }

      if (Math.random() > 0.5) {
        var bx = -JUNCTION_SIZE - 5 - Math.random() * 3;
        this.addVehicleInstance('bus', bx, zPos, 0, 0, Math.PI / 2);
      }
    }

    for (var bi = 0; bi < 10; bi++) {
      var bz = Math.random() * CORRIDOR_LENGTH_TOTAL - CORRIDOR_LENGTH_TOTAL / 2;
      var bx = -ROAD_WIDTH / 2 + Math.random() * ROAD_WIDTH;
      this.addVehicleInstance('bike', bx, bz, 0, 0, Math.random() > 0.5 ? 0 : Math.PI);
    }

    for (var ti = 0; ti < 3; ti++) {
      var tz = 10 + ti * 15;
      if (tz < CORRIDOR_LENGTH_TOTAL - 10) {
        this.addVehicleInstance('truck', ROAD_WIDTH / 4, tz, 0, 0, 0);
      }
    }
  };

  DigitalTwinScene.prototype.addVehicleInstance = function(classType, x, z, y, tilt, rotation, speed) {
    if (speed === undefined) speed = 0.02;
    var instance = this.vehicleInstances[classType];
    if (!instance || !instance.instances) return;

    var instanceId = instance.instances.length;
    if (instanceId >= instance.count) return;

    var dummy = new THREE.Object3D();
    dummy.position.set(x, y + (classType === 'bike' ? 0.2 : 0.15), z);
    dummy.rotation.y = rotation;
    dummy.updateMatrix();

    instance.mesh.setMatrixAt(instanceId, dummy.matrix);

    var vehicleData = {
      id: classType + '_' + instanceId + '_' + Date.now(),
      classType: classType,
      x: x,
      z: z,
      y: y,
      rotationY: rotation,
      speed: speed * (0.5 + Math.random() * 0.5),
      targetX: x,
      targetZ: z,
      targetRotation: rotation,
      instanceId: instanceId,
      dummy: dummy,
    };

    instance.instances.push(vehicleData);
    instance.mesh.instanceMatrix.needsUpdate = true;

    return vehicleData;
  };

  DigitalTwinScene.prototype.updateVehicles = function(deltaTime) {
    for (var classType in this.vehicleInstances) {
      var instance = this.vehicleInstances[classType];
      if (!instance.instances) continue;

      for (var i = 0; i < instance.instances.length; i++) {
        var v = instance.instances[i];
        var speed = v.speed * (this.scenario.name === 'surge' ? 2 : 1);

        if (v.rotationY < Math.PI / 4 || v.rotationY > Math.PI * 6 / 4) {
          v.targetZ += speed * deltaTime * 60;
          if (v.targetZ > CORRIDOR_LENGTH_TOTAL / 2) {
            v.targetZ = -CORRIDOR_LENGTH_TOTAL / 2;
          }
        } else {
          v.targetX += speed * deltaTime * 60;
          if (Math.abs(v.targetX) > ROAD_WIDTH / 2 + 2) {
            v.targetX = -ROAD_WIDTH / 2 - 2;
          }
        }

        this.applyTrafficLightLogic(v, deltaTime);

        v.dummy.position.lerp(
          new THREE.Vector3(v.targetX, v.y + (v.classType === 'bike' ? 0.2 : 0.15), v.targetZ),
          0.1
        );
        v.dummy.rotation.y = THREE.MathUtils.damp(v.dummy.rotation.y, v.targetRotation, 2, deltaTime);
        v.dummy.updateMatrix();
        instance.mesh.setMatrixAt(v.instanceId, v.dummy.matrix);
      }

      instance.mesh.instanceMatrix.needsUpdate = true;
    }
  };

  DigitalTwinScene.prototype.applyTrafficLightLogic = function(vehicle, deltaTime) {
    var z = vehicle.z;
    var x = vehicle.x;

    var junctions = ['J1', 'J2'];
    for (var ji = 0; ji < junctions.length; ji++) {
      var jid = junctions[ji];
      var zPos = jid === 'J1' ? J1_POSITION : J2_POSITION;
      var distToJunction = Math.abs(z - zPos);

      if (distToJunction < JUNCTION_SIZE * 1.5) {
        var isStopped = vehicle.rotationY < Math.PI / 4;
        var signal = this.signalState[jid];
        var shouldStop = signal.EW === 'green' || signal.EW === 'yellow';

        if (isStopped && shouldStop) {
          vehicle.targetZ = z;
          vehicle.speed = 0;
        } else if (vehicle.speed === 0) {
          vehicle.speed = 0.02 * (0.5 + Math.random() * 0.5);
        }
      }
    }
  };

  DigitalTwinScene.prototype.createAIZones = function() {
    this.createAIDetectionZone('J1_N', new THREE.Vector3(0, 2, J1_POSITION - 10), 'north');
    this.createAIDetectionZone('J1_E', new THREE.Vector3(-10, 2, J1_POSITION), 'east');
    this.createAIDetectionZone('J2_N', new THREE.Vector3(0, 2, J2_POSITION - 10), 'north');
    this.createAIDetectionZone('exit_east', new THREE.Vector3(0, 1, J2_POSITION + 15), 'exit');
  };

  DigitalTwinScene.prototype.createAIDetectionZone = function(zoneId, position, direction) {
    var geometry = new THREE.RingGeometry(6, 8, 32);
    var material = new THREE.MeshStandardMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0.2,
      side: THREE.DoubleSide,
      emissive: 0x06b6d4,
      emissiveIntensity: 0.3,
    });

    var zone = new THREE.Mesh(geometry, material);
    zone.position.copy(position);

    if (direction === 'north' || direction === 'south') {
      zone.rotation.x = Math.PI / 2;
    } else if (direction === 'east' || direction === 'west') {
      zone.rotation.z = Math.PI / 2;
    }

    zone.userData = { zoneId: zoneId, direction: direction, pcuCount: 0 };
    this.scene.add(zone);
    this.aiZones[zoneId] = zone;

    this.animateScanLine(zone, direction);
  };

  DigitalTwinScene.prototype.animateScanLine = function(zone, direction) {
    var geometry = new THREE.PlaneGeometry(8, 0.2);
    var material = new THREE.MeshStandardMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0.6,
      emissive: 0x06b6d4,
      emissiveIntensity: 0.5,
    });

    var scanLine = new THREE.Mesh(geometry, material);
    zone.add(scanLine);

    var self = this;
    function animate() {
      if (self.scenario.phase !== 'running') return;

      var elapsed = self.clock.getElapsedTime();
      var sweep = (Math.sin(elapsed * 0.5) * 0.5 + 0.5) * 6;

      if (direction === 'north' || direction === 'south') {
        scanLine.position.z = sweep - 3;
      } else {
        scanLine.position.x = sweep - 3;
      }

      requestAnimationFrame(animate);
    }
    animate();
  };

  DigitalTwinScene.prototype.createSpillbackVisual = function() {
    var geometry = new THREE.PlaneGeometry(10, ROAD_WIDTH * 2.5);
    var material = new THREE.MeshStandardMaterial({
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
  };

  DigitalTwinScene.prototype.setSpillbackActive = function(active, occupancy) {
    if (!this.spillbackZone) return;
    if (occupancy === undefined) occupancy = 0.85;

    var material = this.spillbackZone.material;
    if (active) {
      material.opacity = 0.4 + occupancy * 0.3;
      material.emissiveIntensity = 0.3 + occupancy * 0.2;
    } else {
      material.opacity = 0;
      material.emissiveIntensity = 0;
    }
  };

  DigitalTwinScene.prototype.updateSignalPhase = function(junctionId, direction, color, duration) {
    if (!duration) duration = 0;
    this.signalState[junctionId][direction] = color;
    this.updateSignalColor(junctionId, direction, color);

    if (this.onSignalUpdate) {
      this.onSignalUpdate({
        junction: junctionId,
        direction: direction,
        color: color,
        duration: duration,
      });
    }
  };

  DigitalTwinScene.prototype.setScenario = function(scenarioName) {
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
        this.spawnSurgeVehicles();
        break;

      case 'spillback':
        this.setSpillbackActive(true, 0.85);
        this.updateSignalPhase('J1', 'NS', 'green');
        this.updateSignalPhase('J1', 'EW', 'red');
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
        this.setSpillbackActive(false);
        this.updateSignalPhase('J1', 'NS', 'green');
        this.updateSignalPhase('J1', 'EW', 'red');
        this.updateSignalPhase('J2', 'NS', 'green');
        this.updateSignalPhase('J2', 'EW', 'red');
        this.spawnAmbulance();
        break;

      case 'sensor_fault':
        this.updateSignalPhase('J1', 'NS', 'yellow');
        this.updateSignalPhase('J1', 'EW', 'red');
        this.updateSignalPhase('J2', 'NS', 'yellow');
        this.updateSignalPhase('J2', 'EW', 'red');
        break;

      case 'recovery':
        this.setSpillbackActive(false);
        this.updateSignalPhase('J1', 'NS', 'green');
        this.updateSignalPhase('J1', 'EW', 'red');
        this.updateSignalPhase('J2', 'NS', 'green');
        this.updateSignalPhase('J2', 'EW', 'red');
        break;
    }

    if (this.onScenarioChange) {
      this.onScenarioChange(scenarioName);
    }
  };

  DigitalTwinScene.prototype.spawnSurgeVehicles = function() {
    for (var i = 0; i < 15; i++) {
      var z = Math.random() * 20 - 10 + J1_POSITION;
      this.addVehicleInstance('car', ROAD_WIDTH / 4 + 1, z, 0, 0, 0, 0.05);
    }
    for (var j = 0; j < 5; j++) {
      var zb = Math.random() * 15 + J1_POSITION;
      this.addVehicleInstance('bus', ROAD_WIDTH / 4 + 1, zb, 0, 0, 0, 0.04);
    }
  };

  DigitalTwinScene.prototype.spawnAmbulance = function() {
    var geometry = new THREE.BoxGeometry(1.0, 0.6, 2.5);
    var material = new THREE.MeshStandardMaterial({
      color: 0xef4444,
      emissive: 0xef4444,
      emissiveIntensity: 0.5,
    });

    var ambulance = new THREE.Mesh(geometry, material);
    ambulance.position.set(0, 0.5, J1_POSITION - 15);
    ambulance.rotation.y = 0;
    ambulance.userData = { type: 'ambulance', corridorPos: 0 };
    this.scene.add(ambulance);
    this.ambulance = ambulance;

    var lightGeometry = new THREE.SphereGeometry(0.2, 8, 8);
    var redLight = new THREE.Mesh(lightGeometry, new THREE.MeshBasicMaterial({ color: 0xff0000 }));
    redLight.position.set(-0.5, 0.8, 0);
    ambulance.add(redLight);

    var blueLight = new THREE.Mesh(lightGeometry, new THREE.MeshBasicMaterial({ color: 0x0000ff }));
    blueLight.position.set(0.5, 0.8, 0);
    ambulance.add(blueLight);

    this.ambulanceLights = { red: redLight, blue: blueLight, ambulance: ambulance };
  };

  DigitalTwinScene.prototype.updateAmbulance = function(deltaTime) {
    if (!this.ambulance) return;

    var speed = 0.5 * deltaTime * 60;
    this.ambulance.position.z += speed;

    var elapsed = this.clock.getElapsedTime();
    if (this.ambulanceLights) {
      var intensity = Math.abs(Math.sin(elapsed * 10)) * 0.5 + 0.5;
      this.ambulanceLights.red.material.emissiveIntensity = intensity;
      this.ambulanceLights.blue.material.emissiveIntensity = intensity;
    }

    if (this.ambulance.position.z > J2_POSITION + 5) {
      this.ambulance = null;
      this.ambulanceLights = null;
      this.setScenario('recovery');
    }
  };

  DigitalTwinScene.prototype.setMode = function(mode) {
    this.isQueueSenseMode = mode === 'queuesense';

    if (this.isQueueSenseMode) {
      for (var id in this.aiZones) {
        this.aiZones[id].visible = true;
      }
      var sc = this.scenario.name;
      this.setSpillbackActive(sc === 'spillback' || sc === 'bottleneck');
    } else {
      for (var id2 in this.aiZones) {
        this.aiZones[id2].visible = false;
      }

      var sc2 = this.scenario.name;
      if (sc2 === 'spillback' || sc2 === 'bottleneck') {
        this.setGridlockVisualization(true);
      } else {
        this.setGridlockVisualization(false);
      }
    }

    if (this.onModeChange) {
      this.onModeChange(this.isQueueSenseMode);
    }
  };

  DigitalTwinScene.prototype.setGridlockVisualization = function(active) {
    if (active) {
      var geometry = new THREE.PlaneGeometry(CORRIDOR_LENGTH_TOTAL, ROAD_WIDTH * 3);
      var material = new THREE.MeshStandardMaterial({
        color: 0x7f1d1d,
        transparent: true,
        opacity: 0.3,
        side: THREE.DoubleSide,
        depthWrite: false,
      });

      var overlay = new THREE.Mesh(geometry, material);
      overlay.rotation.x = -Math.PI / 2;
      overlay.position.y = 0.02;
      this.scene.add(overlay);
      this.gridlockOverlay = overlay;
    } else {
      if (this.gridlockOverlay) {
        this.scene.remove(this.gridlockOverlay);
        this.gridlockOverlay.geometry.dispose();
        this.gridlockOverlay.material.dispose();
        this.gridlockOverlay = null;
      }
    }

    Object.keys(this.vehicleInstances).forEach(function(classType) {
      var instance = self.vehicleInstances[classType];
      if (instance && instance.instances) {
        instance.instances.forEach(function(v) {
          v.speed = v.speed * (active ? 0.3 : 3.3);
        });
      }
    });
  };

  DigitalTwinScene.prototype.updateScenarioEngine = function(deltaTime) {
    this.scenario.time += deltaTime;
    this.scenario.transitionTimer += deltaTime;

    if (this.scenario.phase === 'running') {
      var durations = {
        normal: 30,
        surge: 20,
        spillback: 25,
        emergency: 15,
        recovery: 15,
        sensor_fault: 10,
      };

      var duration = durations[this.scenario.name] || 15;

      if (this.scenario.transitionTimer > duration) {
        var nextScenario = this.getNextScenario();
        this.setScenario(nextScenario);
        this.scenario.transitionTimer = 0;
      }
    }

    this.updateZonePCUs();
    this.updateSignalCycle(deltaTime);
    this.updatePedestrianFlash(deltaTime);
  };

  DigitalTwinScene.prototype.getNextScenario = function() {
    var sequence = ['normal', 'surge', 'spillback', 'emergency', 'recovery', 'normal'];
    var currentIndex = sequence.indexOf(this.scenario.name);
    return sequence[(currentIndex + 1) % sequence.length];
  };

  DigitalTwinScene.prototype.updateZonePCUs = function() {
    for (var id in this.aiZones) {
      var zone = this.aiZones[id];
      var count = Math.floor(Math.random() * 8) + 1;
      zone.userData.pcuCount = count;

      var material = zone.material;
      var intensity = Math.min(count / 12, 1);
      material.opacity = 0.2 + intensity * 0.3;
      material.emissiveIntensity = 0.3 + intensity * 0.4;
    }

    if (this.onZoneUpdate) {
      var zones = {};
      for (var id2 in this.aiZones) {
        zones[id2] = this.aiZones[id2].userData.pcuCount;
      }
      this.onZoneUpdate(zones);
    }
  };

  DigitalTwinScene.prototype.updateSignalCycle = function(deltaTime) {
    this.signalTime = (this.signalTime || 0) + deltaTime;

    if (this.signalTime > 30) {
      this.signalTime = 0;

      var states = this.signalState;
      for (var jid in states) {
        var state = states[jid];
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
  };

  DigitalTwinScene.prototype.updatePedestrianFlash = function(deltaTime) {
    var elapsed = this.clock.getElapsedTime();
    if (Math.floor(elapsed) % 2 === 0 && this.pedestrianCrossing) {
      this.pedestrianCrossing.material.emissiveIntensity = Math.abs(Math.sin(elapsed * 3)) * 0.5;
    }
  };

  DigitalTwinScene.prototype.animate = function() {
    var self = this;
    var deltaTime = Math.min(this.clock.getDelta(), 0.1);
    this.frameCount++;

    if (this.controls && this.controls.enabled) {
      this.controls.update();
    }

    this.updateVehicles(deltaTime);

    if (this.ambulance) {
      this.updateAmbulance(deltaTime);
    }

    this.updateScenarioEngine(deltaTime);

    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }

    if (this.frameCount % 60 === 0 && this.onTelemetry) {
      this.onTelemetry({
        fps: Math.round(1 / deltaTime),
        vehicles: this.getTotalVehicleCount(),
        scenario: this.scenario.name,
        mode: this.isQueueSenseMode ? 'queuesense' : 'traditional',
      });
    }

    requestAnimationFrame(function() { self.animate(); });
  };

  DigitalTwinScene.prototype.getTotalVehicleCount = function() {
    var total = 0;
    for (var classType in this.vehicleInstances) {
      var instance = this.vehicleInstances[classType];
      if (instance && instance.instances) {
        total += instance.instances.length;
      }
    }
    return total;
  };

  DigitalTwinScene.prototype.setupEventListeners = function() {
    var self = this;
    window.addEventListener('resize', function() { self.onWindowResize(); });
  };

  DigitalTwinScene.prototype.onWindowResize = function() {
    var width = this.container.clientWidth;
    var height = this.container.clientHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(window.devicePixelRatio);
  };

  DigitalTwinScene.prototype.destroy = function() {
    this.controls && this.controls.dispose();
    this.renderer && this.renderer.dispose();
    this.scene && this.scene.clear();

    if (this.container.contains(this.renderer.domElement)) {
      this.container.removeChild(this.renderer.domElement);
    }
  };

  /* =============================================================================
     GLOBAL EXPOSURE
     ============================================================================= */

  var twinScene = null;

  window.initDigitalTwin = function(canvasContainer) {
    twinScene = new DigitalTwinScene(canvasContainer);

    twinScene.onStateUpdate = function(state) {
      if (window.onTwinStateUpdate) window.onTwinStateUpdate(state);
    };
    twinScene.onSignalUpdate = function(signal) {
      if (window.onSignalUpdate) window.onSignalUpdate(signal);
    };
    twinScene.onScenarioChange = function(scenario) {
      if (window.onScenarioChange) window.onScenarioChange(scenario);
    };
    twinScene.onModeChange = function(isQueueSense) {
      if (window.onModeChange) window.onModeChange(isQueueSense);
    };
    twinScene.onZoneUpdate = function(zones) {
      if (window.onZoneUpdate) window.onZoneUpdate(zones);
    };
    twinScene.onTelemetry = function(stats) {
      if (window.onTwinTelemetry) window.onTwinTelemetry(stats);
    };

    return twinScene;
  };

  window.getTwinScene = function() {
    return twinScene;
  };

  window.switchCameraPreset = function(preset) {
    if (twinScene) twinScene.switchCameraPreset(preset);
  };

  window.setScenario = function(scenario) {
    if (twinScene) twinScene.setScenario(scenario);
  };

  window.setMode = function(mode) {
    if (twinScene) twinScene.setMode(mode);
  };

  window.triggerEmergencyFlush = function() {
    if (twinScene) twinScene.setScenario('emergency');
  };

  window.setSpillbackActive = function(active, occupancy) {
    if (twinScene) twinScene.setSpillbackActive(active, occupancy);
  };

  window.updateSignalPhase = function(junctionId, direction, color, duration) {
    if (twinScene) twinScene.updateSignalPhase(junctionId, direction, color, duration);
  };
})();