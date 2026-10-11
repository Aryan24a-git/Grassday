import React, { useState, useEffect } from 'react'
import {
  Sun,
  Moon,
  Compass,
  Settings,
  ChevronDown,
  Calendar,
  CloudRain,
  Wind,
  Download,
  Plus,
  X,
  Check,
  RefreshCw,
  Sparkles,
  MapPin,
  Clock,
  Radio,
  Trash2,
} from 'lucide-react'
import confetti from 'canvas-confetti'

const ACTIVITIES = ['Walk', 'Sit in park', 'Run', 'Read outside', 'Gardening', 'Cycling']

const RATING_EMOJIS = [
  { val: 1.0, icon: '🥀', label: 'Rough' },
  { val: 2.0, icon: '🍂', label: 'Meh' },
  { val: 3.0, icon: '🌿', label: 'Pleasant' },
  { val: 4.0, icon: '🌳', label: 'Great' },
  { val: 5.0, icon: '🌲', label: 'Magical' },
]

const API_BASE = import.meta.env.VITE_API_BASE_URL ? import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '') : ''

const FALLBACK_PREDICTION = {
  top_window: {
    window_start: new Date(Date.now() + 3600000 * 2).toISOString(),
    window_end: new Date(Date.now() + 3600000 * 4).toISOString(),
    temperature_2m: 21.5,
    apparent_temperature: 21.0,
    precipitation: 0.0,
    wind_speed_10m: 11.2,
    cloud_cover: 22.0,
    uv_index: 3.2,
    pm2_5: 12.0,
    predicted: 4.6,
    q10: 4.1,
    q50: 4.6,
    q90: 4.9,
    uncertainty: 0.8,
  },
  drivers: [
    { feature: 'wind_speed_10m', label: 'Gentle breeze', value: 11.2, delta: 0.45, abs_delta: 0.45, direction: 'positive' },
    { feature: 'apparent_temperature', label: 'Comfortable thermal feel', value: 21.0, delta: 0.38, abs_delta: 0.38, direction: 'positive' },
    { feature: 'precipitation', label: 'Dry conditions', value: 0.0, delta: 0.25, abs_delta: 0.25, direction: 'positive' },
  ],
  nudge: {
    nudge: 'Crisp autumn air and warm afternoon sun make this your peak window today. Step outside for 20 minutes.',
    notice: ['Golden light filtering through the yellow leaves', 'Crickets in the tall grass', 'A quiet breeze in the shade'],
    pack: ['A light jacket or sweater', 'A reusable water bottle', 'A curiosity for quiet paths'],
    leave_phone_tip: "Leave your phone on your desk — the grass doesn't need Wi-Fi.",
  },
  daily_best: [
    { day_name: 'Today', date_str: 'Oct 11', window_start: '2026-10-11T14:00:00', score: 4.6, temperature: 21.5, cloud_cover: 22, precipitation: 0 },
    { day_name: 'Sun', date_str: 'Oct 12', window_start: '2026-10-12T15:00:00', score: 4.4, temperature: 20.0, cloud_cover: 35, precipitation: 0 },
    { day_name: 'Mon', date_str: 'Oct 13', window_start: '2026-10-13T11:00:00', score: 4.1, temperature: 19.0, cloud_cover: 50, precipitation: 0 },
    { day_name: 'Tue', date_str: 'Oct 14', window_start: '2026-10-14T16:00:00', score: 4.5, temperature: 22.0, cloud_cover: 15, precipitation: 0 },
    { day_name: 'Wed', date_str: 'Oct 15', window_start: '2026-10-15T13:00:00', score: 4.2, temperature: 18.5, cloud_cover: 40, precipitation: 0 },
    { day_name: 'Thu', date_str: 'Oct 16', window_start: '2026-10-16T14:00:00', score: 3.9, temperature: 17.0, cloud_cover: 65, precipitation: 0.2 },
    { day_name: 'Fri', date_str: 'Oct 17', window_start: '2026-10-17T15:00:00', score: 4.7, temperature: 21.0, cloud_cover: 10, precipitation: 0 },
  ],
  confidence: 0.88,
  train_count: 14,
  is_cached: true,
  location: 'Central Park',
  season: 'autumn',
}

