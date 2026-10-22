# 10 – Claude Code Benchmark Implementation Specification

**Dokument-ID:** 10 · **Planstand:** 22.10.2026 · **Status:** Implementierungsspezifikation, nicht Implementierung.  
**Test- und Evidenzstand:** Sämtliche praktischen Resultate sind **NOT TESTED**; sämtliche zu erhebenden Zahlen sind `null`. **Liveausführung ist deaktiviert**; Modell-, Voice-, API-, SDK-, Carrier- und Vertrags-IDs sind nicht eingefroren.

> Diese Spezifikation übergibt Claude Code einen **isolierten, offline-first Benchmark- und Validation-Harness**. Sie beauftragt weder eine Produktionsplattform noch Deployment, Installation, Providerzugriff, SIP-/PSTN-Anruf oder Secretbeschaffung. Alle späteren Autorisierungen bleiben beim menschlichen Gate Owner.

Normative Quelle für IDs, Statuswerte, T0-Topologie, Dataset, Phasen und Fachautorität ist der [kanonische Vertrag](contracts/00_Canonical_Contract.md). Die Researchgrundlage stammt aus [Voice Technology Audit](audit_baseline/04_Voice_Technology_Audit.md), [SaaS Architecture Research](audit_baseline/06_SaaS_Architecture_Research.md) und [Open Questions & Validation Plan](audit_baseline/12_Open_Questions_Validation_Plan.md), jeweils Quellenstand **21.10.2026**. Deren externe URLs sind geerbte Zitate, am Planstand nicht erneut verifiziert. Dieses Dokument integriert insbesondere [01](01_Validation_Sprint_Plan.md)–[09](09_Acceptance_Criteria.md), [11](11_ADR_Templates.md) und [12](12_Decision_Gate_Template.md), ohne eine ADR zu entscheiden.

## 1. Zielbild, Scope und nicht verhandelbare Grenzen

Der einzige Fachfall lautet **Inbound Appointment & Qualification**:

`Inbound → KI-Offenlegung → Anliegen → Kontakt erfassen/rücklesen/bestätigen → Qualifikation → Slots lesen → Slot rücklesen/bestätigen → serverseitig buchen → erst nach autoritativer Bestätigung Erfolg sagen → CRM Mock aktualisieren → Outcome persistieren.`

Der Harness bewertet später drei strikt getrennte Transportklassen: `offline` (Standard: kein externer Egress), `sip_virtual` (isolierter Test-Medienpfad) und `pstn_real` (nur nach kompletter Freigabe). Reine S2-API-Komponententests nutzen zusätzlich `component_api`, ohne SIP/PSTN und nur nach eigener Provider-/Daten-/Budgetfreigabe. Ein Offline- oder SIP-virtual-Ergebnis beweist keine Carrier- oder PSTN-Eigenschaft. Outbound-Coldcalling, echte Kundenkontakte, Produktdashboard, Kampagnenlogik und Produktions-SLO sind ausdrücklich ausgeschlossen. Ein späterer Opt-in-Test wäre nur eine separate `TEST_ALLOWLIST`-Lane mit serverseitigem Pre-Dial-Policy-Gate.

Der Runtime-Primärvergleich **T0** ist exakt:

```text
freigegebener deutscher Inbound-DID / gleicher Carrieraccount / gleicher PSTN-Origination-Pfad
  → Carrier SIP-Trunk → gemeinsamer LiveKit SIP/Media-Server
  → gleichartige LiveKit Rooms und Tracks (ein Agent pro Room)
  → RT-A LiveKit Agents Python | RT-B Pipecat Python mit LiveKit Transport
  → gleicher serverseitiger Toolgateway, CalendarMock, CRMMock und Rückpfad zum Testcaller
```

Ein vertrauenswürdiger Dispatcher bindet den erwarteten Test-`call_id` serverseitig an einen Arm. Weder SIP-Header noch Callerinput, LLM-Ausgabe oder `tenant_id` dürfen den Arm wählen. Testcaller und Observer sind verschiedene Rollen. Ein T0-Befund bewertet Agent-/Orchestrierungsruntime, **nicht** LiveKit als unabhängigen Media-Server. Pipecat mit direktem Carrier-WebSocket ist ausschließlich die separate T1-Lane `FULL_TOPOLOGY` / `CONFOUNDED` und erhält eigenes Route-, Codec-, Kosten- und Regionsmanifest.

Die B0-Kandidaten (Deepgram-Nova-3-multilingual, schneller OpenAI-Textkandidat, streamingfähiger ElevenLabs-Flash/Turbo-Kandidat) bleiben Auditnamen bzw. **NOT FROZEN**. C1 hält STT konstant und kombiniert erst nach zwei Ein-Faktor-Läufen Cartesia-TTS mit genau einem freigegebenen alternativen Textkandidaten. S5 erfordert genau einen nativen Pfad über T0. Keine dieser Bezeichnungen ist eine Modell-ID, Empfehlung oder aktuelle Produktverifikation.

