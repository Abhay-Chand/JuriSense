import { useState, useEffect } from "react";
import axios from "axios";

export default function ConversationsSidebar({ token, activeConvId, refreshTrigger, onSelect, onNew, onDelete, onClose }) {
  const [convs, setConvs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [limit] = useState(25);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setLoading(true);
    axios.get(`/api/conversations?limit=${limit}&offset=0`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(({ data }) => {
        setConvs(data.conversations || []);
        setTotal(data.total || 0);
      })
      .catch(() => { if (!axios.isCancel()) setConvs([]); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [token, refreshTrigger, limit]);

  function loadMore() {
    const offset = convs.length;
    if (offset >= total) return;
    setLoading(true);
    axios.get(`/api/conversations?limit=${limit}&offset=${offset}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(({ data }) => {
        setConvs(prev => [...prev, ...(data.conversations || [])]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  function displayTitle(c) {
    const t = c.title || "";
    if (!t || t === "New Chat") return "New Chat";
    return t.length > 28 ? t.slice(0, 28) + "..." : t;
  }

  function relativeTime(dateStr) {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return "now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return `${Math.floor(diff / 86400)}d`;
  }

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Chats <small style={{color:"var(--ink-faint)",fontSize:11}}>({total})</small></span>
        <div className="sidebar-header-actions">
          <button className="sidebar-new-btn" onClick={onNew} title="New Chat">+</button>
          <button className="sidebar-close-btn" onClick={onClose} title="Close Sidebar">✕</button>
        </div>
      </div>
      <div className="sidebar-list">
        {loading && convs.length === 0 && <div className="sidebar-empty">Loading...</div>}
        {!loading && convs.length === 0 && <div className="sidebar-empty">No conversations yet</div>}
        {convs.map(c => (
          <div
            key={c.id}
            className={`sidebar-item ${c.id === activeConvId ? "active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <span className="sidebar-item-title">{displayTitle(c)}</span>
            <span className="sidebar-item-time">{relativeTime(c.updated_at)}</span>
            <button className="sidebar-item-del" onClick={e => { e.stopPropagation(); onDelete(c.id); }} title="Delete">x</button>
          </div>
        ))}
        {convs.length < total && (
          <button className="sidebar-load-more" onClick={loadMore}>
            Load more ({total - convs.length} remaining)
          </button>
        )}
      </div>
    </div>
  );
}
