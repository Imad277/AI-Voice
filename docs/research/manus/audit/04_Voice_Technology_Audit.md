# 04 – Voice Technology Audit

**Stand / Quellenabruf: 21.10.2026.** **Fazit:** LiveKit und Pipecat sind beide geeignete Kandidaten für einen kontrollierten Benchmark. Eine modulare Kaskade ist für überprüfbare Geschäftsdialoge eine sinnvolle Testbaseline; native Speech-to-Speech ist parallel auf Natürlichkeit, Unterbrechung und Kosten zu prüfen. **Keine finale Runtime-, Modell- oder Providerentscheidung.**

**Confidence:** hoch für dokumentierte Fähigkeiten; mittel für abgeleitete Produktpassung; niedrig für tatsächliche deutsche PSTN-Qualität, p95-Latenz und Betriebsstabilität. Anbieter-Latenzwerte sind keine eigenen Messungen. Alle nachfolgenden Preise sind veröffentlichte Original-USD-Einheiten zum Abrufdatum, keine verbindlichen EU-Angebote.

## 1. Runtimevergleich: LiveKit Agents vs. Pipecat

| Kriterium | LiveKit Agents | Pipecat | Entscheidungsauswirkung |
|---|---|---|---|
| Architektur | AgentSession/AgentServer, Jobs, Rooms, Tracks, WebRTC | Frames, Prozessoren, Streaming-Pipelines, austauschbare Transports | Unterschiedliche Lifecycle-/Medienabstraktionen, kein reiner Bibliothekstausch |
| Realtime Performance | Streaming, Turn-/Interrupthandling dokumentiert | Streaming, VAD/Turn-Strategien/Interrupts dokumentiert | Deutsche E2E-Latenz und Last NICHT VERIFIZIERT |
| Telefonie / SIP | integrierte SIP-Room-/Dispatch-Abstraktion, In-/Outbound, Transfers | Carrier-WebSocket-Serializer, Daily/LiveKit und weitere Transportpfade | Pipecat nicht selbst Carrier; LiveKit SIP unterstützt kein SIP REGISTER |
| Agent Orchestration | Worker-/Job-Lifecycle und Sessions | Pipeline-/Flow-/Workersteuerung | Nicht mit langlebigen Business-Workflows gleichsetzen |
| Tools | SDK-Tools, kontrollierte Handler, Handoffs | Funktionen/Flows/Toolhandler | Autorisierung und Seiteneffektkontrolle bleiben Backendpflicht |
| Interruptions | Stop-/Cancel-/Resume-Verhalten im Sessionmodell | Pipelineunterbrechung, Bot-Ausgabe abbrechen | False Barge-in, lost words und committed context testen |
| Turn Detection | VAD/STT/native bzw. eigene Turn-Modelle | Silero VAD, Smart Turn/Strategien, Provider-End-of-Turn | Prosodie, Pausen, Backchannels und Lizenz separat |
| Observability | SDK-Telemetrie, Cloud Session-/Audio-/Eventdaten | Observer/OTel und Evals; Cloud Observability | Eigene PII-/Retention-/Regionkontrollen, fail-open Tracing |
| Deployment / Scaling | Cloud-Agenthosting oder eigene Worker/Server/SIP | Python-Prozesse/Container, Cloudprofile oder eigener Betrieb | Coldstarts, drain, worker failure, aktive Calls bei Rollout testen |
| Python | Server-Agent-SDK | Server-Framework | Beide sinnvoll testbar |
| TypeScript | separates Node.js-Agent-SDK | JS/React u.a. Client-SDKs, kein belegtes TS-Serverframework | Nicht „beide Python und TS gleichwertig“ behaupten |
| Provider Independence | Plugins und direkte Keys vs LiveKit Inference | Serviceadapter und unterschiedliche Transporte | Nicht alle Provider haben gleiche Events/Features |
| Self-Hosting | Media-/SIP-/Agent-Komponenten mit eigener Betriebsverantwortung | Framework selbst hostbar; Carrier/Transport und Betrieb extra | Kein automatisches HA/Compliance-Versprechen |
| EU Deployment | mehrschichtige Cloudregion-/Inference-/SIP-Konfiguration | eigenes EU-Deployment; Cloud-Europe und Enterprise-Details vertraglich | Logs/Support/Backups und Failover separat prüfen |
| Community / Activity | sichtbares Agents-Release 1.8.8, 15.10.2026 | sichtbares Release 1.13.0, 19.10.2026 | Contributorzahlen dynamisch nicht verifiziert; Releaseaktivität ist kein SLO |
| Production Readiness | Produktions-/Scalingdocs vorhanden | Deploy-/Scaling-/Evaldocs vorhanden | Zielprofil, Recovery und HA nicht praktisch geprüft |
| Lizenz | Framework Apache-2.0; Turn-Modelle separate License | BSD-2-Clause; Services/Modelle separat | Commercial SaaS grundsätzlich mit Hinweispflichten, Assets extra prüfen |

