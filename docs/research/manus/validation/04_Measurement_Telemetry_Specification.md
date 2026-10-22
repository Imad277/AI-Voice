# 04 – Measurement & Telemetry Specification

**Dokument-ID:** 04  
**Planstand:** 22.10.2026  
**Status:** **PROPOSED / NOT TESTED** – dies ist eine Spezifikation für einen isolierten Benchmark-Harness, kein Testnachweis, keine Runtime- oder Providerentscheidung.

## 1. Zweck, Geltung und normativer Rahmen

Dieses Dokument macht für den Referenzfall **Inbound Appointment & Qualification** die Messung zwischen LiveKit Agents (Python) und Pipecat (Python mit LiveKit Transport) reproduzierbar. Es konkretisiert den kanonischen Vertrag: T0 ist derselbe freigegebene deutsche Inbound-DID, Carrier-SIP-Trunk, gemeinsame LiveKit-SIP/Media-Schicht sowie gleichartige Rooms und Tracks. Die Runtime-Auswahl wird ausschließlich durch einen vertrauenswürdigen Dispatcher getroffen, nie aus SIP-, LLM-, Caller- oder Tenant-Eingaben. Ein Ergebnis über die Framework-Orchestrierung ist daher **kein** Nachweis, dass LiveKit als Media-Server gewinnt. Direkter Carrier-WebSocket (T1) ist eine eigene, als `CONFOUNDED` markierte Sekundärtopologie.

Verbindliche Begriffe, IDs, Phasen S0–S8, Status und die Daten- bzw. Toolautorität stehen im [kanonischen Vertrag](contracts/00_Canonical_Contract.md). Das Dataset und seine Ground Truth referenzieren [03_German_Voice_Dataset_Specification.md](03_German_Voice_Dataset_Specification.md); Vergleichsarme, Abweichungen und Stages gehören in [02_Benchmark_Matrix.md](02_Benchmark_Matrix.md). Es gibt **keine** Messung, API-Ausführung, Installation oder Deployment in diesem Dokument. Die Auditbasis sind [04_Voice_Technology_Audit.md](audit_baseline/04_Voice_Technology_Audit.md), [08_Cost_Unit_Economics_Report.md](audit_baseline/08_Cost_Unit_Economics_Report.md) und [12_Open_Questions_Validation_Plan.md](audit_baseline/12_Open_Questions_Validation_Plan.md), jeweils Quellenstand 21.10.2026; alle darin enthaltenen URLs sind nur geerbte, nicht am Planstand neu verifizierte Zitate.

Die Ergebnissemantik ist strikt: `NOT TESTED`, `PASS`, `FAIL`, `BLOCKED` oder `INSUFFICIENT EVIDENCE`. Run-Status sind zusätzlich `RUNNING`, `ABORTED` und `INVALID`. Jede nicht erhobene Zahl ist `null`, niemals `0`. `UNOBSERVABLE` beschreibt eine prinzipiell nicht zugängliche Metrik (etwa native Zwischenstufen), `NOT APPLICABLE` eine nicht passende Metrik, `MISSING` eine eigentlich erwartete, aber nicht gelieferte Erhebung. Ein erforderlicher, aber nicht ausführbarer Test wird `BLOCKED`, nicht still ausgelassen.

## 2. Messarchitektur und vertrauenswürdige Zeitbasis

### 2.1 Caller-observable Primärmessung

Die maßgebliche Antwortlatenz ist nicht eine Provider- oder SDK-Zeit, sondern

> `voice_latency_ms = caller.AI_AUDIO_START − caller.USER_AUDIO_END`.

`USER_AUDIO_END` ist das in der Referenzspur annotierte Ende **tatsächlicher** Nutzersprache am Caller-Probe. `AI_AUDIO_START` ist der erste beim selben Caller hörbare, valide Agent-Audioabschnitt. Beide Zeitpunkte verwenden dieselbe monotone Sampleclock im Caller-Probe; die separate Returned-Agent-Track-Aufzeichnung dient als Evidenz. VAD-/Endpoint-Entscheidungen sind ausdrücklich nicht die Ground Truth. Der Probe muss Testcaller und Beobachter vom Agentenraum trennen und weder `call_id` noch Armwahl akzeptieren.

