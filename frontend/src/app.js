const LAYER_ORDER = ["evidence", "ability", "composite", "direction", "role"];
const LAYER_LABELS = {
  evidence: "原子证据",
  ability: "基础能力",
  composite: "复合能力",
  direction: "岗位方向",
  role: "具体职业",
};
const LAYER_LIMITS = {
  evidence: 10,
  ability: 10,
  composite: 8,
  direction: 6,
  role: 6,
};
const RELATION_COLORS = {
  supports: "#0f766e",
  evidences: "#c4672e",
  requires: "#1f4f78",
  prefers: "#c08a1f",
  inhibits: "#8b3c2e",
};
const SOURCE_TYPE_LABELS = {
  onet_online: "O*NET",
  roadmap_sh: "roadmap.sh",
};
const ACTION_TYPE_LABELS = {
  project: "项目",
  practice: "练习",
  course: "课程",
  portfolio: "作品集",
};
const EFFORT_LEVEL_LABELS = {
  low: "低投入",
  medium: "中投入",
  high: "高投入",
};

const state = {
  catalog: [],
  roleCatalog: [],
  sampleRequest: null,
  input: {
    text: "",
    structured: [],
  },
  confirmedSignals: [],
  result: null,
  targetRoleId: "",
  targetGapResult: null,
  targetGapInputSignature: "",
  actionSimulationResult: null,
  selectedActionBundleKeys: [],
  selectedJobId: null,
  selectedPathIndex: 0,
  selectedNodeId: null,
  busy: false,
  statusMessage: "",
  errorMessage: "",
};

const elements = {
  graphSize: document.querySelector("#meta-graph-size"),
  roleCount: document.querySelector("#meta-role-count"),
  textInput: document.querySelector("#text-input"),
  submitBtn: document.querySelector("#submit-btn"),
  recomputeBtn: document.querySelector("#recompute-btn"),
  loadSampleBtn: document.querySelector("#load-sample-btn"),
  analyzeTargetBtn: document.querySelector("#analyze-target-btn"),
  addStructuredRowBtn: document.querySelector("#add-structured-row-btn"),
  addConfirmedRowBtn: document.querySelector("#add-confirmed-row-btn"),
  structuredRows: document.querySelector("#structured-rows"),
  requestNotes: document.querySelector("#request-notes"),
  signalList: document.querySelector("#normalized-signals"),
  targetRoleSelect: document.querySelector("#target-role-select"),
  targetGapAnalysis: document.querySelector("#target-gap-analysis"),
  recommendationList: document.querySelector("#recommendation-list"),
  nearMissList: document.querySelector("#near-miss-list"),
  pathInspector: document.querySelector("#path-inspector"),
  graphArea: document.querySelector("#graph-area"),
  graphDetail: document.querySelector("#graph-detail"),
  catalogOptions: document.querySelector("#catalog-options"),
};

const uid = () => Math.random().toString(36).slice(2, 10);

async function init() {
  bindEvents();
  renderAll();
  await loadCatalog();
}

function bindEvents() {
  elements.submitBtn.addEventListener("click", () => submitInitialRecommendation());
  elements.recomputeBtn.addEventListener("click", () => recomputeFromConfirmedSignals());
  elements.loadSampleBtn.addEventListener("click", () => applySampleRequest());
  elements.analyzeTargetBtn.addEventListener("click", () => analyzeTargetRole());
  elements.addStructuredRowBtn.addEventListener("click", () => {
    state.input.structured.push(createStructuredRow());
    renderStructuredRows();
  });
  elements.addConfirmedRowBtn.addEventListener("click", () => {
    state.confirmedSignals.push(createConfirmedRow());
    renderConfirmedSignals();
  });
  elements.textInput.addEventListener("input", (event) => {
    state.input.text = event.target.value;
  });
  elements.targetRoleSelect.addEventListener("change", (event) => {
    state.targetRoleId = event.target.value;
    state.targetGapResult = null;
    state.targetGapInputSignature = "";
    state.actionSimulationResult = null;
    state.selectedActionBundleKeys = [];
    renderTargetGapAnalysis();
  });
}

function createStructuredRow() {
  return { id: uid(), entity: "", score: 0.7 };
}

function createConfirmedRow() {
  return { id: uid(), nodeId: "", nodeName: "", score: 0.5, source: "manual" };
}

async function loadCatalog() {
  setBusy(true, "正在加载图谱目录…");
  try {
    const payload = await fetchJSON("/api/catalog");
    state.catalog = payload.evidence_nodes || [];
    state.roleCatalog = payload.role_nodes || [];
    if (!state.targetRoleId) {
      state.targetRoleId =
        state.roleCatalog.find((item) => item.id === "role_backend_engineer")?.id ||
        state.roleCatalog[0]?.id ||
        "";
    }
    state.sampleRequest = payload.sample_request || null;
    const graphStats = payload.graph_stats || {};
    elements.graphSize.textContent =
      `${graphStats.node_count || 0} 节点 / ${graphStats.edge_count || 0} 边 / ${graphStats.source_profile_count || 0} 条来源画像 / ${graphStats.source_type_count || 0} 类来源`;
    elements.roleCount.textContent =
      `${graphStats.role_count || 0} 个岗位 / ${graphStats.nodes_with_provenance || 0} 个溯源节点`;
    if (state.input.structured.length === 0) {
      state.input.structured.push(createStructuredRow());
    }
    renderCatalogOptions();
    renderTargetRoleOptions();
    renderAll();
    setBusy(false, "图谱目录已加载");
  } catch (error) {
    setError(`加载 catalog 失败：${error.message}`);
  }
}

function applySampleRequest() {
  if (!state.sampleRequest) {
    setError("示例请求尚未加载完成。");
    return;
  }
  state.targetGapResult = null;
  state.targetGapInputSignature = "";
  state.actionSimulationResult = null;
  state.selectedActionBundleKeys = [];
  state.input.text = state.sampleRequest.text || "";
  elements.textInput.value = state.input.text;
  state.input.structured = (state.sampleRequest.signals || []).map((signal) => ({
    id: uid(),
    entity: signal.entity,
    score: Number(signal.score || 0.7),
  }));
  if (state.input.structured.length === 0) {
    state.input.structured.push(createStructuredRow());
  }
  renderStructuredRows();
  setBusy(false, "已载入示例输入");
}

async function submitInitialRecommendation() {
  const payload = buildInitialRecommendationPayload();
  if (!payload.text && payload.signals.length === 0) {
    setError("请至少提供一条自然语言描述或结构化信号，再生成推荐。");
    return;
  }

  setBusy(true, "正在解析输入并运行图推理…");
  try {
    const result = await postJSON("/api/recommend", payload);
    state.result = result;
    state.targetGapResult = null;
    state.targetGapInputSignature = "";
    state.actionSimulationResult = null;
    state.selectedActionBundleKeys = [];
    state.confirmedSignals = (result.normalized_inputs || []).map((item) => ({
      id: uid(),
      nodeId: item.node_id,
      nodeName: item.node_name,
      score: clampScore(item.score),
      source: item.source,
    }));
    state.selectedJobId = pickInitialJobId(result);
    state.selectedPathIndex = 0;
    state.selectedNodeId = state.selectedJobId;
    setBusy(false, "推荐结果已更新，可继续微调节点后重算。");
    renderAll();
  } catch (error) {
    setError(`推荐请求失败：${error.message}`);
  }
}

