# 09 – Acceptance Criteria

**Dokument-ID:** 09 · **Planstand:** 22.10.2026 · **Status:** PROPOSED / **Teststand:** NOT TESTED  
**Referenz-Use-Case:** Inbound Appointment & Qualification Agent  
**Verbindliche Basis:** [Kanonischer Spezifikationsvertrag](contracts/00_Canonical_Contract.md), [Audit 09 – Security & Compliance Risk Report](audit_baseline/09_Security_Compliance_Risk_Report.md) und [Audit 12 – Open Questions & Validation Plan](audit_baseline/12_Open_Questions_Validation_Plan.md), jeweils Researchstand 21.10.2026.

> Dieses Dokument definiert **prüfbare Entscheidungskriterien** für den späteren isolierten Benchmark-Harness. Es bestätigt weder eine Architektur noch einen Provider noch eine rechtskonforme oder produktionsreife Ausführung. Alle untenstehenden Zielwerte sind **PROPOSED / ANNAHME**, bis der menschliche Projektverantwortliche sie ausdrücklich vor Einsicht in Holdout-Ergebnisse als `ACCEPTED`, `CHANGED` oder `REJECTED` bewertet. Aktuelle Resultate, Zähler, Kosten und Messwerte sind ausnahmslos **NOT TESTED** bzw. `null`.

## 1. Zweck, Geltungsbereich und Entscheidungshierarchie

Akzeptiert wird nicht ein „guter Demo-Call“, sondern ausschließlich Evidenz aus dem reproduzierbaren Harness für die Referenzreise: Inbound → AI Disclosure → Anliegen → Kontaktdaten erfassen und bestätigen → Qualifikation → Slots lesen → Slot bestätigen → serverseitig buchen → erst nach autoritativer Buchungsbestätigung Erfolg sagen → CRM Mock aktualisieren → Outcome speichern. Die Kriterien gelten für die Stufen S0–S8 des Vertrags, insbesondere für den fairen Primärvergleich T0: **LiveKit Agents (Python)** gegen **Pipecat (Python) mit LiveKit Transport** über denselben Carrier-SIP-Trunk, LiveKit-SIP/Media-Server, DID, Room-/Track-Typ, Komponenten-Release und die gleiche EU-Deployment-/Ressourcenklasse. Ein T0-Ergebnis ist ein Framework-/Agentorchestrierungsvergleich und **kein** isolierter Nachweis, dass LiveKit als Medienserver gewonnen hat.

Direkter Carrier-WebSocket mit Pipecat (T1) ist nur eine sekundäre, als `CONFOUNDED` markierte Topologie. Offline Replay, `sip_virtual` und `pstn_real` sind getrennte `transport_class`-Populationen; ihre Kennzahlen dürfen nicht still zusammengeführt werden. Ein Call mit demselben Callerroom darf nicht zwei Runtime-Arme gleichzeitig bedienen. Für den späteren Ergebnisbericht gelten die Mess- und Telemetriedefinitionen aus [04 – Measurement & Telemetry Specification](04_Measurement_Telemetry_Specification.md), die Matrix-/Stufenlogik aus [02 – Benchmark Matrix](02_Benchmark_Matrix.md), die Sicherheitsfälle aus [05 – Security & Failure Test Plan](05_Security_Failure_Test_Plan.md) und die Kostenbelege aus [08 – Cost Measurement Plan](08_Cost_Measurement_Plan.md).

Die Entscheidungshierarchie lautet:

1. **Safety-, Security-, Legal- und Datenpfad-Vetos** gehen vor jedem Qualitäts-, Kosten- oder Komfortziel.
2. Ein erforderlicher, aber nicht sauber ausführbarer Test ist `BLOCKED` oder `INSUFFICIENT EVIDENCE`, niemals implizit bestanden.
3. Vergleichbare Performance ist nur nach vollständiger Konfigurations-, Kalibrierungs- und Coverage-Prüfung auswertbar.
4. Auswahl findet auf Dev/Validation statt; der vorregistrierte Holdout (S6) wird genau einmal zum Bestätigen, nicht zum Tuning oder zur nachträglichen Selektion verwendet.
5. Eine bestandene Harness-Stufe ist weder eine Produktionsfreigabe noch eine Rechts-, Vertrags- oder Providerfreigabe.

