const state = {
  config: null,
  resolveResult: null,
  qualifiedCompare: null,
  notifyPrecheck: null,
  converterPrepare: null,
  qualificationMasterCollapsed: false,
};

function $(id) {
  return document.getElementById(id);
}

async function apiGet(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function apiPostJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function apiPostForm(url, formData) {
  const response = await fetch(url, { method: "POST", body: formData });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function setGlobalStatus(text) {
  $("global-task-status").textContent = text;
}

function formatStatusMessage(task) {
  const progress = task.progress_total ? ` ${task.progress_current}/${task.progress_total}` : "";
  const runDir = task.result?.run_dir ? ` | ${task.result.run_dir}` : "";
  return `${task.message || task.kind}${progress}${runDir}`;
}

async function waitTask(taskId) {
  setGlobalStatus(`任务运行中：${taskId}`);
  while (true) {
    const task = await apiGet(`/api/tasks/${taskId}`);
    if (task.status === "completed") {
      setGlobalStatus(formatStatusMessage(task));
      return task.result;
    }
    if (task.status === "failed") {
      setGlobalStatus(`任务失败：${task.kind}`);
      throw new Error(task.error || "任务失败");
    }
    setGlobalStatus(formatStatusMessage(task));
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

function formBindingPayload(prefix) {
  return {
    title: $(`${prefix}_title`).value.trim(),
    entries_url: $(`${prefix}_entries_url`).value.trim(),
  };
}

function bindingNameToPrefix(bindingName) {
  return {
    qualification_form: "qualification",
    singles_form: "singles",
    doubles_form: "doubles",
    team_form: "team",
  }[bindingName] || "";
}

function applySelectToInputs(prefix) {
  const select = $(`${prefix}_select`);
  const option = select.options[select.selectedIndex];
  if (!option || !option.value) return;
  const data = JSON.parse(option.value);
  $(`${prefix}_title`).value = data.title || "";
  $(`${prefix}_entries_url`).value = data.entries_url || "";
}

function collectConfigPayload() {
  return {
    event_group_id: $("event_group_id").value.trim(),
    napcat_config_path: $("napcat_config_path").value.trim(),
    jinshuju_home_url: $("jinshuju_home_url").value.trim(),
    jinshuju_profile_dir: $("jinshuju_profile_dir").value.trim(),
    notify_template: $("notify_template").value.trim(),
    qualification_form: formBindingPayload("qualification"),
    singles_form: formBindingPayload("singles"),
    doubles_form: formBindingPayload("doubles"),
    team_form: formBindingPayload("team"),
  };
}

function fillConfig(config) {
  state.config = config;
  $("event_group_id").value = config.event_group_id || "";
  $("napcat_config_path").value = config.napcat_config_path || "";
  $("jinshuju_home_url").value = config.jinshuju_home_url || "";
  $("jinshuju_profile_dir").value = config.jinshuju_profile_dir || "";
  $("notify_template").value = config.notify_template || "";

  const bindings = {
    qualification: config.qualification_form || {},
    singles: config.singles_form || {},
    doubles: config.doubles_form || {},
    team: config.team_form || {},
  };
  Object.entries(bindings).forEach(([prefix, value]) => {
    $(`${prefix}_title`).value = value.title || "";
    $(`${prefix}_entries_url`).value = value.entries_url || "";
  });

  const forms = config.discovered_forms || [];
  ["qualification", "singles", "doubles", "team"].forEach((prefix) => {
    const select = $(`${prefix}_select`);
    select.innerHTML = `<option value="">从已发现表单里选择</option>`;
    forms.forEach((item) => {
      const option = document.createElement("option");
      option.value = JSON.stringify(item);
      option.textContent = `${item.title}${item.updated_at ? " | " + item.updated_at : ""}`;
      select.appendChild(option);
    });
  });
}

function renderObjectSummary(targetId, data) {
  $(targetId).innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
}

function renderError(targetId, error) {
  const message = error?.message || String(error);
  $(targetId).innerHTML = `<pre>${message}</pre>`;
  setGlobalStatus(`操作失败：${message}`);
}

function updateQualificationMasterVisibility() {
  const resultBox = $("qualification-master-result");
  const toggleButton = $("toggle-master-btn");
  if (!resultBox || !toggleButton) return;
  resultBox.classList.toggle("collapsed", state.qualificationMasterCollapsed);
  toggleButton.textContent = state.qualificationMasterCollapsed
    ? "展开已获取资格名单"
    : "收起已获取资格名单";
}

function buildSimpleTable(rows, columns, checkbox = false) {
  const header = columns.map((col) => `<th>${col}</th>`).join("");
  const checkboxHeader = checkbox ? `<th class="checkbox-cell">选</th>` : "";
  const body = rows.map((row, index) => {
    const checkboxCell = checkbox
      ? `<td class="checkbox-cell"><input type="checkbox" data-row-index="${index}" checked></td>`
      : "";
    const cells = columns.map((col) => `<td>${row[col] ?? ""}</td>`).join("");
    return `<tr>${checkboxCell}${cells}</tr>`;
  }).join("");
  return `<table><thead><tr>${checkboxHeader}${header}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderRows(targetId, rows, columns, emptyText, checkbox = false) {
  if (!rows || !rows.length) {
    $(targetId).innerHTML = `<p class="muted">${emptyText}</p>`;
    return;
  }
  $(targetId).innerHTML = buildSimpleTable(rows, columns, checkbox);
}

function renderDiscoveredForms(forms) {
  if (!forms.length) {
    $("forms-discover-result").innerHTML = `<p class="muted">暂无已发现表单</p>`;
    return;
  }
  const rows = forms.map((item) => ({
    标题: item.title,
    最近更新时间: item.updated_at || "未知",
    链接: `<a href="${item.url}" target="_blank" rel="noreferrer">打开</a>`,
  }));
  const header = ["标题", "最近更新时间", "链接"].map((col) => `<th>${col}</th>`).join("");
  const body = rows.map((row) => `<tr><td>${row.标题}</td><td>${row.最近更新时间}</td><td>${row.链接}</td></tr>`).join("");
  $("forms-discover-result").innerHTML = `<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderResolveResult(result) {
  state.resolveResult = result;
  const blocks = [
    `<p><span class="pill">导出文件</span> ${result.export_file}</p>`,
    `<p><span class="pill">未匹配</span> ${result.unmatched.join("、") || "无"}</p>`,
  ];
  if (result.resolved.length) {
    blocks.push("<h3>已直接匹配</h3>");
    blocks.push(buildSimpleTable(result.resolved, ["name", "college", "qq", "source", "row_number", "created_at", "updated_at"]));
  }
  if (result.ambiguous.length) {
    blocks.push("<h3>待人工确认</h3>");
    result.ambiguous.forEach((group, idx) => {
      let options = "";
      group.candidates.forEach((candidate, candidateIdx) => {
        options += `<option value="${candidateIdx}">${candidate.name} | ${candidate.college} | ${candidate.qq} | ${candidate.created_at || "无提交时间"} </option>`;
      });
      blocks.push(`<div class="result-box"><p class="warn">${group.input_name}</p><select id="ambiguous_${idx}">${options}</select></div>`);
    });
  }
  blocks.push(`<div class="actions"><button id="apply-resolve-btn">合并更新到本地资格名单</button></div>`);
  $("qualification-resolve-result").innerHTML = blocks.join("");
  $("apply-resolve-btn").addEventListener("click", applyResolveSelection);
}

async function applyResolveSelection() {
  const selections = [...(state.resolveResult?.resolved || [])];
  (state.resolveResult?.ambiguous || []).forEach((group, idx) => {
    const select = $(`ambiguous_${idx}`);
    const candidate = group.candidates[Number(select.value)];
    if (candidate) selections.push(candidate);
  });
  const kickoff = await apiPostJson("/api/qualification/apply", { selections });
  const result = await waitTask(kickoff.task_id);
  renderObjectSummary("qualification-master-result", result);
  await loadQualificationMaster();
}

async function loadQualificationMaster() {
  const result = await apiGet("/api/qualification/current");
  const rows = (result.rows || []).map((row) => ({
    姓名: row["姓名"],
    学院: row["学院"],
    QQ号: row["QQ号"],
    来源表单: row["来源表单"],
    最近更新时间: row["最近更新时间"],
  }));
  renderRows("qualification-master-result", rows, ["姓名", "学院", "QQ号", "来源表单", "最近更新时间"], "本地资格名单为空");
  updateQualificationMasterVisibility();
}

function renderCompareResult(targetId, result, emptyText) {
  renderRows(
    targetId,
    result.rows || [],
    ["name", "college", "qq", "source", "match_key", "reason"],
    emptyText,
  );
}

function renderNotifyPrecheck(result) {
  state.notifyPrecheck = result;
  renderRows(
    "notify-precheck-result",
    result.rows || [],
    ["name", "college", "qq", "status", "error", "message_preview"],
    "没有可预检对象",
    true,
  );
  [...$("notify-precheck-result").querySelectorAll("tbody tr")].forEach((tr, index) => {
    const row = result.rows[index];
    const checkbox = tr.querySelector("input[type=checkbox]");
    if (checkbox && row.status !== "precheck_ok") {
      checkbox.checked = false;
    }
  });
}

async function sendSelectedNotifications() {
  const rows = state.notifyPrecheck?.rows || [];
  const checked = [...$("notify-precheck-result").querySelectorAll("input[type=checkbox]:checked")];
  const selectedRows = checked.map((input) => {
    const row = rows[Number(input.dataset.rowIndex)];
    return { name: row.name, college: row.college, qq: row.qq };
  });
  if (!selectedRows.length) {
    alert("请先勾选要发送的人");
    return;
  }
  const kickoff = await apiPostJson("/api/notify/send", { rows: selectedRows });
  const result = await waitTask(kickoff.task_id);
  renderRows(
    "notify-send-result",
    result.rows || [],
    ["name", "college", "qq", "status", "error", "message_preview"],
    "没有发送结果",
  );
}

function renderConverterPrepare(result) {
  state.converterPrepare = result;
  const groups = result.duplicate_groups || [];
  const blocks = [
    `<p><span class="pill">sheet_output</span> ${result.sheet_output}</p>`,
    `<p><span class="pill">重复摘要</span> ${result.duplicate_summary_file}</p>`,
    `<p><span class="pill">重复清单</span> ${result.duplicate_review_file}</p>`,
  ];
  if (groups.length) {
    const rows = groups.map((group) => ({
      标签: group.label,
      类型: group.type,
      保留规则: group.keep_rule,
      重复次数: group.occurrences.length,
    }));
    blocks.push(buildSimpleTable(rows, ["标签", "类型", "保留规则", "重复次数"]));
  } else {
    blocks.push(`<p class="muted">未发现重复项</p>`);
  }
  $("converter-prepare-result").innerHTML = blocks.join("");
}

async function bootstrap() {
  fillConfig(await apiGet("/api/config"));
  renderDiscoveredForms(state.config?.discovered_forms || []);
  await loadQualificationMaster();
  updateQualificationMasterVisibility();

  ["qualification", "singles", "doubles", "team"].forEach((prefix) => {
    $(`${prefix}_select`).addEventListener("change", () => applySelectToInputs(prefix));
  });

  $("save-config-btn").addEventListener("click", async () => {
    fillConfig(await apiPostJson("/api/config", collectConfigPayload()));
    renderDiscoveredForms(state.config?.discovered_forms || []);
  });

  $("check-session-btn").addEventListener("click", async () => {
    const kickoff = await apiPostJson("/api/jinshuju/session/check", collectConfigPayload());
    renderObjectSummary("form-export-result", await waitTask(kickoff.task_id));
  });

  $("discover-forms-btn").addEventListener("click", async () => {
    const kickoff = await apiPostJson("/api/jinshuju/forms/discover", collectConfigPayload());
    await waitTask(kickoff.task_id);
    fillConfig(await apiGet("/api/config"));
    renderDiscoveredForms(state.config?.discovered_forms || []);
  });

  $("export-form-btn").addEventListener("click", async () => {
    try {
      const binding = $("export_binding").value;
      const prefix = bindingNameToPrefix(binding);
      const payload = {
        binding,
        form_title: prefix ? $(`${prefix}_title`).value.trim() : "",
        entries_url: prefix ? $(`${prefix}_entries_url`).value.trim() : "",
      };
      const kickoff = await apiPostJson("/api/jinshuju/forms/export", payload);
      renderObjectSummary("form-export-result", await waitTask(kickoff.task_id));
    } catch (error) {
      $("form-export-result").innerHTML = `<pre>${error.message}</pre>`;
      setGlobalStatus(`导出失败：${error.message}`);
    }
  });

  $("resolve-names-btn").addEventListener("click", async () => {
    try {
      const kickoff = await apiPostJson("/api/qualification/resolve", {
        names: $("qualification_names").value,
        ...collectConfigPayload(),
      });
      renderResolveResult(await waitTask(kickoff.task_id));
    } catch (error) {
      renderError("qualification-resolve-result", error);
    }
  });

  $("refresh-master-btn").addEventListener("click", loadQualificationMaster);

  $("export-master-btn").addEventListener("click", () => {
    window.location.href = "/api/qualification/export";
  });

  $("toggle-master-btn").addEventListener("click", () => {
    state.qualificationMasterCollapsed = !state.qualificationMasterCollapsed;
    updateQualificationMasterVisibility();
  });

  $("compare-form-btn").addEventListener("click", async () => {
    try {
      const kickoff = await apiPostJson("/api/compare/singles-vs-qualification-form", collectConfigPayload());
      renderCompareResult("compare-form-result", await waitTask(kickoff.task_id), "没有异常报名");
    } catch (error) {
      renderError("compare-form-result", error);
    }
  });

  $("compare-qualified-btn").addEventListener("click", async () => {
    try {
      const kickoff = await apiPostJson("/api/compare/qualified-vs-singles", collectConfigPayload());
      const result = await waitTask(kickoff.task_id);
      state.qualifiedCompare = result;
      renderCompareResult("compare-qualified-result", result, "没有“有资格但没报单打”的对象");
    } catch (error) {
      renderError("compare-qualified-result", error);
    }
  });

  $("notify-precheck-btn").addEventListener("click", async () => {
    try {
      const rows = state.qualifiedCompare?.rows || [];
      if (!rows.length) {
        alert("请先完成“有资格但没报单打”比对");
        return;
      }
      const kickoff = await apiPostJson("/api/notify/precheck", { rows });
      renderNotifyPrecheck(await waitTask(kickoff.task_id));
    } catch (error) {
      renderError("notify-precheck-result", error);
    }
  });

  $("notify-send-btn").addEventListener("click", sendSelectedNotifications);

  $("converter-prepare-btn").addEventListener("click", async () => {
    const formData = new FormData();
    formData.append("singles_file", $("final_singles_file").value.trim());
    formData.append("doubles_file", $("final_doubles_file").value.trim());
    formData.append("team_file", $("final_team_file").value.trim());
    const singlesUpload = $("final_singles_upload").files[0];
    const doublesUpload = $("final_doubles_upload").files[0];
    const teamUpload = $("final_team_upload").files[0];
    if (singlesUpload) formData.append("singles_upload", singlesUpload);
    if (doublesUpload) formData.append("doubles_upload", doublesUpload);
    if (teamUpload) formData.append("team_upload", teamUpload);
    const kickoff = await apiPostForm("/api/converter/prepare", formData);
    renderConverterPrepare(await waitTask(kickoff.task_id));
  });

  $("converter-confirm-btn").addEventListener("click", async () => {
    if (!state.converterPrepare?.run_dir) {
      alert("请先执行查重预处理");
      return;
    }
    if (!window.confirm("确认按“保留第一条/第一组”的规则删除重复项并生成优赛上传表？")) {
      return;
    }
    const kickoff = await apiPostJson("/api/converter/confirm-dedupe", { run_dir: state.converterPrepare.run_dir });
    renderObjectSummary("converter-confirm-result", await waitTask(kickoff.task_id));
  });
}

bootstrap().catch((error) => {
  setGlobalStatus(`初始化失败：${error.message}`);
  console.error(error);
});
