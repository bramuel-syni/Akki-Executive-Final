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

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

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