**Belege:** [livekit.docs.agents](https://docs.livekit.io/agents/) [livekit.docs.sessions](https://docs.livekit.io/agents/logic/sessions/) [livekit.docs.telephony](https://docs.livekit.io/telephony/) [livekit.docs.selfhost](https://docs.livekit.io/deploy/custom/deployments/) [livekit.modellicense](https://github.com/livekit/agents/blob/main/MODEL_LICENSE) [livekit.releases](https://github.com/livekit/agents/releases) [pipecat-P03](https://github.com/pipecat-ai/pipecat) [pipecat-P04](https://docs.pipecat.ai/pipecat/learn/transports) [pipecat-P05](https://docs.pipecat.ai/client/js/introduction) [pipecat-P06](https://docs.pipecat.ai/pipecat/learn/speech-input) [pipecat-P07](https://docs.pipecat.ai/pipecat/evals/overview) [pipecat-P11](https://github.com/pipecat-ai/pipecat/blob/main/LICENSE) [pipecat-P12](https://github.com/pipecat-ai/pipecat/releases). Vollständige Einschränkungen: [LiveKit-Dossier](../research/livekit.md), [Pipecat-Dossier](../research/pipecat.md).

### Bedingte Empfehlung und Gegenargument

LiveKit zuerst in einem SIP-/Room-/Session-orientierten Benchmark testen, wenn integrierter Medien-/Job-Lifecycle wichtig ist. Pipecat gleichwertig gegenprüfen, wenn ein expliziter Python-Pipelinepfad mit verschiedenen Carrier-WebSockets und Transporten gut zum Team passt. **Diese Reihenfolge ist eine Arbeitshypothese**, keine festgelegte Architektur. Pipecat kann LiveKit als Transport nutzen; diese Kombination löst keine doppelte Produktanforderung automatisch und sollte nur bei konkretem Nutzen zusätzliche Komplexität erzeugen.

LiveKit bringt eigene Server-/Room- und gegebenenfalls Cloud-Bindung; Pipecat spart diese Bindung nicht für jeden Transport, verlagert aber Medien-/Job-/SIP-Betriebsarbeit. Ein Test muss auch Integrationszeit, Debugging, Rollout/Drain, Fehlerwiederaufnahme und Providerwechsel messen – nicht nur den schnellsten Beispielturn.

**Weitere Alternativen:** Vocode bietet historisch dokumentierte Python-/Twilio-Kaskaden, jedoch jüngste verifizierbare Aktivität aus 2024: Wartungsrisiko. Bolna liefert MIT-Framework plus Hosted-Produkt, dessen Deutschland-/EU-Passung offen bleibt. Vapi/Retell/native Anbieter-Voice-APIs sind Buy-Alternativen, aber keine gleichartigen offenen Frameworks. [Vocode](../research/vocode.md) [Bolna](../research/bolna.md)

## 2. Speech-to-Text für deutsche Echtzeit-Telefonie

| Kandidat / dokumentiertes Modell | Streaming / Audio / Endpointing | Vocabulary / Entitäten | EU-Verarbeitung | Veröffentlichte Preisbasis | Offener Test |
|---|---|---|---|---|---|
| Deepgram Nova-3 multilingual / Flux multilingual | Deutsch; Flux unterstützt 8 kHz und modellnative EOT; Nova braucht getrennte Turnlogik | Keyterms dokumentiert, optionaler Preis; kein garantierter Namen-/Adress-Recall | EU-Endpunkt + `mip_opt_out=true`; Metadatenlogs separat | Nova-3 multi 0,0058; Flux multi 0,0078 USD/Audiomin.; Promo-/Tarifprüfung | Dialekte, Zahlen, names, false/early EOT, speculative LLM-Aufrufe |
| OpenAI Live Transcribe | inkrementelle Deltas; Beispiel 24-kHz-PCM; beim geprüften Live-Modell Client-Commit statt server/semantic VAD | Prompt/keywords/languages; bestimmte Zeit-/Confidence-/Speaker-Metadaten fehlen | endpoint-/modellabhängig, ZDR/MAM-/Retentionmatrix | gpt-live-transcribe 0,017; gpt-transcribe 0,0045 USD/min, letzteres nicht gleich Live | 8-kHz-Resampling, Endpointing, committed vs live API |
| Google Chirp 3 STT V2 | de-DE GA, StreamingRecognize; Sessions laut Doku maximal 5 min | Speech Adaptation; Telefonbandbreite praktisch prüfen | dokumentierte EU-Multiregion; Feature-/Regionkombination prüfen | Standard V2 0,016 USD/min bis 500k, höhere Stufen dokumentiert | Sessionwechsel ohne Wortverlust, Dialekte/entities |
| Azure Speech | de-DE, Streaming, Speech-/Endpointing-/Custom-Funktionen | Vocabulary/Customization plan-/modellabhängig | Speechregion, Azure OpenAI regional/global/DataZone getrennt | US-Preisbeispiel 1 USD/Audiostunde; EU-Tarif nicht daraus ableiten | de-DE-Modell/Region/Telephony, Namen/Zahlen |
| Speechmatics | deutsche Realtime-WebSocket-STT, Custom Dictionary | Entity-/Dialektqualität nicht unabhängig verifiziert | EU-WebSocket, On-prem Enterprise; Gesamtpfad offen | Modelle 0,30–0,80 USD/h je konkretem Modell; siehe Dossier | Melia/Enhanced usw. auf identischem deutschen Telefonmaterial |
| Soniox stt-rt-v5 | deutsche Streaming-STT, konfigurierbares Endpointing/Context | Kontext; aggressive Endpoints können Accuracy verschlechtern | EU-Projekt/-Key/-Endpoint; System-/Usagedaten können außerhalb bleiben | 2 USD/Mio Audioinputtokens + Texttokens; Anbieterapprox. 0,12 USD/h | echte Tokenrate, Finalisierung/Entities/Quotas |
| Mistral Voxtral Realtime Transcribe 3 | Voice-/Realtime-API dokumentiert; Guide-/Modell-ID-Konflikt prüfen | sprach-/modellabhängig; Deutsch-Telefonqualität nicht gemessen | französischer Anbieter/DPA kein EU-only-Nachweis | 0,008 USD/Audiomin.; Version/API prüfen | Modellverfügbarkeit, 8-kHz-/EOT-Fit, kommerzielle Gewichte |

Quellen: [deepgram.models](https://developers.deepgram.com/docs/models-languages-overview) [deepgram.flux](https://developers.deepgram.com/docs/flux/quickstart) [deepgram.pricing](https://deepgram.com/pricing) [deepgram.data](https://developers.deepgram.com/trust-security/your-data) [openai-07](https://platform.openai.com/docs/guides/realtime-transcription) [openai-08](https://developers.openai.com/api/docs/pricing); übrige vollständige Quellen-/Preisdossiers: [Google](../research/google.md), [Azure](../research/azure.md), [Speechmatics](../research/speechmatics.md), [Soniox](../research/soniox.md), [Mistral](../research/mistral.md).

**Keine Anbieter-Rangfolge für deutsche Erkennung.** WER allein übersieht geschäftskritische Entitäten. Namen, Straßen, Datums-/Uhrzeitangaben, Telefonnummern, Geldbeträge, Kennzeichen und VIN brauchen separate Accuracy-, Rückfrage- und Bestätigungsmetriken. Ein vorgegebenes Vocabulary kann nützen, darf aber nicht andere Namen systematisch verfälschen. STT-Teilresultate sind kein autoritatives Kalender-/CRM-Update.

## 3. Text-to-Speech für deutsche Verkaufsgespräche

| Kandidat | Dokumentierte Funktionen | Aussprache/Emotion/Cloning | Region / Preisbasis | Kernrisiko |
|---|---|---|---|---|
| ElevenLabs | Deutsch, verschiedene Modelle, Streaming, Voice Library | Cloning/Design; Normalisierung/Aussprache prüfen | API z.B. v3/multilingual_v2 0,08 USD/1.000 Zeichen; Flash/Turbo 0,04; EU Enterprise | nicht jede Modellversion am gleichen WebSocket-Endpoint; v3/v4 dort laut Doku nicht unterstützt |
| Cartesia Sonic 3.6 | GA, Deutsch in 44 Sprachen, low-latency/streaming APIs | Dictionaries, Cloning; speed/emotion/volume teils beta | Scale 299 USD/8M Credits, Overage 38 USD/M Credits; EU-Pfad offen | Credits vs Zeichen korrekt; TTS-Concurrency nicht Agents-Concurrency |
| OpenAI | GPT-4o-mini-TTS, Streaming/Voices/Instructions | custom voice genehmigungs-/consentgebunden; Stimmen laut Guide englischoptimiert | Audiooutput 12 USD/M Tokens + Textinput; Legacy Zeichenpreise | angekündigte Abschaltung geprüfter TTS-Modelle am 06.01.2027; Realtime-Migration keine Drop-in-Speech-API |
| Azure Neural | de-DE-Stimmen, Streaming, Styles/SSML je Stimme | Pronunciation, Neural/HD/Custom Voice mit Bedingungen | US-Beispiel 15 USD/M Zeichen; EU-Preis/Verfügbarkeit separat | Stimme/Style/Region nicht pauschal verfügbar; Qualität ungetestet |
| Google Chirp 3 HD | de-DE, Streaming, EU dokumentiert | Features je Stimme/Endpoint prüfen | 30 USD/M Zeichen nach Freikontingent | Live-Dialog-/Telefon-TTFB, Zahlen/Namen und gewünschte Steuerbarkeit testen |
| Mistral TTS 3, zusätzlicher Kandidat | Modellkatalog/API dokumentiert | deutsche Eignung/Cloningumfang prüfen | 13 USD/M Zeichen; Gewichte CC BY-NC 4.0 laut Katalog | kommerzielle API-/Selfhost-/Weitergaberechte getrennt freigeben |

Quellen: [el-models](https://elevenlabs.io/docs/overview/models) [el-ws](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts) [el-apiprice](https://elevenlabs.io/pricing/api) [el-residency](https://elevenlabs.io/docs/overview/administration/data-residency) [openai-05](https://platform.openai.com/docs/guides/text-to-speech); [Cartesia](../research/cartesia.md), [Azure](../research/azure.md), [Google](../research/google.md), [Mistral](../research/mistral.md).

Für natürliche deutsche Salesdialoge zuerst **ElevenLabs und Cartesia** mit identischen Texten/Telefoncodecs verblindet vergleichen, Azure/Google als regional orientierte Referenzen ergänzen. Das ist eine Shortlist aufgrund dokumentierter Produktfunktionen, **kein Hörqualitätsurteil**. Emotion, Natürlichkeit, Stabilität über längere Turns, Zahlen/Abkürzungen, Formulierungsangemessenheit und Kosten müssen separat gemessen werden. Voice Cloning ist kein notwendiges MVP-Feature und erzeugt zusätzliche Rechte-/Identitätsrisiken.

## 4. Text-LLMs und native Realtime-Modelle

| Anbieter | Dokumentierte Optionen am Abruf | Tools / Structured / Streaming | Preis-/Datenrisiko | Auswahlfrage |
|---|---|---|---|---|
| OpenAI | Textmodelle gpt-6-luna, gpt-6.1-sol; Realtime 2.1/mini; GPT-Live | Text-/Audiostreams, Function Calling/strict, native Sessions; GPT-Live Delegation | Text- und Audiotoken getrennt; EU-Aufschlag/Tracing/Deprecations | Toolerfolg und deutsche Antwortqualität vs Kosten/Latenz |
| Google | Gemini Text und Gemini 3.8 Live GA laut geprüfter Doku | Streaming, native Live/Tools; Structured Output je API | Developer API vs Vertex; Global keine Residency; EU Live-Marker nicht lesbar | Vertex-EU-Modellverfügbarkeit und Tool-/Dialogtest |
| Anthropic | Haiku/Sonnet/Opus 5.5 laut geprüfter Modellübersicht | SSE-Text, Clienttools/strict/schema; kein nativer Audiopfad belegt | Direct API global/US und US Workspace; keine EU-only Direct-Option belegt | Cloud-distributiertes EU-Angebot separat prüfen; reiner Textbaustein |
| Mistral | Ministral 3 / weitere Textmodelle; Voxtral/Voice Agents | Streaming, Function Calling/structured und Voicekonfiguration | Gewichts-/API-Lizenz, tatsächliche EU-Inferenz, Guide-/Modellversion | selfhost vs hosted TCO und deutsche Voice-/Toolvalidierung |

Quellen: [openai-04](https://platform.openai.com/docs/models) [openai-08](https://developers.openai.com/api/docs/pricing) [openai-10](https://platform.openai.com/docs/guides/your-data) [openai-13](https://platform.openai.com/docs/guides/function-calling); [Google](../research/google.md), [Claude](../research/anthropic.md), [Mistral](../research/mistral.md). Exakte Modell-IDs und Kontext-/Planbedingungen stehen in den versionierten Dossiers. Alias-IDs vor einem späteren Benchmark erneut einfrieren.

LLM-„Reasoning“ kann Tokenverbrauch und Wartezeit erhöhen; kurze Voice-Turns benötigen nicht automatisch das größte Modell. Structured Outputs verbessern Syntax/Schema, nicht Wahrheit, Berechtigung oder fachliche Korrektheit. Repeated system/context/tool tokens, speculative Antworten, Caching und Contextwachstum sind im Kostenmodell ausdrücklich zu berücksichtigen. Deutsche Halluzinations-, Gesprächs- und Tool-Fehlerraten sind **NICHT VERIFIZIERT**.

## 5. Kaskade, native S2S und Hybrid

| Architekturtyp | Geeignete Prüf-Use-Cases | Vorteile als Hypothese | Grenzen / Kontrolle |
|---|---|---|---|
| STT → Text-LLM → TTS | Qualifizierung, Zahlen/Namen, Termin-/CRM-Aktionen | sichtbarer Zwischen-Text, separate Provider/Evals, gezielte Aussprache | mehrere Netzwerk-/Buffer-/Endpoint-Stellen; Transcript nicht automatisch richtig |
| Native Speech-to-Speech | natürlicher Dialog, Prosodie, häufige Unterbrechung | weniger explizite Pipelinegrenzen, Audioinformation bleibt im Modell | höhere Session-/Audiotokenbindung, Auditing und genaue Entitäten testen |
| Hybrid / delegierte Voice | natürliche Oberfläche + kontrollierte fachliche Backendentscheidungen | trennt Audiointeraktion und Business Authority | zusätzliche Roundtrips, klare Bestätigung/Timeoutpolitik erforderlich |

Eine native Session kann trotzdem Tools verwenden und auditierbar gemacht werden; eine Kaskade kann trotzdem halluzinieren und zu langsam sein. Keine Architektur ist ohne konkrete Messung generell überlegen. Parallelisierung/Streaming senken nicht automatisch p95, wenn Endpointing zu früh oder Toolantworten zu spät kommen.

## 6. Vergleichs- und Betriebsplan

Den gemessenen Pfad bei **letzter Nutzersprache → erste hörbare Agentantwort** definieren; Provider-TTFB, End-of-Turn, Text-TTFT, TTSstart und Carrierpuffer separat instrumentieren. Pro Turn und Call Modell-/Agentrelease, Carrierroute, Codec, Region, Toolereignisse, Fehlerraten und abgerechnete Einheiten festhalten. Sinnvolle erste Vergleichsmatrix: zwei Runtimes × zwei Speechkonfigurationen; danach native S2S gegen die beste kontrollierte Kaskade, nicht alle Kombinationsmöglichkeiten gleichzeitig.

PSTN-/Carrierqualität, 8-kHz-Signale, Dialekte, Denkpausen, Backchannels, Barge-in, No-answer/Voicemail, Warmtransfer, fehlerhafte Toolantworten, Last und Deploydrain sind Pflichtfälle. Recording-/Testdaten dürfen nur auf freigegebener Grundlage verarbeitet werden. Die detaillierte Messmethodik und vorgeschlagene Freigabegrenzen stehen in Bericht 12.

**Was die Empfehlung umkehrt:** deutlich besseres End-to-End-Ergebnis eines Kandidaten, nicht verfügbare EU-Modelle, fehlende Carrierkompatibilität, restriktive Modelllizenzen, untragbare Betriebskomplexität oder Änderungen der aktuellen Modell-/Preislage. Benchmark und vertragliche Prüfung bleiben zwingend.
