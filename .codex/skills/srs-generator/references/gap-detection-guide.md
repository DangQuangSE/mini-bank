# Gap Detection Guide
*Consumed by Step 2 (Gap Scan) of `srs-generator`*

Every gap the skill flags must match one of the 7 patterns below.
Output format per detected gap:
```
[P{1|2|3}] Pattern {N} — {type label}: "{verbatim fragment or description of what is absent}"
```

---

## Tag Reference

| Tag | Meaning | Where it appears in SRS |
|-----|---------|------------------------|
| `[CONTEXT-GAP: {desc}]` | Information absent from input | §1–§3, Appendix B |
| `[GLOSSARY-GAP: {term}]` | Domain term undefined | §1.3 reference, Appendix A |
| `[VERIFIABILITY-FAIL: {FR-NN}]` | FR outcome not externally observable | §3.2, Appendix B |
| `[TBD: {condition} \| owner: {role} \| resolve-by: {date}]` | Deferred — must resolve before approval | Any §3 NFR |

---

## Pattern 1: Vague Quantifiers

**Definition:** A non-numeric scalar adjective or adverb applied to a measurable property.

**Trigger vocabulary:** many, few, some, large, small, fast, slow, soon, quickly, appropriate, good, high, low, reasonable, sufficient, minimal, significant, several, numerous.

**Examples:**
- "The system must respond quickly" → `[P3] Pattern 1 — Vague Quantifier: "quickly" — no numeric threshold for response time`
- "We need high availability" → `[P2] Pattern 1 — Vague Quantifier: "high availability" — no percentage or MTBF target stated`

**Priority:** P3 default. Escalates to P2 if the vague term is the only success criterion for a core feature.

---

## Pattern 2: Weak Modality Verbs

**Definition:** Modal verbs expressing possibility or desirability rather than obligation.

**Trigger vocabulary:** should, might, could, may, can (in permission sense within a requirement).
Distinguish from: `shall`, `must` — these are unambiguous obligations per IEEE 830.

**Examples:**
- "Users should be able to export reports" → `[P2] Pattern 2 — Weak Modality: "should" on core feature — is export required or optional?`
- "The dashboard could display analytics" → `[P3] Pattern 2 — Weak Modality: "could" — treat as Conditional/Optional feature`

**Priority:** P2 default. Escalates to P1 if "should" appears on a stated core feature (renders it unimplementably ambiguous per IEEE 830 §4.3.2).

---

## Pattern 3: Undefined Actors

**Definition:** A role label in a requirement with no prior definition, or a pronoun without a clear antecedent role.

**Trigger signals:** "the user" (undefined persona), "they", "it" (system reference), "admin" (no access level), "customer" (multi-persona system), "the system" (when multiple systems are in scope).

**Examples:**
- "It should send a confirmation email" → `[P1] Pattern 3 — Undefined Actor: "It" — unclear which system/component sends the email`
- "Admin can approve orders" → `[P2] Pattern 3 — Undefined Actor: "Admin" — shop admin, platform admin, or both?`

**Priority:** P1 for primary actor ambiguity (core flows untestable). P2 for secondary actor ambiguity.
**Action:** every undefined actor also triggers `[GLOSSARY-GAP: {actor}]` during Step 1 extraction.

---

## Pattern 4: Anaphoric References

**Definition:** A pronoun or demonstrative whose referent is ambiguous when multiple entities of the same type are in scope. Distinct from Pattern 3 — here the actor is named but a later pronoun is unclear.

**Trigger signals:** "this", "that", "these", "it", "they", "the former", "the latter", "same", "the above".

**Example:**
- "The manager approves the invoice; the supplier reviews it and the accountant signs it."
  → `[P2] Pattern 4 — Anaphoric Reference: both "it" instances could refer to the invoice or the approval record`

**Priority:** P2 default. Escalates to P1 if the ambiguous pronoun appears in a transaction, data-flow, ownership, or deletion statement.

---

## Pattern 5: Coordination Ambiguity

**Definition:** Compound noun phrases or conditions joined by "and"/"or" where logical grouping is unclear.

**Classic forms:**
- "A and B or C" — does "or" apply only to B and C, or to the whole phrase?
- "admins and users with permission" — do users need permission, or just admins?
- "create, edit, or delete reports and logs" — does delete apply to both?

**Example:**
- "Managers and users with read access can export reports and invoices."
  Interpretation A: (managers) and (users with read access) can export (reports) and (invoices).
  Interpretation B: (managers) and (users) with read access can export (reports) and (invoices).
  → `[P2] Pattern 5 — Coordination Ambiguity: "managers and users with read access" — permission scope unclear`

**Priority:** P2 default. Escalates to P1 if the ambiguity is in an authorization, permission, or deletion rule.

---

## Pattern 6: Missing Constraints

**Definition:** The complete absence of a required constraint class — not a vague statement of one. Check all five sub-categories:

| Sub-category | What to look for | Priority if absent |
|-------------|------------------|--------------------|
| Error handling | No stated behavior on failure, timeout, or invalid input for a feature | P1 for core transactions |
| Concurrency / volume | No maximum concurrent users, TPS, or data volume | P2 |
| Permissions / roles | Feature exists but no role authorized to perform it (or unauthorized role not denied) | P1 for any CUD operation |
| Rollback / undo | Destructive operation (delete, publish, payment) with no rollback or confirmation requirement | P1 |
| Non-functional baseline | No performance, security, or availability targets anywhere in the document | P2 |

