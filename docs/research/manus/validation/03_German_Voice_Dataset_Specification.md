# 03 – Deutsche Voice-Dataset-Spezifikation

**Dokument-ID:** 03 · **Planstand:** 22.10.2026 · **Researchbasis:** Auditstände 21.10.2026  
**Status:** Spezifikation; Erhebung, Audio, Annotationen, Ausführung und Resultate sind **NOT TESTED**. Dieses Dokument trifft keine Provider-, Runtime- oder Architekturentscheidung.

## 1. Zweck, Abgrenzung und normative Einordnung

Dieses Dataset misst den deutschen Referenzfall **Inbound Appointment & Qualification**: eingehender Anruf, KI-Offenlegung, Anliegen und Kontaktdaten, Qualifizierung, Slot lesen, Slot rückbestätigen, serverseitig buchen, erst nach autoritativer Bestätigung Erfolg sagen, CRM Mock aktualisieren und Outcome persistieren. Es ist ein Evaluationskorpus für den isolierten Harness, **keine** Leadliste, kein Trainingsdatensatz, keine Kampagne und keine Freigabe für PSTN-Anrufe oder Recording.

Die verbindliche Topologie, Phasen S0–S8, Statuswerte, Schutztool-Autorität und Messdefinitionen stehen im [kanonischen Vertrag](contracts/00_Canonical_Contract.md). Insbesondere darf der Agent Ground Truth nie sehen, `tenant_id`, Credentials oder Scopes nie aus Modelltext ableiten und Buchungserfolg nie aus einer Modellbehauptung ableiten. Das Korpus ist deshalb für beide T0-Arme identisch: **LiveKit Agents Python** und **Pipecat Python mit LiveKit-Transport** verwenden dieselbe Carrier-SIP→LiveKit-Media/Room-Route, dieselben Testsätze und dieselben Calendar-/CRM-Mocks. Direkter Carrier-WebSocket ist nur die getrennte, als `CONFOUNDED` markierte T1-Lane.

Die Notwendigkeit getrennter Entity-, Turn- und PSTN-Evaluierung folgt aus dem [Voice-Audit](audit_baseline/04_Voice_Technology_Audit.md); rechtliche Grundlagen, Recording und Datenflüsse bleiben G0-Pflichten nach dem [Security-/Compliance-Audit](audit_baseline/09_Security_Compliance_Risk_Report.md). Datasetplanung und akzeptierte Schwellen sind nicht zu verwechseln mit Evidenz; siehe auch [Open Questions & Validation Plan](audit_baseline/12_Open_Questions_Validation_Plan.md).

## 2. Korpusvertrag: Einheiten, Splits und Invarianten

Der folgende Umfang ist ein **PROPOSED/ANNAHME-v1-Sollumfang**, nicht erhobene Stichprobe. Eine *sprachliche Fall-ID* ist genau ein einzigartiger semantischer Prompt mit versteckter Referenz. Audioableitungen, Replays und Wiederholungen zählen nie als neue unabhängige Fälle.

| Artefakt | Normativer Sollumfang | Split | harte Regel |
|---|---:|---|---|
| Kurzfälle | 360 einzigartige Fälle; 6 Kategorien à 60 | Dev 120 / Validation 60 / Holdout 180 | Speaker-disjoint; Ground Truth für Agent verborgen |
| Sprecher | 30 einwilligende, pseudonymisierte Personen × 12 Kurzfälle | 10 / 5 / 15 Sprecher | genau 2 Fälle pro Kategorie und Sprecher |
| Dialogskripte | 160 Definitionen, jeweils mindestens 8 User-Turns | 40 / 40 / 80 | eigene End-to-End-Oracles, kein Ersatz für Kurzfallaudio |
| Holdout-Verhaltenschancen | je mindestens 20 Interrupt-, 20 Backchannel-Kontroll- und 20 Denkpausen-Chancen | nur Holdout, je zulässige Lane | **PROPOSED**; Nenner vor Ausführung festschreiben |

