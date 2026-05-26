/**
 * DocumentDrawerWatermark — Phase E.3 (2026-05-26).
 *
 * DRAFT watermark overlay rendered on top of the document body when
 * the drawer is in Creation mode (state === "draft"). Tiled repeating
 * "DRAFT" text, rotated -30deg, oxblood at ~12% opacity. Pointer-events
 * disabled so the underlying body remains interactive.
 *
 * Per the Phase E brief: "Visible to anyone shoulder-surfing." This is
 * a viewing-only watermark; export-side watermarking is enforced via
 * the `/export-guard` backend endpoint (drafts cannot export until the
 * server-side watermark pipeline lands).
 */
import React from "react";


export default function DocumentDrawerWatermark() {
  // SVG-based tiled watermark — crisper than CSS background-image text
  // at any zoom level. Pointer-events on the wrapper are disabled so
  // clicks pass through to the body underneath.
  return (
    <div
      className="absolute inset-0 pointer-events-none overflow-hidden z-0"
      aria-hidden="true"
      data-testid="document-drawer-draft-watermark"
    >
      <svg
        width="100%"
        height="100%"
        xmlns="http://www.w3.org/2000/svg"
        style={{ opacity: 0.12 }}
      >
        <defs>
          <pattern
            id="draft-watermark-pattern"
            patternUnits="userSpaceOnUse"
            width="280"
            height="180"
            patternTransform="rotate(-30)"
          >
            <text
              x="0"
              y="100"
              fill="var(--oxblood, #7A2E2E)"
              fontFamily="Georgia, serif"
              fontSize="64"
              fontWeight="700"
              letterSpacing="0.1em"
            >
              DRAFT
            </text>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#draft-watermark-pattern)" />
      </svg>
    </div>
  );
}
