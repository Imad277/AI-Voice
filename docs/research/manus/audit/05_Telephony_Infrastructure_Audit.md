# 05 – Telephony & Infrastructure Audit

**Stand / Quellenabruf: 21.10.2026.** **Fazit:** Twilio und Telnyx sind API-/Medienpfad-Kandidaten; deutsche SIP-Anbieter können eine lokale Nummern-/Carrierbasis liefern, sind aber nicht automatisch CPaaS, automatisierter Dialer oder erlaubte Wholesale-Infrastruktur. Der Gate muss **Interoperabilität, Route, KYC, Resale-/Automation-Recht und den vollständigen Datenpfad** gemeinsam prüfen.

**Confidence:** mittel bis hoch für dokumentierte Funktionen; niedrig bis mittel für konkrete deutsche Routen, Vertragsrechte und Produktionsqualität. Keine Portierung, Anmeldung, Testanrufe, Anbieteranfragen oder Netzwerktests wurden durchgeführt.

## 1. Carrier-Vergleich

| Anbieter | SIP/PSTN / Inbound / Outbound | Nummern / Portierung / Caller ID | API / Events / Audio / Recording | Kapazität / EU / Preisgrenze |
|---|---|---|---|---|
| Twilio | Programmable Voice und Elastic SIP Trunking; In-/Outbound dokumentiert | DE Nummernangebot, konkrete KYC-/Portierungslage nicht vollständig geöffnet; Porting-API-Quelle belegt US, nicht DE | REST/TwiML/Webhooks, bidirektionale Media Streams auch IE1; ein bidir Stream je Call; Recording steuerbar | CPS und Concurrency getrennt; IE1-Ausnahmen; keine Garantie für sämtliche Daten in Region |
| Telnyx | SIP, Call Control, bidirektionales WS/RTP-Audio | DE Nummern/Portingdocs, lokale Nachweise; Prozess gesondert prüfen | API/Webhooks, Streaming, Recording; unterschiedliche Fee-Primitives | EU API/Voice-Anchors/optionale DE at-rest; konkrete DE Ratedeck/CPS/SLA offen |
| sipgate | deutsche SIP-Trunks; REST/Push und zusätzlich Flow-Angebot | Nummern/Porting/Caller-ID planabhängig prüfen | Call-Ereignisse, DTMF/Transfer/Recording; Flow Voicebotclaim vs klassischer SIP-Pfad | Trunkkapazitäten dokumentiert; gewerbliche Weitergabe sipgate.io ohne Zustimmung verboten |
| easybell | deutsche SIP-Trunks, TLS/SRTP | Nummern/Portingkosten in Preisliste; Prozessseite nicht extrahierbar | Carrierpfad; programmatische Call-/Media-API nicht verifiziert | 2–1.000 Kanäle je Angebot; Flatrate Maschine-zu-Mensch/Callcenter eingeschränkt; Reselling genehmigungspflichtig |
| Placetel | Cloud-PBX; SIP-Trunkseite nicht extrahierbar | DE Nummern/PBX-Kontext; Wholesale-/Portingdetails offen | REST v2 und Notify/XML-Call-Control; externe vollwertige Medienkopplung nicht belegt | Seat-/AI-Tarif nicht gleich Carrier-Minutentarif; AI-EU-Pfad/OEM/CPS offen |
| Telekom CompanyFlex | SIP-PBX/NGN-/IMS-Anbindung, externe PBX/SBC nötig | DDI/Caller-ID-Regeln; Clip no screening Option | 1TR119-Spezifikation; keine belegte generische Call-Control-/Media-API | zwei Gespräche inklusive, bis 998 extra beworben; Nummern-/Tarifpaket kein isolierter Trunkpreis |

Alle sechs Dossiers mit den geöffneten Preis-, Vertrags- und technischen Quellen: [Twilio](../research/twilio.md), [Telnyx](../research/telnyx.md), [sipgate](../research/sipgate.md), [easybell](../research/easybell.md), [Placetel](../research/placetel.md), [Telekom](../research/telekom.md).

## 2. Preise nicht auf eine globale „Minute“ reduzieren

