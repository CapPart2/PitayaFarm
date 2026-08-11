import sqlite3
conn=sqlite3.connect('pitaya_database.db')
cur=conn.cursor()
cur.execute("SELECT UserID, Username, Email, FirstName, LastName, Status FROM users WHERE Email = ?", ('robabarintos@gmail.com',))
print('Matches for robabarintos@gmail.com:', cur.fetchall())
cur.execute("SELECT UserID, Username, Email FROM users WHERE Username = ?", ('robabarintos',))
print('Matches for username robabarintos:', cur.fetchall())
conn.close()
