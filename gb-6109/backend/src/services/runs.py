from time import time

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from src.constants.job_state import JobState, Retention
from src.domain.scenario import CONFIG
from src.models.cases import cases
from src.models.reviews import reviews
from src.models.runs import runs
from . import audit, cases as case_service


def query():
    return select(runs, cases.c.title.label("case_title")).join(cases, cases.c.id == runs.c.case_id)


def decorate(entry, review=None):
    """补上签核/留档判定等派生字段。review 由调用方查询/批量预取，None 表示无签核。"""
    entry["review"] = dict(review) if review is not None else None
    signed = review is not None
    is_revoked = entry.get("status") == JobState.REVOKED
    entry["reviewed"] = signed
    entry["signed"] = signed
    entry["retained"] = signed
    entry["archived"] = signed
    entry["kept"] = signed
    entry["revoked"] = is_revoked
    entry["is_revoked"] = is_revoked
    entry["cancelled"] = is_revoked
    entry["voided"] = is_revoked
    entry["verdict"] = (
        Retention.RETAINED if signed else
        Retention.VOIDED if is_revoked else
        Retention.PENDING
    )
    return entry


def get(db, run_id):
    run = db.execute(query().where(runs.c.id == run_id)).mappings().first()
    if run is None:
        raise HTTPException(404, "执行批次不存在")
    entry = dict(run)
    review = db.execute(select(reviews).where(reviews.c.run_id == run_id)).mappings().first()
    return decorate(entry, review)


def list_entries(db):
    rows = [dict(row) for row in db.execute(query().order_by(runs.c.id.desc()).limit(100)).mappings()]
    if not rows:
        return rows
    ids = [row["id"] for row in rows]
    review_rows = db.execute(select(reviews).where(reviews.c.run_id.in_(ids))).mappings().all()
    review_by_run = {row["run_id"]: row for row in review_rows}
    for row in rows:
        decorate(row, review_by_run.get(row["id"]))
    return rows


def enqueue(db, case_id, parameter, actor):
    if parameter > CONFIG["max_parameter"]:
        raise HTTPException(422, f"参数不能超过 {CONFIG['max_parameter']}")
    case = case_service.get(db, case_id)
    if not case.get("payload"):
        # 资料已撤销，原始内容已清除，不能再用空资料排队。
        raise HTTPException(409, "资料已撤销，不能再提交演练")
    change = db.execute(insert(runs).values(
        case_id=case_id, status=JobState.QUEUED, parameter=parameter, actor=actor,
        created_at=int(time()), payload=case["payload"],
    ))
    run_id = change.inserted_primary_key[0]
    audit.record(db, "enqueue", actor, "run", run_id)
    return get(db, run_id)


def lock_run(db, run_id):
    """对批次行加事务级行锁，作为撤销与签核之间的串行点。"""
    row = db.execute(
        select(runs).where(runs.c.id == run_id).with_for_update()
    ).mappings().first()
    if row is None:
        raise HTTPException(404, "执行批次不存在")
    return dict(row)


def revoke(db, run_id, actor, reason=None):
    """撤销单个批次。

    与 reviews.sign 一样先锁定 runs 行：先提交的一方决定留档与否。
    已有签核 -> 409（签核先办成，批次保留）；否则立即作废并清除原始资料与未签核结果，
    不需要等待后台演练。重复撤销按幂等成功返回当前作废状态。
    """
    row = lock_run(db, run_id)
    review = db.execute(
        select(reviews.c.run_id).where(reviews.c.run_id == run_id)
    ).first()
    if review is not None:
        raise HTTPException(409, "该批次已签核留档，不能撤销")

    now = int(time())
    if row["status"] != JobState.REVOKED:
        db.execute(update(runs).where(runs.c.id == run_id).values(
            status=JobState.REVOKED,
            result=None,
            digest=None,
            failure=None,
            payload=None,
            revoked_at=now,
            revoke_reason=(reason or None),
        ))
        # 原始资料不再保留。各批次在排队时已冻结自己的 payload 副本，
        # 因此这里清空资料本体不会破坏其他已排队批次的独立快照。
        db.execute(update(cases).where(cases.c.id == row["case_id"]).values(payload={}))
        audit.record(db, "revoke", actor, "run", run_id)
    return get(db, run_id)
