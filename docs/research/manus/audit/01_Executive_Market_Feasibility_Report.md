# 01 – Executive Market & Feasibility Report

**Stand und Quellenabruf: 21.10.2026.** Entscheidungsgrundlage, keine endgültige Architektur. Der Audit umfasst 46 abgegrenzte Recherchen, elf Wettbewerber, 40 Wettbewerbsmerkmale und gesonderte Analysen der Voice-, Telefonie-, Workflow-, Infrastruktur- und Sicherheitsbereiche. Die vollständigen Einzelbelege liegen im Verzeichnis `../research/`; die zwölf Dokumente verdichten sie für den Review.

## Management-Fazit

Eine eigenständige AI-Voice-Plattform mit dem öffentlich sichtbaren Kernnutzen von Team Follow Up AI ist **technisch plausibel realisierbar**, ohne selbst Spracherkennung, Sprachsynthese oder ein Telefonnetz entwickeln zu müssen. Marktverfügbare Frameworks, Speech-/LLM-APIs und SIP-/CPaaS-Anbieter liefern wesentliche Infrastruktur. Das strategisch eigene Produkt besteht dagegen aus Mandanten- und Agenturverwaltung, Agent-Lifecycle, sicheren Business-Tools, Lead-/Kampagnenprozessen, Integrationen, Qualitätskontrolle, Abrechnung und nachvollziehbarer Compliance.

Das ist keine bereits bewiesene Produktionsmachbarkeit. Insbesondere **deutsche Gesprächsqualität über PSTN, verbindliche EU-Datenpfade, automatisierte Outbound-Nutzungsrechte, Concurrency und Vollkosten** sind noch nicht ausreichend praktisch bzw. vertraglich validiert. Die angemessene nächste Entscheidung ist deshalb ein begrenztes Validierungsprogramm und anschließendes Decision Gate – nicht die sofortige Festlegung aller Technologien.

