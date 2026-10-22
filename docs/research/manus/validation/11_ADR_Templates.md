# 11 – ADR Templates: Architecture Decision Records & Evidence Cards

**Dokument-ID:** 11  
**Planstand:** 22.10.2026  
**Status:** **PROPOSED** – sämtliche Teststände sind **NOT TESTED**.  
**Geltung:** Isolierter Validation-Harness für den **Inbound Appointment & Qualification Agent**. Dies ist keine Produktionsarchitektur, keine Implementierung und keine Technologieentscheidung.

## 1. Zweck und Entscheidungsgrenze

Dieses Paket stellt zehn ausfüllbare Architecture Decision Records (ADRs) und eine einheitliche Evidence Card bereit. Es überführt die Researchbasis in einen kontrollierten menschlichen Entscheidungsprozess: Auditberichte benennen **Kandidaten**, der Benchmark erzeugt später Evidenz, und der menschliche Projektverantwortliche entscheidet anschließend ausdrücklich über Annahme, Änderung oder Verwerfung. Bis dahin darf keine Vorlage einen „Winner“, eine freigegebene Architektur oder eine abgeschlossene Vertragsprüfung suggerieren.

Der fachliche Referenzablauf ist verbindlich: **Inbound → AI Disclosure → Anliegen erfassen → Contact erfassen/bestätigen → Qualify → Calendar lesen → Slot auswählen/bestätigen → serverseitig buchen → erst nach autoritativer Bestätigung Erfolg sagen → CRM Mock aktualisieren → Outcome persistieren**. Eine Runtime, ein Modell oder ein nativer Voice-Pfad besitzen dabei nie Toolautorität. Der Tool-Gateway leitet `tenant_id`, Credentials, Scopes, Kalender-/CRM-Referenzen, `intent_id` und Idempotenzschlüssel ausschließlich aus dem vertrauenswürdigen serverseitigen `CallContext` ab; diese Werte sind nicht Teil der Modell-Toolargumente.

Der [kanonische Vertrag](contracts/00_Canonical_Contract.md) hat Vorrang bei IDs, Topologie, Status, S0–S8, Dataset, Toolautorität, Ergebnissemantik und Hard-Fails. Alle konkreten Mess- und Kostenzahlen in diesen Vorlagen sind `null`; `null` bedeutet **unbekannt**, nicht ein gemessener Wert von null.

## 2. ADR-Index und zulässiger Evidenzpfad

| ADR | Offene Entscheidung | Kandidatenraum – nicht gerankt | Vorgesehene Evidenz | Status |
|---|---|---|---|---|
| [ADR-001](adr/ADR-001_Voice_Runtime.md) | Python-Voice-Runtime | LiveKit Agents; Pipecat mit LiveKit Transport | S0, S3, S4, S6, S7 in T0 | PROPOSED / NOT TESTED |
| [ADR-002](adr/ADR-002_Voice_Architecture.md) | Voice-Architektur | Kaskade; native S2S; delegierter Hybrid | S2–S6, gleicher Tool-/Media-Pfad | PROPOSED / NOT TESTED |
| [ADR-003](adr/ADR-003_STT_Provider.md) | Streaming STT | Deepgram; bedingter Speechmatics-Branch | S0, S2, S3/S4, S6 | PROPOSED / NOT TESTED |
| [ADR-004](adr/ADR-004_TTS_Provider.md) | Streaming TTS | ElevenLabs; Cartesia | S0, S2, S4, S6 | PROPOSED / NOT TESTED |
| [ADR-005](adr/ADR-005_LLM_Strategy.md) | Text-/native Modellstrategie | schneller OpenAI-Textkandidat; ein Challenger; OpenAI Realtime | S0, S2, S4–S6 | PROPOSED / NOT TESTED |
| [ADR-006](adr/ADR-006_Telephony.md) | Carrier-/SIP-Pfad | freigegebener T0-Carrier; expliziter Carrierblockwechsel | S0/T0; optional getrenntes T1 | PROPOSED / NOT TESTED |
| [ADR-007](adr/ADR-007_Workflow_Engine.md) | Durable Workflow außerhalb Audio | Temporal; BullMQ plus Fachstatusmaschine | S8, gemockte Async-Effekte | PROPOSED / NOT TESTED |
| [ADR-008](adr/ADR-008_Tenant_Architecture.md) | Tenant-Isolation/Datenpartitionierung | Shared PostgreSQL+RLS; getrennte Testdatenbanken | S8, echte PostgreSQL-Rollen | PROPOSED / NOT TESTED |
| [ADR-009](adr/ADR-009_Hosting.md) | Hosting-/Betriebsform | Managed EU; eigener EU-Betrieb | S0, S7, S8, gematchte Ressourcen | PROPOSED / NOT TESTED |
| [ADR-010](adr/ADR-010_Observability.md) | Telemetrie-/Auditierbarkeit | OpenTelemetry; optionale Eval-/Trace-Ergänzung | S0, S1, S7, S8 | PROPOSED / NOT TESTED |