Splitzuordnung ist primär eine Sprecherzuordnung: Ein Sprecher samt allen Rohaufnahmen, Dialogturns, Normalisierungsrevisionen und abgeleiteten Varianten befindet sich genau in einem Split. Die `parent_id` einer Ableitung muss dieselbe Split- und Sprecherzuordnung tragen. Die Reihenfolgenrandomisierung verwendet ausschließlich den Vertragsseed `24022026`; er macht Providerantworten nicht deterministisch. Dev/Validation dürfen Konfigurationen auswählen; Holdout wird vor jeder Auswahl eingefroren, einmal ausgeführt und nie für Tuning, Prompt- oder VAD-Anpassung wiederverwendet.

| Resultatplatzhalter (nicht Datensatz-Sollzahl) | Wert | Evidenzstatus |
|---|---:|---|
| aufgenommenes Kurzfallaudio | `null` | `NOT TESTED` / `NOT RECORDED` |
| annotierte Kurzfälle | `null` | `NOT TESTED` |
| geprüfte Dialoge | `null` | `NOT TESTED` |
| Audio-/Entity-/Taskmetriken | `null` | `NOT TESTED` |

## 3. Sprachliche Fallmatrix

Jede Kategorie erhält 60 Fälle, gegliedert in sechs Subkategorien à **10 PROPOSED** Fälle. Innerhalb eines Subtyps werden Namen, Zahlenwerte und Satzrahmen variiert, aber nicht alle Akzente, Codecs und Verhaltensweisen kartesisch multipliziert. Jeder Fall hat ein oder wenige vorab deklarierte Verhaltenstags; eine Variation ist nur bei explizitem `parent_id` zulässig.

| Kategorie | Sechs Subkategorien (je 10 PROPOSED Fälle) | Fachoracle / kritische Behandlung |
|---|---|---|
| `PERSON` | Vorname; Nachname; Umlaut-/Bindestrich-/Apostrophname; seltene Namen; Buchstabieren; Selbstkorrektur | Unicode-NFC, getrennte Felder Vor-/Nachname; `ä` ist nicht implizit `ae`; Änderung invalidiert Bestätigung |
| `PHONE` | DE-Mobil; Festnetz mit Ortsvorwahl; gruppierte Ziffern; langsam buchstabiert; Wiederholung; Korrektur einzelner Ziffern | E.164 nur bei explizitem Länder-Kontext plus lexikalisch erfassten Ziffern; sonst keine fuzzy-Normalisierung |
| `EMAIL` | lokale Buchstabierung; de/en Buchstabiernamen; Punkt/Bindestrich; Plus; Unterstrich; Korrektur | Local Part exakt nach deklarierter Unicode-/Case-Policy; Domain darf nur nach deklarierter IDNA-/Case-Policy normalisieren |
| `ADDRESS` | Straße; schwierige Straße; Hausnummerzusatz; PLZ mit führender Null; Ort/Umlaut; vollständige Korrektur | Straße/Hausnummer/PLZ/Ort und Gesamtadresse getrennt prüfen; keine Geocoding-Rate als Wahrheit |
| `DATETIME` | absolutes Datum; Uhrzeit; morgen/übermorgen; Wochentag; Frühjahr-DST; Herbst-DST | UTC-Instanz **und** `Europe/Berlin`-Zone/Offset/Slot prüfen; lokale Stringgleichheit genügt nicht |
| `MONEY` | ganze EUR; Dezimalbetrag; große Zahl; ausgeschriebene Zahl; Rückfrage; Korrektur | Betrag in Decimal-Minor-Units plus Währung; keine Binary-Floats und keine Rundungsheuristik |

Automotive-Felder (Kennzeichen, VIN, Modelle) sind ausdrücklich **nicht Teil des v1-Sollkorpus** und dürfen keinen v1-Nenner verändern. Ein später freigegebener Annex benötigt eigene Rechte-, Normalisierungs- und Holdoutplanung.

### Verhaltens- und Kanal-Tags

