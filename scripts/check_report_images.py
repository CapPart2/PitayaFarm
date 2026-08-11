import urllib.request, json
reports_url='http://127.0.0.1:5001/api/dashboard/reports'
with urllib.request.urlopen(reports_url) as r:
    data=json.load(r)
reports=data.get('data',[])[:30]
for rep in reports:
    img=rep.get('ImagePath') or rep.get('image_path')
    if not img:
        print(rep.get('DetectionID'),'NO_IMAGE')
        continue
    # normalize
    img = img.replace('\\','/').lstrip('/')
    if img.startswith('uploads/'):
        img = img[len('uploads/'):]
    url=f'http://127.0.0.1:5001/api/uploads/{img}'
    try:
        with urllib.request.urlopen(url) as resp:
            print(rep.get('DetectionID'), resp.status, resp.getheader('Content-Type'), url)
    except Exception as e:
        print(rep.get('DetectionID'),'ERR',e,url)
