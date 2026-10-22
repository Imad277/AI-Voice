# 06 – SaaS Architecture Research

**Stand / Quellenabruf: 21.10.2026.** **Fazit:** Realtime-Medien, SaaS-Control-Plane und langlebige Business-Workflows benötigen unterschiedliche Fehler-/Latenzgrenzen. Die Plattform sollte fachliche Autorisierung selbst besitzen und Mandantenisolation über sämtliche Daten- und Workerpfade nachweisen. Das ist ein Forschungsbefund über Verantwortungen, **keine finale Services-, Datenmodell- oder Deploymentarchitektur**.

**Confidence:** hoch für dokumentierte RLS-/Workflow-/Lizenzgrenzen, mittel für Produktpassung. Team, Mandantenzahl, Concurrency, SLO, RTO/RPO und Budget bleiben offene Anforderungen.

## 1. Funktionale Systemzerlegung, nicht Wettbewerber-Reverse-Engineering

**TECHNISCHE HYPOTHESE:** Control Plane verwaltet Konten/Clients/Rollen, Integrationen und veröffentlichte Agent-Releases. Die Campaign-/Business-Schicht prüft Eligibility, plant Calls und verarbeitet Outcomes. Eine eigenständige Voice-Session besitzt Audio-/Turnzustand und verwendet nur validierte Tools; Carrier/SIP/PSTN und Speech-/LLM-APIs liefern Medien-/Modellinfrastruktur. Call-Events fließen in Transkript-/Recording-/Usage-/Analytics-Speicher. Diese Zerlegung beschreibt benötigte Funktionen, nicht interne Technologien von Team Follow Up.

| Systembereich | Kritische Verantwortung | Fehlergrenze |
|---|---|---|
| Control Plane | Rollen, Releases, Tools, Konfiguration, Credentials | UI/CRM-Ausfall darf Audio nicht unnötig zerstören |
| Realtime Runtime | Medien/Turns/Unterbrechung/Session, Tool-Timeoutkommunikation | kein n8n/Workflowframe im Audiopfad |
| Business Workflow | Consent/Scheduling/Retry/Outcome/Calendar/CRM/Follow-up | langlebiger Zustand, Cancel/Reconciliation |
| Data / Metering | Tenant-Isolation, Ledger, Medienzugriff, Löschung | Geschäftswahrheit nicht aus LLM-Summary ableiten |

Eine modulare Control Plane kann anfänglich einfacher sein als viele Microservices; der gesonderte Realtimebereich hat dagegen konkrete Skalierungs-/Fehler-/Runtimegründe. Next/React/TypeScript/Tailwind/shadcn und NestJS/Python bleiben Arbeitshypothesen. React Flow wäre ein Editorbaustein, kein Beweis für ausführbare oder sichere Businessflows. Das Projektbudget und Teamwissen entscheiden mit.

## 2. Multi-Tenant-Strategien

| Strategie | Vorteil | Nachteil / Isolation | Kosten, Restore und Migration | Bedingte Passung |
|---|---|---|---|---|
| Shared DB + tenant_id + RLS | zentrale Migration/Pooling; effiziente gemeinsame Ressourcen | umfassende Policy-/Rollen-/FK-Abdeckung nötig; noisy neighbor; privilegierte Bypässe | einfacher Grundbetrieb, schwieriger Tenant-Restore/Export; Upgrade-/Index-Budget gemeinsam | Kandidat für Standardtier bei beweisbarer Isolation |
| Schema per Tenant | Namespace-/Tabellengrenze; tenantbezogene Strukturen | dieselbe DB/Runtime/Rolle kann weiterhin quer zugreifen; search_path-Risiko | viele Migrationen/Objekte/Poolingvarianten; Backup bleibt häufig shared | nur bei konkretem Anpassungs-/Operationsnutzen |
| Database per Tenant | stärkere administrative/Backup-/Blast-radius-Grenze | Anwendung/Secrets/Storage können trotzdem falsch zugeordnet sein | höhere Kapazitäts-/Connection-/Migrationslast, besserer einzelner Restore | Enterprise-/Isolationsanforderungen, nicht automatisch Default |
| Hybrid | Standards effizient, sensitive Kunden isoliert | mehr Betriebsvarianten und Routing-/Migrationslogik | explizites Tier-/Exitmodell erforderlich | spätere Option, wenn Verträge/Scale den Aufwand rechtfertigen |