Erlaubte Primärtags sind `self_correction`, `spelling`, `repeat_request`, `fast_speech`, `quiet_speech`, `think_pause`, `backchannel_noninterrupt`, `intentional_interrupt`, `clean`, `noise_snr_20db`, `noise_snr_10db`, `mobile_quality`, `landline_quality`, `g711_narrowband`. Bei `intentional_interrupt` ist die störende Äußerung als intendiert annotiert; `backchannel_noninterrupt` ist eine negative Kontrolle und darf keine Barge-in-Auswertung fälschlich als Erfolg erzeugen. Tags sind nicht automatisch Ground Truth für Endpointing; die akustische Annotation und Caller-Kalibrierung bleiben Voraussetzung der Latenzauswertung nach [04](04_Measurement_Telemetry_Specification.md).

## 4. Zeit-, Slot- und Bestätigungsoracles

Alle Zeitbezüge verwenden die injizierte Fixture-Uhr `2026-10-22T08:00:00Z` und die Zeitzone `Europe/Berlin`, nie Maschinenlokalzeit. Zwei unverzichtbare Fälle sind: **2027-03-28 02:30 Europe/Berlin** (nicht existent; Calendar Mock muss zurückweisen) und **2026-10-25 02:30 Europe/Berlin** (mehrdeutig; Agent muss Offset/Instanz klären). Ein Datum wird daher als `{local_datetime, zone, offset, utc_instant, slot_id}` annotiert; ein nicht existenter Zeitpunkt hat `utc_instant: null` und die erwartete Aktion `REJECT_AND_REASK`.

Für alle geschäftskritischen Felder beschreibt `confirmation_policy` eine fachliche, nicht modellautorisierte Kette: `ContactCandidate → readback → finite user affirmation → CONFIRMED` oder `BookingIntent → slot readback → affirmation → EXECUTABLE`. Ein negatives, mehrdeutiges oder korrigierendes Userturn invalidiert das jeweilige Readback. Die versteckte Referenz dient nur Evaluatoren. Der Backend-Gateway leitet `intent_id` und Idempotenzschlüssel aus `CallContext` ab; ein Dialogskript darf weder Konten noch Kalenderreferenzen erfinden. `CalendarMock` führt die Buchung mit Unique-Constraint aus; nur `BOOKING_CONFIRMED` erlaubt eine Erfolgsaussage. Bei `BOOKING_UNKNOWN` ist `booking.get_status`/Reconciliation erforderlich, nie eine blinde Zweitbuchung. Diese Oracles sind mit [05](05_Security_Failure_Test_Plan.md) und der späteren Harnessübergabe in [10](10_Claude_Code_Benchmark_Implementation_Specification.md) kompatibel.

## 5. Audioerhebung, Ableitungen und Annotation

Zum Planstand existiert **kein** aufgenommener Datensatz. Die mitgelieferten Seeds sind ausschließlich synthetische Textspezifikationen. Vor jeder Aufnahme müssen menschliche Freigabe für Testdaten, dokumentierte freiwillige Einwilligung, Zweck/Empfänger/Retention, Zugriffsmatrix und G0-Rechtsprüfung vorliegen. Produktionskontakte, Kundendaten, Stimmklone, biometrische Identifikation, Emotionserkennung und unkontrollierte Webdaten sind ausgeschlossen. `speaker_id` ist ein Pseudonym; zulässig sind nur freigegebene Minimalmetadaten wie grobe Region/Dialektgruppe, niemals identifizierende Profilmerkmale in Telemetrie.

Nach zulässiger Erhebung erzeugt die Datenpipeline aus einem unveränderten Parent höchstens deklarierte Repräsentationen: sauberer Referenztrack, SNR-20-dB- und SNR-10-dB-Variante sowie PSTN-G.711-Narrowband-Derivat. Der Parent bleibt referenzierbar, die exakte Noise-/Codec-/Resampler-Version wird gehasht, und jede Variante erbt Split, Sprecher und semantische Referenz. Rohes 8-kHz-G.711 bleibt als Verlustprofil sichtbar; für STT ist nur der in G0 bestätigte gemeinsame 16-kHz-PCM16-Resampler erlaubt. Ableitungen sind weder zusätzliche Sprecher noch zusätzliche unabhängige Fälle.

