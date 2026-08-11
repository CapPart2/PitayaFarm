import { AnimatePresence, motion } from 'framer-motion';
import {
    AlertCircle,
    AlertTriangle,
    ArrowLeft,
    BookOpen,
    CheckCircle,
    Images,
    Loader2,
    Plus,
    Save,
    Scissors,
    Search,
    Trash2,
    X
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { TAGALOG_DISEASE_CONTENT } from '../data/tagalogDiseaseContent';
import LoadingSpinner from './LoadingSpinner';

// Disease image mapping for comprehensive dragon fruit diseases
const diseaseImages = {
  'Anthracnose': '/All Disease/Anthracnose.jpg',
  'Stem Canker': '/All Disease/Stem_Canker.jpg',  // Updated from Black Rot
  'White Spot': '/All Disease/White Spot.jpeg',
  'Brown Spot': '/All Disease/brownspot.jpeg',
  'Stem Rot': '/All Disease/Stem Rot.jpeg',
  'Root Rot': '/All Disease/Root Rot.jpg',
  'Soft Rot': '/All Disease/Soft Rot.jpg',
  'Twig Blight': '/All Disease/Twig Blight.jpg',
  'Black Spot': '/All Disease/blackspot.jpeg',
};

const galleryImagesFor = (diseaseName) => {
  const slug = String(diseaseName || '').toLowerCase().replace(/\s+/g, '-');
  return Array.from({ length: 5 }, (_, index) => `/disease-gallery/${slug}/${index + 1}.jpg`);
};

const getLibrarySeverity = (diseaseName, severity) =>
  diseaseName === 'White Spot' ? 'medium' : String(severity || 'medium').toLowerCase();

const OVERRIDES_STORAGE_KEY = 'pitaya.diseaseLibrary.overrides.v1';
const EMPTY_OVERRIDES = Object.freeze({});

const ROOT_REMOVAL_MESSAGE = 'Remove infected roots immediately to prevent spread of disease.';
const ROOT_REMOVAL_PROTOCOL_STEPS = [
  'Carefully remove affected roots',
  'Dispose of infected parts properly',
  'Apply fungicide if necessary',
  'Avoid overwatering',
];

const normalizeList = (value) => {
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
};

const valueToLines = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) return value.flatMap((item) => valueToLines(item));
  if (typeof value === 'string') return normalizeList(value);
  if (typeof value === 'object') return Object.values(value).flatMap((item) => valueToLines(item));
  return [String(value)].filter(Boolean);
};

const toMultilineText = (value) => valueToLines(value).join('\n');

const flattenRecommendedTreatmentsToSteps = (treatmentsData) => {
  if (!treatmentsData) return [];
  if (Array.isArray(treatmentsData) || typeof treatmentsData === 'string') {
    return normalizeList(treatmentsData);
  }
  if (typeof treatmentsData !== 'object') return [];

  const steps = [];
  if (Array.isArray(treatmentsData.non_chemical_methods)) {
    steps.push(...treatmentsData.non_chemical_methods);
  }
  if (Array.isArray(treatmentsData.best_practices)) {
    steps.push(...treatmentsData.best_practices);
  }
  if (Array.isArray(treatmentsData.approved_fungicides)) {
    steps.push(
      ...treatmentsData.approved_fungicides.map((f) => {
        const product = f?.product ? String(f.product) : 'Fungicide';
        const dosage = f?.dosage ? ` — ${f.dosage}` : '';
        const frequency = f?.frequency ? ` (${f.frequency})` : '';
        const notes = f?.notes ? `: ${f.notes}` : '';
        return `Apply ${product}${dosage}${frequency}${notes}`;
      })
    );
  }
  return normalizeList(steps);
};

