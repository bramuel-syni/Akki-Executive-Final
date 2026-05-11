import React from "react";
import WebsiteShell from "../WebsiteShell";
import { ABOUT } from "../copy";
import "../style.css";

export default function AboutPage() {
  return (
    <WebsiteShell
      title="About Akki"
      description="Akki is built by operators, builders and former board members for senior peers."
      pathname="/about"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">About</span>
        <h1>Who builds Akki.</h1>
        <span className="website-rule" />
        {ABOUT.body.map((para, i) => <p key={i}>{para}</p>)}
      </section>
    </WebsiteShell>
  );
}
