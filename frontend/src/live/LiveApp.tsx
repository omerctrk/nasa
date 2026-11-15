import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import {
  Activity, Bell, BookOpen, ClipboardList, Database, Globe2, LayoutDashboard,
  LogOut, RefreshCw, ShieldCheck, Radiation, Users, Satellite, ArrowDownToLine, Wind, Clock,
} from 'lucide-react'
import { AuroraBackground } from '../components/layout/AuroraBackground'
import {
  api, ApiError, type Alert, type Checkin, type Job, type KnowledgeCard,
  type CognitiveTest, type Measurement, type NotificationEvent, type Profile,
  type Result, type User, type WeeklyAssessment,
} from './api'

const TOKEN_KEY = 'astra-live-token'
type View = 'dashboard' | 'anatomy' | 'tests' | 'behavior' | 'reports' | 'settings' | 'analysis' | 'alerts' | 'knowledge'
const MEASURES: Record<string, string> = {
  heart_rate: 'BPM', systolic_bp: 'mmHg', diastolic_bp: 'mmHg',
  blood_glucose: 'mg/dL', body_temperature: '°C',
}

function addDays(day: string, count: number): string {
  const value = new Date(`${day}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + count)
  return value.toISOString().slice(0, 10)
}

function missionDay(profile: Profile): string {
  const today = new Date().toISOString().slice(0, 10)
  const end = addDays(profile.mission_start_date, profile.mission_length_days)
  return today >= profile.mission_start_date && today < end ? today : profile.mission_start_date
}

async function latestRecordedDay(token: string, role: User['role'], profile: Profile): Promise<string> {
  const end = addDays(profile.mission_start_date, profile.mission_length_days)
  const ranges: { start: string; end: string }[] = []
  for (let start = profile.mission_start_date; start < end; start = addDays(start, 120)) {
    ranges.push({ start, end: addDays(start, 120) < end ? addDays(start, 120) : end })
  }
  const pages = await Promise.all(ranges.map((range) =>
    api.measurements(token, role, profile.astronaut_id, range.start, range.end)))
  const dates = pages.flatMap((page) => page.data.map((item) => item.measured_date))
  return dates.length ? dates.sort().at(-1)! : missionDay(profile)
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error && error.name === 'TimeoutError') return 'Sunucu zaman aşımına uğradı.'
  return 'Bağlantı kurulamadı. Servisleri kontrol edip tekrar deneyin.'
}

function Card({ title, icon: Icon, children }: {
  title: string; icon: typeof Activity; children: React.ReactNode
}) {
  return <section className="rounded-2xl border border-slate-200 bg-white/95 shadow-sm p-5">
    <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900 mb-4"><Icon className="h-5 w-5 text-sky-700" />{title}</h2>
    {children}
  </section>
}

const field = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-600'
const button = 'rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-50'
const subtle = 'text-sm text-slate-500'
const LiveAnatomy = lazy(() => import('./LiveAnatomy'))

function DashboardHome({ profile, measurements, checkins, alerts, events, job, result, busy, canAnalyze, onAnalysis, onView }: {
  profile: Profile | null; measurements: Measurement[]; checkins: Checkin[]; alerts: Alert[];
  events: NotificationEvent[]; job: Job | null; result: Result | null; busy: boolean; canAnalyze: boolean;
  onAnalysis: () => void; onView: (view: View) => void
}) {
  const valid = measurements.filter((item) => item.valid && (item.value_num !== null || item.value_text !== null))
  const latest = new Map<string, Measurement>()
  for (const item of [...valid].sort((a, b) => (b.measured_at ?? b.measured_date).localeCompare(a.measured_at ?? a.measured_date))) {
    if (!latest.has(item.measurement)) latest.set(item.measurement, item)
  }
  const current = Array.from(latest.values()).slice(0, 6)
  const openAlerts = alerts.filter((item) => item.status !== 'RESOLVED')
  const hazardCards = [
    { title: 'Radyasyon', value: 'Kayıt yok', detail: 'Doz kaydı bulunmuyor', icon: Radiation },
    { title: 'İzolasyon', value: canAnalyze && checkins[0] ? `${checkins[0].sleep_hours} saat uyku` : 'Kayıt yok', detail: 'Günlük check-in verisi', icon: Users },
    { title: 'Uzaklık', value: 'Kayıt yok', detail: 'İletişim gecikmesi ölçülmüyor', icon: Satellite },
    { title: 'Yerçekimi', value: latest.get('heart_rate') ? `${latest.get('heart_rate')!.value_num} BPM` : 'Kayıt yok', detail: 'Son kayıtlı nabız', icon: ArrowDownToLine },
    { title: 'Kapalı ortam', value: 'Kayıt yok', detail: 'Kabin sensörü bağlı değil', icon: Wind },
  ]
  return <div className="mx-auto max-w-7xl space-y-5 animate-fadeIn">
    <div className="grid gap-4 xl:grid-cols-12">
      <div className="xl:col-span-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 to-cyan-400 text-white"><Globe2 className="h-6 w-6" /></span>
        <div><h2 className="text-lg font-bold text-slate-900">{profile?.display_name ?? 'Görev profili'}</h2>
          <p className="text-xs text-slate-500">{profile?.mission_name ?? 'Yükleniyor'} · {profile?.astronaut_id ?? ''}</p></div>
      </div>
      <div className={`xl:col-span-7 flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 shadow-sm ${openAlerts.length ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white'}`}>
        <div><h2 className="font-bold text-slate-900">{openAlerts.length ? `${openAlerts.length} açık alarm` : 'Açık alarm kaydı yok'}</h2>
          <p className="text-xs text-slate-600">{openAlerts.length ? 'Ayrıntılar veritabanındaki alarm kayıtlarından gelir.' : 'Bu bilgi sağlık değerlendirmesi yapıldığı anlamına gelmez.'}</p></div>
        <button onClick={() => onView('alerts')} className="shrink-0 rounded-xl bg-sky-700 px-3 py-2 text-xs font-bold text-white">Alarmları aç</button>
      </div>
    </div>
    <section><div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-1"><h2 className="text-sm font-bold text-slate-800">Görev Ortam Koşulları</h2>
      <span className="text-xs text-slate-500">Veritabanındaki kayıtlar · klinik risk değerlendirmesi değil</span></div>
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">{hazardCards.map(({ title, value, detail, icon: Icon }) =>
        <div key={title} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600"><Icon className="h-4 w-4" />{title}</div>
          <div className="mt-2 font-mono text-base font-bold text-slate-900">{value}</div><div className="mt-1 text-xs text-slate-500">{detail}</div>
        </div>)}</div>
    </section>
    <div className="grid items-start gap-5 lg:grid-cols-12">
      <div className="space-y-5 lg:col-span-7">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between"><h2 className="text-base font-bold text-slate-900">Sağlık Özeti</h2><span className="rounded-lg bg-sky-50 px-2 py-1 text-xs font-semibold text-sky-800">SQL Server</span></div>
          <p className="mt-1 text-xs text-slate-500">Yalnızca seçilen dönemde kayıtlı ve geçerli ölçümler gösterilir. Klinik eşik değerlendirmesi yapılmaz.</p>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <div className="neon-ring grid h-32 w-32 shrink-0 place-items-center rounded-full border-[9px] border-sky-400 bg-sky-50 shadow-[0_0_25px_rgba(56,189,248,0.25)]">
              <div className="text-center"><div className="font-mono text-3xl font-black text-sky-800">{valid.length}</div><div className="text-[11px] text-slate-500">ölçüm kaydı</div></div>
            </div>
            <div className="text-sm text-slate-600"><div><b className="text-slate-900">{latest.size}</b> farklı ölçüm türü</div>
              <div className="mt-1"><b className="text-slate-900">{openAlerts.length}</b> açık alarm kaydı</div>
              {canAnalyze && <div className="mt-1"><b className="text-slate-900">{checkins.length}</b> check-in kaydı</div>}
              <p className="mt-2 text-xs">Sayılar seçilen tarih aralığından gelir; sağlık puanı değildir.</p>
            </div>
          </div>
          {current.length ? <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">{current.map((item) =>
            <div key={item.measurement} className="rounded-xl border border-sky-100 bg-sky-50/50 p-3">
              <div className="text-xs font-semibold text-slate-600">{item.measurement.replaceAll('_', ' ')}</div>
              <div className="mt-1 font-mono text-lg font-bold text-sky-900">{item.value_num ?? item.value_text} <span className="text-xs font-normal">{item.unit}</span></div>
              <div className="mt-1 text-[11px] text-slate-500">{item.measured_at ?? item.measured_date}</div>
            </div>)}</div> : <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Bu dönemde ölçüm kaydı yok.</p>}
          <button className="mt-4 text-sm font-semibold text-sky-700" onClick={() => onView('reports')}>Tüm ölçümleri aç →</button>
        </section>
        <section className="ai-panel overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3"><span className="ai-orb"><Database className="h-5 w-5 text-white" /></span>
            <div><h2 className="font-bold text-slate-900">Analiz işi</h2><p className="text-xs text-slate-500">Sonuç yalnızca backend değerlendirmesinden gelir.</p></div></div>
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
            {job ? <><div>Durum: <b>{job.state}</b>{job.evaluation_status ? ` · ${job.evaluation_status}` : ''}</div>
              {result && <p className="mt-2">{result.summary}</p>}</> : <p className="text-slate-500">Bu oturumda analiz işi başlatılmadı.</p>}
          </div>
          <div className="mt-3 flex gap-3">{canAnalyze && <button className={button} disabled={busy || !!job && !['COMPLETED', 'FAILED'].includes(job.state)} onClick={onAnalysis}>Analiz et</button>}
            <button className="text-sm font-semibold text-sky-700" onClick={() => onView('analysis')}>Ayrıntılar →</button></div>
          <p className="mt-3 text-xs text-slate-500">Model ve klinik eşikler hazır değilse değerlendirme yetersiz veri dönebilir.</p>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-bold text-slate-900">Bugünkü Hedefler</h2>
          <p className="mt-2 text-sm text-slate-500">Veritabanında onaylı hedef veya öneri kaydı bulunmuyor. Model ve eşik kuralları tamamlandığında burada gösterilecek.</p>
        </section>
        <div className="grid gap-4 sm:grid-cols-2">
          <Card title="Alarmlar" icon={ShieldCheck}>{openAlerts.length ? <p className="text-sm">{openAlerts.length} açık alarm kaydı bulunuyor.</p> : <p className={subtle}>Açık alarm kaydı yok.</p>}</Card>
          <Card title="Bildirimler" icon={Bell}>{events.length ? <p className="text-sm">{events.length} kayıtlı bildirim gösteriliyor.</p> : <p className={subtle}>Bildirim kaydı yok.</p>}</Card>
        </div>
      </div>
      <div className="lg:col-span-5 lg:sticky lg:top-6"><Suspense fallback={<div className="rounded-3xl bg-white p-5">Vücut haritası yükleniyor…</div>}><LiveAnatomy measurements={measurements} /></Suspense></div>
    </div>
  </div>
}