**Examples:**
- No error behavior for failed payment → `[P1] Pattern 6 — Missing Constraint: no error handling for payment failure`
- No concurrent user limit stated → `[P2] Pattern 6 — Missing Constraint: no concurrency/volume target`

---

## Pattern 7: Contradictions

**Definition:** Two or more statements that cannot both be true, or that impose mutually exclusive conditions on the same feature.

**Common forms:**
- Feature is "required" in one sentence and "out of scope" in another
- A role is both granted and denied the same permission
- A performance target conflicts with a stated hardware constraint

**Example:**
- "The system must support 10,000 concurrent users." + "The server will be a single shared VM with 2GB RAM."
  → `[P1] Pattern 7 — Contradiction: concurrent user target (10,000) is incompatible with stated hardware (single 2GB VM)`

**Detection instruction:** Compare all extracted FR statements against each other AND against stated constraints for logical incompatibility. Do not rely solely on trigger word scanning.

**Priority:** P1 if the contradiction involves a core feature, actor permission, or data integrity rule. P2 if it is between a primary and a secondary feature (one may simply be out of scope).

---

## Priority Classification Reference

| Priority | Condition | Action |
|----------|-----------|--------|
| **P1** | Gap makes a requirement unimplementable or untestable | Resolve in Round 1 before any SRS section is written. Block generation if unresolvable. |
| **P2** | Gap creates scope risk but a reasonable default could be assumed | Resolve in Round 2. If unanswered: document assumed default in SRS and Appendix B. |
| **P3** | Gap is deferrable; implementation team can make autonomous call | Offer in Round 3. If skipped: mark `[TBD: {condition} \| owner: {role} \| resolve-by: sprint planning]`. |

---

## IEEE 830 Quality Attribute Checklist

Run this checklist after SRS generation to determine the compliance verdict. Each failing check produces a tag.

| Attribute (IEEE 830 §4.3) | What to verify in the generated SRS | Tag if failing |
|--------------------------|-------------------------------------|----------------|
| **Correct** | Each FR has `[Source: {input location}]` tracing to user-provided content | `[CONTEXT-GAP: FR-NN has no source]` |
| **Unambiguous** | No vague modifiers remain in any FR/NFR statement; exactly one interpretation possible | Pattern 1 or 2 flag |
| **Complete** | All actors have ≥1 FR; all FRs have Actor + Precondition + GWT; §1.2 IN/OUT table populated | `[CONTEXT-GAP: {what is missing}]` |
| **Consistent** | No two FRs contradict; terminology uniform across entire document | Pattern 7 flag |
| **Ranked** | Every FR carries Essential / Conditional / Optional tag | `[CONTEXT-GAP: FR-NN ranking missing]` |
| **Verifiable** | Every NFR has numeric Response Measure; every FR "Then" is externally observable | `[VERIFIABILITY-FAIL: FR-NN]` |
| **Modifiable** | Each requirement is a single atomic "shall" statement; no redundancy between FRs | Structural note (no tag) |
| **Traceable** | Each FR has a unique FR-NN ID; Appendix B links open gaps to their SRS section | Structural note (no tag) |

**Verdict rules:**
- **COMPLIANT** — all 8 checks pass; Appendix B is empty or all items Resolved
- **PARTIALLY COMPLIANT** — all required sections present but Appendix B has open items
- **NON-COMPLIANT** — required sections missing or pervasive failures across ≥3 attributes

---

## Worked Example

**Sample input (realistic client email):**

> Hi team, we're building an internal invoicing tool for our finance department. Managers should be able to create and send invoices to clients, and clients can view and download them. The system needs to be fast and support many users at the same time. Admins can manage user accounts. We also want notifications when an invoice is approved — the system should send them automatically. We don't need mobile support for now. It should integrate with our existing accounting software. Data needs to be kept safe, and we'll need an audit log for compliance purposes.

**Gap scan output:**

| # | Priority | Pattern | Verbatim fragment / missing element |
|---|----------|---------|-------------------------------------|
| 1 | P2 | Pattern 2 — Weak Modality | "should be able to create" — is invoice creation Essential or Conditional? |
| 2 | P3 | Pattern 1 — Vague Quantifier | "fast" — no numeric response time target |
| 3 | P3 | Pattern 1 — Vague Quantifier | "many users at the same time" — no concurrent user count |
| 4 | P2 | Pattern 3 — Undefined Actor | "Admins" — no definition of admin role vs. manager role; overlap unclear |
| 5 | P2 | Pattern 4 — Anaphoric Reference | "the system should send them automatically" — "them" could refer to invoices or notifications |
| 6 | P1 | Pattern 6 — Missing Constraint (Permissions) | "clients can view and download" — no role auth defined; no restriction stated for non-clients |
| 7 | P2 | Pattern 6 — Missing Constraint (Rollback) | no rollback stated for sent invoices — can a sent invoice be recalled? |
| 8 | P1 | Pattern 6 — Missing Constraint (Error handling) | no failure behavior stated for accounting software integration |

**Patterns detected:** 4 distinct types (Pattern 1, 2, 3, 4, 6) — exceeds minimum of 4 for COMPLIANT gap scan.
