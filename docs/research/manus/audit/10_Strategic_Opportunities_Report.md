# 10 – Strategic Opportunities Report

**Stand: 21.10.2026.** **Fazit:** Nachweisbare deutsche Entity-/Telefonqualität, sichere Business-Aktionen und verständlicher Agency-Betrieb sind plausiblere Differenzierungsachsen als ein weiteres generisches Call–Qualify–Book-Versprechen.

**Confidence:** mittel für Problemhypothesen, niedrig für Zahlungsbereitschaft/Marktgröße/dauerhaften Moat. Alle Bewertungen sind **Produkt-/Geschäftsannahmen**, keine gemessenen Marktanteile oder Beweise fehlender Wettbewerberfunktionen.

## 1. Opportunity-Matrix

Ordinal 1–5: Value, Komplexität, potenzieller Vorteil, Monetarisierung. Hohe Komplexität ist Aufwand. Keine mathematische Gesamtpunktzahl suggeriert objektive Rangfolge.

| Opportunity | Value | Komplexität | Vorteil | Monetarisierung | Kundennutzen / Angebotshypothese | Validierung |
|---|---:|---:|---:|---:|---|---|
| Deutsches Entity-QA | 5 | 4 | 4 | 4 | Namen/Nummern/Adressen/Termine richtig bestätigen; QA-Tier | kritische Feldfehler und Task-Erfolg auf PSTN |
| Consent-/Call-Preflight | 5 | 4 | 4 | 4 | erklärt erlaubte/blockierte Calls; Governance-Tier | Jurist + Agency-Workflows, Fehlfreigaben |
| Releases/Diff/Simulation/Rollback | 5 | 3 | 3 | 4 | Änderungen nachvollziehbar und getestet | Regression/Reviewzeit/Releasefehler |
| Sichere CRM-/Calendar-Actions | 5 | 4 | 4 | 4 | bestätigte Termine statt bloßer Dialogversprechen | Race/Timeout/Duplicate/Reconciliation |
| Agency-Multi-Client-Cockpit | 5 | 4 | 3 | 5 | Rechte, Ausfälle, Kosten und Outcome je Client | Delegations-/Supportpilot und Interviews |
| White Label mit klaren Rechten | 4 | 3 | 3 | 5 | Branding/Domain/Onboarding/Rebilling transparent | OEMvertrag + echter Resellerverkauf |
| Outcome-/Margin-Reporting | 4 | 3 | 3 | 4 | Kosten pro zulässigem qualifiziertem Ergebnis | Rechnungsabgleich/human-audited Outcome |
| Vollständiges Human Handover | 5 | 3 | 3 | 4 | Kontext/Annahme/Timeout/Nachfassfall | Warmtransfer/No-answer/Lösungsquote |
| Dokumentierter EU-Datenpfad | 5 | 4 | 4 | 4 | erklärt Inferenz/Logs/Support/Backups statt EU-Logo | Vertrag/Konfiguration/Failoverbeleg |
| Conversation Optimization | 4 | 4 | 3 | 4 | versionierte Experimente nach echten Outcomes | gepaarter/A-B-Test mit Sample/CI |
| Automotive-/Fleet-Templates | 4 | 4 | 4 | 4 | Kennzeichen/Schadenabläufe/Partnerübergabe | Fachpilot + sensitive Daten-/Rechtsprüfung |
| Inbound Customer-Support-Triage | 4 | 3 | 2 | 4 | Intake/Status/Weiterleitung | Lösungsquote/Fehltransfer/API-Ausfall |

## 2. Evidenz und Wettbewerb

