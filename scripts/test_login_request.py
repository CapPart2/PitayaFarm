import requests
resp = requests.post('http://localhost:5000/api/auth/login', json={'email':'robabarintos@gmail.com','password':'robrob12'})
print(resp.status_code)
print(resp.text)
