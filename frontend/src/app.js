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

const state = {
  catalog: [],
  sampleRequest: null,
  input: {
    text: "",
    structured: [],
  },
  confirmedSignals: [],
  result: null,
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
  addStructuredRowBtn: document.querySelector("#add-structured-row-btn"),
  addConfirmedRowBtn: document.querySelector("#add-confirmed-row-btn"),
  structuredRows: document.querySelector("#structured-rows"),
  requestNotes: document.querySelector("#request-notes"),
  signalList: document.querySelector("#normalized-signals"),
  recommendationList: document.querySelector("#recommendation-list"),
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
    state.sampleRequest = payload.sample_request || null;
    elements.graphSize.textContent = `${payload.graph_stats.node_count} 节点 / ${payload.graph_stats.edge_count} 边`;
    elements.roleCount.textContent = `${payload.graph_stats.role_count} 个岗位`;
    if (state.input.structured.length === 0) {
      state.input.structured.push(createStructuredRow());
    }
    renderCatalogOptions();
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
  const payload = {
    text: state.input.text.trim(),
    signals: state.input.structured
      .map((row) => ({ entity: row.entity.trim(), score: clampScore(row.score) }))
      .filter((row) => row.entity),
    top_k: 6,
    include_snapshot: true,
  };
  if (!payload.text && payload.signals.length === 0) {
    setError("请至少提供一条自然语言描述或结构化信号，再生成推荐。");
    return;
  }

  setBusy(true, "正在解析输入并运行图推理…");
  try {
    const result = await postJSON("/api/recommend", payload);
    state.result = result;
    state.confirmedSignals = (result.normalized_inputs || []).map((item) => ({
      id: uid(),
      nodeId: item.node_id,
      nodeName: item.node_name,
      score: clampScore(item.score),
      source: item.source,
    }));
    const firstRecommendation = result.recommendations?.[0];
    state.selectedJobId = firstRecommendation ? firstRecommendation.job_id : null;
    state.selectedPathIndex = 0;
    state.selectedNodeId = null;
    setBusy(false, "推荐结果已更新，可继续微调节点后重算。");
    renderAll();
  } catch (error) {
    setError(`推荐请求失败：${error.message}`);
  }
}

async function recomputeFromConfirmedSignals() {
  const signals = state.confirmedSignals
    .map((item) => ({
      entity: item.nodeId || item.nodeName,
      score: clampScore(item.score),
    }))
    .filter((item) => item.entity);

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
    state.confirmedSignals = (result.normalized_inputs || []).map((item) => ({
      id: uid(),
      nodeId: item.node_id,
      nodeName: item.node_name,
      score: clampScore(item.score),
      source: "confirmed",
    }));
    const stillSelected = result.recommendations?.find((item) => item.job_id === state.selectedJobId);
    state.selectedJobId = stillSelected ? stillSelected.job_id : result.recommendations?.[0]?.job_id || null;
    state.selectedPathIndex = 0;
    state.selectedNodeId = null;
    setBusy(false, "已基于确认节点重新计算。");
    renderAll();
  } catch (error) {
    setError(`重算失败：${error.message}`);
  }
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
  renderStructuredRows();
  renderConfirmedSignals();
  renderRecommendations();
  renderPathInspector();
  renderGraph();
  renderNotice();
}

function renderCatalogOptions() {
  elements.catalogOptions.innerHTML = state.catalog
    .map((node) => `<option value="${escapeHtml(node.name)}"></option>`)
    .join("");
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
      state.selectedNodeId = null;
      renderRecommendations();
      renderPathInspector();
      renderGraph();
    });
  });
}

function renderPathInspector() {
  const selectedRecommendation = getSelectedRecommendation();
  if (!selectedRecommendation) {
    elements.pathInspector.innerHTML = emptyState(
      state.result
        ? "当前还没有可展开的职业路径，请先补充输入或调整确认节点。"
        : "先生成推荐结果，再查看单个职业的路径解释。"
    );
    return;
  }

  const activePath = selectedRecommendation.paths?.[state.selectedPathIndex] || selectedRecommendation.paths?.[0];
  elements.pathInspector.innerHTML = `
    <div class="path-head">
      <div>
        <p class="panel-kicker">当前查看</p>
        <h3>${escapeHtml(selectedRecommendation.job_name)}</h3>
      </div>
      <div class="score-pill">${Math.round(selectedRecommendation.score * 100)} 分</div>
    </div>
    <div class="path-list">
      ${
        selectedRecommendation.paths?.length
          ? selectedRecommendation.paths
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
        <h4>推荐理由</h4>
        <p>${escapeHtml(selectedRecommendation.reason)}</p>
      </div>
      <div class="detail-card">
        <h4>限制因素</h4>
        ${
          selectedRecommendation.limitations?.length
            ? `<ul class="limit-list">${selectedRecommendation.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
            : `<p class="soft-note">当前未触发明显限制。</p>`
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
  const selectedNode = visibleNodes.find((node) => node.id === state.selectedNodeId) || visibleNodes[0];

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
      <p class="node-summary">${escapeHtml(LAYER_LABELS[node.layer] || node.layer)} · ${escapeHtml(node.aggregator)}</p>
      <ul class="diagnostic-list">${diagnostics}</ul>
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

function getSelectedRecommendation() {
  if (!state.result?.recommendations?.length) {
    return null;
  }
  return (
    state.result.recommendations.find((item) => item.job_id === state.selectedJobId) ||
    state.result.recommendations[0]
  );
}

function getSelectedPath() {
  const recommendation = getSelectedRecommendation();
  if (!recommendation?.paths?.length) {
    return null;
  }
  return recommendation.paths[state.selectedPathIndex] || recommendation.paths[0];
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
