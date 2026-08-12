import hashlib
import os
import sqlite3

def reset_admin_user():
    """Reset or create the admin account from Railway environment variables."""
    data_dir = os.environ.get("PITAYA_DATA_DIR", ".")
    db_path = os.path.join(data_dir, "pitaya_database.db")
    password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "")
    if not password or password == "admin123":
        raise SystemExit("Set DEFAULT_ADMIN_PASSWORD to a strong value before resetting admin.")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if users table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        print("Users table does not exist. Creating it...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                UserID INTEGER PRIMARY KEY AUTOINCREMENT,
                Username TEXT NOT NULL UNIQUE,
                PasswordHash TEXT NOT NULL,
                Email TEXT UNIQUE,
                FirstName TEXT,
                LastName TEXT,
                Role TEXT DEFAULT 'user',
                Status TEXT DEFAULT 'active',
                CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                LastLogin TEXT
            )
        """)
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("SELECT UserID FROM users WHERE Username = ?", ("admin",))
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            """
            UPDATE users
            SET PasswordHash = ?, Email = ?, FirstName = ?, LastName = ?, Role = ?, Status = ?
            WHERE Username = ?
            """,
            (password_hash, "admin@pitaya.com", "System", "Administrator", "admin", "active", "admin"),
        )
    else:
        cursor.execute(
            """
            INSERT INTO users (Username, PasswordHash, Email, FirstName, LastName, Role, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            ("admin", password_hash, "admin@pitaya.com", "System", "Administrator", "admin", "active"),
        )
    
    conn.commit()
    
    # Verify the user was created
    cursor.execute("SELECT UserID, Username, Role, Status FROM users WHERE Username = 'admin'")
    user = cursor.fetchone()
    
    if user:
        print("Admin account reset successfully.")
        print(f"UserID: {user[0]}")
        print(f"Username: {user[1]}")
        print(f"Role: {user[2]}")
        print(f"Status: {user[3]}")
        print("Use the Admin Login page with username: admin")
    else:
        print("Failed to create admin user")
    
    conn.close()

if __name__ == "__main__":
    reset_admin_user()
