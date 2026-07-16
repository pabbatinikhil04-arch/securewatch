import re
from typing import Tuple, List, Dict

PATTERNS = [
    (r'(hacked|defaced|owned|pwnd)', 0.5),
    (r'(by\s+\w+\s+hacker)', 0.4),
    (r'(!{3,})', 0.2),
]


def detect_defacement(page_title: str, body_text: str, url: str) -> Tuple[float, List[Dict]]:
    issues = []
    score = 0.0
    page_title = page_title or ""
    body_text = body_text or ""
    for pattern, weight in PATTERNS:
        if re.search(pattern, page_title, re.IGNORECASE):
            issues.append({"type": "suspicious_title", "pattern": pattern})
            score += weight
        if re.search(pattern, body_text[:1000], re.IGNORECASE):
            issues.append({"type": "suspicious_content", "pattern": pattern})
            score += weight * 0.5
    return min(score, 1.0), issues
