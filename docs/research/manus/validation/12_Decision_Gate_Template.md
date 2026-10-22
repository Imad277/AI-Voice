# 12 – Decision Gate Template

**Planstand:** 22.10.2026  
**Dokument-ID:** 12  
**Status:** Vorlage; sämtliche Evidenz und Resultate **NOT TESTED**  
**Referenz-Use-Case:** Inbound Appointment & Qualification Agent

> Dieses Gate entscheidet weder heute eine Architektur noch ist es ein Produktions-Release-Gate. Es strukturiert die spätere menschliche Entscheidung anhand eines isolierten, reproduzierbaren Harness. Eine geleerte, fehlende oder unmessbare Kennzahl ist kein Nullwert und kein Erfolg.

## 1. Zweck, Geltungsbereich und verbindliche Ausgangslage

Diese Vorlage führt die spätere Reviewfolge für zehn voneinander abgrenzbare Architekturentscheidungen zusammen: Voice Runtime, Voice-Architektur, STT, TTS, LLM-Strategie, Telefonie, Workflow Engine, Tenant-Architektur, Hosting und Observability. Sie gilt ausschließlich für den ersten Inbound-Referenzfall: Inbound-Call, KI-Disclosure, Anliegen und Kontaktdaten erfassen/bestätigen, deterministic Qualification, Kalender lesen, Slot bestätigen, serverseitig buchen, **erst nach autoritativer Bestätigung** Erfolg kommunizieren, CRM Mock nachziehen und Outcome persistieren. Cold Outbound ist ausgeschlossen. Ein optionaler Opt-in-Fall bleibt ein separat autorisierter Testpfad mit `TEST_ALLOWLIST` und serverseitigem Pre-Dial-Policy-Gate.

Normative Basis für IDs, Phasen, Status, Dataset, Toolautorität und Topologie ist der [kanonische Vertrag](contracts/00_Canonical_Contract.md). Researchbasis mit Quellenstand 21.10.2026 sind der [Market & Feasibility Report](audit_baseline/01_Executive_Market_Feasibility_Report.md), der [Security & Compliance Risk Report](audit_baseline/09_Security_Compliance_Risk_Report.md) und der [Open Questions & Validation Plan](audit_baseline/12_Open_Questions_Validation_Plan.md). Ihre verlinkten Onlinequellen sind nur geerbte Audit-Zitate; sie sind am 22.10.2026 **nicht erneut verifiziert**.

Für die Runtime-Entscheidung ist T0 zwingend: gleicher freigegebener deutscher Inbound-DID, gleicher Carrieraccount und SIP-Origination-Pfad, **Carrier SIP → gemeinsamer LiveKit SIP/Media-Server → gleichartige Rooms/Tracks**. Verglichen werden LiveKit Agents (Python) und Pipecat (Python) mit LiveKit Transport. Der vertrauenswürdige Dispatcher wählt den Arm aus erwarteter Test-`call_id`; weder SIP- noch Nutzer- oder LLM-Eingaben dürfen den Arm bestimmen. Ein Room enthält genau einen Agenten; Testcaller und Observer sind getrennt. T1 mit direktem Carrier-WebSocket ist lediglich eine deklarierte, volltopologische und damit `CONFOUNDED` Secondary Lane. Ein T0-Sieger wäre kein Beweis, dass LiveKit als Medienserver überlegen ist.

Alle Testarten sind strikt zu beschriften: `offline`, `sip_virtual` oder `pstn_real`. Offline- und virtuelle SIP-Ergebnisse dürfen nicht als PSTN-Ergebnisse ausgegeben werden. Die Laststufen 10/25/50/100 sind explorativ und nur mit allen G0-Freigaben für realen PSTN-Verkehr zulässig; nicht freigegebene Ebenen werden `BLOCKED`, nie übersprungen und als bestanden markiert. Holdout-Daten sind vor der einen finalen Auswertung eingefroren und dürfen nicht für Auswahl oder Tuning verwendet werden.

