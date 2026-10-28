# VoiceOS – Project Rules for Claude Code

VoiceOS is a planned multi-tenant AI voice SaaS platform. **Phase 0 – Foundation** (offline,
deterministic, tenant-isolated foundation) and **Phase 1 – Voice Benchmark** (evidence
harness, `voiceos.benchmark`) are merged. **Phase 2** currently exists only as a `PROPOSED`
product blueprint in `docs/product/`; there is no product code yet.

## Roles and authority

- Claude Code is the implementation engineer for the scoped phase only.
- Architecture / QA review: ChatGPT. Final approvals: the human project owner.
- Do not choose the product architecture, providers or runtimes on your own. Do not start
  another phase, merge, push or deploy without explicit instruction from the human owner.

## Source-of-truth hierarchy

1. Accepted ADRs in `docs/architecture/decisions/`
2. Approved architecture documents in `docs/architecture/`
3. Explicit scoped implementation instructions
4. Manus research in `docs/research/manus/` – evidence/specification input only

`PROPOSED`, `PRIMARY CANDIDATE`, `RECOMMENDED`, `SHORTLIST`, `NOT TESTED` are **not**
decisions. If an accepted ADR contradicts a research document, the ADR wins.

## Permanent rules

### Security / authority
1. LLM output is never business authority.
2. `tenant_id` must originate from trusted server-side context.
3. Never accept `tenant_id`, credentials, authorization scopes or permissions from
   model-generated tool arguments.
4. All business-critical external actions must pass through the validated Tool Gateway.
5. Tool execution requires server-side authentication, authorization, tenant validation,
   schema validation, policy validation, and idempotency where applicable.
6. The LLM may propose an action. It may never authorize that action.
7. No arbitrary URL access, SQL execution, shell execution or credential access through
   model-generated tool requests.

### Multi-tenancy
8. Every tenant-owned persistent entity contains `tenant_id`, unless an explicit documented
   architectural exception exists.
9. PostgreSQL Row Level Security is mandatory for tenant-owned data.
10. Application roles must not be database owners, superusers or `BYPASSRLS`.
11. Cross-tenant data access is a HARD FAILURE.
12. Tenant context never originates from untrusted request fields, LLM output, prompt
    content, knowledge documents or arbitrary webhook payloads.

### Business state
13. Never claim a business action succeeded before authoritative backend confirmation.
14. Booking writes must be idempotent.
15. An uncertain booking result enters `BOOKING_UNKNOWN`.
16. `BOOKING_UNKNOWN` requires reconciliation and never triggers blind rebooking.
17. CRM failure after authoritative booking confirmation does not invalidate the booking;
    it is represented independently as `BOOKED_CRM_PENDING`.

### Security / privacy
18. No secrets in source code.
19. No secrets in fixtures.
20. No secrets in logs or telemetry.
21. No real customer data in the benchmark environment.
22. Recording defaults to disabled unless explicitly authorized later.
23. No real PSTN calls without explicit authorization.
24. No production deployment without explicit authorization.
25. No outbound campaign execution in Phase 0.

### Architecture governance
26. No microservices unless an approved ADR requires them.
27. No Kubernetes.
28. No Temporal.
29. No n8n in Phase 0.
30. n8n must never control realtime voice execution.
31. Do not select LiveKit, Pipecat or another runtime as architecture winner in Phase 0.
32. Do not select STT/TTS/LLM/Telephony providers as architecture winners in Phase 0.
33. Provider integrations later use explicit adapter boundaries.
34. Manus research is evidence/specification input, not implementation authority.
35. Security-critical functionality requires automated negative tests.
36. Decisions that require evidence stay `NOT DECIDED` until their validation gate passes.

## Working conventions

- Python 3.12, managed with `uv`; dev tools `pytest`, `ruff`, `mypy` (strict).
- Small modules, explicit typed contracts, deterministic behavior, negative tests first.
- Report test results only as actually observed; use `NOT TESTED` when there is no evidence.

### Speculative infrastructure, boundaries and dependencies (Phase 2 precision)

These rules refine the Phase 0 conventions for the planned Phase 2 product. They never
weaken the permanent rules above (RLS, tenant authority, trusted `CallContext`, Tool
Gateway, fail closed, ledger/reconciliation, secret handling, no business action on
partial transcripts).

