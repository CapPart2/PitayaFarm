// API client for PITAYA backend (Django).
// Vite proxy: /api -> http://127.0.0.1:8000 (so /api/predict/ -> Django /predict/)

import { getPitayaUserScopeHeaders } from './userScope';

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
const DASHBOARD_API_BASE = (import.meta.env.VITE_DASHBOARD_API_BASE || '/api/dashboard').replace(/\/$/, '');

// Cache for CSRF token
let csrfToken = null;
let csrfTokenPromise = null;

// Helper function to handle API responses
async function handleResponse(response) {
  const contentType = response.headers.get('content-type');
  const isJson = contentType && contentType.includes('application/json');
  
  if (!response.ok) {
    let errorData;
    try {
      errorData = isJson ? await response.json() : await response.text();
    } catch (e) {
      errorData = 'Unknown error';
    }
    
    const error = new Error(`API Error: ${response.status} ${response.statusText}`);
    error.status = response.status;
    error.data = errorData;
    
    console.error('API Error:', {
      url: response.url,
      status: response.status,
      statusText: response.statusText,
      error: errorData
    });
    
    throw error;
  }
  
  return isJson ? response.json() : {};
}

// Helper function to get CSRF token
async function getCsrfToken() {
  // Return cached token if available
  if (csrfToken) return csrfToken;
  
  // If a request for token is already in progress, return that promise
  if (csrfTokenPromise) return csrfTokenPromise;
  
  try {
    csrfTokenPromise = (async () => {
      // Use the proxy for CSRF token
      const response = await fetch('/api/csrf/', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        },
      });
      
      if (!response.ok) {
        console.warn('CSRF token fetch failed with status:', response.status);
        return null;
      }
      
      const data = await response.json();
      csrfToken = data.csrfToken || null;
      return csrfToken;
    })();
    
    return await csrfTokenPromise;
  } catch (error) {
    console.warn('Error getting CSRF token:', error);
    csrfTokenPromise = null;
    return null;
  }
}

// Fetch with authentication and error handling
async function fetchWithAuth(url, options = {}) {
  // Don't try to get CSRF token for external URLs or if explicitly disabled
  const isExternalUrl = url.startsWith('http');
  const skipCsrf = options.skipCsrf || isExternalUrl;
  
  // Get CSRF token if needed
  const token = skipCsrf ? null : await getCsrfToken();
  
  // Prepare headers
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { 'X-CSRFToken': token }),
    ...getPitayaUserScopeHeaders(),
    ...(options.headers || {}),
  };
  
  // Remove Content-Type for FormData
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  // Make the request
  const finalUrl = url.startsWith('http') ? url : (url.startsWith(API_BASE) ? url : `${API_BASE}${url}`);
  const response = await fetch(finalUrl, {
    ...options,
    headers,
    credentials: 'same-origin',
  });

  return handleResponse(response);
}

// Library API
const libraryApi = {
  // Get all diseases with optional search and filter
  getDiseases: async (search = '', plantPart = '') => {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (plantPart) params.append('plant_part', plantPart);
    
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return fetchWithAuth(`${API_BASE}/library/${queryString}`);
  },

  // Get disease details by name
  getDiseaseByName: async (diseaseName) => {
    return fetchWithAuth(`${API_BASE}/library/${encodeURIComponent(diseaseName)}`);
  },
};

// Alerts API
const alertsApi = {
  // Get recent alerts
  getRecentAlerts: async (limit = 10) => {
    // Calls Dashboard API (port 5001) via Vite proxy /api/dashboard
    const response = await fetchWithAuth(`${API_BASE}/dashboard/alerts`); 
    // Dashboard API returns { success: true, data: [...] }
    const alerts = response.data || [];
    return alerts.slice(0, limit);
  },

  // Get alert by ID (Not implemented in Dashboard API yet, placeholder)
  getAlertById: async (id) => {
    // const response = await fetchWithAuth(`${API_BASE}/alerts/${id}/`);
    // return response;
    console.warn('getAlertById not implemented');
    return null;
  },
};

