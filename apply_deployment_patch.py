"""Make the current WanderClimate checkout deployable on one public origin.

Run once at project root after extracting the deployment bundle.
It only updates index.html and website_api.py if their known code is present.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

index = ROOT / "index.html"
s = index.read_text(encoding="utf-8")
old = 'const API = "http://127.0.0.1:8000";'
new = '''const API = (window.WANDERCLIMATE_API_BASE ||
  (["localhost", "127.0.0.1"].includes(window.location.hostname)
    && window.location.port !== "8000"
    ? "http://127.0.0.1:8000"
    : window.location.origin)).replace(/\\/$/, "");'''
if old in s:
    s = s.replace(old, new, 1)
    index.write_text(s, encoding="utf-8")
    print("Updated index.html to use the same origin on Render.")
elif new in s:
    print("index.html already patched.")
else:
    raise SystemExit("Could not locate the expected API configuration in index.html; no change made.")

api = ROOT / "website_api.py"
s = api.read_text(encoding="utf-8")
old = '        return pd.read_csv(data_path(name), low_memory=False)'
new = '''        path = data_path(name)
        # Only load the columns the website uses from the large analysis CSVs.
        # This reduces RAM pressure on Render's 512 MB free instance.
        if name == "tourism_final_clean.csv":
            return pd.read_csv(path, usecols=lambda col: col in {
                "TCI", "TCI_Category"
            }, low_memory=False)
        if name == "full.csv":
            return pd.read_csv(path, usecols=lambda col: col in {
                "Country", "Country_dest", "country", "Month", "month",
                "Destination Name", "Destination", "destination", "Place", "Name",
                "TCI", "tci", "City", "city", "Governorate", "Province",
                "Region", "governorate"
            }, low_memory=False)
        return pd.read_csv(path, low_memory=False)'''
if old in s:
    s = s.replace(old, new, 1)
    api.write_text(s, encoding="utf-8")
    print("Optimized large CSV loading in website_api.py.")
elif "# Only load the columns the website uses" in s:
    print("website_api.py already optimized.")
else:
    print("WARNING: No recognized CSV loading line in website_api.py; skipping optimization.")

print("Deployment setup is ready. Review changes with: git diff")
