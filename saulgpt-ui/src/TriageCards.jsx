import { useState } from "react";

const SWOT_COLORS = {
  strengths:     { bg: "rgba(40, 167, 69, 0.08)", border: "#28a745", icon: "▲" },
  weaknesses:    { bg: "rgba(220, 53, 69, 0.08)", border: "#dc3545", icon: "▼" },
  opportunities: { bg: "rgba(0, 123, 255, 0.08)", border: "#007bff", icon: "★" },
  threats:       { bg: "rgba(255, 193, 7, 0.08)", border: "#ffc107", icon: "⚠" },
};

function SWOTBox({ label, items }) {
  const cfg = SWOT_COLORS[label];
  if (!items || items.length === 0) return null;
  return (
    <div className="swot-box" style={{ background: cfg.bg, borderLeft: `3px solid ${cfg.border}` }}>
      <div className="swot-label">
        <span className="swot-icon">{cfg.icon}</span>
        {label.charAt(0).toUpperCase() + label.slice(1)}
      </div>
      <ul className="swot-list">
        {items.map((item, i) => (
          <li key={i} className="swot-item">{item}</li>
        ))}
      </ul>
    </div>
  );
}

function InfoBanner({ type, message }) {
  if (!message) return null;
  const isWarn = type === "warning";
  return (
    <div className={`info-banner ${isWarn ? "warn" : "note"}`}>
      <span className="info-icon">{isWarn ? "⚠" : "ℹ"}</span>
      <span className="info-text">{message}</span>
    </div>
  );
}

export default function TriageCards({ triage, onChoose }) {
  const [showSwot, setShowSwot] = useState(false);
  const swot = triage?.swot_analysis;
  const options = triage?.options || [];
  const isExplanation = triage?.is_explanation;
  const isIntake = triage?.is_intake_needed;
  const limitationWarning = triage?.limitation_warning;
  const jurisdictionNote = triage?.jurisdiction_note;
  const allowAdvocate = triage?.allow_advocate !== false;

  // Intake mode: no cards, no SWOT — just let the bot message show the question
  if (isExplanation || isIntake) return null;

  if (!options.length) return null;

  return (
    <div className="triage-cards">
      <div className="triage-header">
        <span className="triage-icon">◇</span>
        Strategic Options
      </div>

      {/* Limitation warning banner */}
      <InfoBanner type="warning" message={limitationWarning} />

      {/* Jurisdiction note banner */}
      <InfoBanner type="note" message={jurisdictionNote} />

      {/* Option cards */}
      <div className="triage-options">
        {options.map((opt) => (
          <button
            key={opt.id}
            className="triage-option-card"
            onClick={() => onChoose(opt.id)}
          >
            <span className="triage-option-label">{opt.label}</span>
            <span className="triage-option-desc">{opt.description}</span>
            <span className="triage-option-arrow">→</span>
          </button>
        ))}
      </div>

      {/* Action row */}
      <div className="triage-actions">
        {swot && (
          <button
            className="triage-action-btn"
            onClick={() => setShowSwot(!showSwot)}
          >
            {showSwot ? "▲ Hide Analysis" : "▼ Show Analysis"}
          </button>
        )}
        {triage.allow_explanation && (
          <button
            className="triage-action-btn"
            onClick={() => onChoose("explain")}
          >
            ? Explain These Options
          </button>
        )}
        {allowAdvocate && (
          <button
            className="triage-action-btn advocate-btn"
            onClick={() => onChoose("advocate")}
          >
            ⚖ Advocate Mode
          </button>
        )}
      </div>

      {/* Expandable SWOT */}
      {showSwot && swot && (
        <div className="triage-swot">
          <SWOTBox label="strengths" items={swot.strengths} />
          <SWOTBox label="weaknesses" items={swot.weaknesses} />
          <SWOTBox label="opportunities" items={swot.opportunities} />
          <SWOTBox label="threats" items={swot.threats} />
        </div>
      )}
    </div>
  );
}