// Reports API
const reportsApi = {
  // Get report data with optional date range
  getReportData: async (startDate = null, endDate = null) => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const queryString = params.toString() ? `?${params.toString()}` : '';
    const response = await fetchWithAuth(`${DASHBOARD_API_BASE}/reports${queryString}`);
    const rows = response?.data || [];

    const normalized = rows.map((r) => {
      const diseaseName = r.DiseaseType || r.disease_type || 'Unknown';
      const confidence = Number(r.Confidence ?? r.confidence ?? 0) || 0;
      const detectedDate = r.DateTime || r.detected_date || r.created_at || null;
      return {
        id: r.DetectionID || r.id,
        disease_name: diseaseName,
        confidence,
        detected_date: detectedDate,
      };
    });

    const diseaseCounter = new Map();
    const trendCounter = new Map();
    let confidenceTotal = 0;

    normalized.forEach((row) => {
      diseaseCounter.set(row.disease_name, (diseaseCounter.get(row.disease_name) || 0) + 1);
      confidenceTotal += row.confidence;

      const day = (row.detected_date || '').slice(0, 10);
      if (day) {
        trendCounter.set(day, (trendCounter.get(day) || 0) + 1);
      }
    });

    const disease_distribution = Array.from(diseaseCounter.entries())
      .map(([disease_name, count]) => ({ disease_name, count }))
      .sort((a, b) => b.count - a.count);

    const detection_trends = Array.from(trendCounter.entries())
      .map(([date, count]) => ({ date, count }))
      .sort((a, b) => a.date.localeCompare(b.date));

    return {
      total_scans: normalized.length,
      diseases_detected: normalized.length,
      average_confidence: normalized.length ? confidenceTotal / normalized.length : 0,
      disease_distribution,
      recent_detections: normalized
        .slice()
        .sort((a, b) => String(b.detected_date || '').localeCompare(String(a.detected_date || '')))
        .slice(0, 10),
      detection_trends,
    };
  },

  // Get disease statistics
  getDiseaseStats: async () => {
    const response = await fetchWithAuth(`${DASHBOARD_API_BASE}/disease-stats`);
    return response.data || {};
  },
};

// Prediction API
const predictionApi = {
  // Run disease detection
  predictDisease: async (file) => {
    const formData = new FormData();
    formData.append('file', file, file?.name || 'upload.jpg');

    // Direct fetch without credentials for Flask API
    const response = await fetch(`${API_BASE}/predict`, {
      method: 'POST',
      body: formData,
      headers: getPitayaUserScopeHeaders(),
      // Don't set Content-Type header for FormData - browser sets it automatically with boundary
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  },

  // Map prediction response to frontend format
  mapPredictResponse: (data) => {
    // Handle enhanced API response
    if (data.detection) {
      if (data.detection.disease_name) {
        return {
          diseaseName: data.detection.disease_name,
          confidence: parseFloat(data.detection.confidence_level) || 0,
          severity: data.detection.severity || 'medium',
          affectedPart: 'Leaf/Stem',
          symptoms: data.detection.symptoms?.join('. ') || '',
          recommendation: data.detection.treatment?.slice(0, 2).join('. ') || 'Consult agricultural specialist',
          treatment: data.detection.treatment?.join('. ') || '',
          confidenceMessage: `${data.detection.confidence_level}% confidence`,
          topPredictions: data.predictions || [],
          alert: data.alert,
          reportId: data.report_id
        };
      } else {
        return {
          diseaseName: 'No Disease Detected',
          confidence: parseFloat(data.detection.confidence_level) || 0,
          severity: 'low',
          affectedPart: 'None',
          symptoms: '',
          recommendation: data.detection.message || 'No visible disease detected.',
          treatment: '',
          confidenceMessage: `${data.detection.confidence_level}% confidence`,
          topPredictions: [],
          alert: null,
          reportId: null
        };
      }
    }

    const info = data.disease_info || {};

    return {
      diseaseName: data.predicted_class_name || 'Unknown',
      confidence: parseFloat(data.predicted_class_accuracy) || 0,
      severity: data.confidence_level || 'medium',
      affectedPart: info.affected_part || 'Unknown',
      symptoms: info.symptoms || '',
      recommendation: info.prevention || info.treatment_recommendations || '',
      treatment: info.treatment_recommendations || '',
      confidenceMessage: data.confidence_message,
      topPredictions: data.top_predictions || [],
    };
  },
};

// Export all API functions
export { alertsApi, fetchWithAuth, getCsrfToken, libraryApi, predictionApi, reportsApi };

