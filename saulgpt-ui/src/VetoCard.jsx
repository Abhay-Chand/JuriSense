import { useState, useEffect } from "react";
import "./VetoCard.css";

export default function VetoCard({ scrutiny, onAcknowledge, onAction, logEvent }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // 3. Telemetry Mount
  useEffect(() => {
    if (logEvent && scrutiny && (scrutiny.veto_message || scrutiny.warnings?.length)) {
       logEvent("veto_card_shown", { severity: scrutiny.severity, warnings: scrutiny.warnings?.length });
    }
  }, [scrutiny, logEvent]);

  if (!scrutiny || (!scrutiny.veto_message && !scrutiny.warnings?.length)) return null;

  const severity = scrutiny.severity || "warning";
  const canProceed = scrutiny.can_proceed !== false;
  
  // 4. Defensive Prop Typing
  const warnings = Array.isArray(scrutiny.warnings) ? scrutiny.warnings : [];
  const remappedLaws = scrutiny.remapped_laws && typeof scrutiny.remapped_laws === 'object' ? scrutiny.remapped_laws : {};

  const cfg = {
    serious: { icon: "🚨", title: "SERIOUS LEGAL CONCERNS", cls: "veto-serious", accentColor: "var(--accent-red)" },
    warning: { icon: "⚠️", title: "LEGAL WARNINGS", cls: "veto-warning", accentColor: "var(--gold)" },
    info: { icon: "ℹ️", title: "LEGAL NOTES", cls: "veto-info", accentColor: "var(--accent-teal)" },
  }[severity] || { icon: "ℹ️", title: "LEGAL NOTES", cls: "veto-info", accentColor: "var(--accent-teal)" };

  const limitationWarning = warnings.find(w => w && w.toUpperCase().includes("LIMITATION"));
  const remedyWarning = warnings.find(w => w && w.toUpperCase().includes("REMEDY"));
  const lawWarning = warnings.find(w => w && (w.toUpperCase().includes("LAW UPDATE") || w.toUpperCase().includes("BNS")));
  const otherWarnings = warnings.filter(w => w !== limitationWarning && w !== remedyWarning && w !== lawWarning);

  // 🛡️ SECURITY FIX: Safe string parser
  function renderSafeWarning(text) {
    if (!text) return null;
    const parts = text.split(/\*\*(.*?)\*\*/g);
    
    return (
      <p className="veto-text">
        {parts.map((part, index) => {
          if (index % 2 === 1) return <strong key={index}>{part}</strong>;
          return (
            <span key={index}>
              {part.split('\n').map((line, i, arr) => (
                <span key={i}>{line}{i < arr.length - 1 && <br />}</span>
              ))}
            </span>
          );
        })}
      </p>
    );
  }

  const handleCheckbox = (e) => {
    const isChecked = e.target.checked;
    setAcknowledged(isChecked);
    if (onAcknowledge) onAcknowledge(isChecked);
  };

  return (
    <div className={`veto-card ${cfg.cls}`}>
      {/* 1. Accessibility Fix */}
      <button 
        className="veto-header" 
        onClick={() => setCollapsed(c => !c)}
        aria-expanded={!collapsed}
        tabIndex={0}
      >
        <span className={`veto-icon ${severity === "serious" ? "veto-pulse" : ""}`}>{cfg.icon}</span>
        <span className="veto-title" style={{ color: cfg.accentColor }}>LEGAL SCRUTINY — {cfg.title}</span>
        <span className="veto-collapse">{collapsed ? "▼" : "▲"}</span>
      </button>

      {!collapsed && (
        <div className="veto-body">
          {limitationWarning && (
            <div className="veto-section">
              <span className="veto-subtitle">📅 Limitation Act 1963</span>
              {renderSafeWarning(limitationWarning)}
            </div>
          )}
          {remedyWarning && (
            <div className="veto-section">
              <span className="veto-subtitle">⚖️ Remedy Not Recognized</span>
              {renderSafeWarning(remedyWarning)}
            </div>
          )}
          {lawWarning && (
            <div className="veto-section">
              <span className="veto-subtitle">📜 Law Updated — BNS/BNSS 2023</span>
              {renderSafeWarning(lawWarning)}
            </div>
          )}
          {otherWarnings.map((w, i) => (
            <div key={i} className="veto-section">{renderSafeWarning(w)}</div>
          ))}
          {!warnings.length && scrutiny.veto_message && (
            <div className="veto-section">{renderSafeWarning(scrutiny.veto_message)}</div>
          )}

          {Object.keys(remappedLaws).length > 0 && (
            <div className="veto-remapped">
              <span className="veto-remap-title">⚖️ AUTO-CORRECTIONS APPLIED:</span>
              <div className="veto-remap-list">
                {Object.entries(remappedLaws).map(([old, nw], i) => (
                  <span key={i} className="veto-remap-pill"><s>{old}</s> → <strong>{nw}</strong></span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 2. Actionable Callbacks UX Dead End Fix */}
      {!collapsed && canProceed && (
        <div className="veto-footer">
          <label className="veto-checkbox">
            <input type="checkbox" checked={acknowledged} onChange={handleCheckbox} />
            <span>I understand these concerns and wish to proceed anyway</span>
          </label>
          {acknowledged && <span className="veto-ack">✓ Acknowledged — document drafted at your own risk</span>}
        </div>
      )}

      {!collapsed && !canProceed && severity === "serious" && (
        <div className="veto-footer veto-blocked">
          <span className="veto-blocked-msg">⛔ This matter requires resolution before a legal notice can be drafted.</span>
          <div className="veto-action-buttons">
            <button className="veto-btn primary" onClick={() => onAction && onAction('consult_human')}>Consult a Human Lawyer</button>
            <button className="veto-btn secondary" onClick={() => onAction && onAction('draft_general')}>Draft General Demand Letter</button>
          </div>
        </div>
      )}

      {!collapsed && !canProceed && severity !== "serious" && (
        <div className="veto-footer veto-blocked">
          <span className="veto-blocked-msg">⛔ This matter requires attention before proceeding.</span>
        </div>
      )}
    </div>
  );
}
