# 08 – Kostenmessplan

**Dokument-ID:** 08  
**Planstand:** 22.10.2026  
**Status:** Spezifikation; sämtliche Messresultate **NOT TESTED**, sämtliche Ergebniszahlen `null`  
**Referenzfall:** Inbound Appointment & Qualification Agent  
**Verbindlicher Rahmen:** [Kanonischer Vertrag](contracts/00_Canonical_Contract.md) (v1.0), insbesondere Abschnitte B, C, E und G. Researchbasis: [Telephony & Infrastructure Audit](audit_baseline/05_Telephony_Infrastructure_Audit.md), [Cost & Unit Economics Report](audit_baseline/08_Cost_Unit_Economics_Report.md) und [Open Questions & Validation Plan](audit_baseline/12_Open_Questions_Validation_Plan.md), jeweils Quellenstand 21.10.2026.

## 1. Zweck, Abgrenzung und Kostenstatus

Dieser Plan spezifiziert den **messbaren Kostenledger** des späteren isolierten Benchmark-Harness. Er beantwortet nicht, welcher Provider, welches Runtime-Framework oder welcher Tarif wirtschaftlich gewinnt. Die im Audit genannten Preise, Modelle und Angebotsformen sind lediglich übernommene historische Researchhinweise; sie werden weder am 22.10.2026 erneut verifiziert noch als aktuelle Beschaffungspreise verwendet. Insbesondere dürfen Programmable-Voice-/Media-Streams-Annahmen nicht als Elastic-SIP-/LiveKit-SIP-Tarif und ein früherer Pipecat-WebSocket-Pfad nicht als T0-Preis ausgegeben werden.

Gegenstand sind tatsächlich entstehende, eindeutig zuordenbare Verbrauchseinheiten und deren Belege je Testversuch. Der Ledger erzeugt zunächst nur den Status **METERED_COST_PROVISIONAL**, wenn ein Provider-Usage-Ereignis mit einem vorab eingefrorenen Accounttarif verbunden werden kann. Erst der Abgleich gegen Billing-Export oder Rechnung erzeugt **COST_RECONCILED**. Fehlende Mengen, Raten, Rechnungen oder unklare Abrechnungseinheiten bleiben explizit `NOT TESTED`, `MISSING_UNIT`, `MISSING_RATE`, `MISSING_BILL` oder `BLOCKED` — niemals Kosten `0`.

Ausgeschlossen sind Produktpreis, Umsatz, Marge, finale Kapazitäts- oder Produktions-COGS-Behauptungen. Entwicklungs- und Reviewstunden werden zwar als betrieblicher Aufwand dokumentiert, aber **getrennt** von Provider-, Cloud- und Laufzeitgebühren geführt. Kein hier definiertes Budget autorisiert reale Anrufe, Accounts, Ausgaben, Deployment oder API-Aufrufe.

> **Kernregel:** Eine geschätzte Gesprächsminute, ein Audit-Szenario oder ein modellierter Sprechanteil ist keine gemessene Einheit. Nur ein belegter Zähler aus der später freigegebenen Ausführung darf kostenseitig in den Vergleich eingehen.

## 2. G0: Preis-, Vertrags- und Messfreeze vor jeder Live-Implementierung

Vor Adapterimplementierung mit Livezugang ist der **G0 PRE-IMPLEMENTATION-FREEZE** durch einen benannten menschlichen Owner freizugeben. Die Offline-Mock-Arbeit S1 darf ohne Live-Credentials beginnen, liefert aber keine Kostenmessung. G0 ist offen, bis pro tatsächlich verwendeter Komponente die folgenden Evidenzen versioniert im Freeze-Manifest vorliegen:

