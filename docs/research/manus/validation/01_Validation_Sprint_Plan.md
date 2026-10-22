# 01 – Validation Sprint Plan

**Stand:** 22.10.2026  
**Dokument-ID:** 01  
**Status:** Planung; alle praktischen Evidenzen und Resultate **NOT TESTED**, alle noch zu erfassenden Messwerte `null`.  
**Normativer Vorrang:** [Kanonischer Spezifikationsvertrag](contracts/00_Canonical_Contract.md).  
**Research-Basis (Stand 21.10.2026):** [Audit 01](audit_baseline/01_Executive_Market_Feasibility_Report.md), [Audit 07](audit_baseline/07_Build_vs_Buy_Analysis.md), [Audit 12](audit_baseline/12_Open_Questions_Validation_Plan.md).

## 1. Zweck, Entscheidungsgrenze und Nicht-Ziele

Dieser Sprint spezifiziert den **isolierten Benchmark- und Validation-Harness** für den Referenzfall **Inbound Appointment & Qualification Agent**. Die zu validierende fachliche Folge lautet: Inbound → KI-Offenlegung → Anliegen und Kontaktdaten erfassen/bestätigen → Qualifikation → freie Termine lesen → Slot wählen und rückbestätigen → **serverseitig** buchen → Erfolg erst nach autoritativer Bestätigung sagen → CRM Mock aktualisieren → Outcome persistieren. Eine bestätigte Buchung mit nachfolgendem CRM-Fehler bleibt `BOOKED_CRM_PENDING`; sie darf nicht als ungebucht dargestellt werden.

Der Sprint erzeugt keine Architekturentscheidung, keine produktive Voice-Plattform, keinen produktiven Call, keine Ausgabenfreigabe und keine behauptete Provider-/SDK-Verifikation. Er erzeugt implementierbare Spezifikationen, Fixtures, Mess- und Gate-Regeln, mit denen Claude Code nach menschlicher Freigabe einen Harness bauen kann. Die auditierte strategische Richtung – Fachautorität, Tenant-/Toolkontrolle und Outcome-Semantik selbst kontrollieren; Speech, LLM und PSTN zunächst einkaufen – ist eine zu prüfende Abgrenzung, keine Auswahlentscheidung ([Audit 07](audit_baseline/07_Build_vs_Buy_Analysis.md)).

**Ausgeschlossen:** Outbound-Kaltakquise, produktive CRM-/Kalenderkonten, reale Kundendaten, Echtsecrets, Deployment, Installation, Anbieteranfragen und Live-PSTN-Tests im Rahmen dieser Dokumentenerstellung. Ein optionaler späterer Opt-in-Speed-to-Lead-Fall ist keine Primary-Benchmark-Lane: nur `TEST_ALLOWLIST`, serverseitiges Pre-Dial-Policy-Gate und niemals ein unbekanntes Ziel. Die Offenlegung ersetzt keine Rechtsgrundlage für Anrufe.

Die Endentscheidung bleibt mehrdimensional: messbare deutsche Sprach-/Entity-Qualität, Caller-observable Latenz, Tool- und Buchungskorrektheit, Isolation, Datenpfad/Vertrag, Kosten mit gemessenen Einheiten sowie Betriebs- und Exitaufwand. Keine gewichtete Qualitätszahl darf ein Security-, Legal- oder Datapath-Veto überstimmen. Die Auditberichte weisen gerade für deutsche PSTN-Qualität, EU-Datenpfade, Nutzungsrechte, Vollkosten und Kapazität auf offene Evidenz hin ([Audit 01](audit_baseline/01_Executive_Market_Feasibility_Report.md)).

## 2. Vergleichsrahmen und unveränderliche Leitplanken

### 2.1 Primary T0 und sekundäre Lanes

Der faire Primärvergleich **T0** ist ausschließlich:

`freigegebener deutscher Inbound-DID / gleicher Carrieraccount / gleicher PSTN-Origination-Pfad → Carrier-SIP-Trunk → gemeinsamer LiveKit SIP-/Media-Server → gleichartige Rooms und Tracks → Runtime-Arm`.

