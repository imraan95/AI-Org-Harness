insert into transcripts (id, meeting_title, attendees, meeting_date, source, raw_text)
values ('meeting_test', 'Test Meeting', array['Alice','Bob'], now(), 'anarlog', 'Some transcript text');

insert into transcript_chunks (id, transcript_id, text, embedding, "order")
values ('chunk_test', 'meeting_test', 'Three enterprise customers have asked for SSO.', '[0.1,0.2,0.3]'::vector, 0);

select id, transcript_id, text, embedding, "order" from transcript_chunks where id = 'chunk_test';