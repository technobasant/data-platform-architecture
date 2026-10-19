-- Seeded data at the brief's scale: 6,000 accounts, 60,000 users, two years of invoices,
-- and 90 days of events (events.sql).
\set ON_ERROR_STOP on
\timing on
select setseed(0.42);

insert into plans values
    (1, 'free', 0), (2, 'team', 49), (3, 'business', 199), (4, 'enterprise', 899);

insert into accounts
select g, 'Account ' || g, 'account' || g || '.example',
       (array['software', 'retail', 'finance', 'health', 'media', 'education'])[1 + g % 6],
       (array['US', 'GB', 'DE', 'FR', 'NL', 'IN', 'AU', 'CA'])[1 + (g * 7) % 8],
       case when r < 0.45 then 1 when r < 0.80 then 2 when r < 0.95 then 3 else 4 end,
       case when r2 < 0.97 then 'active' else 'churned' end,
       timestamptz '2019-01-01 00:00+00'
         + random() * (timestamptz '2026-09-01 00:00+00' - timestamptz '2019-01-01 00:00+00'),
       timestamptz '2026-09-01 00:00+00'
from (select g, random() as r, random() as r2 from generate_series(1, 6000) as g) as s;

-- User u belongs to account 1 + u % 6000, so events can carry the account without a join.
insert into users
select u, 1 + u % 6000, 'user' || u || '@account' || (1 + u % 6000) || '.example',
       'User ' || u, (array['admin', 'member', 'member', 'viewer'])[1 + u % 4],
       timestamptz '2019-01-01 00:00+00' + (u % 2700) * interval '1 day', null
from generate_series(1, 60000) as u;

insert into invoices
select row_number() over (order by a.account_id, m), a.account_id, m, p.monthly_price_usd
from accounts as a
join plans as p using (plan_id)
cross join generate_series(timestamptz '2024-10-01 00:00+00', timestamptz '2026-09-01 00:00+00',
                           interval '1 month') as m
where p.monthly_price_usd > 0 and m >= date_trunc('month', a.signup_at);

\ir events.sql

create index users_account on users (account_id);
create index invoices_account on invoices (account_id);
vacuum analyze plans, accounts, users, invoices;
create table loaded_marker (loaded_at timestamptz default now());
insert into loaded_marker default values;
