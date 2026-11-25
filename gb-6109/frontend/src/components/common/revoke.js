import { el } from "../../utils/dom.js";

// 危险/撤销操作按钮：自带禁用与行内错误提示。具体成功后的刷新由页面通过 onTrigger 完成。
export function revokeButton(label, onTrigger, {testid = "revoke-run"} = {}) {
  const issue = el("p", {role: "alert", class: "feedback"});
  const button = el("button", {
    type: "button", class: "danger", "data-testid": testid,
    onclick: async () => {
      button.disabled = true;
      issue.textContent = "";
      try {
        await onTrigger();
      } catch (error) {
        issue.textContent = error.message;
        button.disabled = false;
      }
    },
  }, label);
  return el("div", {class: "stack revoke-control"}, button, issue);
}

export function canRevoke(run, user) {
  if (!user || user.role !== "operator") return false;
  if (!run || run.status === "revoked" || run.verdict === "voided") return false;
  if (run.review || run.retained || run.verdict === "retained") return false;
  return true;
}
