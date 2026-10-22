# 05 – Security & Failure Test Plan

**Dokument-ID:** 05  
**Planstand:** 22.10.2026  
**Status:** Spezifikation; alle Testresultate **NOT TESTED**, Messzahlen `null`  
**Referenzfall:** Inbound Appointment & Qualification Agent

## 1. Zweck, Entscheidungsgrenzen und Quellen

Dieser Plan beschreibt atomare, reproduzierbare **Negativ- und Fehlertests** für den isolierten Benchmark-Harness. Er prüft, ob die Plattform beim Inbound-Referenzablauf Mandanten, Tool-Autorität, bestätigte Buchungen und Fehlerwahrheit fail-closed behandelt. Er implementiert weder Harness noch Produktionsplattform und löst keine Calls, Provider-Requests, Installationen oder Deployments aus.

Normativ sind der [kanonische Vertrag](contracts/00_Canonical_Contract.md), insbesondere Toolkontext, CalendarMock/CRMMock, echte PostgreSQL-RLS und Statussemantik. Researchbasis mit Quellenstand 21.10.2026: [SaaS Architecture Research](audit_baseline/06_SaaS_Architecture_Research.md), [Security & Compliance Risk Report](audit_baseline/09_Security_Compliance_Risk_Report.md) und [Open Questions & Validation Plan](audit_baseline/12_Open_Questions_Validation_Plan.md). Mess- und Ergebnisfelder müssen zur [04 – Measurement & Telemetry Specification](04_Measurement_Telemetry_Specification.md) passen; Stage-, Arm- und Transportzuordnung folgen [02 – Benchmark Matrix](02_Benchmark_Matrix.md). Dataset- und Dialogfixturegrenzen stehen in [03 – German Voice Dataset Specification](03_German_Voice_Dataset_Specification.md); Qualitätsziele werden erst in [09 – Acceptance Criteria](09_Acceptance_Criteria.md) menschlich bewertet.

**Nicht Gegenstand dieses Dokuments:** eine aktuelle Provider-/SDK-/Modellprüfung, ein Penetrationstest gegen Dritte, echte Geheimnisse, Rechtsfreigabe oder eine Behauptung produktiver Kapazität. Die aktuelle Modell-, API-, SDK-, Carrier-, Lizenz-, DPA-/Datenpfad- und Vertragsprüfung ist **G0 PRE-IMPLEMENTATION-FREEZE**, nicht erledigte Evidenz.

> **Sicherheitsveto:** Ein beobachteter mandantenfremder Zugriff, eine ausgeführte unautorisierte Nebenwirkung, ein Call trotz serverseitiger Sperre oder eine gegenüber dem Caller behauptete, nicht autoritativ bestätigte Buchung ist **AUTOFAIL**. Mittelwerte, andere PASS-Fälle, spätere Kompensation oder eine LLM-Erklärung heben das nicht auf.

Der vollständige atomare Katalog liegt in [catalogs/Security_Failure_Cases.csv](catalogs/Security_Failure_Cases.csv). Jede Zeile hat `result_status=NOT TESTED`; `expected_safe_result` ist eine Erwartung, kein Ergebnis. Ein absichtlich abgelehnter Angriffsversuch kann nach späterer Durchführung **PASS** sein. Ein tatsächlich erfolgter Fremdzugriff oder unautorisierter Effekt ist nie „erwarteter Fail“, sondern AUTOFAIL.

## 2. Gemeinsame Testumgebung und vertrauenswürdige Autorität

### 2.1 Isolierte Fixtures, nicht fremde Systeme

Jede Ausführung verwendet ausschließlich testseitige Canaries und T-A/T-B, optional unzugeordnetes T-C: private Contacts, Agents, Calls, Calendar-Slots, Knowledge-Dokumente, Objekt-Referenzen sowie Fake-Credentials. Canaries sind eindeutig markiert, nicht produktiv und dürfen keine personenbezogenen Echtkontakte enthalten. Isolierte Kalender- und CRM-Mocks sind die fachlichen Gegenstellen. SSRF-Fälle laufen in einem Testnetz mit Egress-Deny und lokalen Fake-Hosts; es gibt **keine** Anfrage an Cloud-Metadaten, Internetadressen oder Systeme Dritter.

