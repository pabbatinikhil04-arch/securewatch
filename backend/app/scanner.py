import json
import httpx
from sqlalchemy.orm import Session
from .models import ScanResult


async def scan_website(website_id: int, url: str, db: Session):
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            result = ScanResult(
                website_id=website_id,
                scan_type="full",
                status="completed",
                findings=json.dumps({"url": url, "status_code": response.status_code}),
            )
            db.add(result)
            db.commit()
    except Exception as e:
        result = ScanResult(
            website_id=website_id,
            scan_type="full",
            status="error",
            findings=str(e),
        )
        db.add(result)
        db.commit()
