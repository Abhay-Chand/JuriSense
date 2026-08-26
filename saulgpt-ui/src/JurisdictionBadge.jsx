/**
 * SAULGPT — JurisdictionBadge
 * =============================
 * Court classifier UI showing which court has authority.
 *
 * Displays:
 * → Court level (Supreme Court, High Court, District Court, Tribunal)
 * → Jurisdiction type (Civil, Criminal, Consumer, Family)
 * → Territorial jurisdiction (State, Union Territory)
 * → Pecuniary jurisdiction (value threshold)
 *
 * Backend metadata expected:
 *   meta.jurisdiction_mapped    — object with court info
 *   meta.jurisdiction_mapped.court_level
 *   meta.jurisdiction_mapped.jurisdiction_type
 *   meta.jurisdiction_mapped.territorial
 *   meta.jurisdiction_mapped.pecuniary
 *
 * Usage:
 *   <JurisdictionBadge meta={msg.meta} />
 */

import "./JurisdictionBadge.css";

// Court level configuration
const COURT_CONFIG = {
  "Supreme Court": {
    icon: "🏛️",
    color: "#C9A84C",
    bg: "rgba(201, 168, 76, 0.15)",
    desc: "Highest constitutional court",
  },
  "High Court": {
    icon: "⚖️",
    color: "#7EB8C4",
    bg: "rgba(126, 184, 196, 0.15)",
    desc: "State-level constitutional court",
  },
  "District Court": {
    icon: "🏢",
    color: "#A8C49A",
    bg: "rgba(168, 196, 154, 0.15)",
    desc: "Principal civil court",
  },
  "Sessions Court": {
    icon: "🔨",
    color: "#C49AA8",
    bg: "rgba(196, 154, 168, 0.15)",
    desc: "Principal criminal court",
  },
  "Magistrate": {
    icon: "📋",
    color: "#C44A4A",
    bg: "rgba(196, 74, 74, 0.15)",
    desc: "Lower criminal court",
  },
  "Consumer Forum": {
    icon: "🛒",
    color: "#E8C97A",
    bg: "rgba(232, 201, 122, 0.15)",
    desc: "Consumer disputes redressal",
  },
  "Tribunal": {
    icon: "⚖️",
    color: "#9AA8C4",
    bg: "rgba(154, 168, 196, 0.15)",
    desc: "Specialized quasi-judicial body",
  },
  "Family Court": {
    icon: "👨‍👩‍👧",
    color: "#C49AA8",
    bg: "rgba(196, 154, 168, 0.15)",
    desc: "Matrimonial and family matters",
  },
};

// Jurisdiction type icons
const JURISDICTION_ICONS = {
  "Civil": "📜",
  "Criminal": "⚖️",
  "Consumer": "🛒",
  "Family": "👨‍👩‍👧",
  "Revenue": "📊",
  "Service": "💼",
  "Company": "🏢",
  "Tax": "💰",
};

export default function JurisdictionBadge({ meta }) {
  const jurisdiction = meta?.jurisdiction_mapped;

  if (!jurisdiction || (!jurisdiction.court_level && !jurisdiction.jurisdiction_type)) {
    return null;
  }

  const courtLevel = jurisdiction.court_level;
  const jurisdictionType = jurisdiction.jurisdiction_type;
  const territorial = jurisdiction.territorial;
  const pecuniary = jurisdiction.pecuniary;

  const courtCfg = COURT_CONFIG[courtLevel] || {
    icon: "🏛️",
    color: "#888",
    bg: "rgba(136, 136, 136, 0.12)",
    desc: "Court of law",
  };

  const jurisIcon = JURISDICTION_ICONS[jurisdictionType] || "⚖️";

  return (
    <div className="jurisdiction-badge">
      {/* Court Level Badge */}
      <div
        className="court-badge"
        style={{ background: courtCfg.bg, borderColor: courtCfg.color }}
      >
        <span className="court-icon">{courtCfg.icon}</span>
        <span className="court-name" style={{ color: courtCfg.color }}>
          {courtLevel}
        </span>
      </div>

      {/* Jurisdiction Type */}
      {jurisdictionType && (
        <div className="juris-row">
          <span className="juris-icon">{jurisIcon}</span>
          <span className="juris-text">{jurisdictionType} Jurisdiction</span>
        </div>
      )}

      {/* Territorial Jurisdiction */}
      {territorial && (
        <div className="juris-row">
          <span className="juris-icon">📍</span>
          <span className="juris-text">{territorial}</span>
        </div>
      )}

      {/* Pecuniary Jurisdiction */}
      {pecuniary && (
        <div className="juris-row">
          <span className="juris-icon">💰</span>
          <span className="juris-text">Up to {pecuniary}</span>
        </div>
      )}

      {/* Court Description */}
      <p className="court-desc">{courtCfg.desc}</p>
    </div>
  );
}
