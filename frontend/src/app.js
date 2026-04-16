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
    const graphStats = payload.graph_stats || {};
    elements.graphSize.textContent =
      `${graphStats.node_count || 0} 节点 / ${graphStats.edge_count || 0} 边 / ${graphStats.source_profile_count || 0} 条来源画像 / ${graphStats.source_type_count || 0} 类来源`;
    elements.roleCount.textContent =
      `${graphStats.role_count || 0} 个岗位 / ${graphStats.nodes_with_provenance || 0} 个溯源节点`;
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
