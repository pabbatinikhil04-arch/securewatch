import hashlib
import json
import httpx
from bs4 import BeautifulSoup
from .database import SessionLocal
from .models import Website, DefacementAlert
from .detection import detect_defacement


async def monitor_website(website_id: int, url: str):
    """Runs as a background task, so it opens its own DB session
    instead of reusing the request-scoped one (which is closed by
    the time this runs)."""
    db = SessionLocal()
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return

        if website.baseline_hash is None:
            website.baseline_hash = content_hash
            website.status = "active"
            db.commit()
            return

        if content_hash != website.baseline_hash:
            soup = BeautifulSoup(content, "html.parser")
            page_title = soup.title.string if soup.title else ""
            score, issues = detect_defacement(page_title, content, url)
            if score > 0.5:
                alert = DefacementAlert(
                    website_id=website_id,
                    title="Defacement Detected",
                    description=f"AI detected changes with score {score:.2f}",
                    severity="high" if score > 0.8 else "medium",
                    changes=json.dumps(issues),
                )
                db.add(alert)
            website.baseline_hash = content_hash
            website.status = "active"
            db.commit()
    except Exception as e:
        print(f"Error monitoring {url}: {e}")
        website = db.query(Website).filter(Website.id == website_id).first()
        if website:
            website.status = "error"
            db.commit()
    finally:
        db.close()
