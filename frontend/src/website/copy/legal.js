/**
 * Phase I1 — Legal copy. Generic templates tailored to Akki's
 * privacy-first architecture. Replace with counsel-reviewed text
 * before public launch.
 */
export const PRIVACY = {
  effective: "Effective 1 May 2026",
  blocks: [
    {
      h: "What this is",
      p: "Akki Limited (\"Akki\", \"we\") provides a private working environment for senior people to use AI. This policy explains what data we collect, why, and how we protect it.",
    },
    {
      h: "What we collect",
      p: "Your account details. The content you upload or type into Akki. Operational telemetry: the timing and success of each action you take, sampled at low rates for service-reliability reasons. We log the IP address you used at sign-in (hashed and truncated, never stored in raw form). We do not run third-party analytics or retargeting pixels.",
    },
    {
      h: "How your content is used",
      p: "Your content is used only to provide the service to you. It is never used to train any AI model. When a model is invoked, your content is first passed through Synisense Shield, our de-identification engine, before being sent to the model provider. Synisense rehydrates the response so you see your data fully restored.",
    },
    {
      h: "Where your content lives",
      p: "Encrypted at rest in a customer-isolated database. Original prompts that Synisense Shield processes are stored with envelope encryption and a customer-isolated key. We log only the SHA-256 of the input — never the input itself.",
    },
    {
      h: "Who can see what",
      p: "You — and only you — within your tenant. Akki personnel access tenant data only with your explicit written request (for example, debugging a problem you have asked us to investigate). We log every such access.",
    },
    {
      h: "Cross-board data",
      p: "If you hold seats on more than one company on Akki, the companies are architecturally isolated. Cross-board features run on metadata signatures — never on the underlying content. This is enforced in code and audited in our test suite.",
    },
    {
      h: "Audit trail",
      p: "Every chat turn is written into a hash-chained audit log. You can download and verify the chain at any time. The chain is preserved across deletions.",
    },
    {
      h: "Your rights",
      p: "You can export your data. You can delete your data — soft delete is immediate; hard delete happens after a 30-day window. You can ask for a list of every place your data has been processed. You can ask us to forget you entirely.",
    },
    {
      h: "Contact",
      p: "For privacy questions, write to privacy@akki.syni.ai.",
    },
  ],
};

export const TERMS = {
  effective: "Effective 1 May 2026",
  blocks: [
    { h: "Agreement", p: "By accessing Akki you agree to these Terms. If you do not agree, do not use Akki." },
    { h: "What we provide", p: "A private working environment for senior people to use AI. The service is provided as-is, on a subscription basis described in the Pricing page." },
    { h: "Acceptable use", p: "Akki is a tool for legitimate decision support. Do not use it to break the law, infringe rights, or harm others." },
    { h: "Your content, your responsibility", p: "You retain ownership of everything you upload or generate. You confirm you have the rights to whatever you upload." },
    { h: "Our service, our responsibility", p: "We will operate the service with diligence. We will not train models on your content. We will tell you within 72 hours of any security incident that touches your data." },
    { h: "Limits", p: "Akki is decision support, not legal, regulatory, or fiduciary advice. The output of any AI tool — including ours — must be reviewed by the human who signs the decision." },
    { h: "Termination", p: "You can cancel at any time. We may suspend an account that breaches these Terms. We will export your data on request before any deletion." },
    { h: "Liability", p: "To the extent permitted by law, our liability is capped at the fees you paid us in the prior 12 months." },
    { h: "Governing law", p: "England and Wales." },
    { h: "Contact", p: "For legal questions, write to legal@akki.syni.ai." },
  ],
};