### 2.1 Fairness des Runtimevergleichs

Der Primärvergleich **T0** nutzt denselben freigegebenen deutschen Inbound-DID, Carrieraccount und PSTN-Originationspfad: **Carrier SIP-Trunk → gemeinsamer LiveKit SIP/Media-Server → gleichartige Rooms/Tracks**. Arm `RT-A` ist LiveKit Agents in Python, Arm `RT-B` Pipecat in Python mit LiveKit Transport. Der vertrauenswürdige Dispatcher ordnet einen erwarteten Inbound-Testcall dem Arm zu; Armwahl stammt niemals aus SIP-, User-, LLM- oder Tenantinput. Jeder Room enthält genau einen Agenten, Testcaller und Observer bleiben getrennte Rollen.

Dies vergleicht Agentorchestrierung, **nicht** unabhängig den LiveKit-Mediaserver. Pipecat mit direktem Carrier-WebSocket ist ein nur sekundäres **T1**-Full-Topology-Experiment mit eigenem Carrier-, Preis-, Codec-, Regions- und Deviation-Manifest. T1 darf nie als Frameworkbeweis in ADR-001 dienen.

## 3. Gemeinsames Evidence-Card-Protokoll

Das Maschinenformat ist [evidence_card.schema.json](contracts/evidence_card.schema.json); die valide Leervorlage ist [Evidence_Card_NOT_TESTED.example.json](config/Evidence_Card_NOT_TESTED.example.json). Jede Entscheidungsakte führt mindestens folgende Felder und darf nicht selektiv gute Resultate herausgreifen:

| Feld | Evidenzpflicht vor einer Recommendation | Templatezustand |
|---|---|---|
| **Decision / Candidates** | ADR-ID, Kandidaten, Scope, mögliche Alternativen | Kandidaten, keine Rangfolge |
| **Benchmark Configuration** | Stage/Arm, T0/T1, Codec, Region, Prompt-/Tool-/Fixture-/Config-Hashes, Deviation-Manifest | Hashes `null` |
| **Test Results** | Status, Messwerte, Nenner, CI, Timeouts, Artefakt-Hashes | NOT TESTED; Zahlen `null` |
| **Failures** | Fehlerversuche und BLOCKED/INVALID/ABORTED sichtbar halten | keine Beobachtung |
| **Operational Complexity** | tatsächlich beobachtete Engineering-, Debug-, On-call- und Betriebsarbeit | tatsächliche Zeiten `null` |
| **Cost** | Metered Usage, Route/Leg, Rate-Ref, Rechnung/Export, Allokationsregel | Mengen/Kosten `null` |
| **Compliance / Data** | Datenpfad, Region, Lizenz/Vertrag, Retention/Transfer und Security-Gate | NOT VERIFIED |
| **Lock-in / Migration / Exit** | Adapter-/Exportvertrag, Wiederanlauf/Migration oder Portierung | NOT TESTED |
| **Recommendation / Confidence** | nachvollziehbare Evidenz und Gate-Bezug | `null`; LOW |
| **Rejected Alternative** | erst nach Gate mit Gegenbeleg | `null` / NOT DECIDED |

