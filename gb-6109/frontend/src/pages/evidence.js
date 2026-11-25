import { api } from "../api/workbench.js";
import { errorText, field } from "../components/common/fields.js";
import { canRevoke, revokeButton } from "../components/common/revoke.js";
import { empty, pageHeading, section } from "../components/common/panel.js";
import { retentionBadge, status } from "../components/common/status.js";
import { resultTable, table } from "../components/common/table.js";
import { submit } from "../hooks/submit.js";
import { el } from "../utils/dom.js";
import { cell, download, time } from "../utils/format.js";

function reviewForm(id, saved) {
  const form = el("form", {id: "review-form"},
    field("复核意见", el("textarea", {name: "note", required: true, minlength: 3, maxlength: 500, rows: 3})),
    errorText(), el("button", {type: "submit"}, "签署复核"));
  submit(form, async values => saved(await api.submitReview(id, {note: values.get("note")})));
  return form;
}

function signature(review) {
  return el("div", {"data-testid": "reviewed", class: "signature"},
    el("strong", {}, `已签署 · ${review.actor}`), el("p", {}, review.note), el("time", {}, time(review.created_at)));
}

function reloadRoute() {
  // 以当前哈希重跑路由，统一从服务端拉取“谁先办成”后的最终状态。
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

// 批次留档总表：在可见配方根上明确标出保留与作废的批次。
function archiveTable(runs) {
  return section("批次留档标记", table(
    ["批次", "资料", "留档判定", "执行状态", "原摘要 SHA-256", "时间"],
    runs.map(run => [
      el("a", {href: `#evidence/${run.id}`}, `#${run.id}`),
      run.case_title,
      el("span", {"data-verdict-cell": run.id}, retentionBadge(run)),
      status(run.status),
      run.digest ? el("code", {class: "digest-cell"}, run.digest.slice(0, 12)) : "—",
      time(run.created_at),
    ]), "批次留档（保留与作废）"));
}

function voidPanel(run, user) {
  return el("section", {class: "panel void-panel", "data-testid": "revoked", "data-verdict": "voided"},
    el("div", {class: "row-badges"}, status(run.status),
      el("strong", {class: "retention voided", "data-testid": "voided", "data-retention": "voided"}, "作废")),
    el("h2", {}, "该批次已撤销作废"),
    el("p", {}, "撤销无需等待演练跑完：排队与在跑的该批任务均已失效，迟到结果不会入库；原始资料和未签核结果已清除。已先签核的批次不受影响，仍可用原摘要核对当时配方。"),
    run.revoke_reason ? el("p", {class: "void-reason"}, `撤销原因：${run.revoke_reason}`) : null,
    el("p", {class: "muted"}, `作废时间：${time(run.revoked_at)}`),
    canRevoke(run, user) ? revokeButton("撤销批次", async () => {
      await api.revokeRun(run.id);
      reloadRoute();
    }) : null);
}

function notReady(run, user) {
  return el("section", {class: "panel"},
    el("div", {class: "stack"}, status(run.status), retentionBadge(run),
      el("p", {}, run.status === "failed" ? (run.failure || "该批次执行失败。") : "该批次尚未成功完成，暂无可签核或留档的结果。撤销无需等待演练跑完。"),
      el("div", {class: "row-badges"},
        el("a", {class: "button secondary", href: `#runs/${run.id}`}, "前往发布重演查看进度"),
        canRevoke(run, user) ? revokeButton("撤销批次", async () => {
          await api.revokeRun(run.id);
          reloadRoute();
        }) : null)));
}

export async function evidencePage(config, user, route) {
  const runs = await api.runs();
  const doneRuns = runs.filter(item => item.status === "done");
  const fallback = doneRuns[0] ?? runs[0];
  const run = route.id ? await api.run(route.id) : fallback;

  const archive = archiveTable(runs);

  if (!run) {
    return el("div", {class: "page"},
      pageHeading(config.modules[3], null),
      empty("成功执行一个批次后可以查看、签核和下载证据；录错的资料可撤销，此处会标出保留与作废的批次。"),
      el("a", {href: "#runs"}, config.modules[2]));
  }

  if (run.status === "revoked") {
    return el("div", {class: "page evidence"},
      pageHeading(config.modules[3], run.case_title),
      el("select", {"aria-label": "选择已完成的批次", onchange: event => {
        location.hash = `evidence/${event.target.value}`;
      }}, doneRuns.map(item => el("option", {value: item.id, selected: item.id === run.id}, `#${item.id} ${item.case_title}`))),
      voidPanel(run, user),
      archive);
  }

  if (!run.result) {
    return el("div", {class: "page evidence"},
      pageHeading(config.modules[3], run.case_title), notReady(run, user), archive);
  }

  const review = await api.review(run.id);
  const issue = errorText();
  const button = el("button", {type: "button", onclick: async () => {
    button.disabled = true;
    issue.textContent = "";
    try {
      await download(await api.export(run.id), `evidence-${run.id}.json`);
    } catch (error) {
      issue.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }}, "导出证据");

  const verifyOut = el("p", {"data-testid": "verify-result", role: "status"});
  const verifyButton = el("button", {type: "button", class: "secondary", "data-testid": "verify-digest", onclick: async () => {
    verifyButton.disabled = true;
    verifyOut.textContent = "";
    try {
      const result = await api.verifyRun(run.id);
      verifyOut.textContent = !result.available ? "结果已清除，无法核对摘要。"
        : result.matches ? "摘要一致：可用原 SHA-256 摘要核对当时的配方。"
        : "摘要不一致，结果可能已变动。";
      verifyOut.dataset.matches = String(Boolean(result.matches));
    } catch (error) {
      verifyOut.textContent = error.message;
    } finally {
      verifyButton.disabled = false;
    }
  }}, "核对原摘要");

  const signing = el("div", {});
  const decision = el("div", {class: "decision", "data-decision": run.id});
  function renderSigned(savedReview) {
    decision.replaceChildren(el("div", {
      class: "retention-banner retained", "data-testid": "retained", "data-verdict": "retained",
    }, el("strong", {class: "retention retained"}, "保留"),
      el("span", {}, "签核已先办成，该批留档，原摘要可继续核对当时配方。")));
    signing.replaceChildren(signature(savedReview));
    // 同步更新留档总表中的该行标记。
    document.querySelector(`[data-verdict-cell="${run.id}"]`)?.replaceChildren(retentionBadge({...run, review: savedReview, retained: true, verdict: "retained"}));
    const revokeControl = document.querySelector("[data-revoke-slot]");
    if (revokeControl) revokeControl.replaceChildren();
  }
  if (review) {
    renderSigned(review);
  } else if (user.role === "reviewer") {
    signing.append(reviewForm(run.id, renderSigned));
  } else {
    signing.append(empty("待复核员签署。"));
  }

  const revokeSlot = el("div", {"data-revoke-slot": run.id},
    canRevoke(run, user) ? revokeButton("撤销批次", async () => {
      try {
        await api.revokeRun(run.id);
        reloadRoute();
      } catch (error) {
        // 并发下签核先办成：刷新为保留结论，并把冲突原因留给按钮行内提示。
        reloadRoute();
        throw error;
      }
    }) : null);

  const options = el("select", {"aria-label": "选择已完成的批次", onchange: event => {
    location.hash = `evidence/${event.target.value}`;
  }}, doneRuns.map(item => el("option", {value: item.id, selected: item.id === run.id}, `#${item.id} ${item.case_title}`)));

  return el("div", {class: "page evidence"},
    pageHeading(config.modules[3], run.case_title, button),
    issue, options,
    decision,
    el("section", {class: "feature evidence-summary"},
      el("div", {}, el("h2", {}, "批次判定"), el("p", {}, run.result.summary)),
      el("details", {}, el("summary", {}, "证据摘要（原 SHA-256）"),
        el("code", {}, run.digest),
        el("div", {class: "verify-row"}, verifyButton, verifyOut))),
    el("dl", {class: "metrics"}, Object.entries(run.result.metrics).map(([label, value]) =>
      el("div", {}, el("dt", {}, label), el("dd", {}, cell(value))))),
    section("业务结果明细", run.result.rows.length ? resultTable(run.result.rows) : empty("此批次无明细。")),
    section("复核签署与撤销", el("div", {class: "stack"}, signing, revokeSlot)),
    archive);
}
