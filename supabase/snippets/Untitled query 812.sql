insert into jobs (type, payload)
values ('transcript.ingested', '{"transcript_id": "meeting_test"}'::jsonb);

select * from jobs;