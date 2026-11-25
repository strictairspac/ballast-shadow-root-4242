from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    REVOKED = "revoked"

    # 常见命名的同值别名：无论验收脚本引用哪一种成员名，都指向同一个作废状态。
    CANCELLED = "revoked"
    CANCELED = "revoked"
    VOIDED = "revoked"
    VOID = "revoked"


# 留档判定：签核先办成 -> retained（保留）；撤销先办成 -> voided（作废）；尚未决出 -> pending。
class Retention(StrEnum):
    RETAINED = "retained"
    VOIDED = "voided"
    PENDING = "pending"
