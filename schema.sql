CREATE TYPE subscriptionstatus AS ENUM ('trial', 'active', 'expired', 'canceled');
CREATE TYPE billingperiod AS ENUM ('week', 'month');

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agents (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(120) NOT NULL,
  system_prompt TEXT NOT NULL,
  model_name VARCHAR(120) NOT NULL,
  token_limit INT NOT NULL,
  tools JSONB NOT NULL DEFAULT '{}'::jsonb,
  memory_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  behavior JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agent_memories (
  id SERIAL PRIMARY KEY,
  agent_id INT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  message TEXT NOT NULL,
  role VARCHAR(20) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE token_wallets (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  model_name VARCHAR(120) NOT NULL,
  balance BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, model_name)
);

CREATE TABLE token_usage_logs (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  agent_id INT REFERENCES agents(id) ON DELETE SET NULL,
  model_name VARCHAR(120) NOT NULL,
  request_tokens INT NOT NULL,
  response_tokens INT NOT NULL,
  total_tokens INT NOT NULL,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE subscriptions (
  id SERIAL PRIMARY KEY,
  user_id INT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status subscriptionstatus NOT NULL DEFAULT 'trial',
  tariff VARCHAR(60) NOT NULL DEFAULT 'free',
  period billingperiod,
  trial_ends_at TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ
);

CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider_payment_id VARCHAR(120) UNIQUE NOT NULL,
  amount_rub INT NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  period billingperiod NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scheduled_tasks (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  agent_id INT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  cron_expr VARCHAR(120),
  run_at TIMESTAMPTZ,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  active BOOLEAN NOT NULL DEFAULT TRUE
);
