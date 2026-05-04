import React, { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Copy, Mail, Inbox } from "lucide-react";
import { toast } from "sonner";

/**
 * InboundEmailPanel — surfaces the user's personal forwarding address (and a
 * context-scoped address). Forwarding an email to either ingests it into
 * AKKI as a first-class document via the Postmark inbound webhook.
 */
export default function InboundEmailPanel({ contextId, contextName }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setErr(null);
    const url = contextId
      ? `/inbound/address?context_id=${encodeURIComponent(contextId)}`
      : `/inbound/address`;
    api
      .get(url)
      .then((r) => { if (live) setData(r.data); })
      .catch((e) => { if (live) setErr(apiErrorMessage(e)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [contextId]);

  const copy = (text, label) => {
    if (!text) return;
    navigator.clipboard.writeText(text).then(
      () => toast.success(`${label} copied`),
      () => toast.error("Copy failed")
    );
  };

  return (
    <section
      className="bg-white border border-[#E1E6ED] rounded-sm"
      data-testid="inbound-email-panel"
    >
      <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center gap-3">
        <Inbox className="w-5 h-5 text-[var(--accent)]" strokeWidth={1.7} />
        <div>
          <h3 className="akki-serif text-[18px] text-[var(--ink)]">
            Forward by email
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Forward any email — minutes, board packs, agendas — to your AKKI
            address and we'll ingest it (and its attachments) as a document.
          </p>
        </div>
      </div>

      <div className="px-6 py-5 space-y-5">
        {loading && (
          <p className="text-sm text-slate-500">Loading address…</p>
        )}
        {err && (
          <p className="text-sm text-rose-700" data-testid="inbound-error">{err}</p>
        )}
        {data && !data.configured && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-3 py-2">
            Inbound mail is not yet configured on this server. Addresses are
            shown for preview only — forwarding will not be ingested until an
            administrator enables Postmark inbound.
          </p>
        )}

        {data && (
          <div className="space-y-4">
            <AddressRow
              label="Personal inbox"
              hint="Goes to your default company."
              address={data.address}
              testId="inbound-personal-address"
              onCopy={() => copy(data.address, "Personal address")}
            />
            {data.context_address && (
              <AddressRow
                label={`Direct to ${contextName || "this company"}`}
                hint="Anything sent here lands in this company only."
                address={data.context_address}
                testId="inbound-context-address"
                onCopy={() => copy(data.context_address, "Company address")}
              />
            )}
          </div>
        )}

        <div className="pt-3 border-t border-[#E1E6ED] text-[12px] text-slate-500 leading-relaxed">
          <div className="font-medium text-[var(--ink)] mb-1 flex items-center gap-1.5">
            <Mail className="w-3.5 h-3.5" strokeWidth={1.7} />
            How it works
          </div>
          We attach the forwarded email body and any PDF/DOCX/TXT
          attachments. Subjects starting with "Minutes" are auto-tagged so
          they show up in Prepare → Minutes. Sender must match a registered
          AKKI account.
        </div>
      </div>
    </section>
  );
}

function AddressRow({ label, hint, address, onCopy, testId }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
            {label}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">{hint}</div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onCopy}
          data-testid={`${testId}-copy`}
          className="h-7 text-xs"
        >
          <Copy className="w-3 h-3 mr-1.5" />
          Copy
        </Button>
      </div>
      <div
        className="mt-2 px-3 py-2 bg-[var(--cream)] border border-[#E1E6ED] rounded-sm font-mono text-[13px] text-[var(--ink)] break-all"
        data-testid={testId}
      >
        {address}
      </div>
    </div>
  );
}
