from pathlib import Path
import shutil

backend_json = Path("data/dashboard.json")
frontend_json = Path("../frontend/public/dashboard.json")

frontend_json.parent.mkdir(parents=True, exist_ok=True)

shutil.copy2(backend_json, frontend_json)

print("✓ Dashboard copied successfully.")