# n8n Integration Plan — Arasul / Jetson Orin Nano

## Zusammenfassung

n8n als lokale Workflow-Automatisierung auf dem Jetson Orin Nano (8GB RAM), integriert in die Arasul TUI. Claude Code erstellt Workflows via MCP-Server direkt in n8n. Webhooks werden via Tailscale Funnel exponiert.

**Entscheidungen:**
- Datenbank: PostgreSQL (separater Container)
- Netzwerk: LAN + Tailscale
- Claude-Integration: n8n-mcp MCP-Server
- Webhooks: Tailscale Funnel (nur `/webhook/*`)

**Geschaetzter RAM-Verbrauch:**
- n8n Container: ~300-500MB (mit `NODE_OPTIONS="--max-old-space-size=1024"`)
- PostgreSQL Container: ~100-256MB
- Gesamt: ~500-750MB von 8GB

---

## Phase 1: Docker-Setup & Deployment-Script

### 1.1 Neues Setup-Script: `scripts/09-n8n-setup.sh`

Erstellt Docker-Compose-Stack fuer n8n + PostgreSQL auf NVMe.

**Aufgaben:**
- [ ] Script `scripts/09-n8n-setup.sh` erstellen (idempotent, wie alle anderen Scripts)
- [ ] Docker-Compose-Datei: `/mnt/nvme/n8n/docker-compose.yml`
- [ ] Umgebungsvariablen: `/mnt/nvme/n8n/.env`
- [ ] NVMe-Verzeichnisse anlegen: `/mnt/nvme/n8n/data`, `/mnt/nvme/n8n/postgres`
- [ ] Workflow-Export-Verzeichnis: `/mnt/nvme/n8n/workflows/`
- [ ] n8n Encryption Key generieren und sicher speichern
- [ ] UFW-Regel: Port 5678 im LAN erlauben
- [ ] Setup-Script in `setup.sh` als Step 9 einbinden

**Docker-Compose Struktur:**

```yaml
version: '3.8'

volumes:
  n8n_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/nvme/n8n/data
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/nvme/n8n/postgres

services:
  postgres:
    image: postgres:16
    restart: always
    environment:
      POSTGRES_USER: ${N8N_DB_USER}
      POSTGRES_PASSWORD: ${N8N_DB_PASS}
      POSTGRES_DB: n8n
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -h localhost -U ${N8N_DB_USER} -d n8n']
      interval: 5s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          memory: 256M

  n8n:
    image: docker.n8n.io/n8nio/n8n
    restart: always
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=${N8N_DB_USER}
      - DB_POSTGRESDB_PASSWORD=${N8N_DB_PASS}
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - N8N_HOST=${N8N_HOST}
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - WEBHOOK_URL=${N8N_WEBHOOK_URL}
      - N8N_RUNNERS_MODE=external
      - N8N_BLOCK_ENV_ACCESS_IN_NODE=true
      - N8N_DIAGNOSTICS_ENABLED=false
      - N8N_TEMPLATES_ENABLED=true
      - NODE_OPTIONS=--max-old-space-size=1024
      - NODES_EXCLUDE=["n8n-nodes-base.executeCommand","n8n-nodes-base.localFileTrigger","n8n-nodes-base.readWriteFile"]
    ports:
      - "${N8N_BIND_ADDRESS:-0.0.0.0}:5678:5678"
    volumes:
      - n8n_data:/home/node/.n8n
      - /mnt/nvme/n8n/workflows:/home/node/workflows
    depends_on:
      postgres:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 1G
```

**Umgebungsvariablen (.env):**

```bash
# n8n Database
N8N_DB_USER=n8n
N8N_DB_PASS=<generated-secure-password>

# n8n Security
N8N_ENCRYPTION_KEY=<generated-64-char-hex>

# n8n Network
N8N_HOST=0.0.0.0
N8N_BIND_ADDRESS=0.0.0.0
N8N_WEBHOOK_URL=https://<jetson-tailscale-hostname>.ts.net/webhook/

# n8n API (nach erstem Start generieren)
N8N_API_KEY=<from-n8n-ui>
```

