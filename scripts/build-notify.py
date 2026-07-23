#!/usr/bin/env python3
"""Build notification message for KH CRM weekly report push."""
import argparse, json, os, sys
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('--start', required=True)
parser.add_argument('--end', required=True)
parser.add_argument('--doc-id', default='')
args = parser.parse_args()

doc_id = args.doc_id
doc_url = f"https://ritfitsports.feishu.cn/docx/{doc_id}" if doc_id else "(unavailable)"

week = datetime.strptime(args.end, '%Y-%m-%d')
week_str = f"W{week.isocalendar()[1]:02d}"

# Read klaviyo data
total_rev = 0
camp_rev = 0
flow_rev = 0
try:
    with open('scripts/klaviyo-data.json') as f:
        data = json.load(f)
    for c in data.get('campaigns', []):
        cv = c.get('attributes', {}).get('conversion_value', 0) or 0
        camp_rev += cv
    for fl in data.get('flows', []):
        fv = fl.get('attributes', {}).get('conversion_value', 0) or 0
        flow_rev += fv
    total_rev = camp_rev + flow_rev
except Exception:
    pass

# Read GMV
gmv = 0
try:
    with open('scripts/shopify-gmv.txt') as f:
        gmv = float(f.read().strip() or 0)
except Exception:
    pass

# Format
fmt_rev = f"${total_rev:,.0f}"
fmt_camp = f"${camp_rev:,.0f}"
fmt_flow = f"${flow_rev:,.0f}"
fmt_gmv = f"${gmv:,.0f}"

msg = f"""**KH CRM {week_str} Report Published**
Period: {args.start} ~ {args.end}

**Core Data:**
- EDM Total Revenue: {fmt_rev}
- Campaign Revenue: {fmt_camp} | Flow Revenue: {fmt_flow}
- Shopify GMV: {fmt_gmv}

[Full Report]({doc_url})
"""

os.makedirs('/tmp', exist_ok=True)
with open('/tmp/kh_msg.md', 'w') as f:
    f.write(msg)

print(f"Notification message written: {len(msg)} chars")