Zulässige Testzustände sind ausschließlich `NOT TESTED|PASS|FAIL|BLOCKED|INSUFFICIENT EVIDENCE`; ein Laufstatus kann zusätzlich `RUNNING|ABORTED|INVALID` sein. Der ADR-Status bleibt davon getrennt: `PROPOSED|ACCEPTED|REJECTED|SUPERSEDED`. Ein erwarteter und korrekt abgelehnter Angriff kann `PASS` sein. Ein tatsächlich erfolgter Fremdzugriff kann es nie sein.

### 3.1 Vor Dateneinsicht registrieren

Gate Owner und QA registrieren für jede Evidence Card Kandidaten, Armdefinition, Vergleichseinheit, eingeplante Metriken, Sicherheitsoracles, Ausschlussregeln, Fixture-/Prompt-/Toolversion und Auswahlregel. Die Reihenfolge ist gepaart mit Vertragsseed randomisiert. `failure first` bleibt gezählt; Wiederholungen sind begrenzt. Dev und Validation dienen der Auswahl, der Holdout wird danach einmal gefroren genutzt und niemals für Tuning, Hören, Prompts oder Providerwechsel geöffnet.

Für Voice-Latenz gilt primär die Caller-beobachtbare Differenz von tatsächlichem `USER_AUDIO_END` bis erstem hörbaren `AI_AUDIO_START`. Endpointing, STT-Final, LLM-TTFT und TTS-TTFB sind ergänzende Teilmessungen; Streamingstufen werden nicht addiert. Barge-in misst den annotierten intentional interrupt bis zum letzten hörbaren alten Agentenaudio beim Caller, nicht nur einen Cancel-Ack. Nicht verfügbare native Zwischenwerte bleiben `UNOBSERVABLE` bzw. `NOT APPLICABLE`, niemals `0`.

## 4. Gemeinsame fachliche Oracles

Die ADRs verwenden denselben autoritativen Backendpfad. `ContactCandidate` wird vorgelesen und erst nach eindeutiger Affirmation mit aktueller Readback-Hashversion `CONFIRMED`; Korrektur oder Negation invalidiert die Bestätigung. `BookingIntent` wird analog `EXECUTABLE`. Das Modell kann Vorschläge machen, aber kein fremdes Kalenderobjekt, keine unbekannte URL und keinen Scope auswählen.

`CalendarMock` stellt `GET slots`, `POST booking`, `GET bookingbyoperation` und testonly `POST cancel` bereit. Eine Buchung hat eine semantische Operation-ID pro BookingIntent, nicht pro Toolturn. Gleiche Operation plus gleicher Payloadhash muss dieselbe autoritative Buchung zurückgeben; anderer Payload ist Konflikt. Nach „accept response lost“ wird der Zustand `BOOKING_UNKNOWN`; das System darf nicht blind erneut buchen und darf keine Erfolgsaussage machen, bis die Statusreconciliation bestätigte Evidenz liefert. Ein CRM-Ausfall nach bestätigter Buchung ergibt `BOOKED_CRM_PENDING`, nicht „keine Buchung“.

`CRMMock` erzwingt servereigene Contact-Referenz, Signatur-/Replayprüfung, idempotente Operationen und Fehlerfälle wie Retry-After, Invalid Field sowie doppelte Webhooks. Toolerfolg ist der externe fachliche Zustand, nicht strict JSON oder Modelltext. Dieses Prinzip schützt alle Entscheidungen gleichermaßen vor einer Optimierung auf unechte Erfolgsindikatoren.

## 5. Nicht überstimmbares Veto

Keine Gewichtung, Kostenersparnis oder gute Latenz darf eines der folgenden Ereignisse überstimmen:

- tatsächlicher Cross-Tenant-Zugriff, einschließlich fehlerhafter RLS-Preflight-Konfiguration (**AUTOFAIL**);
- ausgeführte unautorisierte Toolaktion bzw. modellbestimmter Tenant, Credential oder Scope;
- falsche Buchungserfolgsaussage für einen nicht autoritativ bestätigten bzw. unbekannten Vorgang;
- Call trotz serverseitiger Suppression oder außerhalb freigegebener Test-Policy;
- offener Rechts-, Datenpfad-, Lizenz-, Vertrags- oder Recording-Block.