### 1.2 .env.example erweitern

- [ ] n8n-spezifische Variablen zu `.env.example` hinzufuegen
- [ ] Dokumentation der Variablen

### 1.3 Tailscale Funnel Konfiguration

- [ ] `tailscale serve` fuer Port 5678 (n8n UI + API)
- [ ] `tailscale funnel` fuer `/webhook/*` Pfade (oeffentliche Webhooks)
- [ ] Anleitung fuer Tailscale ACL-Regeln (nur autorisierte Geraete)

---

## Phase 2: TUI-Integration

### 2.1 Neues Command-Modul: `arasul_tui/commands/n8n_cmd.py`

**Subcommands:**

| Command | Beschreibung |
|---------|-------------|
| `/n8n` oder `/n8n status` | Dashboard: Container-Status, aktive Workflows, letzte Ausfuehrungen |
| `/n8n install` | Docker-Stack deployen (ruft `09-n8n-setup.sh` auf) |
| `/n8n start` | `docker compose up -d` |
| `/n8n stop` | `docker compose down` |
| `/n8n logs` | Letzte n8n-Logs anzeigen |
| `/n8n workflows` | Liste aller Workflows (via API) |
| `/n8n open` | n8n Web-UI URL anzeigen / oeffnen |
| `/n8n api-key` | API-Key Setup-Wizard |

**Aufgaben:**
- [ ] `arasul_tui/commands/n8n_cmd.py` erstellen
- [ ] Handler `cmd_n8n(state, args)` mit Subcommand-Routing
- [ ] Export in `commands/__init__.py` hinzufuegen
- [ ] CommandSpec in `core/router.py` registrieren (Kategorie: "Services")
- [ ] Aliases: `["workflows", "automation", "n8n workflows"]`

### 2.2 Core-Modul: `arasul_tui/core/n8n_client.py`

API-Client fuer n8n REST API.

**Funktionen:**

```python
def n8n_is_running() -> bool:
    """Prueft ob n8n-Container laeuft."""

def n8n_api_request(method: str, endpoint: str, data: dict | None = None) -> dict:
    """REST API Aufruf mit API-Key Auth."""

def n8n_list_workflows() -> list[dict]:
    """GET /api/v1/workflows"""

def n8n_get_workflow(workflow_id: str) -> dict:
    """GET /api/v1/workflows/{id}"""

def n8n_create_workflow(workflow_json: dict) -> dict:
    """POST /api/v1/workflows"""

def n8n_activate_workflow(workflow_id: str) -> dict:
    """POST /api/v1/workflows/{id}/activate"""

def n8n_list_executions(workflow_id: str | None = None) -> list[dict]:
    """GET /api/v1/executions"""

def n8n_health() -> dict:
    """Container-Status + API-Health + Workflow-Stats."""

def n8n_get_api_key() -> str | None:
    """Liest API-Key aus Config."""

def n8n_save_api_key(key: str) -> None:
    """Speichert API-Key in Config."""
```

**Aufgaben:**
- [ ] `arasul_tui/core/n8n_client.py` erstellen
- [ ] API-Key-Speicherung in `~/.config/arasul/n8n.yaml` oder `~/.claude.json`
- [ ] Fehlerbehandlung fuer Verbindungsprobleme
- [ ] Timeout-Konfiguration

### 2.3 n8n als "Projekt" im TUI

Spezielles Projekt, das n8n-Workflows und Claude Code verknuepft.

**Konzept:**
1. `/create n8n-workflows` erstellt ein Projekt-Verzeichnis: `/mnt/nvme/projects/n8n-workflows/`
2. Dieses Verzeichnis wird als Docker-Volume in n8n gemountet
3. Wenn man das Projekt mit `/open` oeffnet, zeigt der Project Screen:
   - n8n-Status (Running/Stopped)
   - Aktive Workflows
   - Link zur Web-UI
