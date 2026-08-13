/**
 * Dashboard API – Database-driven charts implementation
 */

import { getPitayaUserScopeHeaders } from './userScope';

const configuredDashboardUrl = import.meta.env.VITE_DASHBOARD_API_URL?.replace(/\/$/, '');
const API_BASE = configuredDashboardUrl
  ? configuredDashboardUrl.endsWith('/api/dashboard')
    ? configuredDashboardUrl
    : `${configuredDashboardUrl}/api/dashboard`
  : '/api/dashboard';
const REQUEST_TIMEOUT_MS = 12_000;

// Helper function for API calls
async function apiCall(endpoint, options = {}) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const requestHeaders = {
      'Content-Type': 'application/json',
      ...getPitayaUserScopeHeaders(),
      ...(options.headers || {}),
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: requestHeaders,
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

// Fetch comprehensive dashboard summary
export async function fetchDashboardSummary() {
  try {
    const response = await apiCall('/summary');
    return response.data || response;
  } catch (error) {
    console.warn('Dashboard API unavailable, using fallback data:', error.message);
    return getFallbackData();
  }
}

// Fetch disease statistics
export async function fetchDiseaseStats() {
  try {
    const response = await apiCall('/disease-stats');
    return response.data || response;
  } catch (error) {
    console.warn('Disease stats API unavailable:', error.message);
    return { disease_distribution: [], severity_distribution: [], daily_detections: [] };
  }
}

// Fetch yield statistics
export async function fetchYieldStats() {
  try {
    const response = await apiCall('/yield-stats');
    return response.data || response;
  } catch (error) {
    console.warn('Yield stats API unavailable:', error.message);
    return { yield_trend: [], accuracy_info: { avg_accuracy: 0, total_predictions: 0 } };
  }
}

// Fetch alerts
export async function fetchAlerts(unreadOnly = false) {
  try {
    const response = await apiCall(`/alerts?unread_only=${unreadOnly}`);
    return response.data || response;
  } catch (error) {
    console.warn('Alerts API unavailable:', error.message);
    return [];
  }
}

// Mark alert as read
export async function markAlertRead(alertId) {
  try {
    const response = await apiCall(`/alerts/${alertId}/read`, {
      method: 'POST',
    });
    return response;
  } catch (error) {
    console.warn('Mark alert read API unavailable:', error.message);
    return { success: false };
  }
}

// Fetch chart data for disease distribution
export async function fetchDiseaseDistributionChart() {
  try {
    const response = await apiCall('/charts/disease-distribution');
    return response.data || response;
  } catch (error) {
    console.warn('Disease distribution chart API unavailable:', error.message);
    return { labels: [], datasets: [] };
  }
}

// Fetch chart data for severity distribution
export async function fetchSeverityDistributionChart() {
  try {
    const response = await apiCall('/charts/severity-distribution');
    return response.data || response;
  } catch (error) {
    console.warn('Severity distribution chart API unavailable:', error.message);
    return { labels: [], datasets: [] };
  }
}

// Fetch chart data for yield trend
export async function fetchYieldTrendChart() {
  try {
    const response = await apiCall('/charts/yield-trend');
    return response.data || response;
  } catch (error) {
    console.warn('Yield trend chart API unavailable:', error.message);
    return [];
  }
}

// Fetch chart data for daily detections
export async function fetchDailyDetectionsChart() {
  try {
    const response = await apiCall('/charts/daily-detections');
    return response.data || response;
  } catch (error) {
    console.warn('Daily detections chart API unavailable:', error.message);
    return [];
  }
}

// Add disease detection record
export async function addDiseaseDetection(detectionData) {
  try {
    const response = await apiCall('/disease-detection', {
      method: 'POST',
      body: JSON.stringify(detectionData),
    });
    return response;
  } catch (error) {
    console.warn('Add disease detection API unavailable:', error.message);
    return { success: false };
  }
}

// Add yield prediction record
export async function addYieldPrediction(predictionData) {
  try {
    const response = await apiCall('/yield-prediction', {
      method: 'POST',
      body: JSON.stringify(predictionData),
    });
    return response;
  } catch (error) {
    console.warn('Add yield prediction API unavailable:', error.message);
    return { success: false };
  }
}

// Save a detection result (mature fruit count) to the yield chart
export async function saveYieldToChart(matureFruits, location = 'Field', season = null, uploadType = 'image') {
  try {
    const response = await apiCall('/yield-prediction', {
      method: 'POST',
      body: JSON.stringify({ mature_fruits: matureFruits, location, season, upload_type: uploadType }),
    });
    return response;
  } catch (error) {
    console.warn('Save yield to chart failed:', error.message);
    return { success: false, error: error.message };
  }
}

// Upload an image for yield detection (returns detections and annotated image)
export async function uploadYieldImage(file, conf = 0.55, detectionMode = 'photo') {
  try {
    const form = new FormData();
    form.append('image', file);
    form.append('conf', String(conf));
    form.append('detection_mode', detectionMode);
    // Only the trained mature-dragon-fruit class is allowed to create a count.
    form.append('method', 'yolo');

    const response = await fetch(`${API_BASE}/yield-detect`, {
      method: 'POST',
      body: form,
      headers: getPitayaUserScopeHeaders(),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`HTTP ${response.status}: ${text}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.warn('Yield image upload failed:', error.message);
    return { success: false, error: error.message };
  }
}

// Upload a video for yield detection (counts mature fruits in the whole video)
export async function uploadYieldVideo(videoFile, conf = 0.55) {
  try {
    const form = new FormData();
    form.append('video', videoFile);
    form.append('conf', String(conf));
    form.append('method', 'yolo');

    const response = await fetch(`${API_BASE}/yield-video-detect`, {
      method: 'POST',
      body: form,
      headers: getPitayaUserScopeHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(errorData?.error || `Video upload failed (HTTP ${response.status}).`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.warn('Yield video upload failed:', error.message);
    return { success: false, error: error.message };
  }
}

// Run yield detection on a live stream URL (e.g., Android IP camera)
export async function detectYieldFromStream(streamUrl, conf = 0.55) {
  try {
    const form = new FormData();
    form.append('stream_url', streamUrl);
    form.append('conf', String(conf));

    const response = await fetch(`${API_BASE}/yield-video-detect`, {
      method: 'POST',
      body: form,
      headers: getPitayaUserScopeHeaders(),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`HTTP ${response.status}: ${text}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.warn('Yield stream detection failed:', error.message);
    return { success: false, error: error.message };
  }
}

// Health check
export async function healthCheck() {
  try {
    const response = await apiCall('/health');
    return response;
  } catch (error) {
    console.warn('Health check failed:', error.message);
    return { success: false };
  }
}

// Fallback data for when API is unavailable
function getFallbackData() {
  return {
    summary: {
      total_detections: 0,
      high_severity_cases: 0,
      unread_alerts: 0,
      avg_prediction_accuracy: 0,
      total_predictions: 0
    },
    disease_data: {
      disease_distribution: [],
      severity_distribution: [],
      daily_detections: [],
      location_distribution: []
    },
    yield_data: {
      yield_trend: [],
      accuracy_info: { avg_accuracy: 0, total_predictions: 0 },
      seasonal_yields: [],
      location_yields: []
    },
    recent_alerts: []
  };
}

// Legacy function for backward compatibility
export async function fetchDashboard() {
  try {
    const [summary, diseaseStats, yieldStats, alerts] = await Promise.all([
      fetchDashboardSummary(),
      fetchDiseaseStats(),
      fetchYieldStats(),
      fetchAlerts(),
    ]);

    return {
      totalDetections: summary.totalDetections || 0,
      highSeverityCases: summary.highSeverityCases || 0,
      unreadAlerts: summary.unreadAlerts || 0,
      avgConfidence: summary.avgConfidence || 0,
      totalYieldRecords: summary.totalYieldRecords || 0,
      totalFruits: summary.totalFruits || 0,
      diseaseDistribution: diseaseStats.disease_distribution || {},
      severityDistribution: diseaseStats.severity_distribution || {},
      yieldTrend: yieldStats.yield_trend || [],
      dailyDetections: diseaseStats.daily_detections || [],
      alerts: alerts || []
    };
  } catch (error) {
    console.warn('Dashboard fetch failed, using fallback:', error.message);
    return getFallbackData();
  }
}

// Delete a disease detection record
export async function deleteDetection(detectionId) {
  try {
    const response = await apiCall(`/detections/${detectionId}`, {
      method: 'DELETE'
    });
    return response;
  } catch (error) {
    console.warn('Delete detection API unavailable:', error.message);
    return { success: false, error: error.message };
  }
}

// Get comprehensive detection statistics
export async function fetchDetectionStatistics() {
  try {
    const response = await apiCall('/detection-statistics');
    return response.data || response;
  } catch (error) {
    console.warn('Detection statistics API unavailable:', error.message);
    return {
      total_detections: 0,
      disease_counts: {},
      severity_counts: {},
      recent_detections: {},
      monthly_trends: {}
    };
  }
}

// Get disease library data with detection counts
export async function fetchDiseaseLibraryData() {
  try {
    const response = await apiCall('/disease-library');
    return response.data || response;
  } catch (error) {
    console.warn('Disease library API unavailable:', error.message);
    return [];
  }
}

// Get unread alert count
export async function fetchUnreadAlertCount() {
  try {
    const response = await apiCall('/alerts/unread-count');
    return response.data || response;
  } catch (error) {
    console.warn('Unread alert count API unavailable:', error.message);
    return { count: 0 };
  }
}
