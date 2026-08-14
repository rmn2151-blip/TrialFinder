import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  getAlerts,
  markAlertRead,
  markAllAlertsRead,
} from "../api/client.js";

function timeAgo(iso) {
  if (!iso) return "";
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function AlertsBell() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const data = await getAlerts({ limit: 20 });
      setAlerts(data.alerts || []);
      setUnread(data.unread_count || 0);
    } catch {
      // Not fatal: the bell just stays empty.
    }
  }, []);

  // Poll quietly so a user with the tab open still sees new alerts.
  useEffect(() => {
    load();
    const id = setInterval(load, 120000);
    return () => clearInterval(id);
  }, [load]);

  // Close when clicking outside the dropdown.
  useEffect(() => {
    function onClick(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      await load();
      setLoading(false);
    }
  }

  async function handleRead(id) {
    try {
      const remaining = await markAlertRead(id);
      setUnread(remaining);
      setAlerts((list) =>
        list.map((a) =>
          a.id === id ? { ...a, read_at: new Date().toISOString() } : a
        )
      );
    } catch {
      /* ignore */
    }
  }

  async function handleReadAll() {
    try {
      await markAllAlertsRead();
      setUnread(0);
      const now = new Date().toISOString();
      setAlerts((list) => list.map((a) => ({ ...a, read_at: a.read_at || now })));
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="alerts" ref={wrapperRef}>
      <button
        type="button"
        className="alerts__bell"
        onClick={toggle}
        aria-expanded={open}
        aria-label={
          unread > 0 ? `Alerts, ${unread} unread` : "Alerts, none unread"
        }
      >
        <span aria-hidden="true">🔔</span>
        {unread > 0 && (
          <span className="alerts__badge">{unread > 9 ? "9+" : unread}</span>
        )}
      </button>

      {open && (
        <div className="alerts__panel" role="dialog" aria-label="Trial alerts">
          <div className="alerts__head">
            <strong>Trial updates</strong>
            {unread > 0 && (
              <button type="button" className="btn--link" onClick={handleReadAll}>
                Mark all read
              </button>
            )}
          </div>

          {loading && <p className="alerts__empty">Loading…</p>}

          {!loading && alerts.length === 0 && (
            <p className="alerts__empty">
              No updates yet. We check your saved trials daily and will tell you
              when a status, phase, or site changes.
            </p>
          )}

          <ul className="alerts__list">
            {alerts.map((a) => (
              <li
                key={a.id}
                className={
                  "alert-item" +
                  (a.read_at ? "" : " is-unread") +
                  (a.severity === "high" ? " is-high" : "")
                }
              >
                <div className="alert-item__top">
                  {a.severity === "high" && (
                    <span className="alert-item__flag">Important</span>
                  )}
                  {a.profile_label && (
                    <span className="alert-item__who">{a.profile_label}</span>
                  )}
                  <span className="alert-item__time">{timeAgo(a.created_at)}</span>
                </div>

                <p className="alert-item__desc">{a.description}</p>
                <p className="alert-item__trial">{a.trial_title}</p>

                <div className="alert-item__actions">
                  {a.source_url && (
                    <a
                      href={a.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn--link"
                    >
                      View trial
                    </a>
                  )}
                  {!a.read_at && (
                    <button
                      type="button"
                      className="btn--link"
                      onClick={() => handleRead(a.id)}
                    >
                      Mark read
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>

          <div className="alerts__foot">
            <Link to="/watchlist" onClick={() => setOpen(false)}>
              Manage saved trials and email settings
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
