"""Replace only the Spatial Clustering page in dashboard.py with the UI logic from app.py.

Run this file from the same directory as app.py and dashboard.py:
    python replace_spatial_with_app.py

- Leaves app.py unchanged.
- Embeds the original recommendation + interactive map logic directly in dashboard.py.
- Loads full.csv and places_with_clusters.csv automatically (no upload).
- Keeps other dashboard pages, including both itinerary planners, unchanged.
- Also handles dashboards patched by an earlier recommendations_page.py integration.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import shutil
import textwrap

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
DASHBOARD = ROOT / "dashboard.py"
REQUIREMENTS = ROOT / "requirements.txt"


def validate(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)


def build_page(original_app: str) -> str:
    """Extract original app.py UI while removing the page config and CSV uploads."""
    tree = ast.parse(original_app, filename=str(APP))
    helper_names = ("clean_col", "get_cluster_color")
    helpers = []
    for name in helper_names:
        fn = next((node for node in tree.body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == name), None)
        validate(fn is not None, f"Couldn't find {name}() in original app.py")
        helpers.append(ast.get_source_segment(original_app, fn))

    begin_marker = 'country_col = clean_col(full,'
    map_upload_marker = 'if places_file is None:'
    map_core_marker = '        name_col = clean_col('
    validate(begin_marker in original_app, 'Missing recommendation logic in app.py')
    validate(map_upload_marker in original_app, 'Missing original map section in app.py')
    validate(map_core_marker in original_app, 'Missing original map logic in app.py')

    main_core = original_app[original_app.index(begin_marker):
                             original_app.index(map_upload_marker)]
    original_tail = original_app[original_app.index(map_core_marker):]
    map_tail = textwrap.dedent(original_tail)
    validate(re.search(r'(?m)^except Exception as e:', map_tail) is not None,
             "Could not identify original map's exception handler")

    # Force a fresh Folium component when the selected country or month changes.
    map_tail = re.sub(
        r'(?m)^(\s*)returned_objects=\[\],\s*$',
        r'\1returned_objects=[],\n\1key=f"top5_dynamic_map_{country}_{month}",',
        map_tail,
        count=1,
    )

    page_source = '''# Original app.py page, embedded in the team's Dashboard.
# All helper functions and the Top 5 / DBSCAN Folium code are preserved.
import colorsys
import html
import folium
from pathlib import Path
from branca.element import Element
from streamlit_folium import st_folium

'''
    page_source += "\n\n".join(helpers) + "\n\n"
    page_source += '''@st.cache_data(show_spinner="Loading recommendations...")
def _load_original_app_data():
    folder = Path(__file__).resolve().parent
    full_df = pd.read_csv(folder / "full.csv")
    places_df = pd.read_csv(folder / "places_with_clusters.csv")
    return full_df, places_df

st.title("🌍 Tourism Explorer")
st.caption("Find destinations ranked by the existing Tourism Climate Index (TCI).")
try:
    full, places_data = _load_original_app_data()
except Exception as exc:
    st.error(f"Could not load full.csv and places_with_clusters.csv: {exc}")
    st.stop()

'''
    page_source += main_core
    page_source += '''try:
    places = places_data.copy()
'''
    page_source += map_tail
    page_source = page_source.rstrip() + "\n"

    # Ensure code we will insert does not contain a syntax/indent error.
    validate(ast.parse('if True:\n' + textwrap.indent(page_source, '    ')) is not None,
             "Generated page has a syntax error")
    return page_source


def update_dashboard(source: str, page_source: str) -> str:
    # An earlier attempt imported a separate module; this version does not need it.
    source = re.sub(
        r'(?m)^from recommendations_page import render as render_recommendations\s*\n',
        '', source,
    )

    # Replace only the target page; preserve page 4 and the rest of the dashboard.
    target_pattern = (
        r'(?ms)^elif page == "📍 Spatial Clustering & Map Explorer":\n'
        r'.*?(?=^# ==========================================\n# PAGE 4: INTERACTIVE ITINERARY PLANNER)'
    )
    replacement = (
        'elif page == "📍 Spatial Clustering & Map Explorer":\n'
        + textwrap.indent(page_source, '    ') + '\n'
    )
    modified, count = re.subn(target_pattern, lambda _: replacement, source, count=1)
    validate(count == 1, "Can't identify page boundary in dashboard.py. No files changed.")

    # Fix the file finder using name-only search, and avoid a path specific to a teammate's PC.
    modified = modified.replace(
        "smart_read_csv('cleaned_data/attractions_with_clusters.csv')",
        "smart_read_csv('attractions_with_clusters.csv')",
    )
    modified = re.sub(
        r'''(?m)^ROOT_DIR\s*=\s*r?["']C:\\Users\\.*$''',
        'ROOT_DIR = os.path.dirname(os.path.abspath(__file__))',
        modified,
    )
    ast.parse(modified, filename=str(DASHBOARD))
    return modified


def update_requirements(source: str) -> str:
    packages = ("streamlit", "streamlit-folium", "folium", "pandas",
                "numpy", "matplotlib", "seaborn", "requests")
    existing = {line.strip().lower().split('==')[0].split('>=')[0]
                for line in source.splitlines() if line.strip() and not line.startswith('#')}
    missing = [pkg for pkg in packages if pkg not in existing]
    return source.rstrip() + ("\n" + "\n".join(missing) if missing else "") + "\n"


def main():
    validate(APP.exists() and DASHBOARD.exists(),
             "Put this script in the same project folder as app.py and dashboard.py")
    original_app = APP.read_text(encoding="utf-8-sig")
    dashboard = DASHBOARD.read_text(encoding="utf-8-sig").replace('\r\n', '\n')
    page = build_page(original_app)
    updated_dashboard = update_dashboard(dashboard, page)

    backup = DASHBOARD.with_name(DASHBOARD.name + '.before_app_swap.bak')
    if not backup.exists():
        shutil.copy2(DASHBOARD, backup)
    DASHBOARD.write_text(updated_dashboard, encoding="utf-8")

    if REQUIREMENTS.exists():
        req = REQUIREMENTS.read_text(encoding="utf-8-sig")
        updated = update_requirements(req)
        if updated != req:
            req_backup = REQUIREMENTS.with_name('requirements.txt.before_app_swap.bak')
            if not req_backup.exists():
                shutil.copy2(REQUIREMENTS, req_backup)
            REQUIREMENTS.write_text(updated, encoding="utf-8")

    print('SUCCESS: app.py interface now replaces Spatial Clustering & Map Explorer.')
    print('Only dashboard.py was changed; app.py is untouched.')
    print('No recommendations_page.py import needed.')
    print(f'Backup: {backup.name}')
    print('Run: python -m streamlit run dashboard.py')


if __name__ == '__main__':
    main()