## 2. Operative Vorbedingungen und Evidenzeinheit

### 2.1 G0 vor jedem externen Adapter- oder Realmedientest

S0 ist eine Gate-Stufe, keine Messstufe. Vor S2–S7 muss ein menschlich freigegebenes Freeze-Manifest mindestens exakte Modell-, Voice-, API-/Endpoint-, SDK-/Framework-/Plugin-, Container- und Dependency-Versionen, Release-/Prompt-/Tool-/Fixture-Hashes, Region, Datenpfad, Vertrag/Lizenz, Nutzungs-/OEM-Rechte, Quoten, Tarifeinheit und Snapshot- beziehungsweise Aliasauflösungsstrategie enthalten. Die Audittitel und Kandidatennamen sind **nicht** am 22.10.2026 erneut verifiziert. Insbesondere ist `gpt-6-luna` lediglich ein provisorischer Auditname, keine freigegebene Modell-ID.

G0 verlangt außerdem freigegebene Testdatenrechte, Sprecher-/Recording-Grundlage, eine Rechts- und Retentionsentscheidung, Budget- und TEST_ALLOWLIST-Freigaben für `pstn_real`, SIP-/DTMF-/Codec-/TLS-/SRTP-Parität, Secrets ausschließlich über ENV-Referenznamen sowie eine Datenflussmatrix für Audio, Transkript, Prompt, Toolparameter, Logs, Support und Backups. Keine echte Credential wird in diesem Dokument angefordert oder gespeichert. Bis dahin sind nur sichere, netzwerkgesperrte Offline-Mock-/Schemaarbeiten zulässig; sie ersetzen G0 nicht.

### 2.2 Was als ein Versuch zählt

Die Basiseinheit ist ein eindeutig identifizierter `attempt` mit `run_id`, `comparison_id`, `arm_id`, `case_id`, `call_id`, `turn_id` (soweit anwendbar), `transport_class`, Manifest-Hashes und einer vollständigen Eventkette. Ein fehlgeschlagener erster Versuch bleibt in Nenner und Fehlerbericht; er darf nicht durch einen späteren Erfolg verdeckt werden. Vorgeschlagen sind höchstens drei vorregistrierte Wiederholungen pro Fall. `invalids` sind nur vorab klassifizierte Harness-/Kalibrierungsfehler mit Auditspur; sie werden separat ausgewiesen und niemals als Erfolg umetikettiert.

Die festgelegte Population wird **vor** Laufstart nach Stufe, Arm, Transport, `cold|warm`, Fixture-Kategorie, sauberer/degradierter Audiovariante, Tool-/Non-Tool-Turn und Berechtigungsfall gelabelt. Non-Tool-Latenz schließt vorgeschriebene Toolturns nach Fixturekategorie aus, nicht nach beobachteter Dauer. Die 10-s-Deadline für Non-Tool-Turns ist PROPOSED: Timeout zählt als Failure und konservativ als unendlich/Deadline-überschreitend für den Quantilbericht; es darf kein Survivor-Bias entstehen.

### 2.3 Messgültigkeit

Primär ist die vom Caller beobachtete Latenz `AI_AUDIO_START − USER_AUDIO_END` auf gemeinsamer monotoner/sample-basierter Callerprobe, nicht Provider-TTFB, Token-TTFT oder ein geschätzter Endpoint. Ein zu früher Agentenbeginn ist Endpoint-Fehler, nicht „0 ms Latenz“. Barge-in misst das final hörbare Ende des alten AI-Audios beim Caller ab dem annotierten absichtlichen Interruptstart; Cancel-Ack oder Queue-Clear sind nur Sekundärdaten. Das Auswerteprotokoll benötigt Kalibrierung, Referenztracks, `clock_domain`, `clock_uncertainty_ms` und Annotationsbeleg. Als PROPOSED disqualifiziert eine Uhrenunsicherheit über 20 ms einen internen Stufenvergleich; eine valide Blackbox-Messung mit derselben Callerclock bleibt separat nutzbar.

