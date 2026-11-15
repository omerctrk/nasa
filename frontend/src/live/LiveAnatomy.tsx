import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js'
import type { Measurement } from './api'

const REGIONS = [
  { title: 'Baş ve gözler', codes: [] },
  { title: 'Kalp ve dolaşım', codes: ['heart_rate', 'systolic_bp', 'diastolic_bp'] },
  { title: 'Metabolizma', codes: ['blood_glucose', 'body_temperature'] },
  { title: 'Kas ve iskelet', codes: [] },
]

export default function LiveAnatomy({ measurements }: { measurements: Measurement[] }) {
  const host = useRef<HTMLDivElement>(null)
  const [model, setModel] = useState<'female' | 'male'>('female')
  const [error, setError] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const element = host.current
    if (!element) return
    let disposed = false
    let frame = 0
    setReady(false)
    setError(false)
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true }) }
    catch { setError(true); return }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    element.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100)
    camera.position.set(0, 0, 3.4)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.enableZoom = false
    controls.autoRotate = !matchMedia('(prefers-reduced-motion: reduce)').matches
    controls.autoRotateSpeed = 0.5
    scene.add(new THREE.AmbientLight(0xdbeafe, 1.7))
    const light = new THREE.DirectionalLight(0x38bdf8, 2.2)
    light.position.set(3, 5, 5)
    scene.add(light)
    const rim = new THREE.DirectionalLight(0x818cf8, 1.5)
    rim.position.set(-3, -2, -3)
    scene.add(rim)
    let root: THREE.Group | null = null
    const loader = new GLTFLoader()
    loader.setMeshoptDecoder(MeshoptDecoder)
    loader.load(`/models/anatomy-${model}.glb`, (gltf) => {
      if (disposed) return
      root = gltf.scene
      const box = new THREE.Box3().setFromObject(root)
      const center = box.getCenter(new THREE.Vector3())
      const size = box.getSize(new THREE.Vector3())
      const scale = 2.2 / Math.max(size.x, size.y, size.z)
      root.scale.setScalar(scale)
      root.position.set(-center.x * scale, -center.y * scale, -center.z * scale)
      scene.add(root)
      setReady(true)
    }, undefined, () => { if (!disposed) setError(true) })
    const resize = () => {
      const width = element.clientWidth || 400
      const height = element.clientHeight || 480
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(element)
    resize()
    const render = () => {
      if (disposed) return
      controls.update()
      renderer.render(scene, camera)
      frame = requestAnimationFrame(render)
    }
    render()
    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      observer.disconnect()
      controls.dispose()
      scene.traverse((item) => {
        if (!(item instanceof THREE.Mesh)) return
        item.geometry.dispose()
        const materials = Array.isArray(item.material) ? item.material : [item.material]
        materials.forEach((material) => material.dispose())
      })
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [model])

  const latest = new Map<string, Measurement>()
  for (const item of measurements.filter((row) => row.valid && (row.value_num !== null || row.value_text !== null))
    .sort((a, b) => (b.measured_at ?? b.measured_date).localeCompare(a.measured_at ?? a.measured_date))) {
    if (!latest.has(item.measurement)) latest.set(item.measurement, item)
  }

  return <section className="relative flex h-full min-h-[620px] flex-col overflow-hidden rounded-3xl border border-sky-200 bg-gradient-to-b from-sky-50/90 via-white/85 to-indigo-50/90 p-4 shadow-sm">
    <div className="relative z-10 flex items-center justify-between gap-2">
      <div><h2 className="font-bold text-slate-900">Vücut Haritası</h2><p className="text-xs text-slate-500">Anatomik model · ölçümler SQL Server'dan</p></div>
      <div className="flex gap-1 text-xs"><button className={`rounded-lg border px-2 py-1 ${model === 'female' ? 'bg-sky-100 text-sky-800' : 'bg-white'}`} onClick={() => setModel('female')}>Kadın modeli</button>
        <button className={`rounded-lg border px-2 py-1 ${model === 'male' ? 'bg-sky-100 text-sky-800' : 'bg-white'}`} onClick={() => setModel('male')}>Erkek modeli</button></div>
    </div>
    <div ref={host} className="min-h-[390px] flex-1" aria-label="Etkileşimli anatomik model" />
    {!ready && !error && <div className="pointer-events-none absolute inset-0 grid place-items-center text-sm text-slate-500">Model yükleniyor…</div>}
    {error && <div className="pointer-events-none absolute inset-0 grid place-items-center text-sm text-slate-500">Anatomik model yüklenemedi.</div>}
    <div className="relative z-10 grid grid-cols-2 gap-2">
      {REGIONS.map((region) => {
        const rows = region.codes.map((code) => latest.get(code)).filter((item): item is Measurement => !!item)
        return <div key={region.title} className="rounded-xl border border-white/80 bg-white/85 p-2.5 text-xs shadow-sm">
          <div className="font-semibold text-slate-800">{region.title}</div>
          {rows.length ? rows.map((item) => <div key={item.measurement} className="mt-1 text-slate-600">{item.measurement.replaceAll('_', ' ')}: <b className="font-mono text-sky-800">{item.value_num ?? item.value_text} {item.unit}</b></div>)
            : <div className="mt-1 text-slate-400">Kayıt yok</div>}
        </div>
      })}
    </div>
  </section>
}
