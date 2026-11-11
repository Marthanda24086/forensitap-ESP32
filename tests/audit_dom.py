import re

with open('dashboard/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

with open('dashboard/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# 1. Find duplicate IDs
ids = re.findall(r'id=["\']([^"\']+)["\']', html)
id_counts = {}
for i in ids:
    id_counts[i] = id_counts.get(i, 0) + 1
duplicates = {k: v for k, v in id_counts.items() if v > 1}
print('Duplicate IDs in HTML:', duplicates)

# 2. Check getElementById in JS
get_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js))
missing_ids = [gid for gid in get_ids if gid not in id_counts]
print('Missing IDs referenced by JS:', missing_ids)

# 3. Check dynamic getElementById constructed in JS
dynamic_get_ids = re.findall(r'getElementById\(`([^`]+)`\)', js)
print('\nTabs and Views verification:')
tabs = ['dashboard', 'radar', 'chain', 'architecture', 'overview']
for t in tabs:
    btn_id = f"tabBtn{t.capitalize()}"
    view_id = f"view{t.capitalize()}"
    has_btn = btn_id in id_counts
    has_view = view_id in id_counts
    print(f"  Tab '{t}': button '{btn_id}'={has_btn}, view '{view_id}'={has_view}")

# 4. Check onclick handlers in HTML
onclicks = set(re.findall(r'onclick=["\']([^"\']+)["\']', html))
print('\nUnique onclick handlers in HTML:')
for oc in sorted(onclicks):
    func_name = oc.split('(')[0].strip()
    # Check if func_name is defined in JS
    func_defined = bool(re.search(r'(function\s+' + func_name + r'\b|' + func_name + r'\s*=\s*(?:async\s*)?function|' + func_name + r'\s*=\s*\([^)]*\)\s*=>)', js))
    print(f"  {oc:40} -> Defined in JS: {func_defined}")
