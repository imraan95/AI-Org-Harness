insert into ingestion_events (source, payload)
values ('anarlog', '{"raw": "example webhook payload"}'::jsonb);

select * from ingestion_events;