## 2. Vorbedingung G0 – kein Adapter- oder Live-Test ohne Freeze

Der Gate Coordinator führt vor jeder adapterabhängigen Implementierung ein G0-Register. Safe Offline-Mockarbeit ohne Providerzugriff kann davon getrennt beginnen, aber keine Komponente ist vergleichbar, solange ihr Freeze nicht vorliegt. Jeder G0-Eintrag erhält `NOT TESTED`, `PASS`, `FAIL`, `BLOCKED` oder `INSUFFICIENT EVIDENCE`; bei diesem Planstand ist jeder Eintrag **NOT TESTED**.

| G0-Prüfobjekt | Nachweis, der vor Freigabe vorliegen muss | Entscheidungswirkung bei Fehlen | Verantwortliche Rolle |
|---|---|---|---|
| Modelle, Stimmen, SDK/API | Exakte freigegebene ID, Endpoint, Version/Dependency, Lizenz-/Vertragsstand, Region/Datenpfad, Snapshot oder Alias mit `resolved_meta`, Retrievalzeit und Repeat-Block | Betroffene Arm- oder Native-Lane `BLOCKED`; kein Auto-Upgrade oder Providerwechsel | Technical Review + Legal/Procurement |
| T0-Medienparität | Carrier-SIP, TLS/SRTP, REGISTER, DTMF, Codec/Resampler, DID, LiveKit Media/Rooms, Serverregion und Hardwareklasse | Kein Runtimevergleich; T1 nicht als Ersatzbeweis | Voice/Ops |
| Daten und Rechte | Sprecher-/Testdatenfreigabe, Zweck, Zugriff, Retention, Recording- und Transcript-Policy; keine produktiven Leads | Audiobewertung `BLOCKED`; Textfixtures bleiben `NOT RECORDED` | Datenschutz + Mensch |
| Tool-/Mockautorisierung | Trusted `CallContext`, echte PostgreSQL-Approlle ohne `BYPASSRLS`, CalendarMock/CRMMock, isolierte Canaries, Secret-ENV-Namen ohne Werte | Security/Booking-Freigabe `BLOCKED` | Security + Backend |
| Commercial/Legal | Carrier-/SaaS-/OEM-/Automationsrechte, Tarif-/Quota-/Budgetfreigabe, Datenfluss/DPA/Subprocessor-Review, fallbezogene Rechtsprüfung | `pstn_real`, Outbound-Option und Production-Gate gesperrt | Mensch + Legal + Procurement |
| Messbarkeit | Callerprobe, monotone Clock, Kalibrierung, Event-/Result-/Usage-Schema, Artefakt-Hashes und Redaction | Vergleich ohne Messintegrität `INVALID`/`INSUFFICIENT EVIDENCE` | QA/Telemetry |

Der Freeze manifestiert Modell-/Voice-/Framework-/Plugin-/Container-/Prompt-/Tool-/Fixturehashes, Region, Parameter und Dependency-Herkunft. Fehlt ein unveränderbarer Providersnapshot, wird das Risiko ausdrücklich als eingeschränkte Reproduzierbarkeit geführt. Es darf nie durch einen aktuellen Marketingnamen, eine geschätzte Modellversion oder eine stillschweigende SDK-Aktualisierung verdeckt werden.

## 3. Evidenzpaket und Gültigkeitsregeln

Jede spätere Evidence Card muss die folgende Mindeststruktur erfüllen. Sie entspricht dem maschinenlesbaren Template `config/Decision_Gate_NOT_TESTED.example.json`; die später zuständige generische Konfigurationsschema-Datei muss JSON Schema Draft 2020-12 verwenden, Enums begrenzen, Nullable-Felder explizit machen, `required` definieren und `additionalProperties: false` setzen. Das Beispiel enthält absichtlich keine gemessenen Zahlen.