| Prüfobjekt | G0-Nachweis und Entscheidung | Block bei fehlendem Nachweis |
|---|---|---|
| Account und Produkt | logische `account_ref`, Providerprodukt, Plan/Commitment/Credits, zulässige Testverwendung; keine Secretwerte | Kein Live-Usage-Record, `BLOCKED` |
| Tarif und Währung | exportierbares Ratedeck oder Vertrag, Tarifversion/Stand, Originalwährung, Rundung, Mindestdauer, Mindestabnahme, Freicredit-Regel | `MISSING_RATE`; keine Umrechnung oder Hochrechnung |
| Carrierroute | freigegebener deutscher Inbound-DID, Carrieraccount, T0-SIP-Route, Call-Legs, Ziel-/Origination-Tarif und Nummernfee | kein PSTN-Real-Slot; T0 nicht kostenseitig vergleichbar |
| Providerdatenpfad | Region, Endpoint, Billing-/Usage-Export, Quota, Aufzeichnungs-/Speicherbedingungen sowie AVV/Vertragsrechte | betroffene Lane `BLOCKED` |
| Messzugang | request-/session-/call-/leg-IDs, Meter-/Billing-Export, Abfragefenster und Latenz bis zur Abrechnung | nur technische Ereignisse; kein Kostenresultat |
| Live-Schutz | ausdrücklich autorisiertes Ausgabenlimit, Währung, Session-Minutenlimit, TEST_ALLOWLIST, Country-Denylist und Stop-Verhalten | `live_enabled=false`; Validator verweigert Lauf |

`max_spend_amount=null` ist absichtlich kein unbegrenztes Budget, sondern sperrt jeden Live-Lauf. Die spätere Freigabe muss zudem eine Reserve für verspätete oder noch unbekannte Providerabrechnung definieren. Ein API-Cap garantiert keinen unveränderten Tarif und ersetzt die Rechnung nicht. Secrets werden ausschließlich über ENV-Namen (beispielsweise `BENCH_<PROVIDER>_API_KEY`) referenziert; weder dieses Dokument noch Konfigurationsbeispiele enthalten oder fordern echte Zugangsdaten.

## 3. Ledger-Grenzen, Kostenobjekte und Schlüssel

Jeder Ledger-Record beschreibt **eine abrechenbare Provider- oder Cloud-Einheit**, nicht eine nachträglich geglättete „Kosten pro Minute“. Der Record trägt `run_id`, `comparison_id`, `stage`, `arm_id`, `call_id`, optional `turn_id` und `operation_id`. Er enthält `account_ref`, Provider/Produkt, Request-ID oder Call-Leg, Route, Region, Originalwährung, Einheit, tatsächliche Menge, Rate, Rundung, Kostenstatus, Allokationsregel und unveränderliche Evidenzreferenzen. Damit sind Wiederholungen, Fehler und unvollständige Calls prüfbar, ohne PII, Roh-Audio oder Credentials in den Ledger zu schreiben.

| Kostenkomponente | Primäre tatsächliche Einheit | Zwingende Zuordnung | Was nicht unterstellt werden darf |
|---|---|---|---|
| Carrier | Call-/Leg-Minute, Event, DID-Monat oder andere Carrier-Originaleinheit | `carrier_leg_id`, Route/Origination, DID-Klasse, `product_platform` oder `test_execution` | ein pauschaler DE-Minutenpreis, Mobilmix oder identische Inbound-/Outbound-Rundung |
| Gemeinsames Media/SIP | Session-/Bridge-Minute, SIP-Minute oder Request laut Anbieter | T0-Room/Track, Media-Server, Codec/Transport, `T0_SHARED_*`-Regel | dass LiveKit-SIP, WebSocket und PSTN dieselbe Gebühr haben |
| STT | Audiominute, Kanalminute, Request oder Providerunit | Provider-Request-ID, Audiokanal, Modell-/Endpointfreeze | volle Callzeit, Add-ons oder Stille als kostenfrei bzw. immer gleich |
| Text-LLM | Input-, Cached-Input- und Output-Token getrennt | Request-ID, Modell/Region, Cache-Disposition | Cachequote, Kontextwachstum oder Retryfaktor aus Annahmen |
| TTS | Zeichen, Credits, Audiotoken, Request oder andere Originaleinheit | Synthese-Request, Voice-/Modellfreeze, abgebrochene Ausgabe | dass verworfenes/abgebrochenes Audio unbilled ist |
| Runtime/Compute | aktive/Reservierungs-Sessionminute, vCPU-/Byte-/Stunden- oder Vertragsunit | Worker/Pool, cold/warm/standby, Arm und Ressourcenklasse | dass ein Session-Minute-Tarif CPU, Standby oder Shared Infra einschließt |
| Analytics/Storage | Request/Token sowie Byte-Stunde, GB-Monat, Event oder Export | Postcall-Lauf, Retentionklasse, Speicher-/Egress-Objekt | kostenlose Logs, Backups, Exporte oder Aufzeichnung |

