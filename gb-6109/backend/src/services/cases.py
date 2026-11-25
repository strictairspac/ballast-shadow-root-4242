from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from src.constants.job_state import JobState
from src.domain import scenario
from src.models.cases import cases
from src.models.reviews import reviews
from src.models.runs import runs
from .audit import record


def get(db, case_id):
    entry = db.execute(select(cases).where(cases.c.id == case_id)).mappings().first()
    if entry is None:
        raise HTTPException(404, "资料不存在")
    return dict(entry)


def list_entries(db):
    return [dict(row) for row in db.execute(select(cases).order_by(cases.c.id.desc()).limit(100)).mappings()]


def create(db, data, actor):
    validator = getattr(scenario, "validate", None)
    if validator is not None:
        try:
            validator(data.payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    change = db.execute(insert(cases).values(**data.model_dump(), code=f"CASE-{uuid4().hex[:12].upper()}", created_by=actor))
    case_id = change.inserted_primary_key[0]
    record(db, "create_case", actor, "case", case_id)
    return get(db, case_id)


def revoke(db, case_id, actor, reason=None):
    """撤销整条试配资料：清空原始资料，作废全部未签核批次。

    已先办成签核的批次逐批保留（结果与摘要不动，仍可核对当时配方）。
    通过对 runs 行加锁，与逐批签核串行，落实“先办成的一方决定该批”。
    """
    get(db, case_id)
    run_ids = list(db.execute(
        select(runs.c.id).where(runs.c.case_id == case_id)
        .order_by(runs.c.id).with_for_update()
    ).scalars())

    retained_runs = list(db.execute(
        select(reviews.c.run_id).where(reviews.c.run_id.in_(run_ids or [-1]))
    ).scalars()) if run_ids else []
    retained_set = set(retained_runs)
    revoked_runs = [run_id for run_id in run_ids if run_id not in retained_set]

    if revoked_runs:
        from time import time
        db.execute(update(runs).where(runs.c.id.in_(revoked_runs)).values(
            status=JobState.REVOKED,
            result=None,
            digest=None,
            failure=None,
            payload=None,
            revoked_at=int(time()),
            revoke_reason=(reason or None),
        ))

    # 原始资料不再保留；已签核批次的结果/摘要独立保留，仍可核对。
    db.execute(update(cases).where(cases.c.id == case_id).values(payload={}))
    record(db, "revoke_case", actor, "case", case_id)

    entry = get(db, case_id)
    entry["revoked_runs"] = revoked_runs
    entry["retained_runs"] = sorted(retained_set)
    return entry