function ReportCharts({ measurements }: { measurements: Measurement[] }) {
  const groups = new Map<string, Measurement[]>()
  for (const item of measurements) {
    const value = Number(item.value_num)
    if (!item.valid || item.value_num === null || !Number.isFinite(value)) continue
    groups.set(item.measurement, [...(groups.get(item.measurement) ?? []), item])
  }
  if (!groups.size) return <Card title="Ölçüm grafikleri" icon={Activity}><p className={subtle}>Seçilen dönemde grafik oluşturacak sayısal kayıt yok.</p></Card>
  return <section className="grid gap-4 lg:grid-cols-2">{Array.from(groups).slice(0, 6).map(([code, rows]) => {
    rows.sort((a, b) => (a.measured_at ?? a.measured_date).localeCompare(b.measured_at ?? b.measured_date))
    const values = rows.map((row) => Number(row.value_num))
    const low = Math.min(...values)
    const span = Math.max(1, Math.max(...values) - low)
    const points = values.map((value, index) => `${12 + index * 276 / Math.max(1, values.length - 1)},${72 - ((value - low) / span) * 56}`).join(' ')
    return <div key={code} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex justify-between gap-2"><h2 className="font-bold text-slate-900">{code.replaceAll('_', ' ')}</h2><span className="text-xs text-slate-500">{rows.length} kayıt</span></div>
      <svg viewBox="0 0 300 84" className="mt-3 h-28 w-full" role="img" aria-label={`${code} ölçüm geçmişi`}>
        <line x1="12" y1="72" x2="288" y2="72" stroke="#cbd5e1" />
        {values.length > 1 ? <polyline points={points} fill="none" stroke="#0284c7" strokeWidth="2.5" strokeLinejoin="round" />
          : <circle cx="12" cy="72" r="4" fill="#0284c7" />}
      </svg>
      <div className="flex justify-between text-xs text-slate-500"><span>{rows[0].measured_date}</span>
        <span className="font-mono font-semibold text-sky-800">{rows[rows.length - 1].value_num} {rows[rows.length - 1].unit}</span>
        <span>{rows[rows.length - 1].measured_date}</span></div>
    </div>
  })}</section>
}

