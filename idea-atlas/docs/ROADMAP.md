# Roadmap

Nationwide architecture exists from the first schema. Every phase below is about
**filling** that architecture, not extending it to new jurisdictions.

Status legend: ✅ done · 🟡 partial · ⬜ not started

---

## Phase 0 — Foundation ✅ complete

- ✅ Repository, tooling, CI, Docker
- ✅ Full relational schema, migrations verified to round-trip
- ✅ 70 jurisdictions, 43 IDEA concepts
- ✅ SSRF-hardened ingestion pipeline with hashing and change detection
- ✅ REST API including deterministic `/v1/research`
- ✅ CLI, seeding, coverage reporting
- ✅ Replaceable AI abstraction with a working no-AI default
- ✅ 274 tests, 95% coverage, strict typing
- ✅ Security, threat model, and legal data policy documented

---

## Phase 1 — Federal completeness and the nationwide source registry 🟡

**Goal:** every IDEA jurisdiction has verified official source URLs, and federal
statutes, regulations, and procedural safeguards are ingested nationwide.

This is the phase that turns the foundation into a product.

### 1.1 Federal source verification ⬜
- Verify all 13 federal source URLs (`idea-atlas verify-sources --live`)
- Set `url_verified` per source; correct the stale ones
- Confirm terms of service and copyright posture per source

### 1.2 Federal regulation ingestion ⬜
- eCFR collector for 34 C.F.R. parts 300 and 303 (section-level)
- Effective dates from the versioner API into `AuthorityVersion.effective_from`
- Backfill historical versions so point-in-time queries work
- Federal Register collector as the change trigger for re-crawls

### 1.3 Federal statute ingestion ⬜
- OLRC / GovInfo collector for 20 U.S.C. ch. 33
- Link statute sections to their implementing regulations via
  `AuthorityRelationship(implements)`

### 1.4 Jurisdiction source registry ⬜
- Verify official URLs for all 57 grantee jurisdictions (8 categories each)
- Priority order in [`JURISDICTIONS.md`](JURISDICTIONS.md)
- Resolve the open questions there: American Samoa's circuit, BIE Part C, the
  Freely Associated States, all 50 circuit assignments

### 1.5 State statutes, regulations, and procedural safeguards ⬜
- Generic state collector driven by manifests
- Procedural safeguards notices nationwide — highest practical value per
  document for parents
- Target: 10 states fully ingested before generalizing further

### 1.6 First human review pass ⬜
- Review the seeded propositions against ingested primary text
- Promote to `source_verified` / `human_reviewed` with real `ReviewEvent` rows
- **This is when `/v1/research` starts returning real answers**

**Exit criteria:** federal Part B and Part C regulations ingested and reviewed;
57 jurisdictions with verified source URLs; 10 states with statutes and
procedural safeguards ingested; `/v1/research` answers federal questions with
`sufficient_coverage: true`.

---

## Phase 2 — SEA guidance, decisions, and federal case law ⬜

- SEA guidance document collectors
- State complaint decision ingestion where states publish archives
- Due process decision ingestion, with a redaction policy for
  student-identifying information (see the open question in
  [`LEGAL_DATA_POLICY.md`](LEGAL_DATA_POLICY.md))
- Supreme Court IDEA precedent, with verified citations
- Circuit court IDEA opinions via GovInfo USCOURTS, scoped to the circuit
  jurisdictions already in the schema
- Coverage gap tracking: record where a state publishes nothing, so absence is
  documented rather than inferred

**Exit criteria:** decisions ingested for the 10 highest-volume states; SCOTUS
IDEA precedent complete and reviewed; circuit precedent scoped correctly.

---

## Phase 3 — The proposition graph and review workflow ⬜

- AI-assisted proposition extraction (any provider) writing `ai_extracted`
  candidates with verbatim supporting quotes
- **Human review workflow** — the bottleneck that determines everything:
  - diff review UI showing exactly what changed in an amended authority (closes
    threat T2)
  - proposition review queue with the source text side by side
  - reviewer attribution and expert-reviewer roles
- Authority relationship graph: citator-style `interprets`, `supersedes`,
  `overrules`, `distinguishes`
- Automated change detection scheduling with alerting on material change
- Cross-validation: corroborate a proposition against a second independent
  source to reach `cross_validated`
- Postgres full-text search; pgvector only if measurement shows keyword search
  is actually insufficient

**Exit criteria:** propositions exist for every concept in the federal baseline
and in 10+ states, at `human_reviewed` or better; change detection runs on a
schedule and alerts.

---

## Phase 4 — Machine access and productization ⬜

- **MCP server** exposing research, jurisdiction, and authority tools, so agents
  can query the graph natively
- API keys, scopes, and per-key quotas against the existing `Principal` seam
- Usage metering and billing-grade token counting
- Rate limiting at the edge (closes threat T6)
- Separate database roles for API and ingestion (grants already designed in
  [`SECURITY.md`](SECURITY.md))
- Ingestion worker egress policy (closes threat T1 — the top residual risk)
- Published benchmark results per [`TOKEN_EFFICIENCY.md`](TOKEN_EFFICIENCY.md)
- Professional research UI for attorneys and advocates

**Exit criteria:** an agent can answer a jurisdiction-scoped IDEA question
through MCP with citations; paid access is metered and rate-limited.

---

## Phase 5 — Parent-facing tools and private workspace ⬜

Gated on legal review, not just engineering.

- Parent-facing interface in plain language, with the information/advice
  boundary designed with counsel
- Attorney and advocate tooling: timeline calculators, deadline tracking,
  citation export
- **Optional private document workspace** — separately architected:
  - separate database or schema with per-tenant encryption
  - FERPA-aware access control and retention policy
  - no mixing of private documents with the public knowledge graph
  - its own threat model and security review
- UPL analysis per state before any advice-shaped feature ships

**Exit criteria:** counsel sign-off on the information/advice boundary; private
workspace passes an independent security review.

---

## What would make this fail

Recorded so it stays visible:

1. **Review capacity, not ingestion capacity, is the bottleneck.** Ingesting
   50,000 documents is a weekend. Reviewing 50,000 propositions is a career. The
   review workflow in phase 3 matters more than any collector.
2. **State source churn.** SEA sites reorganize constantly. Without change
   detection running on a schedule, the registry rots within a year.
3. **Scope creep into advice.** The pull toward "just tell parents what to do"
   is strong and is where the legal exposure lives.
4. **Trusting the model.** Every shortcut that lets `ai_extracted` content reach
   users as verified destroys the thing that makes this worth building.