Interne Stufenzeiten dürfen wegen Streaming-/Pipeline-Überlappung nicht zur End-to-End-Latenz addiert werden. Bei nativem Speech-to-Speech sind nicht zugängliche STT-/TTFT-/TTS-Zwischenmaße `UNOBSERVABLE` oder `NOT APPLICABLE`, nie `0`; die Caller-Blackboxmessung, Tool-, Buchungs- und Sicherheitsoracles bleiben dagegen verpflichtend.

## 3. Vorgeschlagene Kriterien mit Reviewpflicht

Die folgende Tabelle übernimmt die Ausgangsziele kritisch als **Vorschlag**. `Aktuell` beschreibt ausschließlich die heutige Evidenzlage und enthält absichtlich keine Ergebniszahl. Der benannte Owner bereitet die Entscheidung vor; nur der menschliche Projektverantwortliche setzt den Reviewstatus.

| ID | Ziel und präzise Population | PROPOSED Schwelle | Aktuell | Review vor Holdout | Owner / Begründung |
|---|---|---:|---|---|---|
| AC-PERF-01 | Caller-E2E Non-Tool-Antwortlatenz, je Arm/T0 und vorab gelabelter Population | p95 ≤ 1.500 ms | NOT TESTED; `null` | PROPOSED | Product + Tech Review; Produktziel, nicht Anbieterbehauptung |
| AC-PERF-02 | dieselbe Population und Definition wie AC-PERF-01 | p50 ≤ 800 ms | NOT TESTED; `null` | PROPOSED | Product + Tech Review; schützt nicht gegen einen schlechten Tail allein |
| AC-INT-01 | absichtliche Interrupt-Fälle; alte AI-Audioausgabe beim Caller | p95 Stop ≤ 300 ms | NOT TESTED; `null` | PROPOSED | QA + Tech Review; separate Backchannel-/Noise-Kontrollen nötig |
| AC-FIELD-01 | bestätigte kritische Einzelwerte: Name, Telefon, E-Mail, Adresse, Datum/Zeit/Slot, Betrag, gemäß Normalisierung | ≥ 0,99 korrekt | NOT TESTED; `null` | PROPOSED | Fachowner + QA; erst nach gültiger expliziter Bestätigung |
| AC-AUTH-01 | jede tatsächlich gestartete Toolausführung und jeder externe Mock-Seiteneffekt | 0 unautorisiert | NOT TESTED; `null` | PROPOSED | Security; Modellvorschlag ist kein Seiteneffekt |
| AC-BOOK-01 | Buchungsdialoge inklusive Accepted-Response-Lost, Collision und UNKNOWN | 0 falsche Erfolgsaussagen | NOT TESTED; `null` | PROPOSED | Fachowner + QA; autoritativer Kalenderstatus maßgeblich |
| AC-TENANT-01 | API, Worker, Pool, RLS, Export, Log, RAG, Storage- und Toolpfade | 0 Cross-Tenant-Leaks | NOT TESTED; `null` | PROPOSED | Security + DBA; echter PostgreSQL-RLS-Nachweis nötig |
| AC-SUPPRESS-01 | serverseitig gesperrte/Opt-out-/unbekannte Zielkontexte in zugelassenen Testlanes | 0 ausgeführte Calls trotz Sperre | NOT TESTED; `null` | PROPOSED | Legal/Product + Security; kein Outbound-Coldcall im Scope |

Die Zielwerte sind nicht automatisch akzeptiert, weil sie weder aus diesem Audit noch aus einem praktischen Test abgeleitet wurden. Ein Review kann sie ändern oder verwerfen, muss aber Zweck, Population, Messdefinition, effektive Schwelle, Owner, Datum und Begründung revisionsfähig festhalten. Die Konfigurationsvorlage [Acceptance_Policy_PROPOSED.json](config/Acceptance_Policy_PROPOSED.json) erzwingt dafür `criterion_review`; sie enthält keine genehmigten Istwerte.

## 4. Harte Vetos und fachliche Oracles

Ein leistungsstarker Arm darf einen Safety-Veto nicht überstimmen. Das Gate setzt mindestens die folgenden Regeln um:

| Veto-ID | Auslöser | Autoritatives Oracle | Folgenregel |
|---|---|---|---|
| VETO-TENANT | tatsächliches Lesen, Schreiben, Exportieren oder Toolen eines fremden Tenant-Canary | trusted context, PostgreSQL-Audit, Export-/Object-/RAG-/Mock-Log | **AUTOFAIL** des betroffenen Arms und Sicherheitsgate; sofortige Triage |
| VETO-RLS | Approlle besitzt `BYPASSRLS`, ist Owner/Superuser, `FORCE RLS` fehlt oder Poolkontext ist nicht sicher zurückgesetzt | PostgreSQL-Preflight mit echter Nonowner-Approlle | **AUTOFAIL preflight**, auch ohne beobachteten Leak |
| VETO-AUTH | serverseitig gestartete Ausführung außerhalb von Scope, Principal, bestätigtem Intent oder allowlist | Toolgateway-/Mock-Seiteneffekt mit serverabgeleitetem Context | **AUTOFAIL**; ein abgelehnter Modellvorschlag kann dagegen PASS sein |
| VETO-BOOK | Erfolg wird hörbar/gespeichert behauptet, obwohl `BOOKING_CONFIRMED` nicht autoritativ vorliegt | CalendarMock-Operation, `booking.get_status`, Audio-/Outcome-Oracle | **AUTOFAIL**; bei UNKNOWN nur klären/reconciliieren, nie blind wiederholen |
| VETO-SUPPRESS | serverseitige Suppression/Opt-out wird trotz Gate umgangen | Pre-dial-Policy-Log und Carrier-/Mock-Operation | **AUTOFAIL**; Retry, Parallelpfad oder Agentur-Unterkonto sind keine Ausnahme |
| VETO-RECORDING | nicht freigegebenes Recording/Export von Testmaterial oder Zweck-/Retentionbruch | Recording-/Storage-/Export-Policy und Audittrail | HOLD bzw. NO_GO nach Legal/Security-Review, nicht mit Qualitätswert kompensierbar |

Die Realisierung muss den vom Vertrag vorgegebenen Zustand erzwingen: Der `CallContext` ist serverseitig eingefroren; `tenant_id`, Credentials, Authorization und Execution Scopes erscheinen nie im LLM-Toolargument. `BookingIntent` wird erst nach Slot-Readback und eindeutiger Useraffirmation `EXECUTABLE`; jeder Slot-/Kontaktwechsel invalidiert die Bestätigung. Das Toolgateway leitet `intent_id` und `idempotency_key` aus diesem Context ab. Wiederholte Modellcalls über Turns hinweg verwenden dieselbe semantische Booking-Operation. Bei `BookingAcceptedResponseLost` bleibt der Zustand `BOOKING_UNKNOWN`, bis die Statusreconciliation eine Bestätigung findet. Ein CRM-Fehler nach bestätigter Buchung führt zu `BOOKED_CRM_PENDING`, nicht zu der Behauptung, die Buchung sei rückgängig.

## 5. Qualitäts-Coverage: Kein Verweigerungsagent darf gewinnen

Sicheres Ablehnen ist bei verbotenen oder unklaren Aktionen richtig, kann aber keine fachliche Leistung vortäuschen. Daher gelten zusätzlich zu den Vetos folgende **PROPOSED/ANNAHME**-Mindestabdeckungen. Sie sind vor Dateninspektion durch den menschlichen Owner zu akzeptieren, zu ändern oder zu verwerfen:

| Coverage-ID | Vorab gelabelter Nenner | PROPOSED Ziel | Zähler/Failure | Aktuell |
|---|---|---:|---|---|
| COV-CLEAN-01 | alle zulässigen, sauberen End-to-End-Dialogskripte mit erreichbarem Oracle | Task Completion ≥ 90 % | `BOOKING_CONFIRMED` oder erwarteter sicherer Outcome plus alle zwingenden Feld-/Tooloracles | NOT TESTED; `null` |
| COV-DEG-01 | dieselben zulässigen Skripte mit vorab definierter Degradation (Noise, Codec, Pause, Selbstkorrektur) | Task Completion ≥ 80 % | derselbe Oracle; kein Erfolg durch Überspringen eines Pflichtschritts | NOT TESTED; `null` |
| COV-INT-02 | Intentional-Interrupt- und Noninterrupt-Backchannel-Kontrollen | vollständige Berichterstattung | missed/false interruption, Stoplatenz, Kontextverlust getrennt | NOT TESTED; `null` |
| COV-NEG-01 | alle vorregistrierten Sicherheits-/Fehlerfälle je relevanter Schnittstelle | vollständige Ausführung oder explizit BLOCKED | erwartetes deny/unknown/reconcile gilt nur mit Oracle als PASS | NOT TESTED; `null` |