| Feldgruppe | Pflichtinhalt / Validierungsregel |
|---|---|
| Identität und Vergleich | `decision_id`, `comparison_id`, Stage, Arm, `transport_class`, Dataset-/Prompt-/Config-/Tool-/Fixturehash sowie Release. Ohne gleiche Vergleichskonfiguration nur `CONFOUNDED` oder scoped. |
| Testbasis | Vorab festgelegte Cases, Split, Wiederholungen, Random-Order-Seed, Samples/Attempts, Erfolg/Failure/Timeout/Invalid, Deviation-Manifest, Kalibrierungsreferenz und Sichtbarkeit der Zwischenmetriken. Actuals bleiben bei fehlendem Lauf `null`. |
| Ergebnis | Testzustand, Zähler/Nenner, Einheit, Availability, Quantile, 95%-KI und Rohartefakt-Hashes. `UNOBSERVABLE`, `NOT APPLICABLE` und `MISSING` sind nicht `0`. |
| Qualitäts- und Sicherheitsbeleg | Caller-Messung von tatsächlichem `USER_AUDIO_END` bis hörbarem `AI_AUDIO_START`; akustisches altes Audioende beim Caller für Barge-in; Entity-/Booking-/Tool-Oracle, Security-/Failure-Cases und Reconciliation. Provider-ACK, Token-TTFT oder LLM-JSON allein reichen nicht. |
| Betrieb und Kosten | Reproduzierbare Dev-/Debug-/On-call-Beobachtung, Drift/Exit-Aufwand, echte Usage-Einheit, Account-/Route-/Leg-Bezug, Tarifreferenz, Rechnungs-/Exportstatus. `null` Kosten bedeuten unbekannt, nie kostenlos. |
| Compliance und Daten | Datenpfad für Audio, Transcript, Prompt, Toolparameter, Ergebnis, Logs, Backups und Support; Vertrag/DPA/Lizenz, Retention/Export-ACL sowie rechtliche Scope-Grenze. |
| Schlussfolgerung | `best_alternative: null`, `rejected_alternative: null`, `selection_status: NOT DECIDED`, `recommendation: null`, `confidence: LOW`, bis menschliche Evidenzprüfung abgeschlossen ist. |

**Messintegrität.** Primäre non-tool Latenz lautet `caller AI_AUDIO_START − caller USER_AUDIO_END`; früh abgeschnittene Antworten sind Endpoint-Fehler, nicht schnelle Antworten. Stage-Latenzen dürfen wegen Streamingüberlappung nicht addiert werden. Erfolgsquantile sind nearest-rank aus erfolgreichen Latenzen; Deadline-Timeouts werden separat als Failure und für die konservative Auswertung erfasst. Bei Clock-Uncertainty über den vorgeschlagenen 20-ms-Grenzwert ist ein Stagevergleich nicht valide. In native Lanes bleiben nicht zugängliche Zwischenmetriken `UNOBSERVABLE`, während die Caller-Blackboxmetriken Pflicht bleiben.

**Statistik.** Dev/Validation dienen Auswahl und Fehleranalyse; der Sprecher-disjunkte Holdout (vorgeschlagen 180 Kurzfälle/80 Dialogskripte) wird genau einmal für die finalen vorregistrierten Kandidaten genutzt. Paired Cases, Reihenfolge-Seed `24022026`, höchstens drei vorregistrierte Wiederholungen und Failure-first-Reporting verhindern selektives Weglassen. Raten enthalten Zähler, Nenner und 95%-KI; vorgeschlagen sind 2.000 Cluster-Bootstrap-Resamples nach Sprecher/Call. Die bekannte Faustregel von 299 unabhängigen fehlerfreien Field-Opportunities stützt nur eine einseitige 95%-Untergrenze von 99 %, nicht pauschal korrelierte Felder oder absolute Sicherheit.

## 4. Ausfüllblatt je Architekturentscheidung

Für **jede** der folgenden Zeilen wird eine eigene Evidence Card angelegt. Die Vorlage trägt keine Vorauswahl ein. `B0`, `C1`, `N-OAI-BEST` und T0 sind Vergleichslabels, keine Sieger.