Verglichen werden **RT-A: LiveKit Agents (Python)** und **RT-B: Pipecat (Python) mit LiveKit Transport**. Beide erhalten dieselbe freigegebene EU-Region, Hardwareklasse, Component Configuration, Prompt-/Tool-/Fixture-Hashes und autoritativen Mocks. Ein vertrauenswürdiger Dispatcher ordnet erwartete Test-`call_id` und Arm zu; Armwahl stammt nie aus SIP-Header, LLM-, Caller- oder Tenant-Eingabe. Ein Room enthält genau einen Agenten; Testcaller und Observer sind getrennte Rollen. Der gleiche DID wird sequenziell randomisiert; unter Last werden Sessions armseitig partitioniert, nicht zwei Agenten in denselben Callerroom gelegt.

Damit wird Framework-/Agentorchestrierung verglichen, **nicht** LiveKit als Media-Server zum Sieger erklärt. Direkter Carrier-WebSocket für Pipecat (T1, z. B. Carrier Media Streams) ist nur eine dokumentierte **secondary, confounded full-topology lane** mit eigenem Carrier-, Codec-, Preis- und Regionsmanifest. Ein stiller Wechsel von Carrier oder Transport innerhalb eines T0-Paares ist ungültig. Runtimeeigene optimierte Turn-Modelle sind erst nach der Primary-Paritätsprüfung eine getrennte secondary lane. Abweichungen werden im `deviation_manifest` und mit `CONFOUNDED` gekennzeichnet, nicht verborgen.

### 2.2 Baseline, Challenger, Native – staged statt Kombinatorik

B0 ist ein **PROPOSED / ANNAHME**-Platzhalter: Deepgram Nova-3 multilingual, ein schneller OpenAI-Textkandidat aus dem Audit, sowie ein streamingfähiger ElevenLabs Flash-/Turbo-Kandidat, `de`, `de-DE`, `Europe/Berlin`. Namen wie `gpt-6-luna` sind lediglich provisorische Auditnamen, keine Modell-ID. C1 hält Deepgram konstant und ändert Cartesia TTS sowie **genau einen** nach G0 freigegebenen alternativen schnellen Textkandidaten. Zuerst isolierte Änderungen C-TTS und C-LLM, dann C1 auf beiden Frameworks. Speechmatics ist ein vorregistrierter bedingter STT-Zweig, nur wenn ein vorher definierter Qualitäts-, Preis- oder Datapath-Trigger eintritt.

S5 vergleicht danach einen nativen Pfad `N-OAI-BEST` (OpenAI Realtime nur nach G0) über dieselbe T0-Media-/Tool-/Mock-Topologie mit der besten Validation-Kaskade. Wenn dieser Pfad an G0 scheitert, ist genau ein alternativer nativer Kandidat (GPT-Live oder Gemini Live) zu begründen. Native Voice erhält nie Tool-Autorität; nicht beobachtbare Zwischenmetriken bleiben `UNOBSERVABLE` oder `NOT APPLICABLE`, nicht `0`. Shadow-ASR und Evaluation sind separat zu bilanzieren.

### 2.3 Safety- und Dateninvarianten

* Das LLM bestimmt niemals `tenant_id`, Credentials, Authorization, Execution Scope, Kalender-/CRM-Referenzen oder Idempotency Keys. Der Server leitet diese nur aus dem eingefrorenen `CallContext` ab.
* Modelltools beschränken sich auf `contact.collect_candidate`, `qualification.submit_candidate`, `calendar.list_slots`, `calendar.book_slot`, `booking.get_status`, `crm.update_contact` und im Primary deaktiviertes `call.request_handover`. Unbekannte Eigenschaften werden abgewiesen; SQL, Shell, beliebige URLs und Credentials sind keine Toolargumente.
* Kontakt- und Slotänderung invalidiert jede vorherige Bestätigung. Nur Readback plus eine eindeutige aktuelle Nutzeraffirmation macht `BookingIntent` ausführbar. Der Evaluator behält Ground Truth verborgen.
* Der `CalendarMock` nutzt gleiche Fixture-Uhr, Antworten und Faults für beide Arme. Seine Einzigkeitsregel schützt `tenant + calendar + UTC-Slot`; eine nach Commit verlorene Antwort führt zu `BOOKING_UNKNOWN`, Status-Reconciliation und **niemals** blindem Zweitbuchungsversuch oder Erfolgssatz.
* Tenanttests verwenden echte PostgreSQL-Rollen, eine Non-Owner-Approlle ohne `BYPASSRLS`, `FORCE ROW LEVEL SECURITY` und zurückgesetzten Transaction Context. SQLite, In-Memory-Mocks oder RLS durch bloße API-Filter beweisen keine Isolation. Jeder tatsächliche Cross-Tenant-Zugriff ist **AUTOFAIL**; eine korrekt abgewiesene Attacke kann `PASS` sein.