Der Harness kalibriert die Referenz- und Rückspur vor einer vergleichenden Stage mit einem bekannten akustischen Signal, dokumentiert `calibration_ref`, Sample-/Resampler-Rate, Codec und geschätzte Mappingunsicherheit. **PROPOSED:** Eine Uhrunsicherheit über 20 ms disqualifiziert interne Stage-Vergleiche (`INVALID`), während ein gültiger Black-Box-Wert aus derselben Callerclock weiter verwendbar ist. Echoerkennung, Codec-Delay, Jitterbuffer und eine Rückspiel-Lautstärkeprüfung gehören in das Kalibrierprotokoll; ein erkennbarer Talkback/Echo-Fall ist zu markieren und nicht als schneller Turn zu werten. Aufnahme ist nur bei freigegebener Testgrundlage zulässig; der Caller-Track ist selbst eine Aufzeichnung.

Für jeden vorab als `non_tool` klassifizierten Fixture-Turn werden p50, p95 und Maximum der erfolgreichen `voice_latency_ms` mit nearest-rank berechnet. **PROPOSED:** Der Deadlinewert beträgt 10 s. Timeout, fehlender hörbarer Beginn und frühe, semantisch unzulässige Antwort zählen als Failure; sie dürfen weder aus dem Nenner entfernt noch als 0 ms gespeichert werden. Filler wird separat annotiert: `AI_AUDIO_START` bleibt für die Caller-Wahrnehmung gültig, `meaningful_response_start` ist nur eine sekundäre Anti-Gaming-Metrik. Tool-Turns werden vorab per Fixture-Kategorie ausgeschlossen und separat ausgewertet; eine nachträgliche Entfernung langsamer Fälle ist verboten.

### 2.2 Interne Stufen, Überlappung und Transport

Zur Ursachenanalyse werden Events aus einer gemappten monotonic/UTC-Zeitdomäne erfasst:

| Kennzahl | Formel / Start- und Endereignis | Zweck und Grenze |
|---|---|---|
| Endpointing | `TURN_COMMITTED − USER_AUDIO_END` | Turn-Entscheidung, nicht Nutzerende |
| STT final | `STT_FINAL − USER_AUDIO_END` | über Referenzclock gemappt; Partial ist kein Final |
| LLM TTFT | `LLM_FIRST_TOKEN − LLM_REQUESTED` | nur bis erstem Token, nicht bis Antwortaudio |
| TTS TTFB | `TTS_FIRST_AUDIO − TTS_REQUESTED` | erster gültig dekodierter Chunk |
| Send/Playback | `AI_AUDIO_START − AUDIO_SENT` | Media-/Playback-Beobachtung, soweit kalibrierbar |
| Transport | explizit deklarierte, beobachtbare Mediengrenze | PSTN-One-Way ohne Messpunkt: `UNOBSERVABLE` |

Streamingstufen überlappen. Ihre Differenzen dürfen **nie addiert** als End-to-End-Zeit präsentiert werden. Jede Formel führt `clock_domain`, `monotonic_ns`, UTC-Anker, Sequenz und `clock_uncertainty_ms`; eine Providerzeit ohne Zuordnung ist Analyseattribut, nicht Vergleichszeit. Native Speech-to-Speech-Arme dürfen zugängliche Zwischenereignisse melden; unzugängliche STT-/LLM-/TTS-Werte bleiben `UNOBSERVABLE`, nicht `0`. Primäre Caller-Latenz, Tool- und Bookingoracles bleiben auch für native Pfade Pflicht.

## 3. Pflichtmetriken: Zähler, Nenner und Oracles

Alle Metriken sind pro `stage`, `comparison_id`, `arm_id`, `transport_class`, Dataset-Split, Fixture-Kategorie, Netzwerkbedingung sowie cold/warm-Flag segmentierbar. Rohwerte werden nicht mit gemittelten Providerwerten ersetzt.