| Decision / ADR | Vergleichsfrage und zulässige Kandidaten | Minimaler Evidenzpfad | Initialer Eintrag |
|---|---|---|---|
| ADR-001 Voice Runtime | LiveKit Agents Python vs. Pipecat Python mit LiveKit Transport | S0 Freeze; S1 Conformance; S3 B0 T0; S4 C1 T0; S6 Holdout; S7 Lifecycle/Load | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-002 Voice Architecture | Kontrollierte Kaskade STT→LLM→TTS vs. genau ein nativer Pfad | Beste Validation-Kaskade gegen S5 N-OAI-BEST über gleiche T0-Tools/Media; S6 Holdout | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-003 STT Provider | Gefrorener Deepgram-Baselinekandidat; Speechmatics nur vorregistrierter Trigger | S2 komponentenisoliert; optionaler Branch nur bei STT-/Preis-/Datenpfadproblem | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-004 TTS Provider | Gefrorener ElevenLabs-Streamingkandidat vs. Cartesia C-TTS | S2 Ein-Faktor; S4 C1, gleicher Outputpfad, Entity-/Hör-/Barge-in-Beleg | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-005 LLM Strategy | Gefrorener schneller OpenAI-Textkandidat vs. genau ein alternativer schneller Textkandidat | S2 C-LLM einzeln; S4 C1; Tool-/Schema-/Kontextoracles; native gehört zusätzlich ADR-002 | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-006 Telephony | T0 freigegebener Carrier-SIP-Pfad; Carrierblockwechsel nur explizit | S0 SIP-/Codec-/Kosten-/Vertragsfreeze; T0 PSTN; T1 separat als voller Topologiewechsel | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-007 Workflow Engine | Temporal vs. BullMQ mit denselben gemockten asynchronen Effects | S8: Restart, Timer, Cancel, Unknown, Replay, Versionchange, idempotenter Backendzustand | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-008 Tenant Architecture | Shared PostgreSQL RLS vs. separate Test-DBs | S8 echte PostgreSQL-Rollen, `FORCE RLS`, Pool-, Export-, Restore- und Canaries-Tests; kein SQLite-Beweis | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-009 Hosting | Matched EU managed/self-hosted/hybrid Optionen | S8 Ressourcen-/Region-/Lifecycle-/Restore-/Datenpfadevidenz, kein Produktions-SLO-Claim | `NOT TESTED`, `NOT DECIDED`, Low |
| ADR-010 Observability | OTel-/Harness-Basis vs. ergänzende QA/Tracing-Option | S8 PII-/Egress-/Overhead-/Debuggability-/Retention-Beleg mit identischem Eventmodell | `NOT TESTED`, `NOT DECIDED`, Low |

Eine Evidence Card enthält wörtlich mindestens: **Decision; Candidates; Benchmark Configuration; Test Results; Failures; Operational Complexity; Cost; Compliance / Data; Lock-in; Migration / Exit; Recommendation; Confidence; Best Alternative; Rejected Alternative**. Bei fehlender Evidenz sind Testresultate und Messfelder `null`, Best/Rejected Alternative `null`, Recommendation `null`, Confidence `LOW`; der verwaltete Selektionsstatus lautet `NOT DECIDED`. Erst im überprüften Review darf eine Alternative begründet als verworfen werden.

Die Zustandsmaschine für Booking ist Teil jeder betreffenden Karte: `BookingIntent → slot_readback → user_affirmation → EXECUTABLE → authoritative POST → BOOKING_CONFIRMED | BOOKING_UNKNOWN`. Aus `BOOKING_UNKNOWN` folgt Reconciliation über `booking.get_status`, kein automatisches zweites Buchen und nie eine Erfolgsaussage. `BookingIntent` und Idempotency Key werden serverseitig pro semantischer Buchungsabsicht abgeleitet, nicht pro LLM-Toolcall. CalendarMock und CRMMock bleiben identisch für beide Arme; ein CRM-Fehler nach bestätigter Buchung erzeugt `BOOKED_CRM_PENDING`, nicht „Buchung fehlgeschlagen“.

