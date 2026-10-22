# 07 – Provider Comparison Plan

**Planstand:** 22.10.2026  
**Status:** `PROPOSED` · alle Evidenz- und Testzustände `NOT TESTED` · alle Ergebnis- und Kostenfelder `null`  
**Scope:** Kontrollierter Providervergleich für den Referenzfall **Inbound Appointment & Qualification**. Dies ist eine Spezifikation für den künftigen Benchmark-Harness, keine Providerentscheidung, keine Implementierung, kein Testlauf und keine erneute Markt- oder Vertragsrecherche.

**Normativer Vorrang:** Dieser Plan konkretisiert den [kanonischen Harnessvertrag](contracts/00_Canonical_Contract.md). Bei Konflikten gelten dessen IDs, Stage-Reihenfolge, T0-Topologie, Statuswerte, Dataset-Splits, Toolautorität und Sicherheitsregeln. Fachliche Ausgangslage sind der [Voice Technology Audit](audit_baseline/04_Voice_Technology_Audit.md) und die [Recommended Technology Shortlist](audit_baseline/11_Recommended_Technology_Shortlist.md), jeweils Quellenstand 21.10.2026. Die dort verlinkten Providerseiten sind ausschließlich **Inherited Citations / G0-Review-Ziele**, nicht am 22.10.2026 neu verifiziert.

## 1. Entscheidungsfrage, Grenze und Nicht-Ziele

Der Harness soll nach autorisierter Durchführung belastbar beantworten, ob eine **kontrollierte Kaskade** und ein **nativer Speech-to-Speech-Pfad** für deutsche, PSTN-nahe Terminqualifizierung unter gleichen fachlichen Sicherheitsgrenzen tragfähig sind. Zu vergleichen sind Providerkomponenten nur in den vorregistrierten Kombinationen und in zwei Python-Runtimes: LiveKit Agents und Pipecat mit LiveKit Transport. Ein Frameworkergebnis ist **kein** Urteil über LiveKit als Medienserver; ein Providerergebnis ist **kein** generelles Qualitätsurteil außerhalb der definierten Konfiguration.

Der Referenzablauf lautet: Inbound → AI Disclosure → Anliegen und Kontaktkandidat → Rücklesen und Nutzerbestätigung → Qualifizierung → Slots lesen → Slot rücklesen und bestätigen → serverseitig buchen → erst nach autoritativer Bestätigung Erfolg aussprechen → CRM Mock aktualisieren → Outcome persistieren. Das Modell darf lediglich Vorschläge abgeben. Das Tool-Gateway leitet `tenant_id`, Berechtigungen, Kalender-/CRM-Referenzen, `operation_id`, Idempotenzschlüssel und Credentials ausschließlich aus dem vertrauenswürdigen `CallContext` ab. Kein Modell – auch kein nativer Anbieterpfad – erhält Autorität über Mandant, Scope, Credential oder Ausführungsziel.

Nicht Gegenstand sind Cold Outbound, produktive Accounts, reale Kundendaten, eine Produktionsentscheidung, ein Preisversprechen oder ein Capacity-/SLO-Nachweis. Ein Opt-in-Test bliebe eine getrennte, freigegebene Lane. Erfolgs-, Latenz-, Kosten- und Hörqualitätswerte werden erst als tatsächliche Evidence erfasst; bis dahin sind sie `null`/`NOT TESTED`.

## 2. Vergleichsinvarianten und T0-Topologie

Der primäre Vergleich T0 erzwingt eine identische äußere Topologie: **freigegebene deutsche Inbound-DID und derselbe Carrieraccount → Carrier-SIP-Trunk → gemeinsamer LiveKit SIP-/Media-Server → gleichartige Rooms/Tracks → genau ein Agent pro Room**. Runtime A ist LiveKit Agents (Python), Runtime B Pipecat (Python) über LiveKit Transport. Ein vertrauenswürdiger Dispatcher ordnet erwarteten Test-`call_id` und Arm zu; diese Zuordnung kommt weder aus SIP-Headern noch aus Nutzer- oder Modellinput. Testcaller und Observer sind separate Rollen. Bei Last wird pro Session armseitig partitioniert, nie ein Callerroom an zwei Agenten gespiegelt.

