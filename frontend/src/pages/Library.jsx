import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { libraryApi } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Library() {
  const [diseases, setDiseases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [plantPart, setPlantPart] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDiseases = async () => {
      try {
        setLoading(true);
        const data = await libraryApi.getDiseases(searchTerm, plantPart);
        setDiseases(Array.isArray(data) ? data : []);
        setError(null);
      } catch (err) {
        console.error('Error fetching diseases:', err);
        setError('Failed to load diseases. Please try again later.');
        setDiseases([]);
      } finally {
        setLoading(false);
      }
    };

    const debounceTimer = setTimeout(() => {
      fetchDiseases();
    }, 300);

    return () => clearTimeout(debounceTimer);
  }, [searchTerm, plantPart]);

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="container mx-auto px-4 py-8 text-gray-900 dark:text-gray-100">
      <h1 className="text-3xl font-bold mb-6">Disease Library</h1>
      
      {/* Search and Filter */}
      <div className="mb-8 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="search" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Search Diseases
          </label>
          <input
            type="text"
            id="search"
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            placeholder="Search by name, symptoms, or causes..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="plantPart" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Filter by Plant Part
          </label>
          <select
            id="plantPart"
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            value={plantPart}
            onChange={(e) => setPlantPart(e.target.value)}
          >
            <option value="">All Parts</option>
            <option value="leaf">Leaf</option>
            <option value="stem">Stem</option>
            <option value="root">Root</option>
            <option value="fruit">Fruit</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {diseases.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 dark:text-gray-400 text-lg">No diseases found. Try adjusting your search criteria.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {diseases.map((disease) => (
            <div key={disease.id} className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow border border-gray-200 dark:border-gray-700">
              {disease.image_url && (
                <div className="h-48 bg-gray-100 dark:bg-gray-700 overflow-hidden">
                  <img
                    src={disease.image_url}
                    alt={disease.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.src = 'https://via.placeholder.com/300x200?text=No+Image';
                    }}
                  />
                </div>
              )}
              <div className="p-4">
                <h2 className="text-xl font-semibold mb-2 text-gray-900 dark:text-gray-100">{disease.name}</h2>
                <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">
                  <span className="font-medium">Affected Part:</span> {disease.affected_part}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-300 mb-4 line-clamp-2">
                  {disease.symptoms}
                </p>
                <div className="flex justify-between items-center">
                  <span className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                    {disease.affected_part}
                  </span>
                  <Link
                    to={`/library/${disease.name}`}
                    className="text-blue-600 hover:text-blue-800 font-medium text-sm"
                  >
                    View Details →
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