## 5. Kriterienreview vor Dateninspektion

Der Mensch als Gate Owner markiert jeden Zielwert **vor** Zugriff auf Validation- oder Holdout-Resultate als `PROPOSED`, `ACCEPTED`, `CHANGED` oder `REJECTED`, begründet die Entscheidung und benennt den Owner. Ohne diesen Datums-/Signaturbeleg bleibt das Gate `HOLD_FOR_EVIDENCE`. Die folgenden Werte sind ausschließlich Produktannahmen, keine erreichten Werte oder Branchenstandards.

| Criterion ID | Vorgeschlagenes Ziel und Population | Reviewstatus heute | Owner/Begründung heute |
|---|---|---|---|
| CR-LAT-01 | p95 non-tool caller audible response ≤ 1.500 ms | `PROPOSED` | `null` |
| CR-LAT-02 | p50 non-tool caller audible response ≤ 800 ms | `PROPOSED` | `null` |
| CR-INT-01 | p95 intentional interrupt bis audible old-AI-stop ≤ 300 ms | `PROPOSED` | `null` |
| CR-ENT-01 | bestätigte kritische Felder ≥ 99 % korrekt, definierte Normalisierung | `PROPOSED` | `null` |
| CR-TOOL-01 | unautorisierte Ausführung = 0 | `PROPOSED` | `null` |
| CR-BOOK-01 | falsche Buchungserfolgsaussage = 0 | `PROPOSED` | `null` |
| CR-TEN-01 | Cross-Tenant-Leak = 0 | `PROPOSED` | `null` |
| CR-SUP-01 | Call trotz serverseitiger Suppression = 0 | `PROPOSED` | `null` |
| CR-TASK-01 | Task Completion clean/degraded, vorgeschlagene Floors 90 %/80 % | `PROPOSED` | `null` |

Latency-Populationen (Transport, cold/warm, tool/non-tool, Fixturekategorie), Deadline (vorgeschlagen zehn Sekunden), Mindestabdeckung und Failurebehandlung werden vorab versioniert. Refusal, Auslassung oder fehlende Toolausführung darf keinen Arm zum Qualitätsgewinner machen. Fehlende native Zwischenmetriken können `NOT APPLICABLE` sein; fehlende Pflicht-Caller-, Sicherheits- oder Bookingdaten nicht. Ein Block bei Load 50/100 begrenzt den Scope der Entscheidung; er wird nicht zu `PASS` umgedeutet.

## 6. Veto, Multi-Objective-Entscheidung und Unsicherheit

### 6.1 Nicht kompensierbare Vetoes

Die folgenden Ereignisse setzen mindestens den betroffenen Scope auf `NO_GO`; ein niedriger Preis, bessere Latenz oder ein hoher Durchschnittswert kann sie nicht aufwiegen:

1. **Tatsächlicher Cross-Tenant-Zugriff** auf Daten, Tool, Storage, Log, Export, RAG, Worker oder Cache (`AUTOFAIL`). Ein absichtlich abgewiesener Angriff kann dagegen `PASS` sein.
2. **Unautorisierte Toolausführung**, insbesondere fremdes Kalender-/CRM-Konto, Scope-/Tenant-Eskalation, Credential-/URL-/SQL-/Shell-Aktionen oder nicht erlaubter Transfer (`AUTOFAIL`). Das LLM bestimmt nie Tenant, Credential, Authorization oder Execution Scope.
3. **False Success**: Erfolgsaussage oder persistiertes „gebucht“ ohne autoritative Bestätigung, insbesondere nach Response-Loss/Unknown.
4. **Suppression-Verstoß**: ein Call trotz serverseitiger Sperre/Opt-out; jede Unklarheit ist fail-closed.
5. **Rechtliches oder Datenpfad-Veto**: fehlende Fallfreigabe, unzulässige Verarbeitung/Aufzeichnung, fehlende Rechte oder nicht akzeptierter Daten-/Subprocessorpfad.