4. `/claude` in diesem Projekt startet Claude Code mit n8n-MCP-Server
5. Claude kann dann Workflows erstellen, die direkt in n8n landen

**Aufgaben:**
- [ ] Projekt-Template fuer n8n-Workflows definieren
- [ ] CLAUDE.md Template fuer das n8n-Projekt erstellen (erklaert Claude den Workflow-Kontext)
- [ ] Verzeichnisstruktur: `workflows/`, `credentials/`, `docs/`

### 2.4 Setup-Wizard erweitern

- [ ] Step 9 "n8n Automation" in `core/setup_wizard.py` hinzufuegen
- [ ] `check_done()`: Prueft ob n8n-Container laeuft und API erreichbar ist
- [ ] Script: `scripts/09-n8n-setup.sh`

---

## Phase 2.5: Projekt-Kontext (API-first, kein Wizard)

### Prinzip: Kein duplizierter Zustand

Der Kontext liegt in n8n selbst — Credentials, Workflows, Executions. Claude holt
sich alles dynamisch ueber den MCP-Server. Es gibt keinen Onboarding-Wizard und
kein Profil-YAML. Die CLAUDE.md im Projekt ist eine schlanke, statische Datei die
nur erklaert WO n8n laeuft und WAS Claude tun/lassen darf.

**Warum kein Wizard:**
- Wizard-Daten sind nach einer Woche veraltet (neue Credentials hinzugefuegt)
- n8n IST die Single Source of Truth — Daten nicht duplizieren
- Der MCP-Server kann Credentials, Workflows und Node-Typen live abfragen
- Claude soll auch Workflows fuer Dienste bauen die NOCH keine Credentials haben

### 2.5.1 CLAUDE.md — Workflow-Design Sparring-Partner

Wird beim `/create n8n-workflows` automatisch angelegt. Diese CLAUDE.md macht
Claude zu einem erfahrenen n8n-Berater der den User durch den gesamten Prozess
fuehrt: Discovery -> Plan -> Review -> Build -> Test.

**Datei: `config/n8n/CLAUDE.md.template`**