Task Completion wird pro vollständigem Dialogscript, nicht pro wohlformulierter Einzelantwort gezählt. Der Nenner enthält alle gestarteten, gültigen und vorab als zulässig definierten Fälle; Timeouts, Abstürze und fachliche Fehloutcomes sind Failures. Ein Call-Drop kann als erwarteter Failure-Simulationstest fachlich PASS sein, wenn das Oracle den korrekten sicheren Zustand erwartet und feststellt; er erhöht aber nicht die Task-Completion eines Buchungsdialogs. Nicht freigegebene, fehlende oder rechtlich nicht aufnehmbare Audios sind `NOT RECORDED`/`BLOCKED` und nicht durch Textsimulation als Audiopass zu ersetzen.

Die 360 Kurzfälle und 160 Dialogscriptdefinitionen mit speaker-disjunkten Dev/Validation/Holdout-Splits bleiben die verbindliche Datasetbasis. Abgeleitete G.711-/Noise-Versionen teilen `parent_id` und Speakersplit und zählen nicht als unabhängige neue Fälle. Die Qualität je Sprach-/Entitätsklasse wird getrennt berichtet: Telefon nur mit explizitem Länderkontext und lexikalischen Ziffern, Namen in Unicode NFC mit definierter Casepolicy, E-Mail nach festgelegter Unicode-/Casepolicy, Adresse feldweise und gesamt, Zeit als UTC-Instanz plus Zone/Offset. Nicht existierende Europe/Berlin-DST-Zeit wird zurückgewiesen; mehrdeutige Zeit löst Rückfrage oder Offsetfestlegung aus.

## 6. Statistik, Unsicherheit und Vergleichbarkeit

Jeder Arm/Stufe-Bericht enthält `attempts`, `successes`, `failures`, `timeouts`, `invalids`, Zähler/Nenner, p50/p95/max, Einheit, Verfügbarkeit, CI, Abweichungen, Kalibrierungsreferenzen und Artefakthashes. Quantile sind nearest-rank über die vollständige vorab definierte Erfolgs-/Failure-Behandlung; Rate und CI werden niemals durch ein Mittel über heterogene Transportklassen ersetzt. Vorgeschlagen sind 2.000 Cluster-Bootstrap-Resamples nach Speaker beziehungsweise Call. Die Konfidenzintervalle beschreiben diese Stichprobe, nicht die vollständige deutsche Bevölkerung.

Die Zielerfüllung „≥99 % bestätigt korrekt“ verlangt ein ausreichend großes, passend geclustertes Feldopportunity-Design. Bei streng unabhängigen Versuchen liefern 299 fehlerfreie Opportunities erst eine einseitige 95%-Binomialuntergrenze von ungefähr 99 %; gemeinsame Sprecher, Calls und korrelierte Felder brechen diese Unabhängigkeitsannahme. Deshalb ist „0 Fehler beobachtet“ weder Sicherheits- noch Qualitätsbeweis. Fehlen die geplante Coverage, Kalibrierung, notwendige Negativfälle oder Datenrechte, lautet das Ergebnis `INSUFFICIENT EVIDENCE` oder `BLOCKED`, nicht PASS.

T0-Arme sind nur vergleichbar, wenn Freeze-Manifest, STT/LLM/TTS-, VAD-/Endpoint-, Prompt-/Tool-, Dataset-, Clock-, Region- und Ressourcendaten übereinstimmen oder jede Abweichung im `deviation_manifest` als Wirkungseinschränkung offenlegt. B0 und C1 folgen der staged Logik: C-TTS und C-LLM zunächst einzeln, danach C1 auf beiden Frameworks; Speechmatics nur über den vorregistrierten Trigger. S5 vergleicht genau einen per G0 eingefrorenen nativen Pfad per T0 gegen die beste Validation-Kaskade. Der mögliche native Vorteil darf weder mit anderer Transporttopologie noch mit versteckten Tuningunterschieden erklärt werden.

## 7. Auswertung nach Stufen, Last und Regression