RLS-Evidenz verlangt die reale PostgreSQL-Testdatenbank mit non-owner Approlle, `FORCE RLS`, ohne `BYPASSRLS` und mit kontrollierten Transaction-Local-Contexts. SQLite, Mockautorisation oder eine korrekt abgewiesene Anfrage beweisen die Datenbankisolation nicht allein. SSRF-Tests erfolgen nur gegen isolierte lokale Fake-Metadaten-/Attackerhosts bei Egress-Deny, inklusive Redirect- und DNS-Rebinding-Simulation; keine externen Systeme werden angegriffen.

### 6.2 Erlaubte Abwägung nach bestandenen Vetoes

Nur Kandidaten ohne Veto und mit ausreichender Abdeckung bilden die Pareto-Menge. Für diese Menge werden **vor** Dateninspektion Gewichtung, Skalierung und Tie-Break-Regel versioniert. Dimensionen sind Caller-Qualität/Entity- und Taskkorrektheit, Robustheit, Tool-/Booking-Integrität, Daten-/Vertragsfit, gemessene Kosten, Betriebsaufwand sowie Lock-in/Migration. Sicherheits-, Rechts- und Datenpfadbedingungen sind Eligibility-Kriterien, keine gewichteten Punkte.

Ein Ergebnis bleibt `HOLD_FOR_EVIDENCE`, wenn Konfidenzintervalle oder wiederholte Runs keine Unterscheidung tragen, Sprecher-/Call-Cluster stark korrelieren, Outage/Warmup/Providerthrottling die Paarung verzerren, Kalibrierung unzureichend ist oder wesentliche Deviations vorliegen. Die zulässige Aktion ist dann vorregistrierte Evidenzverlängerung mit unverändertem Holdout, nicht nachträgliches Umdefinieren des Gewinners. Bei Gleichstand kann eine **scoped** Entscheidung getroffen werden, etwa „für B0 in T0, nicht für T1/Native/Produktion“; die übrigen ADRs bleiben offen.

## 7. Gate-Status, Freigabereihenfolge und Signaturen

| Gate-Status | Zulässige Aussage | Mindestvoraussetzungen | Nicht zulässig |
|---|---|---|---|
| `HOLD_FOR_EVIDENCE` | Evidenz unvollständig, ungeeignet oder noch nicht erhoben | Default dieses Dokuments | Sieger-, Produktions- oder Compliancebehauptung |
| `GO_FOR_HARNESS_IMPLEMENTATION` | Claude Code darf den isolierten Harness gemäß freigegebenen Verträgen implementieren | G0-Teilfreigaben für sichere Offlinearbeit, konkrete Implementierungsspezifikation | Live-Provider- oder PSTN-Ausführung |
| `GO_FOR_AUTHORIZED_TESTS` | Eng begrenzte, dokumentierte Testausführung darf starten | Vollständiger einschlägiger G0, Budget/Allowlist/Region/Legal/Testdaten und Safety-Stop | Produktionsbetrieb oder allgemeines Outreach |
| `GO_FOR_SCOPED_ARCHITECTURE_DECISION` | Mensch akzeptiert eine abgegrenzte ADR-Empfehlung | Vorregistrierte Kriterien, gültige Evidence Cards, kein Veto, Signaturen | Generalisierung auf ungeprüfte Topologien oder Produktion |
| `NO_GO` | Betroffener Scope darf nicht fortgesetzt werden | Veto, bestätigter schwerer Failure oder rechtliche Unzulässigkeit | Kompensation durch Mittelwerte, Kosten oder Promise |

`GO_FOR_HARNESS_IMPLEMENTATION` ist **nicht** `GO_FOR_AUTHORIZED_TESTS`; `GO_FOR_AUTHORIZED_TESTS` ist **nicht** eine Architekturentscheidung; keine dieser Stufen ist `GO_FOR_PRODUCTION`. Ein testbarer, aber fehlender Carriervertrag oder eine fehlende Datenfreigabe bleibt ein operativer Block und wird nicht durch Sandboxergebnisse ersetzt.

