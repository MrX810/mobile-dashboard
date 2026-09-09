-- ============================================
-- Dashboard Supabase Schema
-- ============================================

-- 1. Stats-Tabelle
CREATE TABLE IF NOT EXISTS dashboard_stats (
  id            int PRIMARY KEY DEFAULT 1,
  updated_at    timestamptz DEFAULT now(),

  -- Mac
  mac_online        boolean DEFAULT false,
  cpu_percent       numeric DEFAULT 0,
  cpu_cores         int DEFAULT 0,
  cpu_freq          text DEFAULT '?',
  cpu_history       jsonb DEFAULT '[]',
  mem_total         int DEFAULT 0,
  mem_used          int DEFAULT 0,
  disk_total        int DEFAULT 0,
  disk_used         int DEFAULT 0,
  uptime            text DEFAULT '?',
  boot_time         text DEFAULT '?',
  battery_percent   int,
  battery_charging  boolean DEFAULT true,

  -- Hermes
  hermes_online   boolean DEFAULT false,
  hermes_model    text DEFAULT '?',

  -- OpenRouter
  openrouter_online boolean DEFAULT false,
  total_tokens    bigint DEFAULT 0,
  input_tokens    bigint DEFAULT 0,
  output_tokens   bigint DEFAULT 0,
  total_requests  int DEFAULT 0,
  cost            numeric DEFAULT 0,
  models          jsonb DEFAULT '[]',
  heatmap         jsonb DEFAULT '[]',
  active_day      jsonb DEFAULT '{}',
  weekly          jsonb DEFAULT '{}'
);

-- Seed row (upsert target)
INSERT INTO dashboard_stats (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- 2. Whitelist-Tabelle für Discord Users
CREATE TABLE IF NOT EXISTS allowed_users (
  discord_id    text PRIMARY KEY,
  username      text,
  added_at      timestamptz DEFAULT now()
);

-- Eintragen: Parzival
INSERT INTO allowed_users (discord_id, username)
VALUES ('1282332318576541737', 'Parzival')
ON CONFLICT (discord_id) DO NOTHING;

-- 3. RLS (Row Level Security) aktivieren
ALTER TABLE dashboard_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE allowed_users ENABLE ROW LEVEL SECURITY;

-- 4. Policies
-- Jeder eingeloggte User kann stats lesen (RLS prüft Auth)
CREATE POLICY "Auth can read stats"
  ON dashboard_stats FOR SELECT
  USING (auth.role() = 'authenticated');

-- Nur Service Key kann schreiben (Backend)
CREATE POLICY "Service key can upsert stats"
  ON dashboard_stats FOR ALL
  USING (auth.jwt()->>'role' = 'service_role');

-- Users können eigene Einträge lesen
CREATE POLICY "Users can read own entry"
  ON allowed_users FOR SELECT
  USING (auth.uid()::text = discord_id);

-- Nur Service Key kann whitelist ändern
CREATE POLICY "Service manages whitelist"
  ON allowed_users FOR ALL
  USING (auth.jwt()->>'role' = 'service_role');

-- 5. Index für schnelle Abfrage
CREATE INDEX IF NOT EXISTS idx_dashboard_stats_updated
  ON dashboard_stats (updated_at DESC);

-- ============================================
-- Fertig! Nächste Schritte:
-- 1. Supabase Projekt erstellen (oder bestehendes nutzen)
-- 2. Discord OAuth Provider in Supabase konfigurieren
-- 3. Service Key in Backend als ENV setzen
-- 4. Anon Key in index.html eintragen
-- ============================================
