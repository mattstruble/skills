export const meta = {
  name: "orchestrator_strong_pass",
  description: "Deep review of the integrated working branch: wave mode (one correctness reviewer on the delta since the last strong pass) or epic mode (all four reviewers over the whole base range)",
  phases: [{ title: "Strong review" }],
};

// The deep tier of the tiered review loop (wiki: decisions/2026-11-13-tiered-review-loop).
// The fast loop catches obvious blockers; this pass is where accuracy lives. It
// reviews the INTEGRATED branch (what the user gets from `git diff origin/<branch>`),
// so it sees cross-task issues no per-task reviewer can — the l7j epic's real
// blockers surfaced exactly here, after every per-task pass had waved them through.
//
// mode "wave": one correctness-domain reviewer on `since..HEAD` (since = the SHA
//   recorded as the last strong pass, or the epic BASE). Focuses on the delta;
//   earlier waves' settled ground is not re-litigated. Runs pipelined with the
//   next wave (background: true): findings are not urgent — the fast loop already
//   gated obvious bugs — EXCEPT critical, which preempts the candidate queue.
// mode "epic": all four reviewers over `base..HEAD` — the final gate before the
//   audit. Run it with background: false and fix what it finds before auditing.
//
// args: { integrationPath, mode: "wave"|"epic", since, base }
//   integrationPath: the repo checkout on the working branch (absolute).
//   since (wave): last strong-pass SHA, or the epic BASE for the first pass.
//   base (epic): the epic's BASE SHA.

const DEEP_TIER = "deep-reviewer";
const REVIEWERS = ["correctness-reviewer", "failure-path-reviewer", "readability-reviewer", "security-reviewer"];
const verdictSchema = {
  type: "object",
  properties: {
    verdict: { type: "string", enum: ["LGTM", "FINDINGS"] },
    findings: {
      type: "array",
      items: {
        type: "object",
        properties: {
          severity: { type: "string", enum: ["critical", "important", "suggestion"] },
          file: { type: "string" },
          description: { type: "string" },
        },
        required: ["severity", "description"],
      },
    },
  },
  required: ["verdict", "findings"],
};

const path = String(args?.integrationPath || "");
if (!path) throw new Error("strong-pass.js: args.integrationPath is empty");
const mode = args?.mode === "epic" ? "epic" : "wave";
if (mode === "wave" && !args?.since) throw new Error("strong-pass.js: wave mode needs args.since (last strong SHA or BASE)");
if (mode === "epic" && !args?.base) throw new Error("strong-pass.js: epic mode needs args.base (the epic BASE)");

const range = mode === "epic" ? `${args.base}..HEAD` : `${args.since}..HEAD`;

const prompt =
  mode === "epic"
    ? `Deep review of a whole epic's integration branch.\n\nRepo: ${path}\nRange: \`git diff ${args.base}..HEAD\` in your working directory.\n` +
      `Judge the integrated result: does it hold together, do the parts agree, did anything land that contradicts the rest?\n` +
      `Ignore pre-existing issues outside the range. This is the final gate before the audit — be thorough in your own domain.`
    : `Deep review of the delta since the last strong pass.\n\nRepo: ${path}\nRange: \`git diff ${args.since}..HEAD\` in your working directory.\n` +
      `Focus on this delta and on how it interacts with what landed before it; earlier waves' ground was already strong-passed — do not re-litigate it.\n` +
      `Cross-task consistency, integration seams, and anything the per-task fast reviewers could not see are exactly yours.`;

const runOne = (reviewer) =>
  agent(prompt, {
    agentType: reviewer,
    cwd: path,
    tier: DEEP_TIER,
    schema: verdictSchema,
    phase: "Strong review",
    label: `${reviewer}:strong:${mode}:${range}`,
  }).catch(() => null);

const reviewers = mode === "epic" ? REVIEWERS : ["correctness-reviewer"];
const results = await parallel(reviewers.map((r) => () => runOne(r)));

const findings = [];
const missing = [];
for (let i = 0; i < reviewers.length; i++) {
  const result = results[i] ?? (await runOne(reviewers[i])); // one re-run for a reviewer whose output never validated
  if (result === null) missing.push(reviewers[i]);
  else for (const f of result.findings) findings.push({ ...f, reviewer: reviewers[i] });
}

return {
  mode,
  range,
  missing,
  findings,
  blocking: findings.filter((f) => f.severity !== "suggestion"),
};
