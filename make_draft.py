from pathlib import Path
from datetime import datetime

post = """AI automation isn't replacing founders - it's giving them leverage.

Most solopreneurs waste 3-4 hours daily on repetitive tasks.
Email replies. Social posts. Status updates.

I built a Silver Tier AI system that handles all of this.
One vault. Multiple watchers. Zero manual routing.

The result: I focus on clients. The AI handles the noise.

Want to know how it works? Drop a comment below.

#AIAutomation #FounderProductivity #SolopreneurLife"""

ts = datetime.now().strftime('%Y%m%d_%H%M')
fname = f'LI_{ts}_manual_draft.md'
content = f"""---
type: linkedin_post
created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
status: draft
---

{post}
"""

Path('silver_tier/LinkedIn_Drafts').mkdir(exist_ok=True)
Path('silver_tier/Pending_Approval').mkdir(exist_ok=True)
Path(f'silver_tier/LinkedIn_Drafts/{fname}').write_text(content, encoding='utf-8')
Path(f'silver_tier/Pending_Approval/{fname}').write_text(content, encoding='utf-8')
print(f"Draft saved: {fname}")
print("Check: silver_tier/Pending_Approval/")