```markdown
# n8n Workflow Automation

Du bist ein erfahrener n8n-Workflow-Architekt. Dieses Projekt verwaltet
Automatisierungs-Workflows die lokal auf einem Jetson als Docker-Container
laufen. Du hast ueber den n8n MCP-Server direkten Zugriff auf die
laufende n8n-Instanz.

## Infrastruktur

- n8n Web-UI: http://localhost:5678
- n8n API: http://localhost:5678/api/v1
- Workflow-Dateien (Backup): ./workflows/
- Der MCP-Server "n8n" ist konfiguriert und aktiv

## Dein Arbeitsprozess

Wenn der User einen Workflow erstellen oder aendern moechte, folge IMMER
diesem Prozess. Ueberspringe KEINEN Schritt.

### Schritt 1: Discovery (IMMER zuerst)

Bevor du irgendetwas baust, verstehe das Problem. Nutze das AskUserQuestion
Tool um gezielte Fragen zu stellen. Frage NICHT alles auf einmal — fuehre
ein Gespraech.

Runde 1 — Ziel und Ausloeser:
- Was genau soll automatisiert werden? Beschreibe den aktuellen manuellen
  Ablauf Schritt fuer Schritt.
- Was loest den Prozess aus? (Neue E-Mail, Zeitplan, Webhook, manuell?)
- Wie oft passiert das? (Pro Event, stuendlich, taeglich?)

Runde 2 — Daten und Dienste:
- Welche Dienste/Tools sind beteiligt?
- Wie sehen die Daten aus die fliessen? (Format, Felder, Menge)
- Gibt es Bedingungen oder Verzweigungen? (Wenn X, dann Y?)

Runde 3 — Fehler und Randfaelle:
- Was soll passieren wenn ein Schritt fehlschlaegt?
- Gibt es Spezialfaelle? (Leere Daten, Duplikate, Rate Limits?)
- Wer soll benachrichtigt werden bei Problemen?

Passe die Fragen an den Kontext an. Bei einfachen Workflows (z.B.
"schick mir eine Slack-Nachricht wenn eine Gmail kommt") reichen 2-3
Fragen. Bei komplexen Workflows stelle so viele Fragen wie noetig.

### Schritt 2: Credential-Check

Frage den n8n MCP-Server nach vorhandenen Credentials ab.
- Wenn das benoetigte Credential existiert: Nutze es per Name
- Wenn es NICHT existiert: Baue den Workflow trotzdem, weise den User
  darauf hin welches Credential er in der n8n Web-UI anlegen muss,
  und erklaere kurz welchen Credential-Typ (OAuth2, API Key, etc.)

### Schritt 3: Plan schreiben

Schreibe einen kurzen, konkreten Plan BEVOR du den Workflow baust.
Der Plan enthaelt:
- Workflow-Name
- Trigger-Typ und Konfiguration
- Jeden Node mit Name, Typ und was er tut (als nummerierte Liste)
- Datenfluss zwischen den Nodes
- Fehlerbehandlung
- Fehlende Credentials (falls vorhanden)

Zeige dem User den Plan und frage ob er passt oder ob etwas geaendert
werden soll. Erst nach Freigabe weiter zu Schritt 4.

### Schritt 4: Workflow bauen

Erstelle den Workflow ueber den n8n MCP-Server. Beachte dabei:

Struktur:
- Maximal 10-15 Nodes pro Workflow. Bei mehr: Sub-Workflows nutzen
- Jeden Node beschreibend benennen (nicht "HTTP Request" sondern
  "Kundendaten aus CRM laden")
- Error Trigger Node einbauen fuer Fehlermeldungen

Qualitaet:
- Eingangsdaten validieren (IF Node am Anfang fuer Pflichtfelder)
- Retry-on-Fail aktivieren fuer API-Nodes (3 Versuche, 5s Abstand)
- Keine hartcodierten Werte — Credentials ueber n8n Credential-System
- Bei Schleifen: Batch-Groesse > 1, Wait-Nodes fuer Rate Limits

Backup:
- Workflow-JSON zusaetzlich als Datei in ./workflows/ speichern
- Dateiname: workflow-name-in-kebab-case.json

### Schritt 5: Review und Aktivierung

- Fasse zusammen was der Workflow tut
- Weise auf fehlende Credentials hin
- Frage den User ob der Workflow aktiviert werden soll
- Aktiviere NUR nach expliziter Bestaetigung

## Haeufige Fehler die du vermeiden musst

- KEIN monolithischer 50-Node-Workflow. Aufteilen in Sub-Workflows.
- KEINE IF-Ketten. Nutze Switch-Nodes fuer mehrere Bedingungen.
- KEINE Workflows ohne Fehlerbehandlung. Immer Error Trigger.
- KEIN Polling wenn Webhooks verfuegbar sind (langsamer, mehr Last).
- KEINE Batch-Groesse 1 in Schleifen (erzeugt tausende API-Calls).
- NICHT die Originaldaten ueberschreiben — Rohdaten behalten.
- NICHT "Save Execution Progress" aktivieren bei haeufigen Workflows.

## Regeln

- NICHT den Docker-Container oder die Docker-Compose-Datei anfassen
- NICHT Credentials loeschen oder deren Secrets anzeigen lassen
- NICHT Dateien ausserhalb dieses Projektordners aendern
- NICHT Workflows aktivieren ohne den User zu fragen
- Wenn n8n nicht erreichbar ist: User informieren, NICHT selbst fixen
```

**Aufgaben:**
- [ ] Template in `config/n8n/CLAUDE.md.template` ablegen
- [ ] Beim `/create n8n-workflows` automatisch ins Projekt kopieren
- [ ] n8n-URL dynamisch aus Konfiguration einsetzen (sed/envsubst)

### 2.5.2 Guardrails via .claude/settings.json

