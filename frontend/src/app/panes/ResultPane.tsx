import { useEffect, useState } from "react";

import { SourceProfileList } from "../components/SourceProfileList";
import { formatPercent } from "../lib/scoring";
import { useRecommendationFlow } from "../hooks/useRecommendationFlow";
import type { GapSuggestion, ResultCard, SourceRef } from "../types/api";

type ResultGroupKey = "recommendation" | "near_miss" | "bridge";

function scoreForCard(card: ResultCard): number {
  if (card.kind === "recommendation") {
    return card.score;
  }
  if (card.kind === "near_miss") {
    return card.near_miss_score;
  }
  return card.bridge_score;
}

function titleForCard(card: ResultCard): string {
  if (card.kind === "bridge") {
    return card.anchor_name;
  }
  return card.job_name;
}

function summaryForCard(card: ResultCard): string {
  if (card.kind === "recommendation") {
    return card.reason;
  }
  if (card.kind === "near_miss") {
    return card.gap_summary;
  }
  return card.summary;
}

function sourceRefsForCard(card: ResultCard): SourceRef[] {
  return card.source_refs || [];
}

function groupKeyForCard(card: ResultCard): ResultGroupKey {
  if (card.kind === "recommendation") {
    return "recommendation";
  }
  if (card.kind === "near_miss") {
    return "near_miss";
  }
  return "bridge";
}

function selectCard(flow: ReturnType<typeof useRecommendationFlow>, card: ResultCard) {
  if (card.kind === "recommendation") {
    flow.selectResult({ kind: "recommendation", id: card.job_id });
    return;
  }
  if (card.kind === "near_miss") {
    flow.selectResult({ kind: "near_miss", id: card.job_id });
    return;
  }
  flow.selectResult({ kind: "bridge", id: card.anchor_id });
}

function renderSuggestionChips(suggestions: GapSuggestion[]) {
  if (!suggestions.length) {
    return <div className="empty-slot compact">当前没有稳定的下一步建议。</div>;
  }
  return (
    <div className="chip-row">
      {suggestions.map((suggestion) => (
        <span key={`${suggestion.node_id}-${suggestion.tip}`} className="soft-chip accent-chip">
          {suggestion.tip} · {suggestion.node_name}
        </span>
      ))}
    </div>
  );
}

