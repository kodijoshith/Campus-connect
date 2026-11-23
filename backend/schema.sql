-- Campus Connect schema. Run once in the Supabase SQL Editor.
-- This intentionally allows unauthenticated public access, per the project request.

create extension if not exists pgcrypto;

create table if not exists public.users (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    role text
);

create table if not exists public.events (
    id uuid primary key default gen_random_uuid(),
    organizer_id uuid not null references public.users(id) on delete cascade,
    title text not null,
    capacity integer not null check (capacity >= 0),
    status text not null default 'open'
);

create table if not exists public.registrations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    event_id uuid not null references public.events(id) on delete cascade,
    created_at timestamptz not null default now(),
    constraint registrations_user_event_unique unique (user_id, event_id)
);

create index if not exists events_organizer_id_idx on public.events (organizer_id);
create index if not exists registrations_event_created_at_idx
    on public.registrations (event_id, created_at);
create index if not exists registrations_user_created_at_idx
    on public.registrations (user_id, created_at desc);

-- Keep the capacity rule intact even if a client writes directly to the table.
create or replace function public.enforce_event_capacity()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
declare
    event_capacity integer;
    registered_count bigint;
begin
    select capacity into event_capacity
    from public.events
    where id = new.event_id
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'event_not_found';
    end if;

    select count(*) into registered_count
    from public.registrations
    where event_id = new.event_id;

    if registered_count >= event_capacity then
        raise exception using errcode = 'P0001', message = 'event_full';
    end if;
    return new;
end;
$$;

drop trigger if exists registrations_capacity_guard on public.registrations;
create trigger registrations_capacity_guard
    before insert on public.registrations
    for each row execute function public.enforce_event_capacity();

alter table public.users enable row level security;
alter table public.events enable row level security;
alter table public.registrations enable row level security;

drop policy if exists "Public can read users" on public.users;
create policy "Public can read users" on public.users
    for select to anon, authenticated using (true);

drop policy if exists "Public can read events" on public.events;
create policy "Public can read events" on public.events
    for select to anon, authenticated using (true);

drop policy if exists "Public can read registrations" on public.registrations;
create policy "Public can read registrations" on public.registrations
    for select to anon, authenticated using (true);

drop policy if exists "Anyone can register" on public.registrations;
create policy "Anyone can register" on public.registrations
    for insert to anon, authenticated with check (true);

grant usage on schema public to anon, authenticated;
grant select on public.users, public.events, public.registrations to anon, authenticated;
grant insert on public.registrations to anon, authenticated;

-- Serialize registrations per event so simultaneous requests cannot exceed capacity.
create or replace function public.register_for_event(p_user_id uuid, p_event_id uuid)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    event_capacity integer;
    registered_count bigint;
    new_registration public.registrations%rowtype;
begin
    select capacity into event_capacity
    from public.events
    where id = p_event_id
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'event_not_found';
    end if;

    select count(*) into registered_count
    from public.registrations
    where event_id = p_event_id;

    if registered_count >= event_capacity then
        raise exception using errcode = 'P0001', message = 'event_full';
    end if;

    insert into public.registrations (user_id, event_id)
    values (p_user_id, p_event_id)
    returning * into new_registration;

    return jsonb_build_object(
        'id', new_registration.id,
        'user_id', new_registration.user_id,
        'event_id', new_registration.event_id,
        'created_at', new_registration.created_at
    );
exception
    when unique_violation then
        raise exception using errcode = 'P0001', message = 'already_registered';
end;
$$;

grant execute on function public.register_for_event(uuid, uuid) to anon, authenticated;