Die ausführende Testinstanz erhält den serverseitig eingefrorenen `CallContext`: `tenant_id`, `client_id`, `agent_id`, `call_id`, `agent_release_id`, `authorized_calendar_ref`, `authorized_crm_ref`, `execution_scopes`, `serverissued_principal`. Er wird ausschließlich aus dem Dispatcher bzw. authentifizierten Serverkontext abgeleitet. Weder SIP-Header, Caller-Eingabe, JWT-Claim ohne serverseitige Validierung, Retrieval-Dokument noch LLM-Toolargument bestimmen Mandant, Credentials, Scopes oder Zielintegration.

Modelltools sind auf `contact.collect_candidate`, `qualification.submit_candidate`, `calendar.list_slots`, `calendar.book_slot`, `booking.get_status`, `crm.update_contact` und im Primary deaktiviertes `call.request_handover` begrenzt. Unbekannte Properties werden abgelehnt. SQL, Shell, beliebige URL, Credential, `tenant_id`, `authorization` und Scope-Felder sind kein Teil des Modell-Toolschemas. Testkonfigurationen referenzieren ausschließlich ENV-Namen, etwa `BENCH_PG_APP_DSN`, `BENCH_CALENDAR_MOCK_TOKEN` oder `BENCH_CRM_MOCK_TOKEN`; Werte werden weder angefordert noch dokumentiert.

### 2.2 RLS- und Pool-Prüfung

Shared-RLS ist nur mit **echtem PostgreSQL** prüfbar, niemals SQLite oder einem Mock. Das G0-Preflight legt nachweislich eine Nicht-Owner-App-/Workerrolle ohne `BYPASSRLS` fest, aktiviert RLS und `FORCE ROW LEVEL SECURITY` auf allen geschützten Tabellen und trennt Migration/Admin/Superuser strikt. Owner, Superuser oder eine Approlle mit `BYPASSRLS` sind bereits ohne Leak **AUTOFAIL preflight**. Jede Request-/Job-Transaktion setzt ihren Tenantkontext transaktionslokal, prüft ihn und rollt ihn zurück. Die Pool-Fälle erzwingen die Wiederverwendung derselben physischen Verbindung nach T-A und verlangen bei T-B weder Daten noch Settings aus T-A.

Der fachliche Oracle liest mit einer separaten Test-Observerrolle exakt den Zustand der Mocks bzw. Test-DB: Quelle, Zieltenant, Referenz, Operation-ID, Buchungsstatus und Nebenwirkung. Das LLM-Output, eine Tool-Proposal oder eine erfolgreiche HTTP-Antwort allein zählt **nie** als Oracle.

## 3. Ausführungsmodi, Phasenzuordnung und Regeln

| Modus | Zulässiger Umfang | Ausschluss / Sicherheitsgrenze | Geplante Zuordnung |
|---|---|---|---|
| `offline` | Unit-/Adapter-/Mock-/PostgreSQL-RLS-Tests, deterministische Faults | Standard: Netzwerk gesperrt, keine reale SIP-/PSTN-/Provider-Aktion | S1, erste Sicherheits- und Booking-Conformance |
| `sip_virtual` | Virtueller SIP-/Media-Pfad mit Testcaller und gemeinsamen Fixtures | Kein PSTN-Leg; kein Beweis für Carrierverhalten | S1/S3–S4 für Caller-observable Safety |
| `pstn_real` | Freigegebener deutscher Inbound-DID, T0 Carrier-SIP → gemeinsamer LiveKit SIP/Media → Room | Nur nach G0, Kosten-/Quota-/Rechtsfreigabe und Test-ALLOWLIST; keine Outbound-Kaltakquise | S3–S7; nicht aktuell ausgeführt |

LiveKit Agents (Python) und Pipecat (Python mit LiveKit Transport) nutzen im Primary denselben T0-Carrier-SIP-, LiveKit-Media-, Room- und Toolpfad. Sicherheitstests, die beide Runtimes betreffen, laufen mit gleicher Fixture-/Config-/Prompt-/Toolversion getrennt je Arm. Dieselben Gates gelten vor S4-C1 (staged Challenger) und S5-native sowie erneut vor S6-Holdout; ein abweichender nativer Zwischenmetrikzugang ändert keine Tool-, Tenant-, Booking- oder Caller-Truth-Oracles. Das beweist keine Überlegenheit des Media-Servers. Ein direkter Carrier-WebSocket ist nur T1-Secondary und als `CONFOUNDED` mit eigener Route, Region, Codec- und Kostenmanifest zu kennzeichnen. Offline, SIP-virtual und PSTN-real werden in Resultaten niemals vermischt.

