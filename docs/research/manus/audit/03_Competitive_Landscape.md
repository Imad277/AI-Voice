# 03 – Competitive Landscape

**Quellenabruf: 21.10.2026.** Elf Anbieter, 40 Merkmale, 440 Zellen. **Fazit:** Kein Anbieter ist in der gelesenen öffentlichen Evidenz lückenlos für deutsche PSTN-Qualität, Agency-Rechte, technische Tenant-Isolation, vollständigen EU-Datenpfad und transparente Vollkosten belegt. Das ist eine Evidenzlücke, kein Nachweis, dass kein Anbieter diese Anforderungen erfüllen kann.

**Confidence:** mittel bis hoch für dokumentierte Funktionen, mittel für veröffentlichte Preise, niedrig für Qualitätsrangfolgen und nicht öffentliche Vertragsdetails. Kein Account-/Call-/Funktionsbenchmark wurde durchgeführt.

## 1. Anbieterlandschaft

| Anbieter | Primäres Segment | Öffentlicher Nutzen | Preisstand, Originalwährung und nicht all-in | Kernlücke / Lock-in |
|---|---|---|---|---|
| Team Follow Up AI | Agency / Lead Automation | GHL-Call–Qualify–Book, Handoff, Persona-/Flow-Claims | 97 USD/Monat nach 14 Tagen; Minuten/Overage offen | Signup-Widerspruch; Resale/API/Limits/EU unklar |
| Retell AI | Infrastructure / SaaS | SIP, Batch, Webhooks, Agentenbetrieb/Analytics/Tests | 0,07–0,31 USD/min nach Komponenten; Zusatzfees/Burst | EU-Pfad, Agency/OEM und Isolation nicht vollständig belegt |
| Vapi | Infrastructure | modulare Speech-/LLM-/Transportanbieter, BYOK, Tools/Workflows | 0,05 USD/Hostingmin plus Provider; Core29 USD/Monat; Pro-Servicegebühr mind.999 USD/Monat | EU nur Premier mit offenem Preis; proprietäre Runtime-Orchestrierung |
| Bland AI | SaaS / Infrastructure | Pathways/Draft/Staging/Production, Batch, API/Logs | Start0,14 USD/min; Build299 USD/Monat+0,12 USD/min | Billing-Doku nennt zusätzlich Scale; Preise/Limits konfliktbehaftet |
| Synthflow | SaaS / Agency | No-Code, SIP, Campaigns, Subaccounts/Branding | Enterprise ab30.000 USD/Jahr; aktuelle PAYG-Rate nicht verifiziert | EU-Cluster mit Drittanbietergrenzen, planabhängige Kampagnen |
| ElevenLabs Agents | SaaS / Speech Infrastructure | Flows, RAG, Tools, SIP, Batch, Tests und TTS | Pläne/Kontingente; zusätzliche Minuten0,08 USD/min, LLM/Telefonie separat | EU Enterprise, Batch/ZRM-Ausnahme, Recordingdefault |
| Cognigy | Enterprise | Voice Gateway/SIP, Flows, API und On-prem-Dokumentation | individuelles Angebot, keine Zahl verifiziert | OEM-/Agency-/EU-Gesamtvertrag offen |
| PolyAI | Enterprise | Studio/ADK, SIP-Handoff, APIs, kontrolliert aktiviertes Outbound | verbundene Zeit sekundengenau, Rate individuell | native Campaign-/Retrysuite nicht belegt; EUW-Host nicht ganzer Pfad |
| Parloa | Enterprise | AMP, Simulation/Versionsvergleich, Lens/CCaaS | Voice-Minute/Chat-Interaktion, individuelle Rate | öffentliche Featureclaims stärker als technische API-/Limitbelege |
| Voiceflow | Builder / SaaS | Flows/Knowledge/Tools, Partnertelefonie | Agency usage-based; Business Request pricing; dynamische Credits unlesbar | eigene US/CA-Nummern ohne Outbound; Partner-/EU-Pfad separat |
| Bolna | Hosted Infrastructure / OSS | API/RAG/Tools/SIP/Batch/Retry, MIT-Framework | Preferred0,06 USD/min; FAQ Plattform0,02 USD/min, Beziehung offen | Indienfokus; DE/EU/Hosted-OEM-Rechte ungeklärt |