### 3.1 Sprache und Entitäten

* **WER:** `(Substitutionen + Deletionen + Insertionen) / Referenzwörter`; Zähler und Referenzwortnenner werden ausgewiesen. Der Textnormalisierer ist je Split eingefroren.
* **Entity accuracy nach Typ:** `exakte_korrekte_Entitäten / auswertbare_Entitäten` für Person, Telefon, E-Mail, Adresse, Datum/Uhrzeit und Geld. Jede Rate erhält zusätzlich Fehlertypen und `coverage`.
* Telefon gilt nur mit explizitem Länderkontext und vorab definierter E.164-/lexikalischer-Digits-Policy als korrekt; kein Fuzzy-Match. Name: Unicode NFC und dokumentierte Case-Policy, keine pauschale Umlaut→ae-Umwandlung. E-Mail folgt der definierten Unicode-/Case-Policy, nicht blindem Lowercasing. Adresse wird feldweise **und** als Gesamtadresse ausgewertet. Datetime verlangt UTC-Instanz, Zone, Offset und Slot; im Fixture gelten `Europe/Berlin`, die feste Fixtureclock sowie die normierten DST-Fälle. Geld wird in Decimal-Minor-Units verglichen.
* Die Bestätigung eines kritischen Felds ist eine eigene Metrik: `confirmed_correct / confirmation_opportunities`. Sie misst nicht nur ASR. Der Server muss ContactCandidate→Readback→eindeutige Nutzeraffirmation→`CONFIRMED` und jede Änderung invalidiert die Bestätigung. Ground Truth bleibt ausschließlich beim Evaluator.

### 3.2 Turn Taking und Barge-in

Ein Intentional-Interrupt ist eine vorab annotierte Unterbrechungsgelegenheit; Backchannel-Controls und Denkpausen besitzen eigene Tags. Die **PROPOSED** Akustikdefinition enthält ein 100-ms-Stillefenster und erfordert die Kalibrierung gegen Echo. Die Quoten sind:

| Metrik | Zähler / Nenner | Failure-Entscheidung |
|---|---|---|
| False endpoint rate | vorzeitig abgeschlossene Turns / annotierte Nicht-Enden | Pause, Backchannel oder Teilphrase wird als Ende committed |
| Late endpoint rate | Endpunkte nach zulässiger Verzögerung / echte Nutzerenden | zu spätes Commit nach Ground-Truth-Ende |
| Missed interruption | nicht gestoppte Intentional-Interrupts / Interrupt-Gelegenheiten | alte AI-Audioausgabe bleibt hörbar |
| False interruption | ungerechtfertigte Stops / Non-interrupt-Controls | Backchannel, Echo oder Rauschen stoppt AI |
| Stop latency | `caller.AI_OLD_AUDIO_END − caller.INTERRUPT_START` | Audioende beim Caller, **nicht** Cancel-Ack |
| Context loss rate | falscher oder verlorener bestätigter Dialogzustand / geprüfte Folgeturns | Wiederholung, falsche Referenz oder verlorene Korrektur |

Die Stop-Latenz misst das letzte hörbare Sample der **alten** AI-Antwort; `AUDIO_STOPPED`, TTS-Cancel-Ack und Room-Queue-Clear sind nur Diagnosezeiten. Negative Werte, unannotierte Echoereignisse und fehlende Referenzspuren sind `INVALID` oder `MISSING`, keine günstigen Nullwerte.

### 3.3 Tools, Buchung und Sicherheitsoracles

Die Modellseite kann nur eine Proposal erzeugen. `tenant_id`, Credentials, Scopes, Kalender-/CRM-Referenz, Intent-ID und Idempotenzschlüssel stammen ausschließlich aus dem eingefrorenen `CallContext` im Toolgateway. Gemessen werden:

* **Toolwahl / Parameter:** korrekte autorisierte Proposal bzw. korrekt kanonische Parameter über die vorab erwarteten Toolgelegenheiten. LLM-JSON-Syntax genügt nicht.
* **Unauthorized action attempts:** Zahl nicht autorisierter Proposals **und** Zahl autorisierter, tatsächlich ausgeführter Seiteneffekte getrennt. Ein korrekt abgelehntes Angriffsproposal kann `PASS` sein; jede ausgeführte fremde/unerlaubte Aktion ist Sicherheits-`FAIL` und bei Cross-Tenant-Zugriff `AUTOFAIL`.
* **Duplikate / Timeout / Unknown:** doppelte Wirkung pro `operation_id`, fachlich korrekte bounded-Timeoutbehandlung, `BOOKING_UNKNOWN` ohne Erfolgsaussage und erfolgreiche Reconciliation jeweils mit fachlichem Backendoracle. Das Modell darf diese Ausgänge nicht selbst deklarieren.
* **Booking:** richtiger Slot, Zeitzone, Konfliktbehandlung, Retry und No-double-booking gegen CalendarMock-Unique-Constraint. `POST booking` mit gleicher Intent-/Payloadhash-Kombination muss dieselbe bestätigte Buchung ergeben; gleicher Schlüssel bei anderem Payload erzeugt `IDEMPOTENCY_CONFLICT`. Bei „accepted then response lost“ ist der Zustand bis `GET bookingbyoperation` `UNKNOWN`. Erst `BOOKING_CONFIRMED` erlaubt eine Erfolgsaussage; bestätigte Buchung plus CRM-Ausfall ergibt `BOOKED_CRM_PENDING`, nicht eine rückwirkend verneinte Buchung.

Für Tests gelten CalendarMock und CRMMock als authoritative, mit identischer Fixtureclock und Fehlerszenarien für beide Arme. Tenantisolation wird nur mit echten PostgreSQL-Rollen, `FORCE RLS`, nicht-owner-Approlle und transaktionalem Kontext geprüft. SQLite oder ein Mock belegen keine RLS-Isolation. Einen Cross-Tenant-Read/-Write, unauthenticated Execution, unterdrückten Call trotz serverseitiger Sperre oder eine falsche Erfolgsmeldung zu unterdrücken ist verboten: diese Ereignisse werden separat als Hard-Fail-Flag geloggt, nicht durch einen Durchschnitt maskiert.

### 3.4 Lifecycle, Last und Ressourcen

`SESSION_REQUESTED`, `WORKER_READY`, `SESSION_STARTED`, `DRAIN_STARTED`, `SESSION_ENDED` sowie `RESOURCE_SAMPLE` ermöglichen folgende Metriken: Worker- und Cold-Start-Latenz, Session-Start, Crash-Recovery, Graceful-Shutdown- und Session-Cleanup-Rate, Drain-Dauer, CPU (vCPU oder prozentual klar benannt), RAM (MiB), parallele Sessions, Provider-Throttling und Connection-Failure-Rate. Ressourcenproben tragen Prozess-/Worker-ID als sichere Pseudonym-ID, Samplingintervall und Resource Class; sie sind keine Call- oder Tenantdaten.

S7-Last ist explorativ: 10/25/50/100 Sessions, **PROPOSED** drei Wiederholungen und 10-Minuten-Plateau pro Level/Arm, identische CPU/RAM-Klasse, Poolcount, maxsessioncap und cold/warm-Kennzeichnung. Ramp/CPS und Plateau sind getrennte Testarten. Offline, `sip_virtual` und `pstn_real` dürfen niemals aggregiert werden. Reale PSTN-Level oberhalb genehmigter Quoten/Budget-/Legal- und Allowlist-Grenzen werden `BLOCKED`; ein 100-Room-Test autorisiert keine 100 PSTN-Calls und beweist keine Produktionskapazität. Der Planumfang von 11.100 Agent-Session-Minuten für die beschriebenen Zweiarm-Plateaus ist eine **PROPOSED Rechenannahme**, kein freigegebenes Budget oder Lastnachweis.