async function recomputeFromConfirmedSignals() {
  const signals = buildConfirmedSignalPayload();

  if (signals.length === 0) {
    setError("请先保留至少一个确认后的节点。");
    return;
  }

  setBusy(true, "正在按确认节点重算…");
  try {
    const result = await postJSON("/api/recommend", {
      text: "",
      signals,
      top_k: 6,
      include_snapshot: true,
    });
    state.result = result;
    state.targetGapResult = null;
    state.targetGapInputSignature = "";
    state.actionSimulationResult = null;
    state.selectedActionBundleKeys = [];
    state.confirmedSignals = (result.normalized_inputs || []).map((item) => ({
      id: uid(),
      nodeId: item.node_id,
      nodeName: item.node_name,
      score: clampScore(item.score),
      source: "confirmed",
    }));
    const stillSelected = findJobById(result, state.selectedJobId);
    state.selectedJobId = stillSelected ? stillSelected.job_id : pickInitialJobId(result);
    state.selectedPathIndex = 0;
    state.selectedNodeId = state.selectedJobId;
    setBusy(false, "已基于确认节点重新计算。");
    renderAll();
  } catch (error) {
    setError(`重算失败：${error.message}`);
  }
}

async function analyzeTargetRole() {
  if (!state.targetRoleId) {
    setError("请先选择一个目标岗位。");
    return;
  }
  const payload = buildRoleGapPayload();
  if (!payload.text && payload.signals.length === 0) {
    setError("请先输入或确认至少一组能力信号，再分析目标岗位。");
    return;
  }

  setBusy(true, "正在分析目标岗位差距与模拟收益…");
  try {
    state.targetGapResult = await postJSON("/api/role-gap", payload);
    state.targetGapInputSignature = buildPayloadSignature(payload);
    state.actionSimulationResult = null;
    state.selectedActionBundleKeys = [];
    setBusy(false, "目标岗位分析已更新。");
    renderAll();
  } catch (error) {
    setError(`目标岗位分析失败：${error.message}`);
  }
}

async function simulateActionTemplate(templateId, actionKey) {
  if (!templateId && !actionKey) {
    setError("缺少可模拟的行动模板。");
    return;
  }
  return runActionSimulation(
    buildActionSimulationPayload(templateId, actionKey),
    "正在模拟所选行动会如何改写图谱传播…",
    "行动模拟已更新。"
  );
}

async function simulateActionBundle() {
  const selectedActions = getSelectedBundleActions();
  if (!selectedActions.length) {
    setError("请先加入至少一个动作，再模拟方案。");
    return;
  }
  return runActionSimulation(
    buildActionBundlePayload(selectedActions.map((action) => action.action_key)),
    selectedActions.length >= 2 ? "正在比较双动作组合会如何改写图谱传播…" : "正在模拟当前方案…",
    selectedActions.length >= 2 ? "组合模拟已更新。" : "方案模拟已更新。"
  );
}

async function runActionSimulation(payload, loadingMessage, successMessage) {
  if (!state.targetRoleId || !state.targetGapResult?.target_role) {
    setError("请先完成一次目标岗位分析，再模拟行动。");
    return;
  }
  if (state.targetGapInputSignature && buildPayloadSignature(buildRoleGapPayload()) !== state.targetGapInputSignature) {
    setError("确认节点已变更，请先重新分析目标岗位，再执行行动模拟。");
    return;
  }

  setBusy(true, loadingMessage);
  try {
    const result = await postJSON("/api/action-simulate", payload);
    state.actionSimulationResult = result.simulation || null;
    setBusy(false, successMessage);
    renderTargetGapAnalysis();
  } catch (error) {
    setError(`行动模拟失败：${error.message}`);
  }
}

function toggleActionBundle(actionKey) {
  if (!actionKey) {
    setError("当前动作缺少稳定的 action_key，暂时无法加入方案。");
    return;
  }
  if (state.selectedActionBundleKeys.includes(actionKey)) {
    state.selectedActionBundleKeys = state.selectedActionBundleKeys.filter((item) => item !== actionKey);
    state.actionSimulationResult = null;
    renderTargetGapAnalysis();
    return;
  }
  if (state.selectedActionBundleKeys.length >= 2) {
    setError("当前最多只能对比 2 个动作，请先移除一个。");
    return;
  }
  state.selectedActionBundleKeys = [...state.selectedActionBundleKeys, actionKey];
  state.actionSimulationResult = null;
  renderTargetGapAnalysis();
}

function clearActionBundle() {
  state.selectedActionBundleKeys = [];
  state.actionSimulationResult = null;
  renderTargetGapAnalysis();
}

function setBusy(busy, message = "") {
  state.busy = busy;
  state.statusMessage = message;
  if (!busy) {
    state.errorMessage = "";
  }
  renderNotice();
}

function setError(message) {
  state.busy = false;
  state.errorMessage = message;
  state.statusMessage = "";
  renderNotice();
}

function renderAll() {
  renderCatalogOptions();
  renderTargetRoleOptions();
  renderStructuredRows();
  renderConfirmedSignals();
  renderTargetGapAnalysis();
  renderRecommendations();
  renderNearMisses();
  renderPathInspector();
  renderGraph();
  renderNotice();
}

function renderCatalogOptions() {
  elements.catalogOptions.innerHTML = state.catalog
    .map((node) => `<option value="${escapeHtml(node.name)}"></option>`)
    .join("");
}

function renderTargetRoleOptions() {
  elements.targetRoleSelect.innerHTML = state.roleCatalog
    .map(
      (node) => `
        <option value="${node.id}" ${node.id === state.targetRoleId ? "selected" : ""}>${escapeHtml(node.name)}</option>
      `
    )
    .join("");
}

function buildInitialRecommendationPayload() {
  return {
    text: state.input.text.trim(),
    signals: state.input.structured
      .map((row) => ({ entity: row.entity.trim(), score: clampScore(row.score) }))
      .filter((row) => row.entity),
    top_k: 6,
    include_snapshot: true,
  };
}

function buildConfirmedSignalPayload() {
  return state.confirmedSignals
    .map((item) => ({
      entity: item.nodeId || item.nodeName,
      score: clampScore(item.score),
    }))
    .filter((item) => item.entity);
}

function buildRoleGapPayload() {
  const confirmedSignals = buildConfirmedSignalPayload();
  if (confirmedSignals.length) {
    return {
      text: "",
      signals: confirmedSignals,
      target_role_id: state.targetRoleId,
      scenario_limit: 3,
    };
  }

  const initialPayload = buildInitialRecommendationPayload();
  return {
    text: initialPayload.text,
    signals: initialPayload.signals,
    target_role_id: state.targetRoleId,
    scenario_limit: 3,
  };
}

function buildActionSimulationPayload(templateId, actionKey) {
  return {
    ...buildRoleGapPayload(),
    template_id: templateId,
    action_key: actionKey || "",
  };
}

function buildActionBundlePayload(actionKeys) {
  return {
    ...buildRoleGapPayload(),
    action_keys: actionKeys,
  };
}

function buildPayloadSignature(payload) {
  return JSON.stringify({
    text: payload.text || "",
    target_role_id: payload.target_role_id || "",
    signals: (payload.signals || []).map((item) => ({
      entity: item.entity || "",
      score: clampScore(item.score),
    })),
  });
}

function findTargetActionByKey(actionKey) {
  if (!actionKey || !state.targetGapResult?.target_role?.learning_path?.length) {
    return null;
  }
  for (const step of state.targetGapResult.target_role.learning_path) {
    for (const action of step.recommended_actions || []) {
      if ((action.action_key || "") === actionKey) {
        return { ...action, step };
      }
    }
  }
  return null;
}

