/**
 * Solva briefing-deck canonical data — Phase D.1 (2026-05-26).
 *
 * Slide copy is stored VERBATIM as supplied by the product brief.
 * Any paraphrasing is a hard fail.
 *
 * Area slugs:
 *   - seek-clarity            → backend submodule `seek_clarity`
 *   - test-hypothesis         → backend submodule `simulate_hypothesis`
 *   - develop-strategy        → backend submodule `develop_strategy`
 *   - different-perspective   → backend submodule `get_perspective`
 *
 * The frontend area slugs DIFFER from the backend submodule names by
 * design (the briefing copy was authored against the user-facing
 * names; the backend kept its older internal names from Phase H).
 * `AREA_TO_SUBMODULE` is the canonical translation.
 *
 * The first WORD of each slide title is rendered in oxblood by the
 * deck component (split on the first space). The rest of the title
 * renders in the default INK token.
 *
 * Body strings use markdown — `- ` bullets are rendered as clean
 * bullet lists; blank lines separate paragraphs.
 */

export const AREA_TO_SUBMODULE = {
  "seek-clarity": "seek_clarity",
  "test-hypothesis": "simulate_hypothesis",
  "develop-strategy": "develop_strategy",
  "different-perspective": "get_perspective",
};

export const SUBMODULE_TO_AREA = Object.fromEntries(
  Object.entries(AREA_TO_SUBMODULE).map(([area, sub]) => [sub, area])
);

export const SOLVA_AREAS = {
  "seek-clarity": {
    label: "Seek Clarity",
    slides: [
      {
        title: "Solva seeks clarity.",
        body: "When a decision feels heavy or unclear, Solva walks you through it — one question at a time — until your own thinking holds together.\n\nSolva doesn't give you the answer. It gives you back the question you were actually trying to ask.\n\nUse it for: board calls, regulator responses, hard people decisions, anything you'd normally chew on in the shower."
      },
      {
        title: "Speak plainly. That's it.",
        body: "Full sentences, half-thoughts, \"I don't know where to start\" — Solva works with all of it.\n\nIt will ask you questions back. You're driving; it's pacing.\n\nEverything stays inside this company's account. Shielded before any AI sees it."
      },
      {
        title: "A short, focused conversation.",
        body: "- 3 to 7 questions, depending on complexity\n- A summary of your thinking at the end\n- A clear next step — draft a note, schedule a cycle, save the brief, or just close the loop\n\nSet aside 5 to 15 minutes. You can pause and resume."
      },
      {
        title: "Have your context within reach.",
        body: "Solva may ask for an attachment — board pack, regulator letter, contract, financials.\n\nEvery file is shielded before any AI sees it. Nothing leaves your tenant.\n\nNo document handy? That's fine. Solva works with what you tell it.\n\nReady when you are."
      }
    ]
  },
  "test-hypothesis": {
    label: "Test Your Hypothesis",
    slides: [
      {
        title: "Bring a theory. Solva will pressure-test it.",
        body: "You've got a hunch — maybe a strategy bet, a hire, a risk call. Before it leaves your head, Solva probes it from every side: assumptions, evidence, counter-cases, blind spots.\n\nYou leave with a sharper hypothesis, or a clear reason to drop it.\n\nUse it for: investment theses, market bets, talent decisions, anything you'd ask a smart sceptic."
      },
      {
        title: "State your hypothesis up front.",
        body: "One or two sentences is enough. \"I believe X because Y.\" Solva will treat it as the thing on trial.\n\nExpect challenge — Solva will ask for the weakest version of your case, not the strongest. That's the point.\n\nEverything stays inside this company's account. Shielded before any AI sees it."
      },
      {
        title: "A structured stress test.",
        body: "- Solva surfaces the assumptions you didn't realise you were making\n- It offers counter-evidence and counter-cases\n- You leave with a confidence read — sharper, weaker, or refined\n\nPlan for 10 to 20 minutes. The harder your hypothesis, the longer the test."
      },
      {
        title: "Bring the evidence you'd actually defend with.",
        body: "Numbers, market data, prior decisions, the memo behind your view — whatever you'd use if a sceptical board pushed back.\n\nSolva may ask for attachments. Every file is shielded before any AI sees it. Nothing leaves your tenant.\n\nNo supporting docs? Solva will still test the logic — just with less specificity.\n\nReady when you are."
      }
    ]
  },
  "develop-strategy": {
    label: "Develop Strategy",
    slides: [
      {
        title: "Build the strategy with you, not for you.",
        body: "Start with a goal or a constraint. Solva helps you map the options, weigh trade-offs, sequence the moves, and surface what you haven't thought about yet.\n\nYou leave with a working strategy outline — yours, not the AI's.\n\nUse it for: market entry, restructures, product bets, board strategy refresh."
      },
      {
        title: "Frame the goal and the constraints.",
        body: "\"We need to do X within Y, with Z available.\" Solva will work the shape of the problem before reaching for solutions.\n\nIt will ask about resources, time, risk appetite, what's already been tried. The more you tell it, the sharper the output.\n\nEverything stays inside this company's account. Shielded before any AI sees it."
      },
      {
        title: "A working outline by the end.",
        body: "- 2 to 4 viable paths with honest trade-offs\n- You pick the path; Solva helps you sequence the moves\n- Output: an outline you can take into a board pack, a memo, or a planning session\n\nPlan for 15 to 30 minutes. You can pause and resume — strategy work rarely lands in one sitting."
      },
      {
        title: "Know your boundaries before you start.",
        body: "Budget, headcount, regulatory limits, board mandate, time horizon — Solva's strategy work is only as honest as the constraints you give it.\n\nAttachments help — a prior strategy doc, a board mandate, financials, market research. Every file is shielded before any AI sees it.\n\nNo prep? You'll still get a structure. It just won't fit your situation as precisely.\n\nReady when you are."
      }
    ]
  },
  "different-perspective": {
    label: "See From Different Perspective",
    slides: [
      {
        title: "Step out of your seat for a minute.",
        body: "Pick a situation — a decision, an announcement, a conflict — and Solva replays it through the eyes of people who see it differently: a regulator, an investor, a customer, an employee, a competitor.\n\nYou leave with the same situation, but a wider field of view.\n\nUse it for: board comms, restructures, contentious decisions, anything where you suspect you're seeing one side."
      },
      {
        title: "Describe the situation, then pick the lenses.",
        body: "Tell Solva what's happening in plain language. Then choose which stakeholders to view it through — Solva will role-play each one honestly, including the uncomfortable parts.\n\nIt's not flattery and it's not gotchas. It's what those people would actually be thinking.\n\nEverything stays inside this company's account. Shielded before any AI sees it."
      },
      {
        title: "Multiple lenses, side by side.",
        body: "- 2 to 5 stakeholder perspectives, depending on who you pick\n- Each lens gives you their likely concerns, questions, and reactions\n- A synthesis at the end — where the views overlap, where they collide\n\nPlan for 10 to 20 minutes. The richer the situation, the longer the read."
      },
      {
        title: "Some perspectives may sting.",
        body: "Solva doesn't soften what stakeholders would say. If a regulator would call your plan reckless, you'll see that wording.\n\nAttachments help — the announcement draft, the memo, the policy — but they're optional. Verbal context works too.\n\nEvery file is shielded before any AI sees it. Nothing leaves your tenant.\n\nReady when you are."
      }
    ]
  }
};