Harte Permission-Regeln die Claude nicht umgehen kann:

**`/mnt/nvme/projects/n8n-workflows/.claude/settings.json`:**

```json
{
  "permissions": {
    "deny": [
      "Bash(docker *)",
      "Bash(sudo *)",
      "Bash(rm -rf *)",
      "Bash(systemctl *)",
      "Bash(kill *)",
      "Edit(/mnt/nvme/n8n/*)",
      "Edit(/etc/*)",
      "Read(/mnt/nvme/n8n/.env)"
    ]
  }
}
```

Claude kann im Projekt frei lesen/schreiben (Workflow-JSONs, Docs) aber
Docker, System und n8n-Infrastruktur sind gesperrt. Alles was Claude mit
n8n machen will, laeuft ueber den MCP-Server (API-Calls, nicht Docker).

**Aufgaben:**
- [ ] `settings.json` Template in `config/n8n/settings.json` ablegen
- [ ] Beim Projekt-Setup automatisch nach `.claude/settings.json` kopieren

### 2.5.3 Dynamischer Kontext via MCP (kein Sync noetig)

So bekommt Claude den Kontext — live, ohne Sync, ohne Wizard:

1. Claude startet im n8n-Projekt, liest CLAUDE.md
2. CLAUDE.md sagt: "Frage zuerst ueber MCP ab welche Credentials da sind"
3. Claude ruft MCP-Tool auf: `list_credentials` -> bekommt alle Namen + Typen
4. Claude ruft MCP-Tool auf: `list_workflows` -> sieht bestehende Workflows
5. Claude hat jetzt den vollen Kontext und kann loslegen

**Wenn der Nutzer sagt "Erstelle einen Gmail-Workflow":**
- Claude prueft via MCP ob Gmail-Credential existiert
- Falls ja: Erstellt Workflow mit dem exakten Credential-Namen
- Falls nein: Erstellt Workflow trotzdem, sagt dem Nutzer
  "Du musst noch ein Gmail OAuth2 Credential in n8n anlegen"

**Kein Profil, kein Sync, kein Wizard — n8n ist die einzige Datenquelle.**

---

## Phase 3: MCP-Server Integration

### 3.1 n8n-mcp Server einrichten

