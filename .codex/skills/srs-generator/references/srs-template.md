# Software Requirements Specification
*IEEE 830-1998 Compliant*

| Field | Value |
|-------|-------|
| Project | {project name} |
| Version | v0.1 — Draft |
| Date | {YYYY-MM-DD} |
| Prepared by | {author / role} |
| Status | Draft |

> **Notation:** "shall" = mandatory obligation. "should" = desirable but optional.
> Quality attributes follow ISO/IEC 25010. NFR metrics follow ISO/IEC 25023 Quality Attribute Scenarios.

---

## 1. Introduction

### 1.1 Purpose
{Who this document is for (dev team, QA, stakeholders) and what system it specifies. 1–2 sentences.}

### 1.2 Scope

**System name:** {name}

{One paragraph describing what the product does and its primary goal.}

**In / Out of Scope:**

| Feature Area | In Scope | Out of Scope |
|--------------|----------|--------------|
| {area 1} | ✓ | |
| {area 2} | | ✓ |

> `[CONTEXT-GAP: out-of-scope boundary not defined]` if table cannot be populated from input.
> Every feature area in §3.2 must appear in this table.

### 1.3 Definitions, Acronyms, and Abbreviations
See Appendix A for full glossary. Standard abbreviations used in this document:

| Abbreviation | Definition |
|-------------|------------|
| SRS | Software Requirements Specification |
| FR | Functional Requirement |
| NFR | Non-Functional Requirement |
| GWT | Given / When / Then |
| TBD | To Be Determined |

### 1.4 References
| # | Document | Type | Date |
|---|----------|------|------|
| 1 | {raw input document title or description} | Source input | {date} |
| 2 | IEEE 830-1998 | Standard | 1998 |
| 3 | ISO/IEC 25010:2011 | Quality model | 2011 |
| 4 | ISO/IEC 25023:2016 | Quality measures | 2016 |

### 1.5 Overview
Section 2 describes the overall product context, user characteristics, and constraints. Section 3 provides specific functional and non-functional requirements traceable to the source input. Appendix A contains the glossary; Appendix B lists open issues that must be resolved before development approval.

---

## 2. Overall Description

### 2.1 Product Perspective
{How the system fits into its larger context: standalone product, part of a suite, replacement for an existing system, or new capability. Include a context diagram or external system list if applicable.}

External systems / interfaces:
- {External system 1} — {relationship}
- {External system 2} — {relationship}

### 2.2 Product Functions
High-level summary of major capabilities (detail in §3.2):

- {Capability 1}
- {Capability 2}
- {Capability 3}

### 2.3 User Characteristics

| Actor | Technical Level | Access Rights | Notes |
|-------|----------------|---------------|-------|
| {actor 1} | {beginner / intermediate / expert} | {permissions} | |
| {actor 2} | | | |

> `[GLOSSARY-GAP: {actor}]` for any role lacking a formal definition.

### 2.4 Constraints
{Regulatory, technical, resource, and platform constraints extracted from input. Numbered list.}

1. {Constraint 1 — verbatim or paraphrased from input}
2. {Constraint 2}

> `[CONTEXT-GAP: no constraints identified]` if none found in input.

### 2.5 Assumptions and Dependencies
{Conditions that must be true for this spec to hold.}

1. {Assumption 1 — if wrong, this spec changes}
2. {Assumption 2 — third-party service, data migration, tech stack, etc.}

### 2.6 Apportioning of Requirements
*(Optional — IEEE 830 §5.2.6)* Features explicitly deferred to future releases:

- {Deferred feature 1} — reason for deferral
- If none: "No requirements are currently deferred."

---

## 3. Specific Requirements

### 3.1 External Interface Requirements

#### 3.1.1 User Interfaces
{Screen/page list, navigation constraints, accessibility standards (e.g., WCAG 2.1 AA).}

#### 3.1.2 Hardware Interfaces
{Device targets, sensors, peripherals.}
`[TBD: hardware interfaces not specified | owner: {role} | resolve-by: sprint planning]`

#### 3.1.3 Software Interfaces

| External System | Interface Type | Protocol | Auth Method | Notes |
|-----------------|---------------|----------|-------------|-------|
| {system 1} | REST API / SDK / DB | HTTPS / WebSocket | OAuth 2.0 / API Key | |

#### 3.1.4 Communication Interfaces
{Network protocols, data formats, encryption requirements.}

---

### 3.2 Functions (Functional Requirements)

