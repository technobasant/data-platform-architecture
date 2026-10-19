-- The application's own tables, as the product's database holds them today.
create table plans (
    plan_id int primary key,
    plan_name text not null,
    monthly_price_usd numeric(10, 2) not null
);
create table accounts (
    account_id bigint primary key,
    account_name text not null,
    domain text not null,
    industry text not null,
    country text not null,
    plan_id int not null references plans,
    status text not null,
    signup_at timestamptz not null,
    updated_at timestamptz not null
);
create table users (
    user_id bigint primary key,
    account_id bigint not null references accounts,
    email text not null,
    full_name text not null,
    role text not null,
    created_at timestamptz not null,
    last_seen_at timestamptz
);
create table invoices (
    invoice_id bigint primary key,
    account_id bigint not null references accounts,
    invoiced_at timestamptz not null,
    amount_usd numeric(10, 2) not null
);
-- events: see events.sql
