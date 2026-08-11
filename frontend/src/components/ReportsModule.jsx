import { AlertTriangle, Calendar, Download, Eye, FileText, Filter, Search, Trash2, TrendingUp, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { getPitayaUserScopeHeaders } from '../api/userScope';

const ReportsModule = () => {
  const API_BASE = (import.meta.env.VITE_DASHBOARD_API_BASE_URL || '').replace(/\/$/, '');
  const [reports, setReports] = useState([]);
  const [filteredReports, setFilteredReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('all'); // 'all', 'high', 'medium', 'low'
  const [selectedReport, setSelectedReport] = useState(null);
  const [previewReport, setPreviewReport] = useState(null);
  const [previewContent, setPreviewContent] = useState(null);
  const [previewFormat, setPreviewFormat] = useState('csv');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null); // { id, label } | null
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  useEffect(() => {
    fetchReports();
  }, []);

  useEffect(() => {
    const handler = () => fetchReports();
    window.addEventListener('pitaya:refresh', handler);
    return () => window.removeEventListener('pitaya:refresh', handler);
  }, []);
  useEffect(() => {
    filterReports();
    setCurrentPage(1); // Reset to page 1 when filters change
  }, [reports, searchTerm, filter]);

  const fetchReports = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/dashboard/reports`, {
        headers: getPitayaUserScopeHeaders(),
      });
      const root = await response.json();
      const data = root.data || [];
      
      // Fetch disease information to populate symptoms, causes, and treatment
      let diseases = {};
      try {
        const diseaseResponse = await fetch(`${API_BASE}/api/library/`, {
          headers: getPitayaUserScopeHeaders(),
        });
        if (diseaseResponse.ok) {
          const diseaseData = await diseaseResponse.json();
          const diseaseList = diseaseData.data || [];
          diseases = diseaseList.reduce((acc, item) => {
            const name = item.name || item.disease_name;
            if (name) acc[name] = item;
            return acc;
          }, {});
        }
      } catch (diseaseError) {
        console.warn('Could not fetch disease information:', diseaseError.message);
        // Continue without disease information
      }
      
      // Fallback disease information for common dragon fruit diseases
      const fallbackDiseases = {
        'Anthracnose': {
          symptoms: ['Dark brown to black lesions on stems', 'Sunken spots on fruits', 'Leaf tip burn and yellowing'],
          causes: ['Fungal infection (Colletotrichum gloeosporioides)', 'High humidity and warm temperatures', 'Poor air circulation'],
          treatment: ['Apply approved fungicides', 'Remove infected plant parts', 'Improve air circulation', 'Avoid overhead irrigation']
        },
        'Stem Canker': {
          symptoms: ['Cankers on stems and branches', 'Oozing gum from infected areas', 'Dieback of affected parts'],
          causes: ['Fungal infection (Botryosphaeria spp.)', 'Physical damage to stems', 'Stress conditions'],
          treatment: ['Prune infected branches', 'Apply copper-based fungicides', 'Avoid mechanical damage to stems']
        },
        'White Spot': {
          symptoms: ['White circular spots on leaves', 'Yellowing around spots', 'Leaf drop in severe cases'],
          causes: ['Fungal infection (Pseudocercospora spp.)', 'High humidity', 'Poor plant nutrition'],
          treatment: ['Apply appropriate fungicides', 'Improve air circulation', 'Balance fertilization']
        },
        'Brown Spot': {
          symptoms: ['Brown to black spots on leaves', 'Leaf yellowing and drop', 'Fruit lesions'],
          causes: ['Fungal infection (Alternaria alternata)', 'Leaf wetness', 'Nutrient deficiencies'],
          treatment: ['Apply fungicides', 'Remove affected leaves', 'Ensure proper nutrition']
        },
        'Stem Rot': {
          symptoms: ['Soft, watery rot at stem base', 'Foul odor from infected area', 'Plant wilting and collapse'],
          causes: ['Fungal infection (Fusarium spp.)', 'Poor drainage', 'Overwatering'],
          treatment: ['Improve drainage', 'Reduce watering', 'Apply fungicides to soil', 'Remove infected plants']
        },
        'Root Rot': {
          symptoms: ['Yellowing and wilting of leaves', 'Brown, mushy roots', 'Stunted growth'],
          causes: ['Fungal infection (Pythium spp.)', 'Overwatering', 'Poor drainage'],
          treatment: ['Improve soil drainage', 'Reduce watering frequency', 'Apply fungicides', 'Repot if necessary']
        },
        'Soft Rot': {
          symptoms: ['Watery, soft lesions on fruits', 'Foul odor', 'Rapid decay'],
          causes: ['Bacterial infection (Erwinia spp.)', 'Physical damage to fruit', 'High humidity'],
          treatment: ['Remove infected fruits', 'Improve air circulation', 'Handle fruits carefully']
        },
        'Twig Blight': {
          symptoms: ['Dieback of young shoots', 'Dark lesions on twigs', 'Leaf drop'],
          causes: ['Fungal infection (Phomopsis spp.)', 'Environmental stress', 'Poor pruning practices'],
          treatment: ['Prune infected twigs', 'Apply fungicides', 'Improve plant vigor']
        },
        'Black Spot': {
          symptoms: ['Black circular spots on leaves', 'Yellowing around spots', 'Premature leaf drop'],
          causes: ['Fungal infection (Diplocarpon spp.)', 'High humidity', 'Leaf wetness'],
          treatment: ['Apply fungicides', 'Remove affected leaves', 'Improve air circulation']
        }
      };
      
      // Merge fallback data with API data
      Object.keys(fallbackDiseases).forEach(disease => {
        if (!diseases[disease]) {
          diseases[disease] = fallbackDiseases[disease];
        }
      });
      
      // Group records by session_id to combine multi-disease detections
      const groupedBySession = {};
      data.forEach(d => {
        const sessionId = d.session_id || d.DetectionID?.toString();
        if (!groupedBySession[sessionId]) {
          groupedBySession[sessionId] = [];
        }
        // Normalize image_path field name
        const record = {
          ...d,
          image_path: d.image_path || d.ImagePath || d.filename
        };
        groupedBySession[sessionId].push(record);
      });

      // Define extraction functions to handle different disease data structures
      const getSymptoms = (info) => {
        if (!info) return [];
        if (Array.isArray(info)) return info;
        
        // Handle nested object structure from API
        const symptoms = [];
        
        // Extract from visible_signs array
        if (info.visible_signs) {
          if (Array.isArray(info.visible_signs)) {
            symptoms.push(...info.visible_signs);
          } else if (typeof info.visible_signs === 'string') {
            symptoms.push(info.visible_signs);
          }
        }
        
        // Extract from color_changes array
        if (info.color_changes && Array.isArray(info.color_changes)) {
          symptoms.push(...info.color_changes);
        }
        
        // Extract from lesions if it's a string
        if (info.lesions && typeof info.lesions === 'string') {
          symptoms.push(info.lesions);
        }
        
        // Extract from abnormal_growth if it's a string
        if (info.abnormal_growth && typeof info.abnormal_growth === 'string') {
          symptoms.push(info.abnormal_growth);
        }
        
        // If symptoms is a direct array (fallback structure)
        if (info.symptoms) {
          if (Array.isArray(info.symptoms)) {
            symptoms.push(...info.symptoms);
          } else if (typeof info.symptoms === 'string') {
            symptoms.push(info.symptoms);
          } else if (typeof info.symptoms === 'object') {
            Object.values(info.symptoms).forEach(v => {
              if (typeof v === 'string') symptoms.push(v);
              if (Array.isArray(v)) symptoms.push(...v);
            });
          }
        }
        
        return symptoms.length > 0 ? symptoms : [];
      };
      
      const getCauses = (info) => {
        if (!info) return [];
        if (Array.isArray(info)) return info;
        
        // Handle nested object structure from API
        const causes = [];
        
        // Extract from environmental_factors array
        if (info.environmental_factors && Array.isArray(info.environmental_factors)) {
          causes.push(...info.environmental_factors);
        }
        
        // Extract from spread_methods array
        if (info.spread_methods && Array.isArray(info.spread_methods)) {
          causes.push(...info.spread_methods);
        }
        
        // Extract pathogen_type if it's a string
        if (info.pathogen_type && typeof info.pathogen_type === 'string') {
          causes.push(`Pathogen type: ${info.pathogen_type}`);
        }
        
        // Extract causal_organism if it's a string
        if (info.causal_organism && typeof info.causal_organism === 'string') {
          causes.push(`Causal organism: ${info.causal_organism}`);
        }
        
        // If causes is a direct array (fallback structure)
        if (info.causes) {
          if (Array.isArray(info.causes)) {
            causes.push(...info.causes);
          } else if (typeof info.causes === 'string') {
            causes.push(info.causes);
          } else if (typeof info.causes === 'object') {
            Object.values(info.causes).forEach(v => {
              if (typeof v === 'string') causes.push(v);
              if (Array.isArray(v)) causes.push(...v);
            });
          }
        }
        
        // Handle causal_factors (alternative field name)
        if (info.causal_factors) {
          if (Array.isArray(info.causal_factors)) {
            causes.push(...info.causal_factors);
          } else if (typeof info.causal_factors === 'string') {
            causes.push(info.causal_factors);
          } else if (typeof info.causal_factors === 'object') {
            Object.values(info.causal_factors).forEach(v => {
              if (typeof v === 'string') causes.push(v);
              if (Array.isArray(v)) causes.push(...v);
            });
          }
        }
        
        return causes.length > 0 ? causes : [];
      };
      
      const getTreatment = (info) => {
        if (!info) return [];
        if (Array.isArray(info)) return info;
        
        // Handle nested object structure from API
        const treatments = [];
        
        // Extract from best_practices array
        if (info.best_practices && Array.isArray(info.best_practices)) {
          treatments.push(...info.best_practices);
        }
        
        // Extract from non_chemical_methods array
        if (info.non_chemical_methods && Array.isArray(info.non_chemical_methods)) {
          treatments.push(...info.non_chemical_methods);
        }
        
        // Extract from approved_fungicides array (may contain objects)
        if (info.approved_fungicides && Array.isArray(info.approved_fungicides)) {
          info.approved_fungicides.forEach(fungicide => {
            if (typeof fungicide === 'string') {
              treatments.push(fungicide);
            } else if (typeof fungicide === 'object' && fungicide.product) {
              treatments.push(`${fungicide.product} - ${fungicide.dosage || 'As directed'} (${fungicide.frequency || 'As needed'})${fungicide.notes ? ': ' + fungicide.notes : ''}`);
            }
          });
        }
        
        // If treatment is a direct array (fallback structure)
        if (info.treatment) {
          if (Array.isArray(info.treatment)) {
            treatments.push(...info.treatment);
          } else if (typeof info.treatment === 'string') {
            treatments.push(info.treatment);
          } else if (typeof info.treatment === 'object') {
            Object.values(info.treatment).forEach(v => {
              if (typeof v === 'string') treatments.push(v);
              if (Array.isArray(v)) treatments.push(...v);
            });
          }
        }
        
        // Handle treatment_methods (alternative nested structure)
        if (info.treatment_methods) {
          if (info.treatment_methods.chemical_control) {
            if (Array.isArray(info.treatment_methods.chemical_control)) {
              treatments.push(...info.treatment_methods.chemical_control);
            } else if (typeof info.treatment_methods.chemical_control === 'object') {
              Object.values(info.treatment_methods.chemical_control).forEach(v => {
                if (typeof v === 'string') treatments.push(v);
                if (Array.isArray(v)) treatments.push(...v);
              });
            } else if (typeof info.treatment_methods.chemical_control === 'string') {
              treatments.push(info.treatment_methods.chemical_control);
            }
          }
          if (info.treatment_methods.biological_control) {
            if (Array.isArray(info.treatment_methods.biological_control)) {
              treatments.push(...info.treatment_methods.biological_control);
            } else if (typeof info.treatment_methods.biological_control === 'object') {
              Object.values(info.treatment_methods.biological_control).forEach(v => {
                if (typeof v === 'string') treatments.push(v);
                if (Array.isArray(v)) treatments.push(...v);
              });
            } else if (typeof info.treatment_methods.biological_control === 'string') {
              treatments.push(info.treatment_methods.biological_control);
            }
          }
          if (info.treatment_methods.cultural_practices) {
            if (Array.isArray(info.treatment_methods.cultural_practices)) {
              treatments.push(...info.treatment_methods.cultural_practices);
            } else if (typeof info.treatment_methods.cultural_practices === 'object') {
              Object.values(info.treatment_methods.cultural_practices).forEach(v => {
                if (typeof v === 'string') treatments.push(v);
                if (Array.isArray(v)) treatments.push(...v);
              });
            } else if (typeof info.treatment_methods.cultural_practices === 'string') {
              treatments.push(info.treatment_methods.cultural_practices);
            }
          }
        }
        
        return treatments.length > 0 ? treatments : [];
      };

      const mapped = Object.keys(groupedBySession).map(sessionId => {
        const records = groupedBySession[sessionId];
        const primaryRecord = records[0]; // Use first record as primary
        
        // If multiple records in session, combine them
        if (records.length > 1) {
          const diseaseNames = records.map(r => r.DiseaseType || r.disease_name).join(', ');
          const averageConfidence = records.reduce(
            (sum, r) => sum + (r.Confidence || r.confidence_score || 0),
            0
          ) / records.length;
          const maxSeverity = records.some(r => (r.Severity || r.severity) === 'high') ? 'high' : 
                             records.some(r => (r.Severity || r.severity) === 'medium') ? 'medium' : 'low';
          
          // Aggregate symptoms, causes, and treatment from all diseases
          const allSymptoms = [];
          const allCauses = [];
          const allTreatments = [];
          
          records.forEach(r => {
            const diseaseName = r.DiseaseType || r.disease_name;
            const diseaseInfo = diseases[diseaseName] || {};
            
            // Use the same extraction functions
            allSymptoms.push(...getSymptoms(diseaseInfo));
            allCauses.push(...getCauses(diseaseInfo));
            allTreatments.push(...getTreatment(diseaseInfo));
          });
          
          return {
            id: sessionId,
            timestamp: primaryRecord.DateTime || primaryRecord.detection_time,
            disease_name: diseaseNames,
            severity: maxSeverity,
            confidence: averageConfidence,
            filename: primaryRecord.image_path || primaryRecord.ImagePath || `detection_${primaryRecord.DetectionID || primaryRecord.id}.jpg`,
            location: primaryRecord.Location || primaryRecord.location || 'Unknown',
            symptoms: allSymptoms,
            causes: allCauses,
            treatment: allTreatments,
            isMultiDisease: true,
            diseases: records.map(r => ({
              name: r.DiseaseType || r.disease_name,
              severity: r.Severity || r.severity,
              confidence: r.Confidence || r.confidence_score
            }))
          };
        }
        
        // Single disease record
        const diseaseName = primaryRecord.DiseaseType || primaryRecord.disease_name || 'Unknown';
        const diseaseInfo = diseases[diseaseName] || {};
        
        return {
          id: primaryRecord.DetectionID || primaryRecord.id || Math.random().toString(36).substr(2, 9),
          timestamp: primaryRecord.DateTime || primaryRecord.detection_time,
          disease_name: diseaseName,
          severity: primaryRecord.Severity || primaryRecord.severity || 'medium',
          confidence: typeof (primaryRecord.Confidence || primaryRecord.confidence_score) === 'number' ? (primaryRecord.Confidence || primaryRecord.confidence_score) : 0,
          filename: primaryRecord.image_path || primaryRecord.ImagePath || `detection_${primaryRecord.DetectionID || primaryRecord.id}.jpg`,
          location: primaryRecord.Location || primaryRecord.location || 'Unknown',
          symptoms: getSymptoms(diseaseInfo),
          causes: getCauses(diseaseInfo),
          treatment: getTreatment(diseaseInfo),
          isMultiDisease: false
        };
      });
      // Sanitize mapped reports to ensure no function values are present
      const sanitizeValue = (v) => {
        if (typeof v === 'function') return String(v);
        if (v && Array.isArray(v)) return v.map(sanitizeValue);
        if (v && typeof v === 'object') {
          const o = {};
          Object.keys(v).forEach(k => { o[k] = sanitizeValue(v[k]); });
          return o;
        }
        return v;
      };

      const sanitized = mapped.map(r => sanitizeValue(r));
      setReports(sanitized);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching reports:', error);
      setLoading(false);
    }
  };

  const filterReports = () => {
    let filtered = [...reports];

    // Filter by search term
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(report => 
        report.disease_name.toLowerCase().includes(term) ||
        report.filename.toLowerCase().includes(term) ||
        report.severity.toLowerCase().includes(term)
      );
    }

    // Filter by severity
    if (filter !== 'all') {
      filtered = filtered.filter(report => report.severity === filter);
    }

    // Sort by date (newest first)
    filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    setFilteredReports(filtered);
  };

  const downloadReport = async (reportId, format = 'csv') => {
    try {
      const response = await fetch(`${API_BASE}/api/dashboard/reports/${reportId}/download?format=${format}`, {
        headers: getPitayaUserScopeHeaders(),
      });
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `disease_report_${reportId}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        console.error('Download failed');
      }
    } catch (error) {
      console.error('Error downloading report:', error);
    }
  };

  const previewReportContent = async (reportId, format = 'csv') => {
    try {
      setPreviewLoading(true);
      setPreviewFormat(format);
      
      const response = await fetch(`${API_BASE}/api/dashboard/reports/${reportId}/preview?format=${format}`, {
        headers: getPitayaUserScopeHeaders(),
      });
      const result = await response.json();
      
      if (result.success) {
        setPreviewContent(result.data.content);
        setPreviewReport(reports.find(r => r.id === reportId));
      } else {
        console.error('Preview failed:', result.error);
      }
    } catch (error) {
      console.error('Error previewing report:', error);
    } finally {
      setPreviewLoading(false);
    }
  };

  const deleteReport = async (reportId) => {
    try {
        const response = await fetch(`${API_BASE}/api/dashboard/detections/${reportId}`, {
        method: 'DELETE',
        headers: getPitayaUserScopeHeaders(),
      });
      if (response.ok) {
        setReports(reports.filter(report => report.id !== reportId));
        setTimeout(() => { fetchReports(); }, 500);
      } else {
        fetchReports();
      }
    } catch (error) {
      console.error('Error deleting report:', error);
      fetchReports();
    }
  };

  const askDelete = (id, label) => setConfirmDelete({ id, label });

  const confirmAndDelete = async () => {
    if (!confirmDelete) return;
    await deleteReport(confirmDelete.id);
    setConfirmDelete(null);
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high': return 'bg-red-100 text-red-800 border-red-300';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'low': return 'bg-green-100 text-green-800 border-green-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const getReportStats = () => {
    const total = reports.length;
    const high = reports.filter(r => r.severity === 'high').length;
    const medium = reports.filter(r => r.severity === 'medium').length;
    const low = reports.filter(r => r.severity === 'low').length;
    const avgConfidence = reports.length > 0 
      ? (reports.reduce((sum, r) => sum + r.confidence, 0) / reports.length).toFixed(1)
      : 0;

    return { total, high, medium, low, avgConfidence };
  };

  const stats = getReportStats();

  // Pagination calculations
  const totalPages = Math.ceil(filteredReports.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentReports = filteredReports.slice(startIndex, endIndex);

  const handlePageChange = (page) => {
    setCurrentPage(page);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
        <div className="flex items-center gap-3">
          <FileText className="w-6 h-6 sm:w-8 sm:h-8 text-blue-600 dark:text-blue-400" />
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">Disease Report</h1>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3 sm:gap-4 mb-4 sm:mb-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Total Reports</span>
          </div>
          <p className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">{stats.total}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">High Severity</span>
          </div>
          <p className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">{stats.high}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Medium Severity</span>
          </div>
          <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400 mt-1">{stats.medium}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-green-600 dark:text-green-400" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Low Severity</span>
          </div>
          <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">{stats.low}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Avg Confidence</span>
          </div>
          <p className="text-2xl font-bold text-purple-600 dark:text-purple-400 mt-1">{stats.avgConfidence}%</p>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search by disease name, filename, or severity..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>

          {/* Severity Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            >
              <option value="all">All Severities</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>
      </div>

      {/* Reports Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Date & Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Disease
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Severity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Confidence
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Image
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {currentReports.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center">
                    <FileText className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No reports found</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      {searchTerm || filter !== 'all' ? 'Try adjusting your search or filters' : 'No disease detection reports available yet'}
                    </p>
                  </td>
                </tr>
              ) : (
                currentReports.map((report) => (
                  <tr key={report.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                        {formatDate(report.timestamp)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{report.disease_name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getSeverityColor(report.severity)}`}>
                        {report.severity?.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: `${report.confidence}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{report.confidence.toFixed(1)}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {report.filename && report.filename !== 'detection_image.jpg' ? (
                        <img 
                          src={`${API_BASE}/api/uploads/${report.filename.replace(/\\/g, '/')}`} 
                          alt="Detection" 
                          className="w-12 h-12 object-cover rounded cursor-pointer hover:opacity-80"
                          onClick={() => window.open(`${API_BASE}/api/uploads/${report.filename.replace(/\\/g, '/')}`, '_blank')}
                        />
                      ) : (
                        <span className="text-gray-400">No image</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedReport(report)}
                          className="p-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
                          title="View Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => previewReportContent(report.id, 'csv')}
                          className="p-1 text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded"
                          title="Preview Report"
                        >
                          <FileText className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => askDelete(report.id, `${report.disease_name} — ${report.severity} severity (${new Date(report.timestamp).toLocaleDateString()})`)}
                          className="p-1 text-red-600 hover:text-red-800 hover:bg-red-50 rounded"
                          title="Delete Report"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-sm text-gray-600 dark:text-gray-300">
            Showing {startIndex + 1} to {Math.min(endIndex, filteredReports.length)} of {filteredReports.length} reports
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="px-3 py-1 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
            >
              Previous
            </button>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <button
                  key={page}
                  onClick={() => handlePageChange(page)}
                  className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                    currentPage === page
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                  }`}
                >
                  {page}
                </button>
              ))}
            </div>
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="px-3 py-1 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Report Detail Modal */}
      {selectedReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-gray-900/80 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              {/* Modal Header */}
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Disease Detection Report</h2>
                  <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-300">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-4 h-4" />
                      {formatDate(selectedReport.timestamp)}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getSeverityColor(selectedReport.severity)}`}>
                      {selectedReport.severity?.toUpperCase()}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedReport(null)}
                  className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Detection Image */}
              {selectedReport.filename && selectedReport.filename !== 'detection_image.jpg' && (
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Detection Image</h3>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                    <img
                      src={`${API_BASE}/api/uploads/${selectedReport.filename.replace(/\\/g, '/')}`}
                      alt="Detection"
                      className="w-full max-w-md mx-auto rounded-lg object-cover cursor-pointer hover:opacity-90"
                      onClick={() => window.open(`${API_BASE}/api/uploads/${selectedReport.filename.replace(/\\/g, '/')}`, '_blank')}
                    />
                  </div>
                </div>
              )}

              {/* Report Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Detection Information</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600 dark:text-gray-300">Report ID:</span>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{selectedReport.id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600 dark:text-gray-300">Disease:</span>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{selectedReport.disease_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600 dark:text-gray-300">Confidence:</span>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{selectedReport.confidence.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600 dark:text-gray-300">Image File:</span>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{selectedReport.filename}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Quick Actions</h3>
                  <div className="space-y-2">
                    <button
                      onClick={() => downloadReport(selectedReport.id, 'csv')}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                      <Download className="w-4 h-4" />
                      Download CSV Report
                    </button>
                    <button
                      onClick={() => downloadReport(selectedReport.id, 'pdf')}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-white-600 text-red rounded-lg hover:bg-white-700 transition-colors border border-red-600"
                    >
                      <FileText className="w-4 h-4" />
                      Download PDF Report
                    </button>
                    <button
                      onClick={() => { setSelectedReport(null); askDelete(selectedReport.id, `${selectedReport.disease_name} — ${selectedReport.severity} severity (${new Date(selectedReport.timestamp).toLocaleDateString()})`); }}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete Report
                    </button>
                  </div>
                </div>
              </div>

              {/* Detailed Information */}
              <div className="space-y-6">
                {/* Symptoms */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Symptoms</h3>
                  <ul className="space-y-2">
                    {selectedReport.symptoms?.map((symptom, index) => (
                      <li key={index} className="flex items-start gap-2">
                        <span className="text-red-500 dark:text-red-400 mt-1">•</span>
                        <span className="text-gray-700 dark:text-gray-300">{symptom}</span>
                      </li>
                    )) || <li className="text-gray-500 dark:text-gray-400">No symptoms information available</li>}
                  </ul>
                </div>

                {/* Causes */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Causes</h3>
                  <ul className="space-y-2">
                    {selectedReport.causes?.map((cause, index) => (
                      <li key={index} className="flex items-start gap-2">
                        <span className="text-orange-500 dark:text-orange-400 mt-1">•</span>
                        <span className="text-gray-700 dark:text-gray-300">{cause}</span>
                      </li>
                    )) || <li className="text-gray-500 dark:text-gray-400">No causes information available</li>}
                  </ul>
                </div>

                {/* Treatment */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Recommended Treatment</h3>
                  <ul className="space-y-2">
                    {selectedReport.treatment?.map((treatment, index) => (
                      <li key={index} className="flex items-start gap-2">
                        <span className="text-green-500 dark:text-green-400 mt-1">•</span>
                        <span className="text-gray-700 dark:text-gray-300">{treatment}</span>
                      </li>
                    )) || <li className="text-gray-500 dark:text-gray-400">No treatment information available</li>}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Report Preview Modal */}
      {previewReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-gray-900/80 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  Report Preview
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                  {previewReport.disease_name} - {formatDate(previewReport.timestamp)}
                </p>
              </div>
              <button
                onClick={() => {
                  setPreviewReport(null);
                  setPreviewContent(null);
                }}
                className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-auto p-6">
              {previewLoading ? (
                <div className="flex items-center justify-center h-64">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Format Selection and Actions */}
                  <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Format:</span>
                      <div className="flex gap-2">
                        <button
                          onClick={() => previewReportContent(previewReport.id, 'csv')}
                          className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                            previewFormat === 'csv'
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                          }`}
                        >
                          CSV
                        </button>
                        <button
                          onClick={() => previewReportContent(previewReport.id, 'pdf')}
                          className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                            previewFormat === 'pdf'
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                          }`}
                        >
                          PDF
                        </button>
                      </div>
                    </div>
                    <div className="flex gap-2 ml-auto">
                      <button
                        onClick={() => downloadReport(previewReport.id, previewFormat)}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
                      >
                        <Download className="w-4 h-4" />
                        Download {previewFormat.toUpperCase()}
                      </button>
                    </div>
                  </div>

                  {/* Content Display */}
                  <div className="border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden">
                    {previewFormat === 'csv' ? (
                      <div className="p-4 bg-gray-50 dark:bg-gray-900">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">CSV Content</h3>
                        <pre className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono bg-white dark:bg-gray-800 p-4 rounded border border-gray-200 dark:border-gray-600 max-h-96 overflow-auto">
                          {previewContent || 'Loading CSV content...'}
                        </pre>
                      </div>
                    ) : (
                      <div className="p-4 bg-gray-50 dark:bg-gray-900">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">PDF Content</h3>
                        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-600">
                          {previewContent ? (
                            <iframe
                              src={`data:application/pdf;base64,${previewContent}`}
                              className="w-full h-96 border-0"
                              title="PDF Preview"
                            />
                          ) : (
                            <div className="flex items-center justify-center h-96">
                              <div className="text-gray-500 dark:text-gray-400">Loading PDF content...</div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm Delete Dialog ──────────────────────────── */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[60] animate-in fade-in duration-200">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-md w-full shadow-2xl animate-in slide-in-from-bottom-4 duration-300">
            <div className="p-6">
              {/* Header */}
              <div className="flex items-center gap-4 mb-6">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-red-100 to-red-200 dark:from-red-900/40 dark:to-red-800/30 flex items-center justify-center shrink-0 shadow-sm">
                  <Trash2 className="w-7 h-7 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">Delete Report</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">This action cannot be undone</p>
                </div>
              </div>

              {/* Content Box */}
              <div className="bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-700/50 dark:to-gray-800/50 rounded-xl px-5 py-4 mb-6 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-red-500"></div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">{confirmDelete.label}</p>
                </div>
              </div>

              {/* Warning Message */}
              <div className="flex items-start gap-3 mb-6 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  Deleting this report will permanently remove it from the database. Make sure you have a backup if needed.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => setConfirmDelete(null)}
                  className="flex-1 px-4 py-3 rounded-xl border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-all duration-200 font-semibold"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmAndDelete}
                  className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-semibold transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-red-500/25"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportsModule;
