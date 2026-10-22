# 06 – Runtime Comparison Plan

**Dokument-ID:** 06  
**Planstand:** 22.10.2026  
**Status:** PROPOSED / **NOT TESTED**  
**Scope:** Fairer Vergleich von LiveKit Agents (Python) und Pipecat (Python mit LiveKit-Transport) für den Referenzfall **Inbound Appointment & Qualification**. Dieses Dokument spezifiziert einen künftigen, isolierten Benchmark-Harness; es implementiert, deployt oder startet nichts und trifft keine Architekturentscheidung.

## 1. Entscheidung, Grenzen und verbindlicher Ausgangspunkt

Die zu beantwortende Frage lautet nicht, welcher Anbieter allgemein „besser“ ist, sondern: **Welches Python-Runtime-Framework liefert im gleichen deutschsprachigen Inbound-PSTN-Pfad die belegbar bessere Kombination aus Gesprächsverhalten, korrekter serverseitiger Fachausführung und betreibbarer Lifecycle-Operabilität?** Eine Antwort ist heute nicht vorhanden. Beide Arme und alle Resultate sind `NOT TESTED`; Messfelder bleiben `null`.

Der normative Bezug für IDs, Status, Phasen, Dataset, Toolautorität und Topologie ist der [kanonische Vertrag](contracts/00_Canonical_Contract.md). Der Ausgangspunkt ist die in [Audit 04](audit_baseline/04_Voice_Technology_Audit.md) beschriebene unterschiedliche Session-/Pipeline-Abstraktion: LiveKit Agents hat Job-/Room-/Session-Mechaniken, Pipecat Frames und Prozessorpipelines. Das ist ein Vergleich von Agentorchestrierung, **kein** isolierter Medienserver- oder Carriervergleich. [Audit 05](audit_baseline/05_Telephony_Infrastructure_Audit.md) begründet die getrennte Behandlung von SIP/RTP und Carrier-WebSocket; [Audit 11](audit_baseline/11_Recommended_Technology_Shortlist.md) enthält nur Arbeitshypothesen, keine Auswahl.

Ausgeschlossen sind Outbound-Coldcalling, ein Produktions-SLO, ein Capacity- oder SLA-Versprechen, eine Live-Migration und eine Aussage über EU-/Vertragsfähigkeit. Kein Runtime-Ergebnis darf Safety-Vetos überstimmen: Cross-Tenant-Zugriff ist `AUTOFAIL`; unautorisierte Ausführung, eine falsche Buchungserfolgsmeldung oder ein Call trotz serverseitiger Suppression sind Hard Fails. Die Fach- und Negativoracles sind in [05](05_Security_Failure_Test_Plan.md), die Akzeptanzpolitik in [09](09_Acceptance_Criteria.md) zu führen.

## 2. Zwingende G0-Pre-Implementation-Freeze-Blöcke

Vor Adapterimplementierung oder einem livefähigen Pfad muss ein Mensch die folgenden G0-Nachweise prüfen und ein versioniertes Freeze-Manifest freigeben. Diese Punkte sind **offen**, nicht stillschweigend durch die Auditberichte erfüllt:

| G0-Block | Erforderlicher Nachweis vor dem betroffenen Lauf | Aktueller Zustand / Sperrfolge |
|---|---|---|
| Carrier–SIP–Media | Freigegebener deutscher Inbound-DID, gleicher Carrieraccount/-origination-Pfad, SIP-Interoperabilität, Codec, Firewall, TLS/SRTP, DTMF und die dokumentierte Einschränkung von SIP REGISTER | `NOT TESTED`; T0 und insbesondere `pstn_real` blockiert |
| Runtime/SDK | Aktuelle, kompatible Python-, LiveKit-Agents-, Pipecat- und LiveKit-Transport-IDs, Lizenzen, Plugin-/Dependency-Lock und deren Lifecycle-Verhalten | `NOT FROZEN`; keine Auditversionsnummer als aktuelle Verifikation ausgeben |
| Modelle und Datenpfad | Exakte STT/LLM/TTS-/Voice-/Endpoint-ID, Region, Datenpfad, Retention, Snapshot-/Aliasauflösung, Quoten, Vertrags- und Lizenzlage | `NOT FROZEN`; `live_enabled=false` bis Freigabe |
| Testgrundlage | Rechtsfreigegebene Sprecher-/Audio-/Aufzeichnungsgrundlage, `TEST_ALLOWLIST`, Zeitzone Europe/Berlin, dataset-/prompt-/fixture-Hashes | Audioeval bei fehlenden Dateien `NOT RECORDED` bzw. `BLOCKED` |
| Infrastruktur und Budget | Gleiches EU-Deployment, definierte Hardwareklasse, Netzwerkgrenzen, Observability-/Retention-Policy, Kostenkonto und expliziter Maximalbetrag | Maximalbudget `null`; providerkostenpflichtige Läufe blockiert |
| Fachautorität | Echter PostgreSQL-Rollen-/RLS-Preflight, server-issued Principal, CalendarMock/CRMMock, Confirmation- und Reconciliation-Policy | Bei Owner/BYPASSRLS/fehlendem `FORCE RLS`: `AUTOFAIL`-Preflight, nicht „später testen“ |

