/**
 * SAULGPT — UrgencyBanner
 * =========================
 * Pulsing red alert banner for legal deadlines and urgency flags.
 *
 * Displays:
 * → Limitation period warnings (days remaining)
 * → Statute of limitation expiry dates
 * → Urgent matters (bail hearings, custody deadlines)
 * → Cheque bounce notice windows (30 days)
 *
 * Backend metadata expected:
 *   meta.urgency_flags      — array of urgency indicators
 *   meta.limitation_days    — days remaining before time-bar
 *   meta.limitation_expiry  — date when claim becomes time-barred
 *   meta.urgency_reason     — human-readable urgency explanation
 *
 * Usage:
 *   <UrgencyBanner meta={msg.meta} />
 */

import "./UrgencyBanner.css";

export default function UrgencyBanner({ meta }) {
  // Extract urgency data from meta
  const urgencyFlags = meta?.urgency_flags || [];
  const limitationDays = meta?.limitation_days;
  const limitationExpiry = meta?.limitation_expiry;
  const urgencyReason = meta?.urgency_reason;
  const scrutiny = meta?.scrutiny;

  // Determine if we should show the banner
  const hasUrgency = urgencyFlags?.length > 0
    || (limitationDays !== undefined && limitationDays < 90)
    || (scrutiny?.severity === "serious" && scrutiny?.limitation_info);

  if (!hasUrgency) return null;

  // Calculate urgency level
  const isCritical = (limitationDays !== undefined && limitationDays < 30)
    || urgencyFlags.includes("immediate_filing_required")
    || urgencyFlags.includes("bail_hearing_pending");

  const isWarning = (limitationDays !== undefined && limitationDays < 90 && limitationDays >= 30)
    || urgencyFlags.includes("notice_period_expiring")
    || urgencyFlags.includes("evidence_deadline");

  // Build the message
  const title = isCritical
    ? "⏰ URGENT DEADLINE"
    : "⚠️ LIMITATION ALERT";

  const message = urgencyReason || (
    limitationDays !== undefined
      ? `Only **${limitationDays} days** remaining before this claim becomes time-barred under the Limitation Act, 1963.`
      : "Action required within the statutory limitation period."
  );

  const expiryDate = limitationExpiry
    ? `Deadline: ${new Date(limitationExpiry).toLocaleDateString('en-IN', {
        day: 'numeric', month: 'long', year: 'numeric'
      })}`
    : "";

  return (
    <div className={`urgency-banner ${isCritical ? "critical" : "warning"}`}>
      <div className="urgency-icon">
        {isCritical ? "🚨" : "⏰"}
      </div>
      <div className="urgency-content">
        <span className="urgency-title">{title}</span>
        <span
          className="urgency-text"
          dangerouslySetInnerHTML={{
            __html: message.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
          }}
        />
        {expiryDate && <span className="urgency-date">{expiryDate}</span>}
      </div>
      <div className="urgency-pulse" />
    </div>
  );
}
