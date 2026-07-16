from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re


class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str) -> str:
        if not (3 <= len(v) <= 50):
            raise ValueError("Username must be between 3 and 50 characters")
        if not re.fullmatch(r"[A-Za-z0-9_]+", v):
            raise ValueError("Username may only contain letters, numbers, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters long")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("Password must contain both letters and numbers")
        return v


class WebsiteCreate(BaseModel):
    url: str
    name: str
    description: Optional[str] = None

    @field_validator("url")
    @classmethod
    def url_format(cls, v: str) -> str:
        if not re.match(r"^https?://", v):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 500:
            raise ValueError("URL is too long")
        return v

    @field_validator("name")
    @classmethod
    def name_format(cls, v: str) -> str:
        if not (1 <= len(v) <= 100):
            raise ValueError("Name must be between 1 and 100 characters")
        return v
