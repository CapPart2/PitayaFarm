import os
root='uploads'
if not os.path.exists(root):
    print('uploads dir missing')
    raise SystemExit(1)
count=0
for dirpath, dirs, files in os.walk(root):
    for f in files:
        print(os.path.join(dirpath,f))
        count+=1
        if count>=50:
            break
    if count>=50:
        break
print('total found:',count)
