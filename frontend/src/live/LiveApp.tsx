import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  Activity, Bell, BookOpen, ClipboardList, Database, LogOut, RefreshCw, ShieldCheck,
} from 'lucide-react'
import {
  api, ApiError, type Alert, type Checkin, type Job, type KnowledgeCard,
  type Measurement, type NotificationEvent, type Profile, type Result, type User,
} from './api'

const TOKEN_KEY = 'astra-live-token'
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

export default function LiveApp() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? '')
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [crew, setCrew] = useState<Profile[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [day, setDay] = useState('')
  const [measurements, setMeasurements] = useState<Measurement[]>([])
  const [checkins, setCheckins] = useState<Checkin[]>([])
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

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY)
    setToken(''); setUser(null); setProfile(null); setCrew([])
    setMeasurements([]); setCheckins([]); setAlerts([]); setCards([]); setEvents([])
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
    load.then(({ data }) => {
      if (!active) return
      if (user.role === 'ASTRONAUT') {
        const next = data as Profile
        setProfile(next); setSelectedId(next.astronaut_id); setDay(missionDay(next))
      } else {
        const next = data as Profile[]
        setCrew(next)
        const first = next.find((item) => !item.is_display_only) ?? next[0]
        if (first) { setSelectedId(first.astronaut_id); setDay(missionDay(first)) }
      }
    }).catch(report)
    return () => { active = false }
  }, [token, user, report])

  const loadData = useCallback(async () => {
    if (!token || !user || !selectedId || !day) return
    const start = addDays(day, -29)
    const end = addDays(day, 1)
    try {
      const [readings, alertRows, pending] = await Promise.all([
        api.measurements(token, user.role, selectedId, start, end),
        api.alerts(token, user.role), api.pending(token),
      ])
      setMeasurements(readings.data.filter((row) => row.astronaut_id === selectedId).reverse())
      setAlerts(alertRows.data.filter((row) => row.astronaut_id === selectedId))
      setEvents((previous) => [...pending.data,
        ...previous.filter((item) => !pending.data.some((next) => next.event_id === item.event_id))].slice(0, 20))
      if (user.role === 'ASTRONAUT') {
        const [rows, current] = await Promise.all([
          api.checkins(token, start, end),
          api.checkin(token, day).catch((cause) => {
            if (cause instanceof ApiError && cause.status === 404) return null
            throw cause
          }),
        ])
        setCheckins(rows.data.reverse())
        setCurrentCheckin(current?.data ?? null)
        setCheckinEtag(current?.etag ?? null)
      } else {
        const rows = await api.cards(token)
        setCards(rows.data)
      }
      setError('')
    } catch (cause) { report(cause) }
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
  return <div className="min-h-screen bg-slate-50 text-slate-800">
    <header className="border-b border-slate-200 bg-white px-5 py-4">
      <div className="mx-auto max-w-7xl flex flex-wrap items-center justify-between gap-4">
        <div><div className="text-xs font-bold tracking-[0.25em] text-sky-700">ASTRA HEALTH · CANLI VERİ</div>
          <h1 className="text-xl font-semibold">{user.role === 'ASTRONAUT' ? 'Astronot paneli' : 'Yer kontrolü paneli'}</h1></div>
        <div className="flex items-center gap-3 text-sm"><span className="text-slate-500">{user.email}</span>
          <a href="/" className="rounded-lg border px-3 py-2 hover:bg-slate-50">Orijinal arayüz</a>
          {import.meta.env.DEV ? <div className="flex gap-1" aria-label="Yerel demo rolü">
            <button className="rounded-lg border px-3 py-2 disabled:bg-sky-50 disabled:text-sky-800" disabled={busy || user.role === 'ASTRONAUT'} onClick={() => void switchDevRole('ASTRONAUT')}>Astronot</button>
            <button className="rounded-lg border px-3 py-2 disabled:bg-sky-50 disabled:text-sky-800" disabled={busy || user.role === 'GROUND_CONTROL'} onClick={() => void switchDevRole('GROUND_CONTROL')}>Yer kontrolü</button>
          </div> : <button onClick={logout} className="flex items-center gap-1 rounded-lg border px-3 py-2 hover:bg-slate-50"><LogOut className="h-4 w-4" />Çıkış</button>}</div>
      </div>
    </header>
    <main className="mx-auto max-w-7xl space-y-5 px-4 py-6">
      <div className="grid gap-4 md:grid-cols-[1fr_auto_auto] items-end">
        <div><div className="text-sm text-slate-500">Görev profili</div>
          {user.role === 'GROUND_CONTROL'
            ? <select className={field} value={selectedId} onChange={(event) => { const id = event.target.value; setSelectedId(id)
              const next = crew.find((item) => item.astronaut_id === id); if (next) setDay(missionDay(next)) }}>
                {crew.map((item) => <option key={item.astronaut_id} value={item.astronaut_id}>{item.display_name} · {item.astronaut_id}{item.is_display_only ? ' · gösterim' : ''}</option>)}
              </select>
            : <div className="text-lg font-semibold">{profile?.display_name ?? user.astronaut_id}</div>}
          {selectedProfile && <p className={subtle}>{selectedProfile.mission_name} · {selectedProfile.mission_id}{selectedProfile.is_display_only ? ' · yalnız görüntüleme' : ''}</p>}
        </div>
        <label className="text-sm">Görüntüleme günü<input className={`${field} mt-1`} type="date" value={day} onChange={(event) => setDay(event.target.value)} /></label>
        <button className="flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-white" onClick={() => void loadData()}><RefreshCw className="h-4 w-4" />Yenile</button>
      </div>
      {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {notice && <div role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">{notice}</div>}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Ölçümler · son 30 gün" icon={Activity}>
          {measurements.length === 0 ? <p className={subtle}>Bu aralıkta kayıtlı ölçüm yok.</p>
            : <div className="max-h-80 overflow-auto divide-y divide-slate-100">{measurements.slice(0, 60).map((item) => <div key={item.record_id} className="flex justify-between gap-3 py-2 text-sm">
              <div><div className="font-medium">{item.measurement}</div><div className="text-xs text-slate-500">{item.measured_date} · {item.module} · {item.source}</div></div>
              <div className="font-mono">{item.value_num ?? item.value_text ?? '—'} {item.unit}</div></div>)}</div>}
        </Card>
        <Card title="Alarmlar" icon={ShieldCheck}>
          {alerts.length === 0 ? <p className={subtle}>Kayıtlı alarm yok. Bu, değerlendirme yapıldığı anlamına gelmez.</p>
            : <div className="space-y-3">{alerts.map((item) => <div key={item.alert_id} className="rounded-lg border p-3 text-sm">
              <div className="flex justify-between"><b>{item.severity}</b><span>{item.status}</span></div>
              <div className="text-xs text-slate-500">{item.created_at.slice(0, 16)} · {item.astronaut_id}</div>
              {user.role === 'GROUND_CONTROL' && item.status !== 'RESOLVED' && <div className="mt-2 flex gap-2">
                {item.status === 'OPEN' && <button className="text-sky-700" disabled={busy} onClick={() => void updateAlert(item, 'acknowledge')}>Onayla</button>}
                {item.status === 'ACKNOWLEDGED' && <button className="text-sky-700" disabled={busy} onClick={() => void updateAlert(item, 'resolve')}>Kapat</button>}
              </div>}</div>)}</div>}
        </Card>
        {user.role === 'ASTRONAUT' && <>
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
          <Card title="Fizyolojik ölçüm ekle" icon={Activity}>
            <form onSubmit={(event) => void saveMeasurement(event)} className="space-y-3 text-sm">
              <label>Ölçüm<select name="measurement" className={`${field} mt-1`}>{Object.entries(MEASURES).map(([code, unit]) => <option key={code} value={code}>{code} · {unit}</option>)}</select></label>
              <label>Değer<input name="value" type="number" step="any" required className={`${field} mt-1`} /></label>
              <p className={subtle}>Tarih: {day}. Gerçek ölçüm saati bilinmiyorsa saat eklenmez.</p>
              <button className={button} disabled={busy || !day}>Ölçümü kaydet</button>
            </form>
          </Card>
          <Card title="Analiz işi" icon={Database}>
            <p className={subtle}>Model servisi ve eşikler hazır değilken değerlendirme sonucu yetersiz veri olabilir.</p>
            <button className={`${button} mt-3`} disabled={busy || !!job && !['COMPLETED', 'FAILED'].includes(job.state)} onClick={() => void startAnalysis()}>Analiz isteği oluştur</button>
            {job && <div className="mt-3 text-sm">İş: <span className="font-mono">{job.job_id}</span><br />Durum: <b>{job.state}</b>
              {job.evaluation_status && <span> · {job.evaluation_status}</span>}{job.error_code && <span> · {job.error_code}</span>}</div>}
            {result && <div className="mt-3 rounded-lg bg-sky-50 p-3 text-sm"><b>{result.level}</b><p>{result.summary}</p><p>{result.recommendation}</p></div>}
          </Card>
          <Card title="Check-in geçmişi" icon={ClipboardList}>
            {checkins.length === 0 ? <p className={subtle}>Bu aralıkta check-in yok.</p>
              : <div className="max-h-72 overflow-auto divide-y">{checkins.map((item) => <div key={item.date} className="flex justify-between py-2 text-sm"><span>{item.date}</span><span>Ruh hâli {item.mood} · Uyku {item.sleep_quality}/5</span></div>)}</div>}
          </Card>
        </>}
        {user.role === 'GROUND_CONTROL' && <Card title="Bilgi kartları" icon={BookOpen}>
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
        <Card title="Bildirimler" icon={Bell}>
          {events.length === 0 ? <p className={subtle}>Bekleyen bildirim yok.</p>
            : <div className="max-h-72 overflow-auto divide-y">{events.map((item) => <div key={item.event_id} className="py-2 text-sm"><b>{item.event_type}</b>
              <p className="text-slate-500">{item.created_at.slice(0, 16)}</p></div>)}</div>}
        </Card>
      </div>
    </main>
  </div>
}