Pro gepaartem T0-Fall sind fest einzufrieren: DID-/Carrierroute, Serverregion und Hardwareklasse, Codec- und Resamplingpfad, Prompt-, Tool- und Fixturehash, Kalenderuhr, Dataset-Fall, Reihenfolge-Seed, Runtimerelease und Adapterkonfiguration. Rohes 8-kHz-G.711 bleibt als PSTN-Eigenschaft messbar; der gemeinsame STT-Eingang ist nur nach G0-Bestätigung ein dokumentierter Mono-16-kHz-PCM16-Resampler. TTS nutzt 24-kHz-PCM16 nur bei beidseitiger Adapterparität, sonst einen gemeinsamen belegten Zielcodec. Keine SDK-Defaults, kein stilles Auto-Upgrade und keine künstliche Bandbreitenrekonstruktion.

Die gemeinsame VAD-/Endpoint-Startpolicy ist `PROPOSED`: Silero mit identischem Modellhash und – soweit beide Hooks zulassen – `speech_start_min_ms=100`, `silence_end_ms=500`, `interruption_min_ms=150`; Deepgram-Smartformat, Vocabulary und Endpoint-Flag werden gleich gefroren. Gibt es keine Hookparität, erfasst `deviation_manifest` Ursache, Umfang und Paar als `CONFOUNDED`; daraus darf kein Primary-Winner abgeleitet werden. Runtimeeigene Turn-Modelle sind erst eine getrennte Secondary Lane.

T1, etwa Pipecat mit direktem Carrier-WebSocket, ist ausdrücklich ein **full-topology secondary comparison**: eigener Carrier-, Region-, Codec- und Preismanifest; kein Ersatz und kein Beweis für eine Runtime-Überlegenheit in T0. Offline Replay, `sip_virtual` und `pstn_real` sind durch `transport_class` vollständig getrennt. Ergebnisse werden nicht vermischt.

## 3. Baseline B0: einzufrierende Arbeitshypothese

| Schicht | B0-Kandidat und vorgesehene Rolle | Vorläufiger Status / G0-relevante Grenze |
|---|---|---|
| Carrier / T0 | **Twilio SIP** am gemeinsamen Carrier-SIP-/LiveKit-Media-Pfad | `NOT FROZEN`; Tarif, DE-Inboundfähigkeit, TLS/SRTP/Codec/Firewall/DTMF, Rufnummernklasse und Kontoentitlement vor dem Adapter prüfen. Kein Twilio-Media-Streams-Mix in T0. |
| STT | **Deepgram Nova-3 multilingual**, Streaming, `de-DE` | Auditkandidat, nicht aktuelle Tatsachenbehauptung. Modell-ID, EU-Endpunkt/Datenpfad, Smartformat/Vocabulary, MIP-/Retention-Option, 8-kHz-Verhalten, Quoten und Metering müssen G0 bestehen. |
| Text-LLM | schneller OpenAI-Textkandidat, Auditname **`gpt-6-luna`** | Der Name ist ausdrücklich ein provisorischer Auditname, `NOT FROZEN`. Exakte Modell-ID, API, Region, Structured-/Tool-Schema, Streaming, Limits und Preisunit sind nicht angenommen. |
| TTS | streamingfähiges ElevenLabs-**Flash- oder Turbo**-Modell, deutsche freigegebene Stimme | `NOT FROZEN`; „Flash/Turbo“ ist keine ID. Endpoint-/Modellparität, Voice-Rechte, Streamingformat, Aussprache, Concurrent-Streams, Datenresidenz und Zeicheneinheit sind G0. |
| Fachpfad | serverseitiges Tool-Gateway, Calendar Mock, CRM Mock, PostgreSQL-RLS-Testumgebung | Für beide Runtimes identisch und autoritativ; kein Provider darf Tools direkt mit Daten-/Ausführungsautorität verbinden. |

B0 ist keine Vorauswahl. Die Audits nennen Deepgram, ElevenLabs und einen schnellen OpenAI-Textkandidaten aufgrund dokumentierter Funktionen, nicht aufgrund gemessener deutscher PSTN-Qualität. Insbesondere darf ein öffentliches Latenz- oder Preisbeispiel nicht in einen B0-Messwert oder einen EUR/Minute-Wert umgerechnet werden.

## 4. G0 – Pre-Implementation-Freeze (operative Blockade)

**Vor jeder Adapterimplementierung mit Livezugang** führt ein benannter Owner eine dokumentierte, menschlich freigegebene G0-Checkliste je eingesetzter Komponente aus. Ohne vollständigen Eintrag bleibt der Arm `BLOCKED`; ein Alias, eine Werbeaussage oder ein Auditdatum genügt nicht.

