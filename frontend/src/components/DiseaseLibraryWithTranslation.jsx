import React, { useState, useEffect } from 'react';
import { Book, Globe, CheckCircle, AlertCircle, Loader2, X } from 'lucide-react';

const DiseaseLibraryWithTranslation = () => {
  const [diseases, setDiseases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDisease, setSelectedDisease] = useState(null);
  const [showTranslation, setShowTranslation] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDiseasesWithTranslations();
  }, []);

  const fetchDiseasesWithTranslations = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/library/with-translations');
      const data = await response.json();
      
      if (data.success) {
        setDiseases(data.data.diseases);
      } else {
        setError('Failed to load disease library');
      }
    } catch (error) {
      console.error('Error fetching diseases:', error);
      setError('Error loading disease library');
    } finally {
      setLoading(false);
    }
  };

  const checkTranslationExists = async (diseaseId) => {
    try {
      const response = await fetch(`/api/translate/check/${diseaseId}`);
      const data = await response.json();
      return data.success ? data.data.exists : false;
    } catch (error) {
      console.error('Error checking translation:', error);
      return false;
    }
  };

  const generateTranslation = async (disease) => {
    try {
      setTranslating(true);
      setError(null);

      // Check if translation already exists
      const exists = await checkTranslationExists(disease.DiseaseID);
      if (exists) {
        // Translation exists, just show it
        setShowTranslation(true);
        setTranslating(false);
        return;
      }

      // Generate translation (simulated - in real app, this would call translation API)
      const tagalogTranslation = {
        tagalog_description: `Ang ${disease.DiseaseName} ay isang sakit na nakakaapekto sa pitaya plants.`,
        tagalog_symptoms: `Mga sintomas: pagkakulay ng dahon, mga spots, at paglala.`,
        tagalog_causes: `Dahilan: fungal, bacterial, o viral infection.`,
        tagalog_prevention: `Pag-iwas: proper sanitation at regular inspection.`,
        tagalog_treatment: `Paggamot: appropriate fungicides o treatment methods.`,
        quality_score: 0.95
      };

      // Save translation to database
      const saveResponse = await fetch('/api/translate/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          disease_id: disease.DiseaseID,
          ...tagalogTranslation
        })
      });

      const saveData = await saveResponse.json();
      
      if (saveData.success) {
        // Refresh diseases to get updated translation
        await fetchDiseasesWithTranslations();
        setShowTranslation(true);
      } else {
        setError('Failed to save translation');
      }
    } catch (error) {
      console.error('Error generating translation:', error);
      setError('Error generating translation');
    } finally {
      setTranslating(false);
    }
  };

  const toggleLanguage = () => {
    setShowTranslation(!showTranslation);
  };

  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'high': return 'bg-red-100 text-red-800 border-red-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <span className="ml-2 text-gray-600">Loading disease library...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <AlertCircle className="w-8 h-8 text-red-600" />
        <span className="ml-2 text-red-600">{error}</span>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Disease Library</h1>
        <p className="text-gray-600">Comprehensive information about dragon fruit diseases with Tagalog translations</p>
      </div>

      {/* Disease Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        {diseases.map((disease) => (
          <div
            key={disease.DiseaseID}
            className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow cursor-pointer border border-gray-200"
            onClick={() => setSelectedDisease(disease)}
          >
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold text-gray-900">{disease.DiseaseName}</h3>
                {disease.HasTranslation && (
                  <CheckCircle className="w-5 h-5 text-green-600" title="Translation available" />
                )}
              </div>
              
              <div className="mb-3">
                <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full border ${getSeverityColor(disease.Severity)}`}>
                  {disease.Severity?.toUpperCase() || 'UNKNOWN'}
                </span>
              </div>

              <p className="text-sm text-gray-600 line-clamp-3 mb-3">
                {showTranslation && disease.TagalogDescription 
                  ? disease.TagalogDescription 
                  : disease.Description
                }
              </p>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Book className="w-4 h-4 text-gray-400" />
                  <span className="text-xs text-gray-500">
                    {disease.HasTranslation ? 'Translated' : 'English only'}
                  </span>
                </div>
                
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedDisease(disease);
                    if (!disease.HasTranslation) {
                      generateTranslation(disease);
                    } else {
                      setShowTranslation(!showTranslation);
                    }
                  }}
                  className="flex items-center space-x-1 px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                >
                  <Globe className="w-3 h-3" />
                  <span>{disease.HasTranslation ? 'Toggle' : 'Translate'}</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Disease Detail Modal */}
      {selectedDisease && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 p-6 flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">{selectedDisease.DiseaseName}</h2>
                <div className="flex items-center space-x-4 mt-2">
                  <span className={`inline-block px-3 py-1 text-sm font-medium rounded-full border ${getSeverityColor(selectedDisease.Severity)}`}>
                    {selectedDisease.Severity?.toUpperCase() || 'UNKNOWN'}
                  </span>
                  {selectedDisease.HasTranslation && (
                    <div className="flex items-center space-x-1 text-green-600">
                      <CheckCircle className="w-4 h-4" />
                      <span className="text-sm">Translation Available</span>
                    </div>
                  )}
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                {selectedDisease.HasTranslation && (
                  <button
                    onClick={() => setShowTranslation(!showTranslation)}
                    className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    <Globe className="w-4 h-4" />
                    <span>{showTranslation ? 'English' : 'Tagalog'}</span>
                  </button>
                )}
                
                <button
                  onClick={() => setSelectedDisease(null)}
                  className="p-2 text-gray-500 hover:text-gray-700"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="p-6">
              {/* Description */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Description</h3>
                <p className="text-gray-700 leading-relaxed">
                  {showTranslation && selectedDisease.TagalogDescription 
                    ? selectedDisease.TagalogDescription 
                    : selectedDisease.Description
                  }
                </p>
              </div>

              {/* Symptoms */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Symptoms</h3>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-gray-700 leading-relaxed">
                    {showTranslation && selectedDisease.TagalogSymptoms 
                      ? selectedDisease.TagalogSymptoms 
                      : selectedDisease.Symptoms
                    }
                  </p>
                </div>
              </div>

              {/* Causes */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Causes</h3>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-gray-700 leading-relaxed">
                    {showTranslation && selectedDisease.TagalogCauses 
                      ? selectedDisease.TagalogCauses 
                      : selectedDisease.Causes
                    }
                  </p>
                </div>
              </div>

              {/* Prevention */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Prevention</h3>
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-gray-700 leading-relaxed">
                    {showTranslation && selectedDisease.TagalogPrevention 
                      ? selectedDisease.TagalogPrevention 
                      : selectedDisease.Prevention
                    }
                  </p>
                </div>
              </div>

              {/* Treatment */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Treatment</h3>
                <div className="bg-green-50 rounded-lg p-4">
                  <p className="text-gray-700 leading-relaxed">
                    {showTranslation && selectedDisease.TagalogTreatment 
                      ? selectedDisease.TagalogTreatment 
                      : selectedDisease.Treatment
                  }
                </p>
                </div>
              </div>

              {/* Translation Status */}
              {selectedDisease.QualityScore && (
                <div className="mt-6 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                  <div className="flex items-center space-x-2">
                    <AlertCircle className="w-5 h-5 text-yellow-600" />
                    <div>
                      <p className="text-sm font-medium text-yellow-800">Translation Quality Score</p>
                      <p className="text-xs text-yellow-600">
                        {(selectedDisease.QualityScore * 100).toFixed(1)}% accuracy
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Translation Loading Overlay */}
      {translating && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 flex items-center space-x-3">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            <span className="text-gray-700">Generating translation...</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default DiseaseLibraryWithTranslation;