Das Freeze-Manifest speichert mindestens Runtime- und Containerhash, Modell-/Voice-/Plugin-/Provider-Metadaten samt Retrievalzeit, Carrierroute, Region, Hardwareprofil, VAD-Parameter, Prompt-/Tool-/Fixture-/Dataset-Hashes und Abweichungen. Ein nicht immutabler Provideralias verlangt `resolved_meta` und einen Wiederholungsblock; dies reduziert die Reproduzierbarkeit. Secrets erscheinen nur als ENV-Referenznamen und niemals als Werte, etwa `BENCH_CARRIER_SIP_SECRET_REF`; weder dieses Dokument noch ein Testdialog fordert echte Credentials an.

## 3. Faire Primärtopologie T0

**T0 ist die alleinige primäre Runtimevergleichstopologie:**

```text
freigegebener deutscher Inbound-DID / gleicher Carrieraccount
  → Carrier SIP-Trunk
  → gemeinsamer LiveKit SIP-/Media-Server
  → gleichartige LiveKit Rooms und Tracks
  → Arm RT-A: LiveKit Agents (Python)
     oder Arm RT-B: Pipecat (Python, LiveKit Transport)
  → gleiche serverautoritative Tools, Mocks und Rückroute zum Caller
```

Ein vertrauenswürdiger Dispatcher ordnet nur den erwarteten, freigegebenen Test-`call_id` einem Arm zu. Armwahl wird niemals aus SIP-Headern, Callerinput, LLM-Ausgabe oder `tenant_id` abgeleitet. Jeder Room enthält genau einen Agenten; Testcaller und Observer sind getrennte Rollen. Der gleiche DID wird bei Paarvergleichen sequenziell randomisiert (`seed=24022026`); bei Lastläufen erhält jede Session genau einen Arm und keinen gemeinsamen Callerroom. Die T0-Medienkosten und die gemeinsame Media-Nutzung sind später nach einer vorab fixierten Regel gleich oder nach gemessener Nutzung zuzuordnen, nicht doppelt zu zählen.

**RT-A-B0** und **RT-B-B0** sind in S3 die kontrollierte Baseline. B0 bedeutet den noch einzufrierenden Deepgram-Nova-3-multilingual-/schnellen-OpenAI-Text-/streamingfähigen-ElevenLabs-Pfad aus dem Vertrag, nicht eine bereits verfügbare Konfiguration. S4 vergleicht auf beiden Runtimes C1 (gleiches STT, Cartesia TTS und genau ein gefrorener alternativer Textkandidat), nach einzeln attribuierbaren C-TTS- und C-LLM-Vorläufen. S5 vergleicht einen G0-freigegebenen nativen Pfad nur mit der besten **Validation**-Kaskade; S6 verwendet den vorregistrierten Holdout einmalig. Holdout-Fälle dürfen weder Runtime-, Prompt-, VAD- noch Komponentenwahl beeinflussen.

Für T0 sind identisch festzuhalten: Carrier/DID/Konto und Route, EU-Region, vCPU/RAM-/Netzklasse, OS-/Containerbasis, STT/LLM/TTS-Konfiguration, `de-DE`, Europe/Berlin, Prompt, Toolversion, CalendarMock/CRMMock, Dataset-Split, Clock-Kalibrierung, Codec und die Confirmation-Policy. Eingangsseitig bleiben 8-kHz-G.711-/PSTN-Verluste sichtbar; nach G0 wird derselbe Mono-Resampler auf 16-kHz PCM16 verwendet. Ausgangsseitig gilt 24-kHz PCM16 nur, wenn beide TTS-Adapter dies tragen, sonst ein gemeinsam unterstützter und protokollierter Codec. Eine höhere interne Rate darf keine verlorene Bandbreite als wiederhergestellt ausgeben.

