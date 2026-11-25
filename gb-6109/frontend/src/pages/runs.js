import { api } from "../api/workbench.js";
import { canRevoke, revokeButton } from "../components/common/revoke.js";
import { empty, pageHeading, section } from "../components/common/panel.js";
import { retentionBadge, status } from "../components/common/status.js";
import { table } from "../components/common/table.js";
import { poll } from "../hooks/poll.js";
import { el } from "../utils/dom.js";
import { time } from "../utils/format.js";

function reportState(run, user, onRevoked) {
  const revoked = run.status === "revoked";
  const body = el("div", {class: "stack", id: "run-state"},
    el("div", {class: "row-badges"}, status(run.status), retentionBadge(run)),
    el("p", {},
      revoked ? "该批次已作废：无需等待演练结束，排队/在跑任务已失效，迟到结果也不会入库；原始资料与未签核结果已清除。"
      : run.status === "queued" ? "后台正在排队处理，页面会自动更新。"
      : run.status === "running" ? "演练正在执行，撤销无需等待其跑完。"
      : run.failure || run.result?.summary || ""),
    run.status === "done" ? el("a", {class: "button", href: `#evidence/${run.id}`}, "查看业务证据") : null,
    revoked ? el("a", {class: "button quiet-link", href: "#evidence"}, "前往可见配方根查看留档标记") : null,
    canRevoke(run, user) ? revokeButton("撤销批次", async () => {
      await api.revokeRun(run.id);
      await onRevoked?.();
    }) : null);
  return body;
}

export async function runsPage(config, user, route, signal) {
  const items = await api.runs();
  const latest = route.id ? await api.run(route.id, signal) : items[0];

  function renderDetail(run) {
    return reportState(run, user, async () => { await refresh(); });
  }

  const detail = latest ? renderDetail(latest) : empty("进入资料页，选用一个业务样本并提交执行。");
  async function refresh() {
    try {
      const next = await api.run(latest.id, signal);
      if (!signal.aborted) {
        detail.replaceChildren(...renderDetail(next).childNodes);
        const badge = document.querySelector(`[data-run="${next.id}"] .status`);
        if (badge) badge.replaceWith(status(next.status));
        const verdict = document.querySelector(`[data-run="${next.id}"] [data-retention]`);
        if (verdict) verdict.replaceWith(retentionBadge(next));
      }
      return next.status === "queued" || next.status === "running";
    } catch (error) {
      if (!signal.aborted) detail.append(el("p", {role: "alert"}, error.message));
      return false;
    }
  }
  if (latest && (latest.status === "queued" || latest.status === "running")) poll(refresh, signal);
  return el("div", {class: "page"},
    pageHeading(config.modules[2], config.parameter_label),
    latest ? section(latest.case_title, detail) : detail,
    section("执行批次", items.length ? table(["资料", "编号", "参数", "状态", "留档", "提交时间"],
      items.map(run => [
        el("a", {"data-run": run.id, href: `#runs/${run.id}`}, run.case_title),
        run.id,
        run.parameter,
        el("span", {"data-run": run.id}, status(run.status)),
        el("span", {"data-run": run.id}, retentionBadge(run)),
        time(run.created_at),
      ]), "执行批次") :
      empty("暂无执行记录。")));
}