Inbound-`busy`, `no_answer`, `carrier_timeout` und `unknown_call_creation` sind im Inbound-Referenzablauf nicht als bereits gemessene Runtimeereignisse auszugeben. Sie werden offline gegen Carrier-Contract-Mocks geprüft; eine optionale, freigegebene Opt-in-/Provider-Contract-Lane darf sie später getrennt validieren. Sie liefern keine Latenz- oder Runtimewinner-Aussage.

## 4. Katalogfamilien und konkrete Safety-Oracles

### 4.1 TEN – Mandanten- und Datenpfadisolation

`TEN-*` deckt manipulierte Tenant-/API-/Call-/Agent-/Contact-IDs, gefälschte Worker-Jobs, Pool-Restzustand, RLS-Preflight und -Bypass, Exporte, Logs/Traces, Object-Referenzen und Retrieval-Canaries ab. Jeder Lese-, Schreib-, Export- oder Downloadversuch von T-A nach T-B muss vor Rückgabe/Seiteneffekt mit einem sicheren, nicht materialisierenden Deny enden. Der Observer zeigt: kein fremder Inhalt im Response, Cache, Exportartefakt, Trace, Workerresultat oder Toolrequest; keine T-B-Zeile wurde erzeugt/geändert.

RLS-Policies müssen sowohl `USING` als auch `WITH CHECK` relevant abdecken. Ein absichtlich schlechtes Fixture kann zeigen, dass ein Guard anschlägt, aber eine schlechte Rollen-/Policy-Konfiguration wird nicht „für die Demo“ akzeptiert. Ein nicht ausführbarer echter-PostgreSQL-Test ist **BLOCKED**, nicht PASS und nicht durch einen SQLite-Test ersetzbar.

### 4.2 TOOL – Injection, Zielbindung und Ausführungsautorität

`TOOL-*` injiziert direkte Prompttexte und Knowledge-Base-Canaries, unbekannte Argumente, fremde Integrationsreferenzen, Scope-Eskalation, Transferforderungen, Credentials und URL-Varianten. Für SSRF werden Loopback-, private-, Fake-Metadaten-, Redirect- und DNS-Rebinding-Ziele allein im isolierten Testnetz erzeugt. Die URL-Policy muss bereits vor DNS/Connect nach erlaubtem Scheme, Host, Port und aufgelöster IP fail-closed kontrollieren; Redirects werden erneut geprüft. Der Test ist bestanden, wenn kein ausgehender Request erfolgt und der Audittrail `TOOL_REJECTED` mit nicht-sensitivem Grund zeigt.

Prompt- oder KB-Injection darf eine **Proposal** erzeugen, nicht aber Autorität. Ist die Proposal vollständig abgelehnt und bleibt der externe Oracle leer, ist dies ein erwarteter PASS. Sobald `TOOL_STARTED` oder eine fremde/unerlaubte Nebenwirkung nachgewiesen wird, gilt AUTOFAIL. Gleiche Regel für Handover/Transfer: Primary deaktiviert, keine implizite Carrieraktion, keine Gebührenroute.

### 4.3 BOOK und FAIL – Geschäftsstatus vor Sprachbehauptung

Eine Kontakt- oder Slotänderung invalidiert die vorherige Bestätigung. Erst `ContactCandidate → readback → useraffirmation → CONFIRMED` und `BookingIntent → Slot-Readback → useraffirmation → EXECUTABLE` erlauben die serverseitige Aktion. Negative oder korrigierende Antwort, fehlender aktueller Readback-Hash oder fremde Calendar-Referenz führen zum Deny/erneuten Nachfragen. Ein Confirmation-Token ist keine LLM-Credential.

CalendarMock verwendet eine eindeutige `operation_id` pro **semantischem BookingIntent**, nicht pro Turn. Gleiches Operation-ID/Payload-Hash ist idempotent; gleiche ID mit abweichendem Hash erzeugt `409 IDEMPOTENCY_CONFLICT`. `BookingAcceptedResponseLost` committet vor künstlichem Disconnect, setzt den Gesprächsstatus auf `BOOKING_UNKNOWN` und erzwingt `booking.get_status`/Reconciliation. Nie blind erneut buchen, nie Erfolg sagen, solange kein autoritatives `CONFIRMED` vorliegt. Die externe Unique-Constraint `tenant + calendar + UTC slot` und der Mock-Buchungsdatensatz sind der Oracle.