RLS-Evidenz setzt echte PostgreSQL-Approllen voraus, die weder Owner noch Superuser noch `BYPASSRLS` sind; `FORCE ROW LEVEL SECURITY`, Policies und transaktionslokaler Kontext mit Rollback sind nachzuweisen. SQLite, Mock-RLS oder ein bloßes `tenant_id` im Payload gelten nicht als Isolationstest. Isolierte Fake-Canaries sind zulässig; reale Kundendaten und aggressives SSRF gegen Dritte sind es nicht.

## 6. G0 vor Adapterimplementierung und realem Test

**G0 ist offen.** Es ist kein bereits erledigter Audit. Mensch, Legal/Datenschutz, Procurement und Ops schließen je Lane folgende operative Blöcke oder kennzeichnen sie als `BLOCKED`:

1. **Modell-/SDK-/API-/Vertragsfreeze:** exakte aktuelle IDs, Voice, Endpoint, Region/Datenpfad, SDK/Plugin/Container, Lizenz, Quoten und Snapshotfähigkeit. Auditnamen – beispielsweise `gpt-6-luna` – sind nur provisorische Auditnamen.
2. **Carrier-/Media-Parität:** DID, Route, Nummernklasse, SIP-/DTMF-/Codec-/Firewall-/TLS/SRTP-Fit, Account und tarifliche Grundlage. T0 ist festzuschreiben; ein Carrierwechsel ist ein eigener Block.
3. **Testdaten/Legal:** rechtmäßige Sprecher- und Audioerhebung, Aufzeichnung/Transkript, Retention, Disclosure, Datasetlizenz und erlaubte Länder/Ziele. Ohne Grundlage bleibt PSTN real `BLOCKED`.
4. **Sicherer Testbetrieb:** ausschließlich ENV-Namen, niemals Secrets; TEST_ALLOWLIST, Country-Deny, Budgetgrenze, Egress-deny und lokale Fake-Angreifer für SSRF.
5. **Mess- und Kostenfähigkeit:** kalibrierte Caller-Uhr, Event-/Usage-Korrelation, aktuelle Accounttarife, exportierbare Rechnung. Fehlende Einheit, Rate oder Rechnung ist `NOT TESTED`/`BLOCKED`, nie `0`.

S1 kann offline, mit Mocks und virtuell-SIP sicher starten. Offline, `sip_virtual` und `pstn_real` bleiben aber getrennte `transport_class`. Die Laststufen sind nur vorgeschlagene Explorationen: reale PSTN-Oberstufen benötigen jeweils Legal-, Account-, Quota- und Budgetfreigabe. Kein Ergebnis ist ein Produktionskapazitäts- oder SLO-Nachweis.

## 7. Abhängigkeiten der zehn Entscheidungen

ADR-001 bis ADR-006 sind realtimekritisch, aber auch sie werden gestuft statt kombinatorisch verglichen. B0 ist eine kontrollierte Kaskade mit Deepgram, schnellem Audit-Textkandidaten und streamingfähigem ElevenLabs-Kandidaten – alle bis G0 **NOT FROZEN**. In S4 ändert C1 Deepgram+Cartesia+genau einen alternativen Textkandidaten; isolierte TTS-/LLM-Vorläufe gehen der Kombination voraus. S5 prüft einen nativen Voice-Pfad gegen die beste *Validation*-Kaskade bei gleichem Tool-, Calendar-, CRM- und Media-Kontext. Native Voice behält nie Businessautorisierung.