Jede Referenz wird durch zwei deutschkundige Annotierende unabhängig erstellt; Konflikte gehen an eine dritte Adjudikation. Zu versionieren sind Prompttext, Audiodatei-/Derivathashes, Transkript, Entities, Normalisierungspolitik, Oracles und Reviewer-IDs als pseudonyme Rollen. Der Agent erhält nur den Stimulus und seine legitimierte Laufzeitkonfiguration, nie `expected_entities`, Oracles, Annotatornotizen oder Holdoutdaten. Roh-Audio/Transkript liegen außerhalb von OTel; Events referenzieren nur geschützte Material-IDs und Hashes. Lizenz-, Consent-, Zugriff- und Löschstatus pro Parent sind Loaderpflichten, kein Kommentar im Prompt.

| Feldtyp | kanonische Darstellung | Vergleichspolitik |
|---|---|---|
| Name | NFC-Displaywert + getrennte Vor-/Nachnamen | Case-Policy explizit; Umlaute/`ae` nur wenn als zulässige Alternative annotiert |
| Telefon | gesprochene Ziffern + optionales E.164 | exakte Ziffernfolge; E.164 nur bei explizitem Länder-Kontext |
| E-Mail | Local Part, Domain, Gesamtwert | kein blindes Lowercasing der ganzen Adresse; IDNA/Domain-Case nur deklarierter Transform |
| Adresse | strukturierte Felder + Gesamtwert | PLZ String; definierte Abkürzungsmap statt freier Ähnlichkeit |
| Datum/Uhrzeit | lokale Zeit, Zone, Offset, UTC, Slot | Instanz/Offset und Folgeaktion prüfen, nicht nur Text |
| Geld | ISO-Währung + Integer-Minor-Units | Integer-Gleichheit; Sprachformat ist nicht Rechenwahrheit |

## 6. Dialogskripte als End-to-End-Fixtures

Die 160 Skripte modellieren mindestens acht Userturns und haben einen deterministischen Zustandsgraphen: Disclosure-Akzeptanz/Abbruch, Anliegen, Contact Collect/Readback, Qualify, Slotliste, Slotauswahl/Readback, Buchungsversuch, bestätigter oder unbekannter Buchungsoutcome und CRM-/Gesprächsabschluss. Branches enthalten mindestens Rückfrage, Korrektur, Tooltimeout, Slotkonflikt und Abbruchpfad; die Dialoglogik übernimmt keine Bewertung des LLM.

Pro Skript liegen verborgen vor: erlaubte Toolreihenfolge, erwartete Sicherheitsablehnung, `operation_id`-Beziehung zur semantischen BookingIntent, erwarteter CalendarMock-Endzustand, CRM-Mock-Endzustand und zulässige Outcome-States. Ein CRM-Fehler nach bestätigter Buchung erwartet `BOOKED_CRM_PENDING`, nicht die Rücknahme der Buchung. Der Oracle-Runner bewertet externe Mockzustände und Eventsequenzen, nie nur Modell-JSON oder einen behaupteten Erfolg. Audio für Dialogturns muss aus dem passenden Speakersplit oder aus neu rechtmäßig erhobenen Dialogturns stammen; 360 Kurzfälle ersetzen diese 160 Dialogaudios nicht.

## 7. Maschinenlesbare Fixtures und Loader-Gates

[`contracts/dataset_fixture.schema.json`](contracts/dataset_fixture.schema.json) ist JSON Schema Draft 2020-12. Es erzwingt IDs, Split, Kategorie, nullable Sprecher, eingefrorene Uhr, strukturierte Entities, Audio-/Rechte-/Abhängigkeitsstatus, Tags, Bestätigungspolitik und `additionalProperties: false`. [`fixtures/Seed_Cases_NOT_RECORDED.jsonl`](fixtures/Seed_Cases_NOT_RECORDED.jsonl) enthält 18 schema-kompatible, ausschließlich synthetische Textspezifikationen – drei je Kategorie über Dev/Validation/Holdout verteilt. Alle tragen top-level `audio: null`, `audio_status: "NOT RECORDED"`, `dial_allowed: false`, `test_state: "NOT TESTED"` und `null`-Messfelder. Sie sind keine Audioaufnahmen, keine Ausführungseinträge und keine freigegebenen Anrufe.

