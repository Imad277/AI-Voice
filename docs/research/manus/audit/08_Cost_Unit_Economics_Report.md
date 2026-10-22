# 08 – Cost & Unit Economics Report

**Preis-/Quellenstand: 21.10.2026. Originalwährung USD, keine FX-Umrechnung.** **Fazit:** Die drei Kandidatenstacks lassen sich als nachvollziehbare Gebührenmodelle berechnen, aber nicht als verifizierte EU-/Deutschland-Produktionsangebote. Verbrauch, Zielroute, Cache, Quoten, Standby-/HA-/Personalkosten und Enterpriseverträge entscheiden über echte Profitabilität.

**Confidence:** mittel für gelesene Listenpreise; niedrig bis mittel für Plan-/Regionanwendbarkeit; niedrig für tatsächlich gemessenen Verbrauch und Vollkosten. Die Tabellen sind ausschließlich **offizielle Unit-Preise × explizite ANNAHMEN**, kein Qualitätstest und kein Angebot. Quality/Balanced/Cost sind Optimierungsziele, keine bewiesene Rangfolge.

## 1. Drei konkrete, topologisch konsistente Kandidaten

| Stack | Telefonie / Medien | STT | Text-LLM | TTS | Voice Compute |
|---|---|---|---|---|---|
| A – Quality Optimized | Twilio Programmable Voice DE + bidirektionale Media Streams | Deepgram Flux multilingual | OpenAI gpt-6.1-sol | ElevenLabs multilingual_v2, veröffentlichte 0,08 USD/1.000 Zeichen | Pipecat Cloud agent-1x |
| B – Balanced | derselbe Twilio/Media-Streams-Pfad | Deepgram Nova-3 multilingual | OpenAI gpt-6-luna | Cartesia Sonic3.6 Scale, 299 USD/8M Credits + Overage | Pipecat Cloud agent-1x |
| C – Cost Optimized | derselbe Twilio/Media-Streams-Pfad | Deepgram Nova-3 multilingual | OpenAI gpt-6-luna | ElevenLabs streamingfähige Flash/Turbo-Linie, 0,04 USD/1.000 Zeichen | Pipecat selfhost, Compute-Budgetannahme |