ADR-007 ist eine dünne S8-Entscheidung: Temporal gegen BullMQ plus explizite Statusmaschine auf identischen gemockten Async-Effekten mit Restart, Timer, Cancel, Unknown Outcome, Replay und Versionchange. ADR-008 verlangt echte RLS- versus separate Datenbanktests. ADR-009 vergleicht gematchte Ressourcen, Region und Lifecycle, nicht Produktions-SLO. ADR-010 prüft Ereignisvollständigkeit, PII-Minimierung, Egress und tatsächlich gemessenen Telemetrieoverhead. Ein Voice-Gewinner schließt keine dieser vier ADRs.

Die im Vertrag genannten Schwellen für non-tool-Latenz, Stop-Latenz, bestätigte Felder und Sicherheitsereignisse bleiben **PROPOSED / ANNAHME**. Vor Holdout müssen sie mit Owner als `ACCEPTED`, `CHANGED` oder `REJECTED` protokolliert sein. Qualitäts-, Attempt- und Successful-Booking-Coverage gehören in die Beurteilung, damit ein nur verweigernder Agent nicht gewinnt.

## 8. Governance, Signoff und Paketbezüge

| Zeitpunkt | Verantwortlich | Verbindliches Ergebnis |
|---|---|---|
| Vor G0 | Mensch, Legal/Datenschutz, Procurement/Ops | Freigabe oder Block zu Daten, Vertrag, Region, Accounts, Budget und Testzielen |
| S0 | Claude Code nach Freigabe | Freeze-Manifest, Media-Parity, Messkalibrierung, RLS-Preflight – noch kein Messergebnis |
| S1–S8 | Harnessoperator/QA | Unveränderlicher Run-Ordner mit Manifest, JSONL, Usage, Calibration, Failures und Artefakthashes |
| Vor Holdout | Gate Owner + Mensch | Kriterien- und Gewichtungsreview vor Dateneinsicht |
| Decision Gate | ChatGPT-Review + Mensch | ADR akzeptiert, abgelehnt, superseded oder ausdrücklich offen |
| Danach | Claude Code | Nur freigegebene scoped ADRs als Implementierungsinput; kein Produktionsrelease aus Harness-PASS |

Gate-Zustände (`GO_FOR_HARNESS_IMPLEMENTATION`, `GO_FOR_AUTHORIZED_TESTS`, `HOLD_FOR_EVIDENCE`, `NO_GO`, `GO_FOR_SCOPED_ARCHITECTURE_DECISION`) sind nicht der ADR-Status. Bei unvollständiger Evidenz bleibt die ADR offen. Eine begrenzte Entscheidung – etwa nur Runtime für T0 – dokumentiert Scope, Ablaufdatum und offene Folgerungen.

Verknüpfte, geplante Geschwisterartefakte: [02 Benchmark Matrix](02_Benchmark_Matrix.md), [03 Dataset](03_German_Voice_Dataset_Specification.md), [04 Telemetry](04_Measurement_Telemetry_Specification.md), [05 Security & Failure](05_Security_Failure_Test_Plan.md), [06 Runtime](06_Runtime_Comparison_Plan.md), [07 Provider](07_Provider_Comparison_Plan.md), [08 Cost](08_Cost_Measurement_Plan.md), [09 Acceptance](09_Acceptance_Criteria.md), [10 Harness-Spezifikation](10_Claude_Code_Benchmark_Implementation_Specification.md) und [12 Decision Gate](12_Decision_Gate_Template.md).

Verbindliche Researchbasis, jeweils Stand 21.10.2026: [Voice Technology Audit](audit_baseline/04_Voice_Technology_Audit.md), [SaaS Architecture Research](audit_baseline/06_SaaS_Architecture_Research.md), [Recommended Technology Shortlist](audit_baseline/11_Recommended_Technology_Shortlist.md) und [Open Questions Validation Plan](audit_baseline/12_Open_Questions_Validation_Plan.md). Deren externe Links sind geerbte Zitate und am 22.10.2026 nicht erneut verifiziert.

> **Ausfüllregel:** Bis zu autorisierten, kalibrierten und reproduzierbaren Läufen bleiben Testresultate `NOT TESTED`, alle Mess- und Kostenzahlen `null`, Recommendation `null`, Rejected Alternative `null / NOT DECIDED` und Confidence **LOW aufgrund fehlender Tests**.