Die gemeinsame VAD/Endpoint-Startpolicy ist **PROPOSED**: gleicher Silero-Modellhash und, soweit Hookparität besteht, `speech_start_min_ms=100`, `silence_end_ms=500`, `interruption_min_ms=150`; Deepgram Smartformat, Vocabulary und Endpoint-Flags werden identisch eingefroren. Frameworknative Turnmodelle sind in T0 zunächst aus. Zeigt der Parity Spike eine echte Hook-Lücke, wird sie mit Ursache, Effekt und `deviation_manifest` festgehalten; das Paar lautet `CONFOUNDED`, nicht „gleich“. Native Turnmodelle dürfen nur in einer getrennten, sekundären Optimierungslane laufen.

## 4. Secondary Lanes und bekannte Vergleichsverzerrungen

**T1** (Pipecat plus direkter Carrier-WebSocket, etwa Media Streams) ist eine zulässige, aber nichtprimäre Full-Topology-Studie. Sie braucht ein eigenes Carrier-/Preis-/Regions-/Codecmanifest und trägt `comparison_scope=FULL_TOPOLOGY`, `confounded=true`. Sie kann einen Integrationspfad bewerten, beweist aber nicht, dass Pipecat als Framework gegenüber LiveKit Agents gewinnt. Insbesondere dürfen Programmable-Voice-/Media-Stream-Preise nicht als T0-SIP-Kosten ausgegeben werden.

Ebenso sekundär sind runtimeeigene Turnmodelle, native Speech-to-Speech-Prosodie und direkte SIP-Shortcuts. Native Pfade erhalten die gleichen serverautoritativen Tools, KB, CalendarMock, Confirmation- und Caller-Messung. Nicht zugängliche Zwischenmetriken sind `UNOBSERVABLE` oder `NOT APPLICABLE`, nie `0`. Ein native Modell darf Toolvorschläge liefern, aber niemals Tenant, Principal, Credentials, Scopes, Kalenderreferenz oder Idempotency-Key bestimmen.

Mögliche gemeinsame Verzerrungen werden nicht wegoptimiert, sondern deklariert: Shared Media macht keine Aussage über den Media-Server; Cloud-/Providerpools können Warmth erzeugen; gleiche Textausgabe bedeutet nicht gleiche Prosodie; Providerlatenzen sind nicht aus Auditmarketing abzuleiten. Der Paarvergleich führt `comparison_id`, `arm_id`, Konfigurationshash, Abweichungen, Transportklasse und Kalibrierungsreferenz. Ein Vergleich mit Clock-Uncertainty über **PROPOSED** 20 ms ist für Stagenvergleiche ungültig, bleibt aber als gleichuhriger Blackboxwert separat sichtbar.

## 5. Gemeinsame Fach- und Messdurchführung

Jeder Arm führt dieselbe Inbound-Reise aus: AI Disclosure, Anliegen und Kontaktdaten, Qualifikation, Slotliste, Slot-Readback und explizite Bestätigung, serverseitige Buchung, erst danach Erfolgsaussage, CRM Mock und Outcome. `CallContext` kommt ausschließlich vom vertrauenswürdigen Backend: `tenant_id`, `client_id`, `agent_id`, `call_id`, `agent_release_id`, autorisierte Kalender-/CRM-Referenzen, Scopes und Principal. Diese Werte sind nicht Teil des Modelltoolschemas; unknown properties werden abgelehnt.

Das Toolgateway leitet `intent_id`, Berechtigungen und Idempotency-Key aus Context und semantischem BookingIntent ab. Der Agent sieht weder Ground Truth noch Confirmationtoken. Eine Kontakt-/Slotänderung invalidiert die Bestätigung. `POST booking` bestätigt idempotent nur dieselbe Operation mit demselben Payloadhash; bei verloren gegangener Antwort bleibt der Status `BOOKING_UNKNOWN`, bis `booking.get_status` autoritativ `CONFIRMED` findet. Es wird niemals blind ein zweites Mal gebucht oder Erfolg behauptet. CRM-Fehler nach bestätigter Buchung ergeben `BOOKED_CRM_PENDING`, keine Rücknahme der Buchung.

