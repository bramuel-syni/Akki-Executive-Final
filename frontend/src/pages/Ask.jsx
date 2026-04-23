import React from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import AskPanel from "@/components/ask/AskPanel";
import { useAuth } from "@/contexts/AuthContext";
import { ArrowRight } from "lucide-react";

export default function Ask() {
  const { account, activeContext } = useAuth();
  const contextId = activeContext?.id;

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  const header = (
    <div className="border-b border-[#E1E6ED] bg-white px-6 py-5">
      <p className="akki-overline mb-1.5">Ask · Module M5</p>
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-light tracking-tight text-[#0A1F44]">Grounded Q&amp;A</h1>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Every answer is grounded in documents from <strong className="text-[#0A1F44]">{activeContext.name}</strong> with inline citations. If the answer isn't there, AKKI will say so.
          </p>
        </div>
        <Link to="/app/workspace" className="inline-flex items-center gap-1 text-[11px] text-[#C9A961] hover:underline font-medium shrink-0">
          Open Workspace <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] max-w-5xl mx-auto">
        <AskPanel
          contextId={contextId}
          accountName={account?.name}
          header={header}
        />
      </div>
    </AppShell>
  );
}
