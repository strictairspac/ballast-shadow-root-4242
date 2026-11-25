from pydantic import BaseModel, Field

from src.constants.job_state import JobState
from src.schemas.reviews import ReviewEntry


class RunInput(BaseModel):
    parameter: int = Field(strict=True, ge=1)


class RevokeInput(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class RunEntry(BaseModel):
    id: int
    case_id: int
    case_title: str
    status: JobState
    parameter: int
    actor: str
    created_at: int
    finished_at: int | None
    result: dict | None
    failure: str | None
    digest: str | None
    # 撤销/留档判定的只读派生字段（均有默认值，兼容旧调用与旧数据）。
    review: ReviewEntry | None = None
    reviewed: bool = False
    signed: bool = False
    retained: bool = False
    archived: bool = False
    kept: bool = False
    revoked: bool = False
    is_revoked: bool = False
    cancelled: bool = False
    voided: bool = False
    verdict: str | None = None
    revoked_at: int | None = None
    revoke_reason: str | None = None