1. **No speculative infrastructure.** No abstraction or infrastructure only "for later". In
   particular no Redis, Kafka, RabbitMQ, Temporal, Kubernetes, service mesh, generic plugin
   systems or unnecessary (micro)services without a concrete, documented product need;
   permanent rules 26–28 continue to apply.
2. **Product-required boundaries are allowed.** Ports, adapters and provider boundaries are
   allowed when they model a concrete, existing product boundary – e.g. runtime, STT, LLM,
   TTS, telephony, integration provider, secret provider, object storage ports. No abstract
   factory or plugin architecture for hypothetical future providers.
3. **Queues and async work** are not introduced speculatively. The PostgreSQL transactional
   outbox and PostgreSQL job queue (`SKIP LOCKED`) proposed in the Phase 2 blueprint are
   allowed once the corresponding Phase 2 decision has been formally made and a concrete
   product workflow needs them. This does not allow Redis, Kafka or other external queue
   systems.
4. **Dependencies stay minimal but are not frozen** to `pydantic` and `psycopg`. A new
   dependency only for a concrete product need, never for convenience. Before adding one,
   check maintenance, license, security, transitive dependencies and existing alternatives
   in the project, and state the reason. Larger architecture dependencies require the
   corresponding decision/ADR first – e.g. a web framework only after D-18, an auth SDK only
   after the auth decision, a runtime SDK only in the productive runtime PR, a telephony SDK
   only after the telephony decision.

## VoiceOS Product UI & Apple Design Governance

Binding for every future task that touches UI, UX, the web app, dashboards, navigation,
forms, tables, dialogs, Agent Studio, Call Detail, analytics, onboarding, settings,
responsive behavior, accessibility, motion/animation, glass/materials, the design system,
components or a frontend review. It governs design quality only; it does not implement UI.

### Required skill

- Use the locally installed `apple-design` skill (`~/.claude/skills/apple-design`) for
  every such task: consult it actively while designing and check design decisions against
  it, including accessibility reviews and the final design review of a UI PR.

### Design authority (highest first)

1. VoiceOS product requirements and business requirements
2. Accessibility and functional usability
3. Apple Human Interface Guidelines
4. The installed `apple-design` skill
5. VoiceOS design system
6. Project-specific UI requirements

Visual aesthetics must never degrade functionality, accessibility, comprehensibility, data
clarity, security or business processes.

### Principles

- **Apple as principle, not copy.** Use Apple for hierarchy, clarity, focus, progressive
  disclosure, typography, spacing, materials, depth, motion, feedback, navigation,
  accessibility, information architecture and interaction quality. VoiceOS keeps its own
  B2B SaaS identity: not a copied Apple website, not macOS Settings. Never copy Apple
  trademarks or protected Apple assets.
- **Web-first.** VoiceOS is a professional web SaaS. The future UI is oriented towards
  React, Next.js and TypeScript; Apple principles are translated to the web. SwiftUI, UIKit
  and AppKit are conceptual references only, never the implementation technology of the
  web app, even if the skill knows them.
- **Target impression:** high quality, calm, precise, modern, trustworthy, technically
  advanced, professional, clear, fast, consistent. Not a generic SaaS template, AdminLTE,
  Bootstrap dashboard, AI-generated component patchwork, overloaded enterprise software or
  a marketing landing page inside the app.
- **Visual hierarchy.** Before building a screen, settle: the most important information,
  the primary action, what is secondary, what can be hidden or disclosed progressively,
  and what must stay visible. Do not weight all information equally.
- **Glass / materials** only where they serve a purpose: navigation, sidebars, floating
  controls, overlays, command surfaces, modals, context panels and important layered
  surfaces. Not every card is glass. Data-rich areas need contrast and calm. Glass never
  reduces legibility or accessibility.
- **Depth** comes from layering, material, blur, border, shadow, tonal separation and
  motion – no exaggerated shadows, no decorative depth without functional meaning.
- **Typography** has a clear hierarchy (page title, section title, card/panel title, body,
  secondary information, metadata, labels, numeric/KPI emphasis) with few sizes and
  weights. No Apple-proprietary fonts unless their license allows use in this web SaaS;
  the VoiceOS design system defines the web font.
- **Spacing and tokens.** Systematic spacing, no scattered pixel values. Design tokens for
  spacing, radius, typography, elevation, blur, borders, colors and motion; components use
  the tokens.
