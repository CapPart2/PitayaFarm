/**
 * Mock disease detection result – ready for API: POST image → { diseaseName, confidence, severity, ... }
 */
export function mockDetectDisease() {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        diseaseName: 'Anthracnose',
        confidence: 91.4,
        severity: 'high', // 'low' | 'medium' | 'high'
        affectedPart: 'Leaf',
        symptoms: 'Dark lesions on leaves and stems; sunken spots that may develop pink spore masses in wet conditions.',
        recommendation: 'Remove infected tissue; apply recommended fungicide; improve air circulation.',
      })
    }, 1500)
  })
}
