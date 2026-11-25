import { States } from "../../constants/states.js";
import { el } from "../../utils/dom.js";

export function status(value) {
  return el("span", {class: `status state-${value}`, "data-state": value}, States[value] || value);
}

// 可见配方根用它明确标出“保留 / 作废”的批次。
export function retentionVerdict(run) {
  if (run?.verdict) return run.verdict;
  if (run?.review || run?.retained) return "retained";
  if (run?.status === "revoked" || run?.revoked || run?.voided) return "voided";
  return "pending";
}

export function retentionBadge(run) {
  const verdict = retentionVerdict(run);
  if (verdict === "retained") {
    return el("span", {
      class: "retention retained", "data-retention": "retained", "data-testid": "retention-retained",
    }, "保留");
  }
  if (verdict === "voided") {
    return el("span", {
      class: "retention voided", "data-retention": "voided", "data-testid": "retention-voided",
    }, "作废");
  }
  const busy = run?.status === "queued" || run?.status === "running";
  return el("span", {class: "retention pending", "data-retention": "pending"}, busy ? "演练中" : "待签核");
}
