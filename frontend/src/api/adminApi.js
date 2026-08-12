// Admin API service for PITAYA admin panel

import { getPitayaUserScopeHeaders } from './userScope';

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
const REQUEST_TIMEOUT_MS = 15_000;

// Store admin token in localStorage
const ADMIN_TOKEN_KEY = 'pitaya_admin_token';

function getDefaultAdminToken() {
  return import.meta.env.VITE_ADMIN_TOKEN || 'admin-secret-token-12345';
}

// Helper to get admin token
function getAdminToken() {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

// Helper to set admin token
function setAdminToken(token) {
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

// Helper to clear admin token
function clearAdminToken() {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}

// Helper to get current user from localStorage
function getCurrentUser() {
  try {
    const raw = localStorage.getItem('pitayaUser');
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// Helper to make authenticated admin requests
async function fetchWithAdminAuth(url, options = {}) {
  const token = getAdminToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` }),
    ...getPitayaUserScopeHeaders(),
    ...(options.headers || {}),
  };

  // Remove Content-Type for FormData
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const finalUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;
  
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(finalUrl, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeoutId);
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
    const error = new Error(errorData.error || `API Error: ${response.status}`);
    error.status = response.status;
    error.data = errorData;
    throw error;
  }

  return response.json();
}

// Admin Authentication API
const adminAuthApi = {
  // Admin login
  login: async (username, password) => {
    const response = await fetchWithAdminAuth('/api/admin/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    if (response.success && response.adminToken) {
      setAdminToken(response.adminToken);
    }

    return response;
  },

  // Admin logout
  logout: () => {
    clearAdminToken();
    // Also clear the pitayaUser from localStorage
    localStorage.removeItem('pitayaUser');
  },

  // Check if admin is authenticated
  isAuthenticated: () => {
    const user = getCurrentUser();
    if (user?.isAdmin !== true) return false;

    const token = getAdminToken();
    if (token) return true;

    // Keep admin session alive on refresh when admin came from regular login.
    const fallbackToken = getDefaultAdminToken();
    if (fallbackToken) {
      setAdminToken(fallbackToken);
      return true;
    }

    return false;
  },
};

// Admin Dashboard API
const adminDashboardApi = {
  // Get dashboard metrics
  getMetrics: async () => {
    return fetchWithAdminAuth('/api/admin/dashboard/metrics');
  },
};

// Admin User Management API
const adminUsersApi = {
  // Get all users
  getAllUsers: async () => {
    return fetchWithAdminAuth('/api/admin/users');
  },

  // Get user by ID
  getUserById: async (userId) => {
    return fetchWithAdminAuth(`/api/admin/users/${userId}`);
  },

  // Create new user
  createUser: async (userData) => {
    return fetchWithAdminAuth('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  },

  // Update user
  updateUser: async (userId, userData) => {
    return fetchWithAdminAuth(`/api/admin/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    });
  },

  // Delete user
  deleteUser: async (userId) => {
    return fetchWithAdminAuth(`/api/admin/users/${userId}`, {
      method: 'DELETE',
    });
  },
};

// Admin User Logs API
const adminLogsApi = {
  // Get user logs with filters
  getLogs: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.user_id) params.append('user_id', filters.user_id);
    if (filters.action) params.append('action', filters.action);
    if (filters.limit) params.append('limit', filters.limit);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    return fetchWithAdminAuth(`/api/admin/logs${queryString}`);
  },
};

// Admin Site Settings API
const adminSettingsApi = {
  // Get site settings
  getSettings: async (category = null) => {
    const params = category ? `?category=${category}` : '';
    return fetchWithAdminAuth(`/api/admin/settings${params}`);
  },

  // Update site setting
  updateSetting: async (settingKey, value) => {
    return fetchWithAdminAuth(`/api/admin/settings/${settingKey}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    });
  },
};

// Admin Disease Detections API
const adminDetectionsApi = {
  // Get all detections
  getAllDetections: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    return fetchWithAdminAuth(`/api/admin/detections${queryString}`);
  },

  // Delete detection
  deleteDetection: async (detectionId) => {
    return fetchWithAdminAuth(`/api/admin/detections/${detectionId}`, {
      method: 'DELETE',
    });
  },
};

// Admin Yield Predictions API
const adminYieldApi = {
  // Get all yield predictions
  getAllPredictions: async () => {
    return fetchWithAdminAuth('/api/admin/yield-predictions');
  },

  // Delete yield prediction
  deletePrediction: async (predictionId) => {
    return fetchWithAdminAuth(`/api/admin/yield-predictions/${predictionId}`, {
      method: 'DELETE',
    });
  },
};

// Export all admin API functions
export {
    adminAuthApi,
    adminDashboardApi, adminDetectionsApi, adminLogsApi,
    adminSettingsApi,
    adminUsersApi, adminYieldApi, clearAdminToken, getAdminToken,
    setAdminToken
};