function SelectedResultDetail({
  card,
  selectedPathIndex,
  onSelectPathIndex,
}: {
  card: ResultCard | null;
  selectedPathIndex: number;
  onSelectPathIndex: (index: number) => void;
}) {
  if (!card) {
    return <div className="empty-slot">先点选一张结果卡片，再查看路径、限制与来源。</div>;
  }

  const activePath = card.paths?.[selectedPathIndex] || card.paths?.[0];
  const suggestions =
    card.kind === "bridge" ? card.next_steps : card.kind === "near_miss" ? card.suggestions : ([] as GapSuggestion[]);

  return (
    <section key={`${card.key}-${selectedPathIndex}`} className="section-card detail-panel result-reveal">
      <div className="section-head">
        <div>
          <h3>{titleForCard(card)}</h3>
          <p>{summaryForCard(card)}</p>
        </div>
        <span className="score-badge">{formatPercent(scoreForCard(card))}</span>
      </div>

      {card.paths?.length ? (
        <div className="path-cluster">
          {card.paths.length > 1 ? (
            <label className="field-block path-picker" htmlFor="result-path-select">
              <span className="micro-label">解释路径</span>
              <select
                id="result-path-select"
                className="editor-select"
                value={Math.min(selectedPathIndex, card.paths.length - 1)}
                onChange={(event) => onSelectPathIndex(Number(event.target.value))}
              >
                {card.paths.map((path, index) => (
                  <option key={`${titleForCard(card)}-${path.score}-${index}`} value={index}>
                    路径 {index + 1} / {formatPercent(path.score)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {activePath ? (
            <div className="path-track">
              {activePath.labels.map((label, index) => (
                <div key={`${label}-${index}`} className="path-node">
                  <span>{label}</span>
                  {index < activePath.labels.length - 1 ? <i>→</i> : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="empty-slot compact">当前卡片没有稳定路径，属于更稀疏的桥接结果。</div>
      )}

      <div className="detail-grid">
        <div className="mini-panel">
          <h4>限制与缺口</h4>
          {card.kind === "near_miss" && card.missing_requirements.length ? (
            <ul className="list-stack">
              {card.missing_requirements.map((item) => (
                <li key={item}>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : card.limitations.length ? (
            <ul className="list-stack">
              {card.limitations.map((item) => (
                <li key={item}>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-slot compact">当前没有额外限制说明。</div>
          )}
        </div>
        <div className="mini-panel">
          <h4>下一步建议</h4>
          {renderSuggestionChips(suggestions)}
          {card.kind === "bridge" && card.related_roles.length ? (
            <div className="chip-row top-gap">
              {card.related_roles.map((role) => (
                <span key={role.job_id} className="soft-chip">
                  {role.job_name}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className="mini-panel">
        <h4>来源锚点</h4>
        <SourceProfileList sources={sourceRefsForCard(card)} emptyText="这个结果卡片当前没有来源锚点。" />
      </div>
    </section>
  );
}

export function ResultPane({ flow }: { flow: ReturnType<typeof useRecommendationFlow> }) {
  const [activeResultGroup, setActiveResultGroup] = useState<ResultGroupKey>("recommendation");

  const resultGroups = [
    {
      key: "recommendation" as const,
      label: "推荐",
      title: "Strong Match",
      description: "直接穿透岗位门槛的正式推荐。",
      empty: flow.recommendation?.empty_result_reason || "当前还没有正式推荐。",
      cards: flow.cards.recommendations,
    },
    {
      key: "near_miss" as const,
      label: "临门一脚",
      title: "Near Miss",
      description: "已经被激活，但还差关键前置或核心支撑。",
      empty: "当前没有需要重点补缺口的岗位。",
      cards: flow.cards.nearMisses,
    },
    {
      key: "bridge" as const,
      label: "桥接",
      title: "Bridge",
      description: "给稀疏输入准备的桥接方向，避免空白结果页。",
      empty: "当前没有桥接方向。",
      cards: flow.cards.bridges,
    },
  ];
  const activeResultMeta = resultGroups.find((group) => group.key === activeResultGroup) || resultGroups[0];
  const activeResultCards = activeResultMeta.cards;
  const activeResultCard =
    flow.selectedCard && groupKeyForCard(flow.selectedCard) === activeResultGroup ? flow.selectedCard : activeResultCards[0] || null;

  useEffect(() => {
    if (flow.selectedCard) {
      setActiveResultGroup(groupKeyForCard(flow.selectedCard));
    }
  }, [flow.selectedCard]);

  useEffect(() => {
    if (!activeResultCards.length) {
      return;
    }

    if (!activeResultCard || !activeResultCards.some((card) => card.key === activeResultCard.key)) {
      selectCard(flow, activeResultCards[0]);
    }
  }, [activeResultCard, activeResultCards, activeResultGroup, flow, resultGroups]);

  return (
    <section className="pane pane-results">
      <div className="pane-header">
        <div>
          <p className="section-kicker">Results</p>
          <h2>结果解释</h2>
        </div>
      </div>

      <div className="pane-scroll">
          <div className={`result-browser result-browser--${activeResultGroup}`}>
            <div className="result-browser-head">
              <div>
                <h3>{activeResultMeta.title}</h3>
              </div>
              <label className="field-block inline-select" htmlFor="result-group-select">
                <span className="micro-label">结果类型</span>
                <select
                  id="result-group-select"
                  className="editor-select"
                  value={activeResultGroup}
                  onChange={(event) => {
                    const nextGroup = resultGroups.find((group) => group.key === event.target.value);
                    if (!nextGroup) {
                      return;
                    }
                    setActiveResultGroup(nextGroup.key);
                    if (nextGroup.cards[0]) {
                      selectCard(flow, nextGroup.cards[0]);
                    }
                  }}
                >
                  {resultGroups.map((group) => (
                    <option key={group.key} value={group.key}>
                      {group.label} ({group.cards.length})
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {activeResultCards.length ? (
              <>
                <label className="field-block result-picker" htmlFor="result-card-select">
                  <span className="micro-label">当前结果</span>
                  <select
                    id="result-card-select"
                    className="editor-select"
                    value={activeResultCard?.key || ""}
                    onChange={(event) => {
                      const nextCard = activeResultCards.find((card) => card.key === event.target.value);
                      if (nextCard) {
                        selectCard(flow, nextCard);
                      }
                    }}
                  >
                    {activeResultCards.map((card) => (
                      <option key={card.key} value={card.key}>
                        {formatPercent(scoreForCard(card))} / {titleForCard(card)}
                      </option>
                    ))}
                  </select>
                </label>

                <SelectedResultDetail
                  card={activeResultCard}
                  selectedPathIndex={flow.selectedPathIndex}
                  onSelectPathIndex={flow.setSelectedPathIndex}
                />
              </>
            ) : (
              <div className="empty-slot compact">{activeResultMeta.empty}</div>
            )}
          </div>
      </div>
    </section>
  );
}
