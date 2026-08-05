/**
 * Mock dashboard data – structure ready for API integration.
 * Replace with: fetch('/api/dashboard/') or your Django REST endpoint.
 */

export const mockKpis = {
  totalPlants: 1240,
  healthyPlants: 1080,
  diseasedPlants: 160,
  predictedYieldKg: 3420,
}

export const mockMonthlyYield = [
  { month: 'Jan', yield: 2800 },
  { month: 'Feb', yield: 2950 },
  { month: 'Mar', yield: 3100 },
  { month: 'Apr', yield: 3250 },
  { month: 'May', yield: 3180 },
  { month: 'Jun', yield: 3320 },
  { month: 'Jul', yield: 3400 },
  { month: 'Aug', yield: 3380 },
  { month: 'Sep', yield: 3450 },
  { month: 'Oct', yield: 3420 },
]

export const mockDiseaseOccurrence = [
  { name: 'Anthracnose', count: 42 },
  { name: 'Stem Rot', count: 28 },
  { name: 'Black Spot', count: 24 },
  { name: 'Brown Spot', count: 18 },
  { name: 'Root Rot', count: 15 },
  { name: 'White Spot', count: 12 },
  { name: 'Stem Canker', count: 11 },
  { name: 'Twig Blight', count: 6 },
  { name: 'Soft Rot', count: 4 },
]

export const mockDiseaseDistribution = [
  { name: 'Anthracnose', value: 42, fill: '#2f6a21' },
  { name: 'Stem Rot', value: 28, fill: '#3c7b2b' },
  { name: 'Black Spot', value: 24, fill: '#4d9c3d' },
  { name: 'Brown Spot', value: 18, fill: '#6bb854' },
  { name: 'Root Rot', value: 15, fill: '#8b7355' },
  { name: 'Others', value: 33, fill: '#d4c4b0' },
]

export const mockAlerts = [
  { id: 1, disease: 'Anthracnose', confidence: 94.2, severity: 'high', date: '2025-01-30T14:32:00' },
  { id: 2, disease: 'Stem Rot', confidence: 87.1, severity: 'high', date: '2025-01-30T11:20:00' },
  { id: 3, disease: 'Black Spot', confidence: 78.5, severity: 'medium', date: '2025-01-29T16:45:00' },
  { id: 4, disease: 'Brown Spot', confidence: 72.0, severity: 'medium', date: '2025-01-29T09:10:00' },
  { id: 5, disease: 'White Spot', confidence: 65.3, severity: 'low', date: '2025-01-28T13:00:00' },
]