function getSelectedBundleActions() {
  return state.selectedActionBundleKeys.map((actionKey) => findTargetActionByKey(actionKey)).filter(Boolean);
}

function renderTargetGapAnalysis() {
  if (!state.targetGapResult?.target_role) {
    const selectedRoleName = state.roleCatalog.find((item) => item.id === state.targetRoleId)?.name;
    elements.targetGapAnalysis.innerHTML = emptyState(
      selectedRoleName
        ? `当前目标岗位是“${selectedRoleName}”，点击“分析目标岗位”后会展示缺口、成长路径和 what-if 模拟。`
        : "选择一个目标岗位后，可查看定向差距分析、成长路径和 what-if 模拟。"
    );
    return;
  }

  const target = state.targetGapResult.target_role;
  const leadPath = target.paths?.[0];
  const sourceBadges = renderSourceTypeBadges(target.source_types || []);
  const selectedBundleActionKeys = new Set(state.selectedActionBundleKeys);
  const simulatedActionKeys = new Set((state.actionSimulationResult?.applied_actions || []).map((action) => action.action_key || action.template_id));
  const roadmapMarkup = target.learning_path?.length
    ? `<div class="roadmap-list">${target.learning_path
        .map(
          (step) => `
            <article class="roadmap-step-card">
              <div class="roadmap-step-head">
                <div>
                  <p class="signal-name">${escapeHtml(step.title)}</p>
                  <p class="signal-meta">${escapeHtml(step.summary)}</p>
                </div>
                <div class="score-chip">+${Math.round((step.expected_score_delta || 0) * 100)} / ${Math.round((step.expected_total_score || 0) * 100)} 分</div>
              </div>
              ${
                step.blocked_by?.length
                  ? `<div class="chip-row roadmap-chip-row">${step.blocked_by
                      .map((item) => `<span class="soft-chip">受限于 ${escapeHtml(item)}</span>`)
                      .join("")}</div>`
                  : ""
              }
              ${
                step.unlock_nodes?.length
                  ? `<div class="chip-row roadmap-chip-row">${step.unlock_nodes
                      .map((item) => `<span class="soft-chip accent-chip">带动 ${escapeHtml(item)}</span>`)
                      .join("")}</div>`
                  : ""
              }
              <ul class="limit-list scenario-boost-list">
                ${step.boosts
                  .map(
                    (boost) =>
                      `<li>${escapeHtml(`${boost.node_name}：${Math.round((boost.from_score || 0) * 100)} → ${Math.round((boost.to_score || 0) * 100)} 分`)}</li>`
                  )
                  .join("")}
              </ul>
              <div class="action-template-section">
                <p class="action-section-title">推荐行动</p>
                ${
                  step.recommended_actions?.length
                    ? `<div class="action-card-list">${step.recommended_actions
                        .map(
                          (action) => `
                            <article class="action-card ${simulatedActionKeys.has(action.action_key || action.template_id) ? "is-simulated" : ""}">
                              <div class="action-card-head">
                                <div>
                                  <p class="signal-name">${escapeHtml(action.title)}</p>
                                  <p class="signal-meta">${escapeHtml(action.summary)}</p>
                                </div>
                                <div class="chip-row action-chip-row">
                                  <span class="soft-chip">${escapeHtml(ACTION_TYPE_LABELS[action.action_type] || action.action_type)}</span>
                                  <span class="soft-chip accent-chip">${escapeHtml(EFFORT_LEVEL_LABELS[action.effort_level] || action.effort_level)}</span>
                                </div>
                              </div>
                              ${
                                action.reason
                                  ? `<p class="action-reason">${escapeHtml(action.reason)}</p>`
                                  : ""
                              }
                              ${
                                action.deliverables?.length
                                  ? `<p class="action-subtitle">建议交付物</p>
                                     <div class="chip-row action-chip-row">${action.deliverables
                                       .map((item) => `<span class="soft-chip">${escapeHtml(item)}</span>`)
                                       .join("")}</div>`
                                  : ""
                              }
                              <div class="action-card-footer">
                                <p class="soft-note action-sim-note">${
                                  action.simulation_node_ids?.length
                                    ? `模拟时会注入 ${escapeHtml(
                                        action.simulation_node_ids
                                          .map((nodeId) => lookupNodeMeta(nodeId, nodeId)?.name || nodeId)
                                          .join("、")
                                      )}`
                                    : "当前没有稳定的模拟锚点"
                                }</p>
                                <div class="action-card-controls">
                                  <button
                                    class="ghost-btn action-bundle-btn ${selectedBundleActionKeys.has(action.action_key || "") ? "is-selected" : ""}"
                                    type="button"
                                    data-bundle-action-key="${action.action_key || ""}"
                                    ${!action.action_key || state.busy ? "disabled" : ""}
                                  >
                                    ${selectedBundleActionKeys.has(action.action_key || "") ? "移出方案" : "加入方案"}
                                  </button>
                                  <button
                                    class="ghost-btn action-simulate-btn ${simulatedActionKeys.has(action.action_key || action.template_id) ? "is-active" : ""}"
                                    type="button"
                                    data-simulate-template-id="${action.template_id}"
                                    data-simulate-action-key="${action.action_key || ""}"
                                    ${state.busy ? "disabled" : ""}
                                  >
                                    ${simulatedActionKeys.has(action.action_key || action.template_id) ? "重新模拟" : "单独模拟"}
                                  </button>
                                </div>
                              </div>
                            </article>
                          `
                        )
                        .join("")}</div>`
                    : `<p class="soft-note">当前这一步还没有稳定匹配到行动模板。</p>`
                }
              </div>
            </article>
          `
        )
        .join("")}</div>`
    : `<p class="soft-note">当前没有足够稳定的多步成长路径，优先参考缺口与 what-if 模拟。</p>`;
  elements.targetGapAnalysis.innerHTML = `
    <article class="detail-card accent-card target-analysis-card">
      <div class="detail-headline">
        <div>
          <p class="panel-kicker">目标岗位</p>
          <h3>${escapeHtml(target.job_name)}</h3>
        </div>
        <div class="score-pill">${Math.round((target.current_score || 0) * 100)} 分</div>
      </div>
      <p class="reason-text">${escapeHtml(target.gap_summary)}</p>
      ${sourceBadges ? `<div class="source-chip-row target-source-row">${sourceBadges}</div>` : ""}
      ${
        leadPath?.labels?.length
          ? `
            <div class="path-track">
              ${leadPath.labels
                .map(
                  (label, index) => `
                    <div class="path-node">
                      <span>${escapeHtml(label)}</span>
                      ${index < leadPath.labels.length - 1 ? '<i>→</i>' : ""}
                    </div>
                  `
                )
                .join("")}
            </div>
          `
          : `<p class="soft-note">当前目标岗位暂无足够长的路径可展示。</p>`
      }
      <div class="detail-grid">
        <div class="detail-card">
          <h4>关键缺口</h4>
          ${
            target.missing_requirements?.length
              ? `<ul class="limit-list">${target.missing_requirements.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
              : target.limitations?.length
                ? `<ul class="limit-list">${target.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
                : `<p class="soft-note">当前没有明显的硬门槛缺口。</p>`
          }
        </div>
        <div class="detail-card">
          <h4>优先补齐建议</h4>
          ${
            target.priority_suggestions?.length
              ? `<ul class="limit-list">${target.priority_suggestions
                  .map(
                    (item) =>
                      `<li>${escapeHtml(`${item.tip}：${item.node_name}（当前 ${Math.round((item.current_score || 0) * 100)} 分）`)}</li>`
                  )
                  .join("")}</ul>`
              : `<p class="soft-note">当前没有额外建议，说明该岗位已接近现有能力上限。</p>`
          }
        </div>
      </div>
      <section class="roadmap-section">
        <div class="subhead">
          <h3>成长路径</h3>
          <p class="soft-note">按前置约束和增益排序，把“先补什么、后补什么”拆成 2-4 步动作。</p>
        </div>
        ${roadmapMarkup}
      </section>
      ${renderActionBundleSection()}
      ${renderActionSimulationSection()}
      <section class="scenario-section">
        <div class="subhead">
          <h3>What-if 模拟</h3>
          <p class="soft-note">轻量注入建议节点后，估算目标岗位分数会怎么变。</p>
        </div>
        ${
          target.what_if_scenarios?.length
            ? `<div class="scenario-list">${target.what_if_scenarios
                .map(
                  (scenario) => `
                    <article class="scenario-card">
                      <div class="scenario-headline">
                        <div>
                          <p class="signal-name">${escapeHtml(scenario.title)}</p>
                          <p class="signal-meta">${escapeHtml(scenario.summary)}</p>
                        </div>
                        <div class="delta-chip">+${Math.round((scenario.delta_score || 0) * 100)}</div>
                      </div>
                      <p class="scenario-score">预计得分 ${Math.round((scenario.predicted_score || 0) * 100)} 分</p>
                      <ul class="limit-list scenario-boost-list">
                        ${scenario.boosts
                          .map(
                            (boost) =>
                              `<li>${escapeHtml(`${boost.node_name}：${Math.round((boost.from_score || 0) * 100)} → ${Math.round((boost.to_score || 0) * 100)} 分`)}</li>`
                          )
                          .join("")}
                      </ul>
                    </article>
                  `
                )
                .join("")}</div>`
            : `<p class="soft-note">当前还没有能稳定抬升该岗位分数的模拟方案。</p>`
        }
      </section>
    </article>
  `;

  elements.targetGapAnalysis.querySelectorAll("[data-simulate-template-id]").forEach((button) => {
    button.addEventListener("click", () => {
      simulateActionTemplate(button.dataset.simulateTemplateId, button.dataset.simulateActionKey);
    });
  });
  elements.targetGapAnalysis.querySelectorAll("[data-bundle-action-key]").forEach((button) => {
    button.addEventListener("click", () => {
      toggleActionBundle(button.dataset.bundleActionKey);
    });
  });
  elements.targetGapAnalysis.querySelectorAll("[data-action-bundle-run]").forEach((button) => {
    button.addEventListener("click", () => {
      simulateActionBundle();
    });
  });
  elements.targetGapAnalysis.querySelectorAll("[data-action-bundle-clear]").forEach((button) => {
    button.addEventListener("click", () => {
      clearActionBundle();
    });
  });
}

function renderActionBundleSection() {
  const selectedActions = getSelectedBundleActions();
  const bundleInsight = buildActionBundleInsight(selectedActions);

  return `
    <section class="scenario-section action-bundle-section">
      <div class="subhead">
        <h3>方案篮子</h3>
        <p class="soft-note">最多选 2 个动作做组合比较，查看它们是互补增益还是重复覆盖。</p>
      </div>
      ${
        selectedActions.length
          ? `
            <article class="scenario-card action-bundle-card">
              <div class="scenario-headline">
                <div>
                  <p class="signal-name">当前已选 ${selectedActions.length} / 2 个动作</p>
                  <p class="signal-meta">${escapeHtml(bundleInsight.summary)}</p>
                </div>
                <div class="delta-chip">${selectedActions.length === 2 ? "组合待算" : "可单步"}</div>
              </div>
              <div class="bundle-chip-list">
                ${selectedActions
                  .map(
                    (action) => `
                      <span class="soft-chip accent-chip">
                        ${escapeHtml(action.title)}
                        <button type="button" class="bundle-chip-remove" data-bundle-action-key="${action.action_key}">×</button>
                      </span>
                    `
                  )
                  .join("")}
              </div>
              ${
                bundleInsight.overlapNames.length
                  ? `<div class="chip-row action-chip-row">${bundleInsight.overlapNames
                      .map((name) => `<span class="soft-chip">重复覆盖 ${escapeHtml(name)}</span>`)
                      .join("")}</div>`
                  : `<p class="soft-note">当前已选动作覆盖范围基本互补，适合看组合收益。</p>`
              }
              <div class="bundle-action-row">
                <button class="primary-btn bundle-run-btn" type="button" data-action-bundle-run ${state.busy ? "disabled" : ""}>
                  ${selectedActions.length === 1 ? "模拟当前动作" : "模拟组合方案"}
                </button>
                <button class="ghost-btn" type="button" data-action-bundle-clear ${state.busy ? "disabled" : ""}>清空方案</button>
              </div>
            </article>
          `
          : `<p class="soft-note">从上方行动卡中加入 1-2 个动作，就能直接比较组合后的分数提升、岗位排名变化和重复覆盖情况。</p>`
      }
    </section>
  `;
}

function renderActionSimulationSection() {
  const simulation = state.actionSimulationResult;
  return `
    <section class="scenario-section action-simulation-section">
      <div class="subhead">
        <h3>行动模拟</h3>
        <p class="soft-note">支持单动作和双动作组合模拟，结果都来自同一套知识图谱重算，而不是前端本地拼接。</p>
      </div>
      ${
        simulation
          ? `
            <article class="scenario-card action-simulation-card">
              <div class="scenario-headline">
                <div>
                  <p class="signal-name">${escapeHtml(simulation.target_role_name)}</p>
                  <p class="signal-meta">${escapeHtml(simulation.summary)}</p>
                </div>
                <div class="delta-chip">${formatSignedScore(simulation.delta_score || 0)}</div>
              </div>
              <div class="simulation-metric-grid">
                <div class="simulation-metric">
                  <span>当前分数</span>
                  <strong>${Math.round((simulation.current_score || 0) * 100)} 分</strong>
                </div>
                <div class="simulation-metric">
                  <span>模拟后分数</span>
                  <strong>${Math.round((simulation.predicted_score || 0) * 100)} 分</strong>
                </div>
                <div class="simulation-metric">
                  <span>岗位排名</span>
                  <strong>${simulation.target_role_rank_before || "-"} → ${simulation.target_role_rank_after || "-"}</strong>
                </div>
              </div>
                ${
                  simulation.applied_actions?.length
                    ? `<div class="chip-row action-chip-row">${simulation.applied_actions
                        .map((action) => `<span class="soft-chip accent-chip">${escapeHtml(action.title)}</span>`)
                        .join("")}</div>`
                    : ""
              }
              ${
                simulation.bundle_size > 1
                  ? `<div class="detail-card bundle-result-card">
                      <h4>组合覆盖分析</h4>
                      <p class="reason-text">${escapeHtml(simulation.bundle_summary || "当前组合会同时覆盖多个证据节点。")}</p>
                      ${
                        simulation.overlap_node_names?.length
                          ? `<div class="chip-row action-chip-row">${simulation.overlap_node_names
                              .map((name) => `<span class="soft-chip">重复覆盖 ${escapeHtml(name)}</span>`)
                              .join("")}</div>`
                          : `<p class="soft-note">这两个动作覆盖范围基本互补，组合收益更多来自新增证据与新增激活。</p>`
                      }
                    </div>`
                  : ""
              }
              <div class="detail-grid simulation-detail-grid">
                <div class="detail-card">
                  <h4>注入的证据节点</h4>
                  ${
                    simulation.injected_boosts?.length
                      ? `<ul class="limit-list">${simulation.injected_boosts
                          .map(
                            (boost) =>
                              `<li>${escapeHtml(
                                `${boost.node_name}：${Math.round((boost.from_score || 0) * 100)} → ${Math.round((boost.to_score || 0) * 100)} 分`
                              )}</li>`
                          )
                          .join("")}</ul>`
                      : `<p class="soft-note">当前行动更偏向巩固已有节点，短期内没有新增证据注入。</p>`
                  }
                </div>
                <div class="detail-card">
                  <h4>被带动的图节点</h4>
                  ${
                    simulation.activated_nodes?.length
                      ? `<ul class="limit-list">${simulation.activated_nodes
                          .map(
                            (node) =>
                              `<li>${escapeHtml(
                                `${node.node_name}（${LAYER_LABELS[node.layer] || node.layer}）：${Math.round((node.before_score || 0) * 100)} → ${Math.round((node.after_score || 0) * 100)} 分`
                              )}</li>`
                          )
                          .join("")}</ul>`
                      : `<p class="soft-note">当前没有足够显著的下游节点增益。</p>`
                  }
                </div>
              </div>
              <div class="role-preview-grid">
                <div class="detail-card">
                  <h4>模拟前 Top 岗位</h4>
                  ${renderRolePreviewList(simulation.before_top_roles)}
                </div>
                <div class="detail-card">
                  <h4>模拟后 Top 岗位</h4>
                  ${renderRolePreviewList(simulation.after_top_roles)}
                </div>
              </div>
            </article>
          `
          : `<p class="soft-note">点击上方“单独模拟”可看单动作收益，或先把 2 个动作加入方案篮子，再比较组合模拟结果。</p>`
      }
    </section>
  `;
}

function buildActionBundleInsight(actions) {
  const overlapNames = [];
  const overlapCounts = new Map();
  const bundleNodeNames = new Map();

  actions.forEach((action) => {
    const nodeIds = [...new Set(action.simulation_node_ids || [])];
    nodeIds.forEach((nodeId) => {
      bundleNodeNames.set(nodeId, lookupNodeMeta(nodeId, nodeId)?.name || nodeId);
      overlapCounts.set(nodeId, (overlapCounts.get(nodeId) || 0) + 1);
    });
  });

  overlapCounts.forEach((count, nodeId) => {
    if (count >= 2) {
      overlapNames.push(bundleNodeNames.get(nodeId) || nodeId);
    }
  });

  if (!actions.length) {
    return { overlapNames, summary: "" };
  }
  if (actions.length === 1) {
    return {
      overlapNames,
      summary: "当前先选了 1 个动作。你可以直接模拟它，也可以再加 1 个动作查看组合收益。",
    };
  }
  if (overlapNames.length) {
    return {
      overlapNames,
      summary: `这两个动作都覆盖 ${overlapNames.join("、")}，组合收益会更偏向巩固共用证据，而不是完全新增。`,
    };
  }
  return {
    overlapNames,
    summary: "这两个动作覆盖范围基本互补，更适合看组合收益和新增带动。",
  };
}

function renderRolePreviewList(items) {
  if (!items?.length) {
    return `<p class="soft-note">当前没有足够稳定的岗位排序变化。</p>`;
  }
  return `
    <div class="role-preview-list">
      ${items
        .map(
          (item, index) => `
            <div class="role-preview-row">
              <span>Top ${index + 1} · ${escapeHtml(item.job_name)}</span>
              <strong>${Math.round((item.score || 0) * 100)} 分</strong>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderStructuredRows() {
  elements.structuredRows.innerHTML = state.input.structured
    .map(
      (row) => `
        <div class="signal-row" data-row-id="${row.id}">
          <label class="field compact">
            <span>节点</span>
            <input class="structured-entity" name="structured_entity_${row.id}" list="catalog-options" value="${escapeHtml(row.entity)}" placeholder="输入技能、工具或偏好" />
          </label>
          <label class="field compact range-field">
            <span>强度 <strong>${formatScore(row.score)}</strong></span>
            <input class="structured-score" name="structured_score_${row.id}" type="range" min="0" max="1" step="0.01" value="${clampScore(row.score)}" />
          </label>
          <button class="icon-btn danger" type="button" data-action="remove-structured">删除</button>
        </div>
      `
    )
    .join("");

  elements.structuredRows.querySelectorAll(".signal-row").forEach((rowElement) => {
    const rowId = rowElement.dataset.rowId;
    const row = state.input.structured.find((item) => item.id === rowId);
    if (!row) return;

    rowElement.querySelector(".structured-entity").addEventListener("input", (event) => {
      row.entity = event.target.value;
    });
    rowElement.querySelector(".structured-score").addEventListener("input", (event) => {
      row.score = Number(event.target.value);
      renderStructuredRows();
    });
    rowElement.querySelector('[data-action="remove-structured"]').addEventListener("click", () => {
      state.input.structured = state.input.structured.filter((item) => item.id !== rowId);
      if (state.input.structured.length === 0) {
        state.input.structured.push(createStructuredRow());
      }
      renderStructuredRows();
    });
  });
}

function renderConfirmedSignals() {
  if (state.confirmedSignals.length === 0) {
    elements.signalList.innerHTML = emptyState("提交一次推荐后，这里会出现标准化节点，可直接微调分值。");
    return;
  }

  elements.signalList.innerHTML = state.confirmedSignals
    .map((item) => {
      const meta = lookupNodeMeta(item.nodeId, item.nodeName);
      return `
        <article class="confirmed-card" data-confirmed-id="${item.id}">
          <div>
            <p class="signal-name">${escapeHtml(item.nodeName || meta?.name || item.nodeId)}</p>
            <p class="signal-meta">${escapeHtml(meta?.node_type || "manual")} · ${escapeHtml(item.source)}</p>
          </div>
          <label class="field compact range-field">
            <span>分值 <strong>${formatScore(item.score)}</strong></span>
            <input class="confirmed-score" name="confirmed_score_${item.id}" type="range" min="0" max="1" step="0.01" value="${clampScore(item.score)}" />
          </label>
          <label class="field compact">
            <span>节点</span>
            <input class="confirmed-entity" name="confirmed_entity_${item.id}" list="catalog-options" value="${escapeHtml(item.nodeName)}" />
          </label>
          <button class="icon-btn danger" type="button" data-action="remove-confirmed">移除</button>
        </article>
      `;
    })
    .join("");

  elements.signalList.querySelectorAll(".confirmed-card").forEach((card) => {
    const signal = state.confirmedSignals.find((item) => item.id === card.dataset.confirmedId);
    if (!signal) return;

    card.querySelector(".confirmed-score").addEventListener("input", (event) => {
      signal.score = Number(event.target.value);
      renderConfirmedSignals();
    });
    card.querySelector(".confirmed-entity").addEventListener("input", (event) => {
      const text = event.target.value.trim();
      const meta = findCatalogByName(text);
      signal.nodeName = text;
      signal.nodeId = meta?.id || "";
    });
    card.querySelector('[data-action="remove-confirmed"]').addEventListener("click", () => {
      state.confirmedSignals = state.confirmedSignals.filter((item) => item.id !== signal.id);
      renderConfirmedSignals();
    });
  });
}

function renderRecommendations() {
  if (!state.result?.recommendations?.length) {
    elements.recommendationList.innerHTML = emptyState(
      state.result
        ? "当前输入还不足以形成有效职业推荐，请补充技能、经历或偏好后再试。"
        : "推荐结果会在这里展示，包括分数、理由和限制项。"
    );
    return;
  }

  elements.recommendationList.innerHTML = state.result.recommendations
    .map((item, index) => {
      const active = item.job_id === state.selectedJobId || (!state.selectedJobId && index === 0);
      return `
        <article class="recommend-card ${active ? "is-active" : ""}" data-job-id="${item.job_id}">
          <div class="recommend-topline">
            <div>
              <p class="rank-chip">Top ${index + 1}</p>
              <h3>${escapeHtml(item.job_name)}</h3>
            </div>
            <div class="score-badge">${Math.round(item.score * 100)}</div>
          </div>
          <div class="score-track"><span style="width: ${Math.min(100, item.score * 100)}%"></span></div>
          <p class="reason-text">${escapeHtml(item.reason)}</p>
          ${renderRecommendationProvenance(item)}
          ${
            item.limitations?.length
              ? `<ul class="limit-list">${item.limitations.map((limit) => `<li>${escapeHtml(limit)}</li>`).join("")}</ul>`
              : `<p class="soft-note">当前没有明显的硬性限制项。</p>`
          }
        </article>
      `;
    })
    .join("");

  elements.recommendationList.querySelectorAll(".recommend-card").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedJobId = card.dataset.jobId;
      state.selectedPathIndex = 0;
      state.selectedNodeId = card.dataset.jobId;
      renderRecommendations();
      renderNearMisses();
      renderPathInspector();
      renderGraph();
    });
  });
}