## 3. G0 – verbindlicher Pre-Implementation Freeze

**G0 ist vor Adapterimplementierung, Livekonfiguration oder Provider-Call zwingend.** Er verifiziert zum Ausführungszeitpunkt, nicht am 22.10.2026 bereits geschehen: exakte Modell-, Voice-, Endpoint-, API-, SDK-, Plugin-, Framework-, Container- und Dependency-Version; Lizenz und kommerzielle/OEM-/Automationsrechte; Carrier-SIP/DTMF/Codec/Firewall/TLS/SRTP-Fähigkeit; EU-Region und vollständigen Datenpfad; AVV/Subprozessoren, Retention/Training/Tracing; Preis-/Quoten-/Routing-/Billing-Einheit; Export-, Portierungs- und Kündigungsbedingungen. Jeder Wert wird mit Retrievalzeit, Quelle, Freigabe-Owner, Hash bzw. `resolved_meta` abgelegt. Fehlt ein unveränderlicher Providersnapshot, müssen Alias plus Auflösungsmetadaten und Wiederholungsblock dokumentiert werden.

G0 verlangt außerdem menschlich autorisierte Testdaten-/Aufnahmegrundlage, minimale Speaker-Metadaten, Retention/ACL, erlaubte Testregion, Carrieraccount, Ziel-DID/Allowlist, Budgetobergrenze, Quoten, Ländersperre und Legal-/Datenschutzfreigabe. `enabled=false`, `live=false` und fehlende Secrets sind bis dahin korrekt. Eine fehlende G0-Antwort ist `BLOCKED`, nicht implizit freigegeben.

**Parallel sicher offline zulässig:** Das Team darf vor G0 Dokumente, JSON-Schemas, Text-Seed-Fixtures ohne Audio, deterministische Mock- und Faultdesigns, Contract-/Schema-Validierung sowie ein netzgesperrtes Offline-Konzept spezifizieren. Es darf keine Provideradapter, keine echte Modellauflösung, keine Call-/Audioaufnahme, keine Accountnutzung und keine Messbehauptung als „safe offline“ etikettieren.

## 4. Vorgeschlagener Arbeits- und Ticketplan

Die folgenden 20 Arbeitstage sind **PROPOSED / ANNAHME**, kein zugesagter Termin. Sie setzen mindestens Product/Business Owner, Technical Lead/Claude-Code-Implementierung, QA/Evaluation, Security/Privacy sowie Legal/Procurement als verfügbare Rollen voraus; konkrete Teamkapazität, Budget und Freigabezeiten sind unbekannt. Der Puffer absorbiert nicht fehlende Rechts-, Vertrags-, Testdaten- oder Budgetfreigaben.

