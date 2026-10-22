# 11 – Recommended Technology Shortlist

**Stand: 21.10.2026.** **Fazit:** Die Arbeitshypothesen sind größtenteils plausible Kandidaten, aber nicht beschlossen. Primary Candidate bedeutet **zuerst zu validierende Option**, nicht genehmigte Technologie. Benchmark, Vertrags-/Lizenzprüfung und menschliches Decision Gate bleiben zwingend.

**Confidence:** mittel für die Shortlist; niedrig für beste Qualität/Vollkosten ohne Test. Anforderungen an Team, Budget, SLO, Peak/Clients und Datenklassen sind noch offen.

## 1. Kern-Shortlist

| Entscheidung | Primary Candidate | Alternative Candidate | Why / Vorteile | Risks / Nachteile / Betrieb | Open Questions / Wechselbedingung |
|---|---|---|---|---|---|
| Voice Runtime | LiveKit Agents im SIP-/Sessionbenchmark | Pipecat; Bolna/Vocode nachrangig | integrierte Rooms/Jobs/SIP, Python/Node; Pipecat modulare Python-Transporte | Cloud-/Media-/Model-Lock-in vs Pipeline-/Transportbetrieb | p95/Entities/Drain/Carrierkompatibilität, Teamfit; offen |
| Voice-Architektur | Kaskade als überprüfbare Baseline | native S2S, delegierter Hybrid | Zwischen-Text/Providerwechsel/Entity-Evals | mehr Streamingstellen vs weniger transparente native Session | gleicher PSTN-/Toolbenchmark; nicht vorab entscheiden |
| STT | Deepgram Nova-3/Flux multilingual paarweise | Speechmatics, Soniox; Azure/Google/OpenAI/Mistral ergänzend | Deutsch/Streaming/Flux-EOT und EU-Kontrollen dokumentiert | MIP-Opt-out/Quoten/Promopreise; Anbieterqualität ungemessen | kritische Entities/Dialekte/8kHz/EOT und vertraglicher EU-Pfad |
| TTS | ElevenLabs streamingfähiges Modell | Cartesia Sonic; Azure/Google als regionale Referenzen | Stimmen/Deutsch/Streaming-/Aussprachefunktionen | Modell-/Endpointparität, EU-Enterprise/Cloningrechte | Blindtest/Zahlen/Aussprache/Longturn/TTFB/Concurrency |
| Text-LLM | schneller und stärkerer OpenAI-Textkandidat | Gemini Vertex, Mistral; Claude via geprüftem Datenpfad | Tools/strict/Streaming/preislich differenzierbar | Modelle/Regionen ändern; reasoning/contextcost | deutsche Task-/Toolqualität vs TTFT; Direct-Claude EU offen |
| Native Voice | OpenAI Realtime/GPT-Live | Gemini Live; Mistral Voice Agents | dokumentierte native Audio-/Toolpfade | Audio-/Sessionlockin, Tracing/Region, preisliche Einheiten | EU-Modell/Endpoint, S2S-/Kaskadenkosten und Confirmations |
| Carrier | Twilio + Telnyx parallel prüfen | sipgate/easybell; Placetel/Telekom bei passendem SIP-/PBX-Vertrag | CPaaS/API/Media vs lokale SIPbasis | DE-Mobilrouten/OEM/Automation/KYC, evtl SBC | konkrete Ratedecks/Porting/Callroute/Resale, offener Preisgate |
| Durable Workflow | Temporal | BullMQ+fachlicher State; Restate | lange Timer/Recovery/Versioning | History/replay/ops vs viel Eigenzustand; Restate BSL | echte Prozessdauer/Cancelvolumen/teamops/TCO |
| External Automation | n8n nach Lizenzfreigabe | direkte Connectoren/Webhookadapter | viele Backgroundintegrationen | SaaS-Embedding-/OEM-Kosten, credentials/executionPII | konkretes Lizenzmodell/Kundenzugang/EUdaten; nicht realtime |
| Hosting | Managed EU-Angebot gegen eigenen EU-Betrieb testen | OVH/AWS vs Hetzner selbstbetrieben | Betriebsentlastung vs Kosten-/Datenkontrolle | Multi-AZ/egress/UDP-LB/On-call/Subprocessorpfade | SLO/RTO/RPO/Peak und vollständiges Angebot; offen |