Die Kostenobjekte tragen zusätzlich `cost_scope`: `product_platform`, `test_execution`, `observer` oder `shadow_evaluation`. Der PSTN-Caller, der den Testanruf erzeugt, ist **test_execution** und darf nicht als Kundenplattformkosten erscheinen. Gleiches gilt für menschliche Rater, Kalibrierungsaufnahmen und optionales Shadow-ASR. Native S2S-Audio-/Texttoken werden eigenständig gebucht; Kaskaden-STT/TTS werden dafür nicht künstlich zusätzlich gerechnet. Eine unabhängig aktivierte Shadow-ASR bleibt als `shadow_evaluation` sichtbar.

## 4. Faire Zuordnung in T0, T1 und den Stages

S3/S4 vergleichen LiveKit Agents Python und Pipecat Python mit LiveKit Transport auf **demselben T0 Carrier-SIP → LiveKit-Media → Room/Track-Pfad**. Der Ledger muss daher Medienkosten als gemeinsames Objekt markieren, nicht beide Arme mit einer frei erfundenen Vollsumme belasten. Die vor dem Vergleich fixierte `allocation_rule_id` lautet entweder `T0_SHARED_EQUAL` (gleiche Zahl vergleichbarer Sessions) oder `T0_SHARED_WEIGHTED` (nach belegter Nutzung); sie gilt symmetrisch für beide Arme und wird in der Run-Manifestdatei gehasht. Carrier-Testleg und Caller bleiben getrennt. Ein Arm erhält keinen Vorteil durch versteckte Warm-Pools, abweichende DID, Rate, Region oder Reservation.

T1 (Pipecat + direkter Carrier-WebSocket) ist eine **separate, konfundierte Volltopologie**: eigene Route, Codec, Region, Media- und Carrierprodukte werden als `T1_DEDICATED` erfasst; kein T0-Tarif wird übernommen. Die Differenz zeigt eine Topologieentscheidung, keinen reinen Frameworkeffekt. Der spätere native S5-Pfad nutzt ebenfalls T0, soweit G0 das bestätigt. Seine Audio-/Texttokens, Tools, Media und Carrier werden eigenständig gemessen; aus fehlenden STT-/TTS-Teilmetriken darf weder `0` noch ein hypothetischer Kaskadenpreis werden.

| Stufe/Transportklasse | Kostenzweck | Erlaubte Kostenbehauptung heute | Vergleichsregel |
|---|---|---|---|
| S0 Freeze | Account-/Tarif-/Exportfähigkeit prüfen | `NOT TESTED` | keine Messung, keine Tarifableitung |
| S1 `offline` / `sip_virtual` | Ledgerformat, Mocks, Fehlerszenarien | keine reale Providerkosten | `network=deny`; Mockmengen sind keine Kosten |
| S2 Komponenten | STT/TTS/LLM-Einzelfaktor B0/C1 | nur nach G0 je Providerunit | gleicher Fixture-/Repeat-/Regionenfreeze |
| S3/S4 T0 `pstn_real` | Runtime- und Kaskadenvergleich | pro Arm/Call/Turn/Unit, später provisional | gemeinsame Medienallokation, gleicher DID sequenziell randomisiert |
| S5 Native | native gegen beste Validation-Kaskade | eigene native Unit, kein Kaskaden-Doppelcount | gleiche Tools/Fixture/Media, Shadow getrennt |
| S6 Holdout | Bestätigung ohne Tuning | gleiche Ledgerlogik, einmalig frozen | keine Auswahl aufgrund des Holdouts |
| S7 Load | Lifecycle/Lastkosten und Quoten | explorativ, keine Produktionskapazität | Cold/warm, Poolzahl und Ressourcengröße deklarieren |