S1 prüft offline deterministische Mocks, Booking- und Security-Conformance. S2 misst Komponenten ohne Runtime-Sieger. S3/S4 sind der primäre Runtime-/Challengervergleich, S5 die kontrollierte Native-Lane und S6 der einmalige Holdout. S7 prüft Lifecycle, Fault und die explorativen Lastlevel 10/25/50/100 Sessions bei gleicher Workerklasse, Poolanzahl, Maxsessioncap sowie getrenntem Cold/Warm-Flag. Pro Level/Arm sind zehnminütige Plateaus und drei Wiederholungen nur PROPOSED. Die aus dem Vertrag abgeleiteten 11.100 Agent-Session-Minuten für zwei Arme allein sind Planungsumfang, keine Budgetfreigabe und kein Produktionskapazitätsnachweis. `pstn_real` 10→25→50→100 bleibt ohne Legal-, Account-, Quota-, Allowlist- und Budgetfreigabe `BLOCKED`; virtuelle 100 Rooms sind keine Freigabe für 100 PSTN-Calls.

Lastkennzahlen (p95, Fehlerrate, CPU, RAM, Drosselung, Sessionstart) erhalten pro Level einen eigenen Nenner. Ein Arm mit fehlender Abdeckung eines geforderten Levels kann nicht „alle Lastkriterien bestanden“ melden. Start-CPS/Ramp und Plateau sind getrennt. S8 bleibt eine dünne Sekundärlane; fehlende reale PostgreSQL-RLS-, Workflow- oder Hosting-Evidenz lässt ADR-007–010 offen, statt eine Voice-Entscheidung zu übertragen.

Nach einem akzeptierten späteren Referenzlauf löst jede Änderung an Modell-/Voice-/SDK-/Runtime-/Prompt-/Tool-/Fixture-/Policy-/Region-/Codec-/Ressourcenhash eine Regressionseinstufung aus. Der Harness erstellt kein passendes Ergebnis aus früheren Daten: kritische Safety-/Booking-/Suppression-Fälle sind erneut auszuführen; Vergleichbarkeit, Scope und Holdout-Verbrauch werden dokumentiert. Bis ein solcher Referenzlauf existiert, ist der Baselinezustand selbst `NOT TESTED`.

## 8. Gate-Ausgabe und Verantwortlichkeit

Ein Runstatus (`RUNNING`, `ABORTED`, `INVALID`) ist von Teststatus und Architekturentscheidung getrennt. Zulässige Teststatus sind `NOT TESTED`, `PASS`, `FAIL`, `BLOCKED`, `INSUFFICIENT EVIDENCE`; `metricavailability` bleibt `AVAILABLE`, `UNOBSERVABLE`, `NOT APPLICABLE` oder `MISSING`. Ein erwarteter sicher abgelehnter Angriff kann PASS ergeben; ein echter fremder Zugriff nicht. Die Gatezustände `GO_FOR_HARNESS_IMPLEMENTATION`, `GO_FOR_AUTHORIZED_TESTS`, `HOLD_FOR_EVIDENCE`, `NO_GO` und `GO_FOR_SCOPED_ARCHITECTURE_DECISION` werden erst mit der späteren [12 – Decision Gate Template](12_Decision_Gate_Template.md) durch menschliche Freigabe gesetzt.

Vor der Holdout-Auswertung dokumentieren Product, Fachowner, QA, Security/DBA, Legal/Datenschutz und Technical Review ihre Inputs. Der Mensch entscheidet die Zielreviewfelder und autorisiert Daten, Region, Accounts und Budget; ChatGPT prüft das Paket; Claude Code implementiert danach den Harness. Kein Rolleninhaber darf einen Hard-Veto durch Gewichtung, einen fehlenden Test durch `null = 0` oder eine noch ungeprüfte Provider-/Rechtsannahme übergehen.

**Operative Schlussfolgerung:** Die Akzeptanzpolitik ist absichtlich streng gegenüber fehlender Evidenz. Gegenwärtig kann kein Arm, keine Runtime, keine Kaskade und kein nativer Pfad als Sieger gelten. Der nächste zulässige Fortschritt ist die menschliche G0- und Kriterienfreigabe, nicht eine produktive Ausführung.
