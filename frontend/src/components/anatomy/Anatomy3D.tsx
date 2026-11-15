import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import {
  Brain,
  Heart,
  Activity,
  Bone,
  RotateCw,
  Maximize2,
  Scan,
  Compass,
} from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { statusMeta } from '../../utils/status';
import { AnatomyZoneId } from '../../types/telemetry';
import { playUiBeep } from '../../utils/audio';

interface Anatomy3DProps {
  onSelectZone?: (zone: AnatomyZoneId) => void;
  fullPageView?: boolean;
}

type LayerMode = 'all' | 'organs' | 'skeleton' | 'vessels' | 'skin_only';

export const Anatomy3D: React.FC<Anatomy3DProps> = ({ onSelectZone, fullPageView = false }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cardContainerRef = useRef<HTMLDivElement>(null);
  const { vitals, selectedAnatomyZone, setSelectedAnatomyZone, astronaut } = useTelemetry();
  const { t } = usePrefs();
  const metricText = (value: number, unit: string) => Number.isFinite(value) ? `${value} ${unit}` : t('Kayıt yok', 'No record');
  const worst = (...st: string[]) => (st.includes('critical') ? 'critical' : st.includes('warning') ? 'warning' : 'normal') as 'normal' | 'warning' | 'critical';
  const zoneStatus = {
    head: statusMeta(vitals.sleep.status, t),
    chest: statusMeta(worst(vitals.pulse.status, vitals.bp_systolic.status, vitals.bp_diastolic.status), t),
    abdomen: statusMeta(worst(vitals.glucose.status, vitals.temperature.status), t),
    musculoskeletal: statusMeta('normal', t),
  };

  const [hoveredZone, setHoveredZone] = useState<AnatomyZoneId | null>(null);
  const [hoveredMeshName, setHoveredMeshName] = useState<string | null>(null);
  const [isRotating, setIsRotating] = useState(true);
  const [activeLayer, setActiveLayer] = useState<LayerMode>('all');
  const [selectedGender, setSelectedGender] = useState<'female' | 'male'>(
    astronaut.sex === 'M' ? 'male' : 'female'
  );
  const [loadingProgress, setLoadingProgress] = useState<number>(0);
  const [isModelLoaded, setIsModelLoaded] = useState<boolean>(false);

  // Synchronize gender with astronaut profile
  useEffect(() => {
    if (astronaut.sex === 'M') {
      setSelectedGender('male');
    } else {
      setSelectedGender('female');
    }
  }, [astronaut.id, astronaut.sex]);

  // Three.js References
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);
  const heartMeshRef = useRef<THREE.Mesh | null>(null);
  const initialHeartScaleRef = useRef<THREE.Vector3 | null>(null);
  const animFrameIdRef = useRef<number | null>(null);
  const raycasterRef = useRef<THREE.Raycaster>(new THREE.Raycaster());
  const mousePosRef = useRef<THREE.Vector2>(new THREE.Vector2());

  // Categorize mesh into one of the 4 required zones
  const getZoneFromMeshName = useCallback((name: string): AnatomyZoneId | null => {
    const lower = name.toLowerCase();
    if (lower.includes('brain') || lower.includes('head') || lower.includes('cranium') || lower.includes('eye')) {
      return 'head';
    }
    if (
      lower.includes('heart') ||
      lower.includes('lung') ||
      lower.includes('aorta') ||
      lower.includes('thorax') ||
      lower.includes('coronary') ||
      lower.includes('chest')
    ) {
      return 'chest';
    }
    if (
      lower.includes('liver') ||
      lower.includes('stomach') ||
      lower.includes('intestine') ||
      lower.includes('abdomen') ||
      lower.includes('kidney') ||
      lower.includes('pelvis') ||
      lower.includes('urinary')
    ) {
      return 'abdomen';
    }
    if (
      lower.includes('skeleton') ||
      lower.includes('bone') ||
      lower.includes('muscle') ||
      lower.includes('femur') ||
      lower.includes('tibia') ||
      lower.includes('arm') ||
      lower.includes('leg') ||
      lower.includes('joint')
    ) {
      return 'musculoskeletal';
    }
    return null;
  }, []);

  // Update visibility and materials when activeLayer changes
  const applyLayerVisibility = useCallback((group: THREE.Group, layer: LayerMode) => {
    group.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        const name = (mesh.name || '').toLowerCase();
        const parentName = (mesh.parent?.name || '').toLowerCase();

        // Check category
        const isSkin = name.includes('skin') || parentName.includes('skin');
        const isSkeleton =
          name.includes('skeleton') ||
          name.includes('bone') ||
          name.includes('spine') ||
          name.includes('femur') ||
          name.includes('ribs') ||
          name.includes('skull') ||
          name.includes('pelvis') ||
          name.includes('sternum') ||
          name.includes('clavicle') ||
          name.includes('patella') ||
          parentName.includes('skeleton');
        const isVessel =
          name.includes('vessel') ||
          name.includes('arter') ||
          name.includes('vein') ||
          name.includes('aorta') ||
          parentName.includes('vessels');
        const isMuscle = name.includes('muscle') || parentName.includes('muscles') || name.includes('deltoid');
        const isOrgan =
          name.includes('organ') ||
          name.includes('heart') ||
          name.includes('lung') ||
          name.includes('brain') ||
          name.includes('liver') ||
          name.includes('stomach') ||
          name.includes('intestine') ||
          name.includes('kidney') ||
          parentName.includes('organs');

        switch (layer) {
          case 'all':
            mesh.visible = true;
            if (isSkin && mesh.material) {
              (mesh.material as THREE.Material).opacity = 0.22;
              (mesh.material as THREE.Material).transparent = true;
            }
            break;
          case 'organs':
            mesh.visible = isOrgan || isVessel || isSkin;
            if (isSkin && mesh.material) {
              (mesh.material as THREE.Material).opacity = 0.08;
              (mesh.material as THREE.Material).transparent = true;
            }
            break;
          case 'skeleton':
            mesh.visible = isSkeleton;
            break;
          case 'vessels':
            mesh.visible = isVessel || (isOrgan && (name.includes('heart') || name.includes('lung')));
            break;
          case 'skin_only':
            mesh.visible = isSkin;
            if (isSkin && mesh.material) {
              (mesh.material as THREE.Material).opacity = 0.65;
            }
            break;
        }
      }
    });
  }, []);

  // Initialize Three.js Scene and Load Open Anatomy 3D GLB Model
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth || 450;
    const height = container.clientHeight || (fullPageView ? 650 : 540);

    // 1. Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000);
    camera.position.set(0, 0, 3.4);
    cameraRef.current = camera;

    // 3. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = false;
    rendererRef.current = renderer;

    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // 4. OrbitControls (Full 360 drag rotation, smooth damping, zoom)
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.rotateSpeed = 0.7;
    controls.zoomSpeed = 0.8;
    controls.enableZoom = fullPageView;
    controls.minDistance = 1.4;
    controls.maxDistance = 6.0;
    controls.target.set(0, 0, 0);
    controlsRef.current = controls;

    // 5. Sci-Fi Biomedical Lighting Setup
    const ambientLight = new THREE.AmbientLight(0xdbeafe, 1.4);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0x38bdf8, 2.5);
    keyLight.position.set(4, 6, 5);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x00f0ff, 2.0);
    rimLight.position.set(-4, -2, -4);
    scene.add(rimLight);

    const frontPulseLight = new THREE.PointLight(0xef4444, 1.5, 6);
    frontPulseLight.position.set(0, 0.3, 1.2);
    scene.add(frontPulseLight);

    // 6. Background Hologram Stage (Pedestal & Rings matching reference image)
    const stageGroup = new THREE.Group();
    scene.add(stageGroup);

    // Rotating Holographic Rings
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
    });
    const bigBackRing = new THREE.Mesh(new THREE.TorusGeometry(1.6, 0.012, 16, 90), ringMat);
    bigBackRing.position.set(0, 0, -0.4);
    stageGroup.add(bigBackRing);

    const dashedRing = new THREE.Mesh(
      new THREE.TorusGeometry(1.8, 0.016, 12, 60),
      new THREE.MeshBasicMaterial({ color: 0x0284c7, wireframe: true, transparent: true, opacity: 0.25 })
    );
    dashedRing.position.set(0, 0, -0.5);
    stageGroup.add(dashedRing);

    // Circular Feet Pedestal Platform (multi-tiered glowing cyan discs)
    const pedestalGroup = new THREE.Group();
    pedestalGroup.position.set(0, -1.2, 0);

    const disc1 = new THREE.Mesh(
      new THREE.RingGeometry(0.7, 0.78, 48),
      new THREE.MeshBasicMaterial({ color: 0x00f0ff, side: THREE.DoubleSide, transparent: true, opacity: 0.7 })
    );
    disc1.rotation.x = Math.PI / 2;
    pedestalGroup.add(disc1);

    const disc2 = new THREE.Mesh(
      new THREE.RingGeometry(0.9, 0.95, 48),
      new THREE.MeshBasicMaterial({ color: 0x0284c7, side: THREE.DoubleSide, transparent: true, opacity: 0.4 })
    );
    disc2.rotation.x = Math.PI / 2;
    pedestalGroup.add(disc2);

    stageGroup.add(pedestalGroup);

    // 7. Load Real Open Anatomy 3D Model
    const modelGroup = new THREE.Group();
    modelGroupRef.current = modelGroup;
    scene.add(modelGroup);

    setIsModelLoaded(false);
    setLoadingProgress(10);

    const modelPath = selectedGender === 'female' ? '/models/anatomy-female.glb' : '/models/anatomy-male.glb';
    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);

    loader.load(
      modelPath,
      (gltf) => {
        const root = gltf.scene;

        // Auto-center and normalize human body scale
        const box = new THREE.Box3().setFromObject(root);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());

        // Target height ~2.1 units in 3D scene
        const maxAxis = Math.max(size.x, size.y, size.z);
        const targetScale = 2.05 / maxAxis;
        root.scale.set(targetScale, targetScale, targetScale);

        // Center vertically so feet touch pedestal at y = -1.0
        root.position.x = -center.x * targetScale;
        root.position.y = -center.y * targetScale;
        root.position.z = -center.z * targetScale;

        // Apply authentic medical hologram shaders matching the user's reference image
        root.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const mesh = child as THREE.Mesh;
            const name = (mesh.name || '').toLowerCase();
            const parentName = (mesh.parent?.name || '').toLowerCase();

            // 1. SKIN / SPACESUIT: Translucent glowing electric blue hologram
            if (name.includes('skin') || parentName.includes('skin')) {
              mesh.material = new THREE.MeshPhysicalMaterial({
                color: 0x0284c7,
                emissive: 0x00f0ff,
                emissiveIntensity: 0.25,
                transparent: true,
                opacity: 0.22,
                roughness: 0.15,
                metalness: 0.1,
                transmission: 0.85,
                ior: 1.35,
                side: THREE.DoubleSide,
                depthWrite: false,
              });
            }
            // 2. HEART & LUNGS (Göğüs): Glowing Red & Coral
            else if (
              name.includes('heart') ||
              name.includes('lung') ||
              name.includes('aorta') ||
              name.includes('coronary')
            ) {
              mesh.material = new THREE.MeshStandardMaterial({
                color: 0xf87171,
                emissive: 0xef4444,
                emissiveIntensity: 0.85,
                roughness: 0.2,
                transparent: true,
                opacity: 0.95,
              });
              if (name.includes('heart')) {
                heartMeshRef.current = mesh;
                initialHeartScaleRef.current = mesh.scale.clone();
              }
            }
            // 3. DIGESTIVE & ABDOMEN (Metabolizma): Glowing Orange & Amber
            else if (
              name.includes('stomach') ||
              name.includes('liver') ||
              name.includes('intestine') ||
              name.includes('digest') ||
              name.includes('kidney')
            ) {
              mesh.material = new THREE.MeshStandardMaterial({
                color: 0xfb923c,
                emissive: 0xf97316,
                emissiveIntensity: 0.75,
                roughness: 0.25,
                transparent: true,
                opacity: 0.9,
              });
            }
            // 4. SKELETON / BONES (Kas-İskelet): Glowing Cyan & Light Blue
            else if (name.includes('skeleton') || name.includes('bone') || parentName.includes('skeleton')) {
              mesh.material = new THREE.MeshStandardMaterial({
                color: 0x93c5fd,
                emissive: 0x0284c7,
                emissiveIntensity: 0.45,
                roughness: 0.35,
                transparent: true,
                opacity: 0.75,
              });
            }
            // 5. BRAIN / HEAD (Baş & Zihin): Glowing Electric Blue & Cyan
            else if (name.includes('brain') || name.includes('head') || parentName.includes('nerves')) {
              mesh.material = new THREE.MeshStandardMaterial({
                color: 0x38bdf8,
                emissive: 0x00f0ff,
                emissiveIntensity: 0.8,
                roughness: 0.25,
                transparent: true,
                opacity: 0.85,
              });
            }
            // 6. MUSCLES / VESSELS: Subtle translucent cyan/blue
            else {
              mesh.material = new THREE.MeshStandardMaterial({
                color: 0x38bdf8,
                emissive: 0x0284c7,
                emissiveIntensity: 0.3,
                roughness: 0.4,
                transparent: true,
                opacity: 0.5,
              });
            }
          }
        });

        modelGroup.add(root);
        applyLayerVisibility(modelGroup, activeLayer);
        setIsModelLoaded(true);
        setLoadingProgress(100);
      },
      (xhr) => {
        if (xhr.total > 0) {
          setLoadingProgress(Math.round((xhr.loaded / xhr.total) * 100));
        }
      },
      (err) => {
        console.error('Error loading Open Anatomy 3D GLB model:', err);
        setIsModelLoaded(true); // Don't block screen on error
      }
    );

    // 8. Animation Render Loop
    let clock = new THREE.Clock();
    const animate = () => {
      animFrameIdRef.current = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Controls damping update
      controls.update();

      // Auto rotation if enabled
      if (isRotating && modelGroupRef.current) {
        modelGroupRef.current.rotation.y += 0.005;
      }

      // Slow orbital ring rotation
      bigBackRing.rotation.z = elapsed * 0.05;
      dashedRing.rotation.z = -elapsed * 0.03;
      disc1.rotation.z = elapsed * 0.15;
      disc2.rotation.z = -elapsed * 0.1;

      // Realistic heartbeat pulse synchronized with astronaut pulse rate
      if (heartMeshRef.current && initialHeartScaleRef.current) {
        const base = initialHeartScaleRef.current;
        const pulse = vitals.pulse?.value;
        const pulseRateHz = (Number.isFinite(pulse) ? pulse / 60 : 0) * Math.PI * 2;
        const beatFactor = 1.0 + Math.pow(Math.sin(elapsed * pulseRateHz), 6) * 0.08;
        heartMeshRef.current.scale.set(
          base.x * beatFactor,
          base.y * beatFactor,
          base.z * beatFactor
        );
      }

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!containerRef.current || !rendererRef.current || !cameraRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight || (fullPageView ? 650 : 540);
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(w, h);
    };

    // Kapsayıcının boyutu değiştiğinde (sütun genişliği, tema, sekme) canvas'ı uyarla
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
      controls.dispose();
      renderer.dispose();
    };
  }, [selectedGender, fullPageView, applyLayerVisibility]);

  // Update layer visibility when activeLayer changes
  useEffect(() => {
    if (modelGroupRef.current) {
      applyLayerVisibility(modelGroupRef.current, activeLayer);
    }
  }, [activeLayer, applyLayerVisibility]);

  // Raycasting on Mouse Move (highlight hovered organ)
  const handlePointerMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current || !cameraRef.current || !modelGroupRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    mousePosRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mousePosRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mousePosRef.current, cameraRef.current);
    const intersects = raycasterRef.current.intersectObjects(modelGroupRef.current.children, true);

    if (intersects.length > 0) {
      const topMesh = intersects[0].object as THREE.Mesh;
      const meshName = topMesh.name || topMesh.parent?.name || '';
      setHoveredMeshName(meshName);
      const zone = getZoneFromMeshName(meshName);
      if (zone) {
        setHoveredZone(zone);
      }
    } else {
      setHoveredMeshName(null);
      setHoveredZone(null);
    }
  };

  // Reset 3D Camera Pose
  const handleResetCamera = () => {
    playUiBeep(650);
    if (controlsRef.current && cameraRef.current && modelGroupRef.current) {
      controlsRef.current.reset();
      cameraRef.current.position.set(0, 0, 3.4);
      controlsRef.current.target.set(0, 0, 0);
      modelGroupRef.current.rotation.set(0, 0, 0);
    }
  };

  const handleZoneClick = (zone: AnatomyZoneId) => {
    playUiBeep(980);
    setSelectedAnatomyZone(zone);
    if (onSelectZone) onSelectZone(zone);
  };

  const activeZone = hoveredZone || selectedAnatomyZone;

  return (
    <div
      ref={cardContainerRef}
      className="relative w-full h-full flex flex-col items-center justify-between overflow-hidden bg-gradient-to-b from-sky-50/60 via-white/40 to-blue-50/60 backdrop-blur-xl rounded-2xl border neon-frame shadow-card p-4 select-none"
    >
      {/* Top Header Bar */}
      <div className="w-full flex flex-wrap items-center justify-between border-b border-sky-200/70 pb-3 gap-2 z-30">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 via-sky-500 to-cyan-400 p-0.5 shadow-sm flex items-center justify-center text-white">
            <Scan className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-slate-900">
                {t('Vücut Haritası', 'Body Map')}
              </h2>
            </div>
            <p className="text-xs text-slate-500">
              {t('Bir bölgeye tıklayarak durumunu görün', 'Click an area to see its status')}
            </p>
          </div>
        </div>

        {/* 3D Action Controls: Layer Switcher, Gender Switcher, Auto-Rotate */}
        <div className="flex items-center space-x-1.5 bg-white/95 p-1 rounded-xl border border-sky-200 shadow-sm backdrop-blur">
          {/* Gender Model Switcher */}
          <div className="flex items-center bg-slate-100/90 p-0.5 rounded-lg border border-slate-200">
            <button
              onClick={() => {
                playUiBeep(700);
                setSelectedGender('female');
              }}
              className={`px-2 py-1 rounded text-xs font-bold transition-all ${
                selectedGender === 'female' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600'
              }`}
              title={t('Kadın model', 'Female model')}
            >
              {t('Kadın', 'Female')}
            </button>
            <button
              onClick={() => {
                playUiBeep(700);
                setSelectedGender('male');
              }}
              className={`px-2 py-1 rounded text-xs font-bold transition-all ${
                selectedGender === 'male' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600'
              }`}
              title={t('Erkek model', 'Male model')}
            >
              {t('Erkek', 'Male')}
            </button>
          </div>

          {/* Layer Selector */}
          <select
            value={activeLayer}
            onChange={(e) => {
              playUiBeep(700);
              setActiveLayer(e.target.value as LayerMode);
            }}
            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-white text-slate-700 border border-slate-200 hover:border-sky-300 transition-colors cursor-pointer outline-none"
          >
            <option value="all">{t('Tüm katmanlar', 'All layers')}</option>
            <option value="organs">{t('İç organlar', 'Organs')}</option>
            <option value="skeleton">{t('İskelet', 'Skeleton')}</option>
            <option value="vessels">{t('Kalp & damarlar', 'Heart & vessels')}</option>
            <option value="skin_only">{t('Sadece dış yüzey', 'Outer surface')}</option>
          </select>

          {/* Auto-Rotate Toggle */}
          <button
            onClick={() => {
              playUiBeep(700);
              setIsRotating(!isRotating);
            }}
            className={`p-1.5 rounded-lg text-xs transition-colors ${
              isRotating ? 'bg-blue-600 text-white shadow-xs' : 'text-slate-600 hover:bg-slate-100'
            }`}
            title={isRotating ? t('Dönüşü durdur', 'Pause rotation') : t('Otomatik döndür', 'Auto-rotate')}
            aria-label={isRotating ? t('Dönüşü durdur', 'Pause rotation') : t('Otomatik döndür', 'Auto-rotate')}
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRotating ? 'animate-spin' : ''}`} style={{ animationDuration: '6s' }} />
          </button>

          {/* Reset Camera Pose */}
          <button
            onClick={handleResetCamera}
            className="p-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100 transition-colors"
            title={t('Açıyı sıfırla', 'Reset view')}
            aria-label={t('Açıyı sıfırla', 'Reset view')}
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main 3D Viewport Area */}
      <div
        className="relative w-full flex-1 flex items-center justify-center min-h-[460px] cursor-grab active:cursor-grabbing overflow-hidden"
        onMouseMove={handlePointerMove}
      >
        {/* Loading Progress Overlay */}
        {!isModelLoaded && (
          <div className="absolute inset-0 z-40 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center space-y-3">
            <div className="w-10 h-10 rounded-full border-4 border-blue-600 border-t-transparent animate-spin" />
            <div className="text-xs font-bold text-slate-800">
              {t('3D model yükleniyor', 'Loading 3D model')}… {loadingProgress}%
            </div>
            <p className="text-xs text-slate-600">
              {t('130+ organ ve kemik hazırlanıyor', 'Preparing 130+ organs and bones')}
            </p>
          </div>
        )}

        {/* Dynamic Holographic Scanner Laser Beam Sweeping */}
        <div
          className="absolute inset-x-8 h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-glow-cyan pointer-events-none z-10 opacity-70 animate-pulse"
          style={{
            animation: 'scanMove 5s ease-in-out infinite alternate',
          }}
        />
        <style>{`
          @keyframes scanMove {
            0% { top: 10%; }
            100% { top: 88%; }
          }
        `}</style>

        {/* Real Three.js Canvas with Open Anatomy 3D GLB Model */}
        <div ref={containerRef} className="w-full h-full" />

        {/* ======================================================== */}
        {/* EXACT REFERENCE CALLOUT PILLS WITH CONNECTOR LINES        */}
        {/* ======================================================== */}

        {/* 1. BAŞ PILL (Top-Right) */}
        <div
          className="absolute top-[8%] right-[4%] z-30 group cursor-pointer"
          onMouseEnter={() => setHoveredZone('head')}
          onMouseLeave={() => setHoveredZone(null)}
          onClick={() => handleZoneClick('head')}
        >
          <div
            className={`flex items-center gap-1.5 px-2 py-1 rounded-xl shadow-md border backdrop-blur-sm transition-all duration-200 transform ${
              activeZone === 'head'
                ? 'bg-blue-600 text-white scale-105 border-cyan-300 ring-2 ring-cyan-200/50'
                : 'bg-white/80 text-slate-800 hover:bg-white border-slate-200 hover:scale-105'
            }`}
          >
            <div className="w-5 h-5 rounded-md bg-blue-100/90 text-blue-600 flex items-center justify-center">
              <Brain className="w-3 h-3" />
            </div>
            <div>
              <div className="text-xs font-bold leading-none">{t('Baş & Gözler', 'Head & Eyes')}</div>
              <div className="text-[10px] opacity-75 mt-0.5 leading-none">{t('Göz basıncı', 'Eye pressure')} {metricText(vitals.iop.value, 'mmHg')}</div>
            </div>
            <span className={`w-2 h-2 rounded-full shrink-0 ${zoneStatus.head.dot}`} title={zoneStatus.head.label} />
          </div>

          <svg className="hidden md:block absolute -left-16 top-4 w-16 h-6 overflow-visible pointer-events-none">
            <polyline points="64,12 20,12 0,22" fill="none" stroke="#0284c7" strokeWidth="2" strokeDasharray="4 2" />
            <circle cx="0" cy="22" r="3" fill="#00f0ff" />
          </svg>
        </div>

        {/* 2. GÖĞÜS PILL (Top-Left) */}
        <div
          className="absolute top-[22%] left-[3%] z-30 group cursor-pointer"
          onMouseEnter={() => setHoveredZone('chest')}
          onMouseLeave={() => setHoveredZone(null)}
          onClick={() => handleZoneClick('chest')}
        >
          <div
            className={`flex items-center gap-1.5 px-2 py-1 rounded-xl shadow-md border backdrop-blur-sm transition-all duration-200 transform ${
              activeZone === 'chest'
                ? 'bg-blue-600 text-white scale-105 border-cyan-300 ring-2 ring-cyan-200/50'
                : 'bg-white/80 text-slate-800 hover:bg-white border-slate-200 hover:scale-105'
            }`}
          >
            <div className="w-5 h-5 rounded-md bg-rose-100/90 text-rose-600 flex items-center justify-center">
              <Heart className="w-3 h-3 animate-pulse" />
            </div>
            <div>
              <div className="text-xs font-bold leading-none">{t('Kalp & Akciğer', 'Heart & Lungs')}</div>
              <div className="text-[10px] opacity-75 mt-0.5 leading-none">{metricText(vitals.pulse.value, 'bpm')} • SpO₂ {metricText(vitals.oxygen.value, '%')}</div>
            </div>
            <span className={`w-2 h-2 rounded-full shrink-0 ${zoneStatus.chest.dot}`} title={zoneStatus.chest.label} />
          </div>

          <svg className="hidden md:block absolute -right-16 top-4 w-16 h-6 overflow-visible pointer-events-none">
            <polyline points="0,12 44,12 64,22" fill="none" stroke="#0284c7" strokeWidth="2" strokeDasharray="4 2" />
            <circle cx="64" cy="22" r="3" fill="#ef4444" />
          </svg>
        </div>

        {/* 3. METABOLİZMA PILL (Middle-Right) */}
        <div
          className="absolute top-[40%] right-[3%] z-30 group cursor-pointer"
          onMouseEnter={() => setHoveredZone('abdomen')}
          onMouseLeave={() => setHoveredZone(null)}
          onClick={() => handleZoneClick('abdomen')}
        >
          <div
            className={`flex items-center gap-1.5 px-2 py-1 rounded-xl shadow-md border backdrop-blur-sm transition-all duration-200 transform ${
              activeZone === 'abdomen'
                ? 'bg-blue-600 text-white scale-105 border-cyan-300 ring-2 ring-cyan-200/50'
                : 'bg-white/80 text-slate-800 hover:bg-white border-slate-200 hover:scale-105'
            }`}
          >
            <div className="w-5 h-5 rounded-md bg-emerald-100/90 text-emerald-600 flex items-center justify-center">
              <Activity className="w-3 h-3" />
            </div>
            <div>
              <div className="text-xs font-bold leading-none">{t('Metabolizma', 'Metabolism')}</div>
              <div className="text-[10px] opacity-75 mt-0.5 leading-none">{metricText(vitals.glucose.value, 'mg/dL')} • {metricText(vitals.temperature.value, '°C')}</div>
            </div>
            <span className={`w-2 h-2 rounded-full shrink-0 ${zoneStatus.abdomen.dot}`} title={zoneStatus.abdomen.label} />
          </div>

          <svg className="hidden md:block absolute -left-16 top-4 w-16 h-6 overflow-visible pointer-events-none">
            <polyline points="64,12 24,12 0,16" fill="none" stroke="#0284c7" strokeWidth="2" strokeDasharray="4 2" />
            <circle cx="0" cy="16" r="3" fill="#10b981" />
          </svg>
        </div>

        {/* 4. KAS-İSKELET SİSTEMİ PILL (Bottom-Left) */}
        <div
          className="absolute top-[62%] left-[3%] z-30 group cursor-pointer"
          onMouseEnter={() => setHoveredZone('musculoskeletal')}
          onMouseLeave={() => setHoveredZone(null)}
          onClick={() => handleZoneClick('musculoskeletal')}
        >
          <div
            className={`flex items-center gap-1.5 px-2 py-1 rounded-xl shadow-md border backdrop-blur-sm transition-all duration-200 transform ${
              activeZone === 'musculoskeletal'
                ? 'bg-blue-600 text-white scale-105 border-cyan-300 ring-2 ring-cyan-200/50'
                : 'bg-white/80 text-slate-800 hover:bg-white border-slate-200 hover:scale-105'
            }`}
          >
            <div className="w-5 h-5 rounded-md bg-indigo-100/90 text-indigo-600 flex items-center justify-center">
              <Bone className="w-3 h-3" />
            </div>
            <div>
              <div className="text-xs font-bold leading-none">{t('Kas & Kemik', 'Muscle & Bone')}</div>
              <div className="text-[10px] opacity-75 mt-0.5 leading-none">{t('Veri kaynağı bağlı değil', 'Data source not connected')}</div>
            </div>
            <span className={`w-2 h-2 rounded-full shrink-0 ${zoneStatus.musculoskeletal.dot}`} title={zoneStatus.musculoskeletal.label} />
          </div>

          <svg className="hidden md:block absolute -right-16 top-4 w-16 h-6 overflow-visible pointer-events-none">
            <polyline points="0,12 40,12 64,18" fill="none" stroke="#0284c7" strokeWidth="2" strokeDasharray="4 2" />
            <circle cx="64" cy="18" r="3" fill="#6366f1" />
          </svg>
        </div>

        {/* 3D Raycasting Tooltip when hovering over a specific anatomical mesh */}
        {hoveredMeshName && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-slate-900/90 text-white text-xs font-mono px-3 py-1 rounded-full shadow-lg border border-cyan-400 pointer-events-none z-30 flex items-center space-x-1.5 animate-fadeIn">
            <span className={`w-2 h-2 rounded-full shrink-0 ${zoneStatus.head.dot}`} title={zoneStatus.head.label} />
            <span>{hoveredMeshName}</span>
          </div>
        )}
      </div>

      {/* Bottom Exact Callout Banner */}
      <div className="w-full flex items-center justify-between pt-2 z-30">
        <div className="flex items-center space-x-1.5 text-xs text-slate-500 font-mono">
          <Compass className="w-3.5 h-3.5 text-blue-600" />
          <span>{fullPageView ? t('Sürükleyerek döndürün, tekerlekle yakınlaştırın', 'Drag to rotate, scroll to zoom') : t('Sürükleyerek döndürün', 'Drag to rotate')}</span>
        </div>

        <div
          onClick={() => handleZoneClick(activeZone || 'head')}
          className="flex items-center space-x-2 px-5 py-2 rounded-full bg-white/95 hover:bg-blue-50 border border-sky-300 shadow-md text-xs font-bold text-slate-700 cursor-pointer transition-all hover:scale-105"
        >
          <span>{t('Bölge detaylarını aç', 'Open area details')}</span>
        </div>

        <div className="text-xs text-slate-500 font-mono">
          {selectedGender === 'female' ? t('Kadın modeli', 'Female model') : t('Erkek modeli', 'Male model')}
        </div>
      </div>
    </div>
  );
};
