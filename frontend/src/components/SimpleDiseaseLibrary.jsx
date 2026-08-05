import React, { useState, useEffect } from 'react';
import { Book, Languages, Globe, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

const SimpleDiseaseLibrary = () => {
  const [diseases, setDiseases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDisease, setSelectedDisease] = useState(null);
  const [language, setLanguage] = useState('english');
  const [translating, setTranslating] = useState(false);
  const [translationProgress, setTranslationProgress] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDiseases();
  }, []);

  const fetchDiseases = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/library/');
      const data = await response.json();
      
      if (data.success) {
        setDiseases(data.data);
      } else {
        setError('Failed to load diseases');
      }
    } catch (err) {
      setError('Error connecting to server');
      console.error('Error fetching diseases:', err);
    } finally {
      setLoading(false);
    }
  };

  const translateDisease = async (diseaseName) => {
    try {
      setTranslating(true);
      setTranslationProgress(prev => ({ ...prev, [diseaseName]: 'translating' }));
      
      const response = await fetch('/api/translate/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          diseases: [diseaseName],
          target_language: 'tagalog'
        })
      });

      const result = await response.json();
      
      if (result.success && result.data.successful > 0) {
        setTranslationProgress(prev => ({ ...prev, [diseaseName]: 'completed' }));
        await fetchDiseases();
      } else {
        setTranslationProgress(prev => ({ ...prev, [diseaseName]: 'failed' }));
        setError(`Translation failed for ${diseaseName}`);
      }
    } catch (err) {
      setTranslationProgress(prev => ({ ...prev, [diseaseName]: 'failed' }));
      setError(`Error translating ${diseaseName}: ${err.message}`);
    } finally {
      setTranslating(false);
    }
  };

  const translateAllDiseases = async () => {
    try {
      setTranslating(true);
      setError(null);
      
      const diseaseNames = diseases.map(d => d.name);
      
      const response = await fetch('/api/translate/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          diseases: diseaseNames,
          target_language: 'tagalog'
        })
      });

      const result = await response.json();
      
      if (result.success) {
        const newProgress = {};
        result.data.results.forEach(res => {
          newProgress[res.disease_name] = res.success ? 'completed' : 'failed';
        });
        setTranslationProgress(newProgress);
        await fetchDiseases();
      } else {
        setError('Batch translation failed');
      }
    } catch (err) {
      setError(`Error in batch translation: ${err.message}`);
    } finally {
      setTranslating(false);
    }
  };

  const hasTranslation = (disease) => {
    return disease.has_translation || 
           (disease.description_tagalog && disease.description_tagalog.trim() !== '');
  };

  const getTranslatedContent = (disease) => {
    if (!hasTranslation(disease)) return null;
    
    return {
      description: disease.description_tagalog || disease.description,
      symptoms: disease.symptoms_tagalog || disease.symptoms,
      causes: disease.causes_tagalog || disease.causes,
      prevention: disease.prevention_methods_tagalog || disease.prevention_methods,
      treatment: disease.recommended_treatments_tagalog || disease.recommended_treatments
    };
  };

  const getOriginalContent = (disease) => {
    return {
      description: disease.description,
      symptoms: disease.symptoms,
      causes: disease.causes,
      prevention: disease.prevention_methods,
      treatment: disease.recommended_treatments
    };
  };

  const renderContent = (disease) => {
    const content = language === 'tagalog' && hasTranslation(disease) 
      ? getTranslatedContent(disease) 
      : getOriginalContent(disease);

    return (
      <div className=\"space-y-6\">
        {/* Description */}
        <div className=\"bg-white p-6 rounded-lg border border-gray-200 shadow-sm\">
          <h3 className=\"text-lg font-semibold text-gray-900 mb-3\">Description</h3>
          <p className=\"text-gray-700 leading-relaxed\">{content.description}</p>
        </div>

        {/* Symptoms */}
        <div className=\"bg-white p-6 rounded-lg border border-gray-200 shadow-sm\">
          <h3 className=\"text-lg font-semibold text-gray-900 mb-3\">Symptoms</h3>
          <div className=\"text-gray-700\">
            {typeof content.symptoms === 'object' ? (
              <div className=\"space-y-3\">
                {content.symptoms.visible_signs && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Visible Signs:</h4>
                    <ul className=\"list-disc list-inside space-y-1 ml-4\">
                      {content.symptoms.visible_signs.map((sign, index) => (
                        <li key={index}>{sign}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {content.symptoms.progression && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Progression:</h4>
                    <p>{content.symptoms.progression}</p>
                  </div>
                )}
              </div>
            ) : (
              <p>{content.symptoms}</p>
            )}
          </div>
        </div>

        {/* Causes */}
        <div className=\"bg-white p-6 rounded-lg border border-gray-200 shadow-sm\">
          <h3 className=\"text-lg font-semibold text-gray-900 mb-3\">Causes</h3>
          <div className=\"text-gray-700\">
            {typeof content.causes === 'object' ? (
              <div className=\"space-y-3\">
                {content.causes.pathogen_type && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Pathogen Type:</h4>
                    <p>{content.causes.pathogen_type}</p>
                  </div>
                )}
                {content.causes.causal_organism && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Causal Organism:</h4>
                    <p>{content.causes.causal_organism}</p>
                  </div>
                )}
                {content.causes.environmental_factors && content.causes.environmental_factors.length > 0 && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Environmental Factors:</h4>
                    <ul className=\"list-disc list-inside space-y-1 ml-4\">
                      {content.causes.environmental_factors.map((factor, index) => (
                        <li key={index}>{factor}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p>{content.causes}</p>
            )}
          </div>
        </div>

        {/* Prevention Methods */}
        <div className=\"bg-white p-6 rounded-lg border border-gray-200 shadow-sm\">
          <h3 className=\"text-lg font-semibold text-gray-900 mb-3\">Prevention Methods</h3>
          <div className=\"text-gray-700\">
            {typeof content.prevention === 'object' ? (
              <div className=\"space-y-3\">
                {content.prevention.cultural_practices && content.prevention.cultural_practices.length > 0 && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Cultural Practices:</h4>
                    <ul className=\"list-disc list-inside space-y-1 ml-4\">
                      {content.prevention.cultural_practices.map((practice, index) => (
                        <li key={index}>{practice}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {content.prevention.chemical_control && content.prevention.chemical_control.length > 0 && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Chemical Control:</h4>
                    <ul className=\"list-disc list-inside space-y-1 ml-4\">
                      {content.prevention.chemical_control.map((control, index) => (
                        <li key={index}>{control}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {content.prevention.biological_control && content.prevention.biological_control.length > 0 && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Biological Control:</h4>
                    <ul className=\"list-disc list-inside space-y-1 ml-4\">
                      {content.prevention.biological_control.map((control, index) => (
                        <li key={index}>{control}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p>{content.prevention}</p>
            )}
          </div>
        </div>

        {/* Recommended Treatments */}
        <div className=\"bg-white p-6 rounded-lg border border-gray-200 shadow-sm\">
          <h3 className=\"text-lg font-semibold text-gray-900 mb-3\">Recommended Treatments</h3>
          <div className=\"text-gray-700\">
            {typeof content.treatment === 'object' ? (
              <div className=\"space-y-3\">
                {content.treatment.chemical_treatments && content.treatment.chemical_treatments.length > 0 && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Chemical Treatments:</h4>
                    <ul className=\"list-disc list-inside space-y-1 ml-4\">
                      {content.treatment.chemical_treatments.map((treatment, index) => (
                        <li key={index}>{treatment}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {content.treatment.cultural_treatments && content.treatment.cultural_treatments.length > 0 && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Cultural Treatments:</h4>
                    <ul className=\"list-disc list-inside space-y-1 ml-4\">
                      {content.treatment.cultural_treatments.map((treatment, index) => (
                        <li key={index}>{treatment}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {content.treatment.application_instructions && (
                  <div>
                    <h4 className=\"font-medium text-gray-800 mb-2\">Application Instructions:</h4>
                    <p>{content.treatment.application_instructions}</p>
                  </div>
                )}
              </div>
            ) : (
              <p>{content.treatment}</p>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className=\"min-h-screen bg-gray-50 flex items-center justify-center\">
        <div className=\"text-center\">
          <Loader2 className=\"h-12 w-12 animate-spin text-blue-600 mx-auto mb-4\" />
          <p className=\"text-gray-600\">Loading disease library...</p>
        </div>
      </div>
    );
  }

  return (
    <div className=\"min-h-screen bg-gray-50\">
      {/* Header */}
      <div className=\"bg-white shadow-sm border-b border-gray-200\">
        <div className=\"max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6\">
          <div className=\"flex items-center justify-between\">
            <div className=\"flex items-center space-x-3\">
              <Book className=\"h-8 w-8 text-blue-600\" />
              <h1 className=\"text-2xl font-bold text-gray-900\">Disease Library</h1>
            </div>
            
            {/* Language Toggle */}
            <div className=\"flex items-center space-x-4\">
              <div className=\"flex items-center bg-gray-100 rounded-lg p-1\">
                <button
                  onClick={() => setLanguage('english')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    language === 'english'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <Globe className=\"h-4 w-4 inline mr-2\" />
                  English
                </button>
                <button
                  onClick={() => setLanguage('tagalog')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    language === 'tagalog'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <Languages className=\"h-4 w-4 inline mr-2\" />
                  Tagalog
                </button>
              </div>
              
              {/* Translate All Button */}
              <button
                onClick={translateAllDiseases}
                disabled={translating}
                className=\"bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2\"
              >
                {translating ? (
                  <Loader2 className=\"h-4 w-4 animate-spin\" />
                ) : (
                  <Languages className=\"h-4 w-4\" />
                )}
                <span>{translating ? 'Translating...' : 'Translate All'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className=\"max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6\">
          <div className=\"bg-red-50 border border-red-200 rounded-lg p-4 flex items-center space-x-3\">
            <AlertCircle className=\"h-5 w-5 text-red-600\" />
            <p className=\"text-red-800\">{error}</p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className=\"max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8\">
        <div className=\"grid grid-cols-1 lg:grid-cols-4 gap-8\">
          {/* Disease List */}
          <div className=\"lg:col-span-1\">
            <div className=\"bg-white rounded-lg shadow-sm border border-gray-200\">
              <div className=\"p-4 border-b border-gray-200\">
                <h2 className=\"font-semibold text-gray-900\">Diseases</h2>
              </div>
              <div className=\"max-h-96 overflow-y-auto\">
                {diseases.map((disease) => (
                  <div
                    key={disease.name}
                    onClick={() => setSelectedDisease(disease)}
                    className={`p-4 border-b border-gray-100 cursor-pointer transition-colors hover:bg-gray-50 ${
                      selectedDisease?.name === disease.name ? 'bg-blue-50' : ''
                    }`}
                  >
                    <div className=\"flex items-center justify-between\">
                      <div>
                        <h3 className=\"font-medium text-gray-900\">{disease.name}</h3>
                        <p className=\"text-sm text-gray-500\">{disease.severity_level}</p>
                      </div>
                      <div className=\"flex items-center space-x-2\">
                        {hasTranslation(disease) ? (
                          <CheckCircle className=\"h-5 w-5 text-green-600\" />
                        ) : (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              translateDisease(disease.name);
                            }}
                            disabled={translating}
                            className=\"text-blue-600 hover:text-blue-800 disabled:opacity-50\"
                          >
                            <Languages className=\"h-5 w-5\" />
                          </button>
                        )}
                        {translationProgress[disease.name] === 'translating' && (
                          <Loader2 className=\"h-4 w-4 animate-spin text-blue-600\" />
                        )}
                        {translationProgress[disease.name] === 'completed' && (
                          <CheckCircle className=\"h-4 w-4 text-green-600\" />
                        )}
                        {translationProgress[disease.name] === 'failed' && (
                          <AlertCircle className=\"h-4 w-4 text-red-600\" />
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Disease Details */}
          <div className=\"lg:col-span-3\">
            {selectedDisease ? (
              <div className=\"space-y-6\">
                {/* Disease Header */}
                <div className=\"bg-white rounded-lg shadow-sm border border-gray-200 p-6\">
                  <div className=\"flex items-start justify-between\">
                    <div>
                      <h2 className=\"text-2xl font-bold text-gray-900\">{selectedDisease.name}</h2>
                      <p className=\"text-gray-600 mt-1\">{selectedDisease.scientific_name}</p>
                      <div className=\"mt-3 flex items-center space-x-4\">
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                          selectedDisease.severity_level === 'High' 
                            ? 'bg-red-100 text-red-800'
                            : selectedDisease.severity_level === 'Medium'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {selectedDisease.severity_level} Severity
                        </span>
                        {hasTranslation(selectedDisease) && (
                          <span className=\"inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800\">
                            <Languages className=\"h-4 w-4 mr-1\" />
                            {language === 'tagalog' ? 'Tagalog' : 'English'} Available
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {/* Individual Translate Button */}
                    {!hasTranslation(selectedDisease) && (
                      <button
                        onClick={() => translateDisease(selectedDisease.name)}
                        disabled={translating}
                        className=\"bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2\"
                      >
                        {translationProgress[selectedDisease.name] === 'translating' ? (
                          <Loader2 className=\"h-4 w-4 animate-spin\" />
                        ) : (
                          <Languages className=\"h-4 w-4\" />
                        )}
                        <span>Translate to Tagalog</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Disease Image */}
                {selectedDisease.image_path && (
                  <div className=\"bg-white rounded-lg shadow-sm border border-gray-200 p-6\">
                    <h3 className=\"text-lg font-semibold text-gray-900 mb-4\">Disease Image</h3>
                    <img
                      src={selectedDisease.image_path}
                      alt={selectedDisease.name}
                      className=\"w-full h-64 object-cover rounded-lg\"
                      onError={(e) => {
                        e.target.src = '/placeholder-disease.jpg';
                      }}
                    />
                  </div>
                )}

                {/* Disease Content */}
                {renderContent(selectedDisease)}

                {/* Translation Status */}
                {language === 'tagalog' && hasTranslation(selectedDisease) && (
                  <div className=\"bg-blue-50 border border-blue-200 rounded-lg p-4\">
                    <div className=\"flex items-center space-x-2\">
                      <CheckCircle className=\"h-5 w-5 text-blue-600\" />
                      <p className=\"text-blue-800\">
                        High-quality Tagalog translation available. Context-based translation preserves agricultural and medical terminology accuracy.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className=\"bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center\">
                <Book className=\"h-16 w-16 text-gray-400 mx-auto mb-4\" />
                <h3 className=\"text-lg font-medium text-gray-900 mb-2\">Select a Disease</h3>
                <p className=\"text-gray-600\">Choose a disease from the list to view detailed information and translations.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SimpleDiseaseLibrary;
