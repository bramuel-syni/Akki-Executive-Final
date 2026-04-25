import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Loader2, Sparkles, FileText, Send, ExternalLink, Copy, Trash2, BookOpen } from "lucide-react";

/**
 * BlogAdmin — superadmin-only surface for composing and publishing
 * Exco360 articles. Once published, an article is reachable at /blog/:slug.
 * The admin can also copy the LinkedIn / X post copy AKKI generated.
 */
export default function BlogAdmin() {
  const { account } = useAuth();
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("NEDs and operating executives");
  const [composing, setComposing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [posts, setPosts] = useState([]);
  const [subscribers, setSubscribers] = useState([]);
  const [bodyCache, setBodyCache] = useState({}); // slug -> full post doc

  const loadPosts = useCallback(async () => {
    try {
      const { data } = await api.get("/blog/posts?include_drafts=true&limit=50");
      setPosts(data.posts || []);
    } catch { /* silent */ }
  }, []);
  const loadSubs = useCallback(async () => {
    try {
      const { data } = await api.get("/blog/subscribers");
      setSubscribers(data.subscribers || []);
    } catch { /* silent */ }
  }, []);
  useEffect(() => { loadPosts(); loadSubs(); }, [loadPosts, loadSubs]);

  if (!account?.is_superadmin) {
    return <AppShell><div className="p-12 text-center text-[var(--muted)]">Superadmin only.</div></AppShell>;
  }

  const onCompose = async () => {
    if (topic.trim().length < 8) { toast.message("Give the topic at least 8 characters."); return; }
    setComposing(true); setDraft(null);
    try {
      const { data } = await api.post("/blog/compose", { topic: topic.trim(), audience_hint: audience }, { timeout: 180000 });
      setDraft(data);
      toast.success("Draft composed. Review below, then publish.");
      loadPosts();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setComposing(false); }
  };

  const onPublish = async (slug) => {
    try {
      await api.post(`/blog/posts/${slug}/publish`);
      toast.success(`Published — live at /blog/${slug}`);
      setDraft(null);
      loadPosts();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onDelete = async (slug) => {
    if (!confirm(`Delete "${slug}"?`)) return;
    try {
      await api.delete(`/blog/posts/${slug}`);
      toast.success("Deleted.");
      loadPosts();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const copy = (text, label) => {
    navigator.clipboard.writeText(text || "");
    toast.success(`${label} copied.`);
  };

  // Build a Medium-flavored markdown payload from a draft (or any post-shaped object).
  // Medium's import accepts standard markdown — kicker becomes a label line, dek becomes
  // a blockquote so it renders as a styled subtitle, then body markdown is preserved.
  const buildMediumMarkdown = (p) => {
    const lines = [];
    if (p.kicker) lines.push(`**${p.kicker.toUpperCase()}**`, "");
    lines.push(`# ${p.title}`, "");
    if (p.dek) lines.push(`> ${p.dek}`, "");
    lines.push((p.body || "").trim());
    if (p.tags?.length) lines.push("", `_Tags: ${p.tags.join(", ")}_`);
    return lines.join("\n");
  };

  const onCopyForMedium = async (p) => {
    let full = p?.body ? p : bodyCache[p?.slug];
    if (!full?.body) {
      try {
        const { data } = await api.get(`/blog/admin/posts/${p.slug}`);
        full = data;
        setBodyCache((prev) => ({ ...prev, [p.slug]: data }));
      } catch (e) { toast.error(apiErrorMessage(e)); return; }
    }
    if (!full?.body) { toast.error("This post has no body to copy."); return; }
    copy(buildMediumMarkdown(full), "Medium-ready markdown");
  };

  return (
    <AppShell>
      <div className="max-w-[1100px] mx-auto px-8 py-10">
        <div className="mb-8">
          <p className="akki-overline mb-2 text-[var(--accent)]">Exco360 · Admin</p>
          <h1 className="akki-greeting mb-2">Compose, publish, distribute.</h1>
          <p className="akki-meta">{subscribers.length} active subscribers · {posts.filter((p) => p.status === "published").length} published · {posts.filter((p) => p.status === "draft").length} drafts</p>
        </div>

        <div className="bg-white border border-[var(--rule)] rounded-lg p-5 mb-8" data-testid="blog-compose">
          <p className="akki-overline mb-3">Compose this week's issue</p>
          <div className="space-y-2">
            <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Topic — e.g. 'Why audit committees should ask about model drift this quarter'" className="h-11 bg-[var(--cream)] border-[var(--rule)] text-sm" data-testid="compose-topic" />
            <Input value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="Audience hint (optional)" className="h-10 bg-[var(--cream)] border-[var(--rule)] text-sm" data-testid="compose-audience" />
            <Button onClick={onCompose} disabled={composing} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="compose-btn">
              {composing
                ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> AKKI is writing — usually 30–60s</>
                : <><Sparkles className="w-3.5 h-3.5 mr-2" /> Compose draft</>}
            </Button>
          </div>
        </div>

        {draft && (
          <div className="bg-white border-2 border-[var(--accent)]/30 rounded-lg p-7 mb-8" data-testid="blog-draft">
            <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] font-mono mb-3">{draft.kicker}</p>
            <h2 className="akki-serif text-[26px] text-[var(--ink)] mb-3 leading-snug">{draft.title}</h2>
            <p className="akki-serif text-[15.5px] italic text-[var(--deep)] mb-4">{draft.dek}</p>
            <div className="bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-md p-4 max-h-80 overflow-y-auto mb-5">
              <p className="akki-serif text-[14px] whitespace-pre-wrap text-[var(--deep)]">{draft.body.slice(0, 2200)}{draft.body.length > 2200 ? "…" : ""}</p>
            </div>
            <div className="flex flex-wrap gap-2 items-center mb-5">
              <Link to={`/blog/${draft.slug}`} target="_blank" className="text-[13px] text-[var(--accent)] hover:underline inline-flex items-center gap-1">
                <ExternalLink className="w-3.5 h-3.5" /> Preview at /blog/{draft.slug}
              </Link>
              <span className="text-[12px] text-[var(--muted)]">· {draft.read_minutes} min read</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
              {draft.linkedin_post && (
                <button onClick={() => copy(draft.linkedin_post, "LinkedIn post")} className="text-left bg-white border border-[var(--rule)] rounded-md p-3 hover:border-[var(--accent)]/40 transition-colors" data-testid="copy-linkedin">
                  <p className="text-[10.5px] uppercase tracking-wider text-[var(--accent)] mb-1.5 inline-flex items-center gap-1.5"><Copy className="w-3 h-3" /> Copy for LinkedIn</p>
                  <p className="text-[13px] text-[var(--deep)] line-clamp-3">{draft.linkedin_post.slice(0, 220)}…</p>
                </button>
              )}
              {draft.email_intro && (
                <button onClick={() => copy(draft.email_intro, "Email intro")} className="text-left bg-white border border-[var(--rule)] rounded-md p-3 hover:border-[var(--accent)]/40 transition-colors" data-testid="copy-email">
                  <p className="text-[10.5px] uppercase tracking-wider text-[var(--accent)] mb-1.5 inline-flex items-center gap-1.5"><Copy className="w-3 h-3" /> Copy for newsletter</p>
                  <p className="text-[13px] text-[var(--deep)] line-clamp-3">{draft.email_intro.slice(0, 220)}…</p>
                </button>
              )}
              <button onClick={() => onCopyForMedium(draft)} className="text-left bg-white border border-[var(--rule)] rounded-md p-3 hover:border-[var(--accent)]/40 transition-colors" data-testid="copy-medium">
                <p className="text-[10.5px] uppercase tracking-wider text-[var(--accent)] mb-1.5 inline-flex items-center gap-1.5"><BookOpen className="w-3 h-3" /> Copy for Medium</p>
                <p className="text-[13px] text-[var(--deep)] line-clamp-3">
                  Title, dek and full body as Medium-ready markdown. Paste into <em>Stories → Import a story</em> or a new draft.
                </p>
              </button>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDraft(null)} className="border-[var(--rule)]">Discard preview</Button>
              <Button onClick={() => onPublish(draft.slug)} className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white" data-testid="publish-btn">
                <Send className="w-3.5 h-3.5 mr-1.5" /> Publish
              </Button>
            </div>
          </div>
        )}

        <div data-testid="blog-posts-list">
          <p className="akki-overline mb-3">All posts</p>
          {posts.length === 0 ? (
            <p className="text-[13px] text-[var(--muted)] italic py-6">No posts yet. Compose your first above.</p>
          ) : (
            <div className="space-y-2">
              {posts.map((p) => (
                <div key={p.slug} className="bg-white border border-[var(--rule)] rounded-md p-4 flex items-start gap-3" data-testid={`admin-post-${p.slug}`}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded ${p.status === "published" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{p.status}</span>
                      <span className="text-[11px] text-[var(--muted)] font-mono">{p.kicker}</span>
                    </div>
                    <p className="akki-serif text-[15px] text-[var(--ink)]">{p.title}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Link to={`/blog/${p.slug}`} target="_blank" className="text-[12px] text-[var(--accent)] hover:underline inline-flex items-center gap-1">
                      <ExternalLink className="w-3 h-3" /> View
                    </Link>
                    <button onClick={() => onCopyForMedium(p)} className="text-[12px] text-[var(--deep)] hover:text-[var(--accent)] inline-flex items-center gap-1" data-testid={`copy-medium-${p.slug}`}>
                      <BookOpen className="w-3 h-3" /> Medium
                    </button>
                    {p.status === "draft" && (
                      <button onClick={() => onPublish(p.slug)} className="text-[12px] text-emerald-700 hover:underline" data-testid={`publish-${p.slug}`}>Publish</button>
                    )}
                    <button onClick={() => onDelete(p.slug)} className="text-[var(--muted)] hover:text-[var(--accent)]" data-testid={`delete-${p.slug}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
