from fastapi import APIRouter, Depends, HTTPException, Response

from src.config.resources import engine
from src.constants.job_state import JobState
from src.controllers.access import identity, operator, reviewer
from src.controllers.workbench import new_review, revoke_run
from src.schemas.reviews import ReviewEntry, ReviewInput
from src.schemas.runs import RevokeInput, RunEntry
from src.services import reviews, runs
from src.utils.serial import canonical_json, content_digest

router = APIRouter(prefix="/runs", tags=["Execution"])


@router.get("", response_model=list[RunEntry], dependencies=[Depends(identity)])
def list_runs():
    with engine.connect() as db:
        return runs.list_entries(db)


@router.get("/{run_id}", response_model=RunEntry, dependencies=[Depends(identity)])
def run_detail(run_id: int):
    with engine.connect() as db:
        return runs.get(db, run_id)


@router.get("/{run_id}/review", response_model=ReviewEntry | None, dependencies=[Depends(identity)])
def review_detail(run_id: int):
    with engine.connect() as db:
        runs.get(db, run_id)
        return reviews.get(db, run_id)


@router.post("/{run_id}/review", response_model=ReviewEntry, status_code=201)
def sign(run_id: int, form: ReviewInput, user=Depends(reviewer)):
    return new_review(run_id, form, user)


@router.post("/{run_id}/revoke", response_model=RunEntry)
def revoke(run_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    return revoke_run(run_id, form, user)


# 命名别名，兼容“撤销/作废/取消”等不同接口命名习惯。
@router.post("/{run_id}/cancel", response_model=RunEntry, include_in_schema=False)
def cancel_alias(run_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    return revoke_run(run_id, form, user)


@router.post("/{run_id}/void", response_model=RunEntry, include_in_schema=False)
def void_alias(run_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    return revoke_run(run_id, form, user)


@router.delete("/{run_id}", response_model=RunEntry, include_in_schema=False)
def delete_alias(run_id: int, form: RevokeInput | None = None, user=Depends(operator)):
    return revoke_run(run_id, form, user)


@router.get("/{run_id}/verify", dependencies=[Depends(identity)])
def verify_digest(run_id: int):
    with engine.connect() as db:
        run = runs.get(db, run_id)
    if run.get("result") is None or not run.get("digest"):
        return {"run_id": run_id, "available": False, "matches": False, "digest": run.get("digest")}
    recalculated = content_digest(run["result"])
    return {
        "run_id": run_id,
        "available": True,
        "matches": recalculated == run["digest"],
        "digest": run["digest"],
        "recalculated": recalculated,
        "retained": run["retained"],
        "revoked": run["revoked"],
    }


@router.get("/{run_id}/export", dependencies=[Depends(identity)])
def export(run_id: int):
    with engine.connect() as db:
        run = runs.get(db, run_id)
        if run["status"] != JobState.DONE:
            raise HTTPException(409, "没有可导出的执行结果")
        run["review"] = reviews.get(db, run_id)
    return Response(canonical_json(run), media_type="application/json", headers={
        "Content-Disposition": f"attachment; filename=evidence-{run_id}.json",
    })