Die Kategorien überschneiden sich und sind eine **analytische Einordnung**. Preisbereiche und Gebühren sind zum Abruf veröffentlicht, keine Angebote. Eine reine Runtimefee darf nicht mit einem inklusive Speech bepreisten SaaS verglichen werden; Hosted- und OSS-Produkte sind ebenfalls nicht identisch. Quellen und sämtliche Einschränkungen stehen in den elf [Einzelanalysen unten](#4-einzelanalysen-und-quellen).

## 2. Strategische Schlussfolgerungen

Infrastructure verkürzt Time-to-first-call, lässt aber Runtimezustand, Events, Kosten und regionale Sonderbedingungen beim Anbieter. Ein austauschbarer LLM ist noch keine austauschbare Runtime. SaaS-/Agencyprodukte liefern nützliche Client-/Builder-Journeys, können jedoch OEM-Rechte und Fachregeln einschränken. Enterpriseangebote zeigen, dass Simulation, Releases und Contact-Center-Handover bereits wettbewerbliche Kernelemente sind.

GoHighLevel ist ein sinnvoller erster Connector, aber kein universelles Produktdomänenmodell. Team Follow Up nennt öffentlich GHL als aktuellen Integrationsfokus. Kontakte, Berechtigungen, Buchungen und Ergebnisse sollten deshalb unabhängig vom CRM spezifiziert werden. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas)

**Deutsche Qualität:** Kein unabhängiger vergleichbarer deutscher PSTN-Benchmark dieser elf Anbieter wurde in den geöffneten Quellen festgestellt. Sprachlisten, Demo-Audio, Anbieter-TTFB und Testimonials messen unterschiedliche Dinge. Kein positives Qualitätsranking ableiten.

**Tenant und EU:** Workspaces/Subaccounts/Branding sind Produktfunktionen, keine unabhängige Sicherheitsgarantie. GDPR-Positionierung, EU-Endpoint und EU-Storage müssen getrennt von Inferenz, Logs, Support, Backups und Unterauftragsverarbeitern betrachtet werden. Nicht veröffentlichte Funktionen werden nicht als fehlend gewertet.

**Widersprüche:** Team Follow Ups Testangebot/Signup und Resale-AGB, Blands Pricing/Billing sowie Bolnas Plattform-/Preferred-Tarif bleiben beschaffungsrelevante Konflikte. Plan/Version/Vertrag müssen den jeweiligen Scope auflösen; Preise nicht mitteln oder still den günstigeren nehmen.

## 3. Vollständige Featurematrix

Die [CSV](Competitive_Feature_Matrix.csv) enthält jede der 440 Zellen mit Status, Detailgrenze und Quellen-IDs. Das [normalisierte JSON](Competitive_Landscape.json) enthält zusätzlich Positionierung, Preise, Stärken/Schwächen und Quellen.

**Legende:** V = VERIFIZIERT als Dokumentation/Vertrag, nicht eigener Test; M = MARKETING CLAIM; N = NICHT VERIFIZIERT; P = teilweise/bedingt dokumentiert; A = Annahme/Hypothese; X = explizit dokumentierte Einschränkung. Verlinkte Codes führen zur ersten zugrunde liegenden Quelle; alle Quellen/Pläne/Details stehen in der CSV. N ist kein Nein. Die Lesefassung teilt die Merkmale in fünf Gruppen und die elf Anbieter jeweils in zwei Tabellen.

### Merkmalsgruppe 1

