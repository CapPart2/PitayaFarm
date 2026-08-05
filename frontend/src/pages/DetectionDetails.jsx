import { useEffect, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import LoadingSpinner from '../components/LoadingSpinner'

export default function DetectionDetails() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchDetection = async () => {
      try {
        const res = await fetch(`/api/dashboard/detections/${id}`)
        if (!res.ok) {
          console.error(`Detection fetch failed: ${res.status}`)
          setData(null)
          return
        }
        const root = await res.json()
        console.log('Detection data received:', root)
        setData(root.data || null)
      } catch (error) {
        console.error('Error fetching detection:', error)
        setData(null)
      } finally {
        setLoading(false)
      }
    }
    fetchDetection()
  }, [id])

  useEffect(() => {
    const alertId = searchParams.get('alertId')
    if (alertId) {
      fetch(`/api/dashboard/alerts/${alertId}/read`, { method: 'POST' }).catch(() => {})
      window.dispatchEvent(new Event('pitaya:refresh'))
    }
  }, [searchParams])

  if (loading) return <LoadingSpinner className="min-h-[60vh]" />
  
  if (!data) {
    return (
      <div className="max-w-3xl mx-auto bg-white dark:bg-gray-800 rounded-2xl p-6 border border-gray-100 dark:border-gray-700 shadow-card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="font-display font-bold text-2xl text-gray-900 dark:text-gray-100">Detection Details</h1>
            <p className="text-gray-600 dark:text-gray-300">Detection ID #{id}</p>
          </div>
          <button
            onClick={() => navigate(-1)}
            className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            title="Go back"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="text-center py-8">
          <p className="text-gray-500 dark:text-gray-400">No detection details available for ID #{id}</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">Please check the detection ID and try again.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto bg-white dark:bg-gray-800 rounded-2xl p-6 border border-gray-100 dark:border-gray-700 shadow-card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="font-display font-bold text-2xl text-gray-900 dark:text-gray-100">Detection Details</h1>
          <p className="text-gray-600 dark:text-gray-300">Detection ID #{data.id}</p>
        </div>
        <button
          onClick={() => navigate(-1)}
          className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          title="Go back"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Disease</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{data.disease_type || data.disease_name || 'Unknown'}</p>
        </div>
        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Severity</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{data.severity || 'Unknown'}</p>
        </div>
        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Confidence</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{(data.confidence ?? 0).toFixed(1)}%</p>
        </div>
        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Date & Time</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{new Date(data.created_at || data.detection_time).toLocaleString()}</p>
        </div>
        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Location</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{data.location || 'User Upload'}</p>
        </div>
        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Image</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{data.image_path ? 'Available' : 'Not Available'}</p>
        </div>
      </div>
      
      {/* Alert Information */}
      {data.alert && (
        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-300 mb-2">Alert Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-blue-700 dark:text-blue-400">Alert ID</p>
              <p className="text-lg font-semibold text-blue-900 dark:text-blue-300">#{data.alert.AlertID}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-blue-700 dark:text-blue-400">Status</p>
              <p className="text-lg font-semibold text-blue-900 dark:text-blue-300">{data.alert.Status}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-blue-700 dark:text-blue-400">Created</p>
              <p className="text-lg font-semibold text-blue-900 dark:text-blue-300">{new Date(data.alert.CreatedAt).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-blue-700 dark:text-blue-400">Read At</p>
              <p className="text-lg font-semibold text-blue-900 dark:text-blue-300">{data.alert.ReadAt ? new Date(data.alert.ReadAt).toLocaleString() : 'Not read yet'}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