## 2. G0 ist eine harte Implementierungs- und Ausführungsgrenze

Vor jeder Adapterimplementierung mit Livezugang sowie vor `sip_virtual`/`pstn_real` erstellt der zuständige Mensch ein G0-Freeze-Manifest nach [contracts/freeze.schema.json](contracts/freeze.schema.json). Bis dahin darf Claude Code nur lokale, deterministische Contracts, Mocks, Schema-/Fixturevalidierung, Faultdesign und Resultattemplates bauen. Provideradapter dürfen nicht „vorsorglich“ reale IDs auflösen oder Konten ansprechen.

G0 muss pro tatsächlich verwendeter Komponente dokumentieren: exakte Modell-/Voice-/Endpoint-/API-/SDK-/Plugin-/Framework-/Container-/Dependency-ID, Lizenz und kommerzielle Rechte, Region und vollständigen Datenpfad, Retention/Training/Support/Backup, Rate-/Quota-/Usage-/Billing-Export, Snapshot oder Alias mit `resolved_meta` und Abrufzeit. Zusätzlich sind DID, Carrierroute, SIP-REGISTER-Grenze, DTMF, Codec/Resampler, Firewall, TLS/SRTP, T0-Room-/Track-Parität, Testdaten-/Recordingrechte, Budget, Country-Deny, TEST_ALLOWLIST, Callerclock-Kalibrierung, Postgresrollen und Mock-Faulthooks zu belegen.

`config/Freeze_NOT_FROZEN.example.json` ist der korrekte heutige Zustand: `live_enabled=false`, `freeze_state=NOT FROZEN`, alle Nachweise `NOT VERIFIED`, Hashes `null`. Ein Alias ohne immutable Snapshot verlangt einen Wiederholungsblock; ein stilles Auto-Upgrade invalidiert Vergleichbarkeit. Der heutige Gatezustand lautet deshalb `HOLD_FOR_EVIDENCE`, nicht „bereit für Test“.

## 3. Vorgeschlagener Paketbaum und Eigentumsgrenzen

Der nachfolgende Baum ist ein **Implementierungsplan für Python 3.12**, kein angelegtes Repository und kein Produktionsdesign. `common` definiert nur contracts und sichere Basisdienste; Runtimes importieren keinen fachlichen Autoritätscode in eigene SDK-Callbacks.

```text
/benchmark
  /voice                 # Callerprobe, audio route contract, playback markers
  /stt                   # provider-neutral STT adapter ports; no provider call before G0
  /tts                   # provider-neutral TTS adapter ports
  /runtime               # dispatcher, RT-A, RT-B, native adapter boundary, lifecycle
  /tools                 # untrusted proposal parser, authoritative gateway, confirmation policy
  /booking               # BookingIntent, CalendarMock client, reconciliation state machine
  /tenant                # trusted CallContext, RLS preflight, pool boundary, test principals
  /security              # fault catalogue runner, egress-deny contract, canary observers
  /load                  # planned ramp/plateau orchestration and resource sampler contracts
  /common                # IDs, state enums, hash/ref types, validation and immutable manifests
  /config                # loaded config/freeze/acceptance references, never secret values
  /fixtures              # schema-validated text/dialog/fault manifests; protected audio refs only
  /mocks                 # CalendarMock, CRMMock, fake carrier and fake SSRF endpoints
  /telemetry             # event normalizer, clock mapper, redaction and OTel bridge
  /results               # immutable run directory writer, aggregation, evidence export
/contracts               # JSON Schema 2020-12, immutable wire contracts
/config                  # only examples and later human-approved manifests
```

Abhängigkeiten dürfen nur in Richtung Ports gehen: Runtimes senden untrusted `ToolRequest`; `tools` hat allein Zugriff auf `CallContext`, Confirmation State und Mockclients. `tenant` emittiert Context-Referenzen, nie Credentials. `telemetry` akzeptiert nur allowgelistete Attribute und darf keine Roh-Audio-, Transkript-, Kontakt- oder Toolpayloadinhalte schreiben. `results` darf fehlende Daten nie als `0` materialisieren.

Ein Laufverzeichnis wird erst während später autorisierter Ausführung erstellt und ist danach append-only:

```text
results/<run_id>/
  manifest.json  freeze-ref.json  config-hash.txt  deviation-manifest.json
  events.jsonl   metrics.json     usage.json       failures.json
  calibration.json  protected-material-refs.json  artifact-hashes.json
```

