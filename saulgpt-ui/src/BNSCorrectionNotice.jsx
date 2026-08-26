/**
 * SAULGPT — BNSCorrectionNotice
 * ===============================
 * Visual notice for IPC/CrPC → BNS/BNSS law updates.
 *
 * Displays when:
 * → User cites IPC, CrPC, or Evidence Act for post-July 2024 incidents
 * → Backend remaps old laws to new legislation
 *
 * Backend metadata expected:
 *   meta.remapped_laws     — object { old_law: new_law }
 *   meta.scrutiny?.warnings — may contain "LAW UPDATE" warning
 *
 * Usage:
 *   <BNSCorrectionNotice meta={msg.meta} />
 */

import "./BNSCorrectionNotice.css";

// Law mapping display configuration
const LAW_DISPLAY = {
  "IPC": {
    new: "BNS 2023",
    full: "Bharatiya Nyaya Sanhita, 2023",
    icon: "📖",
    note: "Replaced IPC from July 1, 2024",
  },
  "Indian Penal Code": {
    new: "BNS 2023",
    full: "Bharatiya Nyaya Sanhita, 2023",
    icon: "📖",
    note: "Replaced IPC from July 1, 2024",
  },
  "CrPC": {
    new: "BNSS 2023",
    full: "Bharatiya Nagarik Suraksha Sanhita, 2023",
    icon: "⚖️",
    note: "Replaced CrPC from July 1, 2024",
  },
  "Code of Criminal Procedure": {
    new: "BNSS 2023",
    full: "Bharatiya Nagarik Suraksha Sanhita, 2023",
    icon: "⚖️",
    note: "Replaced CrPC from July 1, 2024",
  },
  "Indian Evidence Act": {
    new: "BSA 2023",
    full: "Bharatiya Sakshya Adhiniyam, 2023",
    icon: "📜",
    note: "Replaced Evidence Act from July 1, 2024",
  },
  "IEA": {
    new: "BSA 2023",
    full: "Bharatiya Sakshya Adhiniyam, 2023",
    icon: "📜",
    note: "Replaced Evidence Act from July 1, 2024",
  },
};

export default function BNSCorrectionNotice({ meta }) {
  const remappedLaws = meta?.remapped_laws;
  const scrutiny = meta?.scrutiny;

  // Guard: only show if there are remapped laws
  if (!remappedLaws || Object.keys(remappedLaws).length === 0) {
    return null;
  }

  const entries = Object.entries(remappedLaws);

  return (
    <div className="bns-notice">
      <div className="bns-header">
        <span className="bns-icon">📜</span>
        <span className="bns-title">LEGISLATION UPDATE 2024</span>
      </div>

      <p className="bns-subtitle">
        The following laws were replaced effective <strong>July 1, 2024</strong>.
        Your document will use the updated legislation.
      </p>

      <div className="bns-mappings">
        {entries.map(([oldLaw, newLaw], i) => {
          const cfg = LAW_DISPLAY[oldLaw] || {
            new: newLaw,
            full: newLaw,
            icon: "⚖️",
            note: "Updated legislation",
          };

          return (
            <div key={i} className="bns-card">
              <div className="bns-row">
                <div className="bns-old">
                  <span className="bns-old-icon">❌</span>
                  <span className="bns-old-name">{oldLaw}</span>
                </div>
                <span className="bns-arrow">→</span>
                <div className="bns-new">
                  <span className="bns-new-icon">{cfg.icon}</span>
                  <span className="bns-new-name">{cfg.new}</span>
                </div>
              </div>
              <p className="bns-note">{cfg.note}</p>
            </div>
          );
        })}
      </div>

      <p className="bns-disclaimer">
        The three criminal laws (IPC, CrPC, Evidence Act) were replaced by BNS, BNSS, and BSA
        respectively, effective July 1, 2024. Offences committed after this date are governed
        by the new legislation.
      </p>
    </div>
  );
}