**Confidence:** hoch, dass erforderliche Infrastrukturbausteine dokumentiert verfügbar sind; mittel für deren kombinierte Produktpassung; niedrig für gemessene Qualität, Kapazität und Profitabilität unserer noch nicht existierenden Plattform. [livekit.docs.agents](https://docs.livekit.io/agents/) [pipecat-P04](https://docs.pipecat.ai/pipecat/learn/transports) [twilio-streams](https://www.twilio.com/docs/voice/media-streams) [tenancy-3](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)

## 1. Was Team Follow Up AI als Referenz tatsächlich zeigt

Das Referenzprodukt positioniert sich erkennbar für GoHighLevel-basierte Lead-Gen-Agenturen: Leads schnell anrufen, qualifizieren, Termine buchen und an Mitarbeiter übergeben. Öffentlich beworben werden editierbare Prompts, Persönlichkeiten und Stimmen, visuelle Workflows sowie clientfähige Gesprächsergebnisse. Die aktuellen App-AGB bestätigen eine gehostete Plattform für Voice-Agenten und Kampagnen mit aus- und eingehenden Calls; die Datenschutzerklärung bestätigt Audio-, Transkript- und Outcome-Verarbeitung. Das belegt den angebotenen Funktionszweck, nicht den zugrunde liegenden technischen Stack. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) [teamfollowup-s5](https://app.teamfollowup.ai/terms) [teamfollowup-s6](https://app.teamfollowup.ai/privacy)

Mehrere für unser Zielprodukt zentrale Fragen bleiben öffentlich offen: API/SIP, Mandantenisolation, immutable Agent-Releases, deutsche Qualitätswerte, vollständige Gebühren, Limits und Datenregionen. Besonders relevant ist der Widerspruch zwischen White-Label-/Resale-Marketing und einem Standard-AGB-Verbot ohne ausdrückliche Erlaubnis. Der veröffentlichte Einstieg von **97 USD/Monat nach 14 Tagen** ist kein verifizierter All-in-Minutenpreis; andere Signup-Texte widersprechen dem Testangebot. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s4](https://app.teamfollowup.ai/signup-30-day-free-trial) [teamfollowup-s5](https://app.teamfollowup.ai/terms)

Daraus folgt kein Beweis, dass diese Funktionen fehlen. Es folgt, dass unser Produkt nicht durch unkritisches Abschreiben einer Landingpage spezifiziert werden sollte. Das belastbare Referenzziel ist die **geschäftliche Outcome-Journey**, nicht ein behaupteter interner Stack oder eine unbekannte Dashboard-Navigation.

## 2. Marktstruktur und strategische Position

| Marktsegment | Beispiele im Audit | Relevanz für uns | Zentrale Grenze |
|---|---|---|---|
| Voice Infrastructure | Vapi, Retell; Bolna als Hosted/OSS-Mischfall | Schnell nutzbare Orchestrierung, APIs und Telefonpfade | Runtime- und kommerzielle Abhängigkeit trotz modularer Providerwahl |
| Voice SaaS / Builder | Synthflow, ElevenLabs Agents, Voiceflow, Bland mit Infrastrukturüberschneidung | Agenten-UX, Flows, Testing, Kampagnen als Produktreferenz | Fertige Plattform ist nicht automatisch OEM-/White-Label-Infrastruktur |
| Agency / Lead Automation | Team Follow Up AI; Agency-Angebote von Synthflow/Voiceflow | Multi-Client-Journey, CRM-Nähe, Wiederverkauf | Rechte, Isolation und Pricing sind separate Prüfgegenstände |
| Enterprise Conversational AI | Cognigy, PolyAI, Parloa | Governance, Simulation, Contact-Center-Handover | Vertriebsgeführte Angebote; öffentliche Preis- und API-Lücken |

Die Einteilung ist eine **analytische Einordnung**, keine trennscharfe Herstellerkategorisierung. Einige Produkte bedienen mehrere Segmente. Der Wettbewerb wird nicht allein über „spricht natürlicher“ entschieden: Tests, Integrationszuverlässigkeit, Betriebssteuerung und Governance sind bereits sichtbare Produktdimensionen. ElevenLabs dokumentiert Agent Testing; Parloa bewirbt Simulation und Versionsvergleich; Cognigy dokumentiert eine umfassende Enterprise-Voice-Schicht. Eine bloße Promptmaske mit gekaufter Voice-API wäre daher eine schwache Differenzierung. [el-testing](https://elevenlabs.io/docs/eleven-agents/customization/agent-testing) [el-workflows](https://elevenlabs.io/docs/eleven-agents/customization/agent-workflows) Weitere Anbieterbelege und planbezogene Grenzen: [03 – Competitive Landscape](03_Competitive_Landscape.md).

**Marktgröße, Wachstumsrate und Zahlungsbereitschaft sind nicht verifiziert.** Aus elf Anbieterprofilen folgt kein quantifizierter TAM und kein Nachweis, dass eine Agentur für unsere konkrete Lösung bezahlt. Kundeninterviews und ein kontrollierter Pilot müssen diese Geschäftshypothese prüfen.

## 3. Was sinnvoll selbst kontrolliert werden sollte

Die wichtigste strategische Grenze verläuft zwischen austauschbarer Infrastruktur und unserer fachlichen Autorität. Eigenständig kontrolliert werden sollten Tenant-/Client-Rechte, Agent-Releases, Einwilligungs- und Sperrregeln, Kampagnenzustände, Business-Tool-Verträge, Usage-Ledger, Kundenergebnisdefinitionen und Integrationsfehlerbehandlung. STT, TTS, LLM und PSTN werden zunächst eingekauft; offene Voice-Frameworks und gegebenenfalls verwaltetes Hosting bilden eine hybride Schicht. Die detaillierte BUILD/BUY/HYBRID-Matrix steht in Bericht 07.

Provider-Unabhängigkeit ist dabei kein Alles-oder-nichts-Ziel. Ein gemeinsames Transcript-/Turn-/Tool-Ereignismodell kann Migration erleichtern; Stimmen, Turn-Semantik, native Audiozustände, Rufnummern und langlebige Workflows bleiben dennoch migrationsintensiv. SIP abstrahiert nicht automatisch Call-Control, KYC oder Portierung. Ein Exit-Plan muss deshalb Datenexport, Nummernübertragbarkeit, Konfigurationsrechte, Credential-Zuordnung und Testparität umfassen. [livekit.docs.pipelines](https://docs.livekit.io/agents/models/pipelines/) [pipecat-P04](https://docs.pipecat.ai/pipecat/learn/transports) [twilio-sip](https://www.twilio.com/docs/sip-trunking)

## 4. Technische Machbarkeit und wichtigste Trade-offs

**LiveKit und Pipecat sind beide ernsthafte Kandidaten.** LiveKit dokumentiert integrierte Media-/Room-/Job-Abstraktionen, SIP und Python-/Node-Agenten. Pipecat dokumentiert Python-Pipelines mit austauschbaren Transporten und Speech-Anbietern; seine TypeScript-Pakete sind Client-SDKs, nicht eine gleichwertige Server-Runtime. Pipecat kann auch einen LiveKit-Transport verwenden: Framework und Medientransport sind verschiedene Entscheidungsebenen. Es gibt keine gemessene Evidenz, welcher Kandidat unsere deutsche Telefonie besser erfüllt. [livekit.docs.agents](https://docs.livekit.io/agents/) [livekit.docs.telephony](https://docs.livekit.io/telephony/) [pipecat-P04](https://docs.pipecat.ai/pipecat/learn/transports) [pipecat-P05](https://docs.pipecat.ai/client/js/introduction)

Die **Kaskade STT → LLM → TTS** ermöglicht stärkere Textinspektion, Austauschbarkeit und Entity-/Tool-Evaluation, hat aber zusätzliche Streaming-, Endpointing- und Fehlerstellen. **Native Speech-to-Speech** kann prosodische Informationen und Interaktion in einer Session erhalten, erzeugt jedoch höhere Modell-/Sessionbindung und weniger vergleichbare Zwischenrepräsentationen. Kontrollierte Backend-Tools bleiben in beiden Fällen notwendig. „Nativer Audiopfad“ bedeutet nicht „Modell darf Termine autoritativ buchen“. [openai-09](https://platform.openai.com/docs/guides/voice-agents) [openai-13](https://platform.openai.com/docs/guides/function-calling) [livekit.docs.pipelines](https://docs.livekit.io/agents/models/pipelines/)

Durable Workflows koordinieren Scheduling, Consent-Prüfung, Retry und Nachbearbeitung; sie sollten nicht Audioframes oder Turntaking steuern. Temporal ist ein belastbarer Kandidat für lang laufende Prozesse; BullMQ kann bei geringerem Persistenz-/Replay-Bedarf einfacher sein. n8n eignet sich für externe Integrationen, hat aber für Einbettung und Kundenzugang relevante Lizenzgrenzen. Restate ist eine weitere Durable-Alternative mit BSL-Nutzungsgrenzen. Externe Seiteneffekte bleiben bei allen Lösungen idempotenz- und reconciliationbedürftig. [tenancy-6](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) [restate.workflows](https://docs.restate.dev/tour/workflows) [restate.license](https://raw.githubusercontent.com/restatedev/restate/main/LICENSE)

## 5. Wirtschaftliche Einordnung

Die Minutenkosten bestehen aus mehreren unterschiedlich gemessenen Einheiten: Carrierzeit und Transferlegs, verarbeitete STT-Audiokanäle, wiederholt gesendete LLM-Kontexte, TTS-Zeichen bzw. Audioausgabe, Runtimezeit, Mitschnitte, Retention und Analytics. Die neun Szenarien in Bericht 08 sind **Planungsmodelle auf offiziellen Unit-Preisen und ausdrücklich angenommenem Verbrauch**, keine Anbieterangebote oder gemessenen Produktionskosten.

Ein Kernrisiko sind deutsche Mobilrouten: Twilios geöffnete Detailtabelle unterscheidet günstige EEA-Herkunft und erheblich teurere andere Routen. Ein globaler Telnyx-„ab“-Preis ist kein deutscher Zieltarif. Auch eine deutsche Flatrate kann für automatisierte Anrufe oder Reselling ungeeignet sein: easybell schränkt Maschine-zu-Mensch-Nutzung in Flatrates ein; sipgate.io untersagt gewerbliche Weitergabe ohne Zustimmung. [twilio-pricing](https://www.twilio.com/en-us/voice/pricing/de) Die jeweiligen Vertragsbelege stehen in [05 – Telephony](05_Telephony_Infrastructure_Audit.md).

Technisch kleine Tokenkosten sind außerdem kein Argument gegen Backend-Sicherheit. Der wirtschaftlich relevante Wert ist **Kosten pro zulässigem, korrekt qualifiziertem und fachlich bestätigtem Ergebnis** – nicht allein Preis pro verbundener Minute. Versuche, schlechte Erkennung, Doppelbuchungen, Transfers und Support erhöhen die tatsächlichen Ergebnis- und Betriebskosten.

Für eine Geschäftsentscheidung fehlen Teamgröße, Budget, Erstkundensegment, Preisbereitschaft, SLO, Peak-Concurrency und Supportmodell. Vollständige HA-, SRE-, Produktentwicklungs- und Vertriebskosten dürfen nicht aus einem günstigen VM-Preis abgeleitet werden.

## 6. Compliance als Produkt- und Markteintrittsgrenze

Deutsche B2C-Telefonwerbung benötigt vorherige ausdrückliche Einwilligung; für automatische Anrufmaschinen enthält §7 UWG eine ausdrückliche Einwilligungsregel. Die konkrete Einordnung eines interaktiven KI-Agenten und B2B-Kampagnen erfordert spezialisierte Rechtsprüfung. Ein berechtigtes Datenschutzinteresse oder eine mutmaßliche B2B-Einwilligung ist kein pauschales Recht für KI-Kaltakquise. [compliance-03](https://www.gesetze-im-internet.de/uwg_2004/__7.html) [compliance-04](https://www.gesetze-im-internet.de/englisch_uwg/englisch_uwg.html)

KI-Transparenz, Aufzeichnung, Live-Verarbeitung, Transkription und weitere Analysen sind getrennte Zwecke/Pflichten. Recording sollte bis zur fallbezogenen Freigabe ausgeschaltet sein; die fünfjährige Aufbewahrung von Verbraucher-Werbeeinwilligungsnachweisen ist keine fünfjährige Call-Recording-Erlaubnis. §201 StGB ist ein eigenständiges Risiko. [compliance-08](https://www.gesetze-im-internet.de/stgb/__201.html) [compliance-01](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng)

EU-Hosting ist ebenfalls keine einzelne Checkbox: Medien, Inferenz, Logs, Backups, Support und Subprozessoren müssen getrennt kartiert werden. Ein EU-Endpunkt kann zusätzliche Parameter, Enterprise-Verträge oder Modellbeschränkungen voraussetzen. Deepgram verlangt für seine regionale Garantie zusätzlich MIP-Opt-out; OpenAI dokumentiert Einschränkungen bei Realtime-Tracing. [deepgram.data](https://developers.deepgram.com/trust-security/your-data) [deepgram.regions](https://developers.deepgram.com/reference/regional-endpoints) [openai-10](https://platform.openai.com/docs/guides/your-data)

## 7. Priorisierte Produktchancen – noch keine bewiesenen Moats

**Produktannahmen:** Besonders plausibel sind deutsche Entity-Qualität mit nachvollziehbaren Tests, ein verständlicher Call-Preflight, sichere CRM-/Calendar-Aktionen, immutable Releases mit Regressionstests, Agency-Margin-/Client-Reporting und operativ vollständiges Human Handover. Der Wert liegt nicht in einem pauschalen „DSGVO-konform“-Label, sondern in nachweisbaren Kontrollen und Ergebnissen. Wettbewerb und Zahlungsbereitschaft können diese Hypothesen bestätigen oder widerlegen; Bericht 10 macht die Bewertung transparent.

Automotive und Fleet können später spezialisierte Templates erhalten, dürfen aber Kern-Domänen und Architektur nicht an Gutachtery24 binden. Unfallaufnahme kann zusätzliche sensible Daten verarbeiten und sollte nicht unbesehen der erste Outbound-MVP sein.

## 8. Entscheidungsvorbereitung und Stop-Kriterien

Der nächste Gate sollte vier Nachweise verlangen: rechtliche Zulässigkeit der ersten Use Cases; vertraglich dokumentierter Daten-/Telefoniepfad; reproduzierbarer deutscher Voice-/Tool-Benchmark; belastbares Kapazitäts- und Kostenprofil. Kein Produktionsstart bei unzulässigem Outreach, Cross-Tenant-Leak, nicht autorisierter Tool-Aktion oder unklarer Aufnahmegrundlage. Quantitative Qualitäts- und Latenzziele sind vor dem Benchmark als Produktannahmen festzulegen.

**Was die Empfehlung ändern würde:** Ein Framework kann beim identischen PSTN-Test deutlich zuverlässiger sein; ein EU-Vertrag kann einen günstigen Provider ausschließen; Lizenz-/Resalebedingungen können einen Kandidaten disqualifizieren; Kunden können die Agency-Features nicht wertschätzen; hohe Mobilkosten können das geplante Pricing unprofitabel machen. Genau deshalb bleibt die finale Technologieauswahl offen.

**Reviewfolge:** Berichte 02–03 für Referenz/Markt, 04–06 für technische Grenzen, 07–09 für Kontrolle/Wirtschaftlichkeit/Risiken, anschließend 10–12 für Priorisierung und Decision Gate. ChatGPT prüft die Entscheidungsgrundlage; der menschliche Projektverantwortliche entscheidet; Claude Code implementiert erst nach Freigabe.
