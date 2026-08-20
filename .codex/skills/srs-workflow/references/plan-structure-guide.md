# Plan Structure Guide

Reference for Phase 4 — Plan Writing.
Defines what each plan file must contain. These are blueprints: unambiguous, complete,
no word limit. Each file answers the question "What exactly will the SRS section say?"

---

## File Map

```
projects/{slug}/plan/
  00-overview.md
  01-introduction.md
  02-overall-description.md
  03-01-external-interfaces.md
  03-02-functional-requirements.md
  03-03-performance.md
  03-04-database.md
  03-05-design-constraints.md
  03-06-system-attributes.md
  03-07-other-requirements.md
  appendix-a-glossary.md
  appendix-b-open-issues.md
```

---

## 00-overview.md

**Purpose:** Master map of the entire planned SRS. Not itself a section — it's the reader's guide.

**Must contain:**
- Project name, version, date, primary author
- System one-liner (≤ 2 sentences)
- Complete FR count by priority (Essential / Conditional / Optional)
- Complete NFR count by ISO/IEC 25010 characteristic
- Section file list with planned word-count estimate for each
- List of ALL actors (table: name | type | description)
- List of ALL external interfaces (table: system | protocol | direction)
- Key assumptions made during planning (numbered)
- Open items that must be resolved before SRS generation (use [NEEDS USER INPUT: {what}])

---

## 01-introduction.md

**Purpose:** Plan for SRS §1 (Purpose, Scope, Definitions, References, Overview).

**Must contain:**

§1.1 Purpose
- Who will read this SRS? List every audience role.
- What decisions will this SRS enable? (dev team estimates | QA test planning | stakeholder sign-off)

§1.2 Scope
- System name (planned)
- One-paragraph system description — what it does, for whom, why
- IN scope table: every feature/capability that will be in this release
- OUT scope table: every capability explicitly excluded (with reason)
- Adjacent systems that interact but are out of scope

§1.3 Definitions / Acronyms / Abbreviations
- List every term from brainstorm that needs a precise definition
- Format: Term | Definition | Source (domain standard / project-specific)
- Flag any term still needing user clarification: [NEEDS USER INPUT: definition of "{term}"]

§1.4 References
- List applicable standards: IEEE 830-1998, ISO/IEC 25010, domain regulations (HIPAA, GDPR, PCI-DSS...)
- List source documents provided by user during brainstorm
- List any external API specs, style guides, legacy system docs

§1.5 Overview
- How the SRS is organized (section summary)
- How to read it (audience routing: devs → §3, QA → §3 + Appendix B, PMs → §1–§2)

---

## 02-overall-description.md

**Purpose:** Plan for SRS §2 (Product Perspective, Functions, User Characteristics, Constraints, Assumptions).

**Must contain:**

§2.1 Product Perspective
- Is this a new standalone system, replacement, or component of larger system?
- System context diagram description (draw a text diagram with ASCII boxes if helpful)
- All external interfaces listed (expand in 03-01)
- How this system fits into the user's existing ecosystem

§2.2 Product Functions
- High-level function list (not detailed FRs yet — those are in 03-02)
- Organized by functional area / feature cluster
- Each function: 1-sentence description + which actors use it

§2.3 User Characteristics
- One profile per actor type confirmed in brainstorm
- Each profile: name | technical proficiency | domain knowledge | frequency of use | device/channel | accessibility needs
- Persona summary (3–5 sentences per actor)

§2.4 Constraints
- Regulatory / legal: list each requirement and its source regulation
- Hardware: target devices, minimum specs
- Software interfaces: mandatory tech stack items confirmed in brainstorm
- Security: auth requirements, encryption standards
- Timeline / budget: if confirmed (even rough)

§2.5 Assumptions and Dependencies
- Every assumption made during planning (numbered, each can invalidate scope if wrong)
- External dependencies: third-party APIs, shared services, other teams' deliverables
- For each dependency: risk if it changes or is unavailable

§2.6 Apportioning of Requirements
- Features planned for future versions (deferred)
- Reason for deferral (out of scope by user choice | technical dependency | compliance not yet ready)

---

## 03-01-external-interfaces.md

**Purpose:** Plan for SRS §3.1 (User Interfaces, Hardware Interfaces, Software Interfaces, Communication Interfaces).

**Must contain:**

§3.1.1 User Interfaces
- Every screen/view/page planned
- For each: name | description | primary user | key actions available | navigation flow
- UI constraints: responsive (breakpoints?) | WCAG level | supported browsers/OS

§3.1.2 Hardware Interfaces
- Any hardware devices the system must interface with
- (If none: state "None required" — do not skip)

§3.1.3 Software Interfaces
- Table: System | Version/Protocol | Direction | Data exchanged | Auth method | Error handling
- For each integration confirmed in brainstorm
- Specify: REST/GraphQL/gRPC | sync/async | rate limits | SLA of external system

§3.1.4 Communication Interfaces
- Network protocols (HTTPS, WebSocket, AMQP, etc.)
- Email/SMS gateway
- Push notification provider
- Data formats (JSON, XML, CSV, PDF)

---

## 03-02-functional-requirements.md

**Purpose:** Plan for SRS §3.2 — the largest section. Plan every FR.

**Must contain:**

For each feature cluster from brainstorm:

### Feature Cluster: {name}

**Planned FRs:**

