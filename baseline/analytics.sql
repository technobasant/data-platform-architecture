-- The queries the BI tool runs today. Each is one statement, separated by a line "-- name".

-- revenue_by_plan_month
select date_trunc('month', i.invoiced_at) as month, p.plan_name, sum(i.amount_usd) as revenue
from invoices as i
join accounts as a using (account_id)
join plans as p using (plan_id)
group by 1, 2
order by 1, 2;

-- active_users_by_plan_day
select date_trunc('day', e.event_at) as day, a.plan_id, count(distinct e.user_id) as active_users
from events as e
join accounts as a using (account_id)
where e.event_at >= timestamptz '2026-07-02 00:00+00'
group by 1, 2
order by 1, 2;

-- weekly_event_mix
select date_trunc('week', event_at) as week, event_type, count(*) as events,
       count(distinct account_id) as accounts
from events
group by 1, 2
order by 1, 2;

-- top_accounts_30d
select account_id, count(*) as events, count(distinct user_id) as users
from events
where event_at >= timestamptz '2026-08-31 00:00+00'
group by account_id
order by events desc
limit 50;