| Merkmal | Team Follow Up AI | Retell AI | Vapi | Bland AI | Synthflow | ElevenLabs Agents / Conversational AI und TTS |
|---|---|---|---|---|---|---|
| Inbound Calling | [V](https://app.teamfollowup.ai/terms) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/advanced/sip) | [V](https://www.bland.ai/) | [V](https://docs.synthflow.ai/phone-numbers) | [V](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking) |
| Outbound Calling | [V](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/advanced/sip) | [V](https://docs.bland.ai/api-v1/post/calls) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking) |
| Realtime Voice | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/security-and-privacy/data-flow) | [V](https://www.bland.ai/) | [V](https://synthflow.ai/) | [V](https://elevenlabs.io/docs/eleven-agents/overview) |
| German Voice Quality | N | [N](https://www.retellai.com/) | N | [N](https://www.bland.ai/) | [N](https://synthflow.ai/) | [N](https://elevenlabs.io/docs/overview/capabilities/text-to-speech) |
| Languages | [M](https://teamfollowup.ai/diy/#personas) | [M](https://www.retellai.com/) | [V](https://vapi.ai/) | [M](https://www.bland.ai/) | [V](https://synthflow.ai/) | [V](https://elevenlabs.io/docs/overview/models) |
| Agent Builder | [M](https://teamfollowup.ai/agency-agent/) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/tools) | [V](https://www.bland.ai/pricing) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/overview) |
| Prompt Configuration | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/outbound-campaigns/quickstart) | [V](https://docs.bland.ai/tutorials/pathways) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/overview) |
| Visual Flow Builder | [M](https://teamfollowup.ai/agency-agent/) | [V](https://docs.retellai.com/) | N | [V](https://docs.bland.ai/tutorials/pathways) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/customization/agent-workflows) |

| Merkmal | Cognigy | PolyAI | Parloa | Voiceflow | Bolna |
|---|---|---|---|---|---|
| Inbound Calling | [V](https://www.cognigy.com/platform/cognigy-voice-gateway) | [V](https://docs.poly.ai/platform/introduction) | [M](https://www.parloa.com/platform/conversation-infrastructure/) | [V](https://www.voiceflow.com/docs/documentation/deploy/phone/connect-a-phone-number) | [V](https://www.bolna.ai/docs/frequently-asked-questions) |
| Outbound Calling | [V](https://docs.cognigy.com/voice-gateway/creating-outbound-calls) | [V](https://docs.poly.ai/voice-channel/numbers/outbound-calling) | [M](https://www.parloa.com/platform/integrations/) | [V](https://www.voiceflow.com/docs/documentation/deploy/phone/outbound-calling) | [V](https://www.bolna.ai/docs/api-reference/introduction) |
| Realtime Voice | [V](https://docs.cognigy.com/voice-gateway/technical-capabilities) | [V](https://poly.ai/) | [M](https://www.parloa.com/platform/conversation-infrastructure/) | [V](https://www.voiceflow.com/docs/documentation/introduction) | [V](https://github.com/bolna-ai/bolna) |
| German Voice Quality | [N](https://www.cognigy.com/platform/cognigy-voice-gateway) | [N](https://poly.ai/languages) | [N](https://www.parloa.com/platform/conversation-infrastructure/) | [N](https://www.voiceflow.com/docs/documentation/introduction) | [N](https://www.bolna.ai/docs/customizations/multilingual-languages-support) |
| Languages | [M](https://www.cognigy.com/platform/cognigy-voice-gateway) | [V](https://poly.ai/languages) | [M](https://www.parloa.com/platform/) | [M](https://www.voiceflow.com/) | [V](https://www.bolna.ai/docs/customizations/multilingual-languages-support) |
| Agent Builder | [V](https://docs.cognigy.com/ai/overview) | [V](https://docs.poly.ai/get-started/quickstart) | [M](https://www.parloa.com/platform/agent-builder/) | [V](https://www.voiceflow.com/docs/documentation/introduction) | [V](https://www.bolna.ai/) |
| Prompt Configuration | [V](https://docs.cognigy.com/ai/agents/deploy/endpoint-reference/voice-gateway) | [V](https://docs.poly.ai/flows/introduction) | [M](https://www.parloa.com/platform/agent-builder/) | [V](https://www.voiceflow.com/docs/courses/phone-agent-quick-start) | [V](https://www.bolna.ai/docs/api-reference/agent/v2/overview) |
| Visual Flow Builder | [V](https://www.cognigy.com/platform/cognigy-voice-gateway) | [V](https://docs.poly.ai/flows/introduction) | [N](https://www.parloa.com/platform/agent-builder/) | [V](https://www.voiceflow.com/docs/documentation/introduction) | [V](https://www.bolna.ai/) |

### Merkmalsgruppe 2

| Merkmal | Team Follow Up AI | Retell AI | Vapi | Bland AI | Synthflow | ElevenLabs Agents / Conversational AI und TTS |
|---|---|---|---|---|---|---|
| Knowledge Base | N | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/knowledge-base) | [V](https://docs.bland.ai/tutorials/pathways) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/overview) |
| RAG | N | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/knowledge-base) | [N](https://docs.bland.ai/tutorials/pathways) | [N](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/overview) |
| Tool Calling | N | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/tools) | [V](https://docs.bland.ai/tutorials/webhooks) | [V](https://docs.synthflow.ai/actions-overview) | [V](https://elevenlabs.io/docs/eleven-agents/customization/tools) |
| Custom Functions | N | [V](https://www.retellai.com/) | [V](https://docs.vapi.ai/tools) | [V](https://docs.bland.ai/tutorials/webhooks) | [V](https://docs.synthflow.ai/actions-overview) | [V](https://elevenlabs.io/docs/eleven-agents/customization/tools) |
| API | N | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/security-and-privacy/eu-region) | [V](https://docs.bland.ai/api-v1/post/calls) | [V](https://docs.synthflow.ai/getting-started-with-your-api) | [V](https://elevenlabs.io/docs/eleven-agents/overview) |
| Webhooks | N | [V](https://docs.retellai.com/features/webhook-overview) | [V](https://docs.vapi.ai/tools) | [V](https://docs.bland.ai/tutorials/webhooks) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks) |
| SIP | [N](https://app.teamfollowup.ai/terms) | [V](https://docs.retellai.com/deploy/custom-telephony) | [V](https://docs.vapi.ai/advanced/sip) | [V](https://docs.bland.ai/platform/billing) | [V](https://docs.synthflow.ai/phone-numbers) | [V](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking) |
| Telefonnummern | [V](https://app.teamfollowup.ai/terms) | [V](https://docs.retellai.com/) | [V](https://vapi.ai/pricing) | [V](https://www.bland.ai/pricing) | [V](https://docs.synthflow.ai/phone-numbers) | [V](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking) |

| Merkmal | Cognigy | PolyAI | Parloa | Voiceflow | Bolna |
|---|---|---|---|---|---|
| Knowledge Base | [V](https://docs.cognigy.com/ai/overview) | [V](https://docs.poly.ai/get-started/quickstart) | [M](https://www.parloa.com/platform/integrations/) | [V](https://www.voiceflow.com/docs/courses/phone-agent-quick-start) | [V](https://www.bolna.ai/docs/getting-started/knowledge-base) |
| RAG | [N](https://docs.cognigy.com/ai/overview) | [V](https://docs.poly.ai/get-started/quickstart) | [N](https://www.parloa.com/platform/integrations/) | [V](https://www.voiceflow.com/docs/documentation/build/querying-the-knowledge-base) | [V](https://www.bolna.ai/docs/getting-started/knowledge-base) |
| Tool Calling | [V](https://docs.cognigy.com/ai/agents/deploy/endpoint-reference/voice-gateway) | [V](https://docs.poly.ai/integrations/introduction) | [M](https://www.parloa.com/platform/agent-builder/) | [V](https://www.voiceflow.com/docs/documentation/build/tools/api-tool) | [V](https://www.bolna.ai/docs/tool-calling/introduction) |
| Custom Functions | [V](https://docs.cognigy.com/voice-gateway/creating-outbound-calls) | [V](https://docs.poly.ai/flows/introduction) | [N](https://www.parloa.com/platform/integrations/) | [V](https://www.voiceflow.com/docs/documentation/introduction) | [V](https://www.bolna.ai/docs/tool-calling/introduction) |
| API | [V](https://docs.cognigy.com/ai/for-developers/developers/api-and-cli) | [V](https://docs.poly.ai/api-reference/introduction; https://docs.poly.ai/api-reference/conversations/introduction; https://docs.poly.ai/api-reference/webhooks/introduction) | [M](https://www.parloa.com/platform/integrations/) | [V](https://www.voiceflow.com/docs/api-reference/api-overview) | [V](https://www.bolna.ai/docs/api-reference/introduction) |
| Webhooks | [V](https://docs.cognigy.com/voice-gateway/creating-outbound-calls) | [V](https://docs.poly.ai/api-reference/introduction; https://docs.poly.ai/api-reference/conversations/introduction; https://docs.poly.ai/api-reference/webhooks/introduction) | [N](https://www.parloa.com/platform/integrations/) | [V](https://www.voiceflow.com/docs/api-reference/api-overview) | [V](https://www.bolna.ai/docs/api-reference/agent/v2/overview) |
| SIP | [V](https://docs.cognigy.com/voice-gateway/technical-capabilities) | [V](https://docs.poly.ai/integrations/introduction) | [M](https://www.parloa.com/platform/conversation-infrastructure/) | [N](https://www.voiceflow.com/docs/documentation/deploy/phone/connect-a-phone-number) | [V](https://www.bolna.ai/integrations/sip-generic) |
| Telefonnummern | [V](https://docs.cognigy.com/voice-gateway/creating-outbound-calls) | [V](https://docs.poly.ai/get-started/quickstart) | [N](https://www.parloa.com/platform/conversation-infrastructure/) | [V](https://www.voiceflow.com/docs/documentation/deploy/phone/connect-a-phone-number) | [V](https://www.bolna.ai/docs/frequently-asked-questions) |

### Merkmalsgruppe 3

| Merkmal | Team Follow Up AI | Retell AI | Vapi | Bland AI | Synthflow | ElevenLabs Agents / Conversational AI und TTS |
|---|---|---|---|---|---|---|
| Campaign Management | [V](https://app.teamfollowup.ai/terms) | [V](https://www.retellai.com/) | [V](https://docs.vapi.ai/outbound-campaigns/quickstart) | [V](https://docs.bland.ai/tutorials/batch-calls) | [V](https://docs.synthflow.ai/batch-calling) | [V](https://elevenlabs.io/docs/eleven-agents/phone-numbers/batch-calls) |
| Batch Calling | [N](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/deploy/concurrency) | [V](https://docs.vapi.ai/outbound-campaigns/quickstart) | [V](https://docs.bland.ai/tutorials/batch-calls) | [V](https://docs.synthflow.ai/batch-calling) | [V](https://elevenlabs.io/docs/eleven-agents/phone-numbers/batch-calls) |
| Retry Logic | N | [V](https://docs.retellai.com/features/webhook-overview) | N | [V](https://docs.bland.ai/tutorials/webhooks) | [N](https://docs.synthflow.ai/batch-calling) | N |
| Lead Management | [M](https://teamfollowup.ai/diy/#personas) | [M](https://www.retellai.com/) | N | [N](https://docs.bland.ai/tutorials/batch-calls) | [V](https://docs.synthflow.ai/batch-calling) | [N](https://elevenlabs.io/docs/eleven-agents/customization/tools) |
| Appointment Booking | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/tools) | [V](https://www.bland.ai/) | [V](https://docs.synthflow.ai/actions-overview) | [N](https://elevenlabs.io/docs/eleven-agents/customization/tools) |
| Calendar Integrations | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://vapi.ai/) | [N](https://www.bland.ai/pricing) | [V](https://docs.synthflow.ai/actions-overview) | N |
| CRM Integrations | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://vapi.ai/) | [N](https://docs.bland.ai/tutorials/webhooks) | [V](https://docs.synthflow.ai/getting-started) | [N](https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks) |
| GoHighLevel | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://vapi.ai/) | [N](https://www.bland.ai/) | N | N |

| Merkmal | Cognigy | PolyAI | Parloa | Voiceflow | Bolna |
|---|---|---|---|---|---|
| Campaign Management | [N](https://docs.cognigy.com/voice-gateway/creating-outbound-calls) | [N](https://docs.poly.ai/voice-channel/numbers/outbound-calling) | [N](https://www.parloa.com/knowledge-hub/ai-proactive-customer-outreach/) | [N](https://www.voiceflow.com/docs/documentation/deploy/phone/outbound-calling) | [V](https://www.bolna.ai/docs/guides/outbound/batch-calling) |
| Batch Calling | [N](https://docs.cognigy.com/voice-gateway/creating-outbound-calls) | [N](https://docs.poly.ai/voice-channel/numbers/outbound-calling) | [N](https://www.parloa.com/knowledge-hub/ai-proactive-customer-outreach/) | [N](https://www.voiceflow.com/docs/documentation/deploy/phone/outbound-calling) | [V](https://www.bolna.ai/docs/guides/outbound/batch-calling) |
| Retry Logic | [N](https://docs.cognigy.com/ai/agents/deploy/endpoint-reference/voice-gateway) | [V](https://docs.poly.ai/voice-channel/numbers/outbound-calling) | [N](https://www.parloa.com/knowledge-hub/ai-proactive-customer-outreach/) | [N](https://www.voiceflow.com/docs/documentation/deploy/phone/outbound-calling) | [V](https://www.bolna.ai/docs/guides/outbound/batch-calling) |
| Lead Management | N | [N](https://docs.poly.ai/integrations/introduction) | [N](https://www.parloa.com/platform/integrations/) | [N](https://www.voiceflow.com/docs/documentation/build/tools/api-tool) | [N](https://www.bolna.ai/docs/guides/outbound/batch-calling) |
| Appointment Booking | [V](https://docs.cognigy.com/ai/overview) | [V](https://docs.poly.ai/flows/introduction) | [N](https://www.parloa.com/platform/integrations/) | [N](https://www.voiceflow.com/docs/documentation/build/tools/api-tool) | [V](https://www.bolna.ai/docs/tool-calling/introduction) |
| Calendar Integrations | N | [N](https://docs.poly.ai/integrations/introduction) | [N](https://www.parloa.com/platform/integrations/) | [N](https://www.voiceflow.com/docs/documentation/build/tools/api-tool) | [V](https://www.bolna.ai/docs/tool-calling/introduction) |
| CRM Integrations | [V](https://docs.cognigy.com/ai/overview) | [V](https://docs.poly.ai/integrations/introduction) | [M](https://www.parloa.com/platform/integrations/) | [V](https://www.voiceflow.com/docs/documentation/build/tools/api-tool) | [N](https://www.bolna.ai/docs/guides/outbound/batch-calling) |
| GoHighLevel | N | [N](https://docs.poly.ai/integrations/introduction) | [N](https://www.parloa.com/platform/integrations/) | [N](https://www.voiceflow.com/docs/documentation/build/tools/api-tool) | [N](https://www.bolna.ai/) |

### Merkmalsgruppe 4

| Merkmal | Team Follow Up AI | Retell AI | Vapi | Bland AI | Synthflow | ElevenLabs Agents / Conversational AI und TTS |
|---|---|---|---|---|---|---|
| Human Transfer | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/tools) | [V](https://www.bland.ai/pricing) | [V](https://docs.synthflow.ai/actions-overview) | [V](https://elevenlabs.io/docs/eleven-agents/customization/agent-workflows) |
| Call Recording | [V](https://app.teamfollowup.ai/privacy) | [V](https://docs.retellai.com/features/webhook-overview) | [V](https://docs.vapi.ai/security-and-privacy/data-flow) | [V](https://docs.bland.ai/tutorials/call-logs) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/customization/privacy/audio-saving) |
| Transcription | [V](https://app.teamfollowup.ai/privacy) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/security-and-privacy/data-flow) | [V](https://docs.bland.ai/tutorials/call-logs) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks) |
| Conversation Analytics | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/outbound-campaigns/quickstart) | [V](https://docs.bland.ai/tutorials/call-logs) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/overview) |
| Sentiment / Outcome Analysis | [M](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://docs.vapi.ai/security-and-privacy/data-flow) | [V](https://docs.bland.ai/tutorials/call-logs) | [V](https://synthflow.ai/) | [V](https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks) |
| Testing | [V](https://teamfollowup.ai/diy/#personas) | [V](https://docs.retellai.com/) | [V](https://vapi.ai/pricing) | [V](https://docs.bland.ai/tutorials/call-logs) | [V](https://docs.synthflow.ai/getting-started) | [V](https://elevenlabs.io/docs/eleven-agents/customization/agent-testing) |
| Agent Versioning | N | [N](https://docs.retellai.com/) | [V](https://docs.vapi.ai/assistants/versioning) | [V](https://docs.bland.ai/tutorials/pathways) | [V](https://docs.synthflow.ai/version-control) | [V](https://elevenlabs.io/docs/eleven-agents/overview) |
| White Label | [N](https://teamfollowup.ai/diy/#personas) | [N](https://www.retellai.com/) | N | [N](https://www.bland.ai/) | [V](https://docs.synthflow.ai/admin-dashboard) | N |

| Merkmal | Cognigy | PolyAI | Parloa | Voiceflow | Bolna |
|---|---|---|---|---|---|
| Human Transfer | [V](https://docs.cognigy.com/voice-gateway/technical-capabilities) | [V](https://docs.poly.ai/voice-channel/handoffs) | [M](https://www.parloa.com/platform/integrations/) | [N](https://www.voiceflow.com/docs/documentation/introduction) | [V](https://www.bolna.ai/docs/tool-calling/introduction) |
| Call Recording | [V](https://docs.cognigy.com/voice-gateway/technical-capabilities) | [V](https://docs.poly.ai/api-reference/introduction; https://docs.poly.ai/api-reference/conversations/introduction; https://docs.poly.ai/api-reference/webhooks/introduction) | [N](https://www.parloa.com/platform/parloa-lens/) | [V](https://www.voiceflow.com/docs/documentation/deploy/phone/connect-a-phone-number) | [V](https://www.bolna.ai/privacy-policy) |
| Transcription | [V](https://docs.cognigy.com/ai/agents/deploy/endpoint-reference/voice-gateway) | [V](https://docs.poly.ai/api-reference/introduction; https://docs.poly.ai/api-reference/conversations/introduction; https://docs.poly.ai/api-reference/webhooks/introduction) | [M](https://www.parloa.com/platform/parloa-lens/) | [V](https://www.voiceflow.com/docs/documentation/measure/transcripts) | [V](https://www.bolna.ai/docs/guides/outbound/batch-calling) |
| Conversation Analytics | [V](https://docs.cognigy.com/ai/overview) | [V](https://docs.poly.ai/api-reference/introduction; https://docs.poly.ai/api-reference/conversations/introduction; https://docs.poly.ai/api-reference/webhooks/introduction) | [M](https://www.parloa.com/platform/parloa-lens/) | [V](https://www.voiceflow.com/docs/documentation/introduction) | [V](https://www.bolna.ai/docs/pricing/call-pricing) |
| Sentiment / Outcome Analysis | N | [V](https://docs.poly.ai/glossary/introduction) | [M](https://www.parloa.com/platform/parloa-lens/) | [V](https://www.voiceflow.com/docs/documentation/introduction) | [N](https://www.bolna.ai/integrations/sip-generic) |
| Testing | [V](https://www.cognigy.com/platform/cognigy-voice-gateway) | [V](https://docs.poly.ai/get-started/quickstart) | [M](https://www.parloa.com/platform/performance-lab/) | [V](https://www.voiceflow.com/docs/documentation/measure/tests) | [M](https://www.bolna.ai/) |
| Agent Versioning | [N](https://docs.cognigy.com/ai/for-developers/developers/api-and-cli) | [V](https://docs.poly.ai/get-started/quickstart) | [M](https://www.parloa.com/platform/performance-lab/) | [V](https://www.voiceflow.com/docs/documentation/deploy/environments/overview) | [N](https://www.bolna.ai/docs/api-reference/agent/v2/overview) |
| White Label | N | [N](https://poly.ai/integrations) | [N](https://www.parloa.com/platform/) | [M](https://www.voiceflow.com/pricing) | [N](https://www.bolna.ai/docs/frequently-asked-questions) |

### Merkmalsgruppe 5

| Merkmal | Team Follow Up AI | Retell AI | Vapi | Bland AI | Synthflow | ElevenLabs Agents / Conversational AI und TTS |
|---|---|---|---|---|---|---|
| Agency Features | [M](https://teamfollowup.ai/agency-agent/) | [N](https://docs.retellai.com/) | [N](https://vapi.ai/pricing) | [N](https://www.bland.ai/) | [V](https://docs.synthflow.ai/admin-dashboard) | [N](https://elevenlabs.io/docs/overview/administration/workspaces/overview) |
| Multi-Tenant | [M](https://teamfollowup.ai/diy/#personas) | [N](https://docs.retellai.com/deploy/concurrency) | [N](https://docs.vapi.ai/security-and-privacy/eu-region) | [N](https://www.bland.ai/pricing) | [N](https://docs.synthflow.ai/admin-dashboard) | [N](https://elevenlabs.io/docs/overview/administration/workspaces/overview) |
| EU Hosting | N | [N](https://www.retellai.com/legal/privacy-policy) | [V](https://docs.vapi.ai/security-and-privacy/eu-region) | [M](https://www.bland.ai/security) | [V](https://docs.synthflow.ai/customer-region) | [V](https://elevenlabs.io/docs/overview/administration/data-residency) |
| GDPR Positioning | [V](https://app.teamfollowup.ai/privacy) | [M](https://trust.retellai.com/) | [M](https://docs.vapi.ai/security-and-privacy/GDPR) | [M](https://www.bland.ai/security) | [M](https://synthflow.ai/) | [V](https://elevenlabs.io/docs/overview/administration/data-residency) |
| Pricing | [V](https://teamfollowup.ai/diy/#personas) | [V](https://www.retellai.com/pricing) | [V](https://vapi.ai/pricing) | [V](https://www.bland.ai/pricing) | [V](https://synthflow.ai/pricing) | [V](https://elevenlabs.io/pricing/agents) |
| Usage Pricing | N | [V](https://www.retellai.com/pricing) | [V](https://vapi.ai/pricing) | [V](https://www.bland.ai/pricing) | [N](https://synthflow.ai/) | [V](https://elevenlabs.io/pricing/agents) |
| Concurrent Calls | N | [V](https://www.retellai.com/pricing) | [V](https://vapi.ai/pricing) | [V](https://www.bland.ai/pricing) | [V](https://docs.synthflow.ai/concurrency) | [V](https://elevenlabs.io/pricing/agents) |
| Rate Limits | N | [P](https://docs.retellai.com/deploy/concurrency) | N | [V](https://www.bland.ai/pricing) | [V](https://docs.synthflow.ai/concurrency) | N |

| Merkmal | Cognigy | PolyAI | Parloa | Voiceflow | Bolna |
|---|---|---|---|---|---|
| Agency Features | N | [N](https://docs.poly.ai/platform/introduction) | [N](https://www.parloa.com/) | [M](https://www.voiceflow.com/pricing) | [N](https://www.bolna.ai/docs/frequently-asked-questions) |
| Multi-Tenant | [N](https://docs.cognigy.com/ai/for-developers/developers/api-and-cli) | [N](https://docs.poly.ai/api-reference/introduction; https://docs.poly.ai/api-reference/conversations/introduction; https://docs.poly.ai/api-reference/webhooks/introduction) | [N](https://www.parloa.com/platform/) | [N](https://www.voiceflow.com/docs/api-reference/api-overview) | [N](https://www.bolna.ai/docs/frequently-asked-questions) |
| EU Hosting | [V](https://docs.cognigy.com/voice-gateway/creating-outbound-calls) | [V](https://docs.poly.ai/api-reference/introduction; https://docs.poly.ai/api-reference/conversations/introduction; https://docs.poly.ai/api-reference/webhooks/introduction) | [M](https://www.parloa.com/platform/enterprise-security-governance/) | [N](https://www.voiceflow.com/legal/gdpr) | [N](https://www.bolna.ai/) |
| GDPR Positioning | [M](https://www.cognigy.com/platform/cognigy-voice-gateway) | [M](https://poly.ai/security) | [V](https://www.parloa.com/platform/enterprise-security-governance/) | [M](https://www.voiceflow.com/legal/gdpr) | [N](https://www.bolna.ai/privacy-policy) |
| Pricing | [N](https://www.cognigy.com/pricing) | [V](https://poly.ai/pricing) | [P](https://www.parloa.com/platform/pricing/) | [N](https://www.voiceflow.com/pricing) | [V](https://www.bolna.ai/pricing) |
| Usage Pricing | [N](https://www.cognigy.com/pricing) | [V](https://poly.ai/pricing) | [P](https://www.parloa.com/platform/pricing/) | [M](https://www.voiceflow.com/pricing) | [V](https://www.bolna.ai/pricing) |
| Concurrent Calls | [M](https://www.cognigy.com/platform/cognigy-voice-gateway) | [M](https://poly.ai/) | [M](https://www.parloa.com/platform/) | [V](https://www.voiceflow.com/docs/documentation/deploy/phone/outbound-calling) | [V](https://www.bolna.ai/docs/frequently-asked-questions) |
| Rate Limits | N | [N](https://docs.poly.ai/api-reference/introduction; https://docs.poly.ai/api-reference/conversations/introduction; https://docs.poly.ai/api-reference/webhooks/introduction) | [N](https://www.parloa.com/platform/integrations/) | [N](https://www.voiceflow.com/docs/api-reference/api-overview) | [N](https://www.bolna.ai/docs/api-reference/introduction) |


## 4. Einzelanalysen und Quellen

[Team Follow Up](../research/teamfollowup.md) · [Retell](../research/retell.md) · [Vapi](../research/vapi.md) · [Bland](../research/bland.md) · [Synthflow](../research/synthflow.md) · [ElevenLabs](../research/elevenlabs.md) · [Cognigy](../research/cognigy.md) · [PolyAI](../research/polyai.md) · [Parloa](../research/parloa.md) · [Voiceflow](../research/voiceflow.md) · [Bolna](../research/bolna.md).

## 5. Wechselbedingungen und offene Validierung

Ein verbindlicher OEM-Vertrag mit Exportrechten, voller EU-Verarbeitung, nachgewiesener Isolation und guten deutschen Benchmarks könnte mehr BUY rechtfertigen. Teure Enterprise-Regionen, unklare Resalerechte oder unportable Rufnummern-/Agentenzustände können einen günstigen Kandidaten disqualifizieren. Kundeninterviews können Inbound-Service statt Agency-Outbound priorisieren. Die Landschaft liefert Fragen und Kandidaten, keine finale Lieferantenauswahl und keinen quantifizierten TAM.
