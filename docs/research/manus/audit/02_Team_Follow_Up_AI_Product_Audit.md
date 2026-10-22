# 02 – Team Follow Up AI Product Audit

**Auditgegenstand:** Team Follow Up AI (Referenzprodukt)  
**Kategorie:** Agency / Lead Automation  
**Abrufdatum aller nachstehend zitierten Webquellen:** 21.10.2026  
**Evidenzgrenze:** ausschließlich öffentlich zugängliche Seiten; kein Login, kein Kauf, kein Anruf und kein Funktionstest. Aussagen zu Qualität, Skalierung oder Innenansicht sind daher nicht als eigene Tests zu lesen.

## 1. Kurzurteil

Team Follow Up AI positioniert sich als **GoHighLevel-(GHL-)zentriertes, no-code-orientiertes AI-Voice-Angebot für Lead-Gen-Agenturen**. Der sichtbare Kern ist kein allgemeines Contact-Center, sondern die schnelle Qualifizierung, Terminbuchung, Live-Übergabe und Nachverfolgung von Leads in vorhandenen GHL-Sub-Accounts. Der Anbieter wirbt mit White-Label-/Resale-Nutzung, einer visuellen Workflow-Erstellung, editierbaren Prompts/Stimmen sowie Aufzeichnungen, Transkripten und Outcomes. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/)

**VERIFIZIERT:** Die aktuellen App-Bedingungen vom 09.06.2026 beschreiben eine gehostete Plattform zum Erstellen, Konfigurieren, Testen, Deployen und Verwalten von AI-Voice-Agents und zugehörigen Kampagnen, die Anrufe platziert und entgegennimmt. Sie nennen Drittanbieter für Telefonie, Sprach-/Voice-Verarbeitung und Infrastruktur ausdrücklich. Sie belegen damit Produktumfang und externe Abhängigkeiten, nicht aber deren Namen, Architektur, Leistungswerte oder Datenregionen. [teamfollowup-s5](https://app.teamfollowup.ai/terms)

**Einschätzung:** Produkt-Markt-Fit und Journey sind öffentlich relativ klar, technische und kommerzielle Due Diligence jedoch nur teilweise möglich. Insbesondere API/SIP, verwendete Carrier/Modelle, Limits, Overage, Datenresidenz, Subprozessoren, Versionierung, Tenant-Isolation und Verfügbarkeit bleiben **NICHT VERIFIZIERT**. Die jüngeren App-Rechtsseiten sind detaillierter als die teils generisch bzw. widersprüchlich wirkenden Marketing-Rechtsseiten; für einen EU-Einsatz wäre dies ein eigenes Beschaffungs- und Rechtsrisiko.

## 2. Positionierung, Zielgruppen und Personas

Die DIY-Seite bezeichnet das Angebot als „AI voice agent software · built for agencies“ und verspricht Agenten, die Kundenleads „call, qualify, and book“ sowie Ergebnisse in GHL-Kontaktdatensätze zurückschreiben. Das ist eine **MARKETING CLAIM**, aber zugleich eine klar erkennbare Produktpositionierung. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas)

| Sichtbare Persona / Bedarf | Öffentliche Aussage | Auditbewertung |
|---|---|---|
| Lead-Gen-Agenturinhaber | Mehr Speed-to-lead, zusätzliche hochmargige Serviceleistung, Nacht-/Wochenendabdeckung und Resale an bestehende Kunden. | **MARKETING CLAIM**; sehr eindeutiger primärer ICP. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) |
| Kleine bis große Agentur | „One man bands to 8 figure agencies“; je GHL-Sub-Account ein Agent. | **MARKETING CLAIM**; kein Nachweis für Mandantenisolation oder Enterprise-Scale. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| In-house-Marketingteams | Inbound qualifizieren, kalte Listen reaktivieren, heiße Leads übergeben. | **MARKETING CLAIM**. Die verwendeten Begriffe belegen keine spezifische Kampagnenlogik. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Coaches, Consultants, Infoproducts | Qualifizieren, Discovery-Calls buchen bzw. umplanen. | **MARKETING CLAIM**. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Ausschlusskriterien | Keine Agenturen ohne kontinuierliche Leadgenerierung; derzeit nur GHL-Integration; perfekte Agenten nicht „out of the box“ erwarten. | **VERIFIZIERT** als veröffentlichte Einschränkung, nicht als Wirksamkeitsnachweis. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) |