Pipecat dokumentiert Twilio-WebSockettransporte. Diese Vergleichsrechnung wählt bewusst denselben Carrier-/Medienpfad; **Programmable-Voice-Preise sind keine Elastic-SIP-/LiveKit-SIP-Raten**. Ein alternativer LiveKit-SIP-Stack benötigt eigene passende Carrier-/SIPfees. Die Wahl für diese Kostenrechnung ist keine Runtimeentscheidung. [pipecat-P04](https://docs.pipecat.ai/pipecat/learn/transports) [pipecat-P10](https://www.daily.co/pricing/pipecat-cloud/) [twilio-streams](https://www.twilio.com/docs/voice/media-streams) [twilio-pricing](https://www.twilio.com/en-us/voice/pricing/de)

A verwendet nicht ungeprüft v4 am TTS-WebSocket: ElevenLabs dokumentiert unterschiedliche Modell-/Endpointunterstützung. Streaming-/Qualitäts-/EU-Parität der konkreten Stimmen bleibt Benchmark- und Vertragsgegenstand. [el-ws](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts) [el-apiprice](https://elevenlabs.io/pricing/api)

## 2. Offizielle Preisbasis

Alle Zeilen am **21.10.2026** abgerufen. Globale USD-Listenpreise soweit die Quelle keine regionale Rate ausweist; Steuer und individuelle Verpflichtungen nicht enthalten.

| Komponente | Unit-Preis | Region / Plan / Einschränkung | Quelle |
|---|---|---|---|
| Twilio Outbound DE | Festnetz0,0283 USD/min; Mobil From EEA0,0420 USD/min | passende EEA-Origination nur ANNAHME; andere Mobilrouten bis0,3763 USD/min | [twilio-pricing](https://www.twilio.com/en-us/voice/pricing/de) |
| Twilio Media Streams | 0,0044 USD/Callminute | tatsächliches Metering/Region bestätigen | [twilio-pricing](https://www.twilio.com/en-us/voice/pricing/de) |
| Twilio lokale Nummer | 1,35 USD/Monat | Menge/DE KYC nicht Bestandteil des Nachweises | [twilio-pricing](https://www.twilio.com/en-us/voice/pricing/de) |
| Deepgram Flux multilingual | 0,0078 USD/Audiominute | PAYG; Region/MIPoptout/Promo-/Quota erneut prüfen | [deepgram.pricing](https://deepgram.com/pricing) |
| Deepgram Nova-3 multilingual | 0,0058 USD/Audiominute | PAYG, ein Audiokanal; Addons extra | [deepgram.pricing](https://deepgram.com/pricing) |
| OpenAI sol | Input2 / cached0,10 / Output10 USD/M Texttokens | Standard short context; eligible regional processing ggf.+10% | [openai-08](https://developers.openai.com/api/docs/pricing) |
| OpenAI luna | Input0,10 / cached0,01 / Output0,50 USD/M Texttokens | Standard short context; regionale Eligibility prüfen | [openai-08](https://developers.openai.com/api/docs/pricing) |
| ElevenLabs multilingual_v2 | 0,08 USD/1.000 Zeichen | veröffentlichte APIusagebasis; Kontingente/Enterprise-Minimum offen | [el-apiprice](https://elevenlabs.io/pricing/api) |
| ElevenLabs Flash/Turbo | 0,04 USD/1.000 Zeichen | konkrete Modell-/Voice-/Planparität vor Einkauf | [el-apiprice](https://elevenlabs.io/pricing/api) |
| Cartesia Sonic Scale | 299 USD/Monat inkl.8M Credits; Overage38 USD/M Credits | ca.1 Credit/Zeichen als Verbrauchsannahme; 15 parallele TTSrequests im Plan | [cartesia.pricing](https://www.cartesia.ai/pricing) |
| Pipecat Cloud agent-1x | 0,01 USD/aktive Minute; reserviert0,0005 USD/Minute | 0,5vCPU/1GB; Modell-/Twiliofees extra; ausreichend CPU NICHT VERIFIZIERT | [pipecat-P10](https://www.daily.co/pricing/pipecat-cloud/) |
| Twilio Recording | 0,0025 USD/aufgezeichnete Minute | nur zulässige Aufnahme, getrennt aktivieren | [twilio-pricing](https://www.twilio.com/en-us/voice/pricing/de) |
| Twilio Recording Storage | 0,0005 USD/aufgezeichnete Minute/Monat | Retention und steady-state Bestandsmenge | [twilio-pricing](https://www.twilio.com/en-us/voice/pricing/de) |

Deepgram-Keyterm-Streaming kostet optional0,0013 USD/min zusätzlich; Redaction/Diarization weitere Zuschläge. Keine Discounts, Freicredits oder kurzfristigen Promotions werden zusätzlich zur angeführten Rate modelliert. Keine nicht veröffentlichte EU-/OEMgebühr wird als null bestätigt. [deepgram.pricing](https://deepgram.com/pricing)

## 3. Verbrauchs- und Betriebsannahmen

**M** ist die monatliche produktive verbundene Gesprächszeit. Zusätzlich angenommen: 15% verbundene Zusatzzeit für Voicemail/erneute Attempts/technische Wiederholung. Das ist **keine Annahme, dass jedes erfolglose Klingeln vom Carrier oder STT voll berechnet wird**. Im Basismodell entstehen 1,15×M Media-/STT-/Runtime-Minuten und weitere0,05×M Carrier-Transferlegminuten. Das Modell bewertet noch nicht die Anzahl nicht verbundener Callversuche oder pro-call Gebühren.

| Parameter | Basisannahme | Sensitivität / offene Messung |
|---|---|---|
| Zielmix | 70% Festnetz / 30% Mobil, günstigere From-EEA-Kategorie | Mobil0–100%; falsche Kategorie großer Preishebel |
| STT | ein voller incoming Audiokanal während1,15×M, inklusive Stille | keine TTS-Sprechanteilreduktion für STT; Multi-channel extra |
| Dialog-LLM | 3 Turns/min, durchschnittlich2.000 wiederholte Inputtokens/Turn =6.000/min;300 Outputtokens/min | Kontext wächst; Tool-/RAGpayload und speculative Turns erhöhen Verbrauch |
| Cache | 75% Inputtokens zum cached Tarif | keine Garantie;0%/50%/75% messen, Mindestprefix/Validity beachten |
| TTS | 45% Agentsprechanteil ×900 Zeichen/Sprechminute =405 Zeichen/Gesprächsminute | Aussprache/Styles/Abbruchaudio können billable Verbrauch ändern |
| Extra-Mediazeit | kein zusätzliches LLM-/TTSvolumen hierfür im Basismodell | konservative Vereinfachung, Voicemailansagen/Retrydialogs erhöhen Kosten |
| Postcall Analytics | ein Lauf/5-Minuten-Call,2.000 Input-/300 Outputtokens, luna ohne Cache | kein zweiter STT-Lauf, vorhandenes Transcript verwenden |
| Recording | nur50% der1,15×M Media-Minuten;3 Monate Retention | Recording ist kein erlaubter Produktdefault |
| Storage steady state |3 Monatskohorten aufgezeichneter Minuten gespeichert | Anlauf billiger; Retention/Mehrfachkopien/Exporte extra |
| Eigene Trace-/Egressreserve |0,0007 USD/M-Gesprächsminute | reine Budgetannahme, kein offizieller Speicher-/Egresstarif |
| Nummern |10/50/200 bei10k/100k/1M Minuten | keine Aussage über verfügbare Nummern oder Mandanten |
| Shared Control-Plane Infra |500/1.000/5.000 USD/Monat je Szenario | Budgetannahme für DB/API/Jobs/Monitoring, kein geprüfter HAplan |
| C Selfhost Runtime |0,002 USD/Media-Minute +300/1.000/5.000 USD/Monat Capacityreserve | Budgetannahme, keine offizielle Pipecatfee oder bewiesene günstige HA |

Cloud-Standbyreservation ist im Basismodell nicht gebucht, was Coldstart-/SLO-Risiko bedeutet. Vier konstant reservierte agent-1x-Replicas in30 Tagen verursachen beispielhaft **86,40 USD/Monat** reservierte Laufzeit zusätzlich gemäß angenommener additiver Anwendung; konkrete Aktiv-/Reservierungssemantik vor Kauf bestätigen. Kosten für höheres Profil/SLA/EUEnterprise sind offen.

## 4. Formeln und vollständige Szenarien

```text
Carrier = M × (0,7×0,0283 +0,3×0,0420) × (1,15+0,05)
Media Bridge = M×1,15×0,0044
STT = M×1,15×STT-Preis pro Audiominute
LLM = M × (6.000×[(1−0,75)×Inputpreis+0,75×Cachepreis] +300×Outputpreis)/1.000.000
TTS A/C = M×405×Preis_pro_1.000_Zeichen/1.000
TTS B = 299 + max(0,M×405−8.000.000)×38/1.000.000
Analytics = (M/5)×(2.000×0,10+300×0,50)/1.000.000
Recording+Storage = M×1,15×0,5×(0,0025+3×0,0005)
```

**Wichtig:** Bei Cartesia steht38 USD **pro Million Credits**, nicht38 USD pro Credit. Bei10k sind4,05M Credits im Scaleplan enthalten; bei100k sind40,5M Credits, davon32,5M Overage. Keine Discounts bei1M angenommen. Kein USD/EUR-Mix.

### Szenarioübersicht (USD/Monat, gerundet)

| Produktive Minuten | Stack | Fees + variable Budgetreserven | Runtimekapazität (ANNAHME) | Shared Infra (ANNAHME) | Budgetsubtotal, kein Voll-COGS | USD/min subtotal |
|---:|---|---:|---:|---:|---:|---:|
| 10,000 | A_Quality | 1,076.92 | 0.00 | 500.00 | 1,576.92 | 0.15769 |
| 10,000 | B_Balanced | 967.87 | 0.00 | 500.00 | 1,467.87 | 0.14679 |
| 10,000 | C_Cost | 738.87 | 300.00 | 500.00 | 1,538.87 | 0.15389 |
| 100,000 | A_Quality | 10,701.70 | 0.00 | 1,000.00 | 11,701.70 | 0.11702 |
| 100,000 | B_Balanced | 8,155.20 | 0.00 | 1,000.00 | 9,155.20 | 0.09155 |
| 100,000 | C_Cost | 7,321.20 | 1,000.00 | 1,000.00 | 9,321.20 | 0.09321 |
| 1,000,000 | A_Quality | 106,612.00 | 0.00 | 5,000.00 | 111,612.00 | 0.11161 |
| 1,000,000 | B_Balanced | 81,192.00 | 0.00 | 5,000.00 | 86,192.00 | 0.08619 |
| 1,000,000 | C_Cost | 72,807.00 | 5,000.00 | 5,000.00 | 82,807.00 | 0.08281 |

### Komponenten bei 100.000 produktiven Minuten (USD/Monat)

| Komponente | A Quality | B Balanced | C Cost |
|---|---:|---:|---:|
| telephony_usd | 3,889.20 | 3,889.20 | 3,889.20 |
| media_streams_usd | 506.00 | 506.00 | 506.00 |
| stt_usd | 897.00 | 667.00 | 667.00 |
| llm_usd | 645.00 | 34.50 | 34.50 |
| tts_usd | 3,240.00 | 1,534.00 | 1,620.00 |
| runtime_variable_usd | 1,150.00 | 1,150.00 | 230.00 |
| recording_usd | 143.75 | 143.75 | 143.75 |
| recording_storage_usd | 86.25 | 86.25 | 86.25 |
| postcall_analytics_usd | 7.00 | 7.00 | 7.00 |
| trace_egress_budget_usd | 70.00 | 70.00 | 70.00 |
| numbers_usd | 67.50 | 67.50 | 67.50 |
| runtime_fixed_budget_usd | 0.00 | 0.00 | 1,000.00 |
| shared_infra_budget_usd | 1,000.00 | 1,000.00 | 1,000.00 |
| budget_subtotal_usd | 11,701.70 | 9,155.20 | 9,321.20 |

[Cost_Model.csv](Cost_Model.csv) enthält alle neun Szenarien mit Komponenten, Nummern-, Infra-/Runtimebudgets, Summen und Währung. [Cost_Model_Assumptions.json](Cost_Model_Assumptions.json) enthält numerische Unit-Preise, Verbrauch, Stackdefinitionen, Quellen/Datum und Formeln. Der lokale Rechenprüfer nutzt Dezimalarithmetik und prüft Summen sowie Planoverage.

Die ausgewiesene Gebührenbasis enthält teilweise angenommene Reserven; auch sie ist kein rein verifizierter Preis. Der erweiterte Budgetsubtotal enthält zusätzliche angenommene Infrastrukturkapazität, **nicht** vollständige COGS oder Betriebskosten. Enterprise-EUverträge, OEM, Support/Personal, Steuern, Zahlungsgebühren, RAG/Embeddings/Parser, Dial-/AMD-/DNCfees, weitere Speicherung/Backups, juristische Kosten und Entwicklung sind offen. Unbekannt wird nicht als kostenlos behandelt.

## 5. Sensitivität und alternative Runtime-/Native-Pfade

- Mobil100% statt30% steigert Carrierkosten um0,011508 USD/M-Minute bei gleicher From-EEA-Annahme. Wird für30% Mobil statt0,0420 die0,3763-Route berechnet, steigt der Betrag um **0,120348 USD/M-Minute**:120.348 USD zusätzlich bei1M. Die Route kann wichtiger als der LLM sein.
- Ohne75%-Cache kostet sol bei gleichem Input/Output0,015 statt0,00645 USD/M-Minute; Mehrkosten8.550 USD bei1M. Bei luna0,00075 statt0,000345; Mehrkosten405 USD.
- TTS405 Zeichen/min ist keine Modellkonstante.60% statt45% Sprechanteil erhöht A/C um33,3%; Bändert den absoluten Overagebetrag und Planbreakpoints.
- Keyterm-Addon bei1,15×M erhöht um0,001495 USD/M-Minute. Längere Prompts, RAG/Tools, Barge-in-generiertes aber verworfenes Audio und spekulative LLM-Aufrufe zusätzlich messen.
- Monatliche Minuten gewährleisten keine Capacity: Cartesia-TTS-, Deepgram-Stream- und Cloudworkerlimits können Enterprise-/höhere Pläne erfordern. Ein günstiger9-Szenarienwert kann deshalb praktisch nicht kaufbar sein.

**LiveKit alternativ:** Ship ab50 USD/5k Sessionmin, danach0,01; zusätzlicher Drittanbieter-SIPoverage0,004/min nach5k, Scale ab500 USD/50k, danach Session0,01 und SIP0,003. Recording/Events/Inferenz extra. Carrier und ggf. WebRTC/Transferressourcen separat. Diese Gebühren nicht im Pipecat/Media-Streams-Basismodell doppelt addieren. [livekit.pricing](https://livekit.com/pricing) [livekit.billing](https://docs.livekit.io/deploy/admin/billing/)

**Native S2S:** separate Formel `Audioinputtokens×Rate + Audiooutputtokens×Rate + Textinput/cache/output + Carrier/Runtime/Storage`. Nicht STT und TTS der Kaskade zusätzlich berechnen. OpenAI Realtime2.1-mini listet10/20 USD proM Audioinput/outputtokens; Vollmodell32/64, Texttokens separat. GPT-Live1 listet0,05 USD/min, Backend/Tools extra. Google Live nennt Audio-/Textpreise mit eigener Token-Minutenapproximation. Ohne gemessene bidirektionale Tokenraten ist kein valider all-in Minutenvergleich möglich. [openai-08](https://developers.openai.com/api/docs/pricing) [Google-Dossier](../research/google.md)

## 6. Marge, Pricing und Ergebnisökonomie

Gross Margin = `(Nettoerlös−COGS)/Nettoerlös`; Markup = `(Preis−Kosten)/Kosten`.70% Gross Margin verlangt Preis=`COGS/0,30`, nicht`COGS×1,70`. Ein Verkaufspreisvorschlag bleibt **ANNAHME**, bis vollständige Carrier-/EU-/OEM-/Supportkosten und Kundenpreisbereitschaft vorliegen.

Als reine Formelillustration: bei gemessenen vollständigen COGS0,10 USD/min wären für70% Marge0,3333 USD/min netto erforderlich. Das ist **kein empfohlener aktueller Produktpreis**. Fixkostenabdeckung/Breakeven braucht Deckungsbeitrag×Volumen gegenüber tatsächlichen Fixkosten; Produktentwicklung, Vertrieb und Finanzierung sind damit nicht bezahlt.

Die relevante Geschäftsmetrik lautet zusätzlich: Gesamtkampagnenkosten / zulässige, human-auditierte qualifizierte und bestätigte Ergebnisse. Buchungsmenge allein verschleiert falsch erkannte Daten, unerlaubte Outreachversuche und fehlgeschlagene Termine.

## 7. Vor Kostenfreigabe zwingend messen

Zielrouten/Origination, reale Caller-/Transfer-/Attemptzeit, Tokens/Cache/contextgrowth, Speechanteil/Zeichen, gebilltes verworfenes Audio, Quoten/Capacity, Number/KYC/OEM/EU-Verträge, Retention und Rechnungskorrekturen. Quellen-/Preisstand bei Vertragsschluss neu erfassen. Die drei Stacks bleiben Vergleichskandidaten, keine endgültige Architektur.
