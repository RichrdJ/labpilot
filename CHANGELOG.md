# Changelog

## v1.1.0
- Alle koppelingen en algemene opties instellen via de webinterface (Instellingen), met "Verbinding testen"
- Instellingen worden bewaard in het volume `/data`; wachtwoorden worden nooit naar de browser gestuurd
- Inlogwachtwoord voor het dashboard instelbaar in de webinterface
- Eenvoudigere `docker-compose.yml` (alleen poort en volume), standaardpoort 38471

## v1.0.1
- Compose geschikt voor Portainer, pytest-configuratie gerepareerd

## v1.0.0
- Eerste release: ESXi, Synology, UniFi en Veeam in één dashboard
- VM ↔ netwerk-correlatie op MAC-adres
- Aandachtspunten met acties (VM aan/uit, client blokkeren, Veeam-job starten)
- Command palette, live updates via SSE, donker/licht thema
- Optionele login, demomodus, multi-arch Docker-image via GHCR