Der künftige Loader muss in dieser Reihenfolge fail-closed prüfen:

1. Draft-2020-12-Validierung, eindeutige `fixture_id`, Kategorie-/Entity-Kohärenz, gültige UTC-/Zone-Formate und Parent-Split-/Speaker-Vererbung.
2. Erfüllung der v1-Quoten (360/6×60, 30×12, 120/60/180) sowie Speaker-Disjointness einschließlich Dialogaudio und Derivaten.
3. Ground-Truth- und Holdout-ACL: Agent-Bundle enthält keine Referenz/Oracle/Adjudikation; Holdout nur mit vorab signiertem Freeze-Manifest.
4. Consent, Lizenz, Retention, Rechte, Audiohash und Auditpfad pro **recorded** Parent. Fehlt einer, `audio_status=NOT RECORDED` oder `BLOCKED`, nicht stillschweigend ersetzbar.
5. Transportzulassung: `offline` kann Text-/Mockoracle vorbereiten; `sip_virtual` und `pstn_real` benötigen zusätzlich G0, freigegebene Accounts/Route/Quota/Budget/Allowlist. `dial_allowed=false` blockiert jede Wahl.

Ein fehlendes Audio blockiert die betreffende Audioevaluation als `BLOCKED`, nicht als Pass oder Nullqualität. Offline, SIP-virtuell und PSTN-real werden in Resultaten strikt mit `transport_class` getrennt und nie gemittelt.

## 8. Statistik, Verzerrung und G0-Blocker

Paired Cases, maximal drei vorregistrierte Wiederholungen und failure-first zählen Fehlversuche sichtbar. Raten berichten Zähler/Nenner sowie 95%-KI; Latenzen nutzen nearest-rank nur unter erfolgreichen, vorab klassifizierten Fällen, während Deadlines/Timeouts separat als Fehler in den konservativen Befund einfließen. Clusterbootstrap nach Sprecher bzw. Call mit 2.000 Resamples ist **PROPOSED**. Die 299 unabhängigen, fehlerfreien Feldgelegenheiten für eine einseitige 95%-Binomialuntergrenze von 99% sind eine mathematische IID-Warnung, **kein** Nachweis bei Sprecher-/Turn-Korrelation. Dafür sind Clusterdesign, Sprecherstreuung und zusätzliche Daten erforderlich.

Vor Adapterimplementierung verbleiben operative G0-Blocks: (a) aktuelle Modell-/SDK-/Voice-/Endpoint-/Region-/Lizenz- und DPA-IDs im Freeze-Manifest, (b) Rechts-/Privacy-Freigabe für Recording, Testdaten, Retention und Datenpfad, (c) schriftliche Sprecherrechte, (d) testfähige gemeinsame T0-SIP/Media/Codec-Route einschließlich TLS/SRTP/DTMF, (e) Budget-, Quota- und Allowlistfreigabe für nicht-offline Läufe sowie (f) Kalender-/CRM-Mockrelease und echte PostgreSQL-RLS-Preflight. G0 ist noch **NOT TESTED**; keine Auditangabe wird als am 22.10.2026 frisch verifiziert ausgegeben.

Die Datasetartefakte liefern [02](02_Benchmark_Matrix.md) die Fallmenge, [04](04_Measurement_Telemetry_Specification.md) die Metrikdefinitionen, [07](07_Provider_Comparison_Plan.md) die eingefrorenen Komponenten, [09](09_Acceptance_Criteria.md) die später vom Menschen zu akzeptierenden Schwellen und [12](12_Decision_Gate_Template.md) die Evidenzkarten. Sie begründen selbst keinen Sieger, kein PASS und keine Produktionsfreigabe.
