import requests

base='http://127.0.0.1:5001/api/dashboard'
h={'X-Pitaya-User':'user-11','Content-Type':'application/json'}

r = requests.post(base+'/disease-detection', headers=h, json={
  'disease_type':'Stem_Canker',
  'severity':'medium',
  'confidence':77.7,
  'location':'User Upload'
}, timeout=10)
print('POST disease-detection', r.status_code)

r = requests.post(base+'/yield-prediction', headers=h, json={
  'mature_fruits': 5,
  'location': 'Field A',
  'upload_type': 'image'
}, timeout=10)
print('POST yield-prediction', r.status_code)

r = requests.get(base+'/reports', headers={'X-Pitaya-User':'user-11'}, timeout=10)
print('GET reports', r.status_code)
if r.ok:
  data = (r.json() or {}).get('data', [])
  print('reports_count', len(data))

r = requests.get(base+'/yield-predictions', headers={'X-Pitaya-User':'user-11'}, timeout=10)
print('GET yield-predictions', r.status_code)
if r.ok:
  data = (r.json() or {}).get('data', [])
  print('yield_predictions_count', len(data))