Fehlversuche, `ABORTED`- und `INVALID`-Runs bleiben erhalten. Nicht angelegte Artefakte sind im heutigen Plan `null`/`NOT TESTED`; keine Beispiel-ID behauptet einen Lauf.

## 4. Typed DTOs und Vertrauensgrenzen (Python-Pseudocode)

Die folgenden Signaturen sind normative Pseudotypen, nicht lauffähiger Code. Alle JSON-Eingänge werden vor Gebrauch gegen das jeweilige Draft-2020-12-Schema validiert; zusätzliche Schlüssel werden abgewiesen.

Die [normative Integrationspräzisierung](contracts/Harness_Integration_Addendum.md) ergänzt die konkreten Media-/STT-/LLM-/TTS-/Native-/Runtimeports, unterscheidet interne Tool-Envelopes von Modellargumenten und definiert kontrollierte Business-Speech-Capsules. Sie ist verpflichtender Bestandteil dieser Spezifikation. Ein nativer Audiostream ohne nachgewiesene Ausgabesteuerung darf nicht als gegen falsche Buchungsbestätigung abgesichert gelten; eine Capsule-TTS-Ergänzung ist ausdrücklich als Hybrid zu messen. Die Vorlage für [Baseline-Prompt und Demo-Fachregeln](fixtures/Baseline_Prompt_and_Business_Fixture_PROPOSED.md) bleibt PROPOSED und muss vor Verwendung eingefroren werden.

```python
# Pseudocode – nicht ausführen, keine Credential-Felder
@dataclass(frozen=True)
class CallContext:
    tenant_id: TrustedTenantId
    client_id: TrustedClientId
    agent_id: TrustedAgentId
    call_id: TrustedCallId
    agent_release_id: ReleaseId
    authorized_calendar_ref: CalendarRef
    authorized_crm_ref: CrmRef
    execution_scopes: frozenset[Scope]
    serverissued_principal: PrincipalRef

@dataclass(frozen=True)
class BookingIntent:
    intent_id: IntentId                # server-derived, semantic intent
    slot_id: SlotId
    calendar_ref: CalendarRef          # only from CallContext
    confirmation_revision: ReadbackHash
    payload_hash: Sha256
    state: BookingIntentState

@dataclass(frozen=True)
class ToolRequest:
    proposal_id: ProposalId
    call_context_ref: ContextRef
    tool_name: ToolName
    arguments: UntrustedToolArguments  # no tenant/auth/scope/credential/calendar/crm/operation fields

@dataclass(frozen=True)
class ToolResult:
    authorization_decision: AuthorizationDecision
    execution_state: ExecutionState
    operation_id: OperationId | None   # gateway-issued only
    booking_state: BookingState
    crm_state: CrmState
    result_ref: ProtectedResultRef | None
```

`CallContext` wird nur vom Dispatcher bzw. authentifizierten Serverkontext ausgestellt, signiert/referenziert und an Session sowie Werkzeugzugriff gebunden. Der LLM-Adapter erhält keine `tenant_id`, Credentials, `authorization`, Scopes, Calendar-/CRM-Referenz, `intent_id` oder Idempotency-Key als Toolargument. Das ist auch für Native Speech-to-Speech zwingend: Providertranskript, Toolcall und Audio sind **untrusted evidence**, keine Autorität.

Die Wire-Contracts sind [contracts/tool_request.schema.json](contracts/tool_request.schema.json) und [contracts/tool_result.schema.json](contracts/tool_result.schema.json). Zulässige Toolnamen sind abschließend: `contact.collect_candidate`, `qualification.submit_candidate`, `calendar.list_slots`, `calendar.book_slot`, `booking.get_status`, `crm.update_contact`; `call.request_handover` ist im Primary deaktiviert. SQL, Shell, beliebige URL, Transferziel, Credential, Auth- oder Tenantfelder existieren nicht im Toolargumentschema. Ein unbekannter Schlüssel wird vor einem Adaptercall verworfen und erzeugt `TOOL_REJECTED`.

## 5. Fachliche State Machines und semantische Idempotenz

### 5.1 Contact und BookingIntent

Kontakt- und Slotdaten haben getrennte Revisionen. Der Gatewayzustand ist nicht aus der LLM-Antwort abgeleitet:

```text
Contact: EMPTY → CANDIDATE → READBACK_RENDERED → CONFIRMED
                       ↑            │                 │
             correction/negative ───┴─────────────────┘ (invalidiert zu CANDIDATE)

Booking: NONE → SLOT_READBACK → USER_AFFIRMED → EXECUTABLE
              → POST_SUBMITTED → BOOKING_CONFIRMED
                                └→ BOOKING_UNKNOWN → RECONCILING → CONFIRMED | MANUAL_PENDING
```

