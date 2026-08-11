import sqlite3
DB='pitaya_database.db'
conn=sqlite3.connect(DB)
c=conn.cursor()
c.execute("SELECT DetectionID, image_path FROM disease_detections WHERE image_path IS NULL OR image_path = '' ORDER BY DateTime DESC")
rows=c.fetchall()
print('Null image_path count:', len(rows))
for r in rows[:50]:
    print(r)
conn.close()
