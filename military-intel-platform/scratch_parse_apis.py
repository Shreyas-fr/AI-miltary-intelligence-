import re

with open('/Users/shreyasdivekar/.gemini/antigravity-ide/brain/cb49c5c5-3e17-43b8-b868-3fa5e108a73c/.system_generated/steps/335/content.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

categories_of_interest = ['Anti-Malware', 'Data Validation', 'Development', 'Geocoding', 'Government', 'Machine Learning', 'News', 'Open Data', 'Security', 'Tracking']
current_cat = None
apis = []

for line in lines:
    if line.startswith('### '):
        current_cat = line[4:].strip()
    elif line.startswith('|') and current_cat in categories_of_interest:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 6 and 'API' not in parts[1] and '---' not in parts[1]:
            # parts: ['', 'API', 'Description', 'Auth', 'HTTPS', 'CORS', '']
            api_name = parts[1]
            desc = parts[2]
            auth = parts[3]
            https = parts[4]
            
            # Extract URL from markdown link if present
            url = api_name
            m = re.search(r'\[(.*?)\]\((.*?)\)', api_name)
            if m:
                api_name = m.group(1)
                url = m.group(2)
            
            if auth.lower() == 'no' and https.lower() == 'yes':
                apis.append({'Category': current_cat, 'Name': api_name, 'Desc': desc, 'URL': url})

import json
print(json.dumps(apis, indent=2))