Nur eine endliche, aktuelle affirmative Nutzerantwort auf eine gerenderte Readback-Version macht `ContactCandidate` zu `CONFIRMED` bzw. `BookingIntent` zu `EXECUTABLE`. Korrektur, Negation, Mehrdeutigkeit, Slot- oder Kontaktdatenänderung invalidiert den vorherigen Hash. Ground Truth aus Fixture-Oracles bleibt beim Evaluator und wird nie in die Session geladen.

`operation_id` ist **pro semantischem BookingIntent**, nicht pro Turn oder Modellproposal. Der Gateway berechnet eine serverseitige Relation aus `CallContext`, autorisierter Kalenderreferenz, bestätigter Slotidentität und Intentrevision; der abgeleitete Idempotency-Key referenziert diese Operation und `payload_hash`. Wiederholte Proposals über mehrere Turns verwenden dieselbe Operation. Gleiches Key/Payload-Paar muss dasselbe autoritative Resultat liefern; derselbe Key bei abweichendem Payload ist `409 IDEMPOTENCY_CONFLICT`. Es gibt keinen blinden Retry für nichtidempotente Writes.

### 5.2 Outcome- und Reconciliation-Regeln

Gültige Fachoutcomes sind `NO_BOOKING`, `BOOKING_CONFIRMED`, `BOOKING_UNKNOWN`, `BOOKED_CRM_PENDING`, `BLOCKED` und `CALL_DROPPED`; `QUALIFIED` ist davon unabhängig. Nach `BookingAcceptedResponseLost` hat der Mock bereits committed, die Clientantwort ist aber absichtlich verloren. Der Gesprächszustand wird **BOOKING_UNKNOWN**. Der Agent darf weder Erfolg aussprechen noch erneut buchen. Nur `booking.get_status` bzw. serverseitige Reconciliation darf `BOOKING_CONFIRMED` herstellen. Ist der Kalender bestätigt und CRM scheitert/429/500, lautet das Ergebnis `BOOKED_CRM_PENDING`, niemals „nicht gebucht“.

Alle Erfolgssätze über Buchung sind durch einen Gateway-Render-Guard zu leiten: kein `BOOKING_CONFIRMED`-Resultat, kein Bestätigungssatz. Der Caller-observable Oracle prüft zugleich den geschützten Response-Ref und den CalendarMockzustand. Eine LLM-Behauptung, HTTP-200 oder ein Toolproposal ist kein Fachoracle.

## 6. CalendarMock- und CRMMock-HTTP-Verträge

Mocks sind fest deterministische Harnesskomponenten, keine Integrationsbehauptung gegenüber einem echten Kalender/CRM. Beide Runtimes teilen Fixture-Uhr `2026-10-22T08:00:00Z`, Zone `Europe/Berlin`, Slots, Delays, Fault-Schedule und externe Writer-Simulation. UTC-Maschinenzeit darf nicht in Oracles eingehen. DST: `2027-03-28 02:30 Europe/Berlin` ist zurückzuweisen; `2026-10-25 02:30` erfordert Offsetklärung.

| API | Requestautorität / Kerninput | Autoritative Antwort und Fehler |
|---|---|---|
| `GET /v1/slots` | Gateway-derived CalendarRef; Anfragefenster nur aus validierter Nutzeraussage | Slots mit `slot_id`, lokaler Zeit, Zone, Offset, UTC; keine fremden Kalenderdaten |
| `POST /v1/bookings` | Gateway sends `operation_id`, server payload hash, trusted CalendarRef, executable BookingIntent | `CONFIRMED`; gleiche Operation/Hash idem; Hashabweichung `409 IDEMPOTENCY_CONFLICT`; Slotcollision `409` |
| `GET /v1/bookings/by-operation/{operation_id}` | Operation aus serverseitigem Intentledger | `CONFIRMED`, `UNKNOWN` oder objektiv definierter manueller Klärstatus |
| `POST /v1/bookings/{id}/cancel` | Nur testonly, sicherer Testprincipal | Reset/Cleanup, kein Produktionsendpoint |
| `PATCH /v1/contacts/{server_owned_ref}` | Gateway-derived ContactRef und idempotente Operation | Update, `429` mit `Retry-After`, `500`, `invalid_field`; kein Kontakt-ID-Override |
| `POST /v1/webhooks/crm` | registrierte Credential-Referenz und geprüfter Raw Body | Signatur-, Replay- und Duplikatprüfung; Out-of-order ist kein Facherfolg |