const inferRequiresRootRemoval = (diseaseName, info) => {
  const haystack = [
    diseaseName,
    JSON.stringify(info?.symptoms ?? ''),
    JSON.stringify(info?.recommended_treatments ?? ''),
    JSON.stringify(info?.description ?? ''),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  if (diseaseName?.toLowerCase().includes('root rot')) return true;
  return /\broot\b|\broots\b|\brooting\b/.test(haystack);
};

const uniqueMerge = (primary = [], secondary = []) => {
  const seen = new Set();
  const out = [];
  for (const item of [...primary, ...secondary]) {
    const key = String(item).trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(String(item).trim());
  }
  return out;
};

const classifyStep = (step) => {
  const t = String(step || '').toLowerCase();
  const isRoot = /\broot\b|\broots\b/.test(t);
  const isCutRemove = /\bcut\b|\bprune\b|\bremove\b|\btrim\b|\bdispose\b|\binfected parts\b|\binfected\b/.test(t);
  return { isRoot, isCutRemove };
};

const isCurrentUserAdmin = () => {
  try {
    const raw = localStorage.getItem('pitayaUser');
    if (!raw) return false;
    const user = JSON.parse(raw);
    return user?.isAdmin === true || String(user?.Role || '').toLowerCase() === 'admin';
  } catch {
    return false;
  }
};

const Library = () => {
  const [diseases, setDiseases] = useState({});
  const [filteredDiseases, setFilteredDiseases] = useState({});
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDiseaseName, setSelectedDiseaseName] = useState(null);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('all');
  const [language, setLanguage] = useState('en');
  const [additionalImages, setAdditionalImages] = useState([]);
  const [showImagesModal, setShowImagesModal] = useState(false);
  const [loadingImages, setLoadingImages] = useState(false);
  const [overrides, setOverrides] = useState({});
  const [adminOpen, setAdminOpen] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [confirmMessage, setConfirmMessage] = useState('');
  const [adminDraft, setAdminDraft] = useState({
    diseaseName: '',
    descriptionText: '',
    symptomsText: '',
    causesText: '',
    preventionText: '',
    treatmentSteps: [''],
    requiresRootRemoval: false,
    severity_level: 'medium',
  });

  const isAdminUser = useMemo(() => isCurrentUserAdmin(), []);
  const location = useLocation();
  const canEditLibrary = isAdminUser && location.pathname.startsWith('/admin');
  // Keep the non-admin fallback reference stable so filtering does not re-run
  // indefinitely after it updates filteredDiseases.
  const activeOverrides = canEditLibrary ? overrides : EMPTY_OVERRIDES;

  const navigate = useNavigate();

  useEffect(() => {
    fetchDiseases();
    fetchUserPreferences();
  }, []);

  useEffect(() => {
    if (!canEditLibrary) return;
    try {
      const raw = localStorage.getItem(OVERRIDES_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') setOverrides(parsed);
    } catch {
      // ignore
    }
  }, [canEditLibrary]);

  useEffect(() => {
    if (!canEditLibrary) return;
    try {
      localStorage.setItem(OVERRIDES_STORAGE_KEY, JSON.stringify(overrides));
    } catch {
      // ignore
    }
  }, [canEditLibrary, overrides]);

  useEffect(() => {
    filterDiseases();
  }, [searchTerm, diseases, severityFilter, activeOverrides]);

  const effectiveDisease = useMemo(() => {
    if (!selectedDiseaseName) return null;
    const base = diseases?.[selectedDiseaseName];
    if (!base) return null;
    const o = activeOverrides?.[selectedDiseaseName] || {};
    const severity_level = getLibrarySeverity(selectedDiseaseName, o.severity_level || base.severity_level);
    const requiresRootRemoval =
      typeof o.requiresRootRemoval === 'boolean'
        ? o.requiresRootRemoval
        : typeof base.requires_root_removal === 'boolean'
          ? base.requires_root_removal
          : inferRequiresRootRemoval(selectedDiseaseName, base);

    return {
      name: selectedDiseaseName,
      ...base,
      severity_level,
      requiresRootRemoval,
      _admin: {
        descriptionText: o.descriptionText || '',
        symptomsText: o.symptomsText || '',
        causesText: o.causesText || '',
        preventionText: o.preventionText || '',
        treatmentSteps: Array.isArray(o.treatmentSteps) ? o.treatmentSteps : null,
      },
    };
  }, [diseases, activeOverrides, selectedDiseaseName]);

  const motionCard = {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.25, ease: 'easeOut' },
  };

  const fetchAdditionalImages = async (diseaseName) => {
    setLoadingImages(true);
    setAdditionalImages(galleryImagesFor(diseaseName));
    setShowImagesModal(true);
    setLoadingImages(false);
  };

  const openAdminEditor = (disease) => {
    if (!canEditLibrary) return;
    const o = overrides?.[disease.name] || {};
    const descriptionSource = getTranslatedText(disease.name, 'description', disease.description || '');
    const symptomsSource = getTranslatedText(disease.name, 'symptoms', disease.symptoms || []);
    const causesSource = getTranslatedText(disease.name, 'causes', disease.causes || []);
    const preventionSource = getTranslatedText(disease.name, 'prevention_methods', disease.prevention_methods || []);
    const treatmentsData = language === 'tagalog'
      ? getTranslatedText(disease.name, 'recommended_treatments', disease.recommended_treatments)
      : disease.recommended_treatments;

    const baseSteps = flattenRecommendedTreatmentsToSteps(treatmentsData);
    const steps = Array.isArray(o.treatmentSteps) && o.treatmentSteps.length
      ? o.treatmentSteps
      : baseSteps.length
        ? baseSteps
        : [''];

    setAdminDraft({
      diseaseName: disease.name,
      descriptionText: o.descriptionText || toMultilineText(descriptionSource),
      symptomsText: o.symptomsText || toMultilineText(symptomsSource),
      causesText: o.causesText || toMultilineText(causesSource),
      preventionText: o.preventionText || toMultilineText(preventionSource),
      treatmentSteps: steps,
      requiresRootRemoval:
        typeof o.requiresRootRemoval === 'boolean'
          ? o.requiresRootRemoval
          : Boolean(disease.requiresRootRemoval),
      severity_level: (o.severity_level || disease.severity_level || 'medium').toLowerCase(),
    });
    // Show confirmation dialog instead of opening directly
    setConfirmMessage(`Open admin editor for "${disease.name}"? This will allow you to edit all library details.`);
    setConfirmAction(() => () => {
      setAdminOpen(true);
      setShowConfirmDialog(false);
    });
    setShowConfirmDialog(true);
  };

  const saveAdminDraft = () => {
    if (!canEditLibrary) return;
    const name = adminDraft.diseaseName;
    if (!name) return;
    // Show confirmation dialog instead of saving directly
    setConfirmMessage(`Save changes for "${name}"? This will update the library information locally.`);
    setConfirmAction(() => () => {
      setOverrides((prev) => ({
        ...prev,
        [name]: {
          ...prev[name],
          descriptionText: String(adminDraft.descriptionText || ''),
          symptomsText: String(adminDraft.symptomsText || ''),
          causesText: String(adminDraft.causesText || ''),
          preventionText: String(adminDraft.preventionText || ''),
          treatmentSteps: normalizeList(adminDraft.treatmentSteps),
          requiresRootRemoval: Boolean(adminDraft.requiresRootRemoval),
          severity_level: String(adminDraft.severity_level || 'medium').toLowerCase(),
          updatedAt: Date.now(),
        },
      }));
      setAdminOpen(false);
      setShowConfirmDialog(false);
    });
    setShowConfirmDialog(true);
  };

  const resetAdminOverrides = (diseaseName) => {
    if (!canEditLibrary) return;
    // Show confirmation dialog instead of resetting directly
    setConfirmMessage(`Reset all changes for "${diseaseName}"? This will restore original treatment information and cannot be undone.`);
    setConfirmAction(() => () => {
      setOverrides((prev) => {
        const next = { ...prev };
        delete next[diseaseName];
        return next;
      });
      setAdminOpen(false);
      setShowConfirmDialog(false);
    });
    setShowConfirmDialog(true);
  };

  const cancelAction = () => {
    setShowConfirmDialog(false);
    setConfirmAction(null);
    setConfirmMessage('');
  };

  const fetchUserPreferences = async () => {
    try {
      const response = await fetch('/api/user/preferences');
      const data = await response.json();
      if (data.success) {
        const preferredLanguage = data.data.preferred_language;
        setLanguage(preferredLanguage);
      }
    } catch (error) {
      console.error('Error fetching user preferences:', error);
    }
  };

  const toggleLanguage = async (targetLanguage) => {
    try {
      // Update user preference
      await fetch('/api/user/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preferred_language: targetLanguage })
      });
      
      setLanguage(targetLanguage);
      localStorage.setItem('language', targetLanguage);
    } catch (error) {
      console.error('Error updating language preference:', error);
    }
  };

  const getTranslatedText = (diseaseName, field, originalText) => {
    if (language !== 'tagalog') {
      return originalText;
    }

    const reviewedTranslation = TAGALOG_DISEASE_CONTENT[diseaseName]?.[field];
    if (reviewedTranslation) return reviewedTranslation;
    
    // Get the disease data
    const disease = diseases[diseaseName];
    if (!disease) {
      console.log(`No disease data found for ${diseaseName}, returning original`);
      return originalText;
    }
    
    // Map field names to Tagalog field names
    const tagalogFieldMap = {
      'description': 'description_tagalog',
      'symptoms': 'symptoms_tagalog',
      'prevention_methods': 'prevention_methods_tagalog',
      'recommended_treatments': 'recommended_treatments_tagalog',
      'causes': 'causes_tagalog'
    };
    
    const tagalogField = tagalogFieldMap[field];
    if (!tagalogField) {
      console.log(`No Tagalog field mapping for ${field}, returning original`);
      return originalText;
    }
    
    // Get the Tagalog translation
    let translation = disease[tagalogField];
    if (translation && typeof translation === 'string' && translation !== null && translation.trim() !== '') {
      // Check if it's a JSON string that needs parsing
      if (translation.startsWith('{') || translation.startsWith('[')) {
        try {
          translation = JSON.parse(translation);
        } catch (e) {
          console.log(`Failed to parse JSON for ${diseaseName} ${field}:`, e);
          // Return original if parsing fails
          return originalText;
        }
      }
      console.log(`Translation found for ${diseaseName} ${field}:`, translation);
      return translation;
    } else if (translation && typeof translation === 'object') {
      // If it's already an object, return it directly
      console.log(`Translation found for ${diseaseName} ${field}:`, translation);
      return translation;
    }
    
    // If no translation found, return original
    console.log(`No translation found for ${diseaseName} ${field}, returning original`);
    return originalText;
  };

  const fetchDiseases = async () => {
    try {
      const response = await fetch('/api/library/');
      const data = await response.json();
      
      // Handle the comprehensive disease library API response
      const diseasesData = data.data || [];
      
      // Convert array to object format for easier access
      const diseasesObject = {};
      diseasesData.forEach(disease => {
        diseasesObject[disease.name] = disease;
      });
      
      setDiseases(diseasesObject);
      setFilteredDiseases(diseasesObject);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching diseases:', error);
      setDiseases({});
      setFilteredDiseases({});
      setLoading(false);
    }
  };
  
  // Helper function for deep search in objects
  const searchInObject = (obj, searchTerm) => {
    if (!obj || typeof obj !== 'object') return false;
    
    const term = searchTerm.toLowerCase();
    return Object.values(obj).some(value => {
      if (Array.isArray(value)) {
        return value.some(item => 
          typeof item === 'string' && item.toLowerCase().includes(term)
        );
      } else if (typeof value === 'string') {
        return value.toLowerCase().includes(term);
      }
      return false;
    });
  };

  const filterDiseases = () => {
    let filtered = { ...diseases };

    // Filter by severity
    if (severityFilter !== 'all') {
      filtered = Object.fromEntries(
        Object.entries(filtered).filter(([_, info]) => 
          getLibrarySeverity(_, activeOverrides?.[_]?.severity_level || info.severity_level) === severityFilter.toLowerCase()
        )
      );
    }

    // Filter by search term
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = Object.fromEntries(
        Object.entries(filtered).filter(([name, info]) => {
          const adminSteps = activeOverrides?.[name]?.treatmentSteps || [];
          const adminStepsText = Array.isArray(adminSteps) ? adminSteps.join(' ') : '';
          const adminDescription = String(activeOverrides?.[name]?.descriptionText || '');
          const adminSymptoms = String(activeOverrides?.[name]?.symptomsText || '');
          const adminCauses = String(activeOverrides?.[name]?.causesText || '');
          const adminPrevention = String(activeOverrides?.[name]?.preventionText || '');
          return (
            name.toLowerCase().includes(term) ||
            searchInObject(info.symptoms, term) ||
            searchInObject(info.causes, term) ||
            searchInObject(info.prevention_methods, term) ||
            searchInObject(info.recommended_treatments, term) ||
            adminStepsText.toLowerCase().includes(term) ||
            adminDescription.toLowerCase().includes(term) ||
            adminSymptoms.toLowerCase().includes(term) ||
            adminCauses.toLowerCase().includes(term) ||
            adminPrevention.toLowerCase().includes(term)
          );
        })
      );
    }

    setFilteredDiseases(filtered);
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high': return 'bg-red-100 text-red-800 border-red-300';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'low': return 'bg-green-100 text-green-800 border-green-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'high': return <AlertTriangle className="w-4 h-4" />;
      case 'medium': return <AlertTriangle className="w-4 h-4" />;
      case 'low': return <AlertTriangle className="w-4 h-4" />;
      default: return <AlertTriangle className="w-4 h-4" />;
    }
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleDateString();
  };

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
      <div className="mb-6 sm:mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => (window.history.length > 1 ? navigate(-1) : navigate(isAdminUser ? '/admin/dashboard' : '/app/dashboard'))}
              className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow transition-all"
              aria-label="Back"
            >
              <ArrowLeft className="w-5 h-5 text-pitaya-primary" />
            </button>
            <BookOpen className="w-6 h-6 sm:w-8 sm:h-8 text-pitaya-primary dark:text-pitaya-mint" />
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">Disease Library</h1>
          </div>
          
          {/* Language Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 dark:text-gray-300">Language:</span>
            <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1 border border-gray-200 dark:border-gray-600">
              <button
                onClick={() => toggleLanguage('en')}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                  language === 'en' 
                    ? 'bg-white dark:bg-gray-600 text-pitaya-primary dark:text-white shadow-sm dark:shadow-lg' 
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'
                }`}
              >
                English
              </button>
              <button
                onClick={() => toggleLanguage('tagalog')}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                  language === 'tagalog' 
                    ? 'bg-white dark:bg-gray-600 text-pitaya-primary dark:text-white shadow-sm dark:shadow-lg' 
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'
                }`}
              >
                Tagalog
              </button>
            </div>
          </div>
        </div>
        <p className="text-gray-600 dark:text-gray-300">
          {language === 'tagalog'
            ? 'Komprehensibong impormasyon tungkol sa mga sakit ng dragon fruit at kaugnayan nito sa awtomatikong pagtukoy'
            : 'Comprehensive information about dragon fruit diseases with automatic detection linking'}
        </p>
      </div>

      {/* Search and Filters */}
      <div className="mb-6 space-y-4">
        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-100 w-5 h-5" />
          <input
            type="text"
            placeholder={language === 'tagalog' ? 'Maghanap ng sakit...' : 'Search diseases...'}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-pitaya-mint focus:border-transparent bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400"
          />
        </div>

        {/* Severity Filter */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {language === 'tagalog' ? 'Filter ayon sa Severidad:' : 'Filter by Severity:'}
          </span>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSeverityFilter('all')}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                severityFilter === 'all'
                  ? 'bg-pitaya-primary text-white dark:bg-pitaya-dark-mint dark:text-white'
                  : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
            >
              {language === 'tagalog' ? 'Lahat' : 'All'}
            </button>
            <button
              onClick={() => setSeverityFilter('high')}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                severityFilter === 'high'
                  ? 'bg-red-600 text-white dark:bg-red-700 dark:text-white'
                  : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
            >
              {language === 'tagalog' ? 'Mataas' : 'High'}
            </button>
            <button
              onClick={() => setSeverityFilter('medium')}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                severityFilter === 'medium'
                  ? 'bg-yellow-600 text-white dark:bg-yellow-700 dark:text-white'
                  : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
            >
              {language === 'tagalog' ? 'Katamtaman' : 'Medium'}
            </button>
            <button
              onClick={() => setSeverityFilter('low')}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                severityFilter === 'low'
                  ? 'bg-green-600 text-white dark:bg-green-700 dark:text-white'
                  : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
            >
              {language === 'tagalog' ? 'Mababa' : 'Low'}
            </button>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-4 sm:mb-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-pitaya-primary dark:text-pitaya-mint" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Total Diseases</span>
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">{Object.keys(diseases || {}).length}</div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">High Severity</span>
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">
            {Object.entries(diseases || {}).filter(([name, d]) => getLibrarySeverity(name, d.severity_level) === 'high').length}
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Medium Severity</span>
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">
            {Object.entries(diseases || {}).filter(([name, d]) => getLibrarySeverity(name, d.severity_level) === 'medium').length}
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Low Severity</span>
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">
            {Object.entries(diseases || {}).filter(([name, d]) => getLibrarySeverity(name, d.severity_level) === 'low').length}
          </div>
        </div>
      </div>

      {/* Disease List */}
      <motion.div layout className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {Object.entries(filteredDiseases || {}).map(([name, info]) => {
          if (!info || !name) return null;
          const o = activeOverrides?.[name] || {};
          const effectiveSeverity = getLibrarySeverity(name, o.severity_level || info.severity_level);
          const requiresRootRemoval =
            typeof o.requiresRootRemoval === 'boolean'
              ? o.requiresRootRemoval
              : typeof info.requires_root_removal === 'boolean'
                ? info.requires_root_removal
                : inferRequiresRootRemoval(name, info);

          return (
          <motion.div
            key={name}
            layout
            {...motionCard}
            className="bg-white dark:bg-gray-800 rounded-2xl shadow-card border border-gray-200 dark:border-gray-700 hover:shadow-card-hover transition-all cursor-pointer overflow-hidden hover:border-pitaya-light dark:hover:border-pitaya-dark-mint flex flex-col h-full"
            onClick={() => {
              setSelectedDiseaseName(name);
              setAdminOpen(false);
            }}
          >
            {/* Disease Image */}
            <div className="h-48 bg-gray-100 dark:bg-gray-700 relative overflow-hidden flex-shrink-0">
              {diseaseImages[name] ? (
                <img
                  src={diseaseImages[name]}
                  alt={name}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'flex';
                  }}
                />
              ) : null}
              {/* Fallback placeholder */}
              <div className="w-full h-full flex items-center justify-center bg-gray-200 dark:bg-gray-600" style={{ display: diseaseImages[name] ? 'none' : 'flex' }}>
                <BookOpen className="w-12 h-12 text-gray-400 dark:text-gray-500" />
              </div>
              {/* Severity Badge */}
              <div className="absolute top-3 right-3">
                <div className={`flex items-center gap-1 px-2 py-1 rounded-full border text-xs font-medium ${getSeverityColor(effectiveSeverity)}`}>
                  {getSeverityIcon(effectiveSeverity)}
                  <span>{effectiveSeverity?.toUpperCase()}</span>
                </div>
              </div>
            </div>

            <div className="p-6 flex flex-col flex-1">
              {/* Disease Header */}
              <div className="mb-4">
                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{name}</h3>
              </div>

              {/* Disease Description */}
              <div className="mb-4">
                <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-2">
                  {String(activeOverrides?.[name]?.descriptionText || '').trim() || getTranslatedText(name, 'description', info.description || 'No description available')}
                </p>
              </div>

              {/* Detection Info */}
              {info.detection_count > 0 && (
                <div className="bg-pitaya-pale/60 dark:bg-pitaya-dark-pale/40 rounded-xl p-3 mb-4 border border-pitaya-leaf/15">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-pitaya-deep dark:text-gray-100 font-medium">{language === 'tagalog' ? 'Kasaysayan ng Pagtukoy' : 'Detection History'}</span>
                    <span className="text-pitaya-primary dark:text-pitaya-mint">{info.detection_count} times</span>
                  </div>
                  <div className="text-xs text-pitaya-primary/80 dark:text-pitaya-mint/90 mt-1">
                    Last detected: {formatDate(info.last_detected)}
                  </div>
                </div>
              )}

              {(requiresRootRemoval || effectiveSeverity === 'high') && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {effectiveSeverity === 'high' && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border bg-red-50 text-red-700 border-red-200">
                      <span aria-hidden>⚠️</span>
                      Immediate action required
                    </span>
                  )}
                  {requiresRootRemoval && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border bg-red-50 text-red-700 border-red-200">
                      <span aria-hidden>✂️</span>
                      Root removal protocol
                    </span>
                  )}
                </div>
              )}

              {/* Quick Info */}
              <div className="space-y-3 flex-1">
                <div>
                  <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {language === 'tagalog' ? 'Mga Pangunahing Sintomas' : 'Key Symptoms'}
                  </h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                    {(() => {
                      const adminSymptomsText = String(activeOverrides?.[name]?.symptomsText || '').trim();
                      if (adminSymptomsText) {
                        const lines = normalizeList(adminSymptomsText);
                        return lines.slice(0, 2).join('. ') ||
                               (language === 'tagalog' ? 'Walang sintomas na available' : 'No symptoms available');
                      }

                      const symptoms = getTranslatedText(name, 'symptoms', info.symptoms);
                      if (symptoms && typeof symptoms === 'object' && !Array.isArray(symptoms)) {
                        const visibleSigns = symptoms.visible_signs || [];
                        return visibleSigns.slice(0, 2).join('. ') ||
                               (language === 'tagalog' ? 'Walang sintomas na available' : 'No symptoms available');
                      } else if (Array.isArray(symptoms)) {
                        return symptoms.slice(0, 2).join('. ') ||
                               (language === 'tagalog' ? 'Walang sintomas na available' : 'No symptoms available');
                      } else {
                        return language === 'tagalog' ? 'Walang sintomas na available' : 'No symptoms available';
                      }
                    })()}
                  </p>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {language === 'tagalog' ? 'Pag-iwas' : 'Prevention'}
                  </h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                    {(() => {
                      const adminPreventionText = String(activeOverrides?.[name]?.preventionText || '').trim();
                      if (adminPreventionText) {
                        const lines = normalizeList(adminPreventionText);
                        return lines.slice(0, 2).join('. ') ||
                               (language === 'tagalog' ? 'Walang paraan sa pag-iwas' : 'No prevention methods available');
                      }

                      const prevention = getTranslatedText(name, 'prevention_methods', info.prevention_methods);
                      if (prevention && typeof prevention === 'object' && !Array.isArray(prevention)) {
                        const farmSanitation = prevention.farm_sanitation || [];
                        return farmSanitation.slice(0, 2).join('. ') ||
                               (language === 'tagalog' ? 'Walang paraan sa pag-iwas' : 'No prevention methods available');
                      } else if (Array.isArray(prevention)) {
                        return prevention.slice(0, 2).join('. ') ||
                               (language === 'tagalog' ? 'Walang paraan sa pag-iwas' : 'No prevention methods available');
                      } else if (typeof prevention === 'string' && prevention.trim()) {
                        return prevention;
                      } else {
                        return language === 'tagalog' ? 'Walang paraan sa pag-iwas' : 'No prevention methods available';
                      }
                    })()}
                  </p>
                </div>
              </div>

              {/* View Details Button */}
              <button className="mt-4 w-full bg-pitaya-primary text-white py-2.5 px-4 rounded-xl hover:bg-pitaya-leaf transition-colors text-sm font-semibold min-h-[44px]">
                {language === 'tagalog' ? 'Tingnan ang Buong Detalye' : 'View Full Details'}
              </button>
            </div>
          </motion.div>
        );
        })}
      </motion.div>

      {/* No Results */}
      {Object.keys(filteredDiseases).length === 0 && (
        <div className="text-center py-12">
          <BookOpen className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">{language === 'tagalog' ? 'Walang nahanap na sakit' : 'No diseases found'}</h3>
          <p className="text-gray-600 dark:text-gray-300">{language === 'tagalog' ? 'Subukang baguhin ang paghahanap o mga filter' : 'Try adjusting your search or filters'}</p>
        </div>
      )}

      {/* Disease Detail Modal */}
      {effectiveDisease && (
        <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-gray-900/80 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-gray-700">
            {/* Disease Image */}
            <div className="h-64 bg-gray-100 dark:bg-gray-700 relative overflow-hidden">
              {diseaseImages[effectiveDisease.name] ? (
                <img
                  src={diseaseImages[effectiveDisease.name]}
                  alt={effectiveDisease.name}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'flex';
                  }}
                />
              ) : null}
              {/* Fallback placeholder */}
              <div className="w-full h-full flex items-center justify-center bg-gray-200 dark:bg-gray-600" style={{ display: diseaseImages[effectiveDisease.name] ? 'none' : 'flex' }}>
                <BookOpen className="w-12 h-12 text-gray-400 dark:text-gray-500" />
              </div>
              {/* More Pictures Button */}
              <button
                onClick={() => fetchAdditionalImages(effectiveDisease.name)}
                disabled={loadingImages}
                className="absolute bottom-4 right-4 bg-green-600 text-white px-3 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 text-sm shadow-lg"
              >
                {loadingImages ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Images className="h-4 w-4" />
                )}
                <span>{language === 'tagalog' ? 'Higit pang Larawan' : 'More Pictures'}</span>
              </button>
              {/* Close button overlay */}
              <button
                onClick={() => {
                  setSelectedDiseaseName(null);
                  setAdminOpen(false);
                }}
                className="absolute top-4 right-4 bg-white/90 dark:bg-gray-700/90 backdrop-blur-sm rounded-full p-2 hover:bg-white dark:hover:bg-gray-600 transition-colors text-gray-900 dark:text-gray-100"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6">
              {/* Modal Header */}
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">{effectiveDisease.name}</h2>
                <div className="flex flex-wrap items-center gap-2">
                  <div className={`inline-flex items-center gap-1 px-3 py-1 rounded-full border text-sm font-medium ${getSeverityColor(effectiveDisease.severity_level)}`}>
                    {getSeverityIcon(effectiveDisease.severity_level)}
                    <span>{language === 'tagalog' ? `${effectiveDisease.severity_level?.toUpperCase()} NA KALUBHAAN` : `${effectiveDisease.severity_level?.toUpperCase()} SEVERITY`}</span>
                  </div>
                  {canEditLibrary && (
                    <button
                      type="button"
                      onClick={() => openAdminEditor(effectiveDisease)}
                      className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-pitaya-leaf/40 bg-pitaya-bg/60 text-pitaya-deep hover:bg-pitaya-bg transition-colors text-sm font-semibold"
                    >
                      Edit Library
                    </button>
                  )}
                </div>
              </div>

              {/* Critical banners */}
              {(effectiveDisease.severity_level === 'high' || effectiveDisease.requiresRootRemoval) && (
                <div className="space-y-3 mb-6">
                  {effectiveDisease.severity_level === 'high' && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-800">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="w-5 h-5 mt-0.5" />
                        <div>
                          <p className="font-semibold">Immediate action required</p>
                          <p className="text-sm mt-0.5">This disease is marked as high severity. Act quickly to limit spread and damage.</p>
                        </div>
                      </div>
                    </div>
                  )}
                  {effectiveDisease.requiresRootRemoval && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-800">
                      <div className="flex items-start gap-3">
                        <Scissors className="w-5 h-5 mt-0.5" />
                        <div>
                          <p className="font-semibold">Root removal required</p>
                          <p className="text-sm mt-0.5">👉 {ROOT_REMOVAL_MESSAGE}</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Detection History */}
              {effectiveDisease.detection_count > 0 && (
                <div className="bg-pitaya-pale/60 dark:bg-pitaya-dark-pale/40 rounded-2xl p-4 mb-6 border border-pitaya-leaf/15">
                  <h3 className="text-lg font-semibold text-pitaya-deep dark:text-gray-100 mb-2">{language === 'tagalog' ? 'Kasaysayan ng Pagtukoy' : 'Detection History'}</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-pitaya-primary dark:text-pitaya-mint">Total Detections:</span>
                      <span className="text-pitaya-deep dark:text-gray-100 font-medium ml-2">{effectiveDisease.detection_count}</span>
                    </div>
                    <div>
                      <span className="text-pitaya-primary dark:text-pitaya-mint">Last Detected:</span>
                      <span className="text-pitaya-deep dark:text-gray-100 font-medium ml-2">
                        {formatDate(effectiveDisease.last_detected)}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Disease Description */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  {language === 'tagalog' ? 'Deskripsyon ng Sakit' : 'Disease Description'}
                </h3>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                  {String(effectiveDisease._admin?.descriptionText || '').trim() || getTranslatedText(effectiveDisease.name, 'description', effectiveDisease.description || 'No description available')}
                </p>
              </div>

              {/* Detailed Information */}
              <div className="space-y-6">
                {/* Symptoms */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
                    {language === 'tagalog' ? 'Mga Sintomas' : 'Symptoms'}
                  </h3>
                  <div className="space-y-4">
                    {(() => {
                      const adminSymptoms = effectiveDisease._admin?.symptomsText;
                      if (adminSymptoms && adminSymptoms.trim()) {
                        const items = normalizeList(adminSymptoms);
                        return (
                          <ul className="space-y-2">
                            {items.map((symptom, index) => (
                              <li key={index} className="flex items-start gap-2">
                                <span className="text-pitaya-primary mt-1">•</span>
                                <span className="text-gray-700 dark:text-gray-300">{symptom}</span>
                              </li>
                            ))}
                          </ul>
                        );
                      }

                      const symptomsData = language === 'tagalog'
                        ? getTranslatedText(effectiveDisease.name, 'symptoms', effectiveDisease.symptoms)
                        : effectiveDisease.symptoms;
                      
                      return symptomsData && typeof symptomsData === 'object' ? (
                        <>
                          {symptomsData.visible_signs && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Mga Nakikitang Tanda' : 'Visible Signs'}
                              </h4>
                              <ul className="space-y-1">
                                {symptomsData.visible_signs.map((sign, index) => (
                                  <li key={`visible-${index}`} className="flex items-start gap-2">
                                    <span className="text-red-500 dark:text-red-400 mt-1">•</span>
                                    <span className="text-gray-700 dark:text-gray-300">
                                      {typeof sign === 'string' ? sign : sign}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {symptomsData.color_changes && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Mga Pagbabago sa Kulay' : 'Color Changes'}
                              </h4>
                              <ul className="space-y-1">
                                {symptomsData.color_changes.map((change, index) => (
                                  <li key={`color-${index}`} className="flex items-start gap-2">
                                    <span className="text-orange-500 dark:text-orange-400 mt-1">•</span>
                                    <span className="text-gray-700 dark:text-gray-300">
                                      {typeof change === 'string' ? change : change}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {symptomsData.lesions && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Mga Lesyon' : 'Lesions'}
                              </h4>
                              <p className="text-gray-700 dark:text-gray-300">
                                {typeof symptomsData.lesions === 'string' ? symptomsData.lesions : symptomsData.lesions}
                              </p>
                            </div>
                          )}
                          {symptomsData.rotting && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Pagkabulok' : 'Rotting'}
                              </h4>
                              <p className="text-gray-700 dark:text-gray-300">
                                {typeof symptomsData.rotting === 'string' ? symptomsData.rotting : symptomsData.rotting}
                              </p>
                            </div>
                          )}
                          {symptomsData.abnormal_growth && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Hindi Karaniwang Paglago' : 'Abnormal Growth'}
                              </h4>
                              <p className="text-gray-700 dark:text-gray-300">
                                {typeof symptomsData.abnormal_growth === 'string' ? symptomsData.abnormal_growth : symptomsData.abnormal_growth}
                              </p>
                            </div>
                          )}
                        </>
                      ) : (
                        <ul className="space-y-2">
                          {Array.isArray(symptomsData) ? symptomsData.map((symptom, index) => (
                            <li key={index} className="flex items-start gap-2">
                              <span className="text-red-500 mt-1">•</span>
                              <span className="text-gray-700 dark:text-gray-300">
                                {typeof symptom === 'string' ? symptom : symptom}
                              </span>
                            </li>
                          )) : (
                            <li className="text-gray-500 dark:text-gray-400">{language === 'tagalog' ? 'Walong impormasyon tungkol sa sintomas' : 'No symptoms information available'}</li>
                          )}
                        </ul>
                      );
                    })()}
                  </div>
                </div>

                {/* Causes */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
                    {language === 'tagalog' ? 'Mga Dahilan' : 'Causes'}
                  </h3>
                  <div className="space-y-4">
                    {(() => {
                      const adminCauses = String(effectiveDisease._admin?.causesText || '').trim();
                      if (adminCauses) {
                        const items = normalizeList(adminCauses);
                        return (
                          <ul className="space-y-2">
                            {items.map((cause, index) => (
                              <li key={index} className="flex items-start gap-2">
                                <span className="text-green-500 mt-1">•</span>
                                <span className="text-gray-700 dark:text-gray-300">{cause}</span>
                              </li>
                            ))}
                          </ul>
                        );
                      }

                      const causesData = language === 'tagalog'
                        ? getTranslatedText(effectiveDisease.name, 'causes', effectiveDisease.causes)
                        : effectiveDisease.causes;
                      
                      return causesData && typeof causesData === 'object' ? (
                        <>
                          {causesData.pathogen_type && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Uri ng Pathogen' : 'Pathogen Type'}
                              </h4>
                              <p className="text-gray-700 dark:text-gray-300">
                                {typeof causesData.pathogen_type === 'string' ? causesData.pathogen_type : causesData.pathogen_type}
                              </p>
                            </div>
                          )}
                          {causesData.causal_organism && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Sanhi ng Organismo' : 'Causal Organism'}
                              </h4>
                              <p className="text-gray-700 dark:text-gray-300">
                                {typeof causesData.causal_organism === 'string' ? causesData.causal_organism : causesData.causal_organism}
                              </p>
                            </div>
                          )}
                          {causesData.environmental_factors && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Mga Dahilang Pangkapaligiran' : 'Environmental Factors'}
                              </h4>
                              <ul className="space-y-1">
                                {causesData.environmental_factors.map((factor, index) => (
                                  <li key={`env-${index}`} className="flex items-start gap-2">
                                    <span className="text-green-500 mt-1">•</span>
                                    <span className="text-gray-700 dark:text-gray-300">
                                      {typeof factor === 'string' ? factor : factor}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {causesData.spread_methods && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Paraan ng Pagkalat' : 'Spread Methods'}
                              </h4>
                              <ul className="space-y-1">
                                {causesData.spread_methods.map((method, index) => (
                                  <li key={`spread-${index}`} className="flex items-start gap-2">
                                    <span className="text-pitaya-primary mt-1">•</span>
                                    <span className="text-gray-700 dark:text-gray-300">
                                      {typeof method === 'string' ? method : method}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </>
                      ) : (
                        <ul className="space-y-2">
                          {Array.isArray(causesData) ? causesData.map((cause, index) => (
                            <li key={index} className="flex items-start gap-2">
                              <span className="text-green-500 mt-1">•</span>
                              <span className="text-gray-700 dark:text-gray-300">
                                {typeof cause === 'string' ? cause : cause}
                              </span>
                            </li>
                          )) : (
                            <li className="text-gray-500 dark:text-gray-400">{language === 'tagalog' ? 'Walong impormasyon tungkol sa mga dahilan' : 'No causes information available'}</li>
                          )}
                        </ul>
                      );
                    })()}
                  </div>
                </div>

                {/* Treatment */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">{language === 'tagalog' ? 'Paggamot' : 'Treatment'}</h3>
                  <div className="space-y-4">
                    {(() => {
                      const treatmentsData = language === 'tagalog'
                        ? getTranslatedText(effectiveDisease.name, 'recommended_treatments', effectiveDisease.recommended_treatments)
                        : effectiveDisease.recommended_treatments;

                      const adminSteps = activeOverrides?.[effectiveDisease.name]?.treatmentSteps;
                      const baseSteps = flattenRecommendedTreatmentsToSteps(treatmentsData);
                      const stepsFromAdmin = Array.isArray(adminSteps) && adminSteps.length ? adminSteps : [];

                      const protocol = effectiveDisease.requiresRootRemoval ? ROOT_REMOVAL_PROTOCOL_STEPS : [];
                      const merged = uniqueMerge(protocol, stepsFromAdmin.length ? stepsFromAdmin : baseSteps);

                      if (!merged.length) {
                        return (
                          <p className="text-gray-500 dark:text-gray-400">
                            {language === 'tagalog' ? 'Walong impormasyon tungkol sa paggamot' : 'No treatment information available'}
                          </p>
                        );
                      }

                      return (
                        <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white/60 dark:bg-gray-800/40 p-4">
                          <h4 className="text-md font-semibold text-gray-900 dark:text-gray-100 mb-3">
                            {language === 'tagalog' ? 'Mga Hakbang sa Paggamot' : 'Step-by-step treatment'}
                          </h4>
                          <ol className="space-y-2">
                            {merged.map((step, index) => {
                              const { isRoot, isCutRemove } = classifyStep(step);
                              const highlight = isRoot || isCutRemove;
                              const icon = isRoot ? '⚠️' : isCutRemove ? '✂️' : '🪴';
                              const classes = highlight
                                ? isRoot
                                  ? 'border-red-200 bg-red-50 text-red-900'
                                  : 'border-amber-200 bg-amber-50 text-amber-900'
                                : 'border-gray-200 bg-white/70 dark:bg-gray-800/50 text-gray-800 dark:text-gray-200';

                              return (
                                <li key={`${index}-${step}`} className={`rounded-xl border px-3 py-2 ${classes}`}>
                                  <div className="flex items-start gap-3">
                                    <span className="mt-0.5 text-sm" aria-hidden>
                                      {icon}
                                    </span>
                                    <div className="flex-1">
                                      <p className="text-sm font-medium">
                                        <span className="mr-2 opacity-70">{index + 1}.</span>
                                        {step}
                                      </p>
                                    </div>
                                  </div>
                                </li>
                              );
                            })}
                          </ol>
                        </div>
                      );
                    })()}
                  </div>
                </div>

                {/* Admin Editor */}
                <AnimatePresence>
                  {canEditLibrary && adminOpen && adminDraft.diseaseName === effectiveDisease.name && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 10 }}
                      transition={{ duration: 0.2, ease: 'easeOut' }}
                      className="rounded-2xl border border-pitaya-leaf/20 bg-pitaya-bg/60 dark:bg-gray-900/30 p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Admin: Edit Library Content</h3>
                          <p className="text-sm text-gray-600 dark:text-gray-300">You can edit description, symptoms, causes, prevention, and treatment. Changes are saved locally in this browser.</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setAdminOpen(false)}
                          className="p-2 rounded-xl hover:bg-white/60 dark:hover:bg-gray-800/60 transition-colors"
                          aria-label="Close admin editor"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>

                      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200">Disease name</label>
                          <input
                            value={adminDraft.diseaseName}
                            disabled
                            className="mt-2 w-full rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-4 py-3 text-gray-700 dark:text-gray-200"
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200">Severity level</label>
                          <select
                            value={adminDraft.severity_level}
                            onChange={(e) => setAdminDraft((d) => ({ ...d, severity_level: e.target.value }))}
                            className="mt-2 w-full rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 text-gray-900 dark:text-gray-100"
                          >
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                          </select>
                        </div>

                        <div className="sm:col-span-2">
                          <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200">
                            Description
                          </label>
                          <textarea
                            value={adminDraft.descriptionText}
                            onChange={(e) => setAdminDraft((d) => ({ ...d, descriptionText: e.target.value }))}
                            placeholder="Disease description"
                            className="mt-2 w-full min-h-[90px] rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 text-gray-900 dark:text-gray-100"
                          />
                        </div>

                        <div className="sm:col-span-2">
                          <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200">
                            Symptoms
                          </label>
                          <textarea
                            value={adminDraft.symptomsText}
                            onChange={(e) => setAdminDraft((d) => ({ ...d, symptomsText: e.target.value }))}
                            placeholder="One symptom per line"
                            className="mt-2 w-full min-h-[110px] rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 text-gray-900 dark:text-gray-100"
                          />
                        </div>

                        <div className="sm:col-span-2">
                          <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200">
                            Causes
                          </label>
                          <textarea
                            value={adminDraft.causesText}
                            onChange={(e) => setAdminDraft((d) => ({ ...d, causesText: e.target.value }))}
                            placeholder="One cause per line"
                            className="mt-2 w-full min-h-[100px] rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 text-gray-900 dark:text-gray-100"
                          />
                        </div>

                        <div className="sm:col-span-2">
                          <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200">
                            Prevention
                          </label>
                          <textarea
                            value={adminDraft.preventionText}
                            onChange={(e) => setAdminDraft((d) => ({ ...d, preventionText: e.target.value }))}
                            placeholder="One prevention step per line"
                            className="mt-2 w-full min-h-[100px] rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 text-gray-900 dark:text-gray-100"
                          />
                        </div>

                        <div className="sm:col-span-2">
                          <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200">Treatment steps</label>
                          <div className="mt-2 space-y-2">
                            {adminDraft.treatmentSteps.map((step, idx) => (
                              <div key={idx} className="flex items-center gap-2">
                                <input
                                  value={step}
                                  onChange={(e) =>
                                    setAdminDraft((d) => {
                                      const next = [...d.treatmentSteps];
                                      next[idx] = e.target.value;
                                      return { ...d, treatmentSteps: next };
                                    })
                                  }
                                  className="flex-1 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 text-gray-900 dark:text-gray-100"
                                  placeholder={`Step ${idx + 1}`}
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    const stepText = adminDraft.treatmentSteps[idx] || `Step ${idx + 1}`;
                                    setConfirmMessage(`Delete "${stepText}"? This will remove this treatment step.`);
                                    setConfirmAction(() => () => {
                                      setAdminDraft((d) => ({
                                        ...d,
                                        treatmentSteps: d.treatmentSteps.filter((_, i) => i !== idx),
                                      }));
                                      setShowConfirmDialog(false);
                                    });
                                    setShowConfirmDialog(true);
                                  }}
                                  className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl border border-gray-200 dark:border-gray-700 hover:bg-white/60 dark:hover:bg-gray-700/60 transition-colors"
                                  aria-label="Remove step"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            ))}

                            <button
                              type="button"
                              onClick={() => setAdminDraft((d) => ({ ...d, treatmentSteps: [...d.treatmentSteps, ''] }))}
                              className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-pitaya-bg/60 dark:hover:bg-gray-700 transition-colors text-sm font-semibold"
                            >
                              <Plus className="w-4 h-4" />
                              Add step
                            </button>
                          </div>
                        </div>

                        <div className="sm:col-span-2">
                          <label className="inline-flex items-center gap-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
                            <input
                              type="checkbox"
                              checked={adminDraft.requiresRootRemoval}
                              onChange={(e) => setAdminDraft((d) => ({ ...d, requiresRootRemoval: e.target.checked }))}
                              className="w-4 h-4"
                            />
                            Requires root removal
                          </label>
                        </div>
                      </div>

                      <div className="mt-4 flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-end">
                        <button
                          type="button"
                          onClick={() => resetAdminOverrides(effectiveDisease.name)}
                          className="inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm font-semibold"
                        >
                          Reset
                        </button>
                        <button
                          type="button"
                          onClick={saveAdminDraft}
                          className="inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-pitaya-primary text-white hover:bg-pitaya-leaf transition-colors text-sm font-semibold"
                        >
                          <Save className="w-4 h-4" />
                          Save
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Prevention */}
                {(() => {
                      const adminPrevention = String(effectiveDisease._admin?.preventionText || '').trim();
                      if (adminPrevention) {
                        const items = normalizeList(adminPrevention);
                        return (
                          <ul className="space-y-2">
                            {items.map((prevention, index) => (
                              <li key={index} className="flex items-start gap-2">
                                <span className="text-pitaya-primary mt-1">•</span>
                                <span className="text-gray-700 dark:text-gray-300">{prevention}</span>
                              </li>
                            ))}
                          </ul>
                        );
                      }

                      const preventionData = language === 'tagalog' 
                        ? getTranslatedText(effectiveDisease.name, 'prevention_methods', effectiveDisease.prevention_methods)
                        : effectiveDisease.prevention_methods;
                      
                      return preventionData && typeof preventionData === 'object' ? (
                        <>
                          {preventionData.farm_sanitation && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Mga Paraan ng Paglilinis sa Bukid' : 'Farm Sanitation'}
                              </h4>
                              <ul className="space-y-1">
                                {preventionData.farm_sanitation.map((practice, index) => (
                                  <li key={`farm-${index}`} className="flex items-start gap-2">
                                    <span className="text-pitaya-primary mt-1">•</span>
                                    <span className="text-gray-700 dark:text-gray-300">{practice}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {preventionData.drainage_spacing && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Pananatilihin ang Sapat na Pagitan' : 'Drainage & Spacing'}
                              </h4>
                              <ul className="space-y-1">
                                {preventionData.drainage_spacing.map((practice, index) => (
                                  <li key={`drainage-${index}`} className="flex items-start gap-2">
                                    <span className="text-green-500 mt-1">•</span>
                                    <span className="text-gray-700 dark:text-gray-300">{practice}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {preventionData.cultural_practices && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Mga Kultural na Gawain' : 'Cultural Practices'}
                              </h4>
                              <ul className="space-y-1">
                                {preventionData.cultural_practices.map((practice, index) => (
                                  <li key={`cultural-${index}`} className="flex items-start gap-2">
                                    <span className="text-purple-500 mt-1">•</span>
                                    <span className="text-gray-700 dark:text-gray-300">{practice}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {preventionData.preventive_spraying && (
                            <div>
                              <h4 className="text-md font-medium text-gray-800 dark:text-gray-200 mb-2">
                                {language === 'tagalog' ? 'Pang-iwas na Pagsaspray' : 'Preventive Spraying'}
                              </h4>
                              <ul className="space-y-1">
                                {preventionData.preventive_spraying.map((practice, index) => (
                                  <li key={`spray-${index}`} className="flex items-start gap-2">
                                    <span className="text-orange-500 mt-1">•</span>
                                    <span className="text-gray-700 dark:text-gray-300">{practice}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </>
                      ) : (
                        <ul className="space-y-2">
                          {Array.isArray(preventionData) ? preventionData.map((prevention, index) => (
                            <li key={index} className="flex items-start gap-2">
                              <span className="text-pitaya-primary mt-1">•</span>
                              <span className="text-gray-700 dark:text-gray-300">{prevention}</span>
                            </li>
                          )) : (
                            <li className="text-gray-500 dark:text-gray-400">{language === 'tagalog' ? 'Walong impormasyon tungkol sa pag-iwas' : 'No prevention information available'}</li>
                          )}
                        </ul>
                      );
                    })()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Additional Images Modal */}
      {showImagesModal && (() => {
        return (
        <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-gray-900/80 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden border border-gray-200 dark:border-gray-700 relative">
            {/* Fixed close button outside of scrollable content */}
            <button
              onClick={() => {
                setShowImagesModal(false);
              }}
              className="fixed top-8 right-8 z-[70] p-3 rounded-full bg-red-600 hover:bg-red-700 text-white shadow-xl transition-all duration-200 hover:scale-110"
              aria-label="Close modal"
              style={{ position: 'fixed' }}
            >
              <X className="h-6 w-6" />
            </button>
            
            <div className="flex items-center justify-between p-6 pr-16 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                {language === 'tagalog' ? 'Karagdagang Larawan' : 'Additional Images'} - {effectiveDisease?.name || selectedDiseaseName}
              </h2>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
              {loadingImages ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-pitaya-primary mr-3" />
                  <p className="text-gray-600 dark:text-gray-300">{language === 'tagalog' ? 'Naglo-load ng karagdagang larawan...' : 'Loading additional images...'}</p>
                </div>
              ) : additionalImages.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {additionalImages.map((image, index) => (
                    <div key={index} className="relative group">
                      <img
                        src={image}
                        alt={`${effectiveDisease?.name || selectedDiseaseName} - Image ${index + 1}`}
                        className="w-full h-48 object-cover rounded-lg border border-gray-200 group-hover:border-pitaya-mint transition-colors"
                        onError={(e) => {
                          e.target.src = '/placeholder-disease.jpg';
                        }}
                      />
                      <div className="absolute bottom-2 right-2 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
                        {index + 1}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Images className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">{language === 'tagalog' ? 'Walang Karagdagang Larawan' : 'No Additional Images'}</h3>
                  <p className="text-gray-600 dark:text-gray-300">{language === 'tagalog' ? 'Walang nahanap na karagdagang larawan para sa sakit na ito.' : 'No additional images found for this disease.'}</p>
                </div>
              )}
            </div>
          </div>
        </div>
        );
      })()}

      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-[60]">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-md w-full shadow-2xl">
            <div className="p-6">
              <div className="flex items-start gap-4 mb-4">
                <div className="flex-shrink-0 w-12 h-12 bg-yellow-100 dark:bg-yellow-900/30 rounded-full flex items-center justify-center">
                  <AlertTriangle className="w-6 h-6 text-yellow-600 dark:text-yellow-400" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">Confirm Action</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                    {confirmMessage}
                  </p>
                </div>
              </div>
              
              <div className="flex gap-3">
                <button
                  onClick={cancelAction}
                  className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={() => confirmAction && confirmAction()}
                  className="flex-1 px-4 py-2 rounded-lg bg-pitaya-primary hover:bg-pitaya-leaf text-white font-semibold transition-colors"
                >
                  Confirm
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Library;