## 4. Ereignisprotokoll, OTel und Datenschutz

Das append-only JSONL-Schema [event.schema.json](contracts/event.schema.json) ist der kanonische Eventumschlag. Er verlangt u. a. `event_id`, lückenlos steigendes `event_seq` pro Call, `run_id`, `comparison_id`, `arm_id`, `case_id`, `call_id`, optionales `turn_id`/`operation_id`, den vertrauenswürdigen Tenant, Release-/Config-/Dataset-/Prompt-Hash, Zeitdomäne, Transportklasse, Status und Fehlercode. Pflicht-Ereignisse sind mindestens `USER_AUDIO_END`, `TURN_COMMITTED`, `STT_FINAL`, `LLM_REQUESTED`, `LLM_FIRST_TOKEN`, `TOOL_PROPOSED`, `TOOL_AUTHORIZED|REJECTED`, `TOOL_STARTED|FINISHED`, `BOOKING_CONFIRMED|UNKNOWN`, `TTS_REQUESTED`, `TTS_FIRST_AUDIO`, `AI_AUDIO_START`, `INTERRUPT_START`, `AUDIO_STOPPED`, Session-/Worker- und Usage-/Fault-Events.

OTel-Spans bilden nur die technische Korrelation ab: `voice.turn`, `stt.stream`, `llm.request`, `tool.gateway`, `calendar.mock`, `crm.mock`, `tts.stream`, `media.playback`, `worker.lifecycle` und `usage.ledger`. `trace_id`/`span_id` werden als sichere technische Attribute in eine geschützte Referenzablage gemappt, nicht mit Transkript oder Audio befüllt. Asynchrone Events nutzen `operation_id` und `event_seq`, nicht die Empfangsreihenfolge; der Normalizer dedupliziert über `(run_id,event_id)` und meldet kollidierende Payloads als `INVALID`. Fehlende Teilereignisse senken die Coverage und dürfen keinen Defaultwert erzeugen.

In `safe_attributes` sind nur allowgelistete, nichtinhaltsführende Codes zulässig. Keine Roh-Audio-, Roh-/normalisierten Transkripte, E-Mail, Telefonnummer, Adresse, Credentials, JWTs, vollständigen Toolargumente oder freies Providerpayload in JSONL/OTel. Zugriffsrechte, Export-ACL, Retention und Hashes geschützter Evidenzblobs werden separat protokolliert. Eine Datenklasse oder Providerregion wird im Freeze-Manifest bestätigt, nicht aus Telemetrie vermutet.

## 5. Aggregation, Statistik und Ergebnisartefakte

Der Aggregator schreibt je Arm und Stage ein unveränderbares Resultat nach [result.schema.json](contracts/result.schema.json). Es enthält Versuchszahlen, Erfolgs-/Failure-/Timeout-/Invalid-Zähler, je Metric Zähler/Nenner, Einheit, Availability, Censoring, Coverage, CI, Dimensionen, Kalibrierreferenzen, Abweichungen und Artefakthashes. Das kompatible [Result_NOT_TESTED.example.json](config/Result_NOT_TESTED.example.json) enthält ausschließlich `NOT TESTED` und numerische `null`; es ist kein simuliertes Resultat.

Regeln für die Auswertung:

1. Reihenfolge wird mit Seed `24022026` randomisiert; derselbe Case wird gepaart zwischen Armen bewertet. Maximal drei Wiederholungen sind **PROPOSED**, der erste Fehlschlag bleibt erhalten.
2. p50/p95 verwenden nearest-rank nur über erfolgreiche Latenzen, berichten aber N und Failures separat. Deadlineouts zählen als Failure bzw. konservativ unendlich für die Entscheidung, damit kein Survivor Bias entsteht.
3. Raten nennen immer Zähler und Nenner. Datenlücken, nicht erlaubte Aufnahmen und ungültige Kalibrierung reduzieren die Abdeckung statt den Nenner unsichtbar zu verkleinern.
4. **PROPOSED:** 2.000 Cluster-Bootstrap-Resamples auf Sprecher- oder Call-Ebene mit 95%-Intervall. Abhängige Entitäten sind nicht als unabhängige Treffer auszugeben. 299 unabhängige, fehlerfreie Feldgelegenheiten wären nur eine einseitige 95%-Untergrenzenbedingung für ein 99%-Ziel; sie ersetzen weder Clustering noch Security-Negativtests.
5. Dev/Validation dienen Auswahl und Tuning; der eingefrorene Holdout wird einmalig für S6 verwendet. Kein Resultat, keine Fehlerliste und keine akustische Beobachtung aus dem Holdout darf Parameter, Prompt oder Providerwahl beeinflussen.