CalendarMock erzwingt Unique-Constraint über `(tenant_id, calendar_ref, utc_slot)`. CRMMock führt dieselbe Operation idempotent und kann `429`, `500`, invalid field und signed duplicate webhook simulieren. Vorgeschlagene `read=2s`, `write=3s`, maximal zwei Read-Retries mit gebundenem Backoff/Jitter und Reconciliation-Deadline 30s sind **PROPOSED**, nicht getestete Defaults. Nichtidempotente Writes werden nicht blind wiederholt. Qualifikation ist eine deterministische Fixture-Regel, nicht freies LLM-Urteil.

## 7. Nichtproduktives Datenmodell, PostgreSQL-RLS und Poolvertrag

Die Testdatenbank ist **echtes PostgreSQL**, keine SQLite- oder In-memory-Ersatzisolation. Folgende Tabellen sind nur ein fachliches Testschemadesign: `tenant`, `test_principal`, `agent_release`, `call_context`, `contact_candidate_revision`, `booking_intent`, `calendar_slot`, `calendar_booking`, `crm_operation`, `tool_operation`, `suppression_fixture`, `event_ref`, `usage_ledger_ref`. Jede tenantfähige Tabelle trägt `tenant_id`; Beziehungen verwenden zusammengesetzte `(tenant_id, id)`-Referenzen, damit eine fremde Verknüpfung nicht nur am API-Filter scheitert.

Das RLS-Preflight muss vor einem Isolationstest nachweisen:

1. Die Laufzeitrolle ist eine Non-Owner-App-/Workerrolle, nicht Superuser und ohne `BYPASSRLS`; Migration/Owner/Admin haben getrennte Rollen.
2. RLS sowie `FORCE ROW LEVEL SECURITY` sind für jede geschützte Tabelle aktiv; Policies schützen Lesen (`USING`) **und** Einfügen/Ändern (`WITH CHECK`).
3. Der Server setzt den Tenantkontext nur transaktionslokal nach Principalvalidierung; Request/Job endet zwingend mit Rollback/Commit plus Poolreset.
4. Derselbe physische Pool-Connection-Handle wird für die Negativsequenz T-A → T-B wiederverwendet. T-B darf weder Zeilen noch `current_setting` oder Cache-/Trace-/Tool-Reste von T-A sehen.
5. Eine getrennte Observerrolle prüft den tatsächlichen DB-/Mock-Endzustand. App-Response, Toolproposal oder HTTP-Status sind nicht ausreichend.

Owner/Superuser/BYPASSRLS oder fehlendes FORCE RLS sind **AUTOFAIL preflight**, selbst ohne beobachteten Leak. Ein tatsächlicher Cross-Tenant-Read, -Write, -Export, -Storagezugriff oder Toolseiteneffekt ist `hardfailCrossTenant` / AUTOFAIL: Run stoppen, Artefakte sichern, Scope quarantänisieren. Ein absichtlich abgewiesener Angriff kann später PASS sein. T-A/T-B und optional T-C enthalten ausschließlich isolierte Fake-Canaries, nie Kundendaten oder echte Credentials.

## 8. Runtime-, Medien- und Audio-Messverträge

Die Runtimeports kapseln je Arm Sessionstart, Room-/Track-Bindung, Audioein-/ausgabe, Turncommit, Streamingadapter, Unterbrechung, Drain und Sessionende. Sie emittieren die kanonischen Events aus [contracts/event.schema.json](contracts/event.schema.json); ein Normalizer ordnet runtime-/providerinterne Ereignisse auf die gemeinsame Sequenz ab. Der Adapter darf keine provider- oder runtimespezifischen Felder unredigiert nach OTel durchreichen.

Die primäre Latenz ist ausschließlich caller-beobachtbar:

```text
voice_latency_ms = caller.AI_AUDIO_START − caller.USER_AUDIO_END
barge_stop_ms    = caller.AI_OLD_AUDIO_END − caller.INTERRUPT_START
```

`USER_AUDIO_END` ist ein annotiertes reales Sprachende auf dem Referenztrack, nicht VAD/Endpoint. `AI_AUDIO_START` ist der erste hörbare valide Audioabschnitt beim selben Caller. Die Callerprobe führt Referenz- und Returned-Agent-Track über eine gemeinsame monotonic Sampleclock; Testcaller und Observer sind getrennt. `AUDIO_STOPPED`, Cancellation-Ack und Room-Queue-Clear sind nur Diagnoseevents. Eine frühe, semantisch unzulässige Antwort ist Endpointfailure, keine `0 ms`-Latenz. Filler bleibt als eigener Start relevant, zusätzlich wird `meaningful_response_start` gegen Gaming erfasst.

