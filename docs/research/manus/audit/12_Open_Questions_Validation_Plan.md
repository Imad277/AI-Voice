# 12 – Open Questions & Validation Plan

**Stand: 21.10.2026.** **Fazit:** Der Audit erlaubt einen gezielten Benchmark und ein Commercial-/Legal-Gate, aber noch keine finale Architektur. Kein produktiver Call, Lasttest, Penetrationstest, Hörvergleich oder Anbieter-/Juristenkontakt wurde im Audit durchgeführt.

**Confidence:** hoch für die Notwendigkeit dieser Prüfungen und die Messabgrenzung, niedrig für die nachfolgend vorgeschlagenen numerischen Ziele. Ziele, Zeit-/Budget-/Sampleangaben sind ausdrücklich **ANNAHMEN für den Review**, keine Industriestandards oder gemessenen Ergebnisse.

## 1. Anforderungsfragen, die jede Technologieempfehlung verändern

| Frage | Warum entscheidungsrelevant | Benötigte Antwort / Owner |
|---|---|---|
| Erster Use Case, Inbound/Outbound, B2C/B2B, Branchen/Länder? | Outreachrecht, Tools, Datenklasse, Carrier und Dataset | Mensch/Product + Fachjurist |
| Agency→Client-Zugriff und WhiteLabel-/Resellmodell? | Tenantgrenze, Billing, OEM-/Carrierrechte | Product + Security + Legal |
| EU-only Verarbeitung oder zulässige Drittlandtransfers? | Modelle/Endpoint/Failover/Enterprisepreis | Legal/Datenschutz + Mensch |
| Monatlicher Verbrauch und Peak-/Burstprofil? | Worker/CarrierCPS/concurrency/quotas/HA | Product/Ops, nicht allein Monatsminuten |
| SLO, RTO/RPO, Callfallback und Supportpflichten? | Hosting/DB/Restore/State/On-call | Mensch + Technical Review |
| Team, Budget, Python-/SIP-/Statebetrieb-Kompetenz? | Managed vs selfhost, Enginekomplexität | Mensch/Claude-Code-Planung nach Gate |
| Kritische Entitäten/Tool-Aktionen und Toleranz? | Modell-/Confirmation-/Evaluationdesign | Fachverantwortlicher + QA |
| Zulässige Recording-/Transcript-/Analytics-/Retentionpolitik? | Dataset, Produktdefault, AVV/Löschung/Storagekosten | Fachjurist/Datenschutz |
| Verkaufs-/Usageeinheit und Zielmarge? | Pricingminimum, Mobilmix, Ergebnisprofitabilität | Businessowner nach vollständigem COGS |

## 2. Evidenz- und Vertragsgate, vor Benchmark/Architektur

Pro shortlisted Provider nachweisen: aktuelles Modell/Snapshot/API, Dienstregion je Datenklasse, Subprozessorliste/AVV/TOM, Training/Retention/Abuse-/Support-/Backupdaten, Failoververhalten, commercial SaaS/OEM-/WhiteLabel-/Automationsrechte, Tarif-/Route-/Quoten-/SLAversion und Exit/Porting. Ungeöffnete/dynamisch unlesbare Seiten nicht als Freigabe werten.