Kosten werden nicht aus dieser Ergebnismetrik geschätzt. `USAGE_REPORTED` referenziert stattdessen die tatsächliche Unit, Provider-/Request-/Callleg-ID, Routing, Region und Evidenz. Carrier, Media, STT, LLM, TTS, Runtime, Analytics und Storage sind getrennt; Caller-Testleg, Shared-T0-Allokation, T1, Native-Audiotoken und Shadow-ASR/Raterkosten ebenso. Fehlende Unit, Tarif oder Rechnung bleibt `null`/`MISSING` beziehungsweise `BLOCKED`; Messwerte werden erst über die Ledger-Spezifikation in [08_Cost_Measurement_Plan.md](08_Cost_Measurement_Plan.md) zu `METERED_COST_PROVISIONAL` und nach Rechnungsabgleich zu `COST_RECONCILED`.

## 6. Übergabe, DoD und operative G0-Blocks

Claude Code implementiert zuerst Schema-Validierung, Caller-Probe-/Kalibrieradapter, Eventnormalizer, Mock-/Fault-Events und Offline-Resultatwriter (S1); erst danach Provideradapter, `sip_virtual` und autorisierte `pstn_real`-Lanes. Die Integrationsstruktur, CLI-Vertrag und Resultatablage folgen [10_Claude_Code_Benchmark_Implementation_Specification.md](10_Claude_Code_Benchmark_Implementation_Specification.md). Acceptance und Hard-Veto werden in [09_Acceptance_Criteria.md](09_Acceptance_Criteria.md) vor Holdout-Inspektion menschlich als `ACCEPTED`, `CHANGED` oder `REJECTED` bewertet.

**Definition of Done für die Messschicht:** (a) beide JSON-Schemas validieren unabhängige Event-/Resultatdateien und unbekannte Schlüssel scheitern, (b) ein Offline-Faultfall erzeugt geordnete Lifecycle-/Tool-/Booking-/Failureevents ohne PII, (c) ein absichtlich fehlendes Ereignis führt zu `MISSING`/Coverageverlust statt 0, (d) Caller- und interne Latenz werden getrennt berichtet, (e) S0-Kalibrierung und alle Hashes sind referenzierbar, (f) `BLOCKED`, `INVALID` und `NOT TESTED` bleiben bis zu echter Evidenz sichtbar.

**G0 vor jeder Adapterimplementierung und vor einem Live-Pfad:** aktueller, menschlich freigegebener Freeze der Modell-/Voice-/SDK-/Endpoint-/Plugin-/Carrier-/SIP-/Codec-/TLS/SRTP-Verträge; EU-Datenpfad, Recording-/Testdatenrechtsgrundlage, DPA/Lizenz/Quoten/Budget/Allowlist; verbindliche Region und Hardwareklasse; freigegebene Sprecher-/Dialogaufnahmen und Datasetinventar; funktionierende Callerclock-Kalibrierung; echte PostgreSQL-Approlle ohne Owner/BYPASSRLS; und ein serverausgestellter Test-`CallContext` ohne LLM-Autorität. Bis dahin sind alle Live- und Providerergebnisse **NOT TESTED**. Diese Messspezifikation trifft deshalb weder eine Architekturentscheidung noch eine Aussage über reale Qualität, Kosten, Kapazität oder Compliance.
