import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Filter,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { libraryApi } from '../api/client';
import { getPitayaUserScopeHeaders } from '../api/userScope';
import LoadingSpinner from './LoadingSpinner';

const HISTORY_KEY = 'pitaya.alerts.history.v1';
const ROOT_REMOVAL_MESSAGE = 'Remove infected roots immediately to prevent spread of disease.';
const ROOT_REMOVAL_PROTOCOL_STEPS = [
  'Carefully remove affected roots',
  'Dispose of infected parts properly',
  'Apply fungicide if necessary',
  'Avoid overwatering',
];

function safeParseJson(value, fallback) {
  try {
    const parsed = JSON.parse(value);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function toAlertKey(raw) {
  const id = raw?.AlertID || raw?.id;
  if (id !== undefined && id !== null && String(id).trim() !== '') return String(id);

  const disease = raw?.DiseaseType || raw?.disease_name || raw?.related_disease || 'Unknown';
  const ts = raw?.DateTime || raw?.detected_date || raw?.created_at || raw?.CreatedAt || '';
  const det = raw?.DetectionID || raw?.detection_id || '';
  return `${String(disease)}|${String(ts)}|${String(det)}`;
}

function normalizeSeverity(sev) {
  const s = String(sev || 'medium').toLowerCase();
  if (['high', 'medium', 'low'].includes(s)) return s;
  return 'medium';
}

function inferRequiresRootRemoval(diseaseName, details) {
  const name = String(diseaseName || '').toLowerCase();
  if (name.includes('root rot')) return true;
  const haystack = [
    diseaseName,
    JSON.stringify(details?.symptoms ?? ''),
    JSON.stringify(details?.recommended_treatments ?? ''),
    JSON.stringify(details?.description ?? ''),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return /\broot\b|\broots\b/.test(haystack);
}

function getSeverityBadgeClasses(severity) {
  switch (severity) {
    case 'high':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'medium':
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'low':
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
}

function mapAlertRecords(data = []) {
  return data.map((a) => {
    const alert_id = a.AlertID ?? a.alert_id ?? a.id ?? null;
    const disease_name = a.DiseaseType || a.disease_name || a.related_disease || 'Unknown';
    const severity = normalizeSeverity(a.Severity || a.severity);
    const detectedAt = a.DateTime || a.detected_date || a.created_at || a.CreatedAt;
    const key = toAlertKey(a);

    return {
      alert_id,
      key,
      disease_name,
      severity,
      message: `${disease_name} detected`,
      confidence: typeof (a.Confidence ?? a.confidence) === 'number' ? (a.Confidence ?? a.confidence) : null,
      detectedAt,
      detection_id: a.DetectionID || a.detection_id || null,
      location: a.Location || a.location || 'User Upload',
      image_path: a.ImagePath || a.image_path || null,
    };
  });
}

function formatDetectedAt(value) {
  if (!value) return 'Unknown time';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return 'Unknown time';
  return d.toLocaleString();
}

function normalizeList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (typeof value === 'string') {
    const cleaned = value
      .replace(/\r/g, '')
      .split('\n')
      .map((line) => line.replace(/^\s*(?:[-•*]|\d+\.)\s*/g, '').trim())
      .filter(Boolean);
    return cleaned.length ? cleaned : [value.trim()].filter(Boolean);
  }
  return [];
}

function flattenRecommendedTreatmentsToSteps(treatmentsData) {
  if (!treatmentsData) return [];
  if (Array.isArray(treatmentsData) || typeof treatmentsData === 'string') {
    return normalizeList(treatmentsData);
  }
  if (typeof treatmentsData !== 'object') return [];

  const steps = [];
  if (Array.isArray(treatmentsData.non_chemical_methods)) steps.push(...treatmentsData.non_chemical_methods);
  if (Array.isArray(treatmentsData.best_practices)) steps.push(...treatmentsData.best_practices);
  if (Array.isArray(treatmentsData.approved_fungicides)) {
    steps.push(
      ...treatmentsData.approved_fungicides.map((f) => {
        const product = f?.product ? String(f.product) : 'Fungicide';
        const dosage = f?.dosage ? ` — ${f.dosage}` : '';
        const frequency = f?.frequency ? ` (${f.frequency})` : '';
        return `Apply ${product}${dosage}${frequency}`;
      })
    );
  }
  return normalizeList(steps);
}

function renderObjectOrList(value) {
  if (!value) return <p className="text-sm text-gray-500">No information available.</p>;
  if (Array.isArray(value)) {
    const items = normalizeList(value);
    if (!items.length) return <p className="text-sm text-gray-500">No information available.</p>;
    return (
      <ul className="space-y-2">
        {items.map((item, idx) => (
          <li key={idx} className="flex items-start gap-2">
            <span className="text-pitaya-primary mt-1">•</span>
            <span className="text-sm text-gray-700 dark:text-gray-300">{item}</span>
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === 'string') {
    const items = normalizeList(value);
    if (items.length > 1) {
      return (
        <ul className="space-y-2">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="text-pitaya-primary mt-1">•</span>
              <span className="text-sm text-gray-700 dark:text-gray-300">{item}</span>
            </li>
          ))}
        </ul>
      );
    }
    return <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{value}</p>;
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value)
      .filter(([_, v]) => v !== null && v !== undefined)
      .map(([k, v]) => ({ key: k, value: v }));

    if (!entries.length) return <p className="text-sm text-gray-500">No information available.</p>;

    return (
      <div className="space-y-4">
        {entries.map((e) => (
          <div key={e.key} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white/60 dark:bg-gray-800/40 p-3">
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 capitalize">
              {String(e.key).replace(/_/g, ' ')}
            </p>
            <div className="mt-2">{renderObjectOrList(e.value)}</div>
          </div>
        ))}
      </div>
    );
  }

  return <p className="text-sm text-gray-500">No information available.</p>;
}

export default function AlertsModule() {
  const [alerts, setAlerts] = useState([]);
  const [unreadAlerts, setUnreadAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);

  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState('all'); // all|high|medium|low
  const [statusFilter, setStatusFilter] = useState('active'); // active|unread|treated

  const [selectedAlertKey, setSelectedAlertKey] = useState(null);
  const [diseaseDetails, setDiseaseDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState('');

  const [confirmTreatKey, setConfirmTreatKey] = useState(null);
  const [pageByStatus, setPageByStatus] = useState({ active: 1, unread: 1, treated: 1 });

  const itemsPerPage = 10;

  const [history, setHistory] = useState(() => {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? safeParseJson(raw, { treatedAlerts: [], viewedDiseases: [] }) : { treatedAlerts: [], viewedDiseases: [] };
  });

  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch {
      // ignore
    }
  }, [history]);

  const treatedKeySet = useMemo(() => {
    const set = new Set();
    for (const item of history.treatedAlerts || []) {
      if (item?.key) set.add(String(item.key));
    }
    return set;
  }, [history.treatedAlerts]);

  const selectedAlert = useMemo(() => {
    if (!selectedAlertKey) return null;
    const fromActive = alerts.find((a) => a.key === selectedAlertKey) || unreadAlerts.find((a) => a.key === selectedAlertKey);
    if (fromActive) return fromActive;
    const fromTreated = (history.treatedAlerts || []).find((a) => String(a.key) === String(selectedAlertKey));
    return fromTreated || null;
  }, [alerts, history.treatedAlerts, selectedAlertKey, unreadAlerts]);

  const fetchUnreadCount = async () => {
    try {
      const response = await fetch('/api/dashboard/alerts/unread-count', { headers: getPitayaUserScopeHeaders() });
      const data = await response.json();
      if (data?.success) setUnreadCount(data.data.count || 0);
    } catch {
      // ignore
    }
  };

  const fetchAlerts = async () => {
    try {
      const scopeHeaders = { headers: getPitayaUserScopeHeaders() };
      const [allResponse, unreadResponse] = await Promise.all([
        fetch('/api/dashboard/alerts', scopeHeaders),
        fetch('/api/dashboard/alerts?unread_only=true', scopeHeaders),
      ]);

      const allRoot = await allResponse.json();
      const unreadRoot = await unreadResponse.json();

      const mappedAll = mapAlertRecords(allRoot?.data || []);
      const mappedUnread = mapAlertRecords(unreadRoot?.data || []);

      // Keep only active items in the active list and unread items in the unread list
      setAlerts(mappedAll.filter((a) => !treatedKeySet.has(a.key)));
      setUnreadAlerts(mappedUnread.filter((a) => !treatedKeySet.has(a.key)));
      setLoading(false);
    } catch (error) {
      console.error('Error fetching alerts:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    fetchUnreadCount();
    const interval = window.setInterval(() => {
      fetchAlerts();
      fetchUnreadCount();
    }, 5000);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [treatedKeySet]);

  useEffect(() => {
    const handler = () => {
      fetchAlerts();
      fetchUnreadCount();
    };
    window.addEventListener('pitaya:refresh', handler);
    return () => window.removeEventListener('pitaya:refresh', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleAlerts = useMemo(() => {
    const base = statusFilter === 'treated'
      ? (history.treatedAlerts || [])
      : statusFilter === 'unread'
        ? unreadAlerts
        : alerts;
    const term = searchTerm.trim().toLowerCase();

    return base
      .filter((a) => {
        if (severityFilter === 'all') return true;
        return normalizeSeverity(a.severity) === severityFilter;
      })
      .filter((a) => {
        if (!term) return true;
        return String(a.disease_name || '').toLowerCase().includes(term);
      })
      .sort((a, b) => {
        const da = new Date(a.detectedAt || a.treatedAt || 0).getTime();
        const db = new Date(b.detectedAt || b.treatedAt || 0).getTime();
        return db - da;
      });
  }, [alerts, history.treatedAlerts, searchTerm, severityFilter, statusFilter, unreadAlerts]);

  const currentPage = pageByStatus[statusFilter] || 1;
  const totalPages = Math.max(1, Math.ceil(visibleAlerts.length / itemsPerPage));
  const paginatedAlerts = visibleAlerts.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  useEffect(() => {
    if (currentPage > totalPages) {
      setPageByStatus((prev) => ({
        ...prev,
        [statusFilter]: totalPages,
      }));
    }
  }, [currentPage, statusFilter, totalPages]);

  useEffect(() => {
    setPageByStatus((prev) => ({
      ...prev,
      [statusFilter]: 1,
    }));
  }, [searchTerm, severityFilter, statusFilter]);

  const goToPage = (nextPage) => {
    setPageByStatus((prev) => ({
      ...prev,
      [statusFilter]: Math.min(Math.max(nextPage, 1), totalPages),
    }));
  };

  const markAsReadOnServer = async (alertKey) => {
    try {
      await fetch(`/api/dashboard/alerts/${encodeURIComponent(alertKey)}/read`, { method: 'POST', headers: getPitayaUserScopeHeaders() });
    } catch {
      // ignore
    }
  };

  const markAlertAsRead = async (alert) => {
    const alertIdentifier = alert?.alert_id ?? alert?.key;
    setUnreadAlerts((prev) => prev.filter((a) => a.key !== alert.key));
    await markAsReadOnServer(alertIdentifier);
    fetchUnreadCount();
  };

  const markAsTreated = async (alert) => {
    const treatedRecord = {
      key: alert.key,
      disease_name: alert.disease_name,
      severity: normalizeSeverity(alert.severity),
      message: alert.message,
      detectedAt: alert.detectedAt,
      treatedAt: new Date().toISOString(),
      location: alert.location,
      confidence: alert.confidence,
    };

    setHistory((prev) => {
      const without = (prev.treatedAlerts || []).filter((x) => String(x.key) !== String(alert.key));
      return {
        ...prev,
        treatedAlerts: [treatedRecord, ...without].slice(0, 50),
      };
    });

    setAlerts((prev) => prev.filter((a) => a.key !== alert.key));
    setUnreadAlerts((prev) => prev.filter((a) => a.key !== alert.key));
    await markAsReadOnServer(alert.key);
    fetchUnreadCount();
  };

  const onViewDetails = async (alert) => {
    setSelectedAlertKey(alert.key);
    setDiseaseDetails(null);
    setDetailsError('');
    setDetailsLoading(true);

    // Viewing details counts as reading the alert.
    markAlertAsRead(alert);

    // Save to viewed history
    setHistory((prev) => {
      const now = new Date().toISOString();
      const without = (prev.viewedDiseases || []).filter(
        (x) => String(x.disease_name || '').toLowerCase() !== String(alert.disease_name || '').toLowerCase()
      );
      return {
        ...prev,
        viewedDiseases: [{ disease_name: alert.disease_name, viewedAt: now }, ...without].slice(0, 20),
      };
    });

    try {
      const res = await libraryApi.getDiseaseByName(alert.disease_name);
      const details = res?.data || res;
      setDiseaseDetails(details);
    } catch (e) {
      setDetailsError('Could not load disease details.');
    } finally {
      setDetailsLoading(false);
    }
  };

  const stats = useMemo(() => {
    const active = alerts.length;
    const treated = (history.treatedAlerts || []).length;
    const high = alerts.filter((a) => normalizeSeverity(a.severity) === 'high').length;
    return { active, treated, high };
  }, [alerts, history.treatedAlerts]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-pitaya-pale border border-pitaya-leaf/20 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-pitaya-primary" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">Alerts</h1>
              <p className="text-sm text-gray-600 dark:text-gray-300">Notifications from recent disease detections</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 mb-6">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-card border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-sm font-medium text-gray-600 dark:text-gray-300">Active alerts</p>
          <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">{stats.active}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-card border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-sm font-medium text-gray-600 dark:text-gray-300">High severity</p>
          <p className="mt-2 text-2xl font-bold text-red-600">{stats.high}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-card border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-sm font-medium text-gray-600 dark:text-gray-300">Treated history</p>
          <p className="mt-2 text-2xl font-bold text-pitaya-primary">{stats.treated}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-card border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search disease name..."
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-pitaya-mint focus:border-transparent"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="w-full py-3 px-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            >
              <option value="all">All severity</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setStatusFilter('active')}
              className={`flex-1 min-h-[44px] px-4 py-3 rounded-xl text-sm font-semibold border transition-colors ${
                statusFilter === 'active'
                  ? 'bg-pitaya-primary text-white border-pitaya-primary'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border-gray-200 dark:border-gray-700 hover:bg-pitaya-bg/60'
              }`}
            >
              Active
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('unread')}
              className={`relative flex-1 min-h-[44px] px-4 py-3 rounded-xl text-sm font-semibold border transition-colors ${
                statusFilter === 'unread'
                  ? 'bg-pitaya-primary text-white border-pitaya-primary'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border-gray-200 dark:border-gray-700 hover:bg-pitaya-bg/60'
              }`}
            >
              {unreadCount > 0 && (
                <span className="absolute -top-2 -left-2 inline-flex min-w-6 h-6 items-center justify-center rounded-full bg-pitaya-primary px-1.5 text-xs font-bold text-white shadow-md ring-2 ring-white dark:ring-gray-800">
                  {unreadCount}
                </span>
              )}
              Unread
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('treated')}
              className={`flex-1 min-h-[44px] px-4 py-3 rounded-xl text-sm font-semibold border transition-colors ${
                statusFilter === 'treated'
                  ? 'bg-pitaya-primary text-white border-pitaya-primary'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border-gray-200 dark:border-gray-700 hover:bg-pitaya-bg/60'
              }`}
            >
              Treated
            </button>
          </div>
        </div>
      </div>

      {/* Viewed History */}
      {(history.viewedDiseases || []).length > 0 && (
        <div className="mb-6 bg-white dark:bg-gray-800 rounded-2xl shadow-card border border-gray-200 dark:border-gray-700 p-4">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Viewed History</h2>
          <p className="text-xs text-gray-600 dark:text-gray-300 mt-1">Recently viewed diseases (latest first)</p>
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {(history.viewedDiseases || []).slice(0, 6).map((v) => (
              <div
                key={`${v.disease_name}-${v.viewedAt}`}
                className="flex items-start justify-between gap-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white/60 dark:bg-gray-800/40 px-3 py-2"
              >
                <div>
                  <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{v.disease_name}</p>
                  <p className="text-xs text-gray-600 dark:text-gray-300 mt-0.5">Viewed: {formatDetectedAt(v.viewedAt)}</p>
                </div>
                <Clock className="w-4 h-4 text-pitaya-primary mt-1" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alerts List */}
      <motion.div layout className="space-y-4">
        {visibleAlerts.length === 0 ? (
          <div className="text-center py-12">
            <CheckCircle className="w-16 h-16 text-pitaya-mint mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">No alerts</h3>
            <p className="text-gray-600 dark:text-gray-300 mt-2">
              {statusFilter === 'active'
                ? 'No active alerts right now.'
                : statusFilter === 'unread'
                  ? 'No unread alerts right now.'
                  : 'No treated alerts in history.'}
            </p>
          </div>
        ) : (
          paginatedAlerts.map((alert) => {
            const severity = normalizeSeverity(alert.severity);
            const isResolved = statusFilter === 'treated' || treatedKeySet.has(alert.key);
            return (
              <motion.div
                key={alert.key}
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className={`rounded-2xl border shadow-card p-4 sm:p-5 bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 ${
                  isResolved ? 'opacity-75' : ''
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                  <div className="flex-1">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{alert.disease_name}</h3>
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-full border text-xs font-semibold ${getSeverityBadgeClasses(severity)}`}>
                            {severity.toUpperCase()}
                          </span>
                          {isResolved && (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold bg-gray-100 text-gray-700 border-gray-200">
                              <ShieldCheck className="w-3.5 h-3.5" />
                              Resolved
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                          {alert.message || `${alert.disease_name} detected`}
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={() => setSelectedAlertKey(null)}
                        className="hidden"
                        aria-hidden
                      />
                    </div>

                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-gray-700 dark:text-gray-300">
                      <p>
                        <span className="font-semibold">Detected:</span> {formatDetectedAt(alert.detectedAt)}
                      </p>
                      <p>
                        <span className="font-semibold">Location:</span> {alert.location || 'Unknown'}
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
                    <button
                      type="button"
                      onClick={() => onViewDetails(alert)}
                      className="min-h-[44px] px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-pitaya-bg/60 transition-colors text-sm font-semibold"
                    >
                      View Details
                    </button>

                    <button
                      type="button"
                      onClick={() => setConfirmTreatKey(alert.key)}
                      disabled={isResolved}
                      className="min-h-[44px] px-4 py-3 rounded-xl bg-pitaya-primary text-white hover:bg-pitaya-leaf transition-colors text-sm font-semibold disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      Mark as Treated ✅
                    </button>
                  </div>
                </div>
              </motion.div>
            );
          })
        )}
      </motion.div>

      {visibleAlerts.length > 0 && (
        <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-3 rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3">
          <p className="text-sm text-gray-600 dark:text-gray-300">
            Showing {Math.min((currentPage - 1) * itemsPerPage + 1, visibleAlerts.length)}-{Math.min(currentPage * itemsPerPage, visibleAlerts.length)} of {visibleAlerts.length}
          </p>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className="min-h-[40px] px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm font-semibold text-gray-700 dark:text-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>

            <span className="min-w-20 text-center text-sm font-semibold text-gray-900 dark:text-gray-100">
              Page {currentPage} of {totalPages}
            </span>

            <button
              type="button"
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="min-h-[40px] px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm font-semibold text-gray-700 dark:text-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Details Modal */}
      <AnimatePresence>
        {selectedAlert && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => {
              setSelectedAlertKey(null);
              setDiseaseDetails(null);
              setDetailsError('');
            }}
          >
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 14 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-white dark:bg-gray-800 rounded-2xl shadow-card-hover border border-gray-200 dark:border-gray-700"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="p-5 sm:p-6 border-b border-gray-200 dark:border-gray-700 flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">{selectedAlert.disease_name}</h2>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">Detected: {formatDetectedAt(selectedAlert.detectedAt)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedAlertKey(null);
                    setDiseaseDetails(null);
                    setDetailsError('');
                  }}
                  className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl border border-gray-200 dark:border-gray-700 hover:bg-pitaya-bg/60 transition-colors"
                  aria-label="Close"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-5 sm:p-6 space-y-6">
                {detailsLoading && (
                  <div className="py-10">
                    <LoadingSpinner className="min-h-0" />
                    <p className="text-center text-sm text-gray-600 dark:text-gray-300 mt-3">Loading details...</p>
                  </div>
                )}

                {!detailsLoading && detailsError && (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
                    <p className="font-semibold">{detailsError}</p>
                    <p className="text-sm mt-1">
                      {(statusFilter === 'treated' || treatedKeySet.has(selectedAlert.key))
                        ? 'This alert is already marked as treated.'
                        : 'You can still mark the alert as treated.'}
                    </p>
                  </div>
                )}

                {!detailsLoading && diseaseDetails && (() => {
                  const requiresRootRemoval = inferRequiresRootRemoval(selectedAlert.disease_name, diseaseDetails);
                  const isSevere = normalizeSeverity(selectedAlert.severity) === 'high';
                  const treatmentsData = diseaseDetails.recommended_treatments;
                  const steps = flattenRecommendedTreatmentsToSteps(treatmentsData);
                  const mergedSteps = requiresRootRemoval
                    ? [...ROOT_REMOVAL_PROTOCOL_STEPS, ...steps]
                    : steps;

                  return (
                    <>
                      {(isSevere || requiresRootRemoval) && (
                        <div className="space-y-3">
                          {isSevere && (
                            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-800">
                              <div className="flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 mt-0.5" />
                                <div>
                                  <p className="font-semibold">Immediate action required</p>
                                  <p className="text-sm mt-0.5">This alert is high severity.</p>
                                </div>
                              </div>
                            </div>
                          )}
                          {requiresRootRemoval && (
                            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-800">
                              <p className="font-semibold">⚠️ Critical action</p>
                              <p className="text-sm mt-1">👉 {ROOT_REMOVAL_MESSAGE}</p>
                            </div>
                          )}
                        </div>
                      )}

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Symptoms</h3>
                          <div className="mt-3">{renderObjectOrList(diseaseDetails.symptoms)}</div>
                        </div>
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Causes</h3>
                          <div className="mt-3">{renderObjectOrList(diseaseDetails.causes)}</div>
                        </div>
                      </div>

                      <div>
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Recommended treatment</h3>
                        <div className="mt-3">
                          {mergedSteps.length ? (
                            <ol className="space-y-2">
                              {mergedSteps.map((s, idx) => (
                                <li key={`${idx}-${s}`} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white/60 dark:bg-gray-800/40 px-3 py-2">
                                  <p className="text-sm text-gray-800 dark:text-gray-200">
                                    <span className="mr-2 opacity-70">{idx + 1}.</span>
                                    {s}
                                  </p>
                                </li>
                              ))}
                            </ol>
                          ) : (
                            renderObjectOrList(diseaseDetails.recommended_treatments)
                          )}
                        </div>
                      </div>
                    </>
                  );
                })()}

                <div className="flex flex-col sm:flex-row gap-2 sm:justify-end">
                  <button
                    type="button"
                    onClick={() => setConfirmTreatKey(selectedAlert.key)}
                    disabled={statusFilter === 'treated' || treatedKeySet.has(selectedAlert.key)}
                    className="min-h-[44px] px-4 py-3 rounded-xl bg-pitaya-primary text-white hover:bg-pitaya-leaf transition-colors text-sm font-semibold disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    Mark as Treated ✅
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedAlertKey(null);
                      setDiseaseDetails(null);
                      setDetailsError('');
                    }}
                    className="min-h-[44px] px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-pitaya-bg/60 transition-colors text-sm font-semibold"
                  >
                    Close
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confirm Treat Modal */}
      <AnimatePresence>
        {confirmTreatKey && (() => {
          const target =
            alerts.find((a) => a.key === confirmTreatKey) ||
            (history.treatedAlerts || []).find((a) => String(a.key) === String(confirmTreatKey));
          if (!target) return null;

          return (
            <motion.div
              className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setConfirmTreatKey(null)}
            >
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className="w-full max-w-md bg-white dark:bg-gray-800 rounded-2xl shadow-card-hover border border-gray-200 dark:border-gray-700 p-5"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">Mark as treated?</h3>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-2">
                  Are you sure you want to mark <span className="font-semibold">{target.disease_name}</span> as treated?
                </p>

                <div className="mt-4 flex flex-col sm:flex-row gap-2 sm:justify-end">
                  <button
                    type="button"
                    onClick={() => setConfirmTreatKey(null)}
                    className="min-h-[44px] px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-pitaya-bg/60 transition-colors text-sm font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      setConfirmTreatKey(null);
                      await markAsTreated(target);
                      if (selectedAlertKey === target.key) {
                        setSelectedAlertKey(null);
                        setDiseaseDetails(null);
                        setDetailsError('');
                      }
                    }}
                    className="min-h-[44px] px-4 py-3 rounded-xl bg-pitaya-primary text-white hover:bg-pitaya-leaf transition-colors text-sm font-semibold"
                  >
                    Yes, mark treated
                  </button>
                </div>
              </motion.div>
            </motion.div>
          );
        })()}
      </AnimatePresence>
    </div>
  );
}
