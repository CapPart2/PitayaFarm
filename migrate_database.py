#!/usr/bin/env python3
"""
Database Migration Script
Migrate from old column names to new Single Source of Truth structure
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Migrate database to new structure"""
    db_path = 'pitaya_database.db'
    
    print("🔄 Database Migration Started")
    print("=" * 50)
    
    # Backup existing database
    if os.path.exists(db_path):
        backup_path = f'pitaya_database_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check current table structure
        cursor.execute("PRAGMA table_info(disease_detections)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Current columns: {columns}")
        
        # Check if we need to migrate
        needs_migration = any(col in columns for col in ['id', 'disease_name', 'detection_time', 'confidence_score'])
        
        if needs_migration:
            print("🔄 Migration needed...")
            
            # Create new table with correct structure
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disease_detections_new (
                    DetectionID INTEGER PRIMARY KEY AUTOINCREMENT,
                    DiseaseType TEXT NOT NULL,
                    Severity TEXT NOT NULL,
                    Confidence REAL NOT NULL,
                    DateTime TEXT NOT NULL,
                    Location TEXT,
                    ImagePath TEXT,
                    UserID TEXT DEFAULT 'default_user',
                    CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Migrate data from old table
            if 'id' in columns:
                cursor.execute('''
                    INSERT INTO disease_detections_new 
                    (DetectionID, DiseaseType, Severity, Confidence, DateTime, Location, ImagePath, UserID, CreatedAt)
                    SELECT 
                        id,
                        COALESCE(disease_name, 'Unknown'),
                        COALESCE(severity, 'Medium'),
                        COALESCE(confidence_score, 0.0),
                        COALESCE(detection_time, CreatedAt),
                        location,
                        image_path,
                        user_id,
                        CreatedAt
                    FROM disease_detections
                ''')
                print("✅ Data migrated to new structure")
            
            # Drop old table and rename new one
            cursor.execute('DROP TABLE disease_detections')
            cursor.execute('ALTER TABLE disease_detections_new RENAME TO disease_detections')
            print("✅ Table structure updated")
            
            # Create new alerts table with 1:1 relationship
            cursor.execute('DROP TABLE IF EXISTS alerts')
            cursor.execute('''
                CREATE TABLE alerts (
                    AlertID INTEGER PRIMARY KEY AUTOINCREMENT,
                    DetectionID INTEGER NOT NULL,
                    Status TEXT DEFAULT 'Unread',
                    CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(DetectionID) REFERENCES disease_detections(DetectionID) ON DELETE CASCADE
                )
            ''')
            
            # Create unique constraint
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_detection_unique 
                ON alerts(DetectionID)
            ''')
            
            # Create alerts for existing detections
            cursor.execute('''
                INSERT INTO alerts (DetectionID, Status)
                SELECT DetectionID, 'Unread' FROM disease_detections
            ''')
            print("✅ Alerts table created with 1:1 relationship")
            
        else:
            print("✅ Database already has correct structure")
        
        conn.commit()
        
        # Verify migration
        cursor.execute("SELECT COUNT(*) FROM disease_detections")
        detection_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM alerts")
        alert_count = cursor.fetchone()[0]
        
        print(f"\n📊 Migration Results:")
        print(f"  Disease Detections: {detection_count}")
        print(f"  Alerts: {alert_count}")
        print(f"  1:1 Relationship: {'✅ VERIFIED' if detection_count == alert_count else '❌ BROKEN'}")
        
        conn.close()
        
        print("\n🎯 Database Migration Complete!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        conn.close()
        raise

if __name__ == "__main__":
    migrate_database()
