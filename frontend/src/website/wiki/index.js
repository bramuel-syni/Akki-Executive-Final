/**
 * Wiki content manifest — Phase P1 γ (2026-02).
 *
 * Compile-time index of every published article. Each article is a
 * markdown file under `wiki/content/**.md` imported as a raw string
 * via webpack's `raw-loader` shape (CRA's `?raw` query). The shape:
 *
 *   {
 *     slug: "work-studio-chat",        // URL slug
 *     title: "Work Studio · Chat",     // sidebar + breadcrumb
 *     category: "Work Studio",         // sidebar group heading
 *     adminOnly: false,                 // true → only renders for admins
 *     order: 10,                        // within-category sort key
 *     body: "<markdown source>",       // raw markdown
 *   }
 *
 * Adding a new article: drop a .md file under `wiki/content/`, then
 * import it here and append to ARTICLES with the metadata. The fuzzy
 * search + sidebar pick it up automatically.
 *
 * Voice-lint runs over every body string before bundle time
 * (CI-enforced by /app/scripts/lint_voice.py extended targets).
 */
import workStudioChat from "./content/work-studio-chat.md";
import workStudioCompile from "./content/work-studio-compile.md";
import solvaOverview from "./content/solva-overview.md";
import trustCenter from "./content/trust-center.md";
import accountAuth from "./content/account-auth.md";
import cohort from "./content/cohort.md";
import adminUsers from "./content/admin/admin-users.md";

export const ARTICLES = [
  // Work Studio
  { slug: "work-studio-chat",    title: "Work Studio · Chat",       category: "Work Studio", order: 10, adminOnly: false, body: workStudioChat },
  { slug: "work-studio-compile", title: "Work Studio · Compile",    category: "Work Studio", order: 20, adminOnly: false, body: workStudioCompile },
  // Solva
  { slug: "solva-overview",      title: "Solva · Overview",          category: "Solva",       order: 10, adminOnly: false, body: solvaOverview },
  // Trust + Account
  { slug: "trust-center",        title: "Trust Center",              category: "Trust",       order: 10, adminOnly: false, body: trustCenter },
  { slug: "account-auth",        title: "Account & sign-in",         category: "Account",     order: 10, adminOnly: false, body: accountAuth },
  { slug: "cohort",              title: "Early access",              category: "Account",     order: 20, adminOnly: false, body: cohort },
  // Admin (only rendered when account.is_superadmin === true)
  { slug: "admin-users",         title: "Admin · Users",             category: "Admin",       order: 10, adminOnly: true,  body: adminUsers },
];

export function categoriesFor(isAdmin) {
  const filtered = ARTICLES.filter((a) => !a.adminOnly || isAdmin);
  const grouped = {};
  for (const a of filtered) {
    (grouped[a.category] = grouped[a.category] || []).push(a);
  }
  for (const k of Object.keys(grouped)) {
    grouped[k].sort((x, y) => x.order - y.order);
  }
  return grouped;
}

export function findArticle(slug, isAdmin) {
  return ARTICLES.find((a) => a.slug === slug && (!a.adminOnly || isAdmin)) || null;
}