Für S7 sind 10, 25, 50 und 100 parallele Sessions mit je zehn Minuten Plateau und drei Wiederholungen pro Level/Arm **PROPOSED/ANNAHME**. Für die zwei Runtimearme entstehen dadurch allein vorgeschlagene **11.100 Agent-Session-Minuten** (`3 × 10 × (10+25+50+100) × 2`), zuzüglich echter Provider-/PSTN-/Caller-Legs. Die frühere Auditbudgetannahme von ungefähr 2.000 Testminuten deckt dies nicht und darf nicht als Gesamtbudget behauptet werden. Offline und SIP-virtual können vorab ohne Kostenrisiko testen; reale PSTN-Last steigt 10→25→50→100 nur bei Legal-, Quota-, Allowlist- und Budgetfreigabe. Nicht freigegebene höhere Stufen sind `BLOCKED`, nicht bestanden.

## 5. Messung vom Ereignis bis zum Ledger

Der gemeinsame Ereignisstrom aus [04_Measurement_Telemetry_Specification.md](04_Measurement_Telemetry_Specification.md) ist der Join-Anker, aber kein Kostenbeweis. Der spätere Adapter korreliert `USAGE_REPORTED` mit `provider_request_id`, `call_id`/`carrier_leg_id`, `operation_id`, `account_ref`, `config_hash`, `transport_class` und dem Provider-Usage-Fenster. `TTS_REQUESTED` oder `LLM_REQUESTED` belegt einen Versuch; erst der Providerzähler belegt die abgerechnete Menge. Überlappende Streamingphasen werden niemals summiert, um einen End-to-End-Preis zu erzeugen.

1. **Erfassen:** Adapter speichern sichere Providerreferenzen und technische Dispositionen (`completed`, `failed_partial`, `retry`, `canceled_tts`, `discarded_audio`, `standby`, `cold_start`). Jede Anfrage, die trotz verworfener Ausgabe berechnet wird, bleibt im Ledger.
2. **Normalisieren:** Der Unit-Normalizer akzeptiert nur die originale Providerunit. Er speichert keine vermeintliche Umrechnung in Minuten. Bei Zeichensystemen, Credits oder Audio-/Texttokens bleiben Einheit und Menge getrennt.
3. **Bewerten:** Ist Menge plus eingefrorene Rate nachweisbar, berechnet der Ledger in **derselben Währung** `cost_amount = quantity_actual × rate_amount_per_unit` unter dokumentierter Rundungsregel. Komplexe Tarife, Pakete, Freicredits und Mindestabnahmen werden nicht geschätzt, sondern als konkrete `invoice_fact`/Periodenallokation ausgewiesen.
4. **Abgleichen:** Billing-Export und Rechnung werden gegen Provider-, Produkt-, Account-, Periode- und Währungsbezug abgeglichen. Differenzen sind als eigene Abweichungsrecords mit Grund, Owner und Auflösungsstatus festzuhalten. Keine unsichtbare Restkostenverteilung.
5. **Sperren:** Fehlt eine Korrelation, Rate oder Rechnung, bleibt das Kostenresultat unvollständig. Der technische Run kann abgeschlossen sein, aber die Kostenevidenz bleibt `BLOCKED` oder `INSUFFICIENT EVIDENCE`.

Die Umsetzung validiert die Struktur mit [contracts/usage.schema.json](contracts/usage.schema.json). Das kompatible [config/Usage_NOT_TESTED.example.json](config/Usage_NOT_TESTED.example.json) demonstriert bewusst einen sperrenden Offlineplatzhalter: `quantity_actual`, Raten- und Kostenfelder sind `null`, Livezugriff ist deaktiviert.

## 6. Abrechnungssonderfälle und vollständige Nenner

Kostenvergleiche sind nur mit vorregistrierten Nennern aussagefähig. Das Ergebnisformat führt deshalb je Arm und Cost Scope separat: Gesamtbetrag je Originalwährung, Zahl aller Attempts, verbundene Carrier-Minuten, erfolgreiche technische Sessions, bestätigte korrekte Buchungen und ihre Nenner. Bei Nenner `0` ist die abgeleitete Kennzahl `null`. Keine Währung wird ohne zugelassene, separat belegte FX-Quelle summiert; USD und EUR erscheinen als getrennte Blöcke.