Die primäre Latenz ist callerbeobachtbar: `AI_AUDIO_START − USER_AUDIO_END` auf der gemeinsamen Caller-Monotonic-/Sampleclock. Endpointing ist kein Ersatz für tatsächlich endende Nutzersprache. Negative Frühantworten sind Endpoint-Fails, nicht künstlich niedrige Latenz. Bei Unterbrechung misst der Benchmark `final audible old-AI-audio end − intentional interrupt start` am Caller; Cancellation-Ack, TTS-Stop und Room-Queue-Clear sind nur Diagnosewerte. Die vollständigen Formeln, JSONL-Felder und Null-/Observability-Regeln stehen in [04](04_Measurement_Telemetry_Specification.md).

Pro Versuch persistiert der Harness die vorgeschriebenen Lifecycle- und Turnevents, insbesondere `SESSION_REQUESTED`, `WORKER_READY`, `SESSION_STARTED`, `USER_AUDIO_END`, `TURN_COMMITTED`, `STT_FINAL`, `LLM_REQUESTED`, `LLM_FIRST_TOKEN`, `TTS_FIRST_AUDIO`, `AI_AUDIO_START`, `DRAIN_STARTED`, `SESSION_ENDED` und `RESOURCE_SAMPLE`. Eventzeiten haben `clock_domain`, `monotonic_ns`, `clock_uncertainty_ms`, `event_seq` und sichere Attribute; keine Raw-Audioinhalte, Transkripte oder Credentials gelangen in OTel. Streamingphasen überlappen, daher werden Einzelzeiten nicht zur E2E-Latenz addiert.

Vor jeder Wiederholung setzt ein **Reset-Protokoll** die gleiche Config-/Prompt-/Fixture-Revision, Kalenderuhr, Slot-/Booking-/CRM-Zustände, Fault-Schedule und Testprincipal zurück; Reset-Ereignisse liegen außerhalb des Messfensters und werden geloggt. Neue Workerprozesse, lokale Caches und Runtime-Sessions werden pro Cold-Lauf erzeugt. Beim Warm-Lauf werden nur vorregistrierte, gleiche Health-/Warm-up-Aktionen vor Messbeginn erlaubt. Providerpool, Verbindungen, Resolver-/DNS- und Modellcache-Zustand sind je Run zu erfassen; wenn sie nicht zurücksetzbar sind, wird der Zustand deklariert und die Reihenfolge blockrandomisiert, nicht als „cachefrei“ bezeichnet. Ein fehlgeschlagener Reset macht den Versuch `INVALID`, nicht still verwertbar.

## 6. Lifecycle- und Recovery-Testkatalog

Die folgenden Cases sind für S7 geplant; jeder beginnt `NOT TESTED`, enthält genau eine Fault-Injektion, denselben Arm-übergreifenden Fixturezustand und eine erwartete, prüfbare Safety-Oracle:

| Case-ID | Injektion und Messpunkte | Erwartete sichere Beobachtung (keine Resultatbehauptung) |
|---|---|---|
| RT-LC-01 | Workerstart: `SESSION_REQUESTED→WORKER_READY→SESSION_STARTED`; getrennt cold/warm | Startup- und Sessionstartwerte messbar oder `UNOBSERVABLE`; kein fremder Context |
| RT-LC-02 | Prozesscrash vor/nach Turn-Commit bzw. vor/nach Toolstart | Aktiver Call kann verloren gehen; Verlust wird als `CALL_DROPPED`/Fehler sichtbar, keine magische Call-Rettung |
| RT-LC-03 | Crash nach bestätigter Buchung, vor Antwort/CRM | Persistenter BookingIntent erlaubt Status-Reconcile; kein zweites Booking und keine unbestätigte Erfolgsaussage |
| RT-LC-04 | Kontrolliertes `SIGTERM` bei idle und bei aktivem Call | Drain stoppt neue Zuweisungen, dokumentiert verbleibende Session/Deadline und beendet oder klassifiziert sie nachvollziehbar |
| RT-LC-05 | Geplanter Releasewechsel bei aktiven Testcalls, nicht Produktion | Alte/Neue Agent-Release-ID und Assignment sichtbar; keine stille Umleitung und kein Cross-Session-Leak |
| RT-LC-06 | Room-/Track-/Tool-/DB-Session-Cleanup nach normalem Ende, Drop und Abort | Keine verbleibenden Rooms/Tracks/Holds/Locks/Tasks über der erlaubten Cleanup-Policy; Befund als Leak erfassen |
| RT-LC-07 | Geordneter Drain unter Eingangslast | Assignment-Stop, In-flight-Verhalten, Drained-Zeit und abgewiesene Starts messen; neue Calls nicht an einen draining Worker |
| RT-LC-08 | Debug-/Trace-Korrelation bei Faults | `run_id/call_id/turn_id/operation_id` verknüpfbar, PII-/Secret-Schutz und fehlertolerantes Tracing überprüfbar |

