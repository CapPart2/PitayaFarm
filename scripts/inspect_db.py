import sqlite3, json, os
DB='pitaya_database.db'
print('DB exists:', os.path.exists(DB))
if not os.path.exists(DB):
    print('Database not found')
    raise SystemExit(1)
conn=sqlite3.connect(DB)
c=conn.cursor()
try:
    c.execute("PRAGMA table_info(disease_detections)")
    cols = [r[1] for r in c.fetchall()]
    print('Columns:', cols)
    # Build a select list that exists in this DB
    wanted = ["DetectionID", "DetectionID", "image_path", "ImagePath", "location", "DateTime"]
    select_cols = [cname for cname in wanted if cname in cols]
    if not select_cols:
        select_cols = cols[:6]
    q = f"SELECT {', '.join(select_cols)} FROM disease_detections ORDER BY DateTime DESC LIMIT 50"
    c.execute(q)
    rows = c.fetchall()
    print(json.dumps({"select": select_cols, "rows": rows}, ensure_ascii=False, indent=2))
except Exception as e:
    print('Error querying DB:', e)
finally:
    conn.close()