| Sonderfall | Erfassung | Sicherheits- und Vergleichsfolge |
|---|---|---|
| kurze/falsche/abgebrochene Calls | eigener Carrier-/Media-Leg mit tatsächlicher Disposition | nicht aus „Kosten pro Call“ entfernen |
| Retry, 429, Timeout | jeder billable Versuch als separater Record, gemeinsame `operation_id` | Tool-/Booking-Duplikate nicht als kostenfreie Logik maskieren |
| TTS-Abbruch/Barge-in | Request, erste Audioausgabe, verworfener Rest und Providerverbrauch | keine Annahme, dass abgespielte Dauer = gebillte Dauer |
| LLM-Cache und Kontext | Input, Cache-Input, Output getrennt | Cache nicht auf andere Arme oder native Pfade übertragen |
| Paket/Credit/Commitment | Periodenrecord mit Tarifreferenz und dokumentierter Allokationsregel | Credits einmal pro Billingperiode anwenden; kein doppelter Abzug |
| Reservierung/Standby/Shared Infra | unabhängige Runtime-/Cloudrecords, cold/warm markiert | nicht in variable Callgebühr verstecken |
| Recording, Storage, Egress, Backups | getrennte Retention-/Bytezeit-/Exportrecords | Aufnahme erst nach Rechts-/Policyfreigabe; fehlende Einheit ist nicht null |
| Rechnung kommt später/korrigiert | `METERED_COST_PROVISIONAL` bis `COST_RECONCILED`; Korrektur als neuer unveränderlicher Record | keine rückwirkende Überschreibung der Messspur |

Die Auditformeln zu Minutenmix, Cache, Sprechanteil, Runtime-Reserve und Infrastruktur waren nützliche **ANNAHMEN** für Sensitivität, nicht Ledgerwerte. Sie können nach G0 als explizit markierte Budgetmodelle neben dem Ledger geführt werden, nie in ihn hinein. Ebenso dürfen Entwicklung, QA, On-call oder Legal nicht als „Runtimekosten“ verdeckt werden: Aufwandseintrag mit Rollenstunden, Kostenbetrag und Währung jeweils `null`, solange keine autorisierte Datenerhebung erfolgt.

## 7. Auswertung, Qualitätsgates und Fehlverhalten

Die Kostenreporting-Pipeline darf keinen Safety- oder Qualitätsveto überstimmen. Ein `hardfailCrossTenant`, `unauthExecution`, eine falsche Buchungserfolgsmeldung oder ein Call trotz Suppression führt gemäß Vertrag unabhängig von günstigen Units zu Fail/Hold. Kosten werden für fehlgeschlagene Versuche weiterhin gezeigt, damit ein System nicht durch Weglassen teurer Fehler besser aussieht. Ein fehlender Providerzähler wird nicht gegen Latenz, WER oder Booking-Erfolg „aufgerechnet“.

Die Reportingansichten sind pro `comparison_id` mindestens:

- **Pro Call:** alle Plattform- und Testausführungslegs, mit Attempts und echten Carrier-/Mediennennern;
- **Pro Turn:** STT, LLM, TTS und Tools nur bei belegbarer Requestzuordnung;
- **Pro verbundener Minute:** nur wenn Carrierdefinition und Rundung feststehen;
- **Pro bestätigter korrekter Buchung:** Plattformbetrag geteilt durch die Anzahl fachlich bestätigter, durch den Evaluator korrekter Buchungen; `null`, falls keine existiert;
- **Pro Provider-/Währung:** Summe ausschließlich gleichartiger Währung und Status; `METERED_COST_PROVISIONAL` und `COST_RECONCILED` niemals vermischen.

Alle Zahlenfelder eines noch nicht gelaufenen Reports bleiben `null`. Ein Run mit Messlücken kann `runstatus=RUNNING`, `ABORTED` oder `INVALID` tragen; ein abgeschlossener Run ist kein Qualitäts-PASS und keine Rechnungsfreigabe. Nachstehende Ergebnisvorlage ist daher absichtlich leer.

