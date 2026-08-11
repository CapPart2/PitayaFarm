# flake8: noqa
# Database Models for PITAYA System - Clean Version
# SQLAlchemy models for database-driven charts

import json
import logging
import os
import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path=None):
        # Railway's build filesystem is replaced on each deploy.  Keeping the
        # database in PITAYA_DATA_DIR lets a mounted volume preserve records.
        data_dir = os.environ.get("PITAYA_DATA_DIR")
        if db_path is None:
            db_path = os.environ.get(
                "PITAYA_DATABASE_PATH",
                os.path.join(data_dir, "pitaya_database.db")
                if data_dir
                else "pitaya_database.db",
            )
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database with required tables - Single Source of Truth"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create Disease_Detections table - SINGLE SOURCE OF TRUTH
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS disease_detections (
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
        """)

        # Create Disease Library table for translations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS disease_library (
                DiseaseID INTEGER PRIMARY KEY AUTOINCREMENT,
                DiseaseName TEXT NOT NULL UNIQUE,
                Description TEXT NOT NULL,
                Symptoms TEXT NOT NULL,
                Causes TEXT NOT NULL,
                Prevention TEXT NOT NULL,
                Treatment TEXT NOT NULL,
                Severity TEXT NOT NULL,
                ImagePath TEXT,
                CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create Tagalog Translations table - Single Source of Truth
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS disease_translations (
                TranslationID INTEGER PRIMARY KEY AUTOINCREMENT,
                DiseaseID INTEGER NOT NULL,
                TagalogDescription TEXT,
                TagalogSymptoms TEXT,
                TagalogCauses TEXT,
                TagalogPrevention TEXT,
                TagalogTreatment TEXT,
                QualityScore REAL DEFAULT 0.0,
                CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(DiseaseID) REFERENCES disease_library(DiseaseID) ON DELETE CASCADE,
                UNIQUE(DiseaseID)
            )
        """)

        # Check if we need to migrate from old structure
        try:
            cursor.execute("PRAGMA table_info(disease_detections)")
            columns = [row[1] for row in cursor.fetchall()]
            normalized_columns = {column.lower() for column in columns}

            # Migrate from old column names if needed
            if "disease_name" in columns and "DiseaseType" not in columns:
                cursor.execute(
                    "ALTER TABLE disease_detections RENAME COLUMN disease_name TO DiseaseType"
                )
            if "detection_time" in columns and "DateTime" not in columns:
                cursor.execute(
                    "ALTER TABLE disease_detections RENAME COLUMN detection_time TO DateTime"
                )
            if "confidence_score" in columns and "Confidence" not in columns:
                cursor.execute(
                    "ALTER TABLE disease_detections RENAME COLUMN confidence_score TO Confidence"
                )
            if "id" in columns and "DetectionID" not in columns:
                cursor.execute(
                    "ALTER TABLE disease_detections RENAME COLUMN id TO DetectionID"
                )

            # Add columns expected by the current write path when older databases
            # were created before these fields existed.
            for column_name, column_sql in [
                ("location", "location TEXT"),
                ("image_path", "image_path TEXT"),
                ("user_id", "user_id TEXT DEFAULT 'default_user'"),
            ]:
                if column_name not in normalized_columns:
                    cursor.execute(
                        f"ALTER TABLE disease_detections ADD COLUMN {column_sql}"
                    )

        except Exception as e:
            print(f"Migration note: {e}")

        # Create Alerts table with 1:1 relationship to Disease_Detections
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                AlertID INTEGER PRIMARY KEY AUTOINCREMENT,
                DetectionID INTEGER NOT NULL,
                Status TEXT DEFAULT 'Unread',
                CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(DetectionID) REFERENCES disease_detections(DetectionID) ON DELETE CASCADE
            )
        """)

        # Create unique constraint to ensure 1:1 relationship
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_detection_unique 
            ON alerts(DetectionID)
        """)

        # Create Yield_Predictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS yield_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                predicted_yield REAL NOT NULL,
                prediction_date TEXT NOT NULL,
                season TEXT,
                location TEXT,
                actual_yield REAL,
                accuracy_score REAL,
                model_version TEXT DEFAULT 'v1.0',
                user_id TEXT DEFAULT 'default_user',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                upload_type TEXT DEFAULT 'image'
            )
        """)

        # Add upload_type column if it doesn't exist (migration for existing databases)
        try:
            cursor.execute("PRAGMA table_info(yield_predictions)")
            columns = [row[1] for row in cursor.fetchall()]
            if "upload_type" not in columns:
                cursor.execute(
                    "ALTER TABLE yield_predictions ADD COLUMN upload_type TEXT DEFAULT 'image'"
                )
        except Exception as e:
            print(f"Migration note for upload_type: {e}")

        # Create user preferences table for alert delivery settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                preferred_language TEXT DEFAULT 'en',
                notification_email TEXT,
                farm_name TEXT,
                email_notifications_enabled INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("PRAGMA table_info(user_preferences)")
        preference_columns = {row[1] for row in cursor.fetchall()}
        for column_name, column_sql in [
            ("preferred_language", "preferred_language TEXT DEFAULT 'en'"),
            ("notification_email", "notification_email TEXT"),
            ("farm_name", "farm_name TEXT"),
            (
                "email_notifications_enabled",
                "email_notifications_enabled INTEGER DEFAULT 1",
            ),
            ("updated_at", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP"),
        ]:
            if column_name not in preference_columns:
                cursor.execute(f"ALTER TABLE user_preferences ADD COLUMN {column_sql}")

        # Create users table for admin/user management
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

        # Create user_logs table for activity tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_logs (
                LogID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER,
                Action TEXT NOT NULL,
                Description TEXT,
                IPAddress TEXT,
                UserAgent TEXT,
                CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(UserID) REFERENCES users(UserID) ON DELETE SET NULL
            )
        """)

        # Create site_settings table for configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                SettingID INTEGER PRIMARY KEY AUTOINCREMENT,
                SettingKey TEXT NOT NULL UNIQUE,
                SettingValue TEXT,
                SettingType TEXT DEFAULT 'string',
                Category TEXT DEFAULT 'general',
                Description TEXT,
                UpdatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
                UpdatedBy INTEGER
            )
        """)

        # Insert default admin user if not exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE Role = 'admin'")
        admin_count = cursor.fetchone()[0]
        if admin_count == 0:
            import hashlib

            default_password = hashlib.sha256(
                os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123").encode()
            ).hexdigest()
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

        # Development accounts must never be added to a public deployment.
        if os.environ.get("PITAYA_SEED_DEMO_USERS", "").lower() in {"1", "true", "yes"}:
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM users WHERE Username = ?", ("robabarintos",)
                )
                if cursor.fetchone()[0] == 0:
                    import hashlib as _hashlib

                    test_pw = _hashlib.sha256("robrob12".encode()).hexdigest()
                    cursor.execute(
                        """
                        INSERT INTO users (Username, PasswordHash, Email, FirstName, LastName, Role, Status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            "robabarintos",
                            test_pw,
                            "robabarintos@example.com",
                            "Rob",
                            "Barintos",
                            "user",
                            "active",
                        ),
                    )
            except Exception:
                # Non-fatal; continue initialization
                pass

        # Insert default site settings if not exists
        default_settings = [
            (
                "site_name",
                "PITAYA Farm Management System",
                "string",
                "general",
                "Site name",
            ),
            (
                "site_description",
                "Dragon Fruit Disease Detection and Yield Prediction",
                "string",
                "general",
                "Site description",
            ),
            ("max_users", "100", "number", "general", "Maximum number of users"),
            (
                "enable_registration",
                "true",
                "boolean",
                "general",
                "Allow new user registration",
            ),
            ("maintenance_mode", "false", "boolean", "general", "Maintenance mode"),
            ("default_language", "en", "string", "general", "Default language"),
            (
                "alert_email_enabled",
                "true",
                "boolean",
                "notifications",
                "Email alerts enabled",
            ),
            (
                "alert_sms_enabled",
                "false",
                "boolean",
                "notifications",
                "SMS alerts enabled",
            ),
        ]

        for key, value, setting_type, category, description in default_settings:
            cursor.execute(
                "SELECT COUNT(*) FROM site_settings WHERE SettingKey = ?", (key,)
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    """
                    INSERT INTO site_settings (SettingKey, SettingValue, SettingType, Category, Description)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (key, value, setting_type, category, description),
                )

        conn.commit()
        conn.close()

    def save_user_preferences(
        self,
        user_id: str = "default_user",
        preferred_language: str = "en",
        notification_email: Optional[str] = None,
        farm_name: Optional[str] = None,
        email_notifications_enabled: int = 1,
    ) -> Dict:
        """Persist profile settings used for alert delivery."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO user_preferences (
                user_id,
                preferred_language,
                notification_email,
                farm_name,
                email_notifications_enabled,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                preferred_language or "en",
                notification_email,
                farm_name,
                1 if email_notifications_enabled else 0,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        return self.get_user_preferences(user_id)

    def get_user_preferences(self, user_id: str = "default_user") -> Dict:
        """Return the stored profile and alert delivery preferences."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT preferred_language, notification_email, farm_name, email_notifications_enabled, updated_at
            FROM user_preferences
            WHERE user_id = ?
        """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {
                "user_id": user_id,
                "preferred_language": "en",
                "notification_email": None,
                "farm_name": None,
                "email_notifications_enabled": False,
                "updated_at": None,
            }

        return {
            "user_id": user_id,
            "preferred_language": row[0] or "en",
            "notification_email": row[1],
            "farm_name": row[2],
            "email_notifications_enabled": bool(row[3]) if row[3] is not None else True,
            "updated_at": row[4],
        }

    def _send_high_severity_email(
        self,
        detection_id: int,
        disease_type: str,
        severity: str,
        confidence: float,
        location: str,
        user_id: str,
        additional_diseases: Optional[List[Dict]] = None,
    ) -> bool:
        """Send a professional SMTP alert for high severity detections with multi-disease support."""
        scoped_user_id = str(user_id or "default_user")
        prefs = self.get_user_preferences(scoped_user_id)
        recipient = (prefs.get("notification_email") or "").strip()

        if not recipient or not prefs.get("email_notifications_enabled", True):
            return False

        smtp_host = "smtp.gmail.com"
        smtp_port = 587
        smtp_username = os.getenv("SMTP_USERNAME", "jacofarm1@gmail.com")
        smtp_password = os.getenv("SMTP_PASSWORD", "daml mkle iehe ybny")
        smtp_from = smtp_username
        smtp_use_tls = True

        if not smtp_host:
            logger.warning(
                "SMTP host is not configured; skipping high severity email notification"
            )
            return False

        if not smtp_password:
            logger.warning(
                "SMTP password/app password is not configured; skipping high severity email notification"
            )
            return False

        farm_name = (prefs.get("farm_name") or "Your farm").strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        severity_text = str(severity or "").upper()
        confidence_text = f"{float(confidence):.1f}%"
        safe_location = location or "Unknown location"

        # Handle multiple diseases in email
        if additional_diseases and len(additional_diseases) > 0:
            disease_count = len(additional_diseases) + 1
            subject = (
                f"High Severity Alert: {disease_count} diseases detected at {farm_name}"
            )

            # Build additional diseases table rows
            additional_diseases_html = ""
            additional_diseases_text = "\nAdditional diseases detected:\n"
            for disease in additional_diseases:
                disease_name = disease.get("disease_name", "Unknown")
                disease_conf = f"{float(disease.get('confidence', 0)):.1f}%"
                disease_sev = str(disease.get("severity", "medium")).upper()
                additional_diseases_html += f"""
          <tr><td style="padding:8px 0;color:#64748b;">Additional Disease</td><td style="padding:8px 0;font-weight:600;">{disease_name}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;">  Confidence</td><td style="padding:8px 0;font-weight:600;">{disease_conf}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;">  Severity</td><td style="padding:8px 0;font-weight:600;">{disease_sev}</td></tr>
"""
                additional_diseases_text += f"- {disease_name} ({disease_conf} confidence, {disease_sev} severity)\n"
        else:
            subject = f"High Severity Alert: {disease_type} detected at {farm_name}"
            additional_diseases_html = ""
            additional_diseases_text = ""

        plain_text = f"""
High Severity Alert

Farm: {farm_name}
Detection ID: {detection_id}
Primary Disease: {disease_type}
Severity: {severity_text}
Confidence: {confidence_text}
Location: {safe_location}
Time: {timestamp}
{additional_diseases_text}
Immediate action is recommended. Please review the alert in the PITAYA dashboard and apply the appropriate treatment steps.
""".strip()

        html_body = f"""
<!DOCTYPE html>
<html lang="en">
  <body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:640px;margin:0 auto;padding:24px;">
      <div style="background:linear-gradient(135deg,#166534,#22c55e);border-radius:18px 18px 0 0;padding:28px 32px;color:#ffffff;">
        <div style="font-size:12px;letter-spacing:.12em;text-transform:uppercase;opacity:.9;">PITAYA Alert System</div>
        <h1 style="margin:12px 0 6px;font-size:28px;line-height:1.2;">High Severity Detection</h1>
        <p style="margin:0;font-size:15px;opacity:.95;">Immediate attention is recommended for {farm_name}.</p>
      </div>
      <div style="background:#ffffff;border:1px solid #dbe3ef;border-top:none;border-radius:0 0 18px 18px;padding:28px 32px;box-shadow:0 10px 30px rgba(15,23,42,.08);">
        <p style="margin:0 0 18px;font-size:16px;line-height:1.6;">A new high severity disease detection has been recorded in your PITAYA dashboard.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;line-height:1.6;">
          <tr><td style="padding:8px 0;color:#64748b;width:170px;">Farm</td><td style="padding:8px 0;font-weight:600;">{farm_name}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;">Detection ID</td><td style="padding:8px 0;font-weight:600;">{detection_id}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;">Primary Disease</td><td style="padding:8px 0;font-weight:600;">{disease_type}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;">Severity</td><td style="padding:8px 0;font-weight:700;color:#dc2626;">{severity_text}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;">Confidence</td><td style="padding:8px 0;font-weight:600;">{confidence_text}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;">Location</td><td style="padding:8px 0;font-weight:600;">{safe_location}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;">Time</td><td style="padding:8px 0;font-weight:600;">{timestamp}</td></tr>
{additional_diseases_html}
        </table>
        <div style="margin-top:24px;padding:16px 18px;background:#ecfdf5;border:1px solid #bbf7d0;border-radius:14px;color:#14532d;">
          <strong>Recommended action:</strong> Review the alert in PITAYA, inspect the affected plants, and apply the suggested treatment immediately.
        </div>
        <p style="margin:22px 0 0;font-size:13px;color:#64748b;">This notification was sent automatically from the PITAYA alert system.</p>
      </div>
    </div>
  </body>
</html>
""".strip()

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"PITAYA Application <{smtp_from}>"
        message["To"] = recipient
        message.set_content(plain_text)
        message.add_alternative(html_body, subtype="html")

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
                if smtp_use_tls:
                    smtp.starttls()
                if smtp_username and smtp_password:
                    smtp.login(smtp_username, smtp_password)
                smtp.send_message(message)
            logger.info(
                "High severity alert email sent to %s for detection %s",
                recipient,
                detection_id,
            )
            return True
        except Exception as exc:
            logger.warning(
                "Failed to send high severity email for detection %s: %s",
                detection_id,
                exc,
            )
            return False

    def add_disease_detection(
        self,
        disease_type: str,
        severity: str,
        confidence: float,
        location: Optional[str] = None,
        image_path: Optional[str] = None,
        additional_diseases: Optional[List[Dict]] = None,
        session_id: Optional[str] = None,
        user_id: str = "default_user",
    ) -> int:
        """
        Add a new disease detection record - SINGLE SOURCE OF TRUTH
        Automatically creates corresponding alert (1:1 relationship)
        session_id groups multiple detections from the same image capture
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Add session_id column if it doesn't exist
        cursor.execute("PRAGMA table_info(disease_detections)")
        columns = [col[1] for col in cursor.fetchall()]
        column_lookup = {column.lower(): column for column in columns}
        if "session_id" not in columns:
            cursor.execute("ALTER TABLE disease_detections ADD COLUMN session_id TEXT")

        user_id_column = column_lookup.get("user_id") or column_lookup.get("userid")
        if not user_id_column:
            cursor.execute(
                "ALTER TABLE disease_detections ADD COLUMN user_id TEXT DEFAULT 'default_user'"
            )
            user_id_column = "user_id"

        # Insert into Disease_Detections table
        cursor.execute(
            """
            INSERT INTO disease_detections 
            (DiseaseType, severity, Confidence, DateTime, location, image_path, {user_id_column}, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """.format(user_id_column=user_id_column),
            (
                disease_type,
                severity,
                confidence,
                datetime.now().isoformat(),
                location,
                image_path,
                user_id or "default_user",
                session_id,
            ),
        )

        detection_id = cursor.lastrowid
        if detection_id is None:
            conn.rollback()
            conn.close()
            raise RuntimeError("Failed to create detection record")

        # Create corresponding alert (1:1 relationship)
        cursor.execute(
            """
            INSERT INTO alerts (DetectionID, Status)
            VALUES (?, 'Unread')
        """,
            (detection_id,),
        )

        conn.commit()
        conn.close()

        if str(severity).strip().lower() == "high":
            self._send_high_severity_email(
                detection_id=detection_id,
                disease_type=disease_type,
                severity=severity,
                confidence=confidence,
                location=location or "Unknown location",
                user_id=user_id,
                additional_diseases=additional_diseases,
            )

        return detection_id

    # ========== DATA INTEGRITY METHODS ==========

    def get_all_disease_detections(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get ALL disease detections - Single Source of Truth"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT DetectionID, DiseaseType, severity, Confidence, DateTime, location, image_path, user_id, session_id
            FROM disease_detections
        """
        params = []
        conditions = []

        if start_date:
            conditions.append("DateTime >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("DateTime <= ?")
            params.append(end_date)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY DateTime DESC"

        cursor.execute(query, params)

        detections = []
        for row in cursor.fetchall():
            detections.append(
                {
                    "DetectionID": row[0],
                    "DiseaseType": row[1],
                    "Severity": row[2],
                    "Confidence": row[3],
                    "DateTime": row[4],
                    "Location": row[5],
                    "ImagePath": row[6],
                    "UserID": row[7],
                    "session_id": row[8],
                }
            )

        conn.close()
        return detections

    def get_all_alerts_with_detections(
        self, user_id: Optional[str] = None
    ) -> List[Dict]:
        """Get ALL alerts with their detection data - Full History"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
                 SELECT a.AlertID, a.DetectionID, a.Status, a.CreatedAt,
                     d.DiseaseType, d.Severity, d.Confidence, d.DateTime, d.Location, d.image_path, d.session_id, d.user_id
            FROM alerts a
            JOIN disease_detections d ON a.DetectionID = d.DetectionID
        """
        params = []
        if user_id:
            query += " WHERE d.user_id = ?"
            params.append(user_id)
        query += " ORDER BY d.DateTime DESC"

        cursor.execute(query, params)

        alerts = []
        for row in cursor.fetchall():
            alerts.append(
                {
                    "AlertID": row[0],
                    "DetectionID": row[1],
                    "Status": row[2],
                    "CreatedAt": row[3],
                    "DiseaseType": row[4],
                    "Severity": row[5],
                    "Confidence": row[6],
                    "DateTime": row[7],
                    "Location": row[8],
                    "image_path": row[9],
                    "session_id": row[10],
                    "UserID": row[11],
                }
            )

        conn.close()
        return alerts

    def mark_alert_read(self, alert_id: int) -> bool:
        """Mark alert as read - maintains 1:1 relationship"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE alerts 
            SET Status = 'Read' 
            WHERE AlertID = ?
        """,
            (alert_id,),
        )

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def get_unread_alerts_count(self) -> int:
        """Get count of unread alerts - Database-driven notification count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM alerts WHERE Status = 'Unread'")
        unread_count = cursor.fetchone()[0]

        conn.close()
        return unread_count

    def verify_alert_detection_integrity(self) -> Dict:
        """Verify 1:1 relationship between detections and alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get counts from each table
        cursor.execute("SELECT COUNT(*) FROM disease_detections")
        detection_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts")
        alert_count = cursor.fetchone()[0]

        # Verify 1:1 relationship
        cursor.execute("""
            SELECT COUNT(*) FROM alerts a
            JOIN disease_detections d ON a.DetectionID = d.DetectionID
        """)
        joined_count = cursor.fetchone()[0]

        # Get unread alerts count
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE Status = 'Unread'")
        unread_count = cursor.fetchone()[0]

        conn.close()

        return {
            "total_detections": detection_count,
            "total_alerts": alert_count,
            "joined_records": joined_count,
            "unread_alerts": unread_count,
            "integrity_check": {
                "detection_equals_alert": detection_count == alert_count,
                "all_alerts_have_detections": joined_count == alert_count,
                "data_integrity_passed": detection_count == alert_count == joined_count,
            },
        }

    def get_dashboard_metrics(self, user_id: Optional[str] = None) -> Dict:
        """Dashboard metrics computed directly from Disease_Detections"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        where_clause = ""
        params = []
        if user_id:
            where_clause = " WHERE user_id = ?"
            params.append(user_id)

        # Total detections
        cursor.execute(f"SELECT COUNT(*) FROM disease_detections{where_clause}", params)
        total_detections = cursor.fetchone()[0]

        # High severity cases
        if user_id:
            cursor.execute(
                "SELECT COUNT(*) FROM disease_detections WHERE Severity = 'high' AND user_id = ?",
                [user_id],
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM disease_detections WHERE Severity = 'high'"
            )
        high_severity = cursor.fetchone()[0]

        # Disease distribution
        disease_query = """
            SELECT DiseaseType, COUNT(*) as count
            FROM disease_detections
        """
        if user_id:
            disease_query += " WHERE user_id = ?"
        disease_query += " GROUP BY DiseaseType ORDER BY count DESC"
        cursor.execute(disease_query, [user_id] if user_id else [])
        disease_distribution = dict(cursor.fetchall())

        # Severity distribution
        severity_query = """
            SELECT Severity, COUNT(*) as count
            FROM disease_detections
        """
        if user_id:
            severity_query += " WHERE user_id = ?"
        severity_query += " GROUP BY Severity"
        cursor.execute(severity_query, [user_id] if user_id else [])
        severity_distribution = dict(cursor.fetchall())

        # Daily detections (last 30 days)
        if user_id:
            cursor.execute(
                """
                SELECT DATE(DateTime) as date, COUNT(*) as count
                FROM disease_detections
                WHERE DateTime >= date('now', '-30 days') AND user_id = ?
                GROUP BY DATE(DateTime)
                ORDER BY date
                """,
                [user_id],
            )
        else:
            cursor.execute("""
                SELECT DATE(DateTime) as date, COUNT(*) as count
                FROM disease_detections
                WHERE DateTime >= date('now', '-30 days')
                GROUP BY DATE(DateTime)
                ORDER BY date
                """)
        daily_detections = dict(cursor.fetchall())

        conn.close()

        return {
            "total_detections": total_detections,
            "high_severity_cases": high_severity,
            "disease_distribution": disease_distribution,
            "severity_distribution": severity_distribution,
            "daily_detections": daily_detections,
        }

    def get_reports_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict]:
        """Reports data from Disease_Detections - Single Source of Truth"""
        return self.get_all_disease_detections(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )

    def add_detection(
        self,
        disease_type: str,
        severity: str,
        confidence: float,
        location: Optional[str] = None,
        image_path: Optional[str] = None,
    ) -> int:
        """Backward-compatible wrapper for older call sites."""
        return self.add_disease_detection(
            disease_type=disease_type,
            severity=severity,
            confidence=confidence,
            location=location,
            image_path=image_path,
        )

    def add_disease_library_entry(
        self,
        disease_name: str,
        description: str,
        symptoms: str,
        causes: str,
        prevention: str,
        treatment: str,
        severity: str,
        image_path: Optional[str] = None,
    ) -> int:
        """Add disease library entry - Single Source of Truth for disease content"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO disease_library 
            (disease_name, description, symptoms, causes, prevention_methods, recommended_treatments, severity_level, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                disease_name,
                description,
                symptoms,
                causes,
                prevention,
                treatment,
                severity,
                image_path,
            ),
        )

        disease_id = cursor.lastrowid
        conn.commit()
        conn.close()
        if disease_id is None:
            raise RuntimeError("Failed to create disease library entry")
        return disease_id

    def get_disease_translation(self, disease_id: int) -> Optional[Dict]:
        """Check existing translation - Single Source of Truth"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, disease_name, description_tagalog, symptoms_tagalog,
                   causes_tagalog, prevention_methods_tagalog, recommended_treatments_tagalog
            FROM disease_library 
            WHERE id = ?
        """,
            (disease_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if result and result[2]:  # Check if description_tagalog exists
            return {
                "TranslationID": result[0],
                "DiseaseID": result[0],
                "TagalogDescription": result[2],
                "TagalogSymptoms": result[3],
                "TagalogCauses": result[4],
                "TagalogPrevention": result[5],
                "TagalogTreatment": result[6],
                "QualityScore": 1.0,
                "CreatedAt": None,
            }
        return None

    def save_disease_translation(
        self,
        disease_id: int,
        tagalog_description: str,
        tagalog_symptoms: str,
        tagalog_causes: str,
        tagalog_prevention: str,
        tagalog_treatment: str,
        quality_score: float = 0.0,
    ) -> bool:
        """Save translation - Generate Once Store Forever"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE disease_library 
                SET description_tagalog = ?, symptoms_tagalog = ?,
                    causes_tagalog = ?, prevention_methods_tagalog = ?,
                    recommended_treatments_tagalog = ?
                WHERE id = ?
            """,
                (
                    tagalog_description,
                    tagalog_symptoms,
                    tagalog_causes,
                    tagalog_prevention,
                    tagalog_treatment,
                    disease_id,
                ),
            )

            conn.commit()
            success = cursor.rowcount > 0
        except Exception as e:
            print(f"Error saving translation: {e}")
            success = False
        finally:
            conn.close()

        return success

    def get_disease_library_with_translations(self) -> List[Dict]:
        """Get all diseases with translations - Toggle Without Reprocessing"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT dl.id, dl.disease_name, dl.description, dl.symptoms,
                   dl.causes, dl.prevention_methods, dl.recommended_treatments, dl.severity_level, dl.image_path,
                   dl.description_tagalog, dl.symptoms_tagalog, dl.causes_tagalog,
                   dl.prevention_methods_tagalog, dl.recommended_treatments_tagalog
            FROM disease_library dl
            ORDER BY dl.disease_name
        """)

        diseases = []
        for row in cursor.fetchall():
            diseases.append(
                {
                    "id": row[0],
                    "disease_name": row[1],
                    "description": row[2],
                    "symptoms": row[3],
                    "causes": row[4],
                    "prevention_methods": row[5],
                    "recommended_treatments": row[6],
                    "severity_level": row[7],
                    "image_path": row[8],
                    "description_tagalog": row[9],
                    "symptoms_tagalog": row[10],
                    "causes_tagalog": row[11],
                    "prevention_methods_tagalog": row[12],
                    "recommended_treatments_tagalog": row[13],
                    "quality_score": 1.0 if row[9] else 0.0,
                    "has_translation": row[9] is not None,
                }
            )

        conn.close()
        return diseases

    def get_disease_by_name(self, disease_name: str) -> Optional[Dict]:
        """Get disease by name from library"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, disease_name, description, symptoms, causes,
                   prevention_methods, recommended_treatments, severity_level
            FROM disease_library 
            WHERE disease_name = ?
        """,
            (disease_name,),
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                "id": result[0],
                "disease_name": result[1],
                "description": result[2],
                "symptoms": result[3],
                "causes": result[4],
                "prevention_methods": result[5],
                "recommended_treatments": result[6],
                "severity_level": result[7],
            }
        return None

    def get_disease_statistics(self, user_id: Optional[str] = None) -> Dict:
        """Get disease statistics for dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total detections
        if user_id:
            cursor.execute(
                "SELECT COUNT(*) FROM disease_detections WHERE user_id = ?", [user_id]
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM disease_detections")
        total_detections = cursor.fetchone()[0]

        # High severity cases
        if user_id:
            cursor.execute(
                "SELECT COUNT(*) FROM disease_detections WHERE severity = 'High' AND user_id = ?",
                [user_id],
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM disease_detections WHERE severity = 'High'"
            )
        high_severity_count = cursor.fetchone()[0]

        # Disease distribution
        disease_query = """
            SELECT DiseaseType, COUNT(*) as count
            FROM disease_detections
        """
        if user_id:
            disease_query += " WHERE user_id = ?"
        disease_query += " GROUP BY DiseaseType ORDER BY count DESC"
        cursor.execute(disease_query, [user_id] if user_id else [])
        disease_data = dict(cursor.fetchall())

        # Daily detections for charts
        if user_id:
            cursor.execute(
                """
                SELECT DATE(DateTime) as date, COUNT(*) as count
                FROM disease_detections
                WHERE DateTime >= date('now', '-30 days') AND user_id = ?
                GROUP BY DATE(DateTime)
                ORDER BY date
                """,
                [user_id],
            )
        else:
            cursor.execute("""
                SELECT DATE(DateTime) as date, COUNT(*) as count
                FROM disease_detections
                WHERE DateTime >= date('now', '-30 days')
                GROUP BY DATE(DateTime)
                ORDER BY date
                """)
        daily_detections = [
            {"date": row[0], "count": row[1]} for row in cursor.fetchall()
        ]

        conn.close()

        return {
            "total_detections": total_detections,
            "high_severity_cases": high_severity_count,
            "disease_data": disease_data,
            "daily_detections": daily_detections,
        }

    def add_yield_prediction(
        self,
        predicted_yield: float,
        location: str = "Field",
        season: Optional[str] = None,
        upload_type: str = "image",
        user_id: str = "default_user",
    ) -> int:
        """Insert a new yield prediction record and return its id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        if season is None:
            d = datetime.now()
            q = (d.month - 1) // 3 + 1
            season = f"{d.year} Q{q}"
        cursor.execute(
            """
            INSERT INTO yield_predictions (predicted_yield, prediction_date, season, location, model_version, user_id, upload_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                predicted_yield,
                now,
                season,
                location,
                "v1.0",
                user_id or "default_user",
                upload_type,
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        if new_id is None:
            raise RuntimeError("Failed to save yield prediction")
        return new_id

    def get_all_yield_predictions(self, user_id: Optional[str] = None) -> List[Dict]:
        """Return all yield prediction records ordered newest first"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = """
            SELECT id, predicted_yield, prediction_date, season, location, actual_yield, accuracy_score, created_at, upload_type, user_id
            FROM yield_predictions
        """
        params = []
        if user_id:
            query += " WHERE user_id = ?"
            params.append(user_id)
        query += " ORDER BY prediction_date DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "predicted_yield": r[1],
                "prediction_date": r[2],
                "season": r[3],
                "location": r[4],
                "actual_yield": r[5],
                "accuracy_score": r[6],
                "created_at": r[7],
                "upload_type": r[8] if len(r) > 8 else "image",
                "user_id": r[9] if len(r) > 9 else "default_user",
            }
            for r in rows
        ]

    def delete_yield_prediction(self, record_id: int) -> bool:
        """Delete a yield prediction record by id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM yield_predictions WHERE id = ?", (record_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def get_yield_statistics(self, user_id: Optional[str] = None) -> Dict:
        """Get yield prediction statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total predictions
        if user_id:
            cursor.execute(
                "SELECT COUNT(*) FROM yield_predictions WHERE user_id = ?", [user_id]
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM yield_predictions")
        total_predictions = cursor.fetchone()[0]

        # Average accuracy
        if user_id:
            cursor.execute(
                """
                SELECT AVG(accuracy_score) as avg_accuracy
                FROM yield_predictions 
                WHERE actual_yield IS NOT NULL AND user_id = ?
                """,
                [user_id],
            )
        else:
            cursor.execute("""
                SELECT AVG(accuracy_score) as avg_accuracy
                FROM yield_predictions 
                WHERE actual_yield IS NOT NULL
                """)
        avg_accuracy = cursor.fetchone()[0] or 0

        # Average confidence from disease detections (0–1 float → multiply by 100 for %)
        if user_id:
            cursor.execute(
                "SELECT AVG(Confidence) FROM disease_detections WHERE Confidence IS NOT NULL AND user_id = ?",
                [user_id],
            )
        else:
            cursor.execute(
                "SELECT AVG(Confidence) FROM disease_detections WHERE Confidence IS NOT NULL"
            )
        avg_confidence_raw = cursor.fetchone()[0] or 0
        avg_confidence = avg_confidence_raw  # stored as 0–1; API will multiply by 100

        # Total fruits detected (sum of predicted_yield across all yield records)
        if user_id:
            cursor.execute(
                "SELECT COALESCE(SUM(predicted_yield), 0) FROM yield_predictions WHERE user_id = ?",
                [user_id],
            )
        else:
            cursor.execute(
                "SELECT COALESCE(SUM(predicted_yield), 0) FROM yield_predictions"
            )
        total_fruits = int(cursor.fetchone()[0] or 0)

        # High severity cases from disease detections
        if user_id:
            cursor.execute(
                "SELECT COUNT(*) FROM disease_detections WHERE Severity = 'high' AND user_id = ?",
                [user_id],
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM disease_detections WHERE Severity = 'high'"
            )
        high_severity_cases = cursor.fetchone()[0]

        # Yield trend for charts
        if user_id:
            cursor.execute(
                """
                SELECT DATE(prediction_date) as date, 
                       AVG(predicted_yield) as avg_predicted,
                       AVG(actual_yield) as avg_actual
                FROM yield_predictions 
                WHERE prediction_date >= date('now', '-90 days') AND user_id = ?
                GROUP BY DATE(prediction_date)
                ORDER BY date
                """,
                [user_id],
            )
        else:
            cursor.execute("""
                SELECT DATE(prediction_date) as date, 
                       AVG(predicted_yield) as avg_predicted,
                       AVG(actual_yield) as avg_actual
                FROM yield_predictions 
                WHERE prediction_date >= date('now', '-90 days')
                GROUP BY DATE(prediction_date)
                ORDER BY date
                """)
        yield_trend = [
            {"date": row[0], "predicted": row[1], "actual": row[2]}
            for row in cursor.fetchall()
        ]

        # Location / block yields
        if user_id:
            cursor.execute(
                """
                SELECT location, SUM(predicted_yield) as total_yield
                FROM yield_predictions
                WHERE location IS NOT NULL AND location != '' AND user_id = ?
                GROUP BY location
                ORDER BY location
                """,
                [user_id],
            )
        else:
            cursor.execute("""
                SELECT location, SUM(predicted_yield) as total_yield
                FROM yield_predictions
                WHERE location IS NOT NULL AND location != ''
                GROUP BY location
                ORDER BY location
                """)
        location_yields = [
            {"location": row[0], "avg_predicted": row[1]} for row in cursor.fetchall()
        ]

        # Seasonal yields
        if user_id:
            cursor.execute(
                """
                SELECT season, SUM(predicted_yield) as total_yield
                FROM yield_predictions
                WHERE season IS NOT NULL AND season != '' AND user_id = ?
                GROUP BY season
                ORDER BY season
                """,
                [user_id],
            )
        else:
            cursor.execute("""
                SELECT season, SUM(predicted_yield) as total_yield
                FROM yield_predictions
                WHERE season IS NOT NULL AND season != ''
                GROUP BY season
                ORDER BY season
                """)
        seasonal_yields = [
            {"season": row[0], "avg_predicted": row[1]} for row in cursor.fetchall()
        ]

        conn.close()

        return {
            "total_predictions": total_predictions,
            "avg_accuracy": avg_accuracy,
            "avg_confidence": avg_confidence,
            "total_fruits": total_fruits,
            "high_severity_cases": high_severity_cases,
            "yield_trend": yield_trend,
            "location_yields": location_yields,
            "seasonal_yields": seasonal_yields,
            "accuracy_info": {
                "avg_accuracy": avg_accuracy,
                "avg_confidence": avg_confidence,
                "total_predictions": total_predictions,
            },
        }

    def get_unread_alert_count(self, user_id: Optional[str] = None) -> int:
        """Get count of unread alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if user_id:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM alerts a
                JOIN disease_detections d ON a.DetectionID = d.DetectionID
                WHERE a.Status = 'Unread' AND d.user_id = ?
                """,
                [user_id],
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE Status = 'Unread'")
        count = cursor.fetchone()[0]

        conn.close()
        return count

    def delete_detection(self, detection_id: int) -> bool:
        """
        Delete detection - cascades to alert due to foreign key
        Maintains 1:1 relationship integrity
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # First verify the detection exists
            cursor.execute(
                """
                SELECT DetectionID FROM disease_detections 
                WHERE DetectionID = ?
            """,
                (detection_id,),
            )

            if not cursor.fetchone():
                conn.close()
                return False

            # Delete the detection (cascade will delete the alert)
            cursor.execute(
                """
                DELETE FROM disease_detections 
                WHERE DetectionID = ?
            """,
                (detection_id,),
            )

            success = cursor.rowcount > 0
            conn.commit()
            conn.close()

            return success

        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    def get_detection_statistics(self) -> Dict:
        """
        Get comprehensive detection statistics for library and system metrics
        Used by Dashboard, Reports, and Library components
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total detections
        cursor.execute("SELECT COUNT(*) FROM disease_detections")
        total_detections = cursor.fetchone()[0]

        # Disease-specific counts
        cursor.execute("""
            SELECT DiseaseType, COUNT(*) as count
            FROM disease_detections
            GROUP BY DiseaseType
            ORDER BY count DESC
        """)
        disease_counts = dict(cursor.fetchall())

        # Severity distribution
        cursor.execute("""
            SELECT Severity, COUNT(*) as count
            FROM disease_detections
            GROUP BY Severity
        """)
        severity_counts = dict(cursor.fetchall())

        # Recent detections (last 30 days)
        cursor.execute("""
            SELECT DATE(DateTime) as date, COUNT(*) as count
            FROM disease_detections
            WHERE DateTime >= date('now', '-30 days')
            GROUP BY DATE(DateTime)
            ORDER BY date DESC
        """)
        recent_detections = dict(cursor.fetchall())

        # Monthly trends (last 6 months)
        cursor.execute("""
            SELECT strftime('%Y-%m', DateTime) as month, COUNT(*) as count
            FROM disease_detections
            WHERE DateTime >= date('now', '-6 months')
            GROUP BY month
            ORDER BY month DESC
        """)
        monthly_trends = dict(cursor.fetchall())

        conn.close()

        return {
            "total_detections": total_detections,
            "disease_counts": disease_counts,
            "severity_counts": severity_counts,
            "recent_detections": recent_detections,
            "monthly_trends": monthly_trends,
        }

    # ========== ADMIN: USER MANAGEMENT METHODS ==========

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: str = "user",
        status: str = "active",
    ) -> int:
        """Create a new user"""
        import hashlib

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        cursor.execute(
            """
            INSERT INTO users (Username, PasswordHash, Email, FirstName, LastName, Role, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (username, password_hash, email, first_name, last_name, role, status),
        )

        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return user_id

    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT UserID, Username, Email, FirstName, LastName, Role, Status, CreatedAt, LastLogin
            FROM users
            ORDER BY CreatedAt DESC
        """)

        users = []
        for row in cursor.fetchall():
            users.append(
                {
                    "UserID": row[0],
                    "Username": row[1],
                    "Email": row[2],
                    "FirstName": row[3],
                    "LastName": row[4],
                    "Role": row[5],
                    "Status": row[6],
                    "CreatedAt": row[7],
                    "LastLogin": row[8],
                }
            )

        conn.close()
        return users

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT UserID, Username, Email, FirstName, LastName, Role, Status, CreatedAt, LastLogin
            FROM users
            WHERE UserID = ?
        """,
            (user_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "UserID": row[0],
                "Username": row[1],
                "Email": row[2],
                "FirstName": row[3],
                "LastName": row[4],
                "Role": row[5],
                "Status": row[6],
                "CreatedAt": row[7],
                "LastLogin": row[8],
            }
        return None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user record by username (any status)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT UserID, Username, Email, FirstName, LastName, Role, Status, PasswordHash, CreatedAt, LastLogin
            FROM users
            WHERE Username = ?
        """,
            (username,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "UserID": row[0],
                "Username": row[1],
                "Email": row[2],
                "FirstName": row[3],
                "LastName": row[4],
                "Role": row[5],
                "Status": row[6],
                "PasswordHash": row[7],
                "CreatedAt": row[8],
                "LastLogin": row[9],
            }
        return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user record by email (any status)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT UserID, Username, Email, FirstName, LastName, Role, Status, PasswordHash, CreatedAt, LastLogin
            FROM users
            WHERE Email = ?
        """,
            (email,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "UserID": row[0],
                "Username": row[1],
                "Email": row[2],
                "FirstName": row[3],
                "LastName": row[4],
                "Role": row[5],
                "Status": row[6],
                "PasswordHash": row[7],
                "CreatedAt": row[8],
                "LastLogin": row[9],
            }
        return None

    def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """Update user information"""
        import hashlib

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = []
        params = []

        if email is not None:
            updates.append("Email = ?")
            params.append(email)
        if first_name is not None:
            updates.append("FirstName = ?")
            params.append(first_name)
        if last_name is not None:
            updates.append("LastName = ?")
            params.append(last_name)
        if role is not None:
            updates.append("Role = ?")
            params.append(role)
        if status is not None:
            updates.append("Status = ?")
            params.append(status)
        if password is not None:
            updates.append("PasswordHash = ?")
            params.append(hashlib.sha256(password.encode()).hexdigest())

        if not updates:
            conn.close()
            return False

        updates.append("UpdatedAt = ?")
        params.append(datetime.now().isoformat())
        params.append(user_id)

        cursor.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE UserID = ?", params
        )

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def delete_user(self, user_id: int) -> bool:
        """Delete a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM users WHERE UserID = ?", (user_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def verify_user_credentials(self, username: str, password: str) -> Optional[Dict]:
        """Verify user credentials for login"""
        import hashlib

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        cursor.execute(
            """
            SELECT UserID, Username, Email, FirstName, LastName, Role, Status
            FROM users
            WHERE Username = ? AND PasswordHash = ? AND Status = 'active'
        """,
            (username, password_hash),
        )

        row = cursor.fetchone()

        if row:
            # Update last login
            cursor.execute(
                "UPDATE users SET LastLogin = ? WHERE UserID = ?",
                (datetime.now().isoformat(), row[0]),
            )
            conn.commit()

        conn.close()

        if row:
            return {
                "UserID": row[0],
                "Username": row[1],
                "Email": row[2],
                "FirstName": row[3],
                "LastName": row[4],
                "Role": row[5],
                "Status": row[6],
            }
        return None

    # ========== ADMIN: USER LOGS METHODS ==========

    def create_user_log(
        self,
        user_id: Optional[int],
        action: str,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> int:
        """Create a user log entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO user_logs (UserID, Action, Description, IPAddress, UserAgent)
            VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, action, description, ip_address, user_agent),
        )

        log_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return log_id

    def get_all_user_logs(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get user logs with optional filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT ul.LogID, ul.UserID, u.Username, ul.Action, ul.Description, 
                   ul.IPAddress, ul.UserAgent, ul.CreatedAt
            FROM user_logs ul
            LEFT JOIN users u ON ul.UserID = u.UserID
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND ul.CreatedAt >= ?"
            params.append(start_date)
        if end_date:
            query += " AND ul.CreatedAt <= ?"
            params.append(end_date)
        if user_id:
            query += " AND ul.UserID = ?"
            params.append(user_id)
        if action:
            query += " AND ul.Action LIKE ?"
            params.append(f"%{action}%")

        query += " ORDER BY ul.CreatedAt DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        logs = []
        for row in cursor.fetchall():
            logs.append(
                {
                    "LogID": row[0],
                    "UserID": row[1],
                    "Username": row[2],
                    "Action": row[3],
                    "Description": row[4],
                    "IPAddress": row[5],
                    "UserAgent": row[6],
                    "CreatedAt": row[7],
                }
            )

        conn.close()
        return logs

    # ========== ADMIN: SITE SETTINGS METHODS ==========

    def get_site_settings(self, category: Optional[str] = None) -> List[Dict]:
        """Get all site settings, optionally filtered by category"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if category:
            cursor.execute(
                """
                SELECT SettingID, SettingKey, SettingValue, SettingType, Category, Description, UpdatedAt
                FROM site_settings
                WHERE Category = ?
                ORDER BY Category, SettingKey
            """,
                (category,),
            )
        else:
            cursor.execute("""
                SELECT SettingID, SettingKey, SettingValue, SettingType, Category, Description, UpdatedAt
                FROM site_settings
                ORDER BY Category, SettingKey
            """)

        settings = []
        for row in cursor.fetchall():
            settings.append(
                {
                    "SettingID": row[0],
                    "SettingKey": row[1],
                    "SettingValue": row[2],
                    "SettingType": row[3],
                    "Category": row[4],
                    "Description": row[5],
                    "UpdatedAt": row[6],
                }
            )

        conn.close()
        return settings

    def update_site_setting(
        self, setting_key: str, setting_value: str, updated_by: Optional[int] = None
    ) -> bool:
        """Update a site setting"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE site_settings
            SET SettingValue = ?, UpdatedAt = ?, UpdatedBy = ?
            WHERE SettingKey = ?
        """,
            (setting_value, datetime.now().isoformat(), updated_by, setting_key),
        )

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def get_admin_dashboard_metrics(self) -> Dict:
        """Get comprehensive metrics for admin dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # User statistics
        cursor.execute("SELECT COUNT(*) FROM users WHERE Status = 'active'")
        active_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE Role = 'admin'")
        admin_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        # Disease detection statistics
        cursor.execute("SELECT COUNT(*) FROM disease_detections")
        total_detections = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM disease_detections WHERE DateTime >= date('now', '-7 days')"
        )
        weekly_detections = cursor.fetchone()[0]

        # Yield statistics
        cursor.execute("SELECT COUNT(*) FROM yield_predictions")
        total_yield_predictions = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COALESCE(SUM(predicted_yield), 0) FROM yield_predictions"
        )
        total_fruits_detected = cursor.fetchone()[0]

        # Alert statistics
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE Status = 'Unread'")
        unread_alerts = cursor.fetchone()[0]

        # Recent activity
        cursor.execute(
            "SELECT COUNT(*) FROM user_logs WHERE CreatedAt >= date('now', '-7 days')"
        )
        weekly_activity = cursor.fetchone()[0]

        conn.close()

        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "admins": admin_count,
            },
            "detections": {
                "total": total_detections,
                "weekly": weekly_detections,
            },
            "yield": {
                "total_predictions": total_yield_predictions,
                "total_fruits": total_fruits_detected,
            },
            "alerts": {
                "unread": unread_alerts,
            },
            "activity": {
                "weekly_logs": weekly_activity,
            },
        }

    def get_disease_library_data(self) -> List[Dict]:
        """
        Get disease data for library component with detection counts
        Includes statistics for each disease type
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all disease types with their statistics
        cursor.execute("""
            SELECT 
                DiseaseType,
                COUNT(*) as detection_count,
                AVG(Confidence) as avg_confidence,
                MAX(DateTime) as last_detected,
                COUNT(CASE WHEN Severity = 'High' THEN 1 END) as high_severity_count,
                COUNT(CASE WHEN Severity = 'Medium' THEN 1 END) as medium_severity_count,
                COUNT(CASE WHEN Severity = 'Low' THEN 1 END) as low_severity_count
            FROM disease_detections
            GROUP BY DiseaseType
            ORDER BY detection_count DESC
        """)

        diseases = []
        for row in cursor.fetchall():
            diseases.append(
                {
                    "name": row[0],
                    "detection_count": row[1],
                    "avg_confidence": round(row[2], 2) if row[2] else 0,
                    "last_detected": row[3],
                    "severity_distribution": {
                        "high": row[4],
                        "medium": row[5],
                        "low": row[6],
                    },
                }
            )

        conn.close()
        return diseases


# Initialize database manager
db_manager = DatabaseManager()

print("Database initialized with Single Source of Truth architecture")