| WP / Ticketgruppe | Inhalt, Input → Output | Owner (R/A; C/I) | Abhängigkeit und DoD |
|---|---|---|---|
| **WP-01 / T02-001–006** | Kick-off, Referenzjourney, RACI, Scope-/No-Go-Register und verbindliche Contract-Traceability. Input: Vertrag, Audits. Output: abgestimmter Sprint-Backlog. | Product Owner / Technical Lead; QA, Security, Legal / Mensch | Tag 1–2. DoD: Primary scope, Ausschlüsse, Statusvokabular und Owner lückenlos; kein Architekturwinner. |
| **WP-02 / T02-010–018** | G0-Evidence-Register für Modelle, SDKs, Carrier, Datenpfad, Verträge, Rechte, Quoten und Exit. Output: Freeze-Manifest-Plan und Blocker-Liste. | Procurement/Legal + Technical Lead / Mensch; Privacy, Security / QA | Start Tag 1, kritisch bis Gate. DoD: jeder Pflichtpunkt `APPROVED` oder `BLOCKED`; nie „angenommen“. |
| **WP-03 / T02-020–027** | Dataset-/Consent-/Retention-Plan: 360 Kurzfälle (6×60), 30 Sprecher (120/60/180 speaker-disjoint) und 160 Dialogskripte (40/40/80), ohne Audioerhebungsbehauptung. | QA Lead / Product Owner; Privacy, Legal / Technical Lead | Tag 2–6, benötigt WP-01. DoD: hidden Ground Truth, Normalisierung, DST-Fixtures, Rechte- und Loader-Gates spezifiziert. |
| **WP-04 / T02-030–036** | Deterministische Fachmocks und Oracles: Calendar/CRM, `BookingIntent`, Confirmation, `UNKNOWN`-Reconciliation, Qualifier-Fixtures. | Backend Lead / Technical Lead; QA, Security / Product Owner | Tag 3–7, WP-01. DoD: symmetrische Mocks, idempotente Operationen und keine False-Success-Lücke spezifiziert. |
| **WP-05 / T02-040–046** | T0-Media-Parität und Run-Manifest: DID/Carrier/SIP/Room/Track, Codec/Resampling, VAD und Deviation-Logik. | Voice/Platform Lead / Technical Lead; QA, Security / Product Owner | Tag 4–8; G0-Mediaanteile blockieren Liveadapter. DoD: RT-A/RT-B exakt beschreibbar, T1 klar `CONFOUNDED`. |
| **WP-06 / T02-050–058** | Telemetrie und Callerprobe: gemeinsame monotone Uhr, Kalibrierung, JSONL-Ereignisse, Redaction und Result-/Usage-Semantik. | QA/Observability Lead / Technical Lead; Privacy, Security / Product Owner | Tag 4–9, WP-03–05. DoD: `USER_AUDIO_END` bis callerhörbares `AI_AUDIO_START` primär; Unsicherheit und Unobservability definiert. |
| **WP-07 / T02-060–071** | Negativ-/Fehlerkatalog: Tenant, Tool, SSRF-Canaries, Booking, STT/LLM/TTS/CRM/Carrier, Suppression und Fail-Closed-Oracles. | Security Lead / Security Lead; Backend, QA, Privacy / Mensch | Tag 5–10, WP-04. DoD: jeder Case reproduzierbar, lokal/canary-only, Expected Safe Result und AUTOFAIL-Regel vorhanden. |
| **WP-08 / T02-080–087** | Staged Benchmarkmatrix S0–S8 inkl. B0, Ein-Faktor-Challenger, C1, Native, Holdout und Secondary Lanes. | QA Lead / Technical Lead; Voice, Finance / Product Owner | Tag 7–11, WP-03/05/06. DoD: keine Permutationsexplosion, keine Holdout-Nutzung zum Tuning. |
| **WP-09 / T02-090–096** | Ressourcen-, Lifecycle- und Kostenplan: offline/sip_virtual/pstn_real strikt getrennt, Lastprofil, Ledger und Budget-Stop. | Platform/Ops Lead / Technical Lead; Finance, QA / Mensch | Tag 8–12, WP-02/05/06. DoD: Einheiten- und Kostenquellen definiert, keine Listenpreis-Schätzung als Ergebnis. |
| **WP-10 / T02-100–106** | Akzeptanz- und Decision-Gate-Regeln, Evidence Cards und offene ADRs. | Product Owner / Mensch; Technical Lead, QA, Legal, Security / Claude Code | Tag 10–14. DoD: Kriterien nur `PROPOSED`, Pre-Holdout-Signoff nötig, Veto von Leistungszielen getrennt. |
| **WP-11 / T02-110–117** | Implementierungsübergabe: Package-/Interface-/CLI-/Konfigurationsplan und Testreihenfolge. | Technical Lead / Claude Code; QA, Security / Product Owner | Tag 12–16; WP-03–10. DoD: reproduzierbarer Offline-first Harnessplan, echte Secrets nur ENV-Namen. |
| **WP-12 / T02-120–125** | Konsistenzreview, ChatGPT-Reviewpaket, menschliche Freigabe und Handoff-Readiness. | Product Owner / Mensch; alle Leads / Claude Code | Tag 17–20 inklusive **4 Arbeitstage Puffer**. DoD: nur freigegebene G0- und Scope-Inputs gehen weiter; alle offenen Punkte sichtbar `BLOCKED`/`HOLD_FOR_EVIDENCE`. |

## 5. Phasen, Gates und kritischer Pfad

