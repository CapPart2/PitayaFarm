import json
from database_models import DatabaseManager

db = DatabaseManager('pitaya_database.db')
reports = db.get_reports_data()
print(json.dumps(reports[:10], ensure_ascii=False, indent=2))
