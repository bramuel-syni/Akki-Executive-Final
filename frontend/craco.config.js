// craco.config.js
const path = require("path");
require("dotenv").config();

// Check if we're in development/preview mode (not production build)
// Craco sets NODE_ENV=development for start, NODE_ENV=production for build
const isDevServer = process.env.NODE_ENV !== "production";

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

let webpackConfig = {
  eslint: {
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
        // ─── Hardening Step 2 Phase C (2026-05-25) — B3 pattern ─────
        // `react/jsx-no-undef` + `no-undef` catch the case from B3
        // (closeout §5.6 import-survival rule) where a JSX symbol
        // referenced inside a conditional branch isn't declared /
        // imported. Without these rules, the broken branch hides
        // behind the condition gate at unit-test time and only
        // surfaces at runtime when the gate fires. Tooling-level
        // pin for the audit-ledger Pattern 2 class. See
        // /app/memory/sprints/FALSE_GREEN_AUDIT_LEDGER.md.
        "react/jsx-no-undef": "error",
        "no-undef": "error",
        // Code-hygiene rules (formerly .eslintrc.js, consolidated here
        // because craco's eslint.configure REPLACES the rc-file config).
        "no-duplicate-imports": ["error", { includeExports: true }],
        // ─── Patch 24B — ban raw `fetch()` / `new Request()` ────────
        // Prevents the P0 (Patch 23) regression class: raw fetch()
        // bypasses the axios `api` client's bearer-token /
        // X-Active-Context interceptors -> every request 401. Use
        // `api` from `@/lib/api` instead. Per-file disables permitted
        // for SSE streaming or PUBLIC marketing endpoints — add
        // `// eslint-disable-next-line no-restricted-syntax -- <reason>`.
        // Allowlist: `src/lib/api.js` (the canonical client), `src/sandbox/api.js`
        // (sandbox-only API surface), `*.test.{js,jsx,ts,tsx}`,
        // `**/__tests__/**`, `tests/**`. See
        // /app/memory/sprints/LINT_API_CLIENT_RULE.md.
        "no-restricted-syntax": [
          "error",
          {
            selector: "CallExpression[callee.name='fetch']",
            message:
              "Use the project's `api` client (`import { api } from '@/lib/api'`) " +
              "instead of raw `fetch()`. Raw `fetch()` bypasses bearer-token / " +
              "X-Active-Context / error interceptors. " +
              "See /app/memory/sprints/LINT_API_CLIENT_RULE.md (Patch 24B). " +
              "Legitimate exception (SSE streaming, public marketing endpoint)? " +
              "Add `// eslint-disable-next-line no-restricted-syntax -- <reason>`.",
          },
          {
            selector: "NewExpression[callee.name='Request']",
            message:
              "Use the project's `api` client (`import { api } from '@/lib/api'`) " +
              "instead of constructing a raw `Request`. " +
              "See /app/memory/sprints/LINT_API_CLIENT_RULE.md (Patch 24B).",
          },
        ],
      },
      overrides: [
        // The api client itself is allowed to use fetch / axios internally.
        { files: ["src/lib/api.js", "src/lib/api.ts"],
          rules: { "no-restricted-syntax": "off" } },
        // Sandbox sub-app has its own (public, no-auth) API wrapper.
        { files: ["src/sandbox/api.js", "src/sandbox/api.ts"],
          rules: { "no-restricted-syntax": "off" } },
        // Test files may use fetch() for setup / mocking.
        { files: ["**/*.test.{js,jsx,ts,tsx}", "**/__tests__/**", "tests/**"],
          rules: { "no-restricted-syntax": "off" } },
      ],
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // Phase P1 γ (2026-02) — Wiki content authored in markdown.
      // Import .md files as raw strings (via asset/source). This
      // keeps the source-of-truth as plain markdown without
      // requiring a separate raw-loader dependency.
      webpackConfig.module = webpackConfig.module || { rules: [] };
      webpackConfig.module.rules.push({
        test: /\.md$/i,
        type: "asset/source",
      });

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  // ─── Phase P2.1-1 (2026-02) — Security headers on the HTML shell ───
  // The webpack-dev-server Express layer serves the React HTML at /,
  // /signin, /app/**, etc. The backend FastAPI middleware doesn't touch
  // those responses. Inject the same 6 headers here so the HTML shell
  // carries them too. CSP is included (relaxed for dev — allows
  // 'unsafe-inline' / 'unsafe-eval' which CRA needs).
  const SECURITY_HEADERS_HTML = {
    "Strict-Transport-Security":       "max-age=63072000; includeSubDomains",
    "X-Frame-Options":                 "DENY",
    "X-Content-Type-Options":          "nosniff",
    "Referrer-Policy":                 "strict-origin-when-cross-origin",
    "Permissions-Policy":              "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Content-Security-Policy": [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.sentry-cdn.com https://browser.sentry-cdn.com",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' data: https://fonts.gstatic.com",
      "img-src 'self' data: blob: https:",
      "connect-src 'self' https: wss: ws:",
      "media-src 'self' blob:",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
    ].join("; "),
  };
  const securityHeadersMiddleware = (req, res, next) => {
    for (const [k, v] of Object.entries(SECURITY_HEADERS_HTML)) {
      // setHeader (not append) — last-write wins so we don't double up.
      res.setHeader(k, v);
    }
    next();
  };

  const originalSetupMiddlewares = devServerConfig.setupMiddlewares;
  devServerConfig.setupMiddlewares = (middlewares, devServer) => {
    if (originalSetupMiddlewares) {
      middlewares = originalSetupMiddlewares(middlewares, devServer);
    }
    // Mount the security-headers middleware FIRST so every downstream
    // response (HTML, static, hot-reload sockets) carries the headers.
    middlewares.unshift({
      name: "security-headers",
      middleware: securityHeadersMiddleware,
    });

    // Phase P2.1-1 — optional health check endpoints (existing feature)
    if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
      setupHealthEndpoints(devServer, healthPluginInstance);
    }
    return middlewares;
  };

  return devServerConfig;
};

// Wrap with visual edits (automatically adds babel plugin, dev server, and overlay in dev mode)
if (isDevServer) {
  try {
    const { withVisualEdits } = require("@emergentbase/visual-edits/craco");
    webpackConfig = withVisualEdits(webpackConfig);
  } catch (err) {
    if (err.code === 'MODULE_NOT_FOUND' && err.message.includes('@emergentbase/visual-edits/craco')) {
      console.warn(
        "[visual-edits] @emergentbase/visual-edits not installed — visual editing disabled."
      );
    } else {
      throw err;
    }
  }
}

module.exports = webpackConfig;
