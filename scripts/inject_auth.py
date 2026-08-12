import os
import glob

# Mappings of page numbers to roles
VIEWER_PAGES = ["10", "20", "22", "24", "43"]
COMMANDER_PAGES = ["50", "99"]

# We will read each page and inject the auth code right below imports (or just at the top)
auth_code_template = """
from utils.auth import require_auth
require_auth({roles})
"""

pages_dir = "pages"
for filepath in glob.glob(os.path.join(pages_dir, "*.py")):
    filename = os.path.basename(filepath)
    prefix = filename.split('_')[0]
    
    if prefix in VIEWER_PAGES:
        roles = "['Viewer', 'Analyst', 'Commander']"
    elif prefix in COMMANDER_PAGES:
        roles = "['Commander']"
    else:
        roles = "['Analyst', 'Commander']"
        
    auth_block = f"""
# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth({roles})
# -----------------------------------
"""
    
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Find the best place to insert: after streamlit import or simply after imports.
    # To be safe, just put it after `import streamlit as st`
    if "import streamlit as st" in content:
        content = content.replace("import streamlit as st", "import streamlit as st\n" + auth_block)
    else:
        content = auth_block + "\n" + content
        
    with open(filepath, 'w') as f:
        f.write(content)
        
print("Auth blocks injected into all pages successfully.")
