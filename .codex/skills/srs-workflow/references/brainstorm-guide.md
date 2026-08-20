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
- What happens when stock hits zero?
- Are taxes calculated by buyer location or seller location?
- How are split-cart orders handled?

---

### SaaS / Internal Tool

**Actors**
- End users: individual contributors | team leads | department heads | guests
- Billing/admin roles: org admin | billing owner | security officer
- External: SSO provider | webhook receiver | API consumers | audit/SIEM system

**Features**
- Auth: email+password | Google OAuth | Microsoft SSO | SAML 2.0 | MFA
- Onboarding: invite-only | self-signup | invite + domain whitelist
- Workspace/team: single workspace | multi-workspace | organization hierarchy
- Permissions: RBAC (Role Based) | ABAC (Attribute Based) | resource-level ACL
- Data model: flat records | hierarchical projects/tasks | relational
- Integrations: Slack/Teams | Zapier | REST API | webhooks | SSO | file storage
- Billing: free tier | per-seat monthly | usage-based | annual contract | trial
- Audit log: user actions | system events | exportable | retention period

**Business rules**
- Can a user belong to multiple organizations?
- What happens to data when a subscription lapses?
- Who can invite new users?
- Can permissions be delegated?

---

### Healthcare / Medical

**Actors**
- Patients / end users: self-service portal | caregiver access | minor guardians
- Clinical staff: doctors | nurses | pharmacists | lab technicians | billing coders
- Admin: hospital admin | department head | IT/compliance officer
- External: HL7/FHIR EHR systems | insurance payers | lab systems | pharmacy systems

**Features**
- Appointments: scheduling | rescheduling | cancellation | reminders
- Medical records: view only | edit with audit | version history
- Prescriptions: e-prescription | refill requests | drug interaction check
- Billing: insurance claim generation | patient invoicing | co-pay collection
- Telemedicine: video consult | chat | async messaging
- Lab results: viewing | flagging abnormal | auto-notify
- Consent management: digital consent forms | signed records

**Compliance questions (always mandatory for healthcare)**
- Jurisdiction: US (HIPAA) | EU (GDPR) | Australia (Privacy Act) | multi-country
- PHI storage: on-premise | cloud with BAA | hybrid
- Audit trail: read/write access logged
- Data retention: 7 years | 10 years | patient-lifetime
- Break-glass access: emergency override capability?

---

### Fintech / Banking

**Actors**
- Retail customers | business customers | relationship managers | compliance officers | auditors
- External: core banking system | payment network | KYC provider | fraud engine

**Features**
- Accounts: savings | checking | multi-currency | sub-accounts
- Transactions: transfers | recurring | scheduled | instant vs T+1 vs T+2
- Cards: virtual | physical | spending limits | PIN management
- KYC/AML: ID verification | document upload | liveness check | watchlist screening
- Statements: monthly PDF | real-time balance | categorized spending
- Lending: credit score check | loan application | repayment schedule
- Notifications: real-time push | email | SMS | in-app

**Compliance questions**
- Licensing jurisdiction
- PCI-DSS scope: card data stored/transmitted?
- Open Banking / PSD2: third-party access?
- Transaction limits: regulatory or product choice?

---

### Mobile App

**Actors**
- App users by platform: iOS | Android | both | React Native / Flutter / PWA
- Backend roles: same as SaaS or domain-specific

**Features**
- Offline mode: none | read-only | full offline + sync
- Push notifications: transactional | marketing | silent/background
- Deep linking: universal links | custom scheme
- Biometrics: Face ID / Touch ID for auth | for payments
- Camera/media: photo capture | video | QR/barcode scanner
- Location: not used | foreground only | background | geofencing
- App stores: public | enterprise MDM | TestFlight/Firebase

---

## Universal NFR Question Bank

Always ask these for every domain. Present numeric examples so user understands the scale.

| NFR Category | Question | Example options |
|---|---|---|
| Performance | Max acceptable response time | < 200ms | < 500ms | < 1s |
| Throughput | Expected concurrent users at peak | < 100 | 100-1,000 | 1,000-10,000 |
| Availability | Uptime SLA | 99% | 99.9% | 99.99% |
| Recoverability | Max data loss acceptable | 0 (sync replica) | 1 min | 1 hour |
| Recoverability | Max recovery time | < 5 min | < 1 hour | < 4 hours |
| Security | Auth strength | Password only | MFA optional | MFA mandatory |
| Security | Data classification | Public | Internal | Confidential |
| Scalability | Growth expectation | < 2x users | 2-5x | 5-10x |
| Compliance | Applicable regulations | None | GDPR | HIPAA | PCI-DSS |
| Localization | Languages needed | English only | + Vietnamese | Multi-language |

---

## Completeness Checklist

Before allowing Phase 2 to begin, confirm all boxes:

- [ ] Every actor has a name, description, and role scope
- [ ] Every actor's data access rights are defined
- [ ] Core features list has been confirmed
- [ ] IN scope / OUT scope boundary is explicit
- [ ] At least one NFR has a numeric target per category
- [ ] At least one business rule per feature cluster is stated
- [ ] Compliance requirements are stated
- [ ] Integration points listed

Any unchecked box means remaining round to complete before Phase 2.
