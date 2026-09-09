# Mobile Dashboard

Mac/Hermes/OpenRouter Dashboard im OpenRouter-Stil. Hosted auf GitHub Pages mit Supabase + Discord OAuth Schutz.

## Setup

### 1. Supabase

1. Supabase Projekt erstellen (oder bestehendes nutzen)
2. **SQL Editor** öffnen → `supabase-schema.sql` ausführen
3. **Authentication > Providers > Discord** aktivieren:
   - Discord Developer Portal: https://discord.com/developers/applications
   - Neue App erstellen oder bestehende nutzen
   - OAuth2 > Redirect URI setzen: `https://DEINE_URL.github.io/REPO/`
   - Client ID + Secret in Supabase eintragen
4. **Settings > API** → URL und Keys notieren

### 2. Frontend (index.html)

In `index.html` die Config-Zeilen anpassen:
```js
const SUPABASE_URL = 'https://DEIN Projekt.supabase.co';
const SUPABASE_ANON = 'DEIN anon key';
const ALLOWED_DISCORD_IDS = ['1282332318576541737']; // Discord User IDs
```

### 3. Backend (backend.py)

Env-Variablen setzen:
```bash
export SUPABASE_URL="https://DEIN Projekt.supabase.co"
export SUPABASE_SERVICE_KEY="DEIN service_role key"
export OPENROUTER_API_KEY="DEIN OpenRouter key"
```

Oder in eine `.env`-Datei:
```
SUPABASE_URL=https://DEIN Projekt.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
OPENROUTER_API_KEY=sk-or-...
```

### 4. Backend starten (launchd)

```bash
# launchd plist erstellen
# Siehe setup.sh für automatisches Setup
```

### 5. GitHub Pages

Repo pushen → Settings > Pages > Source: main branch

## Dateien

```
mobile-dashboard/
├── index.html          # Dashboard (HTML/CSS/JS)
├── backend.py          # Stat-Sammler + Supabase-Push
├── supabase-schema.sql # Datenbank-Schema
├── .env.example        # Env-Variablen Template
├── setup.sh            # Automatisches Setup
├── data/
│   ├── stats.json      # Lokaler Cache
│   └── cpu_history.json # CPU-Sparkline-Daten
└── README.md
```

## Security

- Discord OAuth Login via Supabase
- Whitelist: Nur eingetragene Discord-IDs kommen rein
- RLS: Supabase Row Level Security aktiv
- Repo kann public bleiben