Die Landingpages nennen 7.603+ bzw. 9.276 gebuchte Termine/Live-Transfers. Unterschiedliche Zählerstände und kein prüfbarer Zeitraum/Datensatz bedeuten: **MARKETING CLAIM**, nicht als Benchmark oder Produktleistungsversprechen verwenden. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/)

## 3. Sichtbare Customer Journey und Onboarding

Die dokumentierte Journey ist bewusst friktionsarm und in GHL eingebettet:

1. **Konto anlegen:** Die frei zugängliche App-Seite verlangt Business-Name, geschäftliche E-Mail und Telefonnummer oder Google-Anmeldung; sie verspricht eine Agentenerstellung in unter 60 Sekunden. [teamfollowup-s4](https://app.teamfollowup.ai/signup-30-day-free-trial) Das ist eine **MARKETING CLAIM** zur Dauer, während die sichtbaren Felder selbst **VERIFIZIERT** sind.
2. **Geführtes Setup:** Die Agency-Seite beschreibt Prompt-Framework, GHL-Anbindung, visuellen Workflow und Handoff als vier Schritte. Die Sign-up-Seite nennt Onboarding-Support über privaten Slack-Channel und Walkthrough. **MARKETING CLAIM**; keine Innenansicht oder Anleitung wurde öffentlich gelesen. [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) [teamfollowup-s4](https://app.teamfollowup.ai/signup-30-day-free-trial)
3. **Agent konfigurieren:** Prompt, Stimme, Persönlichkeit und jede Zeile seien editierbar; ein Builder solle Drag-and-connect-Logik bieten. Dies ist **MARKETING CLAIM**. Öffentliche Bilder/Texte ersetzen keine Prüfung der verfügbaren Nodes, Validierung, Rollen oder Publishing-Schritte. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/)
4. **Test vor Livegang:** Die DIY-FAQ nennt fünf kostenlose Browser-Testminuten. Erst eine hinterlegte Karte schalte weitere 45 Minuten und echte Anrufe frei. **VERIFIZIERT** als veröffentlichte Angebotsbedingung, nicht als eigener Test. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas)
5. **Betrieb und Nachweis:** Nach Anbieterangabe werden Gespräche aufgezeichnet, transkribiert und mit Outcome versehen; GHL-Kontakte werden aktualisiert. Recording/Transkription werden zusätzlich in der aktuellen Datenschutzerklärung als verarbeitete Call-Daten bestätigt; die konkrete Darstellung im Dashboard bleibt **NICHT VERIFIZIERT**. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s6](https://app.teamfollowup.ai/privacy)

**Preis-Konflikt:** Die DIY-Seite sagt 14 Tage, danach **USD 97 pro Monat**, kündbar jederzeit, und differenziert die Minuten wie oben. Die öffentliche Sign-up-Seite sagt dagegen „Free forever“ und steht auf einer URL mit „30-day-free-trial“; die Agency-Seite nennt nur 14 Tage ohne Karte. Dies lässt sich ohne Login nicht auflösen. Für Beschaffung gilt daher nur: veröffentlichtes Mindestabo **USD 97/Monat nach der 14-Tage-Testphase**; enthaltene wiederkehrende Minuten, Overage, Telefoniegebühren, Steuern, Währungskonvertierung, Zahlverfahren, Concurrent Calls und Rate Limits sind **NICHT VERIFIZIERT**. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) [teamfollowup-s4](https://app.teamfollowup.ai/signup-30-day-free-trial)

## 4. Produktfunktion und 40-Feature-Matrix

Status bedeutet ausschließlich Evidenzstatus, nicht Marktqualität. „Nicht verifiziert“ ist kein Nein.

| Feature | Status | Öffentliche Evidenz und Grenze |
|---|---|---|
| Inbound Calling | **VERIFIZIERT** | App-AGB nennen das Platzieren **und Empfangen** von Telefonanrufen; Inbound-Routing/Nummerneinrichtung offen. [teamfollowup-s5](https://app.teamfollowup.ai/terms) |
| Outbound Calling | **VERIFIZIERT** | App-AGB und Beispiele für Speed-to-lead/„Power Dialler“; Dialing-Regeln offen. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s5](https://app.teamfollowup.ai/terms) |
| Realtime Voice | **MARKETING CLAIM** | „live response timing“, sofortiges Calling; keine Latenz- oder Architekturwerte. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| German Voice Quality | **NICHT VERIFIZIERT** | Kein unabhängiger deutscher Vergleichstest; Deutsch wird nicht konkret zugesichert. |
| Languages | **MARKETING CLAIM** | „30+ languages and accents“ ohne Liste/Locale- oder Qualitätsbeleg. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Agent Builder | **MARKETING CLAIM** | Builder ist sichtbar beworben, Funktionsumfang nicht dokumentiert. [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) |
| Prompt Configuration | **MARKETING CLAIM** | Voll editierbarer Prompt/Script/Personality beworben. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Visual Flow Builder | **MARKETING CLAIM** | Drag-and-connect-Workflow wird beworben; Nodes/Control Flow unbekannt. [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) |
| Knowledge Base | **NICHT VERIFIZIERT** | Keine öffentliche Produktdokumentation. |
| RAG | **NICHT VERIFIZIERT** | Keine öffentliche Produktdokumentation. |
| Tool Calling | **NICHT VERIFIZIERT** | Kein öffentliches API-/Tool-Schema. |
| Custom Functions | **NICHT VERIFIZIERT** | Keine öffentliche Entwicklerdokumentation. |
| API | **NICHT VERIFIZIERT** | Keine offizielle öffentliche API-Referenz gefunden/geöffnet. |
| Webhooks | **NICHT VERIFIZIERT** | Keine öffentliche Webhook-Dokumentation gefunden/geöffnet. |
| SIP | **NICHT VERIFIZIERT** | Carrier-Abhängigkeit ist genannt, SIP nicht. [teamfollowup-s5](https://app.teamfollowup.ai/terms) |
| Telefonnummern | **VERIFIZIERT** | Nummern werden über Drittcarrier bereitgestellt und unterliegen Carrier-/Regelvorgaben; Länder, Portierung und Auswahl offen. [teamfollowup-s5](https://app.teamfollowup.ai/terms) |
| Campaign Management | **VERIFIZIERT** | „related campaigns“ ist in den App-AGB definiert; UI-/Batch-Umfang offen. [teamfollowup-s5](https://app.teamfollowup.ai/terms) |
| Batch Calling | **NICHT VERIFIZIERT** | „Power Dialler“ ist Marketingbegriff, kein API-/Limitnachweis. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Retry Logic | **NICHT VERIFIZIERT** | Keine Regeln für No-answer, Voicemail oder Retry offenbart. |
| Lead Management | **MARKETING CLAIM** | Lead-Daten aus GHL lesen/schreiben beworben; kein eigenes Lead-System dokumentiert. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Appointment Booking | **MARKETING CLAIM** | Direktes Buchen in GHL-Kalender wird beworben; Konflikt-/Fehlerlogik offen. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Calendar Integrations | **MARKETING CLAIM** | Öffentlich nur GHL-Kalender; weitere Kalender nicht belegt. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| CRM Integrations | **MARKETING CLAIM** | Anbieter sagt: derzeit **nur** GHL. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| GoHighLevel | **MARKETING CLAIM** | Native Anbindung, bestehende Pipelines/Tags/Workflows, Rückschreiben werden beworben; keine technische GHL-Dokumentation. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) |
| Human Transfer | **MARKETING CLAIM** | Live-Transfer/Handoff in Workflow wird beworben; Ziel, Timeout, Eskalation offen. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Call Recording | **VERIFIZIERT** | Datenschutzerklärung nennt Call Audio/Recordings; UI, Retention und Region offen. [teamfollowup-s6](https://app.teamfollowup.ai/privacy) |
| Transcription | **VERIFIZIERT** | Datenschutzerklärung nennt Transkripte; Sprache/Genauigkeit/Export offen. [teamfollowup-s6](https://app.teamfollowup.ai/privacy) |
| Conversation Analytics | **MARKETING CLAIM** | Suchbare Transkripte, Zeitstempel und Outcomes beworben; Metriken/Exports offen. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Sentiment / Outcome Analysis | **MARKETING CLAIM** | Outcome-Tags und Sentiment Scoring beworben; Modell und Validierung offen. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Testing | **VERIFIZIERT** | Fünf Browser-Testminuten sind veröffentlicht; Regression/Evals nicht belegt. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| Agent Versioning | **NICHT VERIFIZIERT** | Keine Releases, Diff, Approval oder Rollback öffentlich. |
| White Label | **NICHT VERIFIZIERT** | Marketing wirbt für White-Label/Resale, AGB untersagen Resale/Sublicense außer ausdrücklich erlaubt; Plan/Vertrag ungeklärt. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s5](https://app.teamfollowup.ai/terms) |
| Agency Features | **MARKETING CLAIM** | Agency-Workflow, Monetization Playbooks und Resale beworben. [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) |
| Multi-Tenant | **MARKETING CLAIM** | Je GHL-Sub-Account eigener Agent/„no cross-contamination“; keine technische Isolation belegt. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) |
| EU Hosting | **NICHT VERIFIZIERT** | Kein Storage-/Compute-Standort publiziert. |
| GDPR Positioning | **VERIFIZIERT** | App-Policy beschreibt Controller/Processor-Rollen und DPA auf Anfrage; keine Zertifizierung/Compliance-Garantie. [teamfollowup-s6](https://app.teamfollowup.ai/privacy) |
| Pricing | **VERIFIZIERT** | USD 97/Monat nach 14 Tagen ist veröffentlicht, widerspricht aber „Free forever“ auf anderer Seite. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s4](https://app.teamfollowup.ai/signup-30-day-free-trial) |
| Usage Pricing | **NICHT VERIFIZIERT** | Keine öffentliche Overage-/Minutenpreisliste. |
| Concurrent Calls | **NICHT VERIFIZIERT** | Keine veröffentlichte Parallelitätsgrenze. |
| Rate Limits | **NICHT VERIFIZIERT** | Keine öffentliche API-/Plattformlimitdokumentation. |

## 5. UX-Muster – was sichtbar ist und was nicht

**Sichtbare Muster mit möglichem Kundennutzen:** Erstens kombiniert die Seite ein agenturbezogenes Ergebnisnarrativ (Speed-to-lead, Retention, Resale) mit einer konkreten Vier-Schritte-Reise. Das senkt das Problem „Ich habe Leads, aber keine Voice-Automation-Expertise“. Zweitens verknüpft sie Prompt-Framework und visuellen Workflow, statt Kunden mit einem leeren Prompt zu starten. Drittens stellt sie Recordings, Transcripts und Outcomes als klientenfähigen Wirkungsnachweis dar – ein relevantes Agency-UX-Muster für Transparenz und Abrechnung. Viertens hält das GHL-first-Versprechen Datenfluss und Kalender im vertrauten Arbeitskontext des Kunden, statt einen CRM-Wechsel zu verlangen. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/)

**Sichtbarkeitsgrenzen:** Öffentlich nicht einsehbar sind Dashboard-Navigation, tatsächliche Agent-/Campaign-/Workflow-Editoren, Call-History, Analytics-Ansichten, Fehlerzustände, Berechtigungen, Mandantenwechsel, Abrechnung, Test-Sandbox oder Integrations-Authentifizierung. Daher ist weder eine UI-Qualitätsbewertung noch eine Behauptung über inneres UX-Verhalten zulässig. Die privaten Beispielcalls sind auf der Landingpage verlinkt, wurden im Rahmen dieses Audits nicht als Audio analysiert; Aussagen über Natürlichkeit sind **NICHT VERIFIZIERT**.

## 6. Öffentliche technische Erkenntnisse und funktionale Zerlegung

**VERIFIZIERT:** Die App-AGB benennen Drittanbieter für Telefonie, Sprach-/Voice-Verarbeitung und Infrastruktur. Sie nennen außerdem KI-Ausgaben als Speech, Conversations, Transcripts, Summaries und Classifications. Die Privacy Policy bestätigt Call-Audio, Transkripte, Metadaten, Outcomes sowie Log-/Diagnosedaten. Das belegt jedoch **nicht** konkrete LLM-, STT-, TTS-, Carrier-, Cloud-, Framework- oder Datenbankanbieter. [teamfollowup-s5](https://app.teamfollowup.ai/terms) [teamfollowup-s6](https://app.teamfollowup.ai/privacy)

> **TECHNISCHE HYPOTHESE – funktionale, nicht interne Systemzerlegung:** Um die beworbenen Abläufe umzusetzen, benötigt ein Produkt dieser Art mindestens (1) Konto-/Abo-/Berechtigungs-Control-Plane, (2) Agenten-, Prompt-, Voice- und Flow-Konfiguration, (3) einen GHL-Connector für Lead-, Kalender-, Kontakt-, Tag- und Workflow-Aktionen, (4) Kampagnen-/Triggerlogik, (5) Carrier-/Nummern- und Call-Control, (6) einen Echtzeit-Audiopfad mit STT, Turn-/Interrupt-Erkennung, LLM/Regellogik und TTS, (7) sichere Tool-Aktionen für Buchung, Übergabe und CRM-Updates, (8) Recording-/Transkript-/Outcome-Speicher, (9) Observability, Retries und Abrechnungs-Metering sowie (10) Mandanten- und Geheimnisisolation. Diese Komponenten sind eine Funktionsableitung, keine Aussage über den tatsächlichen Team-Follow-Up-Stack.

Für einen unabhängigen EU-Nachbau sind gerade die unsichtbaren Komponenten Differenzierungs- und Risikohebel: unveränderliche Agent-Releases, testbare Flows, verbindliche Consent-/Opt-out-Gates vor jedem Call, idempotente GHL-Updates, nachvollziehbare Retry-Policies, Kostenmetering und nachweisbare Isolation. Das ist **keine finale Architekturentscheidung**, sondern eine Validierungsliste.

## 7. Datenschutz, EU-Verarbeitung, Lock-in und Risiken

Die aktuelle App-Privacy Policy (04.08.2026) beschreibt Arcandx LTD in Limassol, Zypern, als Betreiber; bei Lead- und Call-Daten agiere der Anbieter als Processor, Kunde als Controller. Sie nennt eine DPA „available on request“, Call-Aufzeichnung/-Transkription, externe Dienstleister-Kategorien und geeignete Transfermechanismen wie SCCs. [teamfollowup-s6](https://app.teamfollowup.ai/privacy) Das ist **VERIFIZIERT als Rechtsseiteninhalt**, kein unabhängiger Beweis der tatsächlichen Umsetzung.

| Dimension | Öffentlicher Stand | Bewertung |
|---|---|---|
| EU Storage | Standort/Region nicht genannt. | **NICHT VERIFIZIERT** |
| EU Inference | KI-/Voice-Provider werden nicht benannt; Daten können international verarbeitet werden. | **NICHT VERIFIZIERT** |
| Logs/Diagnostics | Erhebung wird genannt, Speicherort/Retention nicht. | **VERIFIZIERT** für Erhebung; Region/Frist **NICHT VERIFIZIERT**. [teamfollowup-s6](https://app.teamfollowup.ai/privacy) |
| Support | Support/Kommunikation genannt, Sitz/Zugriffe/Support-Region offen. | **NICHT VERIFIZIERT** |
| Subprocessors | Kategorien genannt; aktuelle Liste nur auf Anfrage. | **VERIFIZIERT** als Lücke/Prozess, Namen/Regionen **NICHT VERIFIZIERT**. [teamfollowup-s6](https://app.teamfollowup.ai/privacy) |
| Transfers | Verarbeitung außerhalb des Landes und SCC/Mechanismen erwähnt. | **VERIFIZIERT** als Policy-Aussage; konkrete Datenpfade offen. [teamfollowup-s6](https://app.teamfollowup.ai/privacy) |

Risikohinweise: Die aktuellen Terms legen Consent, Recording Disclosure, Do-not-call- und sonstige Telefonrechts-Compliance beim Kunden ab. [teamfollowup-s5](https://app.teamfollowup.ai/terms) Das entbindet einen EU-Kunden nicht von eigener Prüfung insbesondere von DSGVO, ePrivacy/UWG, nationalem Telekommunikationsrecht und AI-Transparenzpflichten. Die Terms erlauben Änderungen der Features/Limits, nennen keine SLA und erlauben bei Ende eine Löschung/Deprovisionierung von Content, Agents und Nummern; Exportfähigkeit ist Kundenpflicht. [teamfollowup-s5](https://app.teamfollowup.ai/terms) Das ist ein materielles **Vendor-Lock-in-/Business-Continuity-Risiko**.

Zusätzlich enthalten ältere Marketing-Rechtsseiten wechselnde Unternehmensbezeichnungen (Avalanche Wellness LLC, ABC INDUSTRIES LLC, Arcandx LTD) und sehr allgemeine Kurs-/Learning-Formulierungen. [teamfollowup-s7](https://teamfollowup.ai/privacy-policy) [teamfollowup-s8](https://teamfollowup.ai/data-protection) Gegenüber den aktuell datierten App-Seiten ist dies kein Nachweis eines Rechtsverstoßes, aber ein **Due-Diligence-Risiko**: Vertragspartei, DPA, TOMs, Subprozessoren, Löschfristen und Datenflüsse sollten vor Einsatz schriftlich abgeglichen werden.

## 8. Stärken, Grenzen und offene Validierung

**Stärken:** sehr klare Agenturpositionierung; GHL-first-Journey; sichtbares No-Code-/Flow-Narrativ; Test-before-paid-Hook; Calls, Transkripte und Outcomes als kundenfähiger Nachweis; dokumentierte Zuweisung der Compliance-Verantwortung. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s2](https://teamfollowup.ai/agency-agent/) [teamfollowup-s5](https://app.teamfollowup.ai/terms)

**Schwächen/Risiken:** starke GHL-Single-Integration; keine öffentlichen Entwicklerdocs/API-/SIP-Belege; unklare Preis- und Testdarstellung; White-Label-Marketing versus Standard-Resale-Verbot; fehlende EU-Residenz-/Subprozessor-/SLA-/Limits-Angaben; keine belastbare deutsche Sprachqualitäts- oder Latenzevidenz; keine sichtbare Release-/Testing-/Versionierungs-Governance.

**Offene Fragen vor jeder Beschaffung oder Wettbewerbsableitung:** (1) schriftliche Preis- und Minutenmatrix je Region/Carrier inklusive Overage, (2) zulässiger White-Label-/Resale-Plan, (3) GHL-Scopes, OAuth/Tokenhaltung, Fehler- und Idempotenzlogik, (4) Carrier, Rufnummernländer, Portierung, SIP/Transfer und Anrufgrenzen, (5) STT/TTS/LLM-Anbieter und Datenpfad, (6) Datenresidenz für Audio, Transkripte, Backups und Logs, (7) DPA/TOM/Subprocessor-Liste und Lösch-SLA, (8) Consent-/Opt-out-/Recording-Mechanik, (9) Concurrency, Rate Limits, SLA und Incident-Handling, (10) Test-, Release-, Rollback- und Exportfunktionen. Keiner dieser Punkte wurde durch diese öffentliche Recherche als erfüllt bestätigt.

### 8.1 Hypothesen für eine eigenständige bessere Kundenerfahrung

Die folgenden Punkte sind **TECHNISCHE HYPOTHESEN bzw. Produktannahmen**, keine Aussagen über interne Defizite von Team Follow Up AI und keine finale Architektur- oder Build-Entscheidung. Sie folgen aus den öffentlichen Transparenzlücken und dem klaren GHL-first-Fokus. Ihre Relevanz muss vor Umsetzung durch Kundeninterviews, rechtliche Prüfung und einen kontrollierten Benchmark belegt werden.

| Opportunity | Warum sie Kundenprobleme adressieren könnte | Customer Value / Komplexität / Differenzierung / Monetarisierung – **ANNAHME** |
|---|---|---|
| **Nachweisbarer Consent- und Call-Policy-Gate** | Die AGB delegieren Call-, Recording- und Consent-Compliance an den Kunden. Ein sichtbarer Preflight mit Rechtsgrundlage, Zeitfenster, Sperrliste, Disclosure und Audit-Trail könnte Agency-Teams Fehler vor dem Dialing erkennen lassen. | Hoch / Mittel bis hoch / Hoch für DE/EU / als Compliance- und Governance-Tier plausibel. |
| **Provider- und CRM-portable Integrationsschicht** | Der sichtbare Nutzen von GHL ist hoch, aber die Exklusivität schränkt Agenturen mit HubSpot, Salesforce, Pipedrive oder Eigen-CRM ein. Eine einheitliche, idempotente Action-Semantik würde CRM-Wechsel und Carrier-/AI-Provider-Wechsel vereinfachen. | Hoch / Hoch / Mittel bis hoch / Integrationspakete oder höhere Pläne plausibel. |
| **Versionierte Agent-Releases mit Simulation** | Öffentliche Seiten zeigen Prompt-/Flow-Editierbarkeit, nicht aber Freigabe, Diff, Tests oder Rollback. Vertriebsteams brauchen vorhersehbare Änderungen an Script, Regeln, Wissensdaten und Übergaben. | Hoch / Mittel / Hoch im B2B-Betrieb / Premium Governance-Tier plausibel. |
| **Kosten- und Ergebnistransparenz je Client** | Aufzeichnung/Outcomes adressieren bereits Reporting. Ergänzend könnten minutengenaue Carrier-, AI- und Kampagnenkosten, Erfolgsdefinitionen und Datenqualitätswarnungen Konflikte zwischen Agency und Endkunde reduzieren. | Mittel bis hoch / Mittel / Mittel / Margin-Management- und Reporting-Add-on plausibel. |
| **Deutsch-/EU-spezifische Qualitäts- und Datenkontrollen** | Die Public Sources liefern keinen Qualitätsbenchmark für deutsche Telefonie und keine verifizierte Datenresidenz. Vergleichbare Qualitäts-Evals mit Namen, Adressen, Zahlen, Dialekten und Telefonbandbreite sowie wählbare Datenpfade wären ein prüfbares Differenzierungsversprechen. | Hoch / Hoch / Hoch bei belastbarer Evidenz / Enterprise- bzw. EU-Add-on plausibel. |
| **Handover als operativer Workflow, nicht nur Transfer** | Marketing nennt Live-Transfer und GHL-Workflows. Ein sauberer Übergabeprozess könnte Erreichbarkeit, Kontextzusammenfassung, Verantwortliche, Fallback, Nachfassfrist und Rückmeldung als messbaren SLA-Prozess bündeln. | Hoch / Mittel / Mittel / Teil eines Agency-/Support-Plans plausibel. |

Für jede Opportunity wäre der entscheidende Validierungsschritt ein kleiner, kontrollierter Test mit vorab festgelegter Erfolgsmetrik: etwa Consent-Fehlerquote, Buchungsqualität statt reiner Buchungszahl, Transfer-Erreichbarkeit, CRM-Update-Fehler, Kosten pro qualifiziertem Termin und deutsche Gesprächsverständlichkeit. Solche Messungen dürfen nicht aus Landingpage-Zählern oder Sprachlisten abgeleitet werden. Besonders bei Voice muss ein Ergebnis nach Zielgruppe, Audiopfad, Region, Carrier, Prompt, Modellversion und Gesprächsszenario aufgeschlüsselt werden. Erst nach dieser Evidenz könnte ein späteres Decision Gate Build, Buy oder Hybrid pro Komponente bewerten.

## Quellenregister

| ID | Titel / Typ | URL | Geöffnet | Abruf | Evidenzinteresse und Einschränkung |
|---|---|---|---|---|---|
| teamfollowup-s1 | DIY – Produkt-/Pricing-/FAQ-Landingpage | https://teamfollowup.ai/diy/#personas | Ja | 21.10.2026 | Primärquelle für Positionierung, GHL, Testminuten, USD 97 und Marketingfeatures; keine technische Doku. |
| teamfollowup-s2 | Free AI Voice Agent For Agencies – Landingpage | https://teamfollowup.ai/agency-agent/ | Ja | 21.10.2026 | Primärquelle für Agency-Journey, Flow-Builder- und White-Label-Claims; Marketingseite. |
| teamfollowup-s3 | Öffentliche Startseite / Builder-Teaser | https://teamfollowup.ai/ | Ja | 21.10.2026 | Sichtbarer Prompt-Builder-Teaser und Login, keine eingeloggte Produktansicht. |
| teamfollowup-s4 | Öffentliche Account-Erstellung | https://app.teamfollowup.ai/signup-30-day-free-trial | Ja | 21.10.2026 | Signup-Felder, Free-forever-/Onboarding-Behauptung; widerspricht teils s1. |
| teamfollowup-s5 | Terms & Conditions, Arcandx LTD, 09.06.2026 | https://app.teamfollowup.ai/terms | Ja | 21.10.2026 | Stärkste Quelle für Serviceumfang, Drittanbieter, Call-Compliance, Content/Nummern, Limits und Vertrag. |
| teamfollowup-s6 | Privacy Policy, Arcandx LTD, 04.08.2026 | https://app.teamfollowup.ai/privacy | Ja | 21.10.2026 | Stärkste Quelle für Controller/Processor, Call-Daten, Logs, Retention, Transfers und Subprozessor-Kategorien. |
| teamfollowup-s7 | Ältere Privacy Policy | https://teamfollowup.ai/privacy-policy | Ja | 21.10.2026 | Dokumentiert widersprüchliche Unternehmens-/Templateangaben; ohne Datumsangabe, daher nicht Grundlage aktueller Datenschutzbewertung. |
| teamfollowup-s8 | Data Protection Policy | https://teamfollowup.ai/data-protection | Ja | 21.10.2026 | Generische DSGVO-/Sicherheitszusagen; keine konkreten Plattformregionen oder Subprozessoren. |
| teamfollowup-s9 | Ältere Terms & Conditions | https://teamfollowup.ai/terms-and-conditions | Ja | 21.10.2026 | Generische ältere Vertragsseite; wegen Kurs-/Commerce-Sprache nur als Dokumentenkonflikt genutzt. |

**Recherchelücke:** Die aktive Suche nach einer offiziellen Team-Follow-Up-API-, Help-Center-, SIP- oder Entwicklerdokumentation ergab keine öffentlich zu öffnende Team-Follow-Up-Primärquelle. Der Abruf von `https://teamfollowup.ai/sitemap.xml` lieferte keine extrahierbaren Inhalte. Das ist keine Aussage, dass solche Unterlagen nicht existieren; sie sind für diesen Audit **NICHT VERIFIZIERT**.