function renderNearMisses() {
  if (!state.result?.near_miss_roles?.length) {
    elements.nearMissList.innerHTML = "";
    return;
  }

  elements.nearMissList.innerHTML = `
    <div class="near-miss-section">
      <div class="subhead">
        <h3>差一点匹配的岗位</h3>
        <p class="soft-note">这些岗位已经被当前信号部分激活，但还缺关键前置或核心支撑。</p>
      </div>
      <div class="near-miss-grid">
        ${state.result.near_miss_roles
          .map((item) => {
            const active = item.job_id === state.selectedJobId;
            return `
              <article class="recommend-card near-miss-card ${active ? "is-active" : ""}" data-near-miss-job-id="${item.job_id}">
                <div class="recommend-topline">
                  <div>
                    <p class="rank-chip warm">Near Miss</p>
                    <h3>${escapeHtml(item.job_name)}</h3>
                  </div>
                  <div class="score-badge">${Math.round((item.near_miss_score || 0) * 100)}</div>
                </div>
                <div class="score-track warm"><span style="width: ${Math.min(100, (item.near_miss_score || 0) * 100)}%"></span></div>
                <p class="reason-text">${escapeHtml(item.gap_summary)}</p>
                ${
                  item.missing_requirements?.length
                    ? `<p class="soft-note">关键缺口：${escapeHtml(item.missing_requirements.slice(0, 3).join("、"))}</p>`
                    : ""
                }
                ${renderNearMissSuggestions(item)}
              </article>
            `;
          })
          .join("")}
      </div>
    </div>
  `;

  elements.nearMissList.querySelectorAll("[data-near-miss-job-id]").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedJobId = card.dataset.nearMissJobId;
      state.selectedPathIndex = 0;
      state.selectedNodeId = card.dataset.nearMissJobId;
      renderRecommendations();
      renderNearMisses();
      renderPathInspector();
      renderGraph();
    });
  });
}

