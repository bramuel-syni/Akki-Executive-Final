import { useEffect, useState } from "react";

/**
 * useAIStageTicker — cycles through a list of narrative stages while a
 * long-running async action is underway. Centralises the "AI is thinking" UX
 * so Signals, Briefings, and The Lens all share one voice.
 *
 * Usage:
 *   const stage = useAIStageTicker(isRunning, [
 *     { at: 0,     text: "Reading your pack…" },
 *     { at: 6000,  text: "Cross-referencing the last minutes…" },
 *     { at: 14000, text: "Drafting the sharpest question for the chair…" },
 *   ]);
 */
export function useAIStageTicker(active, stages) {
  const [stage, setStage] = useState("");
  useEffect(() => {
    if (!active || !stages?.length) {
      setStage("");
      return;
    }
    setStage(stages[0].text);
    const timers = stages.slice(1).map((s) =>
      setTimeout(() => setStage(s.text), s.at)
    );
    return () => timers.forEach(clearTimeout);
  }, [active, stages]);
  return stage;
}