| Phase | Geplante Aktion und Ergebnis | Eintritt / Austritt |
|---|---|---|
| **S0 – Freeze** | G0, Accounts/Legal/Data, Media-Parität, Instrumentierungs-/Clock-Kalibrierung planen. Keine Messentscheidung. | Eintritt: WP-01. Austritt: alle G0-Pflichtfelder freigegeben oder konkrete `BLOCKED`-Sperre. |
| **S1 – Offline Conformance** | Deterministische Mock-, Booking-, Security- und Harness-Tests; lokale Audio-Replays, virtuelle SIP und PSTN real getrennt. | Offline ohne Livezugang möglich. Resultate derzeit `NOT TESTED`. |
| **S2 – Components** | Isolierte STT/TTS/LLM-Tests bei B0 und einzelne Challenger-Änderungen. Kein Runtimewinner. | G0 für jeweilige Anbieter + Dataset-/Consent-Gate. |
| **S3 / S4 – T0 Cascade** | RT-A-B0 vs RT-B-B0, dann C1 auf beiden; gleiche Tools, Daten und T0-Media. | Validierungsdaten nur für Auswahl; jede Abweichung manifestiert. |
| **S5 – Native** | Ein nativer Pfad gegen beste Validation-Kaskade über T0; Toolgateway unverändert. | G0-native + vergleichbares Manifest, sonst `BLOCKED`. |
| **S6 – Holdout** | Einmaliger eingefrorener Holdout: finale Kaskade auf beiden Frameworks plus nativer Pfad. | Menschlicher Kriterien-Signoff **vor** Einsicht; kein Tuning. |
| **S7 – Lifecycle/Load** | Startup, Crash, Drain, Cleanup sowie explorative Last. | Freigegebene Provider-/Carrierquoten, Budget und Transportklasse. |
| **S8 – Thin Secondary** | Workflow Temporal vs BullMQ mit Mocks; Shared-RLS vs getrennte Test-DBs; Hosting/Observability. | Keine Stimme-/Runtime-Entscheidung daraus ableiten. |

Der kritische Pfad lautet: **Use-Case/Legal/Data-Owner → G0-Verträge/Region/Quoten → Testdatenrechte und Datasetloader → T0-Media-Parität + sichere Mocks/Telemetrie → Security-Conformance → S2–S5 validation → Kriterien-Signoff → S6 Holdout → S7/S8 nur im freigegebenen Umfang → Evidence Cards/Gate.** Ohne G0, nicht wegen unvollständiger Implementierung, muss der Plan bei `HOLD_FOR_EVIDENCE` enden.

Für S7 sind 10, 25, 50 und 100 parallele Sessions je Arm, jeweils zehnminütiges Plateau und drei Wiederholungen **PROPOSED**. Allein zwei Arme ergeben `3 × 10 min × (10 + 25 + 50 + 100) × 2 = 11.100 Agent-Session-Minuten`. Das ist keine 2.000-Minuten-Gesamtbudgetzusage, keine Providerfreigabe und keine Produktionskapazitätsaussage. `pstn_real` startet nur nach expliziter Legal-, Account-, Quoten-, Allowlist- und Budgetfreigabe bei 10 und steigt nur bei Erfolg und Reserven; nicht freigegebene Oberstufen sind `BLOCKED`, nicht `PASS`. Ein 100-Room-Test erlaubt keine 100 echten PSTN-Anrufe.

## 6. RACI und Freigaberegeln

| Rolle | Verantwortet | Darf nicht allein freigeben |
|---|---|---|
| Menschlicher Projektverantwortlicher (A) | Use Case, Budget, Region, Accounts, Kriterienstatus `ACCEPTED/CHANGED/REJECTED`, Architektur- und Testfreigabe | Legal-/Datapath-Aussage ohne Fachreview, Produktion |
| Technical/Voice Lead (R) | T0-Parität, Adapter-/Manifest-Design, Mocks, Lifecycle und Handoff | Anbieter-/Vertragsrechte, Messresultate ohne QA |
| QA/Evaluation Lead (R) | Dataset, Hidden Oracles, Randomisierung, Calibration, Holdout-Custody und Ergebnisse | Testdatenrechtsgrundlage, Security-Veto |
| Security Lead (R/C) | Toolgateway, RLS-Preflight, Negativcases, SSRF-Testnetz, AUTOFAIL-Bewertung | Risikoverzicht bei fehlendem Legal-/Data-Review |
| Privacy/Legal/Procurement (R/C) | Consent/Recording/Retention, Datenpfad, AVV, Carrier-/OEM-/Lizenzrechte | technische Qualitätsentscheidung |
| Finance/Ops (R/C) | Budgetcaps, Quoten, gemessene Units, Rechnung/Reconciliation, Ressourcenklasse | Pricing-/Kostenbehauptung ohne Beleg |
| ChatGPT Review (C) | Konsistenz- und Spezifikationsreview | Freigabe oder Architekturentscheidung |
| Claude Code (R nach Freigabe) | Harness gemäß Spezifikation implementieren und Tests ausführen | Kriterien, Testdaten, Budget oder Produktionsfreigabe |

