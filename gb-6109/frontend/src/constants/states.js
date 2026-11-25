export const States = Object.freeze({
  queued: "等待执行",
  running: "正在演练",
  done: "已完成",
  failed: "执行失败",
  revoked: "已作废",
});

export const Actions = Object.freeze({
  create_case: "登记资料",
  enqueue: "提交执行",
  done: "执行完成",
  failed: "执行失败",
  review: "复核签署",
  revoke: "撤销批次",
  revoke_case: "撤销资料",
});

// 留档判定：先签核 -> 保留；先撤销 -> 作废；尚未决出 -> 待签核/演练中。
export const Retention = Object.freeze({
  retained: "保留",
  voided: "作废",
  pending: "待签核",
});