- **Motion is functional:** it explains where something comes from or goes, what changed,
  what is active, which layer opened, which action succeeded. Subtle, fast, interruptible,
  consistent; respects `prefers-reduced-motion`; never slows the user down.
- **Accessibility is mandatory, not an add-on:** keyboard navigation, visible focus states,
  semantic HTML, ARIA only where needed, sufficient contrast, screen-reader clarity,
  reduced motion, zoom, responsive layout, touch targets, status never by color alone.
- **Responsive, desktop-first:** desktop/laptop, then tablet, then mobile. Complex desktop
  workflows may be simplified on mobile; large tables and agent editors are not just
  scaled down.
- **Information density.** B2B screens (Calls, Analytics, Contacts, Usage, Audit Logs) may
  be dense, with clear grouping, hierarchy, filters, search, progressive disclosure, good
  tables and detail views.
- **Dark mode** must be possible in the design-system architecture – not by color
  inversion; contrast, materials, elevation and borders work separately. A first UI PR need
  not ship it unless its scope requires it.

### Product-specific UI requirements

- **Voice interactions are first-class:** plan visualizations for call state, live call,
  caller/agent turns, transcript, tool calls and results, transfer, barge-in, latency, call
  outcome, recording, errors and provider events. A call is not just a text log; Call
  Detail gets a visual timeline of the conversation and its system events.
- **Agent Studio** must be understandable for non-technical users and reduce complexity by
  progressive disclosure. Conceptual areas: Basics, Voice, Behavior, Knowledge, Tools,
  Workflow, Phone, Testing, Deployment; technical advanced settings are separate.
- **Safe action UX:** safety-critical states are always visible, never hidden behind
  decorative UI – e.g. unpublished changes, deployment failure, integration disconnected,
  provider unavailable, operation `UNKNOWN`, recording disabled, missing consent, phone
  routing conflict.
- **Destructive actions** (delete agent, remove phone number, disconnect integration,
  deactivate deployment, delete knowledge, delete recording) get appropriate friction;
  harmless actions get no unnecessary confirmations.
- **Empty states** explain what the area is, why it is useful and the sensible next step –
  no generic "No data available" where a better entry point exists.
- **States:** every productive surface designs loading, empty, success, partial success,
  error, unavailable and permission denied. No happy-path-only UI.

### Design system first

Before larger numbers of product pages are implemented, a small VoiceOS design system
exists with at least: design tokens, typography, spacing, colors, radius,
elevation/material, buttons, inputs, selects, cards/panels, navigation, tabs, tables,
badges/status, dialogs, drawers, tooltips, alerts, empty states, skeleton/loading, charts,
timeline primitives. Do not duplicate screen-specific components where a reusable
primitive fits.

### UI implementation rule

Before larger UI work: (1) read the relevant product requirements, (2) understand the
screen/flow, (3) apply the `apple-design` skill, (4) fix the information hierarchy,
(5) check existing design-system components, (6) implement, (7) check accessibility,
(8) check responsive behavior, (9) check loading/error/empty states, (10) run a final
Apple HIG / design review.

### Design review gate

A UI PR is not done just because TypeScript compiles, tests pass or the screen roughly
looks right. Before completion, a design review with the `apple-design` skill checks:
hierarchy, consistency, HIG principles, accessibility, responsive design, motion,
information density, error states, empty states, design tokens and component reuse.

### Limits of the skill's authority

The `apple-design` skill is a design and review aid. It must not override product or
security requirements, affect tenant isolation, change business rules, determine backend
architecture, or install new dependencies unchecked (the dependency rule in "Working
conventions" applies). Report conflicts instead of resolving them silently.

### Apple references

Apple Human Interface Guidelines and relevant Apple design/WWDC principles may serve as
design references. Do not state time-dependent or specific claims about current Apple
guidelines from memory; check the current source when a concrete decision depends on it.

## Commands

```bash
cp .env.example .env            # then fill in local-only passwords
docker compose up -d --wait     # local PostgreSQL 18.6 on 127.0.0.1:55432
uv sync
uv run --env-file .env pytest   # all tests, including real PostgreSQL RLS tests
uv run pytest -m "not postgres" # offline unit tests only
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

The PostgreSQL test session drops and recreates the `voiceos` schema in the local
development database.
