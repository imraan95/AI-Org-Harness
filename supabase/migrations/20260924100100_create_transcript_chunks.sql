create extension if not exists vector;

create table if not exists transcript_chunks (
  id text primary key,
  transcript_id text not null references transcripts(id),
  text text not null,
  embedding vector,
  "order" int not null
);