Erlaubte Gatezustände sind `GO_FOR_HARNESS_IMPLEMENTATION`, `GO_FOR_AUTHORIZED_TESTS`, `HOLD_FOR_EVIDENCE`, `NO_GO` und `GO_FOR_SCOPED_ARCHITECTURE_DECISION`. „Harness implementiert“, „Tests autorisiert“, „Architektur entschieden“ und „Produktion freigegeben“ sind strikt verschiedene Zustände. `GO_FOR_AUTHORIZED_TESTS` ist ohne G0 unmöglich; kein Testpass ist eine Produktionsfreigabe.

## 7. Mess- und Evidenzdisziplin

Primäre Voice-Latenz ist bei einer gemeinsamen Callerprobe `AI_AUDIO_START − USER_AUDIO_END`: Ende **tatsächlicher** Nutzersprache bis erster hörbarer Agenten-Audioanteil. Endpointing, STT-final, LLM-TTFT, TTS-TTFB und Transportanteile sind getrennte diagnostische Signale; ihre Pipelinezeiten werden nicht addiert. AI-Audio-Stopp bei Unterbrechung wird am Caller gemessen, nicht als Cancellation-ACK. Filler-Gaming, frühe Antworten, Echo, Backchannels und Clock-Unsicherheit werden explizit annotiert. Vorgeschlagene Clock-Unsicherheitsgrenze >20 ms disqualifiziert einen Stagevergleich, ohne einen noch brauchbaren gleichclockigen Blackbox-Caller-Test als `0` umzudeuten.

Jeder Resultatsatz enthält `attempts`, `successes`, `failures`, `timeouts`, `invalids`, Zähler/Nenner, Einheit, Observability, Kalibrierreferenz, Abweichung und Artefakthash. Aktuell sind sie `NOT TESTED` und Messfelder `null`. Für spätere Rates gelten Failure-first, maximal drei vorregistrierte Wiederholungen, paired/randomisierte Fälle mit Seed `24022026`, nearest-rank Quantile über erfolgreiche Latenzen sowie separat gezählte Deadline-Fehler. Holdout bleibt für Auswahl/Tuning gesperrt. Die provisorischen Ziele p95 Non-Tool ≤1.500 ms, p50 ≤800 ms, p95 Interrupt-Stop ≤300 ms, bestätigte kritische Felder ≥0,99 und null unautorisierte Ausführung/Falscherfolg/Cross-Tenant-Leak sind **PROPOSED**; sie werden vor Holdout menschlich akzeptiert, geändert oder verworfen.

## 8. Risikoregister, Stop-Regeln und Eskalation

| Risiko / Trigger | Sofortmaßnahme | Gatewirkung |
|---|---|---|
| Fehlende Modell-/SDK-/Carrier-/Vertrags- oder EU-Datapath-Evidenz | Kandidat sperren, kein Ersatz ohne dokumentierten G0-Review | `HOLD_FOR_EVIDENCE` / betroffene Lane `BLOCKED` |
| Keine eindeutige Testdaten-/Recording-/Retention-Grundlage | Nur Text-Seed-Fixtures; keine Aufnahme, kein PSTN | Audioevaluation `BLOCKED` |
| Cross-Tenant-Lesen/-Schreiben, RLS-Owner/BYPASS-Preflightfehler | Run stoppen, Evidenz sichern, Case nicht wegfiltern | **AUTOFAIL**, `NO_GO` für betroffene Architektur |
| Unautorisierte Toolausführung, SSRF-Egress, Suppression-Umgehung | Seiteneffekte sperren, lokale Canaries sichern, Ursachenanalyse | **AUTOFAIL**, keine Qualitätskompensation |
| `BOOKING_UNKNOWN` oder Response-lost | Erfolgskommunikation unterdrücken, nur Status-Reconciliation | kein Auto-Retry, fachliche Safety-Pflicht |
| Budget-/Quota-/Carrier-CPS-Grenze | Run geordnet abbrechen, Metering sichern, nicht extrapolieren | Lane `BLOCKED` oder `ABORTED` |
| Unkalibrierte/Ungültige Callerclock oder fehlende Audioartefakte | Messung als `INVALID`/`INSUFFICIENT EVIDENCE` markieren | keine Latenzrangleistung |
| Holdout vor Signoff oder zu Tuning genutzt | Holdout verwerfen/neu erzeugen, Ereignis dokumentieren | keine finale Evidenz |

