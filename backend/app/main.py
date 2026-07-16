from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import os

from .database import get_db, engine
from .models import Base, User, Website, DefacementAlert
from .schemas import UserRegister, WebsiteCreate
from .auth import create_access_token, get_current_active_user, require_role
from .monitoring import monitor_website
from .middleware import SecurityHeadersMiddleware, RateLimitMiddleware
from .logging_config import logger

Base.metadata.create_all(bind=engine)

if os.getenv("SECRET_KEY") is None:
    logger.warning(
        "SECRET_KEY is not set — using an insecure default. "
        "Set a strong SECRET_KEY environment variable before deploying to production."
    )

app = FastAPI(title="Website Security Platform", version="1.0.0")

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    limits={
        "/api/auth/login": (5, 60),      # 5 attempts per minute per IP
        "/api/auth/register": (10, 60),
    },
    default_limit=(100, 60),
)
# "*" combined with allow_credentials=True is a known CORS misconfiguration:
# it makes the browser send credentials to (and Starlette reflect) any
# origin that asks. Now that nginx proxies the frontend and API onto the
# same origin, cross-origin calls should be rare — this allow-list is a
# safety net for local dev / calling the API directly.
_default_origins = "http://localhost,http://localhost:80,http://localhost:5173,http://127.0.0.1"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
async def root():
    return {"message": "Website Security Platform API", "status": "running"}


@app.post("/api/auth/register")
async def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.email)
    ).first()
    if existing:
        logger.info(f"Registration rejected: username/email already exists (username={payload.username})")
        raise HTTPException(status_code=400, detail="Username or email already registered")

    user = User(username=payload.username, email=payload.email)
    user.set_password(payload.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"New user registered: user_id={user.id} username={user.username}")
    return {"message": "User created successfully", "user_id": user.id}


@app.post("/api/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.verify_password(form_data.password):
        logger.info(f"Failed login attempt for username={form_data.username}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    logger.info(f"Successful login: user_id={user.id} username={user.username}")
    access_token = create_access_token(data={"sub": user.username, "user_id": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@app.post("/api/websites")
async def add_website(
    payload: WebsiteCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    existing = db.query(Website).filter(Website.url == payload.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Website already being monitored")

    website = Website(
        url=payload.url,
        name=payload.name,
        description=payload.description,
        user_id=current_user.id,
    )
    db.add(website)
    db.commit()
    db.refresh(website)
    return {
        "message": "Website added successfully",
        "website": {"id": website.id, "url": website.url, "name": website.name},
    }


@app.get("/api/websites")
async def get_websites(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    websites = db.query(Website).filter(Website.user_id == current_user.id).all()
    return [
        {
            "id": w.id,
            "url": w.url,
            "name": w.name,
            "status": w.status,
            "last_scan": w.last_scan,
        }
        for w in websites
    ]


@app.get("/api/websites/{website_id}/scan")
async def scan_website(
    website_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    website = db.query(Website).filter(
        Website.id == website_id, Website.user_id == current_user.id
    ).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    website.last_scan = datetime.now(timezone.utc)
    db.commit()

    # Background task opens its own DB session internally.
    background_tasks.add_task(monitor_website, website_id, website.url)
    return {"message": "Scan initiated", "website_id": website_id}


@app.get("/api/alerts")
async def get_alerts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    website_ids = [w.id for w in db.query(Website).filter(Website.user_id == current_user.id).all()]
    alerts = (
        db.query(DefacementAlert)
        .filter(DefacementAlert.website_id.in_(website_ids))
        .order_by(DefacementAlert.detected_at.desc())
        .limit(20)
        .all()
    )
    website_names = {w.id: w.name for w in db.query(Website).filter(Website.id.in_(website_ids)).all()}
    return [
        {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "severity": a.severity,
            "status": a.status,
            "website_name": website_names.get(a.website_id, "Unknown"),
            "detected_at": a.detected_at,
        }
        for a in alerts
    ]


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    websites = db.query(Website).filter(Website.user_id == current_user.id).all()
    website_ids = [w.id for w in websites]
    total_alerts = db.query(DefacementAlert).filter(
        DefacementAlert.website_id.in_(website_ids)
    ).count()
    critical_alerts = db.query(DefacementAlert).filter(
        DefacementAlert.website_id.in_(website_ids),
        DefacementAlert.severity == "critical",
    ).count()
    return {
        "total_websites": len(websites),
        "active_websites": sum(1 for w in websites if w.status == "active"),
        "total_alerts": total_alerts,
        "critical_alerts": critical_alerts,
    }


@app.get("/api/admin/users")
async def list_all_users(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin-only: list all registered users. Demonstrates RBAC enforcement —
    the `role` field on User is actually checked here, not just stored."""
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "email": u.email, "role": u.role} for u in users]


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