export default function LiveApp() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? '')
  const [view, setView] = useState<View>('dashboard')
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [crew, setCrew] = useState<Profile[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [day, setDay] = useState('')
  const [measurements, setMeasurements] = useState<Measurement[]>([])
  const [checkins, setCheckins] = useState<Checkin[]>([])
  const [weekly, setWeekly] = useState<WeeklyAssessment[]>([])
  const [cognitive, setCognitive] = useState<CognitiveTest[]>([])
  const [currentCheckin, setCurrentCheckin] = useState<Checkin | null>(null)
  const [checkinEtag, setCheckinEtag] = useState<string | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [cards, setCards] = useState<KnowledgeCard[]>([])
  const [events, setEvents] = useState<NotificationEvent[]>([])
  const [job, setJob] = useState<Job | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [devPending, setDevPending] = useState(false)
  const loadVersion = useRef(0)
  const [utcTime, setUtcTime] = useState(() => new Date().toUTCString().slice(17, 25))

  useEffect(() => {
    const timer = window.setInterval(() => setUtcTime(new Date().toUTCString().slice(17, 25)), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const logout = useCallback(() => {
    loadVersion.current += 1
    sessionStorage.removeItem(TOKEN_KEY)
    setToken(''); setUser(null); setProfile(null); setCrew([])
    setMeasurements([]); setCheckins([]); setWeekly([]); setCognitive([]); setAlerts([]); setCards([]); setEvents([])
    setJob(null); setResult(null)
  }, [])

  const report = useCallback((cause: unknown) => {
    if (cause instanceof ApiError && cause.status === 401) {
      logout()
      setError('Oturum süresi doldu. Yeniden giriş yapın.')
      return
    }
    setError(errorText(cause))
  }, [logout])

  useEffect(() => {
    if (!import.meta.env.DEV || token) return
    let active = true
    setDevPending(true)
    api.devSession('ASTRONAUT').then((nextToken) => {
      if (!active) return
      sessionStorage.setItem(TOKEN_KEY, nextToken)
      setToken(nextToken)
      setError('')
    }).catch((cause) => { if (active) report(cause) })
      .finally(() => { if (active) setDevPending(false) })
    return () => { active = false }
  }, [token, report])

  useEffect(() => {
    if (!token) return
    let active = true
    api.me(token).then(({ data }) => { if (active) setUser(data) }).catch((cause) => { if (active) report(cause) })
    return () => { active = false }
  }, [token, report])

  useEffect(() => {
    if (!token || !user) return
    let active = true
    const load = user.role === 'ASTRONAUT' ? api.profile(token) : api.crew(token)
    load.then(async ({ data }) => {
      if (!active) return
      if (user.role === 'ASTRONAUT') {
        const next = data as Profile
        setProfile(next); setSelectedId(next.astronaut_id)
        const date = await latestRecordedDay(token, user.role, next).catch(() => missionDay(next))
        if (active) setDay(date)
      } else {
        const next = data as Profile[]
        setCrew(next)
        const first = next.find((item) => !item.is_display_only) ?? next[0]
        if (first) {
          setSelectedId(first.astronaut_id)
          const date = await latestRecordedDay(token, user.role, first).catch(() => missionDay(first))
          if (active) setDay(date)
        }
      }
    }).catch(report)
    return () => { active = false }
  }, [token, user, report])

  const loadData = useCallback(async () => {
    if (!token || !user || !selectedId || !day) return
    const version = ++loadVersion.current
    const start = addDays(day, -29)
    const end = addDays(day, 1)
    try {
      const [readings, alertRows, pending] = await Promise.all([
        api.measurements(token, user.role, selectedId, start, end),
        api.alerts(token, user.role), api.pending(token),
      ])
      if (version !== loadVersion.current) return
      setMeasurements(readings.data.filter((row) => row.astronaut_id === selectedId).reverse())
      setAlerts(alertRows.data.filter((row) => row.astronaut_id === selectedId))
      setEvents((previous) => [...pending.data,
        ...previous.filter((item) => !pending.data.some((next) => next.event_id === item.event_id))].slice(0, 20))
      if (user.role === 'ASTRONAUT') {
        const [rows, current, weeklyRows, cognitiveRows] = await Promise.all([
          api.checkins(token, start, end),
          api.checkin(token, day).catch((cause) => {
            if (cause instanceof ApiError && cause.status === 404) return null
            throw cause
          }),
          api.weekly(token, start, end), api.cognitive(token, start, end),
        ])
        if (version !== loadVersion.current) return
        setCheckins(rows.data.reverse())
        setWeekly(weeklyRows.data.reverse())
        setCognitive(cognitiveRows.data.reverse())
        setCurrentCheckin(current?.data ?? null)
        setCheckinEtag(current?.etag ?? null)
      } else {
        const rows = await api.cards(token)
        if (version !== loadVersion.current) return
        setCards(rows.data)
      }
      setError('')
    } catch (cause) { if (version === loadVersion.current) report(cause) }
  }, [token, user, selectedId, day, report])

  useEffect(() => { void loadData() }, [loadData])
  useEffect(() => {
    if (!token || !user) return
    const timer = window.setInterval(() => void loadData(), 30_000)
    return () => window.clearInterval(timer)
  }, [token, user, loadData])

  useEffect(() => {
    if (!token || !user) return
    let disposed = false
    let socket: WebSocket | null = null
    let retry: number | undefined
    const open = () => {
      if (disposed) return
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/v1/notifications`)
      socket.onopen = () => socket?.send(JSON.stringify({ type: 'authenticate', access_token: token }))
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as { event_id?: string; type?: string; created_at?: string; payload?: Record<string, unknown> }
          if (!event.event_id) return
          socket?.send(JSON.stringify({ type: 'receipt', event_id: event.event_id }))
          setEvents((previous) => [{ event_id: event.event_id!, event_type: event.type ?? '',
            created_at: event.created_at ?? '', payload: event.payload ?? {} },
            ...previous.filter((item) => item.event_id !== event.event_id)])
          void loadData()
        } catch { /* Invalid server frame: wait for the next valid event. */ }
      }
      socket.onclose = (event) => {
        if (disposed) return
        if (event.code === 4401) report(new ApiError(401, 'Oturum süresi doldu.'))
        else retry = window.setTimeout(open, 3000)
      }
    }
    open()
    return () => { disposed = true; window.clearTimeout(retry); socket?.close() }
  }, [token, user, loadData, report])

  useEffect(() => {
    if (!token || !job || job.state === 'COMPLETED' || job.state === 'FAILED') return
    const timer = window.setInterval(async () => {
      try {
        const next = (await api.job(token, job.job_id)).data
        setJob(next)
        if (next.state === 'COMPLETED' && next.anomaly_result_id && user) {
          setResult((await api.result(token, user.role, next.anomaly_result_id)).data)
          void loadData()
        }
      } catch (cause) { report(cause) }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [token, user, job, loadData, report])

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    const form = new FormData(event.currentTarget)
    try {
      const { data } = await api.login(String(form.get('email')), String(form.get('password')))
      sessionStorage.setItem(TOKEN_KEY, data.access_token)
      setToken(data.access_token)
    } catch (cause) { report(cause) }
    finally { setBusy(false) }
  }

  async function switchDevRole(role: User['role']) {
    if (!import.meta.env.DEV || user?.role === role) return
    setBusy(true); setError(''); setNotice('')
    try {
      const nextToken = await api.devSession(role)
      logout()
      sessionStorage.setItem(TOKEN_KEY, nextToken)
      setToken(nextToken)
      setView('dashboard')
    } catch (cause) { report(cause) }
    finally { setBusy(false) }
  }

  async function saveCheckin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token || !day) return
    setBusy(true); setError(''); setNotice('')
    const form = new FormData(event.currentTarget)
    const number = (name: string) => Number(form.get(name))
    const body = {
      mood: number('mood'), energy: number('energy'), stress: number('stress'),
      loneliness: number('loneliness'), crew: number('crew'), mood_index: number('mood_index'),
      bed_time: String(form.get('bed_time')), wake_time: String(form.get('wake_time')),
      sleep_quality: number('sleep_quality'),
      symptoms: null,
    }
    try {
      await api.putCheckin(token, day, body, checkinEtag)
      setNotice('Check-in kaydedildi.'); await loadData()
    } catch (cause) { report(cause) }
    finally { setBusy(false) }
  }

  async function saveMeasurement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token || !day) return
    const formElement = event.currentTarget
    setBusy(true); setError(''); setNotice('')
    const form = new FormData(formElement)
    const measurement = String(form.get('measurement'))
    try {
      await api.physiological(token, { client_request_id: crypto.randomUUID(), measurement,
        value_num: Number(form.get('value')), unit: MEASURES[measurement], measured_date: day })
      setNotice('Ölçüm kaydedildi.'); await loadData()
      formElement.reset()
    } catch (cause) { report(cause) }
    finally { setBusy(false) }
  }

  async function startAnalysis() {
    if (!token) return
    setBusy(true); setError(''); setResult(null)
    try {
      const accepted = (await api.createJob(token, crypto.randomUUID())).data
      setJob((await api.job(token, accepted.job_id)).data)
    } catch (cause) { report(cause) }
    finally { setBusy(false) }
  }

  async function updateAlert(alert: Alert, action: 'acknowledge' | 'resolve') {
    if (!token) return
    setBusy(true); setError('')
    try {
      if (action === 'acknowledge') await api.acknowledge(token, alert.alert_id)
      else {
        const note = window.prompt('Kapatma notu')?.trim()
        if (!note) return
        await api.resolve(token, alert.alert_id, note)
      }
      await loadData()
    } catch (cause) { report(cause) }
    finally { setBusy(false) }
  }

  async function saveCard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token) return
    const formElement = event.currentTarget
    setBusy(true); setError('')
    const form = new FormData(formElement)
    const value = (name: string) => String(form.get(name)).trim()
    const card: KnowledgeCard = {
      card_id: value('card_id'), type: value('type'), system: value('system'),
      metrics: value('metrics').split(',').map((part) => part.trim()).filter(Boolean),
      direction: value('direction'), text: value('text'), source: value('source'),
      url: value('url'), locator: value('locator'),
    }
    try {
      await api.createCard(token, card)
      setNotice('Bilgi kartı kaydedildi.'); await loadData()
      formElement.reset()
    } catch (cause) { report(cause) }
    finally { setBusy(false) }
  }

  if ((!token || !user) && import.meta.env.DEV) return <main className="min-h-screen grid place-items-center px-4">
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-lg">
      <h1 className="text-xl font-semibold">ASTRA HEALTH</h1>
      <p className={`${subtle} mt-2`}>{devPending || token ? 'Yerel oturum açılıyor…' : 'Yerel oturum açılamadı.'}</p>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      {!devPending && !token && <button className={`${button} mt-4`} onClick={() => void switchDevRole('ASTRONAUT')}>Tekrar dene</button>}
    </div>
  </main>

  if (!token || !user) return <main className="min-h-screen grid place-items-center px-4">
    <form onSubmit={(event) => void signIn(event)} className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-lg space-y-5">
      <div><div className="text-sm font-bold tracking-[0.25em] text-sky-700">ASTRA HEALTH</div>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">Merkezi sağlık paneli</h1>
        <p className={`${subtle} mt-2`}>Astronot veya yer kontrolü hesabınızla giriş yapın.</p></div>
      <label className="block text-sm font-medium">E-posta<input className={`${field} mt-1`} name="email" type="email" autoComplete="username" required /></label>
      <label className="block text-sm font-medium">Parola<input className={`${field} mt-1`} name="password" type="password" autoComplete="current-password" required /></label>
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      <button className={`${button} w-full`} disabled={busy}>Giriş yap</button>
    </form>
  </main>

  const selectedProfile = user.role === 'ASTRONAUT' ? profile : crew.find((item) => item.astronaut_id === selectedId)
  const navigation: { id: View; label: string; icon: typeof Activity }[] = [
    { id: 'dashboard', label: 'Ana Panel', icon: LayoutDashboard },
    { id: 'anatomy', label: 'Anatomi 3D', icon: Activity },
    ...(user.role === 'ASTRONAUT' ? [
      { id: 'tests' as View, label: 'Testler', icon: ClipboardList },
      { id: 'behavior' as View, label: 'Davranış', icon: Activity },
    ] : []),
    { id: 'reports', label: 'Raporlar', icon: Database },
    { id: 'settings', label: 'Ayarlar', icon: ShieldCheck },
    { id: 'alerts', label: 'Alarmlar ve Bildirimler', icon: Bell },
    ...(user.role === 'GROUND_CONTROL' ? [{ id: 'knowledge' as View, label: 'Bilgi Kartları', icon: BookOpen }] : []),
  ]
  const currentTitle = navigation.find((item) => item.id === view)?.label ?? 'Ana Panel'
  return <div className="min-h-screen text-slate-800 lg:pl-[17rem]">
    <AuroraBackground />
    <aside className="relative z-10 border-b border-slate-200 bg-white/90 p-4 backdrop-blur-xl lg:fixed lg:bottom-4 lg:left-4 lg:top-4 lg:w-60 lg:overflow-y-auto lg:rounded-3xl lg:border lg:p-4 glass-bar flex flex-col gap-5 shadow-sm">
      <button className="flex items-center gap-3 text-left" onClick={() => setView('dashboard')}>
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 via-sky-500 to-cyan-400 text-white shadow-lg"><Globe2 className="h-5 w-5" /></span>
        <span><strong className="block text-lg tracking-[0.12em]">AHMS</strong><small className="text-slate-500">Astronot Sağlık İzleme</small></span>
      </button>
      <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-800">{selectedProfile?.scenario ?? 'Görev'} · {selectedProfile?.mission_name ?? 'Yükleniyor'}</div>
      <nav aria-label="Ana menü" className="flex flex-wrap gap-1 lg:flex-col">
        {navigation.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => setView(id)}
          className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-sm font-semibold transition-all ${view === id ? 'nav-active' : 'border-transparent text-slate-600 hover:bg-slate-100/70'}`}>
          <Icon className="h-[18px] w-[18px]" />{label}</button>)}
      </nav>
      <div className="mt-auto space-y-3 border-t border-slate-200 pt-4 text-sm">
        <div className="flex items-center justify-between text-xs text-slate-500"><span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{utcTime} UTC</span>
          <span>{error ? 'Bağlantı hatası' : 'API bağlı'}</span></div>
        <div className="font-semibold text-slate-900">{selectedProfile?.display_name ?? user.email}</div>
        <div className="text-xs text-slate-500">{selectedProfile?.mission_name ?? 'Görev profili yükleniyor'} · {selectedProfile?.astronaut_id ?? ''}</div>
        {user.role === 'GROUND_CONTROL' && <select aria-label="Astronot seç" className={field} value={selectedId} onChange={(event) => {
          const id = event.target.value; loadVersion.current += 1; setMeasurements([]); setAlerts([]); setSelectedId(id)
          const next = crew.find((item) => item.astronaut_id === id); if (next) setDay(missionDay(next))
        }}>{crew.map((item) => <option key={item.astronaut_id} value={item.astronaut_id}>{item.display_name} · {item.astronaut_id}{item.is_display_only ? ' · gösterim' : ''}</option>)}</select>}
        <label className="block text-xs text-slate-500">Görüntüleme günü<input className={`${field} mt-1`} type="date" value={day} onChange={(event) => {
          loadVersion.current += 1; setMeasurements([]); setCheckins([]); setDay(event.target.value)
        }} /></label>
        <button className="flex items-center gap-1 text-xs font-semibold text-sky-700" onClick={() => void loadData()}><RefreshCw className="h-3.5 w-3.5" />Veriyi yenile</button>
        {import.meta.env.DEV ? <div className="flex gap-1" aria-label="Yerel demo rolü">
          <button className="rounded-lg border px-2 py-1.5 text-xs disabled:bg-sky-50 disabled:text-sky-800" disabled={busy || user.role === 'ASTRONAUT'} onClick={() => void switchDevRole('ASTRONAUT')}>Astronot</button>
          <button className="rounded-lg border px-2 py-1.5 text-xs disabled:bg-sky-50 disabled:text-sky-800" disabled={busy || user.role === 'GROUND_CONTROL'} onClick={() => void switchDevRole('GROUND_CONTROL')}>Yer kontrolü</button>
        </div> : <button onClick={logout} className="flex items-center gap-1 rounded-lg border px-2 py-1.5"><LogOut className="h-4 w-4" />Çıkış</button>}
      </div>
    </aside>
    <main className="relative z-10 mx-auto max-w-[90rem] space-y-5 px-4 py-6 sm:px-6">
      {view !== 'dashboard' && <div><div className="text-xs font-bold tracking-[0.2em] text-sky-700">ASTRA HEALTH · CANLI VERİ</div>
        <h1 className="text-2xl font-bold text-slate-900">{currentTitle}</h1></div>}
      {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {notice && <div role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">{notice}</div>}
      {view === 'dashboard' && <DashboardHome profile={selectedProfile ?? null} measurements={measurements} checkins={checkins}
        alerts={alerts} events={events} job={job} result={result} busy={busy} canAnalyze={user.role === 'ASTRONAUT'}
        onAnalysis={() => void startAnalysis()} onView={setView} />}
      {view === 'anatomy' && <div className="mx-auto max-w-4xl"><Suspense fallback={<Card title="Vücut Haritası" icon={Activity}>Model yükleniyor…</Card>}>
        <LiveAnatomy measurements={measurements} /></Suspense></div>}
      {view === 'reports' && <ReportCharts measurements={measurements} />}
      <div className="grid gap-5 lg:grid-cols-2">
        {view === 'reports' && <Card title="Ölçümler · son 30 gün" icon={Activity}>
          {measurements.length === 0 ? <p className={subtle}>Bu aralıkta kayıtlı ölçüm yok.</p>
            : <div className="max-h-80 overflow-auto divide-y divide-slate-100">{measurements.slice(0, 60).map((item) => <div key={item.record_id} className="flex justify-between gap-3 py-2 text-sm">
              <div><div className="font-medium">{item.measurement}</div><div className="text-xs text-slate-500">{item.measured_at ?? item.measured_date} · {item.module} · {item.source}</div></div>
              <div className="font-mono">{item.value_num ?? item.value_text ?? '—'} {item.unit}</div></div>)}</div>}
        </Card>}
        {view === 'alerts' && <Card title="Alarmlar" icon={ShieldCheck}>
          {alerts.length === 0 ? <p className={subtle}>Kayıtlı alarm yok. Bu, değerlendirme yapıldığı anlamına gelmez.</p>
            : <div className="space-y-3">{alerts.map((item) => <div key={item.alert_id} className="rounded-lg border p-3 text-sm">
              <div className="flex justify-between"><b>{item.severity}</b><span>{item.status}</span></div>
              <div className="text-xs text-slate-500">{item.created_at.slice(0, 16)} · {item.astronaut_id}</div>
              {user.role === 'GROUND_CONTROL' && item.status !== 'RESOLVED' && <div className="mt-2 flex gap-2">
                {item.status === 'OPEN' && <button className="text-sky-700" disabled={busy} onClick={() => void updateAlert(item, 'acknowledge')}>Onayla</button>}
                {item.status === 'ACKNOWLEDGED' && <button className="text-sky-700" disabled={busy} onClick={() => void updateAlert(item, 'resolve')}>Kapat</button>}
              </div>}</div>)}</div>}
        </Card>}
        {view === 'behavior' && user.role === 'ASTRONAUT' && <>
          <Card title="Günlük check-in" icon={ClipboardList}>
            <form key={`${day}-${checkinEtag ?? 'new'}`} onSubmit={(event) => void saveCheckin(event)} className="grid grid-cols-2 gap-3 text-sm">
              {(['mood', 'energy', 'stress', 'loneliness', 'crew', 'mood_index'] as const).map((name) => <label key={name}>{name}
                <input name={name} type="number" required min="0" max={name === 'mood_index' ? 100 : name === 'loneliness' || name === 'crew' ? 4 : 10}
                  defaultValue={currentCheckin?.[name] ?? ''} className={field} /></label>)}
              <label>Yatış saati<input name="bed_time" type="time" required defaultValue={currentCheckin?.bed_time?.slice(0, 5) ?? ''} className={field} /></label>
              <label>Uyanış saati<input name="wake_time" type="time" required defaultValue={currentCheckin?.wake_time?.slice(0, 5) ?? ''} className={field} /></label>
              <label>Uyku kalitesi · 1–5<input name="sleep_quality" type="number" min="1" max="5" required defaultValue={currentCheckin?.sleep_quality ?? ''} className={field} /></label>
              <div className="col-span-2"><button className={button} disabled={busy || !day}>Kaydet</button>
                <p className={`${subtle} mt-2`}>Mood index değerini manuel girin; hesaplama kuralı henüz tanımlı değil.</p></div>
            </form>
          </Card>
          <Card title="Check-in geçmişi" icon={ClipboardList}>
            {checkins.length === 0 ? <p className={subtle}>Bu aralıkta check-in yok.</p>
              : <div className="max-h-72 overflow-auto divide-y">{checkins.map((item) => <div key={item.date} className="flex justify-between py-2 text-sm"><span>{item.date}</span><span>Ruh hâli {item.mood} · Uyku {item.sleep_quality}/5</span></div>)}</div>}
          </Card>
          <Card title="Haftalık değerlendirmeler" icon={ClipboardList}>
            {weekly.length === 0 ? <p className={subtle}>Bu aralıkta değerlendirme yok.</p>
              : <div className="divide-y">{weekly.map((item) => <div key={item.id} className="py-2 text-sm">{item.taken_at.slice(0, 10)} · WHO-5 {item.who5_score} · PHQ-2 {item.phq2_score} · GAD-2 {item.gad2_score}</div>)}</div>}
          </Card>
        </>}
        {view === 'tests' && user.role === 'ASTRONAUT' && <>
          <Card title="Fizyolojik ölçüm ekle" icon={Activity}>
            <form onSubmit={(event) => void saveMeasurement(event)} className="space-y-3 text-sm">
              <label>Ölçüm<select name="measurement" className={`${field} mt-1`}>{Object.entries(MEASURES).map(([code, unit]) => <option key={code} value={code}>{code} · {unit}</option>)}</select></label>
              <label>Değer<input name="value" type="number" step="any" required className={`${field} mt-1`} /></label>
              <p className={subtle}>Tarih: {day}. Gerçek ölçüm saati bilinmiyorsa saat eklenmez.</p>
              <button className={button} disabled={busy || !day}>Ölçümü kaydet</button>
            </form>
          </Card>
          <Card title="Bilişsel test geçmişi" icon={ClipboardList}>
            {cognitive.length === 0 ? <p className={subtle}>Bu aralıkta test kaydı yok.</p>
              : <div className="divide-y">{cognitive.map((item) => <div key={item.id} className="py-2 text-sm">{item.taken_at.slice(0, 16)} · {item.test_type} · {item.valid ? 'geçerli' : 'geçersiz'}
                {item.mean_rt_ms !== null && ` · ${item.mean_rt_ms} ms`}{item.accuracy !== null && ` · doğruluk ${Math.round(item.accuracy * 100)}%`}</div>)}</div>}
          </Card>
        </>}
        {view === 'analysis' && <Card title="Analiz işi" icon={Database}>
          {user.role === 'ASTRONAUT' ? <><p className={subtle}>Model servisi ve eşikler hazır değilken değerlendirme sonucu yetersiz veri olabilir.</p>
            <button className={`${button} mt-3`} disabled={busy || !!job && !['COMPLETED', 'FAILED'].includes(job.state)} onClick={() => void startAnalysis()}>Analiz isteği oluştur</button>
            {job && <div className="mt-3 text-sm">İş: <span className="font-mono">{job.job_id}</span><br />Durum: <b>{job.state}</b>
              {job.evaluation_status && <span> · {job.evaluation_status}</span>}{job.error_code && <span> · {job.error_code}</span>}</div>}
            {result && <div className="mt-3 rounded-lg bg-sky-50 p-3 text-sm"><b>{result.level}</b><p>{result.summary}</p><p>{result.recommendation}</p></div>}</>
            : <p className={subtle}>Analiz işi astronot hesabından başlatılır. Yer kontrolü alarmları izler.</p>}
        </Card>}
        {view === 'knowledge' && user.role === 'GROUND_CONTROL' && <Card title="Bilgi kartları" icon={BookOpen}>
          <p className={`${subtle} mb-3`}>SQL Server’daki kayıtlar: {cards.length}</p>
          <div className="max-h-48 overflow-auto divide-y">{cards.map((item) => <div key={item.card_id} className="py-2 text-sm"><b>{item.card_id}</b> · {item.system}<p className="text-slate-500 line-clamp-2">{item.text}</p></div>)}</div>
          <details className="mt-4"><summary className="cursor-pointer text-sm font-medium text-sky-700">Yeni kart ekle</summary>
            <form onSubmit={(event) => void saveCard(event)} className="mt-3 grid gap-2 text-sm">
              {(['card_id', 'type', 'system', 'metrics', 'direction', 'source', 'url', 'locator'] as const).map((name) =>
                <label key={name}>{name}<input name={name} required className={field} placeholder={name === 'metrics' ? 'virgülle ayrılmış kodlar' : ''} /></label>)}
              <label>text<textarea name="text" required rows={4} className={field} /></label>
              <button className={button} disabled={busy}>Kartı kaydet</button>
            </form></details>
        </Card>}
        {view === 'alerts' && <Card title="Bildirimler" icon={Bell}>
          {events.length === 0 ? <p className={subtle}>Bekleyen bildirim yok.</p>
            : <div className="max-h-72 overflow-auto divide-y">{events.map((item) => <div key={item.event_id} className="py-2 text-sm"><b>{item.event_type}</b>
              <p className="text-slate-500">{item.created_at.slice(0, 16)}</p></div>)}</div>}
        </Card>}
        {view === 'settings' && <Card title="Görev ve hesap" icon={ShieldCheck}>
          <dl className="grid grid-cols-2 gap-3 text-sm"><dt className="text-slate-500">Hesap</dt><dd>{user.email}</dd>
            <dt className="text-slate-500">Rol</dt><dd>{user.role}</dd>
            <dt className="text-slate-500">Astronot</dt><dd>{selectedProfile?.display_name ?? '—'}</dd>
            <dt className="text-slate-500">Görev</dt><dd>{selectedProfile?.mission_name ?? '—'}</dd>
            <dt className="text-slate-500">Başlangıç</dt><dd>{selectedProfile?.mission_start_date ?? '—'}</dd></dl>
        </Card>}
      </div>
    </main>
    <footer className="relative z-10 mx-4 mb-4 rounded-2xl px-4 py-3 text-xs text-slate-600 glass-bar sm:mx-6">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2"><span>{error ? 'Bağlantı kontrol edilmeli' : 'API bağlantısı aktif'} · SQL Server kayıtları</span>
        <span>{selectedProfile?.mission_name ?? 'Görev'} · ASTRA HEALTH</span></div>
    </footer>
  </div>
}