Der [n8n-mcp](https://github.com/czlonkowski/n8n-mcp) MCP-Server gibt Claude Code direkten Zugriff auf n8n.

**Features:**
- 1.084 Node-Definitionen mit 99% Property-Genauigkeit
- 2.709 Workflow-Templates
- Node-Validierung
- Workflow-CRUD via API

**Konfiguration in `~/.claude.json`:**

```json
{
  "mcpServers": {
    "n8n": {
      "command": "npx",
      "args": ["-y", "n8n-mcp"],
      "env": {
        "N8N_API_URL": "http://localhost:5678/api/v1",
        "N8N_API_KEY": "<api-key>"
      }
    }
  }
}
```

**Aufgaben:**
- [ ] n8n-mcp als MCP-Server in `/mcp add` integrieren
- [ ] TUI-Command `/n8n mcp` zum Konfigurieren des MCP-Servers
- [ ] API-Key aus n8n-Config lesen und automatisch setzen
- [ ] Testen ob `npx n8n-mcp` auf ARM64 funktioniert (Node.js erforderlich)
- [ ] Fallback: Eigenen minimalen MCP-Server in Python schreiben falls npx-Variante auf ARM64 nicht laeuft

### 3.2 MCP als einzige Kontext-Quelle

Der MCP-Server ersetzt jeglichen statischen Kontext. Claude fragt live ab:
- `list_credentials` — welche Dienste eingerichtet sind
- `list_workflows` — was schon existiert
- `get_node_info` — welche Properties ein Node braucht
- `search_templates` — Vorlagen fuer gaengige Use Cases

Kein Profil-YAML, kein Credential-Sync, keine Template-Engine.
Die CLAUDE.md (Phase 2.5.1) sagt Claude nur "nutze den MCP-Server".

---

## Phase 4: Security Hardening

### 4.1 n8n Security

- [ ] `N8N_ENCRYPTION_KEY`: 64-Zeichen Hex-String generieren, in `.env` speichern, Backup erstellen
- [ ] `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`: Code-Nodes koennen keine Server-Umgebungsvariablen lesen
- [ ] `NODES_EXCLUDE`: `executeCommand`, `localFileTrigger`, `readWriteFile` blockieren
- [ ] Task Runners aktiviert (Default in n8n v2.0) fuer Code-Node Sandboxing
- [ ] Owner-Account mit starkem Passwort + 2FA einrichten (nach erstem Start)
- [ ] API-Key sicher speichern (nicht im Git)

### 4.2 Netzwerk-Security

- [ ] UFW: Port 5678 nur fuer LAN-Subnetz erlauben (`ufw allow from 192.168.x.0/24 to any port 5678`)
- [ ] Tailscale: `tailscale serve --bg 5678` fuer VPN-Zugriff
- [ ] Tailscale Funnel: Nur `/webhook/*` exponieren
- [ ] Docker-Netzwerk: PostgreSQL nur intern erreichbar (kein Port-Mapping)

### 4.3 Backup & Recovery

- [ ] Automatisches Workflow-Export Cron: `n8n export:workflow --all --separate --output=/mnt/nvme/n8n/workflows/`
- [ ] PostgreSQL Backup Cron: `pg_dump` nach `/mnt/nvme/backups/n8n/`
- [ ] Encryption Key Backup-Anleitung
- [ ] Cron in `scripts/09-n8n-setup.sh` einrichten

---

## Phase 5: Workflow-Entwicklung mit Claude

### 5.1 Typischer Workflow (Beispiel: Gmail -> Slack)

**User:** "Ich will dass neue Mails von Kunden automatisch in Slack gepostet werden"

**Claude (Discovery — Runde 1):** Stellt ueber AskUserQuestion:
- Alle Mails oder nur bestimmte (Label, Absender, Betreff)?
- In welchen Slack-Channel? Gibt es verschiedene Channels je nach Thema?
- Soll die ganze Mail gepostet werden oder nur eine Zusammenfassung?

**Claude (Discovery — Runde 2):** Stellt Folgefragen:
- Was wenn eine Mail keinen Betreff hat?
- Sollen Anhaenge beruecksichtigt werden?
- Gibt es Mails die gefiltert werden sollen (Newsletter, Spam)?

**Claude (Credential-Check):** Fragt MCP:
- "Gmail Business" (gmailOAuth2) -> vorhanden
- "Slack Workspace" (slackOAuth2Api) -> vorhanden

**Claude (Plan):** Schreibt und zeigt dem User:
```
Workflow: "Kunden-Mails nach Slack"
1. Gmail Trigger — Neue Mails mit Label "Kunden"
2. IF — Hat die Mail einen Betreff? (Fallback: "Kein Betreff")
3. Set — Formatiere Slack-Nachricht (Absender, Betreff, Vorschau)
4. Slack — Poste in #kunden-inbox
5. Error Trigger — Bei Fehler: Nachricht an #alerts
```
"Passt das so oder soll ich etwas aendern?"

**User:** "Ja passt"

**Claude (Build):** Erstellt Workflow via MCP, speichert JSON in ./workflows/

**Claude (Review):** "Workflow erstellt. Soll ich ihn aktivieren?"

### 5.2 Credential-Setup Workflow

1. `/n8n open` -> n8n Web-UI im Browser
2. Credentials Tab -> "New Credential"
3. z.B. Gmail OAuth2: Client ID + Secret eingeben, OAuth-Flow durchlaufen
4. Credential ist jetzt in n8n gespeichert und von Workflows nutzbar
5. Claude referenziert Credentials in Workflows nur per Name (keine Secrets im JSON)

---

## Implementierungsreihenfolge

| Schritt | Phase | Beschreibung | Abhaengigkeiten |
|---------|-------|-------------|-----------------|
| 1 | 1.1 | `09-n8n-setup.sh` Script | Keine |
| 2 | 1.2 | `.env.example` erweitern | Step 1 |
| 3 | 1.3 | Tailscale Funnel Config | Step 1 |
| 4 | 2.2 | `core/n8n_client.py` | Step 1 (n8n muss laufen) |
| 5 | 2.1 | `commands/n8n_cmd.py` | Step 4 |
| 6 | 2.4 | Setup-Wizard Step 9 | Step 1 |
| 7 | 2.5.1 | Statische CLAUDE.md + Projekt-Template | Step 5 |
| 8 | 2.5.2 | `.claude/settings.json` Guardrails | Step 7 |
| 9 | 3.1 | n8n-mcp Server Setup + Test auf ARM64 | Step 4 |
| 10 | 4.1-4.3 | Security & Backups | Step 1 |
| 11 | 5 | Test & Dokumentation | Alles |

---

## Dateien die erstellt/geaendert werden

### Neue Dateien
- `scripts/09-n8n-setup.sh` — Docker-Setup Script
- `config/n8n/docker-compose.yml` — Compose-Template
- `config/n8n/.env.example` — n8n-spezifische Env-Vars
- `config/n8n/CLAUDE.md.template` — Statische CLAUDE.md fuers n8n-Projekt
- `config/n8n/settings.json` — .claude/settings.json Template (Guardrails)
- `arasul_tui/commands/n8n_cmd.py` — TUI Command Handler
- `arasul_tui/core/n8n_client.py` — n8n API Client (Health, Status)
- `tests/test_n8n_cmd.py` — Tests fuer n8n Commands
- `tests/test_n8n_client.py` — Tests fuer API Client

### Geaenderte Dateien
- `.env.example` — n8n Variablen hinzufuegen
- `setup.sh` — Step 9 hinzufuegen
- `arasul_tui/commands/__init__.py` — `cmd_n8n` Export
- `arasul_tui/core/router.py` — n8n CommandSpec registrieren
- `arasul_tui/core/setup_wizard.py` — Step 9 hinzufuegen
- `CLAUDE.md` — n8n Dokumentation
- `README.md` — n8n Abschnitt

---

## Risiken & Mitigationen

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|-----------|
| RAM-Engpass (n8n + PostgreSQL + GPU) | Mittel | Memory Limits setzen, `--max-old-space-size=1024`, Monitoring via `/status` |
| n8n Memory Leak bei langen Laeufen | Mittel | Cron fuer woechentlichen Container-Restart, Execution-History Pruning |
| n8n-mcp funktioniert nicht auf ARM64 | Niedrig | Fallback: eigener Python MCP-Server oder direkte API-Calls |
| Tailscale Funnel Latenz fuer Webhooks | Niedrig | Alternative: Cloudflare Tunnel oder ngrok als Backup |
| PostgreSQL Disk-Usage waechst | Niedrig | Execution-Pruning konfigurieren, Monitoring in `/n8n status` |
| Credential-Verlust bei Container-Reset | Hoch wenn nicht mitigiert | Encryption Key Backup, PostgreSQL Backup Cron, Volume auf NVMe |

---

## Referenzen

- [n8n Docker Hub (ARM64)](https://hub.docker.com/r/n8nio/n8n)
- [n8n Hosting Repo](https://github.com/n8n-io/n8n-hosting)
- [n8n REST API](https://docs.n8n.io/api/)
- [n8n CLI Commands](https://docs.n8n.io/hosting/cli-commands/)
- [n8n-mcp MCP Server](https://github.com/czlonkowski/n8n-mcp)
- [n8n Security Docs](https://docs.n8n.io/hosting/securing/)
- [n8n Memory Management](https://docs.n8n.io/hosting/scaling/memory-errors/)
- [Tailscale Serve/Funnel](https://tailscale.com/kb/1242/tailscale-serve)