STT-/LLM-/TTS-/Calendar-/CRM-Timeout, leeres oder verzögertes STT-Final, ungültiges LLM-Schema, 429, 500, Collision, Invalid-Field und Duplicate-Webhook prüfen begrenzte, fachlich sichere Degradierung. CRM-Ausfall nach bestätigter Buchung führt zu `BOOKED_CRM_PENDING`, nicht zu „Buchung fehlgeschlagen“ und nicht zu einer fälschlichen Erfolgszusage vor Calendarbestätigung. Nichtidempotente Writes erhalten keinen blinden Retry. Ein nicht bestätigter Erfolg muss Caller-observable unterbleiben: Testcaller-/Agenten-Track und renderte Antwortreferenz werden geschützt referenziert; rohe Audio-/Transkriptinhalte stehen nicht in OTel.

### 4.4 COMP/WEB – Suppression, Compliance-Controls und Webhook-Integrität

`COMP-*` validiert, dass eine serverseitige Sperre/Opt-out vor einer Aktion fail-closed wirkt, auch bei bereits eingeplantem Job, parallelem Worker oder Retry. Kein Call trotz Sperre ist harte Bedingung. Recording bleibt bis zur gesonderten Rechts-/Zweckfreigabe standardmäßig aus; ein Disclosure aktiviert es nicht. Diese Fälle sind technische Guards, keine Rechtsberatung und keine Behauptung rechtlicher Compliance.

`WEB-*` prüft registrierte Credentials, Signatur gegen Raw Body, Replayfenster, Duplikat- und Out-of-order-Dedupe. Ein ungültiges oder altes Event darf keinen Zustand oder Tool-Effekt erzeugen. Der Observer prüft persistentes Event-/Operation-Dedupe und fachlichen Endzustand, nicht nur HTTP-Status.

## 5. Standardablauf jedes atomaren Tests

1. **Precondition:** Fixturemanifest, `config_hash`, `dataset_hash` soweit relevant, Testmodus, Arm, trusted `CallContext`, Test-DB-Rolle und Mock-Reset verifizieren. Fehlendes G0/Fixture erzeugt `BLOCKED` bzw. `INVALID`, nie PASS.
2. **Mutation/Fault:** Genau einen katalogisierten Angriffsvektor oder Faultpoint aktivieren. Kombinierte Angriffe sind neue Case-IDs; damit bleibt Fehlerursache reproduzierbar.
3. **Execution:** Testdriver sendet die definierte Eingabe oder simuliert die Antwort. Der Toolgateway erzeugt serverseitig Operation-/Idempotency-IDs. Kein LLM darf Tests auswählen oder deren Oracle auswerten.
4. **Safety-Oracle:** Unabhängiger Observer prüft DB-/Mock-/Export-/Netzwerkzustand, Unique Constraints, persistente Dedupe-Keys und ggf. Caller-observable Aussage. Ausbleibende Evidenz ist `INSUFFICIENT EVIDENCE`, nicht Erfolg.
5. **Evidence:** geschützte Run-Referenzen auf `TOOL_PROPOSED`, `TOOL_AUTHORIZED`/`TOOL_REJECTED`, `TOOL_STARTED`, `TOOL_FINISHED`, `BOOKING_CONFIRMED`/`BOOKING_UNKNOWN`, `CRM_PENDING`, `FAULT_INJECTED` und `SESSION_ENDED`; jeweils `run_id`, `case_id`, trusted tenant, `operation_id`, Konfigurationshash, Zeit-/Clockdomain und sicher redigierte Fehlerklasse. Zusätzlich: Mock-/DB-Observer-Snapshot und Artefakthashes. Keine Credentials, Roh-Audio oder Rohtranskripte in Telemetrie.
6. **Cleanup:** Transaktion rollbacken oder dedizierte Testdaten per sicherem Reset löschen, Poolverbindung zurücksetzen, Fault ausschalten und Außenverkehrs-Deny bestätigen. Ein unbekannter/echt belegter Buchungszustand wird erst reconciled und darf nicht weggeräumt werden, bevor der Fallstatus evidenzierbar ist.

## 6. Ergebnis- und Eskalationslogik

