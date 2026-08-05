import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import {
    Bar,
    BarChart,
    CartesianGrid,
    Legend,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from 'recharts'
import { saveYieldToChart, uploadYieldImage, uploadYieldVideo } from '../api/dashboard'
import { fetchYield } from '../api/yieldApi'
import LoadingSpinner from '../components/LoadingSpinner'

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
}
const item = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }

const CHART_COLORS = { line: '#2f6a21', bar: '#3c7b2b', barAlt: '#6bb854' }

export default function YieldPrediction() {
  const [loading, setLoading] = useState(true)
  const [datasetKey, setDatasetKey] = useState('estimation')
  const [data, setData] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const fileInputRef = useRef(null)
  const videoInputRef = useRef(null)
  const [loadingDetect, setLoadingDetect] = useState(false)
  const [detectionResult, setDetectionResult] = useState(null)
  const [videoCountResult, setVideoCountResult] = useState(null)
  const [videoUploading, setVideoUploading] = useState(false)
  const [videoError, setVideoError] = useState(null)
  const [streamUrl, setStreamUrl] = useState('')
  const [streamLoading, setStreamLoading] = useState(false)
  const [streamResult, setStreamResult] = useState(null)
  // Live capture (auto-count) – separate stream so existing UI isn't affected
  const liveVideoRef = useRef(null)
  const liveCanvasRef = useRef(null)
  const liveStreamRef = useRef(null)
  const liveIntervalRef = useRef(null)
  const liveProcessingRef = useRef(false)
  const liveTracksRef = useRef([])
  const liveNextTrackIdRef = useRef(1)
  const [liveActive, setLiveActive] = useState(false)
  const [liveDetecting, setLiveDetecting] = useState(false)
  const [liveFrameMatureCount, setLiveFrameMatureCount] = useState(0)
  const [liveSessionTotal, setLiveSessionTotal] = useState(() => {
    // Load saved session total from localStorage on mount
    try {
      const saved = localStorage.getItem('liveSessionTotal')
      console.log('📦 Loaded from localStorage:', saved)
      return saved ? parseInt(saved, 10) : 0
    } catch (err) {
      console.warn('⚠️ localStorage read failed:', err)
      return 0
    }
  })
  const [liveLastCountedAt, setLiveLastCountedAt] = useState(null)
  const [liveError, setLiveError] = useState(null)
  const [liveDetections, setLiveDetections] = useState([])
  const [chartRefreshing, setChartRefreshing] = useState(false)
  const [savingToChart, setSavingToChart] = useState(false)
  const [savedMessage, setSavedMessage] = useState(null)
  const [blockName, setBlockName] = useState('Field A')

  // Load/refresh chart data from API
  const loadChartData = async (showSpinner = false) => {
    if (showSpinner) setChartRefreshing(true)
    try {
      const freshData = await fetchYield()
      setData(freshData)
    } finally {
      if (showSpinner) setChartRefreshing(false)
    }
  }

  useEffect(() => {
    fetchYield()
      .then(setData)
      .finally(() => setLoading(false))

    // Poll every 30 seconds to keep charts real-time
    const interval = setInterval(() => loadChartData(false), 30000)
    return () => clearInterval(interval)
  }, [])

  // Persist live session total to localStorage - with error handling
  useEffect(() => {
    try {
      const valueToSave = liveSessionTotal.toString()
      localStorage.setItem('liveSessionTotal', valueToSave)
      console.log('✅ Saved to localStorage:', valueToSave)
    } catch (err) {
      console.error('❌ localStorage write failed:', err)
      // Try sessionStorage as fallback
      try {
        sessionStorage.setItem('liveSessionTotal', liveSessionTotal.toString())
        console.log('💾 Fallback to sessionStorage:', liveSessionTotal)
      } catch (fallbackErr) {
        console.error('❌ sessionStorage fallback also failed:', fallbackErr)
      }
    }
  }, [liveSessionTotal])

  // Handlers for file upload and camera capture
  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file || !file.type.startsWith('image/')) return
    setDetectionResult(null)
    setPreviewUrl(URL.createObjectURL(file))
    // Reset so the same file can be selected again immediately
    e.target.value = ''
    runDetection(file)
  }

  const handleVideoChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !file.type.startsWith('video/')) {
      setVideoError('Please select a video file (mp4, mov, etc.).')
      return
    }
    setVideoError(null)
    setVideoCountResult(null)
    // Reset so same video can be re-selected
    e.target.value = ''
    try {
      setVideoUploading(true)
      const resp = await uploadYieldVideo(file, 0.25)
      if (resp && resp.success) {
        setVideoCountResult(resp.data)
        // Refresh charts with new data
        loadChartData(true)
      } else {
        console.warn('Video detection failed', resp)
        setVideoError(resp?.error || 'Video detection failed. Please try again.')
      }
    } catch (err) {
      console.error('Video detection error', err)
      setVideoError('Server error while processing video.')
    } finally {
      setVideoUploading(false)
    }
  }

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
    } catch (err) {
      console.warn('Camera start failed', err)
    }
  }

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }

  const capturePhoto = () => {
    if (!videoRef.current) return
    const canvas = document.createElement('canvas')
    canvas.width = videoRef.current.videoWidth
    canvas.height = videoRef.current.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(videoRef.current, 0, 0)
    canvas.toBlob((blob) => {
      if (!blob) return
      const file = new File([blob], 'capture.jpg', { type: 'image/jpeg' })
      setPreviewUrl(URL.createObjectURL(blob))
      runDetection(file)
    }, 'image/jpeg', 0.9)
  }

  const stopLiveCapture = () => {
    if (liveIntervalRef.current) {
      clearInterval(liveIntervalRef.current)
      liveIntervalRef.current = null
    }
    liveProcessingRef.current = false
    liveStreamRef.current?.getTracks().forEach((t) => t.stop())
    liveStreamRef.current = null
    if (liveVideoRef.current) liveVideoRef.current.srcObject = null
    setLiveActive(false)
    setLiveDetecting(false)
    setLiveDetections([])
    // Clear canvas
    if (liveCanvasRef.current) {
      const ctx = liveCanvasRef.current.getContext('2d')
      if (ctx) ctx.clearRect(0, 0, liveCanvasRef.current.width, liveCanvasRef.current.height)
    }
  }

  const startLiveCapture = async () => {
    if (liveActive) return
    setLiveError(null)
    setLiveFrameMatureCount(0)
    // Don't reset liveSessionTotal - keep it persisted across sessions
    setLiveLastCountedAt(null)
    setLiveDetections([])
    liveTracksRef.current = []
    liveNextTrackIdRef.current = 1
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      })
      liveStreamRef.current = stream
      if (liveVideoRef.current) liveVideoRef.current.srcObject = stream

      setLiveActive(true)
      // Run detection periodically. This is a tradeoff between responsiveness and server load.
      liveIntervalRef.current = setInterval(async () => {
        if (!liveVideoRef.current) return
        if (liveProcessingRef.current) return
        if (liveVideoRef.current.readyState < 2) return

        liveProcessingRef.current = true
        setLiveDetecting(true)

        try {
          const videoW = liveVideoRef.current.videoWidth || 640
          const videoH = liveVideoRef.current.videoHeight || 480
          const canvas = document.createElement('canvas')
          canvas.width = videoW
          canvas.height = videoH
          const ctx = canvas.getContext('2d')
          ctx.drawImage(liveVideoRef.current, 0, 0)

          const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.7))
          if (!blob) return

          const file = new File([blob], 'live_frame.jpg', { type: 'image/jpeg' })
          const resp = await uploadYieldImage(file, 0.25)
          if (!resp || !resp.success) return

          const detections = Array.isArray(resp.data?.detections) ? resp.data.detections : []
          const matureDetections = detections.filter((d) => String(d?.label || '').toLowerCase() === 'mature' && Array.isArray(d?.box) && d.box.length === 4)
          setLiveFrameMatureCount(matureDetections.length)
          setLiveDetections(matureDetections)

          // --- Lightweight tracker to avoid double counting across frames ---
          // Each detection becomes a centroid point; if it matches an existing track (within a distance threshold)
          // we treat it as the same fruit. Otherwise we create a new track and increment the session total.
          const now = Date.now()
          const diag = Math.sqrt(videoW * videoW + videoH * videoH)
          const matchDist = diag * 0.06 // ~6% of diagonal; adjust if needed for your camera height
          const tracks = liveTracksRef.current
          const usedTrackIds = new Set()
          let newlyCounted = 0

          for (const det of matureDetections) {
            const [x1, y1, x2, y2] = det.box
            const cx = (x1 + x2) / 2
            const cy = (y1 + y2) / 2

            let best = null
            let bestDist = Infinity
            for (const tr of tracks) {
              if (usedTrackIds.has(tr.id)) continue
              const dx = tr.cx - cx
              const dy = tr.cy - cy
              const dist = Math.sqrt(dx * dx + dy * dy)
              if (dist < bestDist) {
                bestDist = dist
                best = tr
              }
            }

            if (best && bestDist <= matchDist) {
              usedTrackIds.add(best.id)
              best.cx = cx
              best.cy = cy
              best.lastSeen = now
            } else {
              const id = liveNextTrackIdRef.current++
              tracks.push({ id, cx, cy, lastSeen: now })
              usedTrackIds.add(id)
              newlyCounted += 1
            }
          }

          // Drop stale tracks (fruit not visible anymore)
          liveTracksRef.current = tracks.filter((t) => now - t.lastSeen <= 2000)

          if (newlyCounted > 0) {
            console.log(`🍓 Detected ${newlyCounted} new mature fruits! Total now:`, liveSessionTotal + newlyCounted)
            setLiveSessionTotal((v) => {
              const newVal = v + newlyCounted
              console.log(`📊 State updated: ${v} + ${newlyCounted} = ${newVal}`)
              return newVal
            })
            setLiveLastCountedAt(new Date().toISOString())
          }
        } catch (err) {
          console.error('Live capture error', err)
          setLiveError('Live capture failed. Please check camera permission and API availability.')
        } finally {
          liveProcessingRef.current = false
          setLiveDetecting(false)
        }
      }, 1500)
    } catch (err) {
      console.warn('Live camera start failed', err)
      setLiveError('Camera permission denied or camera not available.')
      stopLiveCapture()
    }
  }

  // Ensure we stop the live stream when navigating away
  useEffect(() => {
    return () => stopLiveCapture()
  }, [])

  // Draw bounding boxes on the live canvas overlay
  useEffect(() => {
    if (!liveCanvasRef.current || !liveVideoRef.current) return

    const canvas = liveCanvasRef.current
    const video = liveVideoRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Set canvas size to match video dimensions
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
    }

    // Always clear the canvas first
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw bounding boxes only if there are detections
    if (liveDetections.length > 0) {
      liveDetections.forEach((det) => {
        if (Array.isArray(det.box) && det.box.length === 4) {
          const [x1, y1, x2, y2] = det.box
          
          // Blue box for mature fruits
          ctx.strokeStyle = '#0066FF'
          ctx.lineWidth = 3
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
          
          // Label with confidence
          const label = `MATURE ${(det.confidence * 100).toFixed(0)}%`
          ctx.fillStyle = '#0066FF'
          ctx.font = 'bold 14px sans-serif'
          ctx.fillRect(x1, Math.max(0, y1 - 25), ctx.measureText(label).width + 8, 25)
          ctx.fillStyle = '#FFFFFF'
          ctx.fillText(label, x1 + 4, y1 - 8)
        }
      })
    }
  }, [liveDetections])

  const runDetection = async (file) => {
    setSavedMessage(null)
    try {
      setLoadingDetect(true)
      setDetectionResult(null)
      const resp = await uploadYieldImage(file, 0.25)
      if (resp && resp.success) {
        setDetectionResult(resp.data)
      } else {
        console.warn('Detection failed', resp)
      }
    } catch (err) {
      console.error('Detection error', err)
    } finally {
      setLoadingDetect(false)
    }
  }

  const handleSaveToChart = async (matureFruits, uploadType = 'image') => {
    setSavingToChart(true)
    setSavedMessage(null)
    const location = blockName.trim() || 'Field A'
    try {
      console.log(`💾 Saving ${matureFruits} fruits to yield report (Location: ${location}, Type: ${uploadType})`)
      const resp = await saveYieldToChart(matureFruits, location, null, uploadType)
      if (resp && resp.success) {
        setSavedMessage({ type: 'success', text: `✅ Saved ${matureFruits} fruits (${location}) to chart!` })
        console.log('✅ Successfully saved to yield report')
        loadChartData(true)
      } else {
        setSavedMessage({ type: 'error', text: `❌ Failed to save: ${resp?.error || 'Unknown error'}` })
        console.error('❌ Save failed:', resp?.error)
      }
    } catch (err) {
      setSavedMessage({ type: 'error', text: `❌ Error: ${err.message}` })
      console.error('❌ Save error:', err)
    } finally {
      setSavingToChart(false)
    }
  }

  if (loading || !data) return <LoadingSpinner className="min-h-[60vh]" />

  const { yieldEstimation, yieldByBlock, historicalYield } = data

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="max-w-6xl mx-auto space-y-6"
    >
      <div>
        <h1 className="font-display font-bold text-2xl text-gray-900 dark:text-gray-100">Yield Prediction</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-1 text-base">Drone-based yield estimation and historical comparison.</p>
      </div>

      {/* Drone image preview panel with Upload + Camera */}
      <motion.div variants={item} className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-600">
          <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-gray-100">Drone Image Preview</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Upload or capture an image or video to estimate mature fruits.</p>
        </div>
        <div className="p-6">
          <div className="flex gap-3 mb-4">
            <label className="flex-1">
              <input id="yield-file" type="file" accept="image/*" className="sr-only" onChange={(e) => handleFileChange(e)} />
              <div className="min-h-[140px] rounded-lg border-2 border-dashed flex items-center justify-center cursor-pointer p-4">
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <span className="text-3xl block mb-2">📤</span>
                  <p className="text-sm">Click to select or drag-and-drop an image</p>
                </div>
              </div>
            </label>

            <div className="w-1/3 flex flex-col gap-2">
              <button type="button" onClick={startCamera} className="min-h-[44px] px-3 rounded-xl bg-pitaya-primary text-white">Start Camera</button>
              <button type="button" onClick={capturePhoto} className="min-h-[44px] px-3 rounded-xl border border-pitaya-primary text-pitaya-primary">Capture</button>
              <button type="button" onClick={stopCamera} className="min-h-[44px] px-3 rounded-xl border">Stop</button>
            </div>
          </div>

          <div className="flex items-center gap-3 mb-4">
            <label>
              <input type="file" accept="video/*" className="sr-only" onChange={handleVideoChange} />
              <div className="min-h-[44px] px-4 py-2 rounded-xl border border-dashed cursor-pointer text-sm text-gray-600 dark:text-gray-200">
                📹 Upload video file to count <span className="font-semibold">mature fruits</span>
              </div>
            </label>
            {videoUploading && <span className="text-sm text-gray-500 dark:text-gray-400">Processing video… this may take a few seconds.</span>}
          </div>

          

          {/* Live capture box (auto-count mature fruits) */}
          <div className="mb-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-white/60 dark:bg-gray-900/40 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-gray-800 dark:text-gray-100">Live Capture (Auto Count Mature Fruits)</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  When the camera sees a mature fruit, the system runs detection every ~1.5s and automatically increments the session count for newly-seen fruits.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={startLiveCapture}
                  disabled={liveActive}
                  className="min-h-[40px] px-4 rounded-lg bg-pitaya-primary text-white text-sm disabled:opacity-50"
                >
                  {liveActive ? 'Live Capture Running…' : 'Start Live Capture'}
                </button>
                <button
                  type="button"
                  onClick={stopLiveCapture}
                  className="min-h-[40px] px-4 rounded-lg border text-sm"
                >
                  Stop
                </button>
              </div>
            </div>

            {liveError && (
              <p className="mt-2 text-xs font-medium text-red-600 dark:text-red-400">{liveError}</p>
            )}

            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 bg-black relative">
                <video ref={liveVideoRef} autoPlay playsInline muted className="w-full h-56 md:h-64 object-contain" onLoadedMetadata={() => {
                  if (liveCanvasRef.current && liveVideoRef.current) {
                    liveCanvasRef.current.width = liveVideoRef.current.videoWidth
                    liveCanvasRef.current.height = liveVideoRef.current.videoHeight
                  }
                }} />
                <canvas
                  ref={liveCanvasRef}
                  className="absolute inset-0 w-full h-full object-contain"
                  style={{ pointerEvents: 'none' }}
                />
              </div>

              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">Auto Count Status</p>
                  {liveDetecting && <span className="text-xs text-gray-500 dark:text-gray-400">Detecting…</span>}
                </div>
                <div className="mt-2 space-y-1 text-sm text-gray-700 dark:text-gray-200">
                  <div className="flex items-center justify-between">
                    <span>Current frame (mature fruits)</span>
                    <span className="font-semibold text-pitaya-primary">{liveFrameMatureCount}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Session total (unique-ish)</span>
                    <span className="font-semibold text-pitaya-primary">{liveSessionTotal}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Last counted</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {liveLastCountedAt ? new Date(liveLastCountedAt).toLocaleTimeString() : '—'}
                    </span>
                  </div>
                </div>
                <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
                  Tip: If you see double counting, increase camera stability or reduce movement; this tracker matches fruits by bounding-box centroid distance across frames.
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => handleSaveToChart(liveSessionTotal, 'image')}
                    disabled={savingToChart || liveSessionTotal === 0}
                    className="min-h-[36px] px-3 py-1.5 rounded-lg bg-pitaya-primary text-white hover:bg-pitaya-leaf disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-xs font-medium"
                  >
                    {savingToChart ? '⏳ Saving...' : '💾 Save to Report'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setLiveSessionTotal(0)
                      try {
                        localStorage.setItem('liveSessionTotal', '0')
                        sessionStorage.setItem('liveSessionTotal', '0')
                        console.log('🔄 Reset session count to 0')
                      } catch (err) {
                        console.error('Reset failed:', err)
                      }
                    }}
                    className="min-h-[36px] px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-xs font-medium"
                  >
                    Reset Count
                  </button>
                </div>
                {savedMessage && (
                  <p className={`mt-2 text-xs text-center ${
                    savedMessage.type === 'success' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                  }`}>{savedMessage.text}</p>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Camera / Preview panel - always shows camera when active */}
            <div className="rounded-lg overflow-hidden bg-gray-50 dark:bg-gray-900 min-h-[200px] flex flex-col items-center justify-center relative">
              <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-contain" />
              {previewUrl && !streamRef.current && (
                <img src={previewUrl} alt="Captured preview" className="absolute inset-0 w-full h-full object-contain" />
              )}
              {previewUrl && (
                <button
                  type="button"
                  onClick={() => { setPreviewUrl(null); setDetectionResult(null) }}
                  className="absolute top-2 right-2 bg-white/90 dark:bg-gray-800/90 text-xs px-2 py-1 rounded-full border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:text-red-500 shadow"
                >
                  ✕ Clear
                </button>
              )}
            </div>

            <div className="rounded-lg overflow-auto p-3 bg-white dark:bg-gray-800">
              <p className="font-medium text-gray-900 dark:text-gray-100 mb-2">Image Detection Result</p>
              {loadingDetect && <LoadingSpinner />}
              {!loadingDetect && detectionResult && (
                <div>
                  <img src={detectionResult.annotated_image} alt="Annotated" className="w-full mb-2" />
                  <ul className="space-y-1 text-sm mb-3">
                    {detectionResult.detections.map((d, i) => (
                      <li key={i} className="flex items-center justify-between">
                        <div>
                          <strong>{d.label === 'MATURE' ? 'MATURE FRUIT' : d.label}</strong>
                          <div className="text-xs text-gray-500 dark:text-gray-400">Confidence: {(d.confidence * 100).toFixed(1)}%</div>
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-300">Box: {d.box.map(n => Math.round(n)).join(', ')}</div>
                      </li>
                    ))}
                  </ul>
                  {(() => {
                    const matureCount = detectionResult.detections.filter(d => d.label === 'MATURE').length
                    return (
                      <div className="border-t pt-3 space-y-2">
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          Mature fruits detected: <span className="font-semibold text-pitaya-primary">{matureCount}</span>
                        </p>
                        <div className="flex flex-col gap-1">
                          <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">Block / Location</label>
                          <input
                            type="text"
                            value={blockName}
                            onChange={e => setBlockName(e.target.value)}
                            placeholder="e.g. Block A, Field 1"
                            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm"
                          />
                        </div>
                        <button
                          type="button"
                          disabled={savingToChart || matureCount === 0}
                          onClick={() => handleSaveToChart(matureCount, 'image')}
                          className="w-full min-h-[38px] px-4 rounded-lg bg-pitaya-primary text-white text-sm font-medium hover:bg-pitaya-leaf disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                        >
                          {savingToChart ? (
                            <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Saving…</>
                          ) : (
                            <>📊 Save {matureCount} fruits to Chart</>
                          )}
                        </button>
                        {savedMessage && (
                          <p className={`text-xs font-medium ${
                            savedMessage.type === 'success' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                          }`}>{savedMessage.text}</p>
                        )}
                      </div>
                    )
                  })()}
                </div>
              )}
              {!loadingDetect && !detectionResult && (
                <p className="text-sm text-gray-500 dark:text-gray-400">No detections yet. Upload or capture an image.</p>
              )}
            </div>
          </div>

          {/* Video detection summary card */}
          <div className="mt-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 p-4">
            <p className="font-medium text-gray-900 dark:text-gray-50 mb-1">Video Detection Summary</p>
            {videoError && (
              <p className="text-sm text-red-600 dark:text-red-400 mb-1">{videoError}</p>
            )}
            {!videoUploading && videoCountResult && !videoError && (
              <>
                <p className="text-sm text-gray-700 dark:text-gray-200 mb-2">
                  Total mature fruits detected in the uploaded video:{' '}
                  <span className="font-semibold text-pitaya-primary">{videoCountResult.total_mature_fruits}</span>
                  {videoCountResult.frame_count ? ` (processed ${videoCountResult.frame_count} frames)` : ''}.
                </p>
                <div className="flex flex-col gap-1 mb-2">
                  <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">Block / Location</label>
                  <input
                    type="text"
                    value={blockName}
                    onChange={e => setBlockName(e.target.value)}
                    placeholder="e.g. Block A, Field 1"
                    className="w-full max-w-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm"
                  />
                </div>
                <button
                  type="button"
                  disabled={savingToChart}
                  onClick={() => handleSaveToChart(videoCountResult.total_mature_fruits, 'video')}
                  className="mb-3 min-h-[38px] px-4 rounded-lg bg-pitaya-primary text-white text-sm font-medium hover:bg-pitaya-leaf disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  {savingToChart ? (
                    <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Saving…</>
                  ) : (
                    <>📊 Save {videoCountResult.total_mature_fruits} fruits to Chart</>
                  )}
                </button>
                {savedMessage && (
                  <p className={`text-xs font-medium mb-2 ${
                    savedMessage.type === 'success' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                  }`}>{savedMessage.text}</p>
                )}
                
                {/* Original uploaded video */}
                {videoCountResult.original_video_url && (
                  <div className="mt-3">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1 font-medium">Original uploaded video:</p>
                    <video
                      className="w-full max-h-64 rounded-lg border border-gray-300 dark:border-gray-700 bg-black"
                      controls
                      controlsList="nodownload"
                      src={`http://192.168.1.59:5001${videoCountResult.original_video_url}`}
                    />
                  </div>
                )}

                {/* Annotated result video */}
                {videoCountResult.annotated_video_url && (
                  <div className="mt-3">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1 font-medium">Annotated result video (with detection boxes):</p>
                    <video
                      className="w-full max-h-64 rounded-lg border border-gray-300 dark:border-gray-700 bg-black"
                      controls
                      controlsList="nodownload"
                      src={`http://192.168.1.59:5001${videoCountResult.annotated_video_url}`}
                    />
                    <a
                      href={`http://192.168.1.59:5001${videoCountResult.annotated_video_url}`}
                      download
                      className="mt-2 inline-block text-xs text-pitaya-primary hover:underline"
                    >
                      Download annotated video (open in VLC/Movies app if browser preview is blank)
                    </a>
                  </div>
                )}
              </>
            )}
            {!videoUploading && !videoCountResult && !videoError && (
              <p className="text-sm text-gray-500 dark:text-gray-400">Upload a video file above to see the total count of mature dragon fruits.</p>
            )}
            {videoUploading && (
              <p className="text-sm text-gray-500 dark:text-gray-400">Analyzing video… please wait.</p>
            )}
          </div>
        </div>
      </motion.div>

      {/* Dataset toggle */}
      <motion.div variants={item} className="flex gap-2 p-1 bg-gray-100 dark:bg-gray-700 rounded-xl w-fit">
        <button
          type="button"
          onClick={() => setDatasetKey('estimation')}
          className={`min-h-[44px] px-5 rounded-lg text-sm font-medium transition-colors touch-manipulation ${datasetKey === 'estimation' ? 'bg-white dark:bg-gray-600 text-pitaya-primary dark:text-pitaya-light shadow-card' : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'}`}
        >
          Daily Total
        </button>
        <button
          type="button"
          onClick={() => setDatasetKey('block')}
          className={`min-h-[44px] px-5 rounded-lg text-sm font-medium transition-colors touch-manipulation ${datasetKey === 'block' ? 'bg-white dark:bg-gray-600 text-pitaya-primary dark:text-pitaya-light shadow-card' : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'}`}
        >
          By block
        </button>
      </motion.div>

      {/* Yield chart: line (estimation) or bar (block) with animated transition */}
      <motion.div variants={item} className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-gray-100">
            {datasetKey === 'estimation' ? 'Daily Yield Total (Fruits)' : 'Yield by Block (Fruits)'}
          </h2>
          {chartRefreshing && (
            <span className="text-xs text-pitaya-primary animate-pulse">⟳ Updating…</span>
          )}
          <button
            type="button"
            onClick={() => loadChartData(true)}
            disabled={chartRefreshing}
            className="text-xs text-gray-500 dark:text-gray-400 hover:text-pitaya-primary disabled:opacity-40 transition-colors ml-2"
          >
            Refresh
          </button>
        </div>
        <div className="h-[280px]">
          <AnimatePresence mode="wait">
            {datasetKey === 'estimation' ? (
              <motion.div
                key="line"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="h-full w-full"
              >
                {yieldEstimation.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm">
                    No yield data yet. Upload or capture an image/video above to record detections.
                  </div>
                ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={yieldEstimation} margin={{ top: 5, right: 20, left: 0, bottom: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                    <XAxis
                      dataKey="period"
                      tick={{ fontSize: 11 }}
                      stroke="#6b7280"
                      angle={-35}
                      textAnchor="end"
                      height={55}
                      tickFormatter={(v) => {
                        if (typeof v !== 'string') return v
                        try { return new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) } catch { return v }
                      }}
                    />
                    <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" unit=" fruits" />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb' }}
                      formatter={(v) => [`${v} fruits`, 'Total Detected']}
                      labelFormatter={(v) => {
                        try { return new Date(v).toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' }) } catch { return v }
                      }}
                    />
                    <Legend />
                    <Bar dataKey="yieldKg" name="Fruits Detected" fill={CHART_COLORS.bar} radius={[6, 6, 0, 0]} maxBarSize={60} />
                  </BarChart>
                </ResponsiveContainer>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="bar"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="h-full w-full"
              >
                {yieldByBlock.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm">
                    No block data yet. Save detections with different Block / Location names to compare here.
                  </div>
                ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={yieldByBlock} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="block" tick={{ fontSize: 12 }} stroke="#6b7280" />
                    <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" />
                    <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb' }} formatter={(v) => [`${v} fruits`, 'Total Detected']} />
                    <Legend />
                    <Bar dataKey="yieldKg" name="Fruits Detected" fill={CHART_COLORS.bar} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      {/* Historical yield comparison table */}
      <motion.div variants={item} className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-gray-100">Historical Yield Comparison</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Season-over-season yield (kg)</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-700 border-b border-gray-100 dark:border-gray-700">
                <th className="px-5 py-3 text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Season</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wider text-right">Fruits Detected</th>
              </tr>
            </thead>
            <tbody>
              {historicalYield.map((row, i) => (
                <motion.tr
                  key={row.season}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50/80 dark:hover:bg-gray-700/60 transition-colors"
                >
                  <td className="px-5 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{row.season}</td>
                  <td className="px-5 py-3 text-sm text-right font-semibold text-pitaya-primary">{row.yieldKg.toLocaleString()} fruits</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </motion.div>
  )
}