`Crash recovery` wird daher in zwei Ebenen ausgewertet: **Session Recovery** (der Mediencall ist typischerweise nicht transparent rettbar) und **Fach-Reconciliation** (Booking-/CRM-Status aus dem serverseitigen Ledger). Nur Letzteres kann nach einem Abbruch zu einem korrekten Abschluss führen. Das verhindert, dass eine Runtime mit einer unbelegten „Recovery“-Behauptung besser erscheint.

CPU und RAM werden pro Workerprozess, Room-/Sessionzahl, cold/warm-Flag und Zeitfenster als Zeitreihe erfasst; Median/Peak/Methodik sind später berechnet, derzeit `null`. GC, Containerlimit, CPU-Throttling, Prozessrestart, offene Filedeskriptoren sowie Provider-429/Connection-Fails werden als Ursachenattribute aufgenommen. Ein Vergleich ohne identische Samplingfrequenz, cgroup-Limit, Poolcount und maximalem Sessioncap ist `CONFOUNDED`.

## 7. Exploratives Lastdesign S7

Das Arbeitsprofil **R0 (PROPOSED)** reserviert für jeden Arm denselben isolierten Workerpool mit **4 vCPU, 8 GiB RAM** pro Worker, identischem CPU-/Memory-Limit, Poolcount, Netzwerkprofil und `max_session_cap`; die konkrete Instanzklasse wird erst in G0 manifestiert. R0 ist kein Produktionssizing. Falls eine Vorprüfung begründet auf R1 wechseln muss, erhält **beide** Arme dieselbe neue Klasse und R0/R1 werden nicht zusammen gerankt.

Pro Arm sind in getrennten Durchläufen die Stufen **10, 25, 50 und 100** gleichzeitige Agent-Sessions vorgesehen. Jede Stufe hat **PROPOSED** eine zehnminütige Plateauphase und drei Wiederholungen. Daraus folgen allein für zwei Arme `3 × 10 × (10+25+50+100) × 2 = 11.100` **Agent-Session-Minuten**; das ist eine Planungsmenge, kein genehmigtes Budget und keine PSTN-Minutenrechnung. Ramp und Start-CPS werden separat vorregistriert und gemessen; sie dürfen nicht als Plateauzeit oder Concurrent-Call-Kapazität ausgegeben werden. Warm-up, Ramp-down und Fehlerretries bleiben im Ledger sichtbar, aber außerhalb einer klar gelabelten Plateauquantile.

| Transportklasse | Zweck und Zulässigkeit | Fortschrittsregel |
|---|---|---|
| `offline` | Lokales Audio-Replay, deterministische Mocks, Standard `network_deny`, keine Provider-/PSTN-Aussage | S1/S7-Logik, Tool- und Ressourceninstrumentierung möglich; kein Telephony-Qualitätsclaim |
| `sip_virtual` | Kontrollierter SIP-/Room-Pfad ohne reale PSTN-Originierung, getrennte Calleremulation | Validiert T0-Transport- und Lifecycleteile, nicht Carrierqualität oder PSTN-Billing |
| `pstn_real` | Gleicher erlaubter DID/Carrier/T0 mit Testcaller | Erst nach Legal, Accounts, KYC, Quoten, Testdaten-/Recordingfreigabe, Kostenallowlist und Budgetgate; Stufen 10→25→50→100 nacheinander |

Für `pstn_real` bedeuten nicht freigegebene höhere Stufen `BLOCKED`, niemals implizit `PASS`. Ein 100-Room-Test erlaubt keine 100 echten PSTN-Calls. Providerthrottling, CPS, parallele Carrierlegs, Runtimeworker sowie STT/TTS/LLM-Quoten bleiben getrennte Ursachen. Keine durch den Test beobachtete Stufe wird auf Produktionskapazität extrapoliert.

## 8. Operabilität, Exit und Ergebnisschema

Operative Komplexität wird als Evidenz erhoben, nicht als Eindruck bewertet. Für jeden Arm entstehen bei künftiger Umsetzung unveränderbare Worklogs mit `run_id`, Person/Role-Pseudonym, Kategorie (`adapter`, `debug`, `trace`, `failure_recovery`, `release_drain`, `on_call_simulation`), Start/Ende, Ticket-/Case-ID, Blocker, reproduzierbarer Diagnoseartefakt-Hash und Ergebnis. Die Stunden, Ticketzahl und Fehlerzeit stehen gegenwärtig auf `null`. Bewertet werden auch Featureparität, die Zahl framework-spezifischer Abweichungen und ein vorregistrierter Exit-Spike: derselbe Tool-/Mock-/Eventvertrag wird gegen einen alternativen Runtimeadapter kompiliert bzw. in einem isolierten Test umgesetzt. Das ist keine Migrationszusage; nicht belegte Exitkosten bleiben `NOT TESTED`.

