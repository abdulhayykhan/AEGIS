-- Migration 001: Initial AEGIS Database Schema
-- Reference: AEGIS PRD Section 8 (Data Model)
-- Rules: Money stored as NUMERIC (never floats). All timestamps UTC.

CREATE TABLE IF NOT EXISTS instruments (
    symbol VARCHAR(32) PRIMARY KEY,
    venue VARCHAR(32) NOT NULL,
    tick_size NUMERIC(18, 8) NOT NULL,
    min_size NUMERIC(18, 8) NOT NULL,
    allowed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS bars (
    symbol VARCHAR(32) NOT NULL,
    timeframe VARCHAR(16) NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(18, 8) NOT NULL,
    high NUMERIC(18, 8) NOT NULL,
    low NUMERIC(18, 8) NOT NULL,
    close NUMERIC(18, 8) NOT NULL,
    volume NUMERIC(24, 8) NOT NULL,
    source VARCHAR(64) NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (symbol, timeframe, ts)
);

CREATE TABLE IF NOT EXISTS news_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(64) NOT NULL,
    url TEXT,
    ts TIMESTAMPTZ NOT NULL,
    title TEXT NOT NULL,
    body_hash VARCHAR(64) NOT NULL,
    summary TEXT,
    trust VARCHAR(16) NOT NULL DEFAULT 'untrusted'
);

CREATE TABLE IF NOT EXISTS runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    ended_at TIMESTAMPTZ,
    mode VARCHAR(16) NOT NULL, -- 'PAPER' or 'LIVE'
    trigger VARCHAR(32) NOT NULL, -- 'scheduled', 'manual'
    status VARCHAR(16) NOT NULL, -- 'success', 'stopped', 'failed'
    success_checks JSONB,
    version VARCHAR(64) NOT NULL, -- git commit sha
    cost_usd NUMERIC(10, 4) DEFAULT 0.0000
);

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(run_id),
    symbol VARCHAR(32) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    features JSONB NOT NULL,
    signal VARCHAR(16) NOT NULL, -- 'BUY', 'SELL', 'NEUTRAL'
    created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE TABLE IF NOT EXISTS proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(run_id),
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL, -- 'BUY', 'SELL'
    size NUMERIC(18, 8) NOT NULL,
    entry NUMERIC(18, 8) NOT NULL,
    stop NUMERIC(18, 8) NOT NULL,
    target NUMERIC(18, 8),
    rationale TEXT NOT NULL,
    evidence_refs JSONB NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING' -- 'PENDING', 'ACCEPTED', 'REJECTED'
);

CREATE TABLE IF NOT EXISTS gate_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES proposals(id),
    passed BOOLEAN NOT NULL,
    checks JSONB NOT NULL,
    reasons TEXT,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES proposals(id),
    idempotency_key UUID UNIQUE NOT NULL,
    broker_order_id VARCHAR(128),
    type VARCHAR(32) NOT NULL, -- 'LIMIT', 'STOP_LOSS_LIMIT'
    price NUMERIC(18, 8) NOT NULL,
    size NUMERIC(18, 8) NOT NULL,
    status VARCHAR(32) NOT NULL, -- 'SUBMITTED', 'FILLED', 'CANCELLED', 'REJECTED'
    mode VARCHAR(16) NOT NULL, -- 'PAPER', 'LIVE'
    created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE TABLE IF NOT EXISTS fills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES orders(id),
    price NUMERIC(18, 8) NOT NULL,
    size NUMERIC(18, 8) NOT NULL,
    fee NUMERIC(18, 8) NOT NULL DEFAULT 0,
    ts TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE TABLE IF NOT EXISTS positions (
    symbol VARCHAR(32) PRIMARY KEY,
    size NUMERIC(18, 8) NOT NULL,
    avg_price NUMERIC(18, 8) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts TIMESTAMPTZ PRIMARY KEY DEFAULT (NOW() AT TIME ZONE 'UTC'),
    equity NUMERIC(18, 4) NOT NULL,
    cash NUMERIC(18, 4) NOT NULL,
    peak NUMERIC(18, 4) NOT NULL,
    drawdown NUMERIC(8, 4) NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES proposals(id),
    order_hash VARCHAR(64) NOT NULL,
    approved_by VARCHAR(64) NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE TABLE IF NOT EXISTS reconciliations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    broker_state JSONB NOT NULL,
    db_state JSONB NOT NULL,
    match BOOLEAN NOT NULL,
    diff JSONB
);

CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    kind VARCHAR(64) NOT NULL,
    detail TEXT NOT NULL,
    resolved_by VARCHAR(64)
);

-- Seed pre-approved liquid cryptocurrency spot instruments
INSERT INTO instruments (symbol, venue, tick_size, min_size, allowed)
VALUES 
    ('BTC/USDT', 'binance', 0.01, 0.0001, TRUE),
    ('ETH/USDT', 'binance', 0.01, 0.001,  TRUE),
    ('SOL/USDT', 'binance', 0.01, 0.01,   TRUE)
ON CONFLICT (symbol) DO NOTHING;