function renderNearMissSuggestions(item) {
  if (!item.suggestions?.length) {
    return `<p class="soft-note">当前还没有可直接展示的补齐节点。</p>`;
  }
  return `
    <div class="suggestion-row">
      ${item.suggestions
        .map(
          (suggestion) => `
            <span class="suggestion-chip" title="${escapeHtml(`${suggestion.tip} · 当前激活 ${Math.round((suggestion.current_score || 0) * 100)} 分`)}">
              ${escapeHtml(suggestion.tip)} · ${escapeHtml(suggestion.node_name)}
            </span>
          `
        )
        .join("")}
    </div>
  `;
}

function renderPathInspector() {
  const selectedJob = getSelectedJobItem();
  if (!selectedJob) {
    elements.pathInspector.innerHTML = emptyState(
      state.result
        ? "当前还没有可展开的职业路径，请先补充输入或调整确认节点。"
        : "先生成推荐结果，再查看单个职业的路径解释。"
    );
    return;
  }

  const isNearMiss = !Object.prototype.hasOwnProperty.call(selectedJob, "reason");
  const activePath = selectedJob.paths?.[state.selectedPathIndex] || selectedJob.paths?.[0];
  const headerScore = isNearMiss ? selectedJob.near_miss_score || 0 : selectedJob.score || 0;
  elements.pathInspector.innerHTML = `
    <div class="path-head">
      <div>
        <p class="panel-kicker">当前查看</p>
        <h3>${escapeHtml(selectedJob.job_name)}</h3>
      </div>
      <div class="score-pill">${Math.round(headerScore * 100)} ${isNearMiss ? "接近度" : "分"}</div>
    </div>
    <div class="path-list">
      ${
        selectedJob.paths?.length
          ? selectedJob.paths
              .map(
                (path, index) => `
                  <button class="path-chip ${index === state.selectedPathIndex ? "is-active" : ""}" type="button" data-path-index="${index}">
                    路径 ${index + 1} · ${Math.round(path.score * 100)}
                  </button>
                `
              )
              .join("")
          : `<p class="soft-note">当前岗位暂无可展示路径。</p>`
      }
    </div>
    ${
      activePath
        ? `
          <div class="path-track">
            ${activePath.labels
              .map(
                (label, index) => `
                  <div class="path-node">
                    <span>${escapeHtml(label)}</span>
                    ${index < activePath.labels.length - 1 ? '<i>→</i>' : ""}
                  </div>
                `
              )
              .join("")}
          </div>
        `
        : ""
    }
    <div class="detail-grid">
      <div class="detail-card">
        <h4>${isNearMiss ? "差距判断" : "推荐理由"}</h4>
        <p>${escapeHtml(selectedJob.gap_summary || selectedJob.reason)}</p>
      </div>
      <div class="detail-card">
        <h4>${selectedJob.missing_requirements?.length ? "关键缺口" : "限制因素"}</h4>
        ${
          selectedJob.missing_requirements?.length
            ? `<ul class="limit-list">${selectedJob.missing_requirements.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
            : selectedJob.limitations?.length
              ? `<ul class="limit-list">${selectedJob.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
              : `<p class="soft-note">当前未触发明显限制。</p>`
        }
      </div>
      <div class="detail-card">
        <h4>补齐建议</h4>
        ${
          selectedJob.suggestions?.length
            ? `<ul class="limit-list">${selectedJob.suggestions
                .map(
                  (item) =>
                    `<li>${escapeHtml(`${item.tip}：${item.node_name}（当前 ${Math.round((item.current_score || 0) * 100)} 分）`)}</li>`
                )
                .join("")}</ul>`
            : `<p class="soft-note">当前没有额外补齐建议。</p>`
        }
      </div>
    </div>
  `;

  elements.pathInspector.querySelectorAll("[data-path-index]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedPathIndex = Number(button.dataset.pathIndex || 0);
      renderPathInspector();
      renderGraph();
    });
  });
}