Juristisch separat prüfen: KI als automatische Anrufmaschine, B2B-/B2C-/Servicezweck, Consentbeleg/Scope/Optout, AI-Act-Rollen/Disclosure/Markierung und aktuelle Fristen, Recording/Transkription, besondere Daten/DPIA, CallerID und nationale Zielmarktregeln. Eine AI-Offenlegung heilt keinen unzulässigen Werbeanruf. [compliance-03](https://www.gesetze-im-internet.de/uwg_2004/__7.html) [compliance-04](https://www.gesetze-im-internet.de/englisch_uwg/englisch_uwg.html) [compliance-06](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50) [compliance-08](https://www.gesetze-im-internet.de/stgb/__201.html)

## 3. Reproduzierbarer Voice-Benchmark

Ein Testmanifest fixiert Agent-/Prompt-/Rule-/Knowledge-/Toolrelease, Modell-/Voice-ID, Runtimeversion, Carrier/Nummer/Zielroute, Codec/Sampling, Region, Zeit, Puffer-/EOT-/VADsettings, Parameter und abrechenbare Einheiten. Gleiche Stimuli/Fachtools für alle Varianten; Reihenfolge kontrolliert randomisieren, Wiederholungen/Failures nicht aus Mittelwerten entfernen. Einen separat eingefrorenen Holdout für den Freigabelauf behalten.

### Datasetvorschlag – ANNAHME

Zunächst 250 Äußerungen/Fälle mit mindestens 20 eigens einwilligenden deutschsprachigen Sprechern als **exploratives** Material, danach Sample-/Powerplanung nach beobachteter Varianz. Kein Anspruch auf Dialektrepräsentativität mit dieser Zahl. Standarddeutsch plus relevante regionale Akzente, unterschiedliche Sprechgeschwindigkeit/Pausen/Stimmen, Clean-/G.711-/Festnetz-/Mobilspur, Lärm/Crosstalk/Unterbrechung. Namen, Straßen/Orte, E-Mail-Buchstabieren, Telefonnummern, Beträge, Datum/Uhrzeit, Kennzeichen/VIN und Selbstkorrekturen gezielt schichten.

Referenz durch deutschkundige Annotierende, Konfliktadjudikation, Normalisierung vorab festlegen, Fehler je Klasse ausweisen. Synthetische Fälle brauchen Nutzungsrechte; keine produktiven Leadlisten in öffentliche Demos laden. Aufnahmen und menschliche Hörtests erfordern vorab Rechtsgrundlage, Zweck, Zugriff und Retention.

### Messgrößen

| Dimension | Messung | Nicht verwechseln mit |
|---|---|---|
| ASR | WER=(Substitution+Deletion+Insertion)/Referenzwörter; Entity exact/normalized accuracy, field errors und Rückfragen | globale WER als alleiniger Buchungsqualität |
| Antwortlatenz | letzte tatsächliche Nutzersprache → erstes hörbares Antwortaudio; p50/p95/N/failures je Fall | Provider-TTFB oder nur Token-TTFT |
| Turn-Ende | premature/late endpoints, Pausen-/Backchannelfälle | aggressives Endpointing als Qualitätsgewinn |
| Barge-in | false/missed interruption, Stoplatency, verlorene Wörter, Resume/context | jedes Geräusch als echte Unterbrechung |
| TTS | verblindete AB-/Präferenz/ACR nach Verständlichkeit/Natürlichkeit/Aussprache; CIs | MOS aus unterschiedlichen Studien direkt vergleichen |
| Task/Tools | autorisierte richtige Aktion, Datenbestätigung, Fehler-/Timeoutpfad, bestätigter Erfolg | strict JSON als fachlich korrekt |
| Kosten | echte Calllegs/STTaudio/LLM-/Audiotokens/TTScredits/Session/Storage vs Rechnung | Kosten pro verbundener Minute als Ergebnisprofitabilität |
| Robustheit | jitter/loss/reconnect/coldstart/429/outage/deploydrain | einzelner erfolgreicher Democall als SLO |

ITU P.800/P.808 liefern Hörtestgrundlagen, P.863 Hörqualität, aber keinen vollständigen Agent-/ASRtest. Menschliche Turngapwerte sind Kontext, kein KI-SLO. NIST OpenASR20 betrifft andere Sprachen und belegt keine deutsche Rangfolge. [benchmark-01](https://www.itu.int/itu-t/recommendations/rec.aspx?rec=13570) [benchmark-02](https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-P.800-199608-I!!PDF-E&type=items) [benchmark-03](https://www.itu.int/ITU-T/recommendations/rec.aspx?id=14665) [benchmark-04](https://www.nist.gov/publications/openasr20-open-challenge-automatic-speech-recognition-ofconversational-telephone-speech) [benchmark-05](https://pmc.ncbi.nlm.nih.gov/articles/PMC10077995/) [benchmark-06](https://arxiv.org/html/2503.03250v2)

## 4. Vorgeschlagene Akzeptanzziele – ANNAHME, im Review zu genehmigen

Für eine erste Baseline: nicht-toolgebundene Antwort p95 ≤1,5 Sekunden und median ≤0,8 Sekunden; Interrupt→Audio-stop p95 ≤0,3 Sekunden; false/missed barge-in jeweils <5% im festgelegten Dataset. Kritische Felder nach Rückfrage/Bestätigung ≥99% korrekt, keine sicherheitskritische unbestätigte Fehlbuchung. Diese Zahlen sind **Produktvorschläge**, keine belegten Anbieterwerte oder universellen Standards; Akzeptanz und Samplegröße können sie ändern.

Harte Stopkriterien unabhängig von Durchschnittsqualität: irgendein demonstrierter Cross-Tenant-Zugriff, unautorisierter Toolseiteneffekt, Outreach trotz Sperre, unzulässige Aufnahme oder falsche Erfolgsmeldung bei unbekannter Buchung. „Null Fehler beobachtet“ ist kein mathematischer Beweis absoluter Sicherheit; Negative Cases, Holdout und laufende Regression bleiben nötig.

Ein Runtimevergleich beginnt mit LiveKit vs Pipecat bei identischen Speech-/Tool-/Carrierbedingungen. Danach STT/TTS-Paare und native S2S gegen die besten kontrollierten Kaskaden vergleichen. Nicht jede mögliche Kombination testen. Stimmenpräferenz und Modellqualität getrennt behandeln, Effekt-/Unsicherheitsgrenzen berichten.

## 5. Business-, Isolation- und Failuretests

| Testfamilie | Pflichtfälle | Freigabenachweis |
|---|---|---|
| Booking | zwei Calls gleicher Slot, externer Kalenderwriter, DST/timezone, timeout nach Annahme, Retry/Storno | keine blinde Wiederholung, idempotente fachliche Referenz, Reconciliation, keine falsche Erfolgsansage |
| CRM / Follow-up | 429/outage, ungültige Felder, doppelte Events, spätes Outcome, widerrufener Kontakt | begrenzte Retries, manuelle Klärung, Consent erneut prüfen |
| Carrier | noanswer/busy/voicemail, Callstart unknown, DTMF, warmtransfer unreachable/new participant | eindeutige operation IDs, kein Doppelcall, Transfer-/Recordingpolicy |
| Workflow | Neustart/replay/versionchange, geplantes Cancel/Optout, out-of-order Webhooks | History-/Statekonsistenz, Duplikatschutz, fachliche Sicht statt Queue-only Erfolg |
| RLS/Tenant | Appowner/bypass, pooled tenantcontext, forged IDs/headers/jobs, API/CSV/Admin | deny-by-default und negative read/write über alle Zugriffspfade |
| RAG/Storage/Secrets | fremder embeddingfilter, signedURL/objectkey, cache/log/export, prompt secret extraction | kein fremder Inhalt/credential; ownership aus Authkontext |
| Tool Abuse | prompt/KB-injection, arbitrary URL/SSRF, transfer toll fraud, scope escalation | enge Tools, Allowlist/Budget/Autorisierung/Audit |
| Delete / Restore | tenantoffboarding, providerdelete, backuprestore gelöschter Daten | minimale gesetzliche Belege separat, Löschmarker/Retention/recovery getestet |
| Billing | short sessions/rounding/cached tokens/ttsdiscard/transferlegs/credits/duplicateusage | reproduzierbares Ledger, Abgleich Providerrechnung, keinen Doublecount |

Belegbare Kontrollprinzipien: [tenancy-1](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) [tenancy-3](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html) [tenancy-4](https://github.com/pgvector/pgvector) [tenancy-6](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) [tenancy-7](https://docs.stripe.com/webhooks) [compliance-11](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) [compliance-12](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/). Konkrete Produktimplementierung wurde nicht geprüft.

## 6. Last, Zeit und Testbudget – Planungsannahmen

Explorativ 10/50/100 parallele Calls plus genehmigte Carrier-CPS-Bursts, längere Sessions und Transferreserve testen; diese Zahlen dürfen ohne tatsächliches Kundenprofil nicht zur finalen Kapazität erklärt werden. 1.000.000 Minuten/Monat in 22 Tagen à8 Stunden bedeutet im Mittel etwa95 aktive Gespräche, Peak/Burst erheblich höher möglich. Modelle/Cloudpläne können schon darunter limitieren.

Ein vorgeschlagenes Validierungssprintbudget: 2–3 Wochen mit Voice-/Backendengineering, QA und Legal; etwa2.000 freigegebene Testminuten und 200–500 USD direkte API-/Carriergebühren als **Budgetannahme**, plus nicht bezifferte Personalkosten/Enterprise-/Spezialjuristenkosten. Keine Calls oder Ausgaben sind hiermit autorisiert oder ausgelöst. Nach Tarif-/Quota-/Datasetprüfung Budget revidieren.

## 7. Evidence-to-Decision-Gate

Für jede Entscheidung eine Evidenzkarte: Optionen, harte Ausschlüsse, identische Benchmarkbedingungen, Ergebnisse/CI/Failures, Vertrags- und Lizenzstand, realer COGS-/Betriebsaufwand, Migration/Exit, Gegenargument und Empfehlung mit Confidence. ChatGPT überprüft; der menschliche Projektverantwortliche entscheidet; Claude Code implementiert später anhand freigegebener Anforderungen/ADRs. Erfolgreicher Benchmark allein ersetzt keinen Legal-/Security-/Vertragsgate.

## 8. Abschließende Entscheidungsmatrix – Entscheidungen bleiben offen

| Decision | Option A | Option B | Option C | Current Recommendation | Confidence | Requires Benchmark? |
|---|---|---|---|---|---|---|
| Voice Runtime | LiveKit Agents | Pipecat | stärker eingekaufte Voice API / Bolna | LiveKit/Pipecat identisch benchmarken; offen | Mittel | Ja: Audio/Tools/Last/Ops |
| Voice-Architektur | STT→LLM→TTS | Native S2S | delegierter Hybrid | Kaskade Baseline, native parallel; offen | Mittel | Ja: Entities/Latenz/Kosten |
| STT | Deepgram Nova/Flux | Speechmatics/Soniox | Azure/Google/OpenAI/Mistral | deutsche Entity-/EOT-/EUprüfung entscheidet | Niedrig–mittel | Ja |
| TTS | ElevenLabs | Cartesia | Azure/Google/Mistral | Blindtest + Region/Endpointrechte; offen | Niedrig–mittel | Ja |
| LLM | OpenAI Text/Realtime | Gemini/Vertex | Mistral / Claude mit geprüftem Datenpfad | Task-/Toolqualität und regionaler Vertrag; offen | Mittel | Ja |
| Telephony | Twilio | Telnyx | deutscher SIPcarrier | DE-Raten/Nutzungsrecht/Medienroute testen; offen | Mittel | Ja + Vertragsgate |
| Workflow Engine | Temporal | BullMQ+fachlicher State | Restate | Prozessdauer/Recovery/Ops/Lizenz entscheidet; offen | Mittel | Ja: Failure/Replay/TCO |
| Hosting Strategy | Managed EU | EU Selfhost | Hybrid/BYOC | SLO/Team/Datenpfad/Peak entscheiden; offen | Mittel | Ja + Vertragsgate |
| Tenant Isolation | Shared+RLS | Schema/Tenant | DB/Tenant oder Hybrid | Shared-RLS gegen Enterpriseisolation prüfen | Mittel | Ja: negative Tests/Restore |
| External Automation | n8n OEM/internal nach Freigabe | direkte Connectoren | alternative Integrationengine | n8n nur Background und nach Lizenzfit | Mittel | Ja: Lizenz/Secrets/Failure |
| Knowledge / Vector | PostgreSQL/pgvector | Qdrant | minimaler Retrievalpfad | SQL-first bei passendem Recall/Lastprofil | Mittel | Ja: Tenantrecall/Latency |
| Observability / QA | OTel + eigener Harness | Langfuse ergänzt | Runtime-Evals/promptfoo ergänzt | standardisierte Events + PSTNtests, kein PIIdefault | Mittel | Ja: Egress/Overhead/Evalcoverage |

## 9. Abschließende Prioritätenliste

**P0 – muss vor Architektur geklärt werden:** erste Use Cases/Empfänger/Länder und KI-Outreach-Rechtsprüfung; EU-only-/Transferpolicy und Recording/Transkriptzwecke; Agency-/Client-/Resalerechte; Team/Budget/SLO/Peak; Datensatz und harte Freigabekriterien; Runtime-/Kaskade-/native Kernbenchmark; kritische Tenant-/Toolautorität; aktuelle Carrier-/EU-Preis- und Vertragsbasis. Ohne tragfähige Antworten keine finale Architektur.

**P1 – muss vor Implementierung geklärt werden:** konkrete API-/Modell-/Frameworkversionen und Lizenz-SBOM; Agent-/Tool-/Usage-/Webhookverträge; RLS-/Secrets-/RAG-/Objectstoragekontrollen; Booking/Call-unknown-Reconciliation und Optout/Cancel; Retention/Deletion/Restore/RTO/RPO; Workflowversionierung; Rechnungs- und Quotenmodell; Disclosure-/Ansagetexte juristisch freigeben. Implementierungsentscheidungen erst nach dokumentiertem Review.

**P2 – kann während der Entwicklung entschieden werden:** UIkomponentendetails, Editorlayout, nicht kritische Dashboardprojektionen, Monitoringdarstellung, Performanceindizes nach realem Profil, zusätzliche Connectoren nach Bedarf, getestete Fallback-/Optimierungstuningwerte innerhalb freigegebener Grenzen. Security-/Legal-Pflichten dürfen nicht als P2 verschoben werden.

**P3 – spätere Produktentscheidung:** zusätzliche Branchen-/Automotive-/Fleetvorlagen, Voice Cloning, weitergehende Conversation Optimization, komplexe Agency-Rebillingmodelle, Enterprise-DBtiers, weitere Länder/Carrier und neue native Audiomodelle. Gutachtery24 bleibt ein unabhängiger Integrationsfall; die finale Architekturentscheidung ist ausdrücklich nicht Teil dieses Audits.
