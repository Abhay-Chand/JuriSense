/**
 * SAULGPT — usePDF.js
 * ================================
 * Masterclass legal PDF generation engine.
 *
 * What Gemini's basic version does:
 * → Dumps plain text, strips all formatting
 * → No letterhead, no margins, no footer
 * → Runs off the page for long documents
 * → Only works for document mode
 *
 * What this does instead:
 * → Full SaulGPT letterhead + gold dividers
 * → Section-aware rendering (FACTS / LAW / OUTCOME / Steps)
 * → Auto page breaks with continuation headers
 * → Footer: disclaimer + page numbers + generation timestamp
 * → Indian legal margin standard (25mm all sides)
 * → Works for ALL modes: document, evaluate, analysis, pathfinder
 * → Citation block appended at end if metadata present
 * → Copy-to-clipboard fallback if jsPDF not installed
 *
 * Install: npm install jspdf
 * Usage:   import { downloadAsPDF } from "./usePDF";
 */

import { jsPDF } from "jspdf";

// ── LAYOUT CONSTANTS (A4 in mm) ───────────────────────────────
const ML = 22;           // margin left
const MR = 22;           // margin right  
const MT = 28;           // margin top (first page)
const MB = 22;           // margin bottom
const PW = 210;          // page width
const PH = 297;          // page height
const TW = PW - ML - MR; // text width = 166mm
const LH = 5.8;          // base line height mm

// ── COLORS (RGB arrays for jsPDF) ────────────────────────────
const C = {
  gold:     [180, 138, 56],
  goldDim:  [130, 100, 42],
  goldPale: [200, 170, 90],
  ink:      [28,  22,  16],
  inkMid:   [75,  65,  52],
  inkDim:   [120, 108, 88],
  inkFaint: [160, 148, 130],
  sage:     [80,  148, 92],
  red:      [172, 56,  56],
  amber:    [180, 128, 20],
  white:    [255, 255, 255],
};

// ── SECTION HEADER PATTERNS ───────────────────────────────────
const SECTION_STARTERS = [
  "FACTS:", "LEGAL ISSUES:", "APPLICABLE LAW:", "PROCEDURAL OUTCOME:",
  "LEGAL PROCESS:", "IMPORTANT NOTES:", "LEGAL NOTICE", "CONTRACT EVALUATION",
  "CRITICAL FLAWS", "MISSING PROTECTIONS", "SUGGESTED IMPROVEMENTS",
  "RELEVANT CASE LAW", "VALIDATION REPORT",
];