Quellen: [tenancy-1](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) [tenancy-2](https://www.postgresql.org/docs/current/ddl-constraints.html) [tenancy-3](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html) [tenancy-5](https://docs.aws.amazon.com/whitepapers/latest/saas-architecture-fundamentals/tenant-isolation.html). Die Tabelle ist eine technische Abwägung, keine Sicherheitszertifizierung. `tenant_id` allein genügt nicht; schema/db-per-tenant erspart keine API-Autorisierung.

### PostgreSQL RLS: konkrete Grenzen

RLS hat default-deny ohne Policy, gilt aber nicht für jede DB-Operation. Tabellenbesitzer umgehen es normalerweise; FORCE kann Besitzer einbeziehen, **nicht Superuser/BYPASSRLS**. Normale App-/Workerrollen dürfen nicht gleichzeitig Migration-/Adminrollen sein. `USING` und `WITH CHECK`, permissive Policy-OR und referenzielle Integritätsprüfungen benötigen eigene Prüfung. Composite `(tenant_id,id)`-Fremdschlüssel helfen gegen mandantenfremde Zuordnung, ersetzen aber keine Rechtekontrolle. [tenancy-1](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) [tenancy-2](https://www.postgresql.org/docs/current/ddl-constraints.html)

Tenantkontext stammt aus authentisiertem Server-/Callkontext. Connectionpooling darf keinen sessionweiten Tenantrest übernehmen; transaktionslokales Setting, Initialisierung und Rollback-/Asyncpfade sind zu testen. Kein LLM, Header oder unvalidiertes Webhookpayload darf die autoritative Tenant-ID bestimmen. [tenancy-3](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)

### Daten, RAG und Geheimnisse

Contacts, Calls, Releases, Knowledge, Embeddings, CRM-/Calendarverbindungen, APIkeys, Mitschnitte, Transkripte, Analytics und Billing brauchen konsistente Ownership. Agency→Client-Delegation ist ausdrücklich erteilter und widerrufbarer Zugriff, nicht impliziter Vollzugriff auf alle Kundendaten.

pgvector-ANN-Filter können nach dem Indexscan wirken; selektive Tenantfilter verändern Recall und Scanbedarf. Iterative Scans/Partitionen können helfen, sind aber keine Berechtigungsgrenze. Qdrant-Collections/Payloadfilter und LlamaIndex-Metadaten lösen Tenantautorität ebenfalls nicht allein. [tenancy-4](https://github.com/pgvector/pgvector) [Qdrant](../research/qdrant.md) [LlamaIndex](../research/llamaindex.md)

Secrets je Tenant/Integration verschlüsselt, scopebegrenzt, rotierbar und aus Logs/Prompts/Jobs redigiert halten. Objektschlüssel/CDN/Downloads erst nach Autorisierung; kurzlebige Signed URLs, Tenantcachekeys und Hintergrundkontext prüfen. Traces und Supportexports sind oft übersehene Leakpfade. [tenancy-3](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html) [tenancy-9](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)

## 3. Durable Workflows und Queues

| Kandidat | Dokumentierte Kernsemantik | Sinnvoller Einsatz | Verdeckte Komplexität / Grenze | Lizenz-/EU-/Preisstand |
|---|---|---|---|---|
| Temporal | History/Replay, Activities, Timer, Signals, Retry, Versioning, TS/Python | langlebige Lead-/Call-/CRM-Prozesse mit Cancel/Warten/Recovery | deterministischer Workflowcode/Versionsmigration; stateful Betrieb; Activities wiederholbar | MIT Server/SDK; Cloud Frankfurt; Actions/Storagepreise und Supportpläne |
| n8n | Workflowintegrationen, Credentials, Queue Mode mit Redis/DB/Workern | externe CRM/Notifications/Automationen | Produktkundenzugang/Embedding-Lizenz, tenantcredentials, execution PII, genaues Retryverhalten | Sustainable Use/fair-code, OEM separat; Cloud Frankfurt Claim |
| BullMQ | Redisjobs, delays/retries/backoff/flows/scheduler/concurrency | eng begrenzte Asyncjobs/Scheduling | langlebiger fachlicher Zustand/Reconciliation/Versionen selbst; Redisdurability | Core MIT, Pro kommerziell; selfhost EU möglich |
| Restate | persistierte Steps/Journals, Services/Workflows, Timer/Recovery | Durable Alternative bei passendem Zustandsmodell | Journal-/Partition-/Clusterbetrieb, Migration, externe Effekte nicht automatisch einmal | BSL1.1/Additional Grant; EU-/Cloudpreise offen |
| Event Queue / Broker + eigene Statusmaschine | Zustellung und Entkopplung, produktabhängige Guarantees | mehrere Konsumenten, Outboxprojektionen | Timer/Replays/Cancel/History und langfristige Fachrecovery selbst | kein konkreter Broker ausgewählt; Preis/Region/License offen |

Belege und detaillierte Preis-/Betriebsgrenzen: [Temporal](../research/temporal.md), [n8n](../research/n8n.md), [BullMQ](../research/bullmq.md), [restate.docs](https://docs.restate.dev/) [restate.server](https://docs.restate.dev/server/overview) [restate.license](https://raw.githubusercontent.com/restatedev/restate/main/LICENSE). **Bedingte Empfehlung:** Temporal gegen eine bewusst einfache BullMQ-/Statusmaschinenlösung prüfen; Restate als weitere Alternative nur nach Lizenzfit; n8n komplementär, nicht Realtime-Autorität. Ohne lange Warte-/Cancel-/Recoveryprozesse kann Temporal unnötige Betriebskomplexität sein.

## 4. Zuverlässiger Lead→Termin→CRM-Prozess

**Vorgeschlagenes fachliches Ablaufmodell, nicht implementiert:** Lead erfassen → Zweck/Empfänger/Consent/Sperre prüfen → mit Zeitzone/Anrufbudget planen → vor tatsächlichem Dial erneut prüfen → eindeutigen Callauftrag erstellen → Session an eingefrorenen Release binden → qualifizieren und kritische Felder bestätigen → autorisierte Toolaktion → bestätigten Termin/CRM-Status speichern → Follow-up zulässigkeitsprüfen → Outcome/Usage auswerten.

Bei Callstart-Timeout erst Providerstatus abgleichen: „HTTP fehlgeschlagen“ ist kein Beweis, dass nicht angerufen wurde. Doppelte Webhooks brauchen Event-/Call-ID-Deduplizierung. Geschäftsdatenänderung plus Outbox gehören in eine Transaktion, Zustellung bleibt duplikatfähig. Signaturprüfung muss den passenden Rohpayload und Replaygrenzen berücksichtigen. [tenancy-6](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) [tenancy-7](https://docs.stripe.com/webhooks) [tenancy-8](https://docs.stripe.com/api/idempotent_requests)

Kalenderverfügbarkeit erneut autoritativ prüfen. Eine lokale DB-Sperre verhindert keine externen Buchungen anderer Akteure. Für unknown outcome keine blind wiederholte Buchung und keine Erfolgsaussage im Gespräch; Reconciliation oder menschlichen Klärungsfall erzeugen. CRM und Calendar sind keine gemeinsame DB-Transaktion. Opt-out stoppt zukünftige Attempts/Followups und laufende fachliche Outreach-Aktionen nach Policy, selbst wenn Jobs schon geplant sind.

Live-Tools brauchen enge Timeouts, validierte Rückgaben, operation IDs und ein verständliches Fallback. Eine externe Integration darf den Dialog nicht unbegrenzt blockieren. Genau-einmal-Semantik einer Engine endet an deren kontrollierter Transaktionsgrenze. [restate.workflows](https://docs.restate.dev/tour/workflows)

## 5. Versionierung, Metering und Datenlebenszyklus

Agentrelease referenziert unveränderliche Prompt-/Rules-/Tools-/Flow-/Knowledgeversion und Providerkonfiguration. Jeder Call bindet dieselbe Release-ID; Änderungen während der Session erzeugen keine stillen Mischstände. Modelle/stimmen können trotzdem serverseitig verändert/deprecated werden: Snapshotbindung und Regressionstest gehören zum Releaseprozess.

Usage-Ledger enthält Tenant/Client, Call-/Provider-ID, Release, Zeit, Einheit, Menge, Währung, Tarifversion und Korrekturereignis. Dashboardaggregate sind Projektionen. Abrechnungszeit/Speech-/Audio-/Tokenzeit und Transferlegs nicht zusammenwerfen; verspätete Events und Providerrechnungen reconciliieren. Tenantbudgets und Limits schützen vor noisy neighbor/toll fraud. [tenancy-3](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)

Löschung muss Contacts/Audio/Transcripts/Embeddings/Caches/Exporte/Analytics/Providerdaten umfassen; rechtliche Consentnachweise getrennt halten. Ein Backuprestore darf gelöschte Daten nicht unbeabsichtigt wieder aktivieren: Löschmarker und Restoreverfahren testen. RTO/RPO, Tenantrestore und Retention noch nicht beschlossen. [tenancy-3](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html) [compliance-01](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng)

## 6. Open-Source- und Lizenz-Audit

Die Tabelle fasst tatsächlich geöffnete Repository-/Lizenz-/Releasequellen zusammen. Jede Zeile verlinkt das vollständige Dossier mit Security-, Integrations- und Aktivitätsgrenzen. **Contributor-Gesamtzahlen wurden überwiegend wegen dynamisch nicht ladbarer Graphen nicht verifiziert; keine Zahlen geschätzt.** Sichtbare Releases beweisen Wartung, nicht Produktionsqualität. Drittdependencies/Modelle benötigen eine zusätzliche Stücklistenprüfung.

| Projekt / Repository-Dossier | Lizenz / kommerzielles SaaS | Sichtbare Aktivität am Abruf | Produktions-/Security-/Lock-in-/Integrationsrisiko |
|---|---|---|---|
| [LiveKit Agents](../research/livekit.md) | Apache-2.0; separate frameworkgebundene Turn-Model-License | 1.8.8, 15.10.2026 | Media/SIP/Workers integrieren; Cloudfeatures/Modelle getrennt; Drain/HA prüfen |
| [Pipecat](../research/pipecat.md) | BSD-2-Clause | 1.13.0, 19.10.2026 | Pipelines/Transportadapter; Daily-Cloud optionaler Lock-in; Pythonops |
| [Bolna](../research/bolna.md) | MIT Framework; Hosted/UI separat | 0.10.306, 20.10.2026 | Indien-/Providerfokus, Deutschland/EU und Hostedrechte offen |
| [Vocode](../research/vocode.md) | MIT | jüngste verifizierbare Belege 2024 | Wartungs-/Dependencyrisiko, historische Twiliointegration; nicht automatisch eingestellt |
| [Temporal](../research/temporal.md) | MIT Server/TS SDK | Server1.32.1, 08.10.2026 | Replay/Activity-/Statebetrieb; neue Features/Cloud separat; komplizierte Migration |
| [n8n](../research/n8n.md) | Sustainable Use, source-available; OEM/Embed separat | aktive Repository-/Docsprüfung; genaue Version im Dossier soweit belegt | Lizenzkundenzugang, Credentials/ExecutionPII; nicht OSI-OSS |
| [BullMQ](../research/bullmq.md) | MIT Core, Pro separat | 6.3.19, 20.10.2026 | Redis-Persistenz/noeviction, Jobs Klartext; fachliche Recovery selbst |
| [Restate](../research/restate.md) | BSL1.1, spätere Apache2.0, Additional Grant | 1.8.0, 14.10.2026 | öffentliche Restate-API-Plattformnutzung eingeschränkt; Clusterstate/Partitionsgrenzen |
| [Asterisk](../research/asterisk.md) | GPLv2/alternative kommerzielle Rechte; Module separat | aktuelle Zielrelease-/Contributorlage nicht vollständig verifiziert | SIP/ARI/Recording/Transfer; hohe PBX-/Fraud-/Tenantops; Distribution juristisch prüfen |
| [FreeSWITCH](../research/freeswitch.md) | MPL1.1 + Komponentenlizenzen | 1.11.3 sichtbar | SIP/Media/Event Socket; STUN-Advisory bis1.10.12, ab1.11.0 behoben; Zielpatch prüfen |
| [Langfuse](../research/langfuse.md) | MIT Core mit EE-Ausnahmen | 4.67.0, 21.10.2026 | viele Statekomponenten; PII/masking/tenant; Cloudunits und EE-Lock-in |
| [OpenTelemetry](../research/opentelemetry.md) | Apache2.0 in geprüften Collector/Python/JS-Repos | Collector0.163.0, 14.10.2026 | kein Backend; exporters/baggage/sampling können PII leaken; mixed maturity |
| [promptfoo](../research/promptfoo.md) | MIT Core; Enterprise separat | 0.124.1, 08.10.2026 | custom configs/code nicht sandboxed; remote redteam/grade mögliche Egress; kein PSTN-Test |
| [Qdrant](../research/qdrant.md) | Apache2.0 | 1.19.2, 05.10.2026 | Selfhostdefaults ohne Auth/all interfaces; TLS/Auth/ownership; extra DB Betrieb |
| [LlamaIndex](../research/llamaindex.md) | MIT Core; Integrationen/LlamaCloud separat | 0.14.25, 21.09.2026 | Adapter-/Ingestionkomplexität, prompt injection; Filter kein Auth; Dependencies einzeln prüfen |

**Keine Installation oder Ausführung dieser Repositories.** GPL/MPL sind nicht pauschal SaaS-unzulässig; konkret angebotene Distribution, kombinierte Module, Änderungen und Markenrechte entscheiden. BSL, Sustainable Use und nichtkommerzielle Modellgewichte sind keine permissiven Open-Source-Lizenzen. Vor Aufnahme SBOM, Zielversion, Sicherheitsmeldungen, Dependency-/Modelllizenz und kommerziellen Use Case juristisch prüfen. Keine Lizenzempfehlung ersetzt anwaltliche Bewertung.

## 7. Was vor der Architekturentscheidung noch fehlt

Tenant-/Agencyzugriffspolitik, Datenklassen, Zahl/Größe der Clients, Release-/Rollbackanforderungen, Hintergrundworkflowdauer, Peak- und Burstlast, SLO/RTO/RPO, EU-only vs zulässige Transfers, Supportmodell und Teamkompetenz. Benchmarks müssen Leak-/RLS-/Tool-/Restorefehler, Kalender-/Carrierambiguität, Queue/Engine-Neustart und aktive Calls beim Rollout abdecken. Erst diese Evidenz rechtfertigt Datenbanktier, Workflowengine und Hostingstrategie.
