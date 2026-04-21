import { InfoTip } from "../components/InfoTip";
import { useRecommendationFlow } from "../hooks/useRecommendationFlow";

const inputGuide = "填写技能、项目经历、偏好和不擅长的内容。可直接用自然语言，不需要选择职业；越具体，系统打分越准。";

export function InputPane({ flow, onNext }: { flow: ReturnType<typeof useRecommendationFlow>; onNext: () => void }) {
  async function runAndContinue() {
    const ok =
      flow.confirmedSignals.length && flow.confirmedSignalsDirty
        ? await flow.recomputeFromConfirmedSignals()
        : flow.recommendation
          ? true
          : await flow.submitInitialRecommendation();
    if (!ok) {
      return;
    }
    onNext();
  }

  return (
    <section className="pane pane-support">
      <div className="pane-header">
        <div>
          <p className="section-kicker">Input</p>
          <div className="title-with-tip">
            <h2>填写与画像</h2>
            <InfoTip text={inputGuide} />
          </div>
        </div>
        <div className="chip-row">
          <button className="primary-button compact-control" type="button" onClick={() => void runAndContinue()} disabled={flow.status.busy}>
            下一步：微调
          </button>
        </div>
      </div>

      <div className="pane-scroll support-pane-scroll unified-input-flow input-only-flow">
        <section className="section-card support-panel">
          <label className="field-block" htmlFor="profile-input">
            <span className="micro-label">画像描述</span>
            <textarea
              id="profile-input"
              className="editor-textarea"
              value={flow.inputText}
              onChange={(event) => flow.setInputText(event.target.value)}
              placeholder="例如：我熟悉 Python 和 SQL，做过后端接口项目，不太擅长数学，更偏好稳定交付，不喜欢频繁 on-call。"
            />
          </label>
        </section>
      </div>
    </section>
  );
}
