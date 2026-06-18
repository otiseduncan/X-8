-- XV8 operator runtime scaffold tables.
-- This migration is documentation-first for the future Alembic path.
CREATE TABLE IF NOT EXISTS operator_tasks (id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS operator_plan_steps (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS operator_actions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL, risk_level TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS operator_observations (id TEXT PRIMARY KEY, task_id TEXT, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS operator_jobs (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS operator_approvals (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, action_id TEXT NOT NULL, status TEXT NOT NULL, risk_level TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS operator_audit_events (id TEXT PRIMARY KEY, task_id TEXT, job_id TEXT, approval_id TEXT, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS operator_receipts (id TEXT PRIMARY KEY, task_id TEXT, action_id TEXT, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS operator_capabilities (id TEXT PRIMARY KEY, capability_id TEXT NOT NULL, status TEXT NOT NULL, risk_level TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
