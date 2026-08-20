# Brainstorm Question Guide

Reference for Phase 1 — Deep Brainstorm.
Use domain detection from Phase 0 to select the most relevant question banks.
Always present concrete answer options; never ask purely open-ended questions.

---

## Domain-Specific Question Banks

### E-commerce / Marketplace

**Actors**
- Who places orders? (B2C shoppers | B2B buyers | both | wholesale accounts)
- Who fulfills orders? (in-house warehouse | 3PL | dropship suppliers | mixed)
- Are there multiple seller/vendor roles? (single-vendor store | multi-vendor marketplace | hybrid)
- Admin sub-roles? (super admin | catalog manager | order ops | finance | CS support)
- External systems? (payment gateway | shipping carrier | ERP | CRM | tax service | review platform)

**Features**
- Product catalogue: simple products only | configurable (size/color) | bundles | subscriptions | digital downloads
- Pricing: fixed price | tiered | customer-group pricing | flash sale | coupon/promo engine | dynamic pricing
- Checkout: guest checkout | registered only | both | one-page | multi-step | buy-now
- Payments: card (Stripe/PayPal) | bank transfer | COD | crypto | BNPL | stored wallet
- Fulfillment: pick/pack/ship | click & collect | same-day | international shipping
- Returns & refunds: self-service portal | CS-assisted | partial refund | exchange
- Reviews: product reviews | seller ratings | verified purchase only | moderated

**Business rules to confirm**
- Can a product be in more than one category?
- Is inventory tracked per SKU / per warehouse / globally?
- What happens when stock hits zero — hide product, show OOS, backorder?
- Are taxes calculated by buyer location or seller location?
- How are split-cart orders handled (multi-vendor)?

---

### SaaS / Internal Tool

**Actors**
- End users: individual contributors | team leads | department heads | guests
- Billing/admin roles: org admin | billing owner | security officer
- External: SSO provider | webhook receiver | API consumers | audit/SIEM system

**Features**
- Auth: email+password | Google OAuth | Microsoft SSO | SAML 2.0 | MFA (TOTP/SMS/hardware key)
- Onboarding: invite-only | self-signup | invite + domain whitelist
- Workspace/team: single workspace | multi-workspace | organization hierarchy
- Permissions: RBAC (Role Based) | ABAC (Attribute Based) | resource-level ACL | public/private items
- Data model: flat records | hierarchical projects/tasks | relational (many-to-many)
- Integrations: Slack/Teams notifications | Zapier | REST API | webhooks | SSO | file storage (S3/GDrive)
- Billing: free tier | per-seat monthly | usage-based | annual contract | trial period
- Audit log: user actions only | system events | exportable | retention period

**Business rules**
- Can a user belong to multiple organizations?
- What happens to data when a subscription lapses?
- Who can invite new users — any member or admins only?
- Can permissions be delegated (user grants access to another user)?

---

### Healthcare / Medical

**Actors**
- Patients / end users: self-service portal | caregiver access | minor guardians
- Clinical staff: doctors | nurses | pharmacists | lab technicians | billing coders
- Admin: hospital admin | department head | IT/compliance officer
- External: HL7/FHIR EHR systems | insurance payers | lab systems | pharmacy systems

**Features**
- Appointments: scheduling | rescheduling | cancellation | reminders (SMS/email/push)
- Medical records: view only | edit with audit | version history | signed/locked entries
- Prescriptions: e-prescription | refill requests | drug interaction check
- Billing: insurance claim generation | patient invoicing | co-pay collection | ERA processing
- Telemedicine: video consult | chat | async messaging | file sharing during consult
- Lab results: viewing | flagging abnormal | auto-notify patient | ordering new tests
- Consent management: digital consent forms | signed records | withdrawal

**Compliance questions (always mandatory for healthcare)**
- Jurisdiction: US (HIPAA) | EU (GDPR + MDR) | Australia (Privacy Act) | multi-country
- PHI storage: on-premise | cloud with BAA | hybrid
- Audit trail: read access logged | write access logged | full chain of custody
- Data retention: 7 years | 10 years | patient-lifetime | jurisdiction-specific
- Break-glass access: emergency override? Who can invoke, and is it logged?