Vor vergleichbaren Stages dokumentiert ein Kalibrieradapter Referenzsignal, Sample-/Resampler-Rate, Codec, Echo-/Jitterbufferprüfung, Mappingunsicherheit und geschützte Kalibrierreferenz. Clock-Uncertainty über **PROPOSED 20 ms** macht interne Stagevergleiche `INVALID`; ein gleichclockiger Caller-Blackboxwert bleibt getrennt sichtbar. Roh-Audio und -transkript gehören nie in JSONL/OTel. Sie werden, falls Rechte G0 erlauben, nur als geschützte Materialreferenz mit Hash/ACL/Retention geführt.

Interne Messpunkte sind `TURN_COMMITTED`, `STT_FINAL`, `LLM_REQUESTED`, `LLM_FIRST_TOKEN`, `TTS_REQUESTED`, `TTS_FIRST_AUDIO`, `AUDIO_SENT`, `AI_AUDIO_START`, plus Tool-, Booking-, Fault- und Lifecycleevents. Streamingzeiten werden wegen Überlappung nie zu E2E addiert. Native Pfade melden nicht zugängliche STT/LLM/TTS-Zwischenmaße `UNOBSERVABLE`/`NOT APPLICABLE`, niemals `0`; Caller-, Tool-, Booking- und Sicherheitsoracles bleiben Pflicht.

## 9. Fixtureloader, Transport- und Faultvertrag

Der Loader übernimmt ausschließlich schema-valide Datensätze aus [contracts/dataset_fixture.schema.json](contracts/dataset_fixture.schema.json) und [fixtures/Seed_Cases_NOT_RECORDED.jsonl](fixtures/Seed_Cases_NOT_RECORDED.jsonl). Die 18 Seeds sind synthetische Textspezifikationen, `audio:null`, `audio_status=NOT RECORDED`, `dial_allowed=false`; sie sind keine Audio- oder Calltests. Künftige Loader-Gates prüfen schema, eindeutige IDs, Parent-/Speaker-/Split-Disjointness, Rechte/Lizenz/Retention/Audiohash, Ground-Truth-/Holdout-ACL und Transportzulassung. Audioevaluation ist ohne Rechte und Audio `BLOCKED`, nicht PASS.

Der Dev/Validation/Holdout-Vertrag bleibt: 360 Kurzfälle (6×60), 30 Sprecher, Splits 120/60/180 und 160 Dialogdefinitionen 40/40/80, speaker-disjoint. Der Seed `24022026` steuert nur Reihenfolge. Holdout darf einmal in S6 laufen, erst nach menschlichem Kriterienreview und nie zum Prompt-, VAD-, Voice-, Provider- oder Schwellentuning. Wiederholungen: höchstens drei **PROPOSED**, Failure-first bleibt im Ergebnis.

`security` liest den vollständigen [Security_Failure_Cases.csv](catalogs/Security_Failure_Cases.csv) atomar ein: TEN, TOOL, BOOK, FAIL, COMP und WEB. Ein Faultplan injiziert genau einen Faultpoint, protokolliert `FAULT_INJECTED`, ruft den unabhängigen Observer und führt Cleanup aus. SSRF-Varianten verwenden nur lokale Fake-Hosts, DNS-Rebinding/Redirect-Fixtures und Egress-deny; keine Metadatenservices, Internetziele oder Drittsysteme. `hardfailCrossTenant`, `unauthExecution`, `falseSuccess` und `suppression` sind nicht durch Mittelwerte kompensierbar.

## 10. Config-, Secret- und Kostenvertrag

[contracts/config.schema.json](contracts/config.schema.json) schützt Offline-defaults. `config/Benchmark_OFFLINE.example.json` setzt `mode=offline`, `live_enabled=false`, `network_policy=DENY`, Budget-/Sessions-/Hashes-/Messwerte auf `null`, `recording_enabled=false` und `values_present=false`. Dies ist bewusst kein lauffähiger PSTN-Plan.

