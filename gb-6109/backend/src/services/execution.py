import logging
from time import time

from sqlalchemy import select, update

from src.config.resources import engine
from src.constants.job_state import JobState
from src.domain import scenario
from src.models.cases import cases
from src.models.runs import runs
from src.services.audit import record
from src.utils.serial import content_digest

logger = logging.getLogger(__name__)

# 仍允许 worker 写入最终结果的状态；一旦撤销成 revoked，条件更新命中 0 行，迟到结果丢弃。
ACTIVE_STATES = (JobState.QUEUED, JobState.RUNNING)


def service_one():
    # 认领事务尽量短：锁定排队批次、冻结资料并置为 running 后立即提交，
    # 这样撤销不必等待演练跑完，也能与撤销/签核在行锁上正确串行。
    with engine.begin() as db:
        statement = (
            select(runs).where(runs.c.status == JobState.QUEUED).order_by(runs.c.id)
            .limit(1).with_for_update(skip_locked=True)
        )
        task = db.execute(statement).mappings().first()
        if task is None:
            return False
        run_id = task["id"]
        payload = task["payload"]
        if payload is None:
            # 兼容加入批次快照列之前创建的旧记录。
            payload = db.scalar(select(cases.c.payload).where(cases.c.id == task["case_id"]))
        parameter = task["parameter"]
        db.execute(update(runs).where(runs.c.id == run_id).values(status=JobState.RUNNING))

    try:
        result = scenario.run(payload, parameter, None)
        output = {"status": JobState.DONE, "result": result, "digest": content_digest(result)}
    except Exception as exc:
        # 让认领事务之外的失败由 worker 调用 fail() 落库。
        raise JobFailure(run_id, exc) from exc
    complete(run_id, output)
    return True


class JobFailure(Exception):
    def __init__(self, run_id, cause):
        super().__init__(str(cause))
        self.run_id = run_id
        self.cause = cause


def fail(job_failure):
    cause = job_failure.cause
    if isinstance(cause, (ValueError, TypeError, KeyError, OverflowError)):
        reason = str(cause) or "输入资料或批次参数不符合要求"
    else:
        reason = "处理失败，请检查 worker 日志"
    with engine.begin() as db:
        # 条件更新：若批次已被撤销，则迟到失败同样不得覆盖作废结论。
        changed = db.execute(
            update(runs)
            .where(runs.c.id == job_failure.run_id, runs.c.status.in_(ACTIVE_STATES))
            .values(status=JobState.FAILED, failure=reason[:320], finished_at=int(time()))
        )
        if changed.rowcount:
            record(db, JobState.FAILED, "worker", "run", job_failure.run_id)


def finish(db, run_id, output):
    """带状态守卫的落库：只接受排队/在跑批次的结果，撤销后的迟到结果不入库。"""
    changed = db.execute(
        update(runs)
        .where(runs.c.id == run_id, runs.c.status.in_(ACTIVE_STATES))
        .values(**output, finished_at=int(time()))
    )
    if changed.rowcount:
        record(db, str(output["status"]), "worker", "run", run_id)
    return changed.rowcount


def complete(run_id, output):
    with engine.begin() as db:
        return finish(db, run_id, output)