## 9. Package, alle Deliverables und operatives Handoff

Dieses Dokument steuert ein geschlossenes Paket; die Artefakte sind fachlich gekoppelt und dürfen beim Handoff nicht voneinander entkoppelt werden:

1. **[01 Validation Sprint Plan](01_Validation_Sprint_Plan.md)** – Scope, Phasen, RACI, Gates (dieses Dokument).
2. **[02 Benchmark Matrix](02_Benchmark_Matrix.md)** – Arme S0–S8, Kontrollvariablen und Sample-/Transportmatrix.
3. **[03 German Voice Dataset Specification](03_German_Voice_Dataset_Specification.md)** – Corpus, Ground Truth, Split, Consent und Fixtureloader.
4. **[04 Measurement & Telemetry Specification](04_Measurement_Telemetry_Specification.md)** – Callerclock, Events, Formeln und Resultatmodell.
5. **[05 Security & Failure Test Plan](05_Security_Failure_Test_Plan.md)** – Negativtests und Safety-Oracles.
6. **[06 Runtime Comparison Plan](06_Runtime_Comparison_Plan.md)** – T0-Fairness, Lifecycle und explorative Last.
7. **[07 Provider Comparison Plan](07_Provider_Comparison_Plan.md)** – B0/C1/native und G0-providerbezogen.
8. **[08 Cost Measurement Plan](08_Cost_Measurement_Plan.md)** – Usage-Ledger, Rechnung und Kostengrenzen.
9. **[09 Acceptance Criteria](09_Acceptance_Criteria.md)** – vorgeschlagene Ziele, Coverage und Veto-Regeln.
10. **[10 Claude Code Benchmark Implementation Specification](10_Claude_Code_Benchmark_Implementation_Specification.md)** – implementierbarer Harnessvertrag.
11. **[11 ADR Templates](11_ADR_Templates.md)** – zehn offene ADRs und Evidence Cards.
12. **[12 Decision Gate Template](12_Decision_Gate_Template.md)** – signierbarer Evidenz-/Freigabeabschluss.

Die Übergabe erfolgt in vier Schritten: (1) ChatGPT prüft Contract-Traceability, Konsistenz der Schemas und dass kein `NOT TESTED`-Platzhalter als Ergebnis missverstanden wird. (2) Der Mensch akzeptiert/ändert/verwirft Ziele und autorisiert Scope, Rechte, Region, Testdaten, Budget und Accounts. (3) Claude Code implementiert ausschließlich den isolierten, offline-first Harness gemäß Dokument 10 und den gemeinsamen Verträgen; Secrets bleiben ausschließlich ENV-Referenznamen. (4) Erst danach autorisierte Tests, immutable Run-Artefakte, Evidence Cards und das Decision Gate. ADR-001 bis ADR-010 bleiben bis zu echter Evidenz `PROPOSED`/`NOT TESTED`.

**Operative G0-Blocker zum Handoff:** Use Case-/Land-/Empfänger- und Rechtsgrundlage; EU-/Drittland- und Recording/Transcript/Retention-Policy; Modell-/SDK-/Voice-/Carrier-/Preis-/Lizenzfreeze; SIP/DTMF/Codec/Firewall/TLS/SRTP-Preflight; Testdateneinwilligung und Audio-/Metadata-ACL; Teamkapazität, Budget, Quoten, Allowlist und Testregion; Peak-/SLO-/Supportannahmen; klarer erster kritischer Entity-/Toolumfang. Bis diese Punkte explizit vorliegen, ist der korrekte Paketstatus **`HOLD_FOR_EVIDENCE`**, nicht „bereit für Livebetrieb“.