| Anbieter / Produkt | Veröffentlichte Originaleinheit, Abruf 21.10.2026 | Einschränkung |
|---|---|---|
| Twilio Programmable Voice DE | Festnetz Outbound 0,0283 USD/min; Mobil From EEA 0,0420 USD/min; andere Mobilrouten laut Details bis 0,3763 USD/min; Inbound 0,0100 USD/min; lokale Nummer 1,35 USD/Monat | konkrete Herkunft/Route bestätigen; nicht als SIP-Trunkpreis ausgeben |
| Twilio Zusatzkomponenten | Media Streams 0,0044 USD/min; Recording 0,0025 USD/min; Storage 0,0005 USD/aufgezeichnete Minute/Monat; SIP Interface 0,004 USD/min; Refer 0,10 USD/Ereignis | additiv nur im tatsächlich gewählten Pfad; Conversation Relay 0,07 USD/min ist andere Transport-/Speechleistung |
| Telnyx Voice API | Call-Control 0,002 USD/min zusätzlich SIP; WS Media Streaming 0,0035 USD/min; Recording 0,002 USD/min | deutsche Zielrate nicht gelesen/verifiziert; globale SIP-ab-Rate kein DE Tarif |
| sipgate Trunking | 2/10/50: 9,95/16,77/41,98 EUR/Monat laut geöffneter Seite | Test-/Nullpreis-Konflikt und Nutzungsrechte prüfen; Minuten separat |
| easybell Volume | Mindestumsatz 250/500/1.000 EUR/Monat je Volume-Tier | Flatrate-Einschränkungen nicht durch Volumeangebot automatisch aufgehoben; AI-Outbound schriftlich zulassen |
| Placetel AI | Grow 750 min: 69/79 EUR/Monat; Professional 1.500 min: 129/149; Enterprise 4.000 min: 359/399; exkl. MwSt.; längere Bindung vs monatlich | fertiges AI-Produkt, nicht DIY Carrier. Overage 0,19 EUR/min; Nummer/Transfers extra |
| Telekom Optionen | Callrouting 4,95 EUR/Monat/Trunk; Clip no screening 9,95 EUR/Monat/Trunk, netto | beworbenes Paket ab 54,95 EUR enthält weitere Leistungen; Zusatzkanäle/isolierter Tarif offen |

