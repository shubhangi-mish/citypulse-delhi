from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, HttpUrl, field_validator, model_validator

from app.services import geo
from app.services.events import CATEGORIES as EVENT_CATEGORIES
from app.services.issues import CATEGORIES as ISSUE_CATEGORIES
from app.services.issues import STATUSES as ISSUE_STATUSES


def _clean(text: str) -> str:
    text = text.replace("\x00", "").strip()
    return text if "\n" in text else " ".join(text.split())


Clean = AfterValidator(_clean)


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def in_delhi(self):
        if not geo.in_delhi_region(self.latitude, self.longitude):
            raise ValueError("CityPulse currently covers the Delhi region only.")
        return self


class ProfileCreate(Location):
    name: Annotated[str, Clean] = Field(min_length=1, max_length=80)
    email: EmailStr
    address: Annotated[str, Clean] = Field(min_length=3, max_length=300)
    neighborhood_id: str | None = Field(default=None, max_length=64)



class ProfileLocation(Location):
    address: str = Field(min_length=3, max_length=300)
    neighborhood_id: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    public_visibility: Literal["private", "public"] | None = None
    display_name_opt_in: bool | None = None
    discovery_opt_in: bool | None = None
    area_updates_opt_in: bool | None = None
    profession: str | None = Field(default=None, max_length=60)
    open_to_gigs: bool | None = None
    location: ProfileLocation | None = None


class IssueCreate(Location):
    category: str
    title: Annotated[str, Clean] = Field(min_length=5, max_length=120)
    description: Annotated[str, Clean] = Field(min_length=10, max_length=4000)
    precision: Literal["approximate", "neighborhood"] = "approximate"
    anonymous: bool = False
    concerns_asset_id: str | None = Field(default=None, max_length=64)

    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        if v not in ISSUE_CATEGORIES:
            raise ValueError("Unknown category")
        return v



class CommentCreate(BaseModel):
    body: Annotated[str, Clean] = Field(min_length=1, max_length=2000)


class FollowRequest(BaseModel):
    follow: bool = True


class SupportRequest(BaseModel):
    affected: bool = True


class IssueStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid(cls, v: str) -> str:
        if v not in ISSUE_STATUSES:
            raise ValueError("Unknown status")
        return v


class EventCreate(Location):
    title: str = Field(min_length=5, max_length=140)
    description: str = Field(min_length=20, max_length=5000)
    category: str
    start_time: int = Field(description="epoch ms")
    end_time: int
    venue_name: str = Field(min_length=2, max_length=140)
    venue_address: str = Field(min_length=3, max_length=300)
    organizer_name: str = Field(min_length=2, max_length=100)
    organizer_contact: str = Field(min_length=5, max_length=200)
    organization_name: str | None = Field(default=None, max_length=140)
    is_free: bool = True
    setting: Literal["indoor", "outdoor", "mixed"] = "outdoor"
    accessibility: str | None = Field(default=None, max_length=300)
    registration_url: HttpUrl | None = None
    attestation: bool

    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        if v not in EVENT_CATEGORIES:
            raise ValueError("Unknown category")
        return v

    @model_validator(mode="after")
    def check(self):
        if not self.attestation:
            raise ValueError("Organizer attestation is required: confirm this is a genuine event.")
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time.")
        return self


class ParticipateRequest(BaseModel):
    role: Literal["interested", "going", "volunteer"] | None = "going"


class EventUpdateCreate(BaseModel):
    body: str = Field(min_length=3, max_length=2000)


class OperatorLogin(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class CaseCreate(BaseModel):
    title: str = Field(min_length=5, max_length=140)
    case_type: str = Field(default="community_issue", max_length=40)
    issue_ids: list[str] = Field(min_length=1, max_length=20)


class ActionCreate(BaseModel):
    action_type: str
    description: str = Field(min_length=3, max_length=1000)
    payload: dict = Field(default_factory=dict)


class ActionReject(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ActionOutcome(BaseModel):
    outcome: str = Field(min_length=3, max_length=1000)
    success: bool


class CaseStatus(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]


class AnalyzeIssue(BaseModel):
    issue_id: str


class AnalyzeEvent(BaseModel):
    event_id: str


class ImpactRequest(BaseModel):
    entity_id: str