export default function App() {
  // Theme state
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('grassday_theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dusk' : 'daylight')
  })

  // Settings & Config
  const [locationName, setLocationName] = useState('Central Park')
  const [lat, setLat] = useState(40.7128)
  const [lon, setLon] = useState(-74.0060)
  const [activity, setActivity] = useState('Walk')
  const [offline, setOffline] = useState(false)
  const [demo, setDemo] = useState(false)
  const [ollamaModel, setOllamaModel] = useState('qwen3')

  // UI state
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isAccordionOpen, setIsAccordionOpen] = useState(false)
  const [isLogModalOpen, setIsLogModalOpen] = useState(false)
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false)
  const [selectedDay, setSelectedDay] = useState(null)
  const [screenTime, setScreenTime] = useState(0)

  // Outing form state
  const [outingDate, setOutingDate] = useState(() => new Date().toISOString().split('T')[0])
  const [outingTime, setOutingTime] = useState(() => {
    const d = new Date()
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  })
  const [outingActivity, setOutingActivity] = useState('Walk')
  const [outingRating, setOutingRating] = useState(3.0)
  const [outingNotes, setOutingNotes] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Sync theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('grassday_theme', theme)
  }, [theme])

  // Screen-time counter
  useEffect(() => {
    const timer = setInterval(() => {
      setScreenTime((prev) => prev + 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Fetch prediction data
  const fetchPrediction = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        lat: lat.toString(),
        lon: lon.toString(),
        location_name: locationName,
        activity,
        offline: offline.toString(),
        ollama_model: ollamaModel,
        demo: demo.toString(),
      })
      const res = await fetch(`${API_BASE}/api/prediction?${params}`)
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Failed to fetch prediction (${res.status})`)
      }
      const json = await res.json()
      setData(json)
      if (json.daily_best && json.daily_best.length > 0) {
        setSelectedDay(json.daily_best[0].day_name)
      }
    } catch (err) {
      console.warn('Backend waking up or unreachable; loading offline cache snapshot:', err)
      // Provide instant graceful offline snapshot so UI is NEVER broken
      setData(FALLBACK_PREDICTION)
      if (FALLBACK_PREDICTION.daily_best && FALLBACK_PREDICTION.daily_best.length > 0) {
        setSelectedDay(FALLBACK_PREDICTION.daily_best[0].day_name)
      }
      setError(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPrediction()
  }, [lat, lon, locationName, activity, offline, demo])

  const toggleTheme = () => {
    setTheme((t) => (t === 'daylight' ? 'dusk' : 'daylight'))
  }

  // Handle logging an outing
  const handleLogOuting = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      const res = await fetch(`${API_BASE}/api/outings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          latitude: lat,
          longitude: lon,
          outing_date: outingDate,
          outing_time: outingTime,
          activity: outingActivity,
          rating: outingRating,
          notes: outingNotes || null,
        }),
      })
      if (!res.ok) throw new Error('Failed to record outing')

      // Confetti burst on successful save
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.8 },
        colors: ['#2E6845', '#479061', '#D9822B', '#E8F2EC'],
      })

      setIsLogModalOpen(false)
      setOutingNotes('')
      fetchPrediction()
    } catch (err) {
      alert(`Error logging outing: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle field card download
  const handleDownloadFieldCard = () => {
    const params = new URLSearchParams({
      lat: lat.toString(),
      lon: lon.toString(),
      location_name: locationName,
      activity,
      ollama_model: ollamaModel,
    })
    window.open(`${API_BASE}/api/field-card?${params}`, '_blank')
  }

  // Handle resetting outings database
  const handleReset = async () => {
    if (!window.confirm('Clear all logged outings and weather cache?')) return
    try {
      await fetch(`${API_BASE}/api/reset`, { method: 'POST' })
      setIsSettingsModalOpen(false)
      fetchPrediction()
    } catch (err) {
      alert(`Reset failed: ${err.message}`)
    }
  }

  // Format time string (e.g. "4:00 pm")
  const formatTime = (isoString) => {
    if (!isoString) return '4:00 pm'
    try {
      const date = new Date(isoString)
      return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }).toLowerCase()
    } catch {
      return isoString
    }
  }

  // Format screen time
  const formatScreenTime = (sec) => {
    const mins = Math.floor(sec / 60)
    const s = sec % 60
    return mins > 0 ? `${mins}m ${s}s` : `${s}s`
  }

  const topWindow = data?.top_window
  const nudge = data?.nudge
  const drivers = data?.drivers || []
  const dailyBest = data?.daily_best || []
  const confidence = data?.confidence || 0.8
  const score = topWindow?.predicted || 3.5
  const trainCount = data?.train_count || 0
  const isCached = data?.is_cached || false

  return (
    <div className="app-shell">
      {/* Ambient background with morphing liquid blobs */}
      <div className="ambient-background">
        <div className="liquid-blob liquid-blob-1" />
        <div className="liquid-blob liquid-blob-2" />
        <div className="liquid-blob liquid-blob-3" />
      </div>

      {/* Top Header */}
      <header className="app-header">
        <a href="#" className="brand-badge" onClick={(e) => { e.preventDefault(); fetchPrediction(); }}>
          <div className="brand-icon-wrapper">🌿</div>
          <span>Grassday</span>
        </a>

        <div className="header-actions">
          <button
            className="icon-btn"
            onClick={toggleTheme}
            aria-label="Toggle Daylight / Dusk"
            title={theme === 'daylight' ? 'Switch to Dusk' : 'Switch to Daylight'}
          >
            {theme === 'daylight' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          <button
            className="icon-btn"
            onClick={() => setIsSettingsModalOpen(true)}
            aria-label="Settings"
            title="Settings"
          >
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      {loading ? (
        <div className="glass-card loading-container">
          <div className="pulse-sprout">🌱</div>
          <p style={{ color: 'var(--text-muted)', fontWeight: 500 }}>
            Scanning forecast & finding your window...
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', opacity: 0.75, marginTop: '0.25rem' }}>
            Connecting to TabPFN model (free-tier Render cold boot may take ~30s on first load)
          </p>
        </div>
      ) : error ? (
        <div className="glass-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
          <h3 style={{ fontFamily: 'var(--font-serif)', marginBottom: '0.5rem', color: 'var(--accent-danger)' }}>
            Unable to load weather
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
            {error}
          </p>
          <button className="btn-primary" onClick={fetchPrediction}>
            <RefreshCw size={16} /> Try Again
          </button>
        </div>
      ) : topWindow && (
        <>
          {/* Hero Recommendation Card */}
          <section className="glass-card hero-card">
            <div className="hero-pill-row">
              <div className="location-pill">
                <MapPin size={13} style={{ color: 'var(--accent-moss)' }} />
                <span>{locationName}</span>
              </div>

              <div className={`status-pill ${isCached ? 'cached' : 'live'}`}>
                <Radio size={12} />
                <span>{isCached ? 'Offline Cache' : 'Live Open-Meteo'}</span>
              </div>
            </div>

            <div>
              <div className="hero-time-heading">
                {formatTime(topWindow.window_start)}
              </div>
              <div className="hero-condition-summary">
                <span>{topWindow.temperature_2m}°C</span>
                <span>•</span>
                <span>
                  {topWindow.precipitation > 0.5
                    ? 'Light rain'
                    : topWindow.cloud_cover < 30
                    ? 'Clear skies'
                    : topWindow.pm2_5 < 15
                    ? 'Clean air'
                    : 'Calm breeze'}
                </span>
                <span>•</span>
                <span style={{ fontStyle: 'italic' }}>{activity.toLowerCase()}</span>
              </div>
            </div>

            {/* Score & Confidence Radial Gauge */}
            <div className="hero-score-row">
              <div className="score-radial">
                <svg width="58" height="58" viewBox="0 0 58 58">
                  <circle
                    cx="29"
                    cy="29"
                    r="24"
                    fill="none"
                    stroke="rgba(0,0,0,0.06)"
                    strokeWidth="4"
                  />
                  <circle
                    cx="29"
                    cy="29"
                    r="24"
                    fill="none"
                    stroke="var(--accent-moss)"
                    strokeWidth="4"
                    strokeDasharray={2 * Math.PI * 24}
                    strokeDashoffset={2 * Math.PI * 24 * (1 - confidence)}
                    strokeLinecap="round"
                    style={{ transition: 'stroke-dashoffset 1s ease' }}
                  />
                </svg>
                <div className="score-radial-val">{score}</div>
              </div>

              <div className="score-meta-text">
                <span className="score-label">/5 Predicted Enjoyment</span>
                <span className="score-sublabel">
                  TabPFN {Math.round(confidence * 100)}% confidence • 7-day optimum
                </span>
              </div>
            </div>

            {/* Accordion: Why this window? */}
            <div style={{ borderTop: '1px solid var(--glass-border-subtle)', marginTop: '0.25rem' }}>
              <button
                className="accordion-header"
                onClick={() => setIsAccordionOpen(!isAccordionOpen)}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles size={16} style={{ color: 'var(--accent-amber)' }} />
                  Why this window?
                </span>
                <ChevronDown size={18} className={`accordion-icon ${isAccordionOpen ? 'open' : ''}`} />
              </button>

              {isAccordionOpen && (
                <div className="accordion-content">
                  {/* Drivers Chips */}
                  <div className="chips-cloud">
                    {drivers.map((d, i) => (
                      <div
                        key={i}
                        className={`feature-chip ${d.direction === 'positive' ? 'positive' : 'negative'}`}
                      >
                        <span>{d.direction === 'positive' ? '↑' : '↓'}</span>
                        <span>{d.label || d.feature}</span>
                      </div>
                    ))}
                  </div>

                  {/* Nudge Breakdown */}
                  {nudge && (
                    <>
                      <div className="nudge-breakdown-grid">
                        <div className="nudge-list-col">
                          <h5>Notice Outside</h5>
                          <ul>
                            {(nudge.notice || []).map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </div>
                        <div className="nudge-list-col">
                          <h5>Pack With You</h5>
                          <ul>
                            {(nudge.pack || []).map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      </div>

                      {nudge.leave_phone_tip && (
                        <div className="leave-phone-banner">
                          <span>📴</span>
                          <span>{nudge.leave_phone_tip}</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* Primary Action Buttons (Prominent under Hero Recommendation) */}
          <section className="action-row">
            <button className="btn-primary" onClick={() => setIsLogModalOpen(true)}>
              <Plus size={18} /> Log an Outing
            </button>
            <button className="btn-secondary" onClick={handleDownloadFieldCard}>
              <Download size={18} /> Print Field Card
            </button>
          </section>

          {/* 7-Day Forecast Strip */}
          <section>
            <div className="week-section-title">Next 7 Days — Best Windows</div>
            <div className="week-scroll-container">
              {dailyBest.map((day, idx) => {
                const isActive = selectedDay === day.day_name
                const heatOpacity = Math.min(1.0, Math.max(0.2, (day.score - 1.0) / 4.0))
                return (
                  <div
                    key={idx}
                    className={`day-tile-card ${isActive ? 'active' : ''}`}
                    onClick={() => setSelectedDay(day.day_name)}
                  >
                    <span className="day-name">{day.day_name}</span>
                    <span className="day-score">{day.score}</span>
                    <span className="day-temp">{Math.round(day.temperature)}°C</span>
                    <div className="day-heat-bar" style={{ opacity: heatOpacity }} />
                  </div>
                )
              })}
            </div>
          </section>

          {/* Plant Progress Indicator */}
          <section className="glass-card" style={{ padding: '1.25rem 1.5rem' }}>
            <div className="plant-progress-bar-wrapper">
              <div className="plant-status-text">
                <span>🌱</span>
                <span>
                  {trainCount >= 10
                    ? 'Personalization unlocked (10+ outings logged)'
                    : `${10 - trainCount} more outings until TabPFN predictions become personal`}
                </span>
              </div>
              <div className="plant-track">
                <div
                  className="plant-fill"
                  style={{ width: `${Math.min(100, (trainCount / 10) * 100)}%` }}
                />
              </div>
            </div>
          </section>
        </>
      )}

      {/* Floating Screen-Time Footer */}
      <footer className="screen-time-floating-pill">
        <Clock size={14} />
        <span>Screen-time budget:</span>
        <span className="screen-time-highlight">{formatScreenTime(screenTime)}</span>
        <span>• The grass misses you.</span>
      </footer>

      {/* ─── Modal: Log an Outing ────────────────────────────────────────── */}
      {isLogModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsLogModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Log an Outing</h3>
              <button
                className="icon-btn"
                style={{ width: 32, height: 32 }}
                onClick={() => setIsLogModalOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleLogOuting} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="form-group">
                  <label className="form-label">Date</label>
                  <input
                    type="date"
                    className="form-input"
                    value={outingDate}
                    onChange={(e) => setOutingDate(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Time</label>
                  <input
                    type="time"
                    className="form-input"
                    value={outingTime}
                    onChange={(e) => setOutingTime(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Activity</label>
                <select
                  className="form-select"
                  value={outingActivity}
                  onChange={(e) => setOutingActivity(e.target.value)}
                >
                  {ACTIVITIES.map((act) => (
                    <option key={act} value={act}>{act}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Enjoyment Rating</label>
                <div className="rating-leaf-row">
                  {RATING_EMOJIS.map((item) => (
                    <button
                      key={item.val}
                      type="button"
                      className={`rating-leaf-btn ${outingRating === item.val ? 'active' : ''}`}
                      onClick={() => setOutingRating(item.val)}
                    >
                      <div>{item.icon}</div>
                      <span>{item.val}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Notes (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Warm sun, birds singing in the park..."
                  value={outingNotes}
                  onChange={(e) => setOutingNotes(e.target.value)}
                />
              </div>

              <button type="submit" className="btn-primary" disabled={isSubmitting} style={{ marginTop: '0.5rem' }}>
                {isSubmitting ? 'Saving...' : '✅ Save Outing (10s)'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ─── Modal: Settings & Preferences ───────────────────────────────── */}
      {isSettingsModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsSettingsModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Settings</h3>
              <button
                className="icon-btn"
                style={{ width: 32, height: 32 }}
                onClick={() => setIsSettingsModalOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Location Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={locationName}
                  onChange={(e) => setLocationName(e.target.value)}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="form-group">
                  <label className="form-label">Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    className="form-input"
                    value={lat}
                    onChange={(e) => setLat(parseFloat(e.target.value) || 0)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    className="form-input"
                    value={lon}
                    onChange={(e) => setLon(parseFloat(e.target.value) || 0)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Activity</label>
                <select
                  className="form-select"
                  value={activity}
                  onChange={(e) => setActivity(e.target.value)}
                >
                  {ACTIVITIES.map((act) => (
                    <option key={act} value={act}>{act}</option>
                  ))}
                </select>
              </div>

              <label className="settings-toggle-row">
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>📴 Offline Mode</span>
                <input
                  type="checkbox"
                  style={{ width: 18, height: 18, accentColor: 'var(--accent-moss)', cursor: 'pointer' }}
                  checked={offline}
                  onChange={(e) => setOffline(e.target.checked)}
                />
              </label>

              <label className="settings-toggle-row">
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>🎬 Demo Mode (25 seeded logs)</span>
                <input
                  type="checkbox"
                  style={{ width: 18, height: 18, accentColor: 'var(--accent-moss)', cursor: 'pointer' }}
                  checked={demo}
                  onChange={(e) => setDemo(e.target.checked)}
                />
              </label>

              <div style={{ borderTop: '1px solid var(--glass-border-subtle)', paddingTop: '1rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleReset}
                  style={{ width: '100%', borderColor: 'rgba(217, 83, 79, 0.35)', color: 'var(--accent-danger)' }}
                >
                  <Trash2 size={16} /> Reset Outings & Clear Cache
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
