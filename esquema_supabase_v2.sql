-- =====================================================================
-- Esquema v2: UNA sola tabla con la linea y su consumo (historico diario)
-- Pegar TODO en: Supabase -> proyecto "vodafone scrape" -> SQL Editor -> Run
-- =====================================================================

-- Tabla unica: una fila por linea y dia.
create table if not exists consumo_diario (
  id             bigint generated always as identity primary key,
  numero_linea   text not null,
  consumo_mb     numeric,           -- consumo normalizado a MB
  consumo_texto  text,              -- texto crudo: "Consumido 0 MB de tus datos ilimitados"
  tipo_plan      text,              -- ej. "ilimitado"
  fecha_captura  date not null default current_date,
  periodo_inicio date,
  periodo_fin    date,
  cif            text,
  cuenta         text,
  capturado_en   timestamptz default now(),
  unique (numero_linea, fecha_captura)   -- 1 fila por linea/dia (upsert idempotente)
);

create index if not exists idx_consumo_diario_fecha on consumo_diario (fecha_captura);
create index if not exists idx_consumo_diario_linea on consumo_diario (numero_linea);

alter table consumo_diario enable row level security;

-- Eliminar las dos tablas antiguas (linea y consumo por separado).
drop table if exists consumos;
drop table if exists lineas;

-- (Se mantiene la tabla scrape_runs para monitorizar las ejecuciones.)
