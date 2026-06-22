from pydantic import BaseModel
from typing import Optional, List


class RegisterIn(BaseModel):
    email: str
    name: str = ""
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    approved: bool
    permissions: List[str] = []

    class Config:
        from_attributes = True


class PermissionsIn(BaseModel):
    permissions: List[str] = []


class SheetIn(BaseModel):
    name: str = ""
    csv_url: str
    price_default: str = "open"
    active: bool = True


class SheetOut(BaseModel):
    id: int
    name: str
    csv_url: str
    price_default: str
    active: bool
    last_synced: str
    row_count: int

    class Config:
        from_attributes = True


class SettingsIn(BaseModel):
    ig_token: Optional[str] = None
    ig_business_id: Optional[str] = None
    sync_minutes: Optional[int] = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CreatorIn(BaseModel):
    mhs_id: str = ""
    name: str
    handle: str = ""
    link: str = ""
    followers: int = 0
    niche: str = ""
    tier: str = ""
    language: str = ""
    location: str = ""
    gender: str = ""
    platform: str = "Instagram"
    added_by: str = ""
    reel_cost: int = 0
    video_cost: int = 0
    story_cost: int = 0
    engagement: float = 0
    price_bucket: str = "open"
    reel_links: str = ""


class CreatorOut(CreatorIn):
    id: int

    class Config:
        from_attributes = True


class ExecutionIn(BaseModel):
    creator_id: Optional[int] = None
    creator_name: str = ""
    brand: str
    brand_category: str = ""
    campaign: str = ""
    stage: str = "Shortlisted"
    month: str = ""
    reels: int = 0
    stories: int = 0
    budget: int = 0
    deliv: int = 0
    status: str = "Active"
    brief: bool = False
    content: bool = False
    posted: bool = False
    invoice: bool = False
    paid: bool = False
    notes: str = ""


class ExecutionOut(ExecutionIn):
    id: int

    class Config:
        from_attributes = True


class FinanceIn(BaseModel):
    date: str = ""
    kind: str = "income"
    category: str = ""
    brand: str = ""
    creator_name: str = ""
    amount: int = 0
    account: str = ""
    status: str = "pending"
    ref: str = ""
    notes: str = ""


class FinanceOut(FinanceIn):
    id: int

    class Config:
        from_attributes = True