Secrets dürfen ausschließlich durch ENV-Namen referenziert werden, z. B. `BENCH_PG_APP_DSN`, `BENCH_CALENDAR_MOCK_TOKEN`, `BENCH_CRM_MOCK_TOKEN`, `BENCH_CARRIER_SIP_SECRET_REF`, `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `CARTESIA_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`. Kein Dokument, Log, Resultat, Fixture, Toolrequest oder CLIargument enthält ihren Wert. Der Config-Loader muss Secrets vor Event-/Result-/Usage-Serialisierung redigieren und bei nicht erlaubtem Livewert fail-closed blockieren.

Kosten nutzen [contracts/usage.schema.json](contracts/usage.schema.json), nicht Auditpreise oder Minutenproxies. Ein Adapter korreliert `USAGE_REPORTED` mit Request-/Session-/Call-leg-ID, Account, Providerprodukt, Route, Region, Originaleinheit und Evidenz. Carrier, shared Media, STT, LLM, TTS, Runtime, Analytics und Storage haben einzelne Records; Caller-Leg ist `test_execution`, Shadow-ASR/Rater `shadow_evaluation`. T0-Media wird vorab nur nach `T0_SHARED_EQUAL` oder `T0_SHARED_WEIGHTED` verteilt; T1 ist `T1_DEDICATED`. Nutzung wird erst mit Menge plus gefrorener Rate `METERED_COST_PROVISIONAL`, mit Billing-Export/Rechnung `COST_RECONCILED`. Fehlt eine Unit/Rate/Rechnung, ist der Wert `null` und die Evidenz `MISSING_*`/`BLOCKED`, nie kostenlos.

## 11. CLI-Vertrag (vorgeschlagen, nicht installiert)

Die folgenden Befehle sind **Command Contracts**, nicht auf diesem Gerät installierte oder ausgeführte Programme. Keine Zeile autorisiert Netzverkehr.

```text
bench validate --config config/Benchmark_OFFLINE.example.json
bench freeze --manifest config/Freeze_NOT_FROZEN.example.json
bench run --stage S1 --arm S1-OFFLINE --mode offline --config <approved-config>
bench report --run <run_id>
bench reconcile --run <run_id> --usage <usage-ledger>
bench gate --evidence <evidence-card-or-gate-template>
```

`bench validate` prüft nur Schemas, verbotene Secretwerte, Hash-/Freeze-/Transportreferenzen und Holdoutpolicy. `bench freeze` erstellt keine Providerabfrage; es validiert nur einen vom Menschen befüllten Freeze-Manifest. `bench run` erzeugt ohne autorisierte Voraussetzungen höchstens einen `BLOCKED`- bzw. Offline-Mock-Run. `bench report` aggregiert unveränderliche Artefakte und hält `null` erhalten. `bench reconcile` benötigt einen später bereitgestellten Billingbeleg und darf bei Fehlen nicht rechnen. `bench gate` schreibt keine ADR-Entscheidung; es prüft nur Vollständigkeit und Vetoes.

Exitcodes: `0` = Lauf vollständig und fachlich PASS, `1` = getestet und FAIL, `2` = Config/Prerequisite/BLOCKED, `3` = ABORTED oder INSUFFICIENT METRICS. Ein technischer Abschluss, ein PASS und eine Gatefreigabe sind getrennte Zustände. Jeder `bench run`-Aufruf muss `--mode` explizit führen und mit `execution_guard.mode` übereinstimmen; reine Datei-/Reportbefehle benötigen kein redundantes `--mode`. `pstn_real` wird ohne G0, human authorization, positive Budgetgrenze, Allowlist und Country-Deny deterministisch mit Code 2 verweigert.

## 12. Implementierungsreihenfolge, Milestones und DoD

| Milestone | Claude-Code-Arbeit nach Freigabe | Eingang / DoD |
|---|---|---|
| M0 – Contract Lock | Schema-Registry, IDs, Config-/Freezevalidator, forbidden-secret scan | alle vorhandenen Contracts plus neue Config/Freeze/Toolschemas validierbar; keine Liveadapter |
| M1 – Offline Fachkern | Text-fixtureloader, trusted Context issuer, Confirmation/Booking State Machine, Calendar-/CRM-Mocks | Booking idempotent, UNKNOWN/Reconciliation und `BOOKED_CRM_PENDING` als beobachtbare Offlineoracles; keine Providercalls |
| M2 – Isolation/Safety | PostgreSQL-Testschema, Nonowner-Rolle, FORCE RLS preflight, Pool- und Egress-canaries | echte RLS-Preflight; Owner/BYPASSRLS AUTOFAIL; Securitykatalog kann `BLOCKED` statt simuliertem PASS melden |
| M3 – Telemetrie | JSONL Normalizer, redaction, immutable Result-/Usagewriter, callerprobe contract | fehlende Events ⇒ MISSING/Coveragelücke, nie 0; Rohdaten nicht in Standardlogs |
| M4 – Adapter Readiness | Runtime-/STT-/LLM-/TTS-/native Portinterfaces und manifestierte deviations | nur nach komponentenbezogenem G0; B0/C1 IDs noch nicht hartcodiert |
| M5 – Autorisierte Stages | S1, dann S2–S5, anschließend Kriterienreview/S6, separat S7/S8 | Matrixreihenfolge, Transporttrennung, Holdout custody und Freezeprüfung durchgesetzt |
| M6 – Evidence Handoff | Result-/Usage-/Failure-/Deviationexports, Evidence Cards, Gate input | keinerlei Winner-/Productionclaim; alle Blöcke, `null` und `NOT TESTED` sichtbar |

**Definition of Done des Harness, nicht der Produktion:** (a) jede Schnittstelle validiert strikt und unbekannte Properties scheitern; (b) trusted Context sowie Toolgateway lassen keine modellgesteuerte Tenant-/Credential-/Scope-/Zielautorität zu; (c) Calendar/CRM-Mocks liefern externe Fachoracles für Idempotenz, Conflict, Unknown und Pending; (d) RLS wird nur mit echter Postgresrolle getestet; (e) Offline/SIP-virtual/PSTN-real sind nicht aggregierbar; (f) Caller-Messung und interne Stufenmessung sind getrennt; (g) Resultate folgen [result.schema.json](contracts/result.schema.json), Usage dem Ledgervertrag und Evidence Cards [evidence_card.schema.json](contracts/evidence_card.schema.json); (h) jedes Hard-Fail stoppt und bewahrt Artefakte; (i) Holdout bleibt gesperrt; (j) keine Secrets und keine Rohinhalte in Telemetrie.

## 13. Stages, Last und Evidenzexport

S0 ist Freeze/Parität/Kalibrierung, S1 Offline-Conformance, S2 Komponenten, S3 B0-T0, S4 C1-T0, S5 ein nativer T0-Pfad, S6 finaler Holdout, S7 Lifecycle/Last und S8 dünne Workflow-/Tenant-/Hosting-/Observability-Entscheidungen. S7 verwendet nur als **PROPOSED** je Arm 10/25/50/100 Sessions, zehnminütige Plateaus und drei Wiederholungen. Daraus resultieren für zwei Runtimearme allein `3 × 10 × (10+25+50+100) × 2 = 11.100` Agent-Session-Minuten; das ist weder Budget noch PSTN-Freigabe noch Produktionskapazität. `pstn_real` steigt nur 10→25→50→100 und nur nach Legal-, Account-, Quota-, Budget- und Allowlist-Gate. Nicht freigegebene Stufen sind `BLOCKED`.

Evidence Export umfasst pro Arm/Stage Manifest, JSONL, Resultat, Usage, Kalibrierreferenz, Fault-/Observerbefund, Deviationmanifest und Artefakthashes. Metriken folgen [04](04_Measurement_Telemetry_Specification.md): p50/p95/max nur mit Zähler/Nenner, failures/timeouts/invalids sichtbar, nearest-rank über success latencies, Deadlines separat konservativ als Failure. Clusterbootstrap und Zielwerte sind PROPOSED. Safety-, Legal- und Datapath-Vetoes aus [09](09_Acceptance_Criteria.md) können nicht gewichtet werden. Evidence Cards bleiben bis zum menschlichen Review `PROPOSED`, Recommendation `null`, Rejected Alternative `null / NOT DECIDED`, Confidence LOW.

## 14. Aktuelle Blocker und Handoff

Es bestehen keine Messergebnisse und keine frei erfundene Vollständigkeit. Vor weiterem als Offline-Mock-Contractwork müssen explizit geschlossen oder blockierend dokumentiert werden:

1. G0-Verifikation aktueller Modell-/Voice-/API-/SDK-/Framework-/Plugin-/Lizenz-/Carrier-/SIP-/Datenpfad-/Tarif-/Quota-/Billingverträge und immutable bzw. wiederholbar dokumentierte IDs.
2. Freigegebene T0-DID/Carrierroute sowie SIP, TLS/SRTP, DTMF, Codec, Firewall, Room/Track, EU-Region und gleiche Hardwareklasse.
3. Rechtsgrundlage für Testaudio/Recording/Transkript, Sprecher-/Datasetrechte, Retention/ACL, zulässige Länder und DPA-/Subprocessor-Datenpfad.
4. Budgetowner, positive Ausgabengrenze, TEST_ALLOWLIST, Country-Deny, Account-/KYC-/Automation-/OEM-Rechte und echte Secrets ausschließlich nach Freigabe als ENV-Werte.
5. CalendarMock/CRMMock-Faulthooks, nichtproduktive PostgreSQL-Nonowner-Approlle, FORCE RLS, Poolreset, Observerrolle und isoliertes Egress-deny-Canarynetz.
6. Callerprobe samt Clock-/Audioannotation-Kalibrierung, protected evidence ACL sowie Request-/Call-leg-zu-Usage-/Billingkorrelation.
7. Menschlicher Kriterien-/Gewichtungsreview vor jeder Holdout-Einsicht. Ohne diesen Review bleibt S6 gesperrt.

Der Handoff folgt [12](12_Decision_Gate_Template.md): ChatGPT prüft Konsistenz; der Mensch gibt scoped G0, Daten, Budget und Testautorität frei; Claude Code implementiert lediglich den isolierten Harness; erst danach können autorisierte Runs Evidence Cards erzeugen. Ein Harness-PASS ist weder Architekturentscheidung noch Production Release.