| Kennzahl | Einheit/Scope | Resultat | Evidenzstatus |
|---|---|---:|---|
| Carrierkosten je T0-Call | Originalwährung / product_platform | `null` | `NOT TESTED` |
| Shared-Media-Kosten je Arm | Originalwährung / T0-Allokation | `null` | `NOT TESTED` |
| STT/LLM/TTS je Turn | jeweilige Providerunit / product_platform | `null` | `NOT TESTED` |
| Native Audio-/Textkosten | jeweilige Tokenunit / product_platform | `null` | `NOT TESTED` |
| Caller-Testleg | Originalwährung / test_execution | `null` | `NOT TESTED` |
| Storage/Analytics/Runtime | Originaleinheit / getrennte Scopes | `null` | `NOT TESTED` |
| Rechnung–Ledger-Differenz | Originalwährung | `null` | `NOT TESTED` |
| Kosten pro bestätigter korrekter Buchung | Originalwährung / definierter Nenner | `null` | `NOT TESTED` |

## 8. Implementierbare Aufgaben, Verantwortlichkeit und Definition of Done

| Arbeitspaket | Verantwortlich nach Freigabe | Abhängigkeiten | Definition of Done |
|---|---|---|---|
| COST-01 Freeze-Validator | Claude Code, Review durch Ops/Legal | G0-Evidenz, `freeze`-Manifest | blockiert live bei `null`-Budget, fehlender Allowlist, Rate, Unit, Route oder Exportpfad |
| COST-02 Usage-Adapter | Claude Code | Provideradapter, sichere Request-/Leg-IDs | erzeugt schema-valide Rohrecords ohne PII/Secrets und erhält Fehler-/Abbruchdispositionen |
| COST-03 Ledger/Allokation | Claude Code + Finance/Ops Review | T0/T1-Manifest, Allocation Rule | immutable Recordkette; gemeinsame T0-Kosten nach fixierter Regel, keine Doppelzählung |
| COST-04 Reconciliation | Finance/Ops Owner | Billingexport/Rechnung, Tariffreeze | Differenzen sichtbar, Originalwährung erhalten, Status nur nach Belegwechsel |
| COST-05 Cost Gate | Menschlicher Entscheider | Results, Safety-/Legal-Gates, [09_Acceptance_Criteria.md](09_Acceptance_Criteria.md) | keine Architekturentscheidung bei fehlendem/inkonsistentem Kostenbeleg |

Die Kostenartefakte werden zusammen mit Benchmarkmatrix ([02_Benchmark_Matrix.md](02_Benchmark_Matrix.md)), Providermatrix ([07_Provider_Comparison_Plan.md](07_Provider_Comparison_Plan.md)), Runtimeplan ([06_Runtime_Comparison_Plan.md](06_Runtime_Comparison_Plan.md)) und späterem Decision Gate ([12_Decision_Gate_Template.md](12_Decision_Gate_Template.md)) bewertet. Eine Evidence Card darf den Kostenabschnitt erst als belastbar markieren, wenn der Unit-Ledger, Tariffreeze, Billing-Abgleich, Scope- und Allokationsregeln vollständig verlinkt sind. Bis dahin lautet die Entscheidungsempfehlung ausdrücklich: **offen, Confidence Low, NOT TESTED**.

### Operative G0-Blocks

1. Aktuelle Modell-, SDK-, API-, Carrier-, Tarif-, Routen-, Vertrags- und Datenpfadverifikation ist **nicht** erfolgt und muss vor Liveadaptern eingefroren werden.
2. Es gibt keine freigegebene Test-DID-/SIP-Route, keine KYC-/Resale-/Automationsfreigabe, keine Quota- oder Billing-Exportprüfung und keine echte Rechnung.
3. Budgetowner, Ausgabenlimit, TEST_ALLOWLIST, Country-Denylist, Live- und Recordingrechtsgrundlage sind nicht freigegeben.
4. Die tatsächliche Instrumentierbarkeit von Provider-Usage zu Request/Call-Leg sowie die korrekte T0-Mediaallokation sind **NOT TESTED**.
5. Der vorgeschlagene S7-Umfang benötigt 11.100 Agent-Session-Minuten allein für zwei Runtime-Plateaus; daraus folgt weder Budget noch Durchführungserlaubnis.
