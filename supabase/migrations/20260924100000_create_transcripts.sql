create table if not exists transcripts (
  id text primary key,
  meeting_title text not null,
  attendees text[] not null default '{}',
  meeting_date timestamptz not null,
  source text not null,
  raw_text text not null
);