1. **Modell, API und SDK:** exakte Modell-/Voice-ID, Endpoint/API-Version, Streaming- und Tool-/Schemafähigkeit, freigegebene SDK-/Plugin-/Container-Version samt Lizenz; keine automatische Modellauflösung. Bei nicht snapshotfähigem Provider: Alias, `resolved_meta`, Abrufzeit und Wiederholungsblock im Freeze-Manifest.
2. **Datenpfad und Vertrag:** wirksame Region, Inferenz-, Logging-, Support-, Backup- und Subprozessorpfade, DPA/Retention/Opt-out, zulässige Testaudio- und Transcriptverarbeitung, Datenexport sowie Lösch- und Zugriffsmodell. „EU“ im Marketing ist kein Nachweis eines vollständigen Pfads.
3. **Zugang und Betrieb:** autorisierte Testaccounts, Quota-/Concurrency-Grenzen, Rate-Limits, Request-/Session-IDs, Fehlercodes, verbundene Carrierroute, Zahlungs-/Budgetfreigabe sowie sichere ENV-Referenzen. Zugelassen sind nur Namen wie `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `CARTESIA_API_KEY`, `TWILIO_ACCOUNT_SID` und `TWILIO_AUTH_TOKEN`; Werte werden weder angefordert noch dokumentiert.
4. **Media-Parität und Messbarkeit:** SIP-/DID-Route, SIP-Bridge-Eignung ohne unzulässige REGISTER-Annahme, TLS/SRTP/DTMF/Codec/Firewall, Clock-Mapping und Kalibrierung. Eine Clock-Uncertainty über **20 ms** ist als `PROPOSED` Stage-Vergleichsblocker zu behandeln, während eine gleiche Caller-Blackbox-Uhr weiterhin als begrenzt nutzbar markiert werden kann.
5. **Preis und Exit:** aktuelle Account-Tarife, Einheit, Mindestmenge/Credits, Currency, Billing-Export, Rate Card und Export-/Kündigungsbedingungen. Der Vertrag verbietet Minuten-Proxyrechnungen für Token, Zeichen oder Credits.

Review-Ziele aus den Audits, ohne heutige Neuverifikation: [Deepgram Modelle/Sprachen](https://developers.deepgram.com/docs/models-languages-overview), [Deepgram Datenhinweise](https://deepgram.com/trust-security/your-data), [ElevenLabs Modelle](https://elevenlabs.io/docs/overview/models), [ElevenLabs WebSocket-TTS](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts), [OpenAI Modelle](https://platform.openai.com/docs/models), [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling) und [OpenAI Datenhinweise](https://platform.openai.com/docs/guides/your-data). Cartesia- und Carrierdetails werden über die im Audit referenzierten Dossiers und die jeweils offizielle Vertragsdokumentation im G0 geprüft. Diese Links sind keine Freigabe und kein Nachweis gegenwärtiger Verfügbarkeit.

## 5. Gestufter Kaskadenvergleich

Die Auswahl findet ausschließlich auf Dev/Validation statt. Der vorgeschlagene Corpus umfasst 360 Kurzfälle sowie 160 Dialogskriptdefinitionen mit speaker-disjunkten Splits Dev/Validation/Holdout von 120/60/180 bzw. 40/40/80 Fällen; alle Umfangsangaben sind `PROPOSED`. Ground Truth bleibt dem Agenten verborgen. Abgeleitete Noise-/Codec-Versionen teilen `parent_id` und zählen nicht als neue unabhängige Fälle. Konkrete Fälle, Normalisierung und Aufnahmegates stehen in [03_German_Voice_Dataset_Specification.md](03_German_Voice_Dataset_Specification.md).

| Stage und Arms | Zulässige Änderung | Zweck und Selektionsschutz |
|---|---|---|
| S0 | keine Providerwertung | Freeze, Rechte, Legal, Medienparität, Kalibrierung und Instrumentation. Fehlende Freigabe bedeutet `BLOCKED`, nicht „bestanden“. |
| S2 B0 | B0-Komponenten isoliert | Component-Tests ohne Runtimewinner: STT-Entities/EOT, LLM-Toolvorschläge/Schema, TTS-Aussprache/Streaming. Dev/Validation allein, jeweils gepaarte Inputs und eingefrorene Hashes. |
| S3 `RT-A-B0`, `RT-B-B0` | nur Runtime | T0-End-to-End beider Python-Runtimes mit derselben B0-Konfiguration und denselben autoritativen Mocks. |
| S2 Ein-Faktor C-TTS | ElevenLabs → Cartesia Sonic Auditkandidat | Deepgram und B0-LLM bleiben unverändert. Kein gleichzeitiger LLM-Wechsel; Nutzen und Nebenwirkungen bleiben zuordenbar. |
| S2 Ein-Faktor C-LLM | B0-LLM → **genau ein** G0-freigegebener alternativer schneller Textkandidat | Auswahl exakt eines Kandidaten: Auditname `gpt-6.1-sol` **oder** Mistral mit freigegebener ID. Die nicht gewählte Alternative gehört nicht in C1. Deepgram und ElevenLabs bleiben unverändert. |
| S4 `RT-A-C1`, `RT-B-C1` | Cartesia + der eine Alternativ-LLM gemeinsam | Erst nach beiden Ein-Faktor-Vorläufen; derselbe C1-Hash auf beiden Runtimes. |

Speechmatics ist kein verdeckter dritter Faktor. Es darf ausschließlich als vorregistrierter conditional C-STT-Branch aufgenommen werden, wenn ein dokumentierter Dev/Validation-Trigger (kritische STT-Entity-Zielverfehlung, unzulässiger Datenpfad oder nicht tragfähige Einheit) eintritt und menschlich freigegeben wurde. Sein Ergebnis wird nicht als TTS-/LLM-Effekt attribuiert.

Für jede zulässige Änderung erzeugt der Harness eine Differenzkarte: vorheriger/neuer Component-Hash, unveränderte Schichten, Dataset-/Prompt-/Tool-/Fixturehash, Arm, Transportklasse, Abweichungen und `selection_split`. Die Randomisierung verwendet den Vertragsseed `24022026`; höchstens drei vorregistrierte Wiederholungen pro Fall, erster Fehlschlag zählt. Holdout wird weder für Prompt-, Voice-, Modell-, Endpoint- noch Schwellenwerttuning geöffnet.

## 6. Pflichtvergleich: nativer Voice-Pfad

S5 `N-OAI-BEST` vergleicht **OpenAI Realtime** – exakte ID erst nach G0 – mit der besten vorregistriert auf Validation bestimmten Kaskade. „Best“ folgt vor der Einsicht in Holdout einem dokumentierten Mehrzielverfahren: Hard-Safety-/Datenpfad-Vetos zuerst, danach Qualität, Latenz, Kosten und Betriebsaufwand mit registrierten Gewichten. Kein kleiner Geschwindigkeitsvorteil kann unautorisierte Ausführung, Cross-Tenant-Zugriff, fehlende Bestätigung oder unzulässigen Datenpfad überdecken.

Der native Pfad bleibt auf T0: gleiche Carrierroute, DID, LiveKit Media/Room, Region-/Hardwareklasse, Promptinhalt, Knowledge-Base-Fixture, Calendar Mock, CRM Mock und sicheres Tool-Gateway. Direkt-SIP oder andere Medienroute ist höchstens klar gelabelte Secondary Lane. Native Audio/Text-Token sind als eigene Kostenarten zu erfassen; zusätzliches STT/TTS wird nicht als Kernkosten unterstellt. Shadow-ASR, unabhängige Rater und Transkriptvergleich sind separat `eval_only` und kostenmäßig getrennt.

Native Spracheingabe, Providertranskript und Tool-Argumente sind **untrusted evidence**, nie Bestätigungs- oder Berechtigungsquelle. Die serverseitige Contact-/Slot-Policy fordert finite affirmative/negative Grammatik, aktuelle Readback-Hash-Version und Invalidierung bei Korrektur. Fehlt eine unabhängig auditierbare Bestätigungsgrundlage, ist eine gleichwertige geregelte DTMF-/Secure-Confirmation erforderlich; andernfalls der Buchungs-Test `BLOCKED`. Der native Anbieter erhält niemals eine direkte Kalender-/CRM-Autorität.

Falls OpenAI Realtime G0 scheitert, sind **GPT-Live oder Gemini Live** Alternativen, nicht zusätzliche Siegerkandidaten: genau einen Fallback per G0 begründen, registrieren und als einzigen verpflichtenden nativen Pfad ausführen. Ein zweiter nativer Pfad ist optional und budgetabhängig. Providerunzugängliche Zwischenereignisse bleiben `UNOBSERVABLE` oder `NOT APPLICABLE`, niemals `0`.

## 7. Mess-, Qualitäts- und Sicherheitsorakel

Die primäre Latenz ist caller-observierbar: `AI_AUDIO_START – USER_AUDIO_END` auf gemeinsamer Caller-Monotonic-/Sampleclock. Nicht Endpointing oder SDK-TTFB. Neben p50/p95/max werden Versuche, Erfolge, Fehler, Timeouts und Invalids getrennt erfasst; Deadline-Outs gehen konservativ als Fehler ein. Interne STT-Final-, LLM-TTFT- und TTS-TTFB-Ereignisse erklären Teilpfade, werden wegen Streamingüberlappung aber nie addiert. Details, JSONL-Events, Clock- und CI-Regeln stehen in [04_Measurement_Telemetry_Specification.md](04_Measurement_Telemetry_Specification.md).

Providerqualität bedeutet nicht nur WER: Person, Telefon, E-Mail, Adresse, Datum/Uhrzeit und Geld erhalten getrennte Nenner, Normalisierung und Bestätigungsorakel. Für TTS registriert der Plan vorab einen verblindeten Hörtest auf deutsche Verständlichkeit, Aussprache von Namen/Zahlen/Abkürzungen, Angemessenheit, Langturn-Stabilität und hörbaren Start; Rater sehen weder Provider/Voice noch Runtime. Solche Urteile sind Qualitätsdaten, keine Messwerte vor Testbeginn.

Alle Pfade laufen gegen dieselben Negativ- und Failure-Orakel: unbekannte Toolfelder ablehnen, keine willkürliche URL/SQL/Shell, keine fremde Kalender-/CRM-Referenz, `UNKNOWN` bei verlorener Buchungsantwort, Statusreconciliation vor weiterer Buchung, niemals Erfolg ohne `BOOKING_CONFIRMED`. Jede ausgeführte unautorisierte Aktion, jeder Cross-Tenant-Zugriff, jeder Call trotz serverseitiger Suppression und jede falsche Buchungserfolgsaussage ist **AUTOFAIL**. Diese Veto-Orakel gelten auch, wenn ein Provider bessere Audioqualität zeigt; der vollständige Katalog steht in [05_Security_Failure_Test_Plan.md](05_Security_Failure_Test_Plan.md).

Jeder Provider-Arm erhält vorerst exakt diesen Resultatstumpf:

| Feldgruppe | Aktueller Wert |
|---|---|
| `test_state`, `evidence_status` | `NOT TESTED` |
| Latenz-, Qualitäts-, Rater-, Ausfall- und Sicherheitsmetriken | `null` |
| Verbrauchsmenge, Tarif, Kosten, Rechnungskorrelation | `null` |
| Observability | `MISSING` bis G0/Kalibrierung, danach je Feld `AVAILABLE`, `UNOBSERVABLE` oder `NOT APPLICABLE` |
| Gewinner, Empfehlung, abgelehnte Alternative | `null` / `NOT DECIDED` |

## 8. Kosten, Lock-in, Übergabe und Entscheidung

Die Kostenvergleichbarkeit beginnt nicht mit Auditpreisen: pro Call/Turn und Provider werden reale Nutzungsereignisse, Providerprodukt, Request-/Session-ID, Unit, Menge, aktuelle gefrorene Rate, Region, Billingperiode und Evidence gespeichert. Erst `actual usage × account rate` ergibt `METERED_COST_PROVISIONAL`; erst Billing-Export/Invoice-Abgleich `COST_RECONCILED`. Fehlende Unit, Rate oder Rechnung bleibt spezifisch `NOT TESTED` bzw. `BLOCKED`, nicht null Kosten. Carrier-/Caller-Testleg, T0-geteilte Media-Allokation, native Audio/Text, Shadow-Evaluierung, Traces/Storage und Standby/Cloud werden getrennt ausgewiesen. Das Ledgerdesign folgt [08_Cost_Measurement_Plan.md](08_Cost_Measurement_Plan.md).

Provider-Lock-in wird nicht durch die kleinste gemeinsame Schnittmenge verborgen. Für STT werden Final/Partial/EOT/Vocabulary, für TTS Voice/Pronunciation/Buffer, für LLM Tool-/Schema-/Promptverhalten und für Native Session-/Audit-/Exportgrenzen in Adapter- und Exit-Karten festgehalten. Der praktische Exit-Test ist ein begrenzter Adapterwechsel auf denselben Fixtures, keine theoretische Migrationsbehauptung. Operative Komplexität umfasst gemessene Integrations-, Debugging-, Fehlersuche- und Betriebsstunden erst nach Durchführung, nicht vermutete Teamkapazität.

Die Entscheidungskarte zu STT, TTS, LLM und nativer Architektur bleibt `PROPOSED` und verweist auf [11_ADR_Templates.md](11_ADR_Templates.md). Die vorgegebenen Produktziele – p95 Non-Tool-Latenz ≤ 1.500 ms, Median ≤ 800 ms, p95 Interrupt-Stop ≤ 300 ms, bestätigte kritische Felder ≥ 99 % sowie null unautorisierte Ausführung/falsche Buchungserfolge/Cross-Tenant-Leaks – sind ausschließlich `PROPOSED` und müssen vor Holdout von einem Menschen als `ACCEPTED`, `CHANGED` oder `REJECTED` markiert werden. Sicherheitsvetos und ausreichende Versuch-/Task-Completion-Abdeckung verhindern, dass ein Verweigerungsagent gewinnt; die verbindliche Prüfung steht in [09_Acceptance_Criteria.md](09_Acceptance_Criteria.md).

Nach S0–S5 kann der menschliche Gate Owner nur einen evidenzgerechten Zustand wählen: `HOLD_FOR_EVIDENCE`, `NO_GO`, `GO_FOR_AUTHORIZED_TESTS` oder – bei vollständiger, freigegebener Evidenz – `GO_FOR_SCOPED_ARCHITECTURE_DECISION`. Ein Harness-Pass ist nie Produktionsfreigabe. S6 reserviert den einmaligen Holdoutvergleich; S7 (Lifecycle/Load) und S8 (sekundäre Architekturentscheidungen) ändern keine Providerentscheidung rückwirkend ohne registrierte neue Gate-Entscheidung. Siehe [02_Benchmark_Matrix.md](02_Benchmark_Matrix.md), [06_Runtime_Comparison_Plan.md](06_Runtime_Comparison_Plan.md), [10_Claude_Code_Benchmark_Implementation_Specification.md](10_Claude_Code_Benchmark_Implementation_Specification.md) und [12_Decision_Gate_Template.md](12_Decision_Gate_Template.md).

## 9. Operative G0-Blocks und Definition of Ready

Der Providervergleich ist **nicht ausführungsbereit**, solange mindestens einer der folgenden Punkte offen ist:

- menschliche Freigabe von Testdatenrechten, Aufnahme-/Ratergrundlage, Budget, Testregion und zulässigen Accounts;
- G0-Freeze jeder B0-, C1- und Native-Komponente inklusive Model/Voice/API/SDK/Endpoint, DPA/Lizenz, Datenpfad, Quota, Rate Card und Billing-Export;
- nachgewiesene T0-SIP/Media-Parität, Caller-Clock-Kalibrierung und sichere ENV-Referenzierung ohne Secretwerte;
- funktionsgleiche serverseitige Tool-Gateway-, Confirmation-, Calendar-Mock-, CRM-Mock- und echte PostgreSQL-RLS-Preflights;
- freigegebene, rechtmäßig verfügbare speaker-disjunkte Audio-/Dialogfixtures; fehlende Audiofiles bleiben `NOT RECORDED` und blockieren Audioevaluation;
- vor Einsicht in Holdout akzeptierte Kriterien, Paarungs-/Wiederholungsregel, Blindtestprotokoll, Cost-Allokation und Fallbackregel.

Erst wenn diese Blocks dokumentiert geschlossen sind, kann Claude Code den isolierten Harness nach den verlinkten Spezifikationen implementieren und ein autorisierter Mensch dessen Tests freigeben. Bis dahin besteht keine Providerempfehlung.


### Verbindliche Integrationspräzisierung

Reine S2-Anbieter-APItests verwenden den eigenen Modus `component_api`, nicht `offline`; G0, Providerautorisation, Rechte und Budget bleiben Pflicht. Eine gemeinsame `comparison_id` verbindet die zugehörigen Arme; `arm_id` identifiziert die Variante. Der Planungskatalog wird vor Ausführung in ein eindeutiges Runmanifest aufgelöst. Native S5 verlangt einen zeitnahen Referenzlauf der besten Kaskade. Maßgeblich sind die [Integrationspräzisierungen](contracts/Harness_Integration_Addendum.md), einschließlich nativer Ausgabesteuerung und separater echter Holdout-Custody.