function renderGraph() {
  const snapshot = state.result?.propagation_snapshot;
  if (!snapshot?.nodes?.length) {
    elements.graphArea.innerHTML = emptyState("传播图会在推荐结果生成后出现。");
    elements.graphDetail.innerHTML = "";
    return;
  }

  const selectedPath = getSelectedPath();
  const visibleNodes = buildVisibleNodes(snapshot.nodes, selectedPath);
  const visibleNodeIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = (snapshot.edges || []).filter(
    (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
  );
  const layout = buildGraphLayout(visibleNodes);
  const highlightedSegments = new Set(
    selectedPath
      ? selectedPath.node_ids.slice(0, -1).map((nodeId, index) => `${nodeId}->${selectedPath.node_ids[index + 1]}`)
      : []
  );
  const selectedNode =
    visibleNodes.find((node) => node.id === state.selectedNodeId) ||
    visibleNodes.find((node) => node.id === state.selectedJobId) ||
    (selectedPath ? visibleNodes.find((node) => node.id === selectedPath.node_ids[selectedPath.node_ids.length - 1]) : null) ||
    visibleNodes[0];

  elements.graphArea.innerHTML = `
    <svg class="graph-svg" viewBox="0 0 1120 620" role="img" aria-label="Propagation graph">
      ${LAYER_ORDER.map((layer, index) => {
        const x = 110 + index * 210;
        return `
          <g>
            <text class="layer-title" x="${x}" y="42">${escapeHtml(LAYER_LABELS[layer])}</text>
            <line class="layer-divider" x1="${x}" y1="60" x2="${x}" y2="580"></line>
          </g>
        `;
      }).join("")}
      ${visibleEdges
        .map((edge) => {
          const source = layout.get(edge.source);
          const target = layout.get(edge.target);
          if (!source || !target) return "";
          const segmentKey = `${edge.source}->${edge.target}`;
          const relationColor = RELATION_COLORS[edge.relation] || "#92a39b";
          const opacity = highlightedSegments.size === 0 ? 0.38 : highlightedSegments.has(segmentKey) ? 0.92 : 0.14;
          const strokeWidth = highlightedSegments.has(segmentKey) ? 4.2 : Math.max(1.2, edge.value * 18);
          return `
            <line
              x1="${source.x + 70}"
              y1="${source.y}"
              x2="${target.x - 70}"
              y2="${target.y}"
              stroke="${relationColor}"
              stroke-width="${strokeWidth}"
              opacity="${opacity}"
              stroke-linecap="round"
            />
          `;
        })
        .join("")}
      ${visibleNodes
        .map((node) => {
          const point = layout.get(node.id);
          const pathHighlight = selectedPath?.node_ids.includes(node.id);
          const selected = selectedNode?.id === node.id;
          const fill = scoreToColor(node.score);
          return `
            <g class="graph-node ${selected ? "is-selected" : ""} ${pathHighlight ? "is-highlighted" : ""}" data-node-id="${node.id}">
              <rect x="${point.x - 68}" y="${point.y - 26}" rx="18" ry="18" width="136" height="52" fill="${fill}" opacity="0.98"></rect>
              <text x="${point.x}" y="${point.y - 3}" text-anchor="middle">${escapeHtml(node.name)}</text>
              <text x="${point.x}" y="${point.y + 16}" text-anchor="middle">${Math.round(node.score * 100)} 分</text>
            </g>
          `;
        })
        .join("")}
    </svg>
  `;

  elements.graphArea.querySelectorAll("[data-node-id]").forEach((nodeElement) => {
    nodeElement.addEventListener("click", () => {
      state.selectedNodeId = nodeElement.dataset.nodeId;
      renderGraph();
    });
  });

  elements.graphDetail.innerHTML = renderGraphDetail(selectedNode);
}

function renderGraphDetail(node) {
  if (!node) {
    return "";
  }
  const sourceRefs = Array.isArray(node.metadata?.source_refs) ? node.metadata.source_refs : [];
  const diagnostics = Object.entries(node.diagnostics || {})
    .map(([key, value]) => `<li><span>${escapeHtml(key)}</span><strong>${escapeHtml(formatDiagnosticValue(value))}</strong></li>`)
    .join("");
  return `
    <article class="detail-card accent-card">
      <div class="detail-headline">
        <div>
          <p class="panel-kicker">节点详情</p>
          <h3>${escapeHtml(node.name)}</h3>
        </div>
        <div class="score-pill">${Math.round(node.score * 100)} 分</div>
      </div>
      <p class="node-summary">${escapeHtml(LAYER_LABELS[node.layer] || node.layer)} · ${escapeHtml(node.node_type || node.aggregator)} · ${escapeHtml(node.aggregator)}</p>
      ${node.description ? `<p class="node-description">${escapeHtml(node.description)}</p>` : ""}
      ${renderSourceRefs(sourceRefs, node.metadata?.provenance_count || sourceRefs.length)}
      ${
        diagnostics.length
          ? `<ul class="diagnostic-list">${diagnostics}</ul>`
          : `<p class="soft-note">当前节点没有额外诊断项。</p>`
      }
    </article>
  `;
}

function renderNotice() {
  const notes = [];
  if (state.busy && state.statusMessage) notes.push(`<span class="badge busy">${escapeHtml(state.statusMessage)}</span>`);
  if (!state.busy && state.statusMessage) notes.push(`<span class="badge success">${escapeHtml(state.statusMessage)}</span>`);
  if (state.errorMessage) notes.push(`<span class="badge error">${escapeHtml(state.errorMessage)}</span>`);
  if (state.result?.parsing_notes?.length) {
    notes.push(`<span class="badge neutral">解析命中：${escapeHtml(state.result.parsing_notes.slice(0, 4).join(" · "))}</span>`);
  }
  if (state.result?.parsing_debug?.rule_hits?.length) {
    notes.push(`<span class="badge neutral">规则命中：${state.result.parsing_debug.rule_hits.length}</span>`);
  }
  if (state.result?.parsing_debug?.unmatched_segments?.length) {
    notes.push(
      `<span class="badge neutral">未充分解析：${escapeHtml(
        state.result.parsing_debug.unmatched_segments.slice(0, 3).join(" / ")
      )}</span>`
    );
  }
  if (state.result?.unresolved_entities?.length) {
    notes.push(`<span class="badge neutral">未识别：${escapeHtml(state.result.unresolved_entities.join("、"))}</span>`);
  }
  if (state.result?.graph_stats?.source_profile_count) {
    notes.push(
      `<span class="badge neutral">来源画像：${state.result.graph_stats.source_profile_count} 条 / ${state.result.graph_stats.source_type_count || 0} 类 / 溯源节点 ${state.result.graph_stats.nodes_with_provenance}</span>`
    );
  }
  elements.requestNotes.innerHTML = notes.join("") || `<span class="badge neutral">建议先输入自然语言，再按需要补充结构化节点。</span>`;
}

function buildVisibleNodes(nodes, selectedPath) {
  const byLayer = new Map(LAYER_ORDER.map((layer) => [layer, []]));
  nodes.forEach((node) => {
    if (byLayer.has(node.layer)) {
      byLayer.get(node.layer).push(node);
    }
  });

  const selectedIds = new Set(selectedPath?.node_ids || []);
  const visible = [];
  for (const layer of LAYER_ORDER) {
    const sorted = (byLayer.get(layer) || []).sort((a, b) => b.score - a.score);
    const limited = sorted.slice(0, LAYER_LIMITS[layer]);
    const missingSelected = sorted.filter((node) => selectedIds.has(node.id) && !limited.some((item) => item.id === node.id));
    visible.push(...limited, ...missingSelected);
  }

  const unique = new Map();
  visible.forEach((node) => unique.set(node.id, node));
  return Array.from(unique.values());
}

function buildGraphLayout(nodes) {
  const layout = new Map();
  for (const [layerIndex, layer] of LAYER_ORDER.entries()) {
    const layerNodes = nodes.filter((node) => node.layer === layer).sort((a, b) => b.score - a.score);
    const usableHeight = 460;
    const gap = layerNodes.length > 1 ? usableHeight / (layerNodes.length - 1) : 0;
    layerNodes.forEach((node, index) => {
      layout.set(node.id, {
        x: 120 + layerIndex * 210,
        y: 110 + (layerNodes.length > 1 ? gap * index : usableHeight / 2),
      });
    });
  }
  return layout;
}

function findJobById(result, jobId) {
  if (!result || !jobId) {
    return null;
  }
  return (
    result.recommendations?.find((item) => item.job_id === jobId) ||
    result.near_miss_roles?.find((item) => item.job_id === jobId) ||
    null
  );
}

function pickInitialJobId(result) {
  return result?.recommendations?.[0]?.job_id || result?.near_miss_roles?.[0]?.job_id || null;
}

function getSelectedJobItem() {
  if (!state.result) {
    return null;
  }
  return findJobById(state.result, state.selectedJobId) || state.result.recommendations?.[0] || state.result.near_miss_roles?.[0] || null;
}

function getSelectedPath() {
  const item = getSelectedJobItem();
  if (!item?.paths?.length) {
    return null;
  }
  return item.paths[state.selectedPathIndex] || item.paths[0];
}

function renderRecommendationProvenance(item) {
  const sourceRefs = Array.isArray(item.source_refs) ? item.source_refs : [];
  if (!sourceRefs.length) {
    return `<p class="soft-note">当前岗位还没有外部职业画像锚点。</p>`;
  }
  const primarySource = sourceRefs[0];
  const extraCount = Math.max(0, (item.provenance_count || sourceRefs.length) - 1);
  const sourceLabel = [formatSourceType(primarySource.source_type), primarySource.snapshot_date].filter(Boolean).join(" · ");
  const sourceJobs = Array.isArray(primarySource.sample_job_titles) && primarySource.sample_job_titles.length
    ? `样例岗位：${escapeHtml(primarySource.sample_job_titles.slice(0, 3).join("、"))}`
    : "";
  return `
    <div class="source-summary">
      <div class="source-headline">
        <p class="source-note">外部来源锚点 ${item.provenance_count || sourceRefs.length} 条</p>
        <div class="source-chip-row">${renderSourceTypeBadges(item.source_types || sourceRefs.map((source) => source.source_type))}</div>
      </div>
      <p class="source-inline">
        <strong>${escapeHtml(primarySource.source_title || primarySource.source_id || primarySource.profile_id)}</strong>
        ${sourceLabel ? `<span>${escapeHtml(sourceLabel)}</span>` : ""}
      </p>
      ${sourceJobs ? `<p class="source-jobs">${sourceJobs}</p>` : ""}
      <p class="source-more">${item.source_type_count || 1} 类来源共同支撑该岗位。${extraCount > 0 ? `另有 ${extraCount} 条来源可在传播图节点详情中查看。` : ""}</p>
    </div>
  `;
}

function renderSourceRefs(sourceRefs, provenanceCount) {
  if (!sourceRefs.length) {
    return `<p class="soft-note">该节点当前没有外部来源画像锚点。</p>`;
  }
  const groupedSources = groupSourceRefsByType(sourceRefs);
  const totalCount = provenanceCount || sourceRefs.length;
  const extraCount = Math.max(0, totalCount - sourceRefs.length);
  return `
    <section class="source-block">
      <div class="source-headline">
        <p class="source-note">来源画像 ${totalCount} 条</p>
        <div class="source-chip-row">${renderSourceTypeBadges(Object.keys(groupedSources))}</div>
      </div>
      ${Object.entries(groupedSources)
        .map(([sourceType, refs]) => {
          return `
            <div class="source-group">
              <div class="source-group-head">
                <strong>${escapeHtml(formatSourceType(sourceType))}</strong>
                <span>${refs.length} 条</span>
              </div>
              <ul class="source-list">
                ${refs
                  .map((source) => {
                    const meta = [formatSourceType(source.source_type), source.snapshot_date].filter(Boolean).join(" · ");
                    const jobs = Array.isArray(source.sample_job_titles) && source.sample_job_titles.length
                      ? `样例岗位：${escapeHtml(source.sample_job_titles.slice(0, 4).join("、"))}`
                      : "";
                    return `
                      <li>
                        <div class="source-head">
                          <strong>${escapeHtml(source.source_title || source.source_id || source.profile_id)}</strong>
                          ${source.source_url ? `<a class="source-link" href="${escapeHtml(source.source_url)}" target="_blank" rel="noreferrer">原始来源</a>` : ""}
                        </div>
                        ${meta ? `<p class="source-inline">${escapeHtml(meta)}</p>` : ""}
                        ${source.evidence_snippet ? `<p class="source-snippet">${escapeHtml(source.evidence_snippet)}</p>` : ""}
                        ${jobs ? `<p class="source-jobs">${jobs}</p>` : ""}
                      </li>
                    `;
                  })
                  .join("")}
              </ul>
            </div>
          `;
        })
        .join("")}
      ${extraCount > 0 ? `<p class="source-more">还有 ${extraCount} 条来源未在当前面板展开。</p>` : ""}
    </section>
  `;
}

function groupSourceRefsByType(sourceRefs) {
  const groups = {};
  sourceRefs.forEach((source) => {
    const sourceType = source?.source_type || "unknown";
    if (!groups[sourceType]) {
      groups[sourceType] = [];
    }
    groups[sourceType].push(source);
  });
  return Object.fromEntries(Object.entries(groups).sort(([left], [right]) => left.localeCompare(right)));
}

function renderSourceTypeBadges(sourceTypes) {
  const uniqueTypes = Array.from(new Set((sourceTypes || []).filter(Boolean)));
  return uniqueTypes
    .sort((left, right) => left.localeCompare(right))
    .map((sourceType) => `<span class="source-chip">${escapeHtml(formatSourceType(sourceType))}</span>`)
    .join("");
}

function formatSourceType(sourceType) {
  return SOURCE_TYPE_LABELS[sourceType] || sourceType || "未知来源";
}

function lookupNodeMeta(nodeId, nodeName = "") {
  return state.catalog.find((node) => node.id === nodeId || node.name === nodeName) || null;
}

function findCatalogByName(name) {
  const normalized = name.trim().toLowerCase();
  return state.catalog.find((node) => node.name.toLowerCase() === normalized || node.id.toLowerCase() === normalized) || null;
}

async function fetchJSON(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `HTTP ${response.status}`);
  }
  return response.json();
}

function formatScore(score) {
  return clampScore(score).toFixed(2);
}

function formatSignedScore(score) {
  const value = Number(score) || 0;
  const percent = Math.round(Math.abs(value) * 100);
  if (value > 0) return `+${percent}`;
  if (value < 0) return `-${percent}`;
  return "±0";
}

function formatDiagnosticValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join("、") : "无";
  }
  if (typeof value === "number") {
    return value.toFixed(2);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return String(value);
}

function clampScore(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return 0;
  return Math.max(0, Math.min(1, numeric));
}

function scoreToColor(score) {
  const clamped = clampScore(score);
  const hue = 195 - Math.round(clamped * 88);
  const saturation = 48 + Math.round(clamped * 20);
  const lightness = 88 - Math.round(clamped * 30);
  return `hsl(${hue} ${saturation}% ${lightness}%)`;
}

function emptyState(text) {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

init();