Team Follow Up zeigt starken Agency-/GHL-Fokus, öffentlich aber begrenzte Qualitäts-/Release-/Preis-/Datenpfadtransparenz. Dieselben Kundenprobleme nachvollziehbarer zu lösen ist eine Produktchance, nicht ein Beweis interner Defizite. [teamfollowup-s1](https://teamfollowup.ai/diy/#personas) [teamfollowup-s5](https://app.teamfollowup.ai/terms) [teamfollowup-s6](https://app.teamfollowup.ai/privacy)

Testing, Governance und EU-Angebote sind bereits Wettbewerb: ElevenLabs dokumentiert Agent Tests und Flows; Parloa bewirbt Simulation, Versionen und Monitoring. Der Vorteil müsste in **deutscher/Agency-spezifischer Durchführung und Beweisführung** liegen, nicht in „wir erfinden Testing“. [el-testing](https://elevenlabs.io/docs/eleven-agents/customization/agent-testing) [el-workflows](https://elevenlabs.io/docs/eleven-agents/customization/agent-workflows) [Parloa](../research/parloa.md)

Providerunabhängigkeit reduziert unsere Wechselkosten, ist allein kein Kunden-Moat. Wiederholbare Geschäftsergebnisse, verlässliche Integration, Service und Vertrauen können einen Vorteil tragen. Exklusives Cloning kann dagegen Rechte-/Vendorbindung erhöhen.

## 3. Eigenständige UX-Muster

**Onboarding:** Gesprächsziel, zulässiger Kontaktgrund, Region, CRM/Kalender und Handover vor Prompts klären. Vorlagen mit sichtbaren Scopes/Annahmen statt Blankprompt. Ein schneller Test ist nützlich; „sofort produktionsbereit“ ohne Preflight kein gutes Ziel.

**Agent Builder:** Persönlichkeit/Stimme von Policy/Tools trennen. Preview zeigt Aussprache, Ausnahmen und geschätzte Gebühren. Publishing erzeugt Release mit Tests/Diff und fachlicher Freigabe. Laufende Calls verwenden eingefrorene Konfiguration.

**Campaign Builder:** blockierte Kontakte, Nachweisgrenzen, Zeitzonen, Budgets, Concurrency und Retrydefinition erklären. History unterscheidet „nicht gewählt wegen Sperre“, „Callergebnis unbekannt“, „CRM-Nacharbeit offen“ und „Termin bestätigt“.

**Operations:** Call-ID/Release/Toolstatus/Usagequelle zusammen anzeigen; keine Sentimentzahl als Conversion verkaufen. Tenantwechsel, Delegation und Support müssen klar begrenzt sein. Diese UX-Vorschläge sind eigene Hypothesen, keine Kopien oder Beobachtungen nicht einsehbarer Dashboards.

## 4. Erstes Segment und Gutachtery24

Ein enger, zulässiger Inbound-Service-/Terminprozess ist eine **Einstiegshypothese** mit weniger Outreach-Unsicherheit als breite kalte Outbound-Akquise; nicht automatisch datenschutzfrei. Outbound-Speed-to-lead nur für nachweislich zulässige Kontaktanlässe prüfen. [compliance-03](https://www.gesetze-im-internet.de/uwg_2004/__7.html)

Gutachtery24 bleibt späterer Integrationsfall. Automotive/Fleet können Templates erhalten, dürfen generische Kontakte/Consent/Calendar/Handover nicht ersetzen. Unfallgespräche können Gesundheitsdaten enthalten; keine ungeprüften medizinischen, Versicherungs- oder Haftungsentscheidungen. [compliance-01](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng)

## 5. Monetarisierung und Widerlegung

Agency-Grundplan plus nachvollziehbarer Verbrauch und Governance-/Integrationspakete sind Hypothesen. Zahlungsbereitschaft, CAC/LTV und Churn wurden nicht gemessen. „Pro Termin“ setzt verifizierte Definition von rechtmäßigem, passendem und bestätigtem Termin voraus; sonst entsteht Anreiz zu schlechter Qualifikation/aggressivem Calling.

Zuerst deutsche Entity-/Toolqualität, legaler Preflight und Agency-Operations zusammen in Interviews/einem engen Pilot prüfen. Die Priorität ändert sich, wenn Kunden keine Governance bezahlen, bestehende Anbieter diese Anforderungen günstiger erfüllen, Inbound klar bevorzugt wird oder EU-Verträge die Marge aufzehren. Keine finale Produktroadmap aus dieser Matrix ableiten.
