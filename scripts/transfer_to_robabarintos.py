#!/usr/bin/env python3
import sqlite3
import hashlib
import os

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pitaya_database.db')

print('Using DB:', DB)
conn = sqlite3.connect(DB)
cur = conn.cursor()

username = 'robabarintos'
email = 'robabarintos@gmail.com'
password = 'robrob12'

pw_hash = hashlib.sha256(password.encode()).hexdigest()

# Ensure user exists
cur.execute('SELECT UserID, Username, Email FROM users WHERE Username = ? OR Email = ?', (username, email))
row = cur.fetchone()
if row:
    user_id = row[0]
    print('Found existing user id:', user_id)
    # Try to claim the desired email. If another user has it, move that user's email to a backup
    try:
        cur.execute('SELECT UserID FROM users WHERE Email = ? AND UserID != ?', (email, user_id))
        conflict = cur.fetchone()
        if conflict:
            conflict_id = conflict[0]
            # move conflicting email to a backup to free it
            backup_email = f"migrated_{conflict_id}_{int(os.path.getmtime(DB))}@example.com"
            cur.execute('UPDATE users SET Email = ? WHERE UserID = ?', (backup_email, conflict_id))
            conn.commit()
        cur.execute('UPDATE users SET Email = ?, PasswordHash = ?, Status = ? WHERE UserID = ?', (email, pw_hash, 'active', user_id))
        conn.commit()
    except sqlite3.IntegrityError:
        # As a fallback, only update password and status
        cur.execute('UPDATE users SET PasswordHash = ?, Status = ? WHERE UserID = ?', (pw_hash, 'active', user_id))
        conn.commit()
else:
    cur.execute('INSERT INTO users (Username, PasswordHash, Email, FirstName, LastName, Role, Status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (username, pw_hash, email, 'Rob', 'Barintos', 'user', 'active'))
    user_id = cur.lastrowid
    conn.commit()
    print('Created user id:', user_id)

# Identify candidate source identifiers
# Look for other users with same email or username (should be none)
cur.execute('SELECT UserID FROM users WHERE (Username = ? OR Email = ?) AND UserID != ?', (username, email, user_id))
other_users = [r[0] for r in cur.fetchall()]

print('Other matching user ids:', other_users)

# If none found, we'll transfer records attributed to 'default_user' or NULL/empty
# Count before
cur.execute("SELECT COUNT(*) FROM disease_detections WHERE user_id IS NULL OR user_id = '' OR lower(user_id) = 'default_user'")
count_dd_before = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM yield_predictions WHERE user_id IS NULL OR user_id = '' OR lower(user_id) = 'default_user'")
count_yp_before = cur.fetchone()[0]

print('Disease detections to consider (default/empty):', count_dd_before)
print('Yield predictions to consider (default/empty):', count_yp_before)

# Perform updates
if other_users:
    # transfer from those numeric ids AND default/empty entries
    placeholders = ','.join('?' for _ in other_users)
    sql_dd = f"UPDATE disease_detections SET user_id = ? WHERE (user_id IS NULL OR user_id = '' OR lower(user_id) = 'default_user' OR user_id IN ({placeholders}))"
    cur.execute(sql_dd, (str(user_id),) + tuple(str(x) for x in other_users))
    sql_yp = f"UPDATE yield_predictions SET user_id = ? WHERE (user_id IS NULL OR user_id = '' OR lower(user_id) = 'default_user' OR user_id IN ({placeholders}))"
    cur.execute(sql_yp, (str(user_id),) + tuple(str(x) for x in other_users))
else:
    cur.execute("UPDATE disease_detections SET user_id = ? WHERE user_id IS NULL OR user_id = '' OR lower(user_id) = 'default_user'", (str(user_id),))
    cur.execute("UPDATE yield_predictions SET user_id = ? WHERE user_id IS NULL OR user_id = '' OR lower(user_id) = 'default_user'", (str(user_id),))
    # Move user_preferences if exists
    cur.execute("SELECT COUNT(*) FROM user_preferences WHERE user_id = 'default_user' OR user_id IS NULL OR user_id = ''")
    pref_count = cur.fetchone()[0]
    if pref_count > 0:
        cur.execute("INSERT OR REPLACE INTO user_preferences (user_id, preferred_language, notification_email, farm_name, email_notifications_enabled, updated_at) SELECT ?, preferred_language, notification_email, farm_name, email_notifications_enabled, updated_at FROM user_preferences WHERE user_id = 'default_user' OR user_id IS NULL OR user_id = ''", (str(user_id),))
        cur.execute("DELETE FROM user_preferences WHERE user_id = 'default_user' OR user_id IS NULL OR user_id = ''")

conn.commit()

# Count after
cur.execute("SELECT COUNT(*) FROM disease_detections WHERE user_id = ?", (str(user_id),))
count_dd_after = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM yield_predictions WHERE user_id = ?", (str(user_id),))
count_yp_after = cur.fetchone()[0]

print('After transfer, disease_detections with new user_id:', count_dd_after)
print('After transfer, yield_predictions with new user_id:', count_yp_after)

# Show user row
cur.execute('SELECT UserID, Username, Email, Role, Status, CreatedAt FROM users WHERE UserID = ?', (user_id,))
print('User row:', cur.fetchone())

conn.commit()
conn.close()
print('Done')