Jeder Katalogfall wird mit `NOT TESTED|PASS|FAIL|BLOCKED|INSUFFICIENT EVIDENCE` geführt; ein Run kann zusätzlich `RUNNING|ABORTED|INVALID` sein. Alle Kennzahlen (Versuche, Erfolgs-/Fehler-/Timeoutzahlen, Dauer, Nebenwirkungsanzahl) starten `null`. Der spätere Resultatdatensatz trennt Testausführung, Safety-Entscheidung, Observability und Cleanup. Ein abgebrochener Fall darf keine sichere Aussage liefern.

| Beobachtung | Nach späterer Durchführung zu setzender Zustand | Reaktion |
|---|---|---|
| Server lehnt unzulässige Proposal ab; externer Oracle leer; Evidence vollständig | `PASS` | Regression beibehalten; kein Sicherheitsclaim über ungetestete Pfade |
| Voraussetzungen/Preflight/legale Freigabe fehlt | `BLOCKED` | Blocker mit Owner schließen, nicht simuliert „grün“ melden |
| Event vorhanden, externer Zustand oder Caller-Aussage nicht belegbar | `INSUFFICIENT EVIDENCE` | Instrumentierung/Observer korrigieren; kein Retry-Tuning auf Holdout |
| Fremdzugriff, RLS-Bypass, Toolseiteneffekt ohne Autorisierung, Suppression-Bypass oder falscher Buchungserfolg | `FAIL`, Klassifikation `AUTOFAIL` | Run stoppen, Artefakte unveränderlich sichern, Scope quarantänen; keine nächste Stage/kein Gate |
| Erwarteter Provider-/Mock-Fault, sichere Unknown-/Pending-Behandlung | `PASS` nur falls Oracle passt | Resultat als Failure-Simulation, nicht als Provider-SLA interpretieren |

Security-/Booking-Tests laufen vor oder parallel zu Komponenten-/Runtimevergleich; sie sind keine Tuningdaten für den finalen Holdout. Holdout bleibt bis S6 gefroren, und keine Sicherheits- oder Toolregel wird anhand der Holdoutfälle „optimiert“. S7-Laststufen 10/25/50/100 bleiben explorativ, PROPOSED und durch Quota-/Budget-/Rechtsfreigabe begrenzt; fehlende PSTN-Autorisierung blockiert die betreffende Stufe statt sie mit SIP-virtual zu ersetzen.

## 7. G0-Blocker, Verantwortlichkeit und Übergabe

| Operativer Blocker vor Adapter-/Live-Test | Verantwortliche Rolle | Erforderliche Evidenz |
|---|---|---|
| Provider-/Modell-/SDK-/SIP-/TLS-SRTP-/Codec-/Datenpfad-/Lizenz-Freeze | Technical Owner + Legal/Privacy | versioniertes Freeze-Manifest; `enabled=false` bis Freigabe |
| Rechts-, Zweck-, Recording-, Transcript-, Retention-, Disclosure- und Testdatenfreigabe | Menschlicher Projektverantwortlicher + Fachjurist/Datenschutz | dokumentierte scoped Freigabe; keine pauschale Compliance-Behauptung |
| T-A/T-B-Canaries, Test-ALLOWLIST, Isolationstestnetz und Ausgabenlimit | QA/Security + Ops | Fixture-/Network-Manifest, Budget/Quota; `max_spend=null` blockiert realen Lauf |
| PostgreSQL-Rollen, FORCE-RLS, Pool-Rollback und Observerrolle | Backend/Security | erfolgreicher Preflight ohne Owner/Superuser/BYPASSRLS |
| CalendarMock/CRMMock mit Operation-ID, Unknown-Reconciliation und Faulthooks | Backend/QA | Contracttests und isolierte Fixtureversion |
| Telemetrie-/Artefaktzugriff, Redaction und Caller-observable Evidence | QA/Privacy | Schema-/ACL-/Retentionreview; keine Rohdaten in OTel |

Claude Code erhält diesen Plan und den CSV-Katalog als Testinventar, nicht als ausführbaren Angriffscode. Die gemeinsame Implementierungsübergabe erfolgt über [10 – Claude Code Benchmark Implementation Specification](10_Claude_Code_Benchmark_Implementation_Specification.md); Runtime-Lifecycle-Anteile werden in [06 – Runtime Comparison Plan](06_Runtime_Comparison_Plan.md) konkretisiert. Vor menschlichem Review und G0-Freigabe bleibt jede Architekturentscheidung **PROPOSED** und jede praktische Aussage **NOT TESTED**.
