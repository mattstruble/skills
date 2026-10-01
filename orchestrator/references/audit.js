export const meta = {
  name: "orchestrator_audit",
  description: "Audit an epic's integration branch: each ticket's acceptance criteria, then the whole diff against the plan",
  phases: [{ title: "Tickets" }, { title: "Epic" }],
};

// args: { integrationPath, base, tickets: [{ id, title, acceptance, verify }], epic: { id, description, planPath } }
const { integrationPath, base, tickets = [], epic } = args ?? {};
if (!integrationPath || !base || !epic) throw new Error("audit.js: integrationPath, base and epic are required");

const ticketSchema = {
  type: "object",
  properties: {
    verdict: { type: "string", enum: ["met", "not-met"] },
    evidence: { type: "string" },
  },
  required: ["verdict", "evidence"],
};
const gap = { type: "object", properties: { item: { type: "string" }, evidence: { type: "string" } }, required: ["item", "evidence"] };
const epicSchema = {
  type: "object",
  properties: {
    missing: { type: "array", items: gap },
    outOfScope: { type: "array", items: gap },
    contradicted: { type: "array", items: gap },
  },
  required: ["missing", "outOfScope", "contradicted"],
};

phase("Tickets");
const ticketResults = await parallel(
  tickets.map((t) => () =>
    agent(
      [
        `Ticket ${t.id}: ${t.title}`,
        `Integration branch is checked out in your working directory; base is ${base}.`,
        `Acceptance criteria:\n${t.acceptance}`,
        t.verify ? `Verification command: ${t.verify}` : "Verification command: (none given)",
      ].join("\n\n"),
      { agentType: "ticket-auditor", cwd: integrationPath, tier: "medium", schema: ticketSchema, label: `ticket-audit:${t.id}` },
    ).catch(() => null),
  ),
);

phase("Epic");
const epicResult = await agent(
  [
    `Epic ${epic.id}. Audit \`git log --stat ${base}..HEAD\` and \`git diff ${base}..HEAD\` in your working directory against the plan.`,
    `Epic description:\n${epic.description}`,
    epic.planPath ? `Plan document: ${epic.planPath}` : "No plan document is linked; audit against the epic description and tickets only.",
    `Tickets:\n${tickets.map((t) => `- ${t.id}: ${t.title}`).join("\n")}`,
  ].join("\n\n"),
  { agentType: "epic-auditor", cwd: integrationPath, tier: "big", schema: epicSchema, label: `epic-audit:${epic.id}` },
).catch(() => null);

// null = the auditor produced no verdict: missing coverage, never a negative finding.
return {
  tickets: tickets.map((t, i) => ({ ticketId: t.id, ...(ticketResults[i] ?? { verdict: "unknown", evidence: "auditor returned no verdict" }) })),
  epic: epicResult ?? null,
};
