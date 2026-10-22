# 07 – Build vs Buy Analysis

**Stand: 21.10.2026.** **Fazit:** Produktdomänen und fachliche Autorität kontrollieren; STT/TTS/LLM/PSTN einkaufen; Runtime, Integrationen, Wissen und Billing hybrid nutzen. Die Plattform soll kein dünner Wrapper um einen einzigen Voice-SaaS sein.

**Confidence:** mittel bis hoch für Verantwortungsgrenzen, mittel für Aufwand. Die Matrix ist eine **bedingte strategische Empfehlung**, keine Architektur- oder Implementierungsfreigabe. Teamkapazität, Verträge und Kundenprioritäten sind offen.

## 1. Vollständige Entscheidungsmatrix

| Komponente | Kategorie | Selbst kontrollierter Anteil / Begründung | Eingekaufter Anteil | Risiko / Exit |
|---|---|---|---|---|
| SaaS Dashboard | BUILD | eigene Agency-/Client-Journey, Rechte, Kosten/Fehlerstatus | UI/Auth-Standardbausteine | keine fremde UI kopieren, eigene API/Exporte |
| Agent Builder | BUILD | eigene Identity/Policies/Releases/Tests/Publishing | Modell-/Voicekatalogadapter | kein fremdes Configformat als Produktdomäne |
| Workflow Builder | HYBRID | Fachaktionen und Fehlersemantik | Grapheditor/OEM optional | Editor ist keine Engine; exportierbarer Graph |
| Campaign Engine | BUILD | Consent/Schedule/Attempt/Sperre/Budget/Quoten | Durable/Queue/Carrier | Calltimeout nicht blind wiederholen |
| Lead Management | BUILD | Kontaktidentität, Herkunft, Consent/Zustand | Import-/CRM-Connector | eigene Ownership, CRM-ID nur Zuordnung |
| Multi-Tenant | BUILD | API/Runtime/Jobs/RAG/Secrets/Medienautorität | DB/KMS/Authfunktionen | Workspace ≠ Isolation; Negativtests |
| Analytics | HYBRID | eigene Outcome-/Client-/Kostendefinition | OTel/Tracing/BI | PII/Regionspfad und falsche Erfolgslabels |
| Billing | HYBRID | Usage-Ledger/Tarifversion/Reconciliation | Invoice/Paymentinfrastruktur | Aggregate nicht autoritativ; Rohdatenexport |
| Voice Runtime | HYBRID | Session-Lifecycle, Release, sichere Tools/Fallback | LiveKit/Pipecat/Managedcompute | Transport-/Cloud-/Modelle getrennt; Wechseltests |
| STT | BUY | Transcript-/Entityschema/Vocabulary/QAmessung | Streaming API | EOT/Sprache/Region/Preis; zweiter geprüfter Kandidat |
| TTS | BUY | Auswahl/Aussprache/Buffer/Abbruchpolitik | Speech API/Stimmen | Voiceidentität/Cloningrechte nicht portable |
| LLM | BUY | Prompts/Policies/validierte Actions | Text/native Audio API | Strict Schema ≠ Recht/Wahrheit; Deprecations |
| Telephony | BUY | Ziel-/Call-/Transferpolicy/Budget/Adapter | SIP/PSTN/KYC/Nummern | Route/Resale/Automation/Porting vertraglich |
| Knowledge Base | HYBRID | ACL/Ownership/Version/Provenienz/Retention | Parser/Embedding/Vector/Storage | Retrievalfilter ≠ Auth; Neuindexierung/export |
| Conversation Analytics | HYBRID | Outcome-/Qualification-Schema/kalibrierte Evals | LLMextraktion/Telemetry | Sentiment vs Emotion; human audit |
| Integrations | HYBRID | Credentialscope/Toolcontracts/Idempotenz/Status | SDK/n8n-OEM optional | Lizenz/APIänderung/duplikate events |
| Scheduling | HYBRID | Zeitfenster/DST/Consent-Recheck/Cancel | Durable Timer/Queues | widerrufener Job darf nicht starten |
| Recording Infrastructure | HYBRID | Consent/Zweck/Zugriff/Löschung/Tenant | Carrier/Runtimecapture/Objectstore | Defaultaufnahme/Legs/Retention/Regionspfad |