Jeder Arm-/Stageresult hat mindestens `status`, `test_state`, `comparison_id`, `transport_class`, `attempts`, `successes`, `failures`, `timeouts`, `invalids`, `numerator`, `denominator`, `units`, `metricavailability`, `calibration_refs`, `deviations`, Artifact-Hashes und Kostenreferenzen. Fehlende Daten sind nicht nullte Erfolge. Die gemeinsame Ergebnis- und Eventform wird von [04](04_Measurement_Telemetry_Specification.md) definiert; Kosten werden mit [08](08_Cost_Measurement_Plan.md) aus gemessenen Einheiten und nachträglich aus Rechnung/Export abgeglichen.

| Ergebnisfeld für T0 | RT-A-B0 | RT-B-B0 | Status / Bemerkung |
|---|---:|---:|---|
| Caller-Latenz p50/p95/max (ms) | `null` | `null` | `NOT TESTED` |
| Barge-in-stop p95 (ms) | `null` | `null` | `NOT TESTED` |
| Endpoint-/STT-/LLM-/TTS-Teillatenzen | `null` | `null` | `NOT TESTED` bzw. `UNOBSERVABLE` |
| Sessionstart, Workerstart, Drain-Dauer (ms) | `null` | `null` | `NOT TESTED` |
| CPU/RAM pro Prozess/Session | `null` | `null` | `NOT TESTED` |
| Lifecycle-/Tool-/Booking-/Security-Fails | `null` | `null` | `NOT TESTED`; Safety-Fail vetoiert Ranking |
| Gemessene Entwicklungs-/Debug-/On-call-Zeit | `null` | `null` | `NOT TESTED` |
| Kosten je Scope | `null` | `null` | `NOT TESTED`; keine Tarifannahme als Verbrauch |

## 9. Auswertung, Stop-Regeln und Handoff

Je Paar gelten dieselben Cases, die Failure-first-Regel, höchstens **PROPOSED** drei Wiederholungen und der festgelegte Randomseed. Quantile werden nur mit Erfolgslatenzen als nearest-rank berichtet; Deadline-Timeouts sind zusätzlich Failures und in einer konservativen Sicht als unendlich zu behandeln, damit langsame oder abgebrochene Calls nicht aus p95 verschwinden. Rates erhalten Zähler/Nenner und 95%-CI; bei Sprecher-/Call-Korrelation ist Cluster-Bootstrap mit **PROPOSED** 2.000 Resamples auszuführen. Selection erfolgt nur aus Dev/Validation. Ein unvollständiger Instrumentierungs-, Kalibrierungs- oder Safetytest liefert `INSUFFICIENT EVIDENCE`, nicht eine implizite Rangfolge.

Der Harness stoppt den betroffenen Lauf bei Cross-Tenant-Zugriff, ausgeführter unautorisierter Aktion, falscher Erfolgsmeldung, Suppressionbruch, Secret-/PII-Leak in Telemetrie, fehlender vertrauenswürdiger Contextbindung oder Budget-/Quota-Gate. Er bewahrt Logs, Artifact-Hashes und den fehlgeschlagenen Versuch; ein Stop löscht keine Evidenz. Andere Arms dürfen nur nach Ursache, Containment und menschlicher Freigabe fortfahren. Ein funktionaler Testabschluss ist von einer Architekturfreigabe getrennt.

Die Ergebnisübergabe besteht aus den S3/S4/S5/S6/S7-Evidence-Cards, dem Deviation-/Freeze-Manifest, Resultat- und Usage-Artefakten, Sicherheitsbefunden und dem expliziten Eintrag für **ADR-001 Voice Runtime** in [11](11_ADR_Templates.md). Erst das menschliche Decision Gate in [12](12_Decision_Gate_Template.md) kann eine Zielvorgabe als `ACCEPTED`, `CHANGED` oder `REJECTED` markieren. Bis dahin lautet die Recommendation für LiveKit Agents und Pipecat gleichermaßen: **NOT DECIDED – Tests und G0 fehlen**.