| FR-ID | Priority | Actor | Shall-Stub | GWT stub |
|-------|----------|-------|-----------|----------|
| FR-01 | Essential | Customer | The system shall authenticate users via email+password | Given: valid credentials / When: POST /auth/login / Then: JWT returned |
| FR-02 | Essential | Customer | The system shall reject authentication after 5 failed attempts | Given: 5th failed attempt / When: next attempt / Then: account locked 15 min |

Rules:
- Number sequentially across ALL clusters — no resets per cluster
- Mark each Essential | Conditional | Optional (IEEE 830 §4.3.5)
- Shall stubs must be testable: "The system shall X" — not "The system should X" or "The system might X"
- Tag items needing input: [NEEDS USER INPUT: confirm max session duration]
- At the end: total FR count breakdown (Essential: N | Conditional: N | Optional: N)

---

## 03-03-performance.md

**Purpose:** Plan for SRS §3.3 — performance requirements.

**Must contain:**

For each NFR confirmed in brainstorm Round 4:

| NFR-ID | Characteristic (ISO 25010) | Quality Attribute Scenario |
|--------|--------------------------|---------------------------|
| NFR-01 | Time Behaviour | Stimulus: 1,000 concurrent users submit checkout / Response: order confirmation returned / Measure: ≤ 2s at 95th percentile |

Every NFR must have a numeric Response Measure. If brainstorm confirmed [TBD]:
- Write: `[TBD: {what data is needed to set this target} | owner: {who decides} | resolve-by: {milestone}]`

Categories to plan:
- Response time per key operation
- Throughput (transactions/minute or concurrent users)
- Availability / uptime SLA
- Data capacity (records, file sizes, growth rate)
- Scalability model (horizontal? auto-scale trigger?)

---

## 03-04-database.md

**Purpose:** Plan for SRS §3.4 — logical database requirements.

**Must contain:**

- Entity list: every data entity confirmed in brainstorm (table: name | description | key attributes | relationships)
- Data retention: per entity (user data | transaction records | audit logs | media files)
- Data volume projections: launch | 6 months | 12 months
- Backup frequency and recovery targets (RPO/RTO from NFR round)
- PII / sensitive data fields: what is encrypted at rest, what is masked in logs
- Multi-tenancy model (if applicable): how data is isolated between tenants

---

## 03-05-design-constraints.md

**Purpose:** Plan for SRS §3.5 — imposed design constraints.

**Must contain:**

- Tech stack constraints confirmed in brainstorm (language, framework, cloud provider)
- Existing systems the design MUST integrate with (no choice)
- Coding standards / style guides mandated by the organization
- Compliance-driven constraints (e.g., "must use approved encryption algorithms only")
- Infrastructure constraints (e.g., "must deploy on-premise to hospital network")
- Budget constraints (e.g., "no paid third-party services > $X/month")

---

## 03-06-system-attributes.md

**Purpose:** Plan for SRS §3.6 — quality attributes (IEEE 830 §4.3 / ISO/IEC 25010).

**Must contain (one plan entry per characteristic):**

- **Reliability:** MTBF target, failure behavior (graceful degradation | full failover | manual recovery)
- **Availability:** uptime SLA, maintenance window, multi-region / active-active or active-passive
- **Security:** auth model, encryption (at rest / in transit), vulnerability scanning, pen-test schedule, secrets management
- **Maintainability:** code coverage requirement, deployment pipeline (CI/CD), branching strategy, dependency update policy
- **Portability:** supported platforms, containerization (Docker/K8s), data export formats
- **Usability:** WCAG level, screen reader support, max task-completion steps, onboarding requirements

---

## 03-07-other-requirements.md

**Purpose:** Plan for SRS §3.7 — catch-all for requirements not fitting §3.1–§3.6.

**Must contain (if applicable — write "None" if not applicable):**

- Localization / i18n: languages, RTL support, date/number/currency formats, timezone handling
- Legal / regulatory: specific clauses (e.g., "must display cookie consent per GDPR Art. 7")
- Operational: monitoring/alerting requirements, on-call SLA, runbook links
- Transition: data migration from existing system, cutover strategy, rollback plan
- Training: user training materials, admin docs, developer API docs

---

## appendix-a-glossary.md

**Purpose:** Plan for Appendix A — glossary.

**Must contain:**

- Every domain term used in the SRS that could be misunderstood
- Format: Term | Definition | Related terms | Source
- Include acronyms
- Flag terms still needing definition: [NEEDS USER INPUT: definition of "{term}"]

---

## appendix-b-open-issues.md

**Purpose:** Plan for Appendix B — tracked open issues and TBDs.

**Must contain:**

| ID | Description | Owner | Priority | Resolve-by |
|----|-------------|-------|---------|-----------|
| TBD-01 | NFR-03 Response Measure not confirmed | Product Owner | P1 | Sprint 1 |

This table is the canonical tracking list. Every [NEEDS USER INPUT] from other plan files
must be entered here with an owner and resolve-by date.

---

## Quality Check Before Phase 5

After writing all plan files, verify:

1. FR-IDs are sequential across ALL plan files (no duplicates, no gaps)
2. Every actor mentioned in brainstorm appears in at least one FR
3. Every confirmed feature has at least one FR
4. Every NFR has either a numeric measure or a [TBD] entry in appendix-b
5. appendix-b-open-issues lists every [NEEDS USER INPUT] from all plan files
6. 00-overview.md FR/NFR counts match the actual counts in plan files
