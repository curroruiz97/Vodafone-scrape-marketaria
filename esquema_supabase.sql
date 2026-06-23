-- =====================================================================
-- Esquema para el scraper de consumo de Mi Vodafone Business
-- Pegar TODO esto en: Supabase -> proyecto "vodafone scrape" -> SQL Editor -> Run
-- Es seguro reejecutarlo (usa IF NOT EXISTS).
-- =====================================================================

-- 1) Maestro de líneas (una fila por número de teléfono)
create table if not exists lineas (
  id                bigint generated always as identity primary key,
  numero_linea      text not null unique,
  cif               text,            -- ej. "B47573944"
  cuenta            text,            -- ej. "29250841"
  alias             text,
  activa            boolean default true,
  primera_vez_vista timestamptz default now(),
  ultima_vez_vista  timestamptz default now()
);

-- 2) Histórico: un snapshot de consumo por línea y día
create table if not exists consumos (
  id             bigint generated always as identity primary key,
  linea_id       bigint not null references lineas(id) on delete cascade,
  fecha_captura  date not null default current_date,
  periodo_inicio date,
  periodo_fin    date,
  consumo_mb     numeric,           -- consumo normalizado a MB
  consumo_texto  text,              -- texto crudo: "Consumido 0 MB de tus datos ilimitados"
  tipo_plan      text,              -- ej. "ilimitado"
  capturado_en   timestamptz default now(),
  unique (linea_id, fecha_captura)  -- 1 registro por línea/día (permite upsert idempotente)
);

-- 3) Registro de cada ejecución del scraper (para monitorizar)
create table if not exists scrape_runs (
  id                 bigint generated always as identity primary key,
  iniciado_en        timestamptz default now(),
  finalizado_en      timestamptz,
  estado             text,          -- 'ok' | 'parcial' | 'error'
  lineas_detectadas  int,
  lineas_guardadas   int,
  mensaje_error      text
);

-- Índices para consultas por línea y por fecha
create index if not exists idx_consumos_linea_fecha on consumos (linea_id, fecha_captura);
create index if not exists idx_consumos_fecha       on consumos (fecha_captura);

-- 4) Seguridad: RLS activado. Solo el scraper, usando la service_role key,
--    podrá leer/escribir. La clave anónima no tendrá acceso (no creamos políticas públicas).
alter table lineas      enable row level security;
alter table consumos    enable row level security;
alter table scrape_runs enable row level security;
