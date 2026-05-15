/**
 * ArchivedChats — dedicated page listing the user's archived
 * conversations with Restore + Permanently Delete affordances.
 *
 * Route: `/app/chats/archived`
 *
 * Phase C (2026-05-13). Resolves the QA finding that there was no
 * way to retrieve or hard-delete archived chats.
 */
import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { ArchiveRestore, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function ArchivedChats() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const { data } = await api.get("/chats/archived");
      setItems(data.items || []);
    } catch (e) {
      setErr(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const handleRestore = async (id) => {
    setBusyId(id);
    try {
      await api.post(`/chats/${id}/restore`);
      toast.success("Chat restored.");
      fetchList();
    } catch (e) {
      toast.error(`Restore failed: ${e?.message || "unknown error"}`);
    } finally {
      setBusyId(null);
    }
  };

  const handlePermanentDelete = async (id) => {
    const ok = window.confirm(
      "Are you sure you want to permanently delete this conversation? This cannot be undone."
    );
    if (!ok) return;
    setBusyId(id);
    try {
      await api.delete(`/chats/${id}/permanent`, {
        data: { confirm: true },
      });
      toast.success("Chat permanently deleted.");
      fetchList();
    } catch (e) {
      toast.error(`Delete failed: ${e?.message || "unknown error"}`);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div
      data-testid="archived-chats-page"
      className="mx-auto max-w-3xl px-4 py-8 sm:px-6"
    >
      <div className="mb-6 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-slate-900">
          Archived Chats
        </h1>
        <Button
          variant="outline"
          onClick={() => navigate("/app/chat")}
          data-testid="archived-chats-back-button"
        >
          Back to Chat
        </Button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading archived conversations…
        </div>
      )}

      {err && (
        <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {err}
        </div>
      )}

      {!loading && !err && items.length === 0 && (
        <div
          data-testid="archived-chats-empty"
          className="rounded border border-slate-200 bg-slate-50 p-6 text-center text-slate-500"
        >
          No archived conversations.
        </div>
      )}

      <ul className="space-y-2">
        {items.map((c) => (
          <li
            key={c.id}
            data-testid={`archived-chat-row-${c.id}`}
            className="flex flex-col gap-2 rounded border border-slate-200 bg-white p-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <div className="truncate font-medium text-slate-900">
                {c.title || "(untitled chat)"}
              </div>
              <div className="text-xs text-slate-500">
                Archived {c.archived_at ? new Date(c.archived_at).toLocaleString() : "—"}
                {c.message_count != null && ` · ${c.message_count} messages`}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={busyId === c.id}
                onClick={() => handleRestore(c.id)}
                data-testid={`archived-chat-restore-${c.id}`}
              >
                <ArchiveRestore className="mr-1 h-4 w-4" />
                Restore
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={busyId === c.id}
                onClick={() => handlePermanentDelete(c.id)}
                data-testid={`archived-chat-delete-${c.id}`}
              >
                <Trash2 className="mr-1 h-4 w-4" />
                Permanently Delete
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
