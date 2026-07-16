from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from passlib.context import CryptContext
from .database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    websites = relationship("Website", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.hashed_password = pwd_context.hash(password)

    def verify_password(self, password: str):
        return pwd_context.verify(password, self.hashed_password)


class Website(Base):
    __tablename__ = "websites"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    last_scan = Column(DateTime(timezone=True), nullable=True)
    baseline_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="websites")
    scan_results = relationship("ScanResult", back_populates="website", cascade="all, delete-orphan")
    alerts = relationship("DefacementAlert", back_populates="website", cascade="all, delete-orphan")


class ScanResult(Base):
    __tablename__ = "scan_results"
    id = Column(Integer, primary_key=True, index=True)
    scan_type = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")
    findings = Column(Text, nullable=True)
    risk_score = Column(Float, default=0.0)
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    website = relationship("Website", back_populates="scan_results")


class DefacementAlert(Base):
    __tablename__ = "defacement_alerts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="medium")
    status = Column(String(20), default="active")
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    changes = Column(Text, nullable=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    website = relationship("Website", back_populates="alerts")