[twilio-pricing](https://www.twilio.com/en-us/voice/pricing/de) sowie die oben verlinkten Dossiers belegen die Angaben. Deutsche Telefonnummern, regulatorische Voraussetzungen, Portingdauer, Abrechnungsrundung, Mobilmix, Zusatzlegs, nicht erreichte Calls und vertragliche Aufpreise sind vor Kalkulation des echten Produkts erneut festzulegen. Es wird kein FX-Kurs unterstellt.

## 3. Kompatibilität und deutscher Betrieb

**TECHNISCHE HYPOTHESE:** Ein provideragnostischer Carrieradapter sollte Callstart/Status/Transfer/Abbruch und Nummernzuordnung fachlich normalisieren. SIP standardisiert Signalisierung, aber nicht KYC, API-Signaturen, Fehlerzustände, Tarifzonen, Nummernportierung, Events oder Audioformate. Bei registrierungsbasierten Trunks ist relevant, dass LiveKit SIP kein SIP REGISTER unterstützt: ein zusätzlicher SBC/PBX-Pfad könnte nötig werden. Dies muss im vorgesehenen Carrier-/Runtimepaar praktisch geprüft werden. [livekit.docs.telephony](https://docs.livekit.io/telephony/)

Carrier-WebSocket und SIP/RTP sind verschiedene Integrationstopologien. Der Kostenstack in Bericht 08 verwendet **Twilio Programmable Voice → Media Streams → Pipecat**, nicht die gleichen DE-Preise als angeblichen LiveKit-/Elastic-SIP-Tarif. Für einen LiveKit-SIP-Stack wären passende origination/termination/interface Gebühren gesondert zu ermitteln. [twilio-streams](https://www.twilio.com/docs/voice/media-streams) [twilio-sip](https://www.twilio.com/docs/sip-trunking) [pipecat-P04](https://docs.pipecat.ai/pipecat/learn/transports)

Audioqualität hängt an Codec, tatsächlicher Samplingrate, Transcoding, Jitter/Paketverlust, Buffering und Netzroute. Größere Modell-Sampleraten rekonstruieren keine verlorene Telefonbandbreite. G.711/8-kHz sowie Mobil-/Festnetzfälle, DTMF, Ringback/Voicemail, frühe Medien, Warmtransfer und Abbruch sind Pflichtfälle. Twilios bidir Media Streams unterstützen DTMF nicht als ausgehenden Server→Twilio-Kanal. PSTN-/Carrierfailover kann aktive Calls nicht allgemein verlustfrei retten. [twilio-streams](https://www.twilio.com/docs/voice/media-streams)

**CPS ≠ Concurrent Calls.** Startdurchsatz, parallele Carrierlegs, Runtimeworker, STT-/TTS-/LLM-Quoten und Transferreserve bilden die Kapazität gemeinsam. 1 Mio. Minuten/Monat sagt nichts über den Peak. Ein 5-Minuten-Call mit zehn Sekunden Klingeln, falscher Zielnummer oder zweitem Transferleg ist keine einheitliche Abrechnungseinheit.

## 4. EU-Infrastruktur-Vergleich

| Kandidat | Dokumentierte Basis | Realtime-/Betriebsgrenzen | Kosten-/Datenpfadgrenze |
|---|---|---|---|
| AWS Frankfurt | Multi-AZ, EC2, NLB UDP/TCP, RDS, S3, KMS/Secrets | viele Managed-Bausteine; NAT/egress/logs/HA und stateful Media-Pinning komplex | einige Frankfurt-SKU-Preise dynamisch nicht extrahiert; globale Control-/Supportdaten separat |
| OVHcloud Frankfurt/LIM | Compute, Storage, Netzwerk, Managed PostgreSQL, KMS/Secrets laut Matrix | UDP-Listener dokumentiert, aber keine gemessene SIP/WebRTC-Eignung; Cluster/Backup prüfen | geöffnete Preisbeispiele teils USD-US und EUR; kein heimlicher Mix; internationale Subprozessoren |
| Hetzner DE/FI | Cloud-/Server-API, private Netze, Volumes, TCP/HTTP(S)-LB | keine dokumentierte UDP-LB-Weiterleitung; unmanaged DB/HA/Backups wesentlich Eigenbetrieb | EU-Server-/Supportangaben vorhanden; keine Garantie für externe AI/CRM-Pfade; Subprocessorliste älter |

Belege: [aws-01](https://aws.amazon.com/about-aws/global-infrastructure/regions_az/) [aws-02](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/) [aws-03](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/introduction.html); [OVH](../research/ovh.md), [Hetzner](../research/hetzner.md). Für Hetzner ist z.B. CX23 mit 5,99 EUR/Monat exkl. MwSt. veröffentlicht, **kein Produktions-HA-Kostensatz**. AWS/OVH können Managedbetrieb vereinfachen, bringen jedoch zusätzliche Einzelgebühren und Betriebs-/API-Abhängigkeit. Kostengünstige VM und vollständiger SLO-/On-call-Betrieb sind unterschiedliche Dinge.

### Managed vs Self-Hosted: bedingte Abwägung

Managedruntime kann Deployment, Skalierung und Telemetrie beschleunigen; Region, Concurrency, Datenausleitung und Kosten sind an das konkrete Angebot gebunden. Self-Hosting erhöht Kontrolle über Compute/Logs/Medien, verpflichtet aber zu Netzwerk/SIP/SBC, Drain/Recovery, Sicherheitsupdates, Backup/Restore und Bereitschaft. EU-Selfhost macht US-/globale Speech-Provider nicht automatisch EU-lokal. Ein reines EU-only-Produkt benötigt auch eine klare **fail-closed statt globales Fallback**-Policy.

Der frühe Ansatz sollte Betriebsfähigkeit und rechtlich nötige Isolation priorisieren, nicht Kubernetes/Microservices aufgrund erwarteten späteren Wachstums voraussetzen. Die genaue Hostingstrategie bleibt offen, bis SLO, Team, Peakprofile und Verträge feststehen.

## 5. Datenpfad und Vertragscheck

Pro Kandidat getrennt belegen: Carrier- und Mediaregion, Inferenzregion pro Modell, Recording/Transcriptstore, Logs/Tracing, Backups, Supportzugriff, Subprozessoren, Kontometadaten und Drittlandtransfer. Twilio weist selbst auf unvollständige Regionsgarantien hin; Telnyx bietet EU-Anchors/at-rest Optionen, deren Existenz nicht alle AI-/Supportpfade bestätigt. [twilio-regions](https://www.twilio.com/docs/global-infrastructure/understanding-twilio-regions) [twilio-availability](https://www.twilio.com/docs/global-infrastructure/regional-product-and-feature-availability) [twilio-dpa](https://www.twilio.com/legal/data-protection-addendum)

Prüfunterlagen: konkrete Tarif-/Ratedeckversion, AVV/TOM/Subprocessorliste, SLA/Quoten, automatisierte Calling-/Resale-/White-Label-Erlaubnis, KYC/Nummernnutzungsrecht, Porting-/Exitpfad, Legal Caller-ID, Recording-/Retentionmatrix. B2B-/Flatrateformulierung eines Carriers ersetzt keine Outreach-Rechtsprüfung nach UWG.

## 6. Offene Entscheidung und Wechselbedingungen

Primär Twilio/Telnyx in passenden Audio-/SIP-Pfaden testen; einen deutschen Carrier für lokale Nummern-/Vertragsbedingungen gegenprüfen. Keine Anbieterwahl ohne echte Zielraten und Resale-/Automationfreigabe. Ein lokaler Carrier kann wirtschaftlich gewinnen, aber zusätzliche SBC-/API-/Betriebsarbeit erfordern. Ein CPaaS kann technisch gewinnen und bei Mobilkosten oder EU-Sondervertrag wirtschaftlich verlieren.

Eine endgültige Hosting-/Carrierentscheidung verlangt gepaarte Sprach-/Netztests, Last-/Transferfälle, verifizierte Region-/Failoverkonfiguration und vollständige Angebote. Diese Bedingungen und der p95-/Kosten-Gate stehen in Bericht 12.
