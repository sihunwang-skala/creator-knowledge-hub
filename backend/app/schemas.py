from pydantic import BaseModel, Field


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class SettingsIn(BaseModel):
    role_profile: str | None = Field(default=None, max_length=120)
    interests: list[str] | None = Field(default=None, max_length=30)
    default_style: str | None = None
    llm_consent: bool | None = None
    digest_frequency: str | None = Field(default=None, pattern="^(off|daily|weekly)$")


class SubscribeIn(BaseModel):
    channel: str = Field(min_length=1, max_length=300, description="Channel URL, @handle, UC… id, or search text")


class SubscriptionPatch(BaseModel):
    favorite: bool | None = None
    auto_process: bool | None = None
    topics: list[str] | None = Field(default=None, max_length=20)


class QuickAddIn(BaseModel):
    url: str = Field(min_length=3, max_length=500)


class NoteSourceIn(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)


class WebSourceIn(BaseModel):
    url: str
    license: str = ""
    owner: str = ""
    permission_evidence: str = ""
    retention_days: int = 365


class ReevaluateIn(BaseModel):
    license: str | None = None
    permission_evidence: str | None = None
    rights_attested: bool | None = None


class AnalyzeIn(BaseModel):
    style: str = "brief"
    source_id: int | None = None


class NotePatch(BaseModel):
    edited_md: str | None = Field(default=None, max_length=50_000)
    user_notes: str | None = Field(default=None, max_length=50_000)
    favorite: bool | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    collection_id: int | None = None


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SynthIn(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    note_ids: list[int] = Field(min_length=1, max_length=30)


class OptInIn(BaseModel):
    youtube_channel_id: str = Field(max_length=40)
    contact: str = Field(max_length=200)
    allow_transcripts: bool = False
    allow_commercial: bool = False
    transcript_license: str = ""


class TakedownIn(BaseModel):
    video: str
    contact: str = Field(min_length=3, max_length=200)
    reason: str = Field(default="", max_length=2000)
