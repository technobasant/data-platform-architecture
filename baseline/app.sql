-- One request of the product: a customer opens their usage page, and their activity is
-- recorded. pgbench runs it at a fixed rate.
\set aid random(1, 6000)
\set uid random(1, 60000)
\set uacc 1 + :uid % 6000
BEGIN;
SELECT event_type, count(*) FROM events
 WHERE account_id = :aid AND event_at >= timestamptz '2026-09-23 00:00+00'
 GROUP BY event_type;
UPDATE users SET last_seen_at = now() WHERE user_id = :uid;
INSERT INTO events (account_id, user_id, event_type, platform, event_at, received_at)
 VALUES (:uacc, :uid, 'view_dashboard', 'web', now(), now());
END;
