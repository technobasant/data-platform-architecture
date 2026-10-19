-- Product events: 90 days are kept in Postgres; a nightly job deletes older ones.
-- 31.5 million rows, about 350,000 a day, ending 30 September 2026, written in arrival
-- order as the product appends them, so the table is laid out by time. Re-runnable.
\set ON_ERROR_STOP on
\timing on
select setseed(0.43);

drop table if exists events;
create table events (
    event_id bigint generated always as identity primary key,
    account_id bigint not null,
    user_id bigint not null,
    event_type text not null,
    platform text not null,
    event_at timestamptz not null,
    received_at timestamptz not null
);

-- User u belongs to account 1 + u % 6000 (see load.sql).
insert into events (account_id, user_id, event_type, platform, event_at, received_at)
select 1 + u % 6000, u,
       (array['login', 'view_dashboard', 'view_dashboard', 'create_report', 'share_report',
              'export_csv', 'invite_user', 'api_call'])[1 + floor(random() * 8)::int],
       (array['web', 'web', 'web', 'ios', 'android'])[1 + floor(random() * 5)::int],
       t, t + interval '30 seconds'
from (select 1 + floor(random() * 60000)::bigint as u,
             timestamptz '2026-07-02 00:00+00' + g * (interval '90 days' / 31500000) as t
      from generate_series(1, 31500000) as g) as s;

create index events_account_time on events (account_id, event_at);
create index events_time on events (event_at);
vacuum analyze events;