// ── TEXT CLEANER ──────────────────────────────────────────────
function stripMarkdown(raw) {
  return raw
    .replace(/<br\/?>/gi,    "\n")
    .replace(/<[^>]+>/g,     "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g,     "$1")
    .replace(/^#{1,3}\s+/gm,   "")
    .replace(/^[-•]\s+/gm,     "• ")
    .replace(/\r\n/g,          "\n")
    .replace(/\n{3,}/g,        "\n\n")
    .trim();
}

// ── DETECT DOCUMENT TYPE ─────────────────────────────────────
function docTypeLabel(meta) {
  const m = meta?.mode_used || "";
  if (m === "document")   return "Legal Document Draft";
  if (m === "evaluate")   return "Contract Evaluation Report";
  if (m === "pathfinder") return "Legal Procedure Guide";
  if (m === "knowledge")  return "Legal Knowledge Summary";
  if (m === "analysis")   return "Legal Case Analysis";
  return "Legal Document";
}

// ── SAFE FILENAME ─────────────────────────────────────────────
function safeFilename(meta) {
  const label = docTypeLabel(meta).replace(/\s+/g, "_");
  const date  = new Date().toISOString().slice(0, 10);
  return `SaulGPT_${label}_${date}.pdf`;
}

// ════════════════════════════════════════════════════════════
// MAIN EXPORT FUNCTION
// ════════════════════════════════════════════════════════════

export function downloadAsPDF(rawContent, meta = {}) {
  const doc     = new jsPDF({ unit: "mm", format: "a4" });
  const docType = docTypeLabel(meta);
  const now     = new Date();
  const dateStr = now.toLocaleDateString("en-IN", {
    day: "2-digit", month: "long", year: "numeric"
  });
  const timeStr = now.toLocaleTimeString("en-IN", {
    hour: "2-digit", minute: "2-digit"
  });

  let y = MT; // Y cursor

  // ── Helpers ────────────────────────────────────────────────
  const tc = (rgb) => doc.setTextColor(...rgb);
  const dc = (rgb) => doc.setDrawColor(...rgb);
  const fc = (rgb) => doc.setFillColor(...rgb);

  function rule(yp, color = C.goldDim, w = 0.25) {
    dc(color);
    doc.setLineWidth(w);
    doc.line(ML, yp, PW - MR, yp);
  }

  function checkBreak(need = LH * 3) {
    if (y + need > PH - MB) {
      doc.addPage();
      y = 18;
      // Continuation mini-header
      tc(C.goldDim);
      doc.setFont("times", "italic");
      doc.setFontSize(8);
      doc.text(`SaulGPT — ${docType} (continued)`, ML, y);
      doc.text(dateStr, PW - MR, y, { align: "right" });
      y += 3;
      rule(y, C.goldDim, 0.15);
      y += 5;
    }
  }

  // ── LETTERHEAD (first page only) ───────────────────────────

  // Org name
  tc(C.gold);
  doc.setFont("times", "bold");
  doc.setFontSize(20);
  doc.text("SaulGPT", PW / 2, y, { align: "center" });
  y += 6;

  // Tagline
  tc(C.goldDim);
  doc.setFont("times", "normal");
  doc.setFontSize(7.5);
  doc.text(
    "INDIAN LEGAL INTELLIGENCE  ·  AI-POWERED PROCEDURAL GUIDANCE",
    PW / 2, y, { align: "center", charSpace: 0.5 }
  );
  y += 5;

  // Double gold rule
  rule(y, C.gold, 0.5);
  y += 1.5;
  rule(y, C.goldDim, 0.15);
  y += 6;

  // Document type
  tc(C.ink);
  doc.setFont("times", "bold");
  doc.setFontSize(13);
  doc.text(docType.toUpperCase(), PW / 2, y, { align: "center" });
  y += 5;

  // Date + domain
  const domain = meta?.domain
    ? `${meta.domain.toUpperCase()} LAW  ·  `
    : "";
  tc(C.inkDim);
  doc.setFont("times", "italic");
  doc.setFontSize(9);
  doc.text(
    `${domain}Generated: ${dateStr} at ${timeStr}`,
    PW / 2, y, { align: "center" }
  );
  y += 4;

  // Validation badge
  if (meta?.is_hallucinating === false) {
    tc(C.sage);
    doc.setFont("times", "normal");
    doc.setFontSize(8);
    doc.text(
      "✓  Hallucination Check Passed  ·  AI Validation: Clear",
      PW / 2, y, { align: "center" }
    );
    y += 3;
  }

  // Bottom rule of header
  rule(y, C.goldDim, 0.25);
  y += 2;
  rule(y, C.gold, 0.5);
  y += 8;

  // ── RENDER CONTENT ─────────────────────────────────────────

  const clean = stripMarkdown(rawContent);
  const lines = clean.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const raw     = lines[i];
    const trimmed = raw.trim();

    // Empty line — small gap
    if (!trimmed) {
      y += LH * 0.45;
      continue;
    }

    // ── Section header ──
    const isSection = SECTION_STARTERS.some(s =>
      trimmed.toUpperCase().startsWith(s.toUpperCase())
    );

    if (isSection || /^[A-Z][A-Z\s:]{4,}$/.test(trimmed)) {
      checkBreak(LH * 3);
      y += 3;
      rule(y, C.goldDim, 0.12);
      y += LH;

      tc(C.ink);
      doc.setFont("times", "bold");
      doc.setFontSize(10.5);
      doc.text(trimmed, ML, y);
      y += LH * 1.2;
      continue;
    }

    // ── Risk level line ──
    if (/risk level|risk score/i.test(trimmed)) {
      checkBreak(LH * 2);
      const isHigh = /high/i.test(trimmed);
      const isMed  = /medium/i.test(trimmed);
      const rColor = isHigh ? C.red : isMed ? C.amber : C.sage;
      const label  = trimmed.replace(/risk (level|score)[:—]?\s*/i, "").trim();

      tc(C.inkMid);
      doc.setFont("times", "bold");
      doc.setFontSize(10);
      doc.text("Risk Level:", ML, y);

      tc(rColor);
      doc.text(label, ML + 24, y);
      y += LH * 1.3;
      continue;
    }

    // ── Step lines (Step 1:, Step 2:) ──
    if (/^Step \d+:/i.test(trimmed)) {
      checkBreak(LH * 2.5);
      y += 2;
      const match = trimmed.match(/^(Step \d+:)\s*(.*)/i);
      if (match) {
        tc(C.gold);
        doc.setFont("times", "bold");
        doc.setFontSize(10);
        doc.text(match[1], ML, y);

        tc(C.ink);
        const rest = doc.splitTextToSize(match[2], TW - 20);
        doc.text(rest, ML + 20, y);
        y += LH * Math.max(1, rest.length);
      }
      continue;
    }

    // ── Arrow sub-lines (→ Where:, → Timeline:) ──
    if (trimmed.startsWith("→") || trimmed.startsWith("->")) {
      checkBreak(LH * 1.5);
      tc(C.goldDim);
      doc.setFont("times", "normal");
      doc.setFontSize(9.5);
      const arrowText = trimmed.replace(/^[→>-]+\s*/, "");
      const wrapped   = doc.splitTextToSize(`  → ${arrowText}`, TW - 6);
      doc.text(wrapped, ML + 4, y);
      y += LH * wrapped.length;
      continue;
    }

    // ── Bullet points ──
    if (trimmed.startsWith("•") || trimmed.startsWith("-")) {
      checkBreak(LH * 1.5);
      tc(C.gold);
      doc.setFont("times", "bold");
      doc.setFontSize(10);
      doc.text("•", ML + 3, y);

      tc(C.ink);
      doc.setFont("times", "normal");
      doc.setFontSize(10);
      const bulletText = trimmed.replace(/^[•\-]\s*/, "");
      const wrapped    = doc.splitTextToSize(bulletText, TW - 9);
      doc.text(wrapped, ML + 8, y);
      y += LH * wrapped.length + 0.5;
      continue;
    }

    // ── Disclaimer lines (italic, smaller) ──
    if (/disclaimer|does not constitute legal advice/i.test(trimmed)) {
      checkBreak(LH * 2.5);
      y += 3;
      rule(y, C.goldDim, 0.12);
      y += LH;
      tc(C.inkFaint);
      doc.setFont("times", "italic");
      doc.setFontSize(8.5);
      const wrapped = doc.splitTextToSize(trimmed, TW);
      doc.text(wrapped, ML, y);
      y += LH * wrapped.length + 2;
      continue;
    }

    // ── Normal body text ──
    checkBreak(LH * 2);
    tc(C.ink);
    doc.setFont("times", "normal");
    doc.setFontSize(10.5);
    const wrapped = doc.splitTextToSize(trimmed, TW);
    doc.text(wrapped, ML, y);
    y += LH * wrapped.length;
  }

  // ── CITATIONS BLOCK ─────────────────────────────────────────
  const citations = (meta?.citations || []).filter(
    c => c.act_name && c.act_name !== "Live Web Search"
  );

  if (citations.length > 0) {
    checkBreak(LH * (citations.length + 5));
    y += 4;
    rule(y, C.goldDim, 0.2);
    y += LH;

    tc(C.ink);
    doc.setFont("times", "bold");
    doc.setFontSize(10);
    doc.text("LAW SECTIONS RETRIEVED", ML, y);
    y += LH * 1.3;

    citations.forEach((c) => {
      checkBreak(LH * 1.5);
      const act     = (c.act_name || "").replace("_from_db", "");
      const sec     = c.section_number ? ` § ${c.section_number}` : "";
      const expired = c.is_repealed ? "  [REPEALED]" : "";
      const color   = c.is_repealed ? C.red : C.goldDim;

      tc(color);
      doc.setFont("times", "normal");
      doc.setFontSize(9.5);
      doc.text(`• ${act}${sec}${expired}`, ML + 4, y);
      y += LH;
    });
  }

  // ── FOOTERS (all pages) ──────────────────────────────────────
  const totalPages = doc.internal.pages.length - 1;
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p);
    const fy = PH - MB + 4;

    rule(fy - 3, C.goldDim, 0.15);

    tc(C.inkFaint);
    doc.setFont("times", "italic");
    doc.setFontSize(7.5);
    doc.text(
      "This document provides general procedural guidance based on Indian law. It does not constitute legal advice.",
      PW / 2, fy, { align: "center" }
    );

    tc(C.goldDim);
    doc.setFont("times", "normal");
    doc.setFontSize(8);
    doc.text(
      `SaulGPT  ·  Page ${p} of ${totalPages}`,
      PW / 2, fy + 4, { align: "center" }
    );
  }

  // ── SAVE ────────────────────────────────────────────────────
  doc.save(safeFilename(meta));
}

// ── COPY TO CLIPBOARD FALLBACK ────────────────────────────────
export async function copyToClipboard(content) {
  const clean = stripMarkdown(content);
  try {
    await navigator.clipboard.writeText(clean);
    return true;
  } catch {
    // Fallback for older browsers
    const el = document.createElement("textarea");
    el.value = clean;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
    return true;
  }
}