## 2. Strategische Kontrolle statt kompletter Eigenbau

Die eigenen Assets sind die überprüfbaren Domain Contracts: veröffentlichte Agentreleases, Mandantenzugriff, fachlich begrenzte Tools, Einwilligungs-/Sperrnachweise, eindeutige Callaufträge, Ergebnis-/Kostenledger und reproduzierbare Regressionstests. Wenn diese allein im proprietären Agentenformat eines Anbieters liegen, wird ein Providerwechsel zu einer Produktmigration.

Austauschbarkeit verlangt trotzdem keine universelle Abstraktion aller Fähigkeiten. Stimmen, Turnevents, native Sessionzustände und SIP/API-Funktionen sind unterschiedlich. Ein minimales eigenes Fachmodell plus ausdrücklich ausgewiesene Capabilities ist realistischer als „jeder Provider passt ohne Anpassung“. [livekit.docs.pipelines](https://docs.livekit.io/agents/models/pipelines/) [pipecat-P04](https://docs.pipecat.ai/pipecat/learn/transports)

**LLM ≠ Business Authority:** Termin, CRM, Transfer und Nachricht brauchen Backendrechte, Schema-/Policyprüfung und Idempotenz. BUY bei Voice oder LLM ändert diese Verantwortung nicht. Outbox und externe Statusklärung gehören zum eigenen Fachmodell. [openai-13](https://platform.openai.com/docs/guides/function-calling) [tenancy-6](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) [tenancy-8](https://docs.stripe.com/api/idempotent_requests)

## 3. Einkaufs- und Lizenzgates

Vor Beschaffung: kommerzielle SaaS-Nutzung/OEM/WhiteLabel/Reselling, Daten-/Konfigurationsexport, Nummernportierung, AVV/Region/Subprozessoren, Quoten/SLA/Supportzugriff, Kündigung und Preismetering. n8n ist source-available mit kommerziellen Einbettungsgrenzen; Restate BSL erlaubt nicht automatisch einen öffentlichen Restate-API-Plattformdienst. Beide müssen am konkreten Produktmodell geprüft werden. [n8n-Dossier](../research/n8n.md) [restate.license](https://raw.githubusercontent.com/restatedev/restate/main/LICENSE)

Frameworklizenz und Modelllizenz unterscheiden: LiveKit Apache2.0 vs separate Turn-Model-License; bei Mistral TTS3 sind kommerzielle APIrechte und CC-BY-NC-Gewichte getrennt zu klären. [livekit.license](https://github.com/livekit/agents/blob/main/LICENSE) [livekit.modellicense](https://github.com/livekit/agents/blob/main/MODEL_LICENSE) [Mistral](../research/mistral.md)

## 4. Wirtschaftlichkeit, Migration und Betriebsaufwand

BUY spart Modell-/Carrierentwicklung, nicht Security-, Integrations-, Support- und QAarbeit. HYBRID spart Infrastrukturcode, erzeugt aber Upgrade-/API-/Gebührenkopplung. BUILD erhöht Kontrolle und Betriebs-/Testverantwortung. Selfhost ist nicht kostenlos; Cloudpreise sind kein vollständiges Produkt-TCO. Bericht08 trennt variable Gebühren, Minima und offene HA/Personal-/Vertragskosten.

Exit braucht Config-/Knowledge-/Transcript-/Meteringexport, Provider-ID-Zuordnung, Stimm-/Modellalternativen, Nummern-/Consent-/Credentialmigration und eine gleichbleibende PSTN-Testsuite. Workflowenginewechsel ist besonders teuer, wenn laufende Timer/Historyzustände migrieren müssen. Damit sind Exitkosten nicht einfach „Adapter austauschen“.

## 5. Bedingte Priorität

Zuerst Use Case, Rechtsgrundlage, Tenant-/Toolautorität und Qualitätsmaßstab. Danach Runtime/Engine anhand Betriebsfähigkeit und Tests. Ein belastbarer OEM-Vertrag kann für einen engen Pilot mehr BUY sinnvoll machen; restriktive Rechte oder hoher EU-Mindestumsatz verschieben zu HYBRID. Wenige kurze Asyncjobs können BullMQ statt Temporal rechtfertigen. Keine endgültige Wahl vor dem Decision Gate.
