import sqlite3
import hashlib

def reset_admin_user():
    """Reset or create admin user"""
    db_path = "pitaya_database.db"
    
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
    
    # Delete existing admin user if exists
    cursor.execute("DELETE FROM users WHERE Username = 'admin'")
    
    # Create new admin user
    default_password = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute(
        """
        INSERT INTO users (Username, PasswordHash, Email, FirstName, LastName, Role, Status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            "admin",
            default_password,
            "admin@pitaya.com",
            "System",
            "Administrator",
            "admin",
            "active",
        ),
    )
    
    conn.commit()
    
    # Verify the user was created
    cursor.execute("SELECT UserID, Username, Role, Status FROM users WHERE Username = 'admin'")
    user = cursor.fetchone()
    
    if user:
        print(f"Admin user created successfully!")
        print(f"UserID: {user[0]}")
        print(f"Username: {user[1]}")
        print(f"Role: {user[2]}")
        print(f"Status: {user[3]}")
        print(f"\nLogin credentials:")
        print(f"Username: admin")
        print(f"Password: admin123")
    else:
        print("Failed to create admin user")
    
    conn.close()

if __name__ == "__main__":
    reset_admin_user()
