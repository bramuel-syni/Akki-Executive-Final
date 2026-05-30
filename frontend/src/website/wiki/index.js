/**
 * Wiki content manifest — Phase P1 γ (2026-02) · expanded P2 C.3
 * (2026-02).
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
import workStudioTasks from "./content/work-studio-tasks.md";
import workStudioDocuments from "./content/work-studio-documents.md";
import solvaOverview from "./content/solva-overview.md";
import solvaModes from "./content/solva-modes.md";
import solvaConfidence from "./content/solva-confidence.md";
import trustCenter from "./content/trust-center.md";
import trustPillars from "./content/trust-pillars.md";
import auditTrail from "./content/audit-trail.md";
import accountAuth from "./content/account-auth.md";
import mfaArticle from "./content/mfa.md";
import cohort from "./content/cohort.md";
import adminUsers from "./content/admin/admin-users.md";
import adminCohortApplications from "./content/admin/admin-cohort-applications.md";
import adminPromptTuning from "./content/admin/admin-prompt-tuning.md";

export const ARTICLES = [
  // Work Studio
  { slug: "work-studio-chat",      title: "Work Studio · Chat",      category: "Work Studio", order: 10, adminOnly: false, body: workStudioChat },
  { slug: "work-studio-compile",   title: "Work Studio · Compile",   category: "Work Studio", order: 20, adminOnly: false, body: workStudioCompile },
  { slug: "work-studio-tasks",     title: "Work Studio · Tasks",     category: "Work Studio", order: 30, adminOnly: false, body: workStudioTasks },
  { slug: "work-studio-documents", title: "Work Studio · Documents", category: "Work Studio", order: 40, adminOnly: false, body: workStudioDocuments },
  // Solva
  { slug: "solva-overview",        title: "Solva · Overview",         category: "Solva",       order: 10, adminOnly: false, body: solvaOverview },
  { slug: "solva-modes",           title: "Solva · Modes",            category: "Solva",       order: 20, adminOnly: false, body: solvaModes },
  { slug: "solva-confidence",      title: "Solva · Confidence",       category: "Solva",       order: 30, adminOnly: false, body: solvaConfidence },
  // Trust
  { slug: "trust-center",          title: "Trust Center",             category: "Trust",       order: 10, adminOnly: false, body: trustCenter },
  { slug: "trust-pillars",         title: "The four pillars",         category: "Trust",       order: 20, adminOnly: false, body: trustPillars },
  { slug: "audit-trail",           title: "Audit trail",              category: "Trust",       order: 30, adminOnly: false, body: auditTrail },
  // Account
  { slug: "account-auth",          title: "Account & sign-in",        category: "Account",     order: 10, adminOnly: false, body: accountAuth },
  { slug: "mfa",                   title: "Multi-factor authentication", category: "Account",  order: 20, adminOnly: false, body: mfaArticle },
  { slug: "cohort",                title: "Early access",             category: "Account",     order: 30, adminOnly: false, body: cohort },
  // Admin (only rendered when account.is_superadmin === true)
  { slug: "admin-users",           title: "Admin · Users",            category: "Admin",       order: 10, adminOnly: true,  body: adminUsers },
  { slug: "admin-cohort-applications", title: "Admin · Cohort applications", category: "Admin", order: 20, adminOnly: true, body: adminCohortApplications },
  { slug: "admin-prompt-tuning",   title: "Admin · Prompt tuning",    category: "Admin",       order: 30, adminOnly: true,  body: adminPromptTuning },
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