**Ausfüllprotokoll (bei Planstand leer):**

| Kontrollpunkt | Record / Signatur | Status |
|---|---|---|
| ChatGPT-Review: Konsistenz, Reproduzierbarkeit, keine erfundenen Ergebnisse | `null` | `NOT TESTED` |
| Menschliche Freigabe: Kriterien, G0-Scope, Budget, Daten und Risikoakzeptanz | `null` | `NOT TESTED` |
| Security/Legal-Veto-Review | `null` | `NOT TESTED` |
| Claude-Code-Handoff: freigegebene Version, Hashes, offene Blocks | `null` | `NOT TESTED` |
| Gate-ID, Decision-Datum, Ablaufdatum und Review-Intervall | `null` | `NOT TESTED` |

Eine Freigabe erlischt bei Ablaufdatum, veränderter Modell-/SDK-/Voice-/Carrier-/Region-/Prompt-/Tool-/Dataset-/Tarifkonfiguration, verändertem Rechts-/Datenzweck oder neuem Security-Block. Der Coordinator sperrt den betroffenen Arm und verlangt erneuten Freeze beziehungsweise Review. Evidenzartefakte werden als Hash/geschützte Referenz gespeichert; OTel/Logs enthalten weder Roh-Audio, Transkripte noch Credentials. Zugriff, Export, Retention und Löschung folgen dem vorab genehmigten Datenfluss; minimaler Consentbeleg und Call-Medien werden nicht gleich behandelt.

## 8. Operatives Handoff und Querverweise

Das Gate konsumiert, aber ersetzt nicht: den [Sprint Plan](01_Validation_Sprint_Plan.md), die [Benchmark Matrix](02_Benchmark_Matrix.md), die [Dataset Specification](03_German_Voice_Dataset_Specification.md), die [Measurement & Telemetry Specification](04_Measurement_Telemetry_Specification.md), den [Security & Failure Test Plan](05_Security_Failure_Test_Plan.md), den [Runtime Comparison Plan](06_Runtime_Comparison_Plan.md), den [Provider Comparison Plan](07_Provider_Comparison_Plan.md), den [Cost Measurement Plan](08_Cost_Measurement_Plan.md), die [Acceptance Criteria](09_Acceptance_Criteria.md), die [Benchmark Implementation Specification](10_Claude_Code_Benchmark_Implementation_Specification.md) und die [ADR Templates](11_ADR_Templates.md).

Vor einem `GO_FOR_AUTHORIZED_TESTS` übergibt Claude Code einen validierten Freeze-/Config-Manifest, Fixture- und Schemahashes, offline Conformance-Report, G0-Blockliste, Testplan sowie leere immutable Result-Run-Verzeichnisse. Nach einem Run übergibt er vollständige Attempts einschließlich Failures/Invalids, JSONL-Events, Kalibrierung, Usage-Ledger, Redaction-/Retentionnachweise, Deviation-Manifest und Reconciliation-Ausgänge. Der Mensch prüft anschließend Kriterien und Vetoes; weder der Runtime-Agent noch das LLM oder der Implementierer autorisiert die Architekturentscheidung.

**G0-Blockliste am Planstand:** aktuelle Modell-/SDK-/API-/Voice-/Vertragsverifikation; T0-SIP/Media-/Codec-/Region-Parität; freigegebene Testdaten samt Recording-/Retentiongrundlage; echte PostgreSQL-RLS-Preflight; Datenfluss/DPA/Subprocessor- und Carrier-/OEM-/Quota-/Budgetfreigabe; Rechtsprüfung des Use-Case; Callerclock-/Kalibrierungsnachweis; Test-DID/Allowlist für gegebenenfalls erlaubtes PSTN. Deshalb ist der alleinige aktuelle Gate-Status **`HOLD_FOR_EVIDENCE`**.
