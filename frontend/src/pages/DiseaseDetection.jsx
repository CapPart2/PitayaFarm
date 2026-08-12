import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle, Info, XCircle } from 'lucide-react'
import { useRef, useState } from 'react'
import { getPitayaUserScopeHeaders } from '../api/userScope'
import { predictionApi } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import SeverityBadge from '../components/SeverityBadge'
import { attachCameraStream, captureCameraPhoto, openCaptureCamera } from '../utils/cameraCapture'

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
}
const item = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }

export default function DiseaseDetection() {
  const [mode, setMode] = useState('upload') // 'upload' | 'camera'
  const [previewUrl, setPreviewUrl] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [isDetectionConfirmed, setIsDetectionConfirmed] = useState(false)
  const [confirmationMessage, setConfirmationMessage] = useState('')
  const [expandedDiseaseIndex, setExpandedDiseaseIndex] = useState(null)
  const fileInputRef = useRef(null)
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  const [selectedFile, setSelectedFile] = useState(null)
  const [sessionId, setSessionId] = useState(null)

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file || !file.type.startsWith('image/')) return
    setResult(null)
    setIsDetectionConfirmed(false)
    setConfirmationMessage('')
    setExpandedDiseaseIndex(null)
    setSelectedFile(file)
    setPreviewUrl(URL.createObjectURL(file))
    setSessionId(Date.now().toString()) // Generate session ID for grouping
    runDetection(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (!file?.type.startsWith('image/')) return
    setResult(null)
    setIsDetectionConfirmed(false)
    setConfirmationMessage('')
    setExpandedDiseaseIndex(null)
    setSelectedFile(file)
    setPreviewUrl(URL.createObjectURL(file))
    setSessionId(Date.now().toString()) // Generate session ID for grouping
    runDetection(file)
  }

  const handleDragOver = (e) => e.preventDefault()

  const runDetection = (file) => {
    if (!file) return
    handlePredict(file)
  }

  const handlePredict = async (file) => {
    try {
      setLoading(true)
      setError(null)
      
      // Use the prediction API
      const response = await predictionApi.predictDisease(file)

      // Predict endpoint already persists detections; broadcast refresh for Reports/Dashboard modules.
      window.dispatchEvent(new Event('pitaya:refresh'))
      
      // Handle enhanced response from new API
      if (response.detection) {
        if (response.detection.disease_name) {
          // Check if multiple diseases were detected
          if (response.detection.multiple_diseases && response.detection.multiple_diseases.length > 1) {
            // Multiple diseases detected
            setResult({
              diseaseName: response.detection.disease_name,
              confidence: response.detection.confidence_level,
              severity: response.detection.severity,
              multipleDiseases: response.detection.multiple_diseases,
              affectedPart: 'Leaf/Stem',
              recommendation: `Multiple diseases detected (${response.detection.multiple_diseases.length}). Click on each disease for details.`,
              alert: response.alert,
              reportId: response.report_id
            })
          } else {
            // Single disease detected with detailed information
            setResult({
              diseaseName: response.detection.disease_name,
              confidence: response.detection.confidence_level,
              severity: response.detection.severity,
              symptoms: response.detection.symptoms,
              causes: response.detection.causes,
              treatment: response.detection.treatment,
              affectedPart: 'Leaf/Stem',
              recommendation: response.detection.treatment?.slice(0, 2).join(' ') || 'Consult agricultural specialist',
              alert: response.alert,
              reportId: response.report_id
            })
          }
          
          console.log('Detection result ready')
        } else {
          // No disease detected
          setResult({
            diseaseName: 'No disease detection found',
            confidence: response.detection.confidence_level,
            severity: 'none',
            symptoms: [],
            causes: [],
            treatment: [],
            affectedPart: 'None',
            recommendation: response.detection.message || 'No disease detection found. Please upload a clear dragon fruit stem image.',
            noDisease: true,
            alert: null,
            reportId: null
          })
          
          console.log('Healthy plant detected')
        }
      } else {
        // Fallback to old response format
        const mappedResult = predictionApi.mapPredictResponse(response)
        setResult(mappedResult)
        
        console.log('Detection result ready (fallback)')
      }
    } catch (err) {
      console.error('Prediction error:', err)
      const apiMessage = typeof err?.data === 'string'
        ? err.data
        : err?.data?.error || err?.data?.message
      setError(apiMessage || err.message || 'Failed to process image. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleAddDetection = async () => {
    if (!result || result.noDisease || isDetectionConfirmed) return
    
    try {
      setLoading(true)
      
      // Check if multiple diseases were detected
      if (result.multipleDiseases && result.multipleDiseases.length > 1) {
        // Sort diseases by confidence (highest first)
        const sortedDiseases = [...result.multipleDiseases].sort((a, b) => 
          parseFloat(b.confidence_level) - parseFloat(a.confidence_level)
        )
        
        // Get the highest confidence
        const highestConfidence = parseFloat(sortedDiseases[0].confidence_level)
        
        let diseasesToSave = []
        
        // Apply confidence-based saving rules
        if (highestConfidence >= 85) {
          // Save only the highest confidence disease
          diseasesToSave = [sortedDiseases[0]]
          console.log(`🎯 High confidence ({highestConfidence.toFixed(1)}%): Saving only top disease`)
        } else {
          // Save top 2 diseases
          diseasesToSave = sortedDiseases.slice(0, 2)
          console.log(`📊 Low confidence ({highestConfidence.toFixed(1)}%): Saving top 2 diseases`)
        }
        
        // Save the selected diseases with image and session ID
        const savePromises = diseasesToSave.map(disease => {
          const formData = new FormData()
          formData.append('disease_type', disease.disease_name)
          formData.append('severity', disease.severity)
          formData.append('confidence', parseFloat(disease.confidence_level) || 0)
          formData.append('location', 'User Upload')
          formData.append('session_id', sessionId) // Group related detections
          if (selectedFile) {
            formData.append('image', selectedFile)
          }
          
          return fetch('/api/dashboard/disease-detection', {
            method: 'POST',
            headers: getPitayaUserScopeHeaders(),
            body: formData
          })
        })
        
        const responses = await Promise.all(savePromises)
        const allSuccessful = responses.every(response => response.ok)
        
        if (allSuccessful) {
          setIsDetectionConfirmed(true)
          setConfirmationMessage(`✅ ${diseasesToSave.length} disease(s) added successfully!`)
          
          // Now trigger real-time updates across all modules
          window.dispatchEvent(new Event('pitaya:refresh'))
          console.log('🔄 Real-time update triggered after Add Detection button click')
          
          // Clear confirmation message after 3 seconds
          setTimeout(() => {
            setConfirmationMessage('')
          }, 3000)
        } else {
          throw new Error('Failed to save some diseases')
        }
      } else {
        // Single disease - send with image and session ID
        const formData = new FormData()
        formData.append('disease_type', result.diseaseName)
        formData.append('severity', result.severity)
        formData.append('confidence', parseFloat(result.confidence) || 0)
        formData.append('location', 'User Upload')
        formData.append('session_id', sessionId) // Group related detections
        if (selectedFile) {
          formData.append('image', selectedFile)
        }
        
        const response = await fetch('/api/dashboard/disease-detection', {
          method: 'POST',
          headers: getPitayaUserScopeHeaders(),
          body: formData
        })
        
        if (response.ok) {
          const data = await response.json()
          setIsDetectionConfirmed(true)
          setConfirmationMessage('✅ Detection added successfully!')
          
          // Now trigger real-time updates across all modules
          window.dispatchEvent(new Event('pitaya:refresh'))
          console.log('🔄 Real-time update triggered after Add Detection button click')
          
          // Clear confirmation message after 3 seconds
          setTimeout(() => {
            setConfirmationMessage('')
          }, 3000)
        } else {
          throw new Error('Failed to save detection')
        }
      }
    } catch (err) {
      console.error('Error adding detection:', err)
      setConfirmationMessage('❌ Failed to add detection. Please try again.')
      setTimeout(() => {
        setConfirmationMessage('')
      }, 3000)
    } finally {
      setLoading(false)
    }
  }

  const handleCapture = async () => {
    try {
      const file = await captureCameraPhoto(videoRef.current, 'disease-capture.jpg')
      setSelectedFile(file)
      setPreviewUrl(URL.createObjectURL(file))
      setResult(null)
      setSessionId(Date.now().toString()) // Generate session ID for grouping
      runDetection(file)
    } catch (captureError) {
      setError(captureError.message)
    }
  }

  const startCamera = async () => {
    try {
      stopCamera()
      const stream = await openCaptureCamera()
      streamRef.current = stream
      await attachCameraStream(videoRef.current, stream)
      setError(null)
    } catch (cameraError) {
      console.error('Camera access failed:', cameraError)
      setError(cameraError.message)
    }
  }

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }

  const reset = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
    setSelectedFile(null)
    setResult(null)
    setExpandedDiseaseIndex(null)
    setIsDetectionConfirmed(false)
    setConfirmationMessage('')
    stopCamera()
  }

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="max-w-6xl mx-auto h-full flex flex-col"
    >
      <div>
        <h1 className="font-display font-bold text-2xl text-gray-900 dark:text-white">Disease Detection</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-1 text-base">Upload or capture one clear dragon fruit stem image to identify disease.</p>
      </div>

      {/* Tabs: Upload | Camera */}
      <motion.div variants={item} className="flex gap-2 p-1 bg-gray-100 dark:bg-gray-700 rounded-xl w-fit">
        <button
          type="button"
          onClick={() => { setMode('upload'); reset() }}
          className={`min-h-[44px] px-5 rounded-lg text-sm font-medium transition-colors touch-manipulation ${mode === 'upload' ? 'bg-white dark:bg-gray-800 text-pitaya-primary dark:text-green-400 shadow-card' : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'}`}
        >
          Upload
        </button>
        <button
          type="button"
          onClick={() => { setMode('camera'); setPreviewUrl(null); setResult(null) }}
          className={`min-h-[44px] px-5 rounded-lg text-sm font-medium transition-colors touch-manipulation ${mode === 'camera' ? 'bg-white dark:bg-gray-800 text-pitaya-primary dark:text-green-400 shadow-card' : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'}`}
        >
          Camera
        </button>
      </motion.div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-0">
        {/* Upload / Capture area */}
        <motion.div variants={item} className="space-y-4 flex flex-col">
          {mode === 'upload' && (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 min-h-[300px] rounded-2xl border-2 border-dashed border-pitaya-leaf/40 bg-pitaya-pale/50 dark:bg-gray-800/50 dark:border-gray-600 flex flex-col items-center justify-center p-8 cursor-pointer transition-colors hover:border-pitaya-leaf hover:bg-pitaya-pale/70 dark:hover:bg-gray-800/70 active:scale-[0.99] touch-manipulation"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="sr-only"
                onChange={handleFileChange}
                aria-label="Choose image file"
              />
              <span className="text-4xl mb-3" aria-hidden>🖼️</span>
              <p className="font-medium text-gray-800 dark:text-gray-200 text-center">Upload one centered dragon fruit stem</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 text-center">Keep leaves, soil, and other plants out of the frame. PNG or JPG, up to 10MB.</p>
            </div>
          )}
          {mode === 'camera' && (
            <div className="flex-1 flex flex-col space-y-3">
              <div className="flex-1 relative rounded-2xl overflow-hidden bg-gray-900 min-h-[300px] flex items-center justify-center">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-contain"
                />
                <p className="absolute text-white/80 text-sm">Camera preview</p>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={startCamera}
                  className="flex-1 min-h-[44px] px-4 rounded-xl bg-pitaya-primary text-white font-medium touch-manipulation active:scale-[0.98]"
                >
                  Start camera
                </button>
                <button
                  type="button"
                  onClick={handleCapture}
                  className="flex-1 min-h-[44px] px-4 rounded-xl bg-white dark:bg-gray-800 border-2 border-pitaya-primary text-pitaya-primary dark:text-green-400 font-medium touch-manipulation active:scale-[0.98]"
                >
                  Capture
                </button>
                <button
                  type="button"
                  onClick={stopCamera}
                  className="min-h-[44px] px-4 rounded-xl border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 font-medium touch-manipulation"
                >
                  Stop
                </button>
              </div>
            </div>
          )}

          {/* Animated image preview */}
          <AnimatePresence>
            {previewUrl && (
              <motion.div
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.25 }}
                className="flex-1 rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-card flex flex-col"
              >
                <p className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-700">Preview</p>
                <div className="flex-1 flex items-center justify-center p-4">
                  <img src={previewUrl} alt="Preview" className="max-w-full max-h-full object-contain" />
                </div>
                <div className="p-3 flex gap-2">
                  <button
                    type="button"
                    onClick={reset}
                    className="min-h-[44px] px-4 rounded-xl border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-medium text-sm touch-manipulation"
                  >
                    Clear
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Result card */}
        <motion.div variants={item} className="lg:order-none flex flex-col">
          <div className="flex-1 rounded-2xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-card overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-600">
              <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-white">Detection Result</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Disease name, confidence, and severity</p>
            </div>
            <div className="flex-1 p-5 overflow-auto">
              {loading && <LoadingSpinner />}
              {error && (
                <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                  <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
                  <div>
                    <p className="text-sm font-medium text-red-900 dark:text-red-300">Error</p>
                    <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
                  </div>
                </div>
              )}
              {!loading && !result && !error && (
                <p className="text-gray-500 dark:text-gray-400 text-sm py-8 text-center">Upload or capture an image to see results.</p>
              )}
              <AnimatePresence>
                {!loading && result && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="space-y-4"
                  >
                    {/* Alert Section */}
                    {result.alert && (
                      <div className={`p-4 rounded-lg border ${
                        result.alert.alert_level === 'critical' ? 'bg-red-50 border-red-200' :
                        result.alert.alert_level === 'warning' ? 'bg-yellow-50 border-yellow-200' :
                        'bg-blue-50 border-blue-200'
                      }`}>
                        <div className="flex items-start gap-3">
                          <AlertTriangle className={`w-5 h-5 mt-0.5 ${
                            result.alert.alert_level === 'critical' ? 'text-red-600' :
                            result.alert.alert_level === 'warning' ? 'text-yellow-600' :
                            'text-blue-600'
                          }`} />
                          <div className="flex-1">
                            <p className={`font-medium text-sm ${
                              result.alert.alert_level === 'critical' ? 'text-red-900' :
                              result.alert.alert_level === 'warning' ? 'text-yellow-900' :
                              'text-blue-900'
                            }`}>
                              {result.alert.message}
                            </p>
                            {result.alert.is_recurring && (
                              <p className="text-xs text-orange-700 mt-1">⚠️ Recurring disease detected</p>
                            )}
                            <div className="mt-2">
                              <p className="text-xs font-medium text-gray-700 dark:text-gray-200 mb-1">Recommended Actions:</p>
                              <ul className="text-xs space-y-1">
                                {result.alert.recommended_action?.map((action, index) => (
                                  <li key={index} className="flex items-start gap-1">
                                    <span className="text-green-600 mt-0.5">•</span>
                                    <span className="text-gray-600 dark:text-gray-200">{action}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Disease Information */}
                    {!result.noDisease ? (
                      <>
                        {/* Multiple Diseases Display */}
                        {result.multipleDiseases && result.multipleDiseases.length > 1 ? (
                          <div className="space-y-3">
                            <div className="flex items-start gap-3">
                              <span className="text-2xl" aria-hidden>🌿</span>
                              <div className="flex-1 min-w-0">
                                <p className="font-display font-bold text-xl text-gray-900 dark:text-gray-100">Multiple Diseases Detected</p>
                                <p className="text-sm text-gray-500 dark:text-gray-300 mt-0.5">{result.affectedPart} • {result.multipleDiseases.length} diseases found</p>
                              </div>
                            </div>
                            
                            {/* List of detected diseases with expandable details */}
                            {result.multipleDiseases.map((disease, index) => (
                              <div key={index} className="border border-gray-200 dark:border-gray-600 rounded-xl overflow-hidden">
                                <button
                                  type="button"
                                  onClick={() => setExpandedDiseaseIndex(expandedDiseaseIndex === index ? null : index)}
                                  className="w-full p-4 flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                                >
                                  <div className="flex items-center gap-3">
                                    <span className="text-lg" aria-hidden>🍃</span>
                                    <div className="text-left">
                                      <p className="font-semibold text-gray-900 dark:text-gray-100">{disease.disease_name}</p>
                                      <p className="text-xs text-gray-500 dark:text-gray-400">
                                        {typeof disease.confidence_level === 'number' ? disease.confidence_level.toFixed(1) : parseFloat(disease.confidence_level || 0).toFixed(1)}% confidence
                                      </p>
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <SeverityBadge severity={disease.severity} />
                                    <span className="text-gray-400">
                                      {expandedDiseaseIndex === index ? '▼' : '▶'}
                                    </span>
                                  </div>
                                </button>
                                
                                {/* Expandable details */}
                                <AnimatePresence>
                                  {expandedDiseaseIndex === index && (
                                    <motion.div
                                      initial={{ height: 0, opacity: 0 }}
                                      animate={{ height: 'auto', opacity: 1 }}
                                      exit={{ height: 0, opacity: 0 }}
                                      transition={{ duration: 0.2 }}
                                      className="overflow-hidden"
                                    >
                                      <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-600 space-y-3">
                                        {/* Symptoms */}
                                        {disease.symptoms && disease.symptoms.length > 0 && (
                                          <div>
                                            <p className="text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wide mb-2">Symptoms</p>
                                            <ul className="space-y-1">
                                              {disease.symptoms.slice(0, 3).map((symptom, sIndex) => (
                                                <li key={sIndex} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-200">
                                                  <span className="text-red-500 mt-1">•</span>
                                                  <span>{symptom}</span>
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                        
                                        {/* Causes */}
                                        {disease.causes && disease.causes.length > 0 && (
                                          <div>
                                            <p className="text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wide mb-2">Causes</p>
                                            <ul className="space-y-1">
                                              {disease.causes.slice(0, 2).map((cause, cIndex) => (
                                                <li key={cIndex} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-200">
                                                  <span className="text-orange-500 mt-1">•</span>
                                                  <span>{cause}</span>
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                        
                                        {/* Treatment */}
                                        {disease.treatment && disease.treatment.length > 0 && (
                                          <div>
                                            <p className="text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wide mb-2">Recommended Treatment</p>
                                            <ul className="space-y-1">
                                              {disease.treatment.slice(0, 3).map((treatment, tIndex) => (
                                                <li key={tIndex} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-200">
                                                  <span className="text-green-500 mt-1">•</span>
                                                  <span>{treatment}</span>
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                      </div>
                                    </motion.div>
                                  )}
                                </AnimatePresence>
                              </div>
                            ))}
                          </div>
                        ) : (
                          /* Single Disease Display (original) */
                          <>
                            <div className="flex items-start gap-3">
                              <span className="text-2xl" aria-hidden>🌿</span>
                              <div className="flex-1 min-w-0">
                                <p className="font-display font-bold text-xl text-gray-900 dark:text-gray-100">{result.diseaseName}</p>
                                <p className="text-sm text-gray-500 dark:text-gray-300 mt-0.5">{result.affectedPart}</p>
                              </div>
                              <SeverityBadge severity={result.severity} />
                            </div>
                            <div className="flex items-center gap-3 p-3 rounded-xl bg-pitaya-pale/50 dark:bg-gray-700/40 border border-pitaya-leaf/20 dark:border-gray-600">
                              <span className="text-2xl font-bold text-pitaya-primary dark:text-green-400">
                                {typeof result.confidence === 'number' ? result.confidence.toFixed(1) : parseFloat(result.confidence || 0).toFixed(1)}%
                              </span>
                              <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Confidence</span>
                            </div>
                            
                            {/* Symptoms */}
                            {result.symptoms && result.symptoms.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wide mb-2">Symptoms</p>
                                <ul className="space-y-1">
                                  {result.symptoms.slice(0, 3).map((symptom, index) => (
                                    <li key={index} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-200">
                                      <span className="text-red-500 mt-1">•</span>
                                      <span>{symptom}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            
                            {/* Causes */}
                            {result.causes && result.causes.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wide mb-2">Causes</p>
                                <ul className="space-y-1">
                                  {result.causes.slice(0, 2).map((cause, index) => (
                                    <li key={index} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-200">
                                      <span className="text-orange-500 mt-1">•</span>
                                      <span>{cause}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            
                            {/* Treatment */}
                            {result.treatment && result.treatment.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wide mb-2">Recommended Treatment</p>
                                <ul className="space-y-1">
                                  {result.treatment.slice(0, 3).map((treatment, index) => (
                                    <li key={index} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-200">
                                      <span className="text-green-500 mt-1">•</span>
                                      <span>{treatment}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </>
                        )}
                        
                        {result.recommendation && (
                          <div>
                            <p className="text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase tracking-wide mb-1">Additional Recommendation</p>
                            <p className="text-sm text-gray-700 dark:text-gray-200 leading-relaxed">{result.recommendation}</p>
                          </div>
                        )}
                      </>
                    ) : (
                      // No disease detected case
                      <div className="text-center py-8">
                        <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
                        <p className="font-display font-bold text-xl text-gray-900 dark:text-gray-100 mb-2">{result.diseaseName}</p>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">{result.recommendation}</p>
                        <div className="flex items-center justify-center gap-2 text-sm text-gray-500 dark:text-gray-300">
                          <Info className="w-4 h-4" />
                          <span>Confidence: {typeof result.confidence === 'number' ? result.confidence.toFixed(1) : parseFloat(result.confidence || 0).toFixed(1)}%</span>
                        </div>
                      </div>
                    )}
                    
                    {/* Add Detection Button and Confirmation */}
                    {result && !result.noDisease && !isDetectionConfirmed && (
                      <div className="mt-6 space-y-3">
                        <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                          <p className="text-sm text-yellow-800 dark:text-yellow-200">
                            ⚠️ This detection result is a preview. Click "Add Detection" to save it to the system and update totals.
                          </p>
                        </div>
                        
                        <button
                          type="button"
                          onClick={handleAddDetection}
                          disabled={loading}
                          className="w-full min-h-[44px] px-6 rounded-xl bg-pitaya-primary text-white font-medium touch-manipulation active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                          {loading ? (
                            <>
                              <LoadingSpinner className="w-4 h-4" />
                              Adding Detection...
                            </>
                          ) : (
                            <>
                              <CheckCircle className="w-5 h-5" />
                              Add Detection
                            </>
                          )}
                        </button>
                      </div>
                    )}
                    
                    {/* Confirmation Message */}
                    {confirmationMessage && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={`mt-4 p-4 rounded-lg border ${
                          confirmationMessage.includes('✅') 
                            ? 'bg-green-50 border-green-200' 
                            : 'bg-red-50 border-red-200'
                        }`}
                      >
                        <p className={`text-sm font-medium ${
                          confirmationMessage.includes('✅') 
                            ? 'text-green-800' 
                            : 'text-red-800'
                        }`}>
                          {confirmationMessage}
                        </p>
                      </motion.div>
                    )}
                    
                    {/* Detection Confirmed Indicator */}
                    {isDetectionConfirmed && (
                      <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                        <div className="flex items-center gap-3">
                          <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
                          <div>
                            <p className="text-sm font-medium text-green-800 dark:text-green-200">
                              ✅ Detection confirmed and added to system
                            </p>
                            <p className="text-xs text-green-700 dark:text-green-300 mt-1">
                              Dashboard, Reports, and Alerts have been updated automatically
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      </div>
    </motion.div>
  )
}
