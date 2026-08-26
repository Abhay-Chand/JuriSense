import { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import "./App.css";
import { downloadAsPDF, copyToClipboard } from "./usePDF";
import UrgencyBanner from "./UrgencyBanner";
import VetoCard from "./VetoCard";
import JurisdictionBadge from "./JurisdictionBadge";
import BNSCorrectionNotice from "./BNSCorrectionNotice";
import TriageCards from "./TriageCards";
import { scanForTerms, getCategories, GLOSSARY } from "./LegalGlossary";
import AuthPage from "./AuthPage";
import ConversationsSidebar from "./ConversationsSidebar";

function getOrCreateSessionId() {
  const stored = localStorage.getItem("saulgpt_session_id");
  if (stored) return stored;
  const newId = `session_${Math.random().toString(36).slice(2, 9)}_${Date.now().toString(36)}`;
  localStorage.setItem("saulgpt_session_id", newId);
  return newId;
}

const SESSION_ID = getOrCreateSessionId();

const MODES = {
  analysis:   { label: "Case Analysis",     icon: "⚖️",  color: "#C9A84C" },
  knowledge:  { label: "Legal Knowledge",   icon: "📖",  color: "#7EB8C4" },
  document:   { label: "Document Draft",    icon: "📜",  color: "#A8C49A" },
  pathfinder: { label: "Path Finder",       icon: "🗺️",  color: "#C49AA8" },
  evaluate:   { label: "Contract Review",   icon: "🔴",  color: "#C44A4A" },
  interviewing: { label: "Drafting",        icon: "✍️",  color: "#E8C97A" },
};

const SUGGESTED_QUERIES = [
  "My employer hasn't paid salary for 3 months",
  "A cheque I received was returned by the bank",
  "I need to draft a legal notice for unpaid dues",
  "What is the procedure to file an FIR?",
  "What are my rights if police arrest me?",
];

function TypingIndicator({ label }) {
  return (
    <div className="typing-indicator">
      <div className="bot-avatar"><span>⚖</span></div>
      <div className="typing-bubble">
        {label && <span className="typing-label">{label}</span>}
        <div className="typing-dots">
          <span /><span /><span />
        </div>
      </div>
    </div>
  );
}

function InterviewProgress({ pct }) {
  return (
    <div className="interview-progress">
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="progress-label">
        {pct < 100 ? `${pct}% complete` : "✅ All info collected"}
      </span>
    </div>
  );
}

function RiskBadge({ risk }) {
  const cfg = {
    High:   { color: "#C44A4A", bg: "rgba(196,74,74,0.12)",  icon: "🔴" },
    Medium: { color: "#C9A84C", bg: "rgba(201,168,76,0.12)", icon: "🟡" },
    Low:    { color: "#A8C49A", bg: "rgba(168,196,154,0.12)", icon: "🟢" },
  }[risk] || { color: "#888", bg: "rgba(136,136,136,0.1)", icon: "⚪" };

  return (
    <span
      className="risk-badge"
      style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.color}33` }}
    >
      {cfg.icon} {risk} Risk
    </span>
  );
}

function PipelineMeta({ data }) {
  const [open, setOpen] = useState(false);
  const mode = MODES[data.mode_used] || {};

  return (
    <div className="pipeline-meta">
      <div className="meta-bar" onClick={() => setOpen(o => !o)}>
        {mode.label && (
          <span className="mode-tag" style={{ color: mode.color }}>
            {mode.icon} {mode.label}
          </span>
        )}
        <span className="meta-pills">
          {data.domain && <span className="pill domain">{data.domain}</span>}
          {data.laws_retrieved > 0 && (
            <span className="pill laws">{data.laws_retrieved} laws</span>
          )}
          {data.graph_insights?.length > 0 && (
            <span className="pill graph">🕸 {data.graph_insights.length}</span>
          )}
          {data.case_law_found && <span className="pill caselaw">📚 cases</span>}
          {data.elapsed_seconds > 0 && (
            <span className="pill time">{data.elapsed_seconds}s</span>
          )}
          {data.is_hallucinating && <span className="pill warn">⚠️ verify</span>}
        </span>
        <span className="expand-arrow">{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div className="meta-expanded">
          {data.citations?.length > 0 && (
            <div className="meta-section">
              <span className="meta-label">CITATIONS</span>
              <div className="citations-row">
                {data.citations.map((c, i) => (
                  <span
                    key={i}
                    className={`citation-badge ${c.is_repealed ? "repealed" : ""}`}
                  >
                    {c.act_name?.replace("_from_db", "")}
                    {c.section_number && ` § ${c.section_number}`}
                    {c.is_repealed && " ⚠️"}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.repealed_warnings?.length > 0 && (
            <div className="meta-section warn-section">
              <span className="meta-label">⚠️ REPEALED LAWS</span>
              {data.repealed_warnings.map((w, i) => (
                <p key={i} className="warn-text">{w}</p>
              ))}
            </div>
          )}

          {data.struck_down_warnings?.length > 0 && (
            <div className="meta-section warn-section">
              <span className="meta-label">🚨 STRUCK DOWN</span>
              {data.struck_down_warnings.map((w, i) => (
                <p key={i} className="warn-text">{w}</p>
              ))}
            </div>
          )}

          <div className="meta-section">
            <span className="meta-label">VALIDATION</span>
            <span className={`validation-status ${data.is_hallucinating ? "fail" : "pass"}`}>
              {data.is_hallucinating ? "⚠️ Possible unsupported claims" : "✅ Passed"}
            </span>
            {data.confidence_score > 0 && (
              <span className="confidence">
                Confidence: {(data.confidence_score * 100).toFixed(1)}%
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Message({ msg, onTriageChoice }) {
  const isUser  = msg.role === "user";
  const [copied, setCopied] = useState(false);

  const showExport = !isUser && msg.content && msg.content.length > 100;

  const EXPORTABLE_MODES = ["document", "evaluate", "pathfinder", "analysis", "knowledge"];
  const isError    = msg.content.startsWith("🚨");
  const isClarify  = msg.content.includes("Could you please clarify");
  const isLong     = msg.content.length > 300;

  const showPDF = showExport && !isError && !isClarify && (
    EXPORTABLE_MODES.includes(msg.meta?.mode_used) ||
    msg.meta?.interview_complete                   ||
    isLong
  );

  async function handleCopy() {
    await copyToClipboard(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handlePDF() {
    downloadAsPDF(msg.content, msg.meta || {});
  }

  return (
    <div className={`message ${isUser ? "user-message" : "bot-message"}`}>
      {!isUser && <div className="bot-avatar"><span>⚖</span></div>}
      <div className="message-body">
        {msg.interviewProgress !== undefined && (
          <InterviewProgress pct={msg.interviewProgress} />
        )}

        {msg.meta && (
          <>
            <VetoCard scrutiny={msg.meta.scrutiny} />
            <BNSCorrectionNotice meta={msg.meta} />
            <UrgencyBanner meta={msg.meta} />
            <JurisdictionBadge meta={msg.meta} />
          </>
        )}

        {msg.triage && (
          <TriageCards triage={msg.triage} onChoose={onTriageChoice} />
        )}

        <div
          className="message-text"
          dangerouslySetInnerHTML={{
            __html: msg.content
              .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
              .replace(/### (.*?)(\n|$)/g, "<h3>$1</h3>")
              .replace(/## (.*?)(\n|$)/g,  "<h2>$1</h2>")
              .replace(/^- (.*)/gm, "<li>$1</li>")
              .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
              .replace(/\n/g, "<br/>"),
          }}
        />
        {msg.meta && <PipelineMeta data={msg.meta} />}

        {showExport && (
          <div className="export-bar">
            <button
              className="export-btn copy-btn"
              onClick={handleCopy}
              title="Copy plain text to clipboard"
            >
              {copied ? "✓ Copied" : "⎘ Copy"}
            </button>
            {showPDF && (
              <button
                className="export-btn pdf-btn"
                onClick={handlePDF}
                title="Download as formatted PDF"
              >
                <span className="pdf-icon">⬇</span>
                Download PDF
              </button>
            )}
            {msg.meta?.document_ready && msg.meta?.document_url && (
              <a
                href={msg.meta.document_url}
                className="export-btn docx-btn"
                download
                title="Download as .docx (editable)"
              >
                <span className="docx-icon">📄</span>
                Download .docx
              </a>
            )}
          </div>
        )}
      </div>
      {isUser && <div className="user-avatar">U</div>}
    </div>
  );
}

function DropZone({ onFile, disabled }) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  }, [onFile]);

  return (
    <div
      className={`drop-zone ${dragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <span className="drop-icon">📎</span>
      <span className="drop-text">
            Drop a contract here to evaluate
            <br />
            <small>PDF · DOCX · TXT · Max 50MB</small>
      </span>
    </div>
  );
}

export default function App() {
  const [token, setToken]       = useState(() => localStorage.getItem("saulgpt_token"));
  const [user, setUser]         = useState(() => {
    const saved = localStorage.getItem("saulgpt_user");
    if (saved) { try { return JSON.parse(saved); } catch {} }
    return null;
  });
  const [messages, setMessages] = useState(() => {
    // Restore guest messages from localStorage (for session takeover)
    const saved = localStorage.getItem("saulgpt_guest_messages");
    if (saved) { try { return JSON.parse(saved); } catch {} }
    return [];
  });
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("");
  const [forceMode, setForceMode] = useState(null);
  const [interviewActive, setInterviewActive] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(() => {
    const saved = localStorage.getItem("saulgpt_guest_messages");
    return saved ? false : true;
  });
  const [showDropZone, setShowDropZone] = useState(false);
  const [showGlossary, setShowGlossary] = useState(false);
  const [glossaryCategory, setGlossaryCategory] = useState("All");
  const [convId, setConvId]     = useState(() => {
    const saved = localStorage.getItem("saulgpt_conv_id");
    if (!saved) return null;
    const n = Number(saved);
    return !isNaN(n) && n > 0 ? n : null;
  });
  const [showSidebar, setShowSidebar] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);
  const fileRef    = useRef(null);
  const convRef    = useRef(convId);  // ref to prevent stale overwrites

  // Keep convRef in sync with convId
  useEffect(() => { convRef.current = convId; }, [convId]);

  // Persist conv_id and guest messages across refresh
  useEffect(() => {
    if (convId) localStorage.setItem("saulgpt_conv_id", String(convId));
    else localStorage.removeItem("saulgpt_conv_id");
  }, [convId]);

  // Load persisted conversation messages on mount (page refresh recovery)
  useEffect(() => {
    const saved = localStorage.getItem("saulgpt_conv_id");
    const savedToken = localStorage.getItem("saulgpt_token");
    if (saved && savedToken) {
      const n = Number(saved);
      if (!isNaN(n) && n > 0) {
        api().get(`/api/conversations/${n}`).then(({ data }) => {
          if (!convRef.current || convRef.current !== n) return; // stale — user clicked New Chat
          setConvId(n);
          setMessages([]);
          const msgs = (data.messages || []).map(m => ({
            role: m.role,
            content: m.content,
            meta: m.meta ? (typeof m.meta === "string" ? JSON.parse(m.meta) : m.meta) : undefined,
          }));
          setMessages(msgs);
        }).catch(() => {});
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Only persist guest messages (unauthenticated sessions)
    if (!token && messages.length > 0) {
      localStorage.setItem("saulgpt_guest_messages", JSON.stringify(messages.slice(-6)));
    }
    if (token) {
      localStorage.removeItem("saulgpt_guest_messages");
    }
  }, [messages, token]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  }, [input]);

  // Sync auth state across tabs (logout from one tab → logout from all)
  useEffect(() => {
    function handleStorage(e) {
      if (e.key === "saulgpt_token" && !e.newValue) {
        setToken(null);
        setUser(null);
        setMessages([]);
        setConvId(null);
      }
    }
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  function api() {
    const headers = {};
    const currentToken = localStorage.getItem("saulgpt_token");
    if (currentToken) headers.Authorization = `Bearer ${currentToken}`;
    const instance = axios.create({ headers });
    // 401 interceptor: token expired → logout
    instance.interceptors.response.use(
      res => res,
      err => {
        if (err.response?.status === 401 && localStorage.getItem("saulgpt_token")) {
          logout();
        }
        return Promise.reject(err);
      }
    );
    return instance;
  }

  function handleAuth(newToken, newUser) {
    setAuthLoading(true);
    setToken(newToken);
    setUser(newUser);
    // Guest session takeover: bulk-import guest messages to DB in one call
    if (messages.length > 0 && !convId) {
      const turns = messages.map(m => ({
        role: m.role,
        content: m.content,
        meta: m.meta ? JSON.stringify(m.meta) : null,
      }));
      api().post("/api/conversations/migrate", { turns }).then(({ data }) => {
        setConvId(data.conv_id);
        localStorage.removeItem("saulgpt_guest_messages");
      }).catch(() => {}).finally(() => setAuthLoading(false));
    } else {
      setAuthLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("saulgpt_token");
    localStorage.removeItem("saulgpt_user");
    localStorage.removeItem("saulgpt_conv_id");
    setToken(null);
    setUser(null);
    setMessages([]);
    setConvId(null);
  }

  async function loadConversation(id) {
    try {
      setMessages([]);
      setShowSuggestions(false);
      setLoading(true);
      setConvId(id);

      const { data } = await api().get(`/api/conversations/${id}`);

      setMessages((data.messages || []).map(m => ({
        role: m.role,
        content: m.content,
        meta: m.meta ? (typeof m.meta === "string" ? JSON.parse(m.meta) : m.meta) : undefined,
      })));
    } catch (e) {
      console.error("Failed to load conversation:", e);
      setMessages([{ role: "assistant", content: "Failed to load conversation." }]);
    } finally {
      setLoading(false);
    }
  }

  async function newConversation() {
    try {
      setMessages([]);
      setConvId(null);
      setShowSuggestions(true);
      setLoading(true);

      const { data } = await api().post("/api/conversations");

      if (data.conv_id) {
        setConvId(data.conv_id);
        setRefreshTrigger(prev => prev + 1);
      }
    } catch (e) {
      console.error("Failed to create conversation:", e);
      setShowSuggestions(false);
    } finally {
      setLoading(false);
    }
  }

  function deleteConversation(id) {
    api().delete(`/api/conversations/${id}`).then(() => {
      if (convId === id) { setConvId(null); setMessages([]); }
      setRefreshTrigger(prev => prev + 1);
    }).catch(() => {});
  }

  async function sendMessage(query) {
    const text = (query || input).trim();
    if (!text || loading) return;

    setInput("");
    setShowSuggestions(false);
    setMessages(prev => [...prev, { role: "user", content: text }]);
    setLoading(true);
    setLoadingLabel(interviewActive ? "Recording your answer…" : "Consulting the law…");

    try {
      const payload = {
        query: text,
        session_id: SESSION_ID,
      };
      if (forceMode) payload.mode = forceMode;
      if (convId) payload.conv_id = convId;

      const { data } = await api().post("/api/chat", payload);

      // Track conv_id if returned from backend (newly created conversation)
      if (data.conv_id) setConvId(data.conv_id);

      const isInterview = data.status === "interviewing";
      const isTriage = data.status === "triage";
      setInterviewActive(isInterview && !data.interview_complete);

      if (isTriage) setInterviewActive(false);

      setMessages(prev => [
        ...prev,
        {
          role:              "assistant",
          content:           data.response || "No response generated.",
          meta:              isInterview && !data.interview_complete
                               ? null
                               : (isTriage ? null : data),
          triage:            isTriage ? data.triage : undefined,
          interviewProgress: isInterview ? data.progress_pct : undefined,
        },
      ]);
    } catch (err) {
      if (err.response?.status === 401) return; // interceptor handles logout
      let detail = "";
      if (err.response?.data?.detail) {
        const d = err.response.data.detail;
        detail = Array.isArray(d) ? d.map(x => x.msg).join("; ") : (typeof d === "string" ? d : "");
      }
      const msg = err.response
        ? `Server error ${err.response.status}${detail ? `: ${detail}` : ""}`
        : "Cannot connect to SaulGPT API. Is api_server.py running?";
      setMessages(prev => [...prev, { role: "assistant", content: `🚨 ${msg}` }]);
      setInterviewActive(false);
    } finally {
      setLoading(false);
      setLoadingLabel("");
      inputRef.current?.focus();
    }
  }

  async function handleFile(file) {
    if (!file || loading) return;

    setShowSuggestions(false);
    setShowDropZone(false);
    setMessages(prev => [
      ...prev,
      {
        role:    "user",
        content: `📎 **${file.name}** (${(file.size / 1024).toFixed(0)}KB)\nEvaluating for legal flaws…`,
      },
    ]);
    setLoading(true);
    setLoadingLabel("Parsing document…");

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoadingLabel("Running Red Pen evaluation…");
      const { data } = await api().post("/api/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setMessages(prev => [
        ...prev,
        {
          role:    "assistant",
          content: data.response || data.error || "Evaluation complete.",
          meta:    data.meta,
        },
      ]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: "assistant", content: "🚨 File evaluation failed. Check backend." },
      ]);
    } finally {
      setLoading(false);
      setLoadingLabel("");
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function clearChat() {
    try {
      await api().delete(`/api/history/${SESSION_ID}`);
      await api().delete(`/api/draft/state/${SESSION_ID}`);
    } catch {}
    setMessages([]);
    setInterviewActive(false);
    setShowSuggestions(true);
    setForceMode(null);
  }

  function cancelInterview() {
    api().delete(`/api/draft/state/${SESSION_ID}`).catch(() => {});
    setInterviewActive(false);
    setMessages(prev => [
      ...prev,
      { role: "assistant", content: "Draft cancelled. How else can I assist?" },
    ]);
  }

  function handleTriageChoice(choice) {
    sendMessage(choice);
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const lastBotMsg = messages.filter(m => m.role === "assistant" && !m.content.startsWith("🚨")).slice(-1)[0];
  const foundTerms = lastBotMsg ? scanForTerms(lastBotMsg.content) : [];
  const categories = ["All", ...getCategories()];

  function getTermsForCategory(cat) {
    if (cat === "All") return foundTerms;
    return foundTerms.filter(t => t.category === cat);
  }

  // If not authenticated, show auth page
  if (!token) {
    return <AuthPage onAuth={handleAuth} migrating={authLoading} />;
  }

  return (
    <div className="app">
      <div className="bg-grid" />
      <div className="bg-glow" />

      {/* ── SIDEBAR ── */}
      {showSidebar && (
        <>
          {/* Backdrop overlay for mobile — clicking closes sidebar */}
          <div className="sidebar-backdrop" onClick={() => setShowSidebar(false)} />
          <ConversationsSidebar
            token={token}
            activeConvId={convId}
            refreshTrigger={refreshTrigger}
            onSelect={async (id) => { await loadConversation(id); setShowSidebar(false); }}
            onNew={() => { newConversation(); setShowSidebar(false); }}
            onDelete={deleteConversation}
            onClose={() => setShowSidebar(false)}
          />
        </>
      )}

      <div className={`app-main ${showSidebar ? "sidebar-open" : ""}`}>
        <header className="header">
          <div className="header-inner">
            <button className="sidebar-toggle" onClick={() => setShowSidebar(s => !s)} title="Chat History">
              ☰
            </button>

            <div className="logo">
              <div className="logo-seal">
                <span className="seal-text">⚖</span>
                <div className="seal-ring" />
              </div>
              <div className="logo-text">
                <h1>SaulGPT</h1>
                <p>Indian Legal Intelligence</p>
              </div>
            </div>

            {!interviewActive && (
              <nav className="mode-selector">
                <span className="mode-label">MODE</span>
                {[null, "knowledge", "analysis", "document", "pathfinder"].map(m => (
                  <button
                    key={m || "auto"}
                    className={`mode-btn ${forceMode === m ? "active" : ""}`}
                    onClick={() => setForceMode(m)}
                  >
                    {m ? `${MODES[m].icon} ${MODES[m].label}` : "⚡ Auto"}
                  </button>
                ))}
              </nav>
            )}

            {interviewActive && (
              <div className="interview-badge">
                <span>✍️ Drafting Mode Active</span>
                <button className="cancel-btn" onClick={cancelInterview}>
                  ✕ Cancel
                </button>
              </div>
            )}

            <button
              className={`glossary-toggle ${showGlossary ? "active" : ""}`}
              onClick={() => setShowGlossary(!showGlossary)}
              title="Legal Terms Glossary"
            >
              📖 Glossary
            </button>

            <button className="clear-btn" onClick={clearChat}>⟳ New Matter</button>

            {/* User menu */}
            <div className="user-menu">
              <span className="user-email">{user?.username || user?.email || "User"}</span>
              <button className="logout-btn" onClick={logout} title="Sign Out">🚪</button>
            </div>
          </div>

          <div className="header-rule">
            <span className="rule-gem">◆</span>
          </div>
        </header>

        <main className="chat-area">
          {messages.length === 0 && (
            <div className="welcome">
              <div className="welcome-seal">
                <div className="outer-ring" />
                <div className="inner-ring" />
                <span className="seal-glyph">⚖</span>
              </div>
              <h2 className="welcome-title">
                Your Counsel<br />
                <span className="gold-text">Awaits</span>
              </h2>
              <p className="welcome-sub">
                RAG · Knowledge Graph · Contract Evaluation · Interactive Drafting
              </p>

              <div className="feature-cards">
                <div className="feature-card">
                  <span className="feature-icon">💬</span>
                  <strong>Ask Legal Questions</strong>
                  <p>In Hindi or English</p>
                </div>
                <div className="feature-card" onClick={() => setShowDropZone(true)}>
                  <span className="feature-icon">🔴</span>
                  <strong>Evaluate Contracts</strong>
                  <p>Upload PDF or DOCX</p>
                </div>
                <div className="feature-card" onClick={() => sendMessage("I need to draft a legal notice")}>
                  <span className="feature-icon">✍️</span>
                  <strong>Draft Documents</strong>
                  <p>AI-guided interview</p>
                </div>
              </div>

              {showSuggestions && (
                <div className="suggestions">
                  <p className="suggestions-label">— OR START WITH A COMMON MATTER —</p>
                  <div className="suggestions-grid">
                    {SUGGESTED_QUERIES.map((q, i) => (
                      <button
                        key={i}
                        className="suggestion-card"
                        onClick={() => sendMessage(q)}
                      >
                        <span className="suggestion-number">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="suggestion-text">{q}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {showDropZone && (
                <DropZone onFile={handleFile} disabled={loading} />
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <Message key={i} msg={msg} onTriageChoice={handleTriageChoice} />
          ))}

          {loading && <TypingIndicator label={loadingLabel} />}

          <div ref={bottomRef} />
        </main>

        {showGlossary && (
          <aside className="glossary-sidebar">
            <div className="glossary-header">
              <h3>📖 Legal Terms</h3>
              <button onClick={() => setShowGlossary(false)}>✕</button>
            </div>

            <div className="glossary-found">
              <p className="glossary-found-header">Terms Found in Response:</p>
              {foundTerms.length === 0 ? (
                <p className="glossary-empty">No legal terms detected yet. Ask a legal question to see relevant terms.</p>
              ) : (
                <>
                  <select
                    className="glossary-category-select"
                    value={glossaryCategory}
                    onChange={e => setGlossaryCategory(e.target.value)}
                  >
                    {categories.map(c => (
                      <option key={c} value={c}>{c} ({c === "All" ? foundTerms.length : getTermsForCategory(c).length})</option>
                    ))}
                  </select>
                  <div className="glossary-terms-list">
                    {getTermsForCategory(glossaryCategory).map((term, i) => (
                      <div key={i} className="glossary-term-card">
                        <strong>{term.term}</strong>
                        <span className="glossary-term-category">{term.category}</span>
                        <p>{term.def}</p>
                        <small>Source: {term.src}</small>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="glossary-all">
              <p className="glossary-all-header">Browse All Terms:</p>
              <select
                className="glossary-category-select"
                value={glossaryCategory}
                onChange={e => setGlossaryCategory(e.target.value)}
              >
                {categories.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <div className="glossary-terms-list">
                {(glossaryCategory === "All" ? Object.values(GLOSSARY).slice(0, 20) : Object.values(GLOSSARY).filter(t => t.category === glossaryCategory).slice(0, 20)).map((term, i) => {
                  const termKey = Object.keys(GLOSSARY).find(k => GLOSSARY[k] === term);
                  return (
                    <div key={i} className="glossary-term-card">
                      <strong>{termKey}</strong>
                      <span className="glossary-term-category">{term.category}</span>
                      <p>{term.def}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </aside>
        )}

        <footer className="input-area">
          <div className="input-rule">
            <span className="rule-gem">◆</span>
          </div>

          {interviewActive && (
            <div className="interview-hint">
              ✍️ Answer the question above, then press Enter
            </div>
          )}

          <div className="input-inner">
            <div className="input-wrapper">
              <input
                type="file"
                ref={fileRef}
                accept=".pdf,.docx,.txt"
                style={{ display: "none" }}
                onChange={e => handleFile(e.target.files[0])}
              />

              {!interviewActive && (
                <button
                  className="upload-btn"
                  onClick={() => fileRef.current?.click()}
                  disabled={loading}
                  title="Evaluate a Contract (PDF · DOCX · TXT)"
                >
                  📎
                </button>
              )}

              <textarea
                ref={inputRef}
                className="input-box"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder={
                  interviewActive
                    ? "Type your answer…"
                    : "State your matter… (Hindi or English)"
                }
                rows={1}
                disabled={loading}
              />

              <button
                className={`send-btn ${loading ? "loading" : ""}`}
                onClick={() => sendMessage()}
                disabled={loading || !input.trim()}
              >
                {loading
                  ? <span className="spinner" />
                  : <span className="send-icon">▶</span>
                }
              </button>
            </div>

            <p className="disclaimer">
              Procedural guidance only · Not legal advice · Consult a qualified advocate
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
