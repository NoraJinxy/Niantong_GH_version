/* 念析 ELYS — 全局 UI 交互 */
(function () {
  // 侧栏开关（移动端）
  document.addEventListener("click", function (e) {
    const trigger = e.target.closest("[data-toggle-sidebar]");
    if (trigger) {
      const root = document.querySelector(".app");
      if (root) root.classList.toggle("is-sidebar-open");
    }
  });

  // 标签切换
  document.addEventListener("click", function (e) {
    const tab = e.target.closest(".tabs__item[data-target]");
    if (!tab) return;
    const tabs = tab.parentElement;
    tabs.querySelectorAll(".tabs__item").forEach(t => t.classList.remove("is-active"));
    tab.classList.add("is-active");
    const root = tab.closest("[data-tab-root]") || document;
    const target = tab.getAttribute("data-target");
    root.querySelectorAll("[data-pane]").forEach(p => {
      p.style.display = (p.getAttribute("data-pane") === target) ? "" : "none";
    });
  });

  // 任务面板展开
  document.addEventListener("click", function (e) {
    const head = e.target.closest(".task-dock__head");
    if (!head) return;
    head.parentElement.classList.toggle("is-open");
  });

  // 折叠组
  document.addEventListener("click", function (e) {
    const trig = e.target.closest("[data-collapse]");
    if (!trig) return;
    const id = trig.getAttribute("data-collapse");
    const tgt = document.getElementById(id);
    if (tgt) tgt.style.display = (tgt.style.display === "none") ? "" : "none";
  });

  // Toggle switch
  document.addEventListener("click", function (e) {
    const t = e.target.closest(".toggle");
    if (t) t.classList.toggle("is-on");
  });

  // 高亮当前侧栏项（依据 data-key）
  const cur = document.body.getAttribute("data-page");
  if (cur) {
    document.querySelectorAll(".nav-item").forEach(item => {
      if (item.getAttribute("data-key") === cur) item.classList.add("is-active");
    });
  }
})();
