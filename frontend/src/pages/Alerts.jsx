import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { alertsApi } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import SeverityBadge from '../components/SeverityBadge';

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        setLoading(true);
        const data = await alertsApi.getRecentAlerts(20);
        
        // Group alerts by session_id to combine multi-disease detections
        const groupedBySession = {};
        (Array.isArray(data) ? data : []).forEach(alert => {
          const sessionId = alert.session_id || alert.AlertID?.toString() || alert.id?.toString();
          if (!groupedBySession[sessionId]) {
            groupedBySession[sessionId] = [];
          }
          // Normalize image_path field name
          const record = {
            ...alert,
            image_path: alert.image_path || alert.ImagePath
          };
          groupedBySession[sessionId].push(record);
        });

        const groupedAlerts = Object.keys(groupedBySession).map(sessionId => {
          const records = groupedBySession[sessionId];
          const primaryRecord = records[0];
          
          // If multiple records in session, combine them
          if (records.length > 1) {
            const diseaseNames = records.map(r => r.disease_name || r.DiseaseType).join(', ');
            const sumConfidence = records.reduce((sum, r) => sum + (r.confidence || r.Confidence || 0), 0);
            const maxSeverity = records.some(r => (r.severity || r.Severity) === 'high') ? 'high' : 
                               records.some(r => (r.severity || r.Severity) === 'medium') ? 'medium' : 'low';
            
            return {
              ...primaryRecord,
              AlertID: sessionId,
              id: sessionId,
              disease_name: diseaseNames,
              severity: maxSeverity,
              confidence: sumConfidence,
              isMultiDisease: true,
              diseases: records.map(r => ({
                name: r.disease_name || r.DiseaseType,
                severity: r.severity || r.Severity,
                confidence: r.confidence || r.Confidence
              }))
            };
          }
          
          return { ...primaryRecord, isMultiDisease: false, id: primaryRecord.AlertID || primaryRecord.id };
        });
        
        setAlerts(groupedAlerts);
        setError(null);
      } catch (err) {
        console.error('Error fetching alerts:', err);
        setError('Failed to load alerts. Please try again later.');
        setAlerts([]);
      } finally {
        setLoading(false);
      }
    };

    fetchAlerts();
  }, []);

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="container mx-auto px-4 py-8 text-gray-900 dark:text-gray-100">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Disease Alerts</h1>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {alerts.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 dark:text-gray-400 text-lg">No alerts found.</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 shadow overflow-hidden sm:rounded-md border border-gray-200 dark:border-gray-700">
          <ul className="divide-y divide-gray-200 dark:divide-gray-700">
            {alerts.map((alert) => (
              <li key={alert.AlertID || alert.id}>
                <Link to={`/library/${alert.disease_name}`} className="block hover:bg-gray-50 dark:hover:bg-gray-700">
                  <div className="px-4 py-4 sm:px-6">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-4 flex-1">
                        {alert.image_path && alert.image_path !== 'detection_image.jpg' && (
                          <img 
                            src={`http://localhost:5001/${alert.image_path.replace(/\\/g, '/')}`} 
                            alt="Detection" 
                            className="w-16 h-16 object-cover rounded cursor-pointer hover:opacity-80 flex-shrink-0"
                            onClick={(e) => {
                              e.preventDefault()
                              window.open(`http://localhost:5001/${alert.image_path.replace(/\\/g, '/')}`, '_blank')
                            }}
                          />
                        )}
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-medium text-indigo-600 truncate">
                              {alert.disease_name}
                            </p>
                            <div className="ml-2 flex-shrink-0 flex">
                              <SeverityBadge severity={alert.severity} />
                            </div>
                          </div>
                          <div className="mt-2 sm:flex sm:justify-between">
                            <div className="sm:flex">
                              <p className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                                <span className="font-medium">Confidence:</span>
                                <span className="ml-1 font-semibold">
                                  {Math.round(alert.confidence * 10) / 10}%
                                </span>
                              </p>
                              <p className="mt-2 flex items-center text-sm text-gray-500 dark:text-gray-400 sm:mt-0 sm:ml-6">
                                <span className="font-medium">Detected on:</span>
                                <span className="ml-1">
                                  {new Date(alert.detected_date).toLocaleDateString()}
                                </span>
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