Belege: [livekit.docs.agents](https://docs.livekit.io/agents/) [livekit.eu](https://docs.livekit.io/deploy/admin/regions/data-residency/) [pipecat-P04](https://docs.pipecat.ai/pipecat/learn/transports) [pipecat-P05](https://docs.pipecat.ai/client/js/introduction) [deepgram.models](https://developers.deepgram.com/docs/models-languages-overview) [deepgram.data](https://developers.deepgram.com/trust-security/your-data) [el-models](https://elevenlabs.io/docs/overview/models) [el-ws](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts) [openai-09](https://platform.openai.com/docs/guides/voice-agents) [openai-10](https://platform.openai.com/docs/guides/your-data); die plan-/modellgenauen Dossiers liegen bei [04](04_Voice_Technology_Audit.md), [05](05_Telephony_Infrastructure_Audit.md), [06](06_SaaS_Architecture_Research.md).

## 2. SaaS-/Daten-/QA-Kandidaten

| Bereich | Primary / Alternative | Begründung | Risiken / offene Fragen |
|---|---|---|---|
| Frontend | Next.js/React/TypeScript als Projektarbeitshypothese; einfachere React-App möglich | Agent-/Agency-UI, Editor-/Testoberfläche | SSR/SEO ist für interne App kein Selbstzweck; tatsächliche Team-/Produktanforderung offen |
| UI / Floweditor | Tailwind/shadcn/React Flow als Hypothese | Standardkomponenten und Graphdarstellung | Editor löst keine Execution-/Securitysemantik; konkrete Paket-/Versionslizenzen noch prüfen |
| Control Plane | NestJS/TypeScript-Kandidat; einfacherer TS-Backendrahmen alternativ | Modularität/Validierung/Tools/Connectoren | nicht in Microservices zerlegen ohne Skalierungs-/Teamgrund; Stackreview noch ausstehend |
| Voice Worker | Python; LiveKit Node alternative | Pipecat Python, Speech-/Runtimeintegration | separate Deploy-/On-callkompetenz und konkrete Pluginparität |
| Transaktionale Daten | PostgreSQL; Shared+RLS zunächst gegen DB-per-tenant prüfen | Beziehungen/Integrity/Ledger; mehrere Isolationsstufen möglich | RLS-BYPASS/owner/pooling/tenant FKs; Enterprise Restore/Isolation |
| Vector/RAG | pgvector zunächst; Qdrant bei nachgewiesenem Bedarf | SQL-Ownership und geringe zusätzliche Ops | ANN Tenantrecall; große Workloads/Indexmemory prüfen |
| Knowledge Ingestion | minimale eigene Pipeline; LlamaIndex optional | wenig Abstraktions-/Providerbindung | komplexe Parser/LlamaCloud/PII/licence/dependencies |
| Cache/Jobs | Redis bei konkretem Bedarf; Valkey/Alternativen separat prüfen | Limits/Cache/BullMQ | aktuelle Redis-Version-/Lizenz-/Kompatibilität nicht hier finalisiert; nie Geschäftswahrheit |
| Medienstorage | S3-kompatibler EU-Store; Carrierstorage nur bewusst | exportierbare Objekte/Retention | signedURL/tenantACL/egress/backups/Restores |
| Tracing | OpenTelemetry; Langfuse zusätzlich für LLM-Evals | standardisierte Call-/Toolkorrelation | Backend und PII/Sampling/Tenant/Region getrennt, fail-open |
| QA | eigener PSTN-/Business-Harness + promptfoo/Runtime-Evals | Textredteam ergänzend, reale Audio-/Toolfälle entscheidend | promptfoo allein kein Voicebenchmark, configs nicht sandboxed |

Die Frontend-/Backendpakete wurden **nicht einzeln als Produktionsstack auditiert**. Ihre Nennung übernimmt die Projektarbeitshypothese unter Anforderungenvorbehalt. Es wird keine bestätigte Lizenz-/Versions-/Securityfreigabe für ungeprüfte Packages behauptet. PostgreSQL/pgvector-/QA- und Observabilitygrenzen sind dagegen in [06](06_SaaS_Architecture_Research.md) recherchiert. [tenancy-1](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) [tenancy-4](https://github.com/pgvector/pgvector)

## 3. Exit-Verträge und Migrationskosten

Jede Wahl braucht ein eigenes, exportierbares Fachmodell und einen klaren Adaptervertrag. STTwechsel betrifft EOT/partials/vocabulary; TTSwechsel Aussprache/Voice/Buffer; LLMwechsel Prompt/Schema/Toolablauf; Carrierwechsel Callstatus/KYC/Porting/Transfer; Runtimewechsel Sessionstate/Worker/media; Enginewechsel laufende Timer/History; DB-/Storagewechsel Tenantrestore/Schlüssel/Retention.

Migration ist nicht generell billig. Langlaufende Workflows und Nummernrechte sind besonders schwer spontan zu ändern. Für jede Primaryoption muss ein zweiter praktisch kompatibler Kandidat oder bewusster, akzeptierter Lock-in dokumentiert werden. Nicht alle Providerfähigkeiten sollen in den kleinsten gemeinsamen Nenner gepresst werden.

## 4. Betriebs- und Kostenprüfung

Öffentliche Basistarife legen keine EU-/Enterprise- oder Lastfähigkeit fest. Typische Zusatzkosten sind SIP-/Media-/Sessionfees, reservierte Worker/Coldstartvermeidung, Events/Traces, Recordingretention, Egress, DB/Backup/KMS, support und Personalbetrieb. Bericht08 ist eine Preis-/Verbrauchsplanung, kein finales Angebot.

Selbsthosting eines Frameworks reduziert Cloudfees, nicht SRE-/HApflichten. Managedbetrieb reduziert eigene Komponenten, nicht DPA-/Outreach-/Toolverantwortung. Temporals Replaymodell kann wertvoll und für wenige Jobs zu komplex sein; zusätzliche Qdrant/Langfuse-Statekomponenten müssen nach messbarem Bedarf gerechtfertigt werden.

## 5. Gate und Änderungsbedingungen

Ein Legal-/EUvertrag kann die Shortlist stärker ändern als eine geringe TTFB-Differenz. Die endgültige Wahl verlangt die in12 definierten Tests und bestätigte Team-/Last-/Preisanforderungen. ChatGPT reviewt diese Kandidaten; der Mensch entscheidet; Claude Code implementiert danach. Keine der acht ausdrücklich offenen Kernentscheidungen wird hier geschlossen.