---

### Fintech / Banking

**Actors**
- Retail customers | business customers | relationship managers | compliance officers | auditors
- External: core banking system | payment network (Visa/Mastercard/ACH/SWIFT) | KYC provider | fraud engine

**Features**
- Accounts: savings | checking | multi-currency | sub-accounts / pots
- Transactions: transfers (internal/external) | recurring | scheduled | instant vs T+1 vs T+2
- Cards: virtual | physical | spending limits | freeze/unfreeze | PIN management
- KYC/AML: ID verification | document upload | liveness check | watchlist screening | ongoing monitoring
- Statements: monthly PDF | real-time balance | categorized spending | export CSV/XLSX
- Lending: credit score check | loan application | repayment schedule | early repayment
- Notifications: real-time push | email | SMS | in-app | configurable thresholds

**Compliance questions**
- Licensing jurisdiction (each adds requirements)
- PCI-DSS scope: card data stored/transmitted? Tokenization provider?
- Open Banking / PSD2: third-party access to accounts? Consent API?
- Transaction limits: daily/monthly/per-transfer caps — regulatory or product choice?

---

### Mobile App

**Actors**
- App users by platform: iOS | Android | both (native) | React Native / Flutter / PWA
- Backend roles: same as SaaS or domain-specific (see above)

**Features**
- Offline mode: none | read-only | full offline + sync | conflict resolution strategy
- Push notifications: transactional | marketing | silent/background | opt-in/opt-out
- Deep linking: universal links | custom scheme | branch.io
- Biometrics: Face ID / Touch ID for auth | for payments | disabled per org policy
- Camera/media: photo capture | video | QR/barcode scanner | AR features
- Location: not used | foreground only | background (always-on) | geofencing
- App stores: public App Store/Play Store | enterprise MDM distribution | TestFlight/Firebase beta

---

## Universal NFR Question Bank (Round 4)

Always ask these for every domain. Present numeric examples so user understands the scale.

| NFR Category | Question | Example options |
|---|---|---|
| Performance | Max acceptable response time for primary action | < 200ms | < 500ms | < 1s | [TBD] |
| Throughput | Expected concurrent users at peak | < 100 | 100–1,000 | 1,000–10,000 | > 10,000 |
| Availability | Uptime SLA | 99% (~87h/yr downtime) | 99.9% (~8.7h/yr) | 99.99% (~52min/yr) | [TBD] |
| Recoverability | Max data loss acceptable (RPO) | 0 (sync replica) | 1 min | 1 hour | 24 hours |
| Recoverability | Max recovery time after outage (RTO) | < 5 min | < 1 hour | < 4 hours | next business day |
| Security | Auth strength | Password only | MFA optional | MFA mandatory | Hardware key |
| Security | Data classification | Public | Internal | Confidential | Restricted |
| Scalability | Growth expectation in 12 months | < 2x users | 2–5x | 5–10x | > 10x |
| Compliance | Applicable regulations | None | GDPR | HIPAA | PCI-DSS | SOC2 | ISO 27001 |
| Localization | Languages needed at launch | English only | + Vietnamese | Multi-language (list) |

---

## Completeness Checklist (run after Round 5)

Before allowing Phase 2 to begin, confirm all boxes:

- [ ] Every actor has a name, description, and role scope
- [ ] Every actor's data access rights are defined
- [ ] Core features list has been confirmed (not just inferred)
- [ ] IN scope / OUT scope boundary is explicit
- [ ] At least one NFR has a numeric target per category (Performance / Availability / Security)
- [ ] At least one business rule per feature cluster is stated
- [ ] Compliance requirements are stated (even if "none applicable")
- [ ] Integration points listed (even if "no external integrations")

Any unchecked box = remaining round to complete. Do NOT proceed to Phase 2 with unchecked boxes.