<!-- SKILL: repeat the block below for each FR. One "shall" per block. Exactly one "When" per GWT. -->
<!-- Priority: Essential = MVP must-ship | Conditional = nice-to-have | Optional = future release -->

#### FR-01 [Essential]
**Requirement:** The system shall {verb} {object} when {condition}.
**Actor:** {role performing the action}
**Precondition:** {system state that must be true before this FR applies}
**Given:** {initial context / state}
**When:** {trigger or user action — exactly one}
**Then:** {externally observable outcome}
**Source:** [{verbatim location in input or clarification round}]

> ⚠️ If "Then" is not externally observable → tag `[VERIFIABILITY-FAIL: FR-01]` and add to Appendix B.

---

#### FR-02 [Essential]
**Requirement:** The system shall {verb} {object} when {condition}.
**Actor:** {role}
**Precondition:** {state}
**Given:** {context}
**When:** {trigger}
**Then:** {observable outcome}
**Source:** [{location}]

---

<!-- Continue FR-03, FR-04… in sequence. No gaps in numbering. -->

---

### 3.3 Performance Requirements

<!-- SKILL: one block per performance NFR. Response Measure must be numeric — no adjectives. -->

#### NFR-01 [Performance — ISO/IEC 25010: Time Behaviour]
| Attribute | Value |
|-----------|-------|
| Source | {who/what triggers the concern} |
| Stimulus | {event or load condition — e.g., "1,000 simultaneous users submitting forms"} |
| Environment | {normal / peak / degraded} |
| Artifact | {system component or endpoint} |
| Response | {how the system responds} |
| Response Measure | {numeric threshold — e.g., "p95 latency < 500 ms"} |

> ⚠️ Vague modifiers (fast, quick, responsive) not permitted.
> Unresolved: `[TBD: {condition} | owner: {role} | resolve-by: sprint planning]`

---

### 3.4 Logical Database Requirements
{Data entities, relationships, retention periods, access constraints.}

| Entity | Key Attributes | Relationships | Retention |
|--------|---------------|---------------|-----------|
| {Entity 1} | {id, name, …} | {belongs to Entity 2} | {N years} |

> `[TBD: database schema not specified | owner: tech lead | resolve-by: sprint planning]` if no database mentioned.

---

### 3.5 Design Constraints
{Mandatory standards compliance, enforced technology choices, hardware limitations from §2.4.}

1. {e.g., "System shall be implemented in {language/framework} per existing tech stack"}
2. {e.g., "All data at rest shall be encrypted using AES-256"}

---

### 3.6 Software System Attributes

<!-- One QA Scenario block per characteristic. ISO/IEC 25010 characteristics: -->
<!-- Reliability | Availability | Security | Maintainability | Portability -->

#### NFR-{NN} [Security — ISO/IEC 25010: Security]
| Attribute | Value |
|-----------|-------|
| Source | Unauthorized user |
| Stimulus | Attempt to access protected resource without valid credentials |
| Environment | Production |
| Artifact | Authentication layer |
| Response | System rejects request and logs the attempt |
| Response Measure | 100% of unauthorized requests rejected; audit log entry created within 500 ms |

> Include RBAC requirements if system has user roles. Reference OWASP Top 10 if web system.

#### NFR-{NN} [Availability — ISO/IEC 25010: Availability]
| Attribute | Value |
|-----------|-------|
| Source | End user |
| Stimulus | Access request during scheduled operating hours |
| Environment | Normal |
| Artifact | Full system |
| Response | System accepts and processes request |
| Response Measure | {e.g., "99.5% uptime measured monthly, excluding scheduled maintenance"} |

---

### 3.7 Other Requirements
{Internationalization, localization, legal, licensing, regulatory requirements.}

- If none: "No additional requirements identified at this time."

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| {domain term 1} | {one-sentence definition} |
| {domain term 2} | {one-sentence definition} |
| {domain term 3} | {one-sentence definition} |

> All `[GLOSSARY-GAP: {term}]` tags from §1–§3 must be resolved here before a COMPLIANT verdict is possible.

---

## Appendix B: Open Issues

| # | Section | Gap Type | Description | Priority | Status |
|---|---------|----------|-------------|----------|--------|
| 1 | §{N.N} | [CONTEXT-GAP / GLOSSARY-GAP / VERIFIABILITY-FAIL / TBD] | {description} | P{1/2/3} | Open |

> This appendix must be empty (or all items Resolved) before the document is approved for development.

---

## Revision History

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v0.1 | {YYYY-MM-DD} | {author} | Initial draft |
