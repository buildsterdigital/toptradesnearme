-- Top Trades Near Me: firm dashboard database (Supabase / Postgres).
-- Run once in the Supabase SQL editor. Safe to re-run: it only creates what is missing.
--
-- Who can see what (row level security):
--   * A firm user sees only their own firm, their own purchases and change requests.
--   * Open leads are visible to logged-in firms WITHOUT the homeowner's details.
--   * Homeowner details are visible only to firms that bought that lead.
--   * Only the admin (service role, used by John and the edge functions) can add
--     leads, link users to firms, approve changes or record purchases.

create table if not exists public.firms (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,             -- matches data.json "firms" key and /firm/<slug>/
  name text not null,
  trades text[] not null default '{}',   -- roofers, plumbers, driveways
  towns text[] not null default '{}',    -- town slugs they want leads from
  phone text, website text, about text,
  services text[] not null default '{}',
  created_at timestamptz not null default now()
);

-- Which login belongs to which firm (one firm can have more than one login).
create table if not exists public.firm_users (
  user_id uuid primary key references auth.users on delete cascade,
  firm_id uuid not null references public.firms on delete cascade
);

-- A homeowner's job, offered for sale. No personal details in this table.
create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  trade text not null,
  town text not null,                    -- town slug
  summary text not null,                 -- job summary, no names or addresses
  price_pence int not null,              -- shared price
  exclusive_price_pence int,             -- null = not offered exclusive
  max_buyers int not null default 3 check (max_buyers between 1 and 3),
  status text not null default 'open' check (status in ('draft', 'open', 'closed')),
  created_at timestamptz not null default now()
);

-- The homeowner's details, kept apart so firms only see them after buying.
create table if not exists public.lead_contacts (
  lead_id uuid primary key references public.leads on delete cascade,
  name text not null, phone text, email text, postcode text, details text,
  consent_at timestamptz not null        -- when they agreed to be passed to up to 3 firms
);

create table if not exists public.lead_purchases (
  lead_id uuid not null references public.leads on delete cascade,
  firm_id uuid not null references public.firms on delete cascade,
  exclusive boolean not null default false,
  amount_pence int not null,
  stripe_session text unique,
  created_at timestamptz not null default now(),
  primary key (lead_id, firm_id)
);

-- Edits a firm asks for. John approves them before they go on the public site.
create table if not exists public.change_requests (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms on delete cascade,
  changes jsonb not null,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  note text,
  created_at timestamptz not null default now()
);

-- The firm id of whoever is logged in.
create or replace function public.my_firm() returns uuid
language sql stable security definer set search_path = public as
$$ select firm_id from public.firm_users where user_id = auth.uid() $$;

-- How many firms have bought a lead (firms can't see each other's purchases).
create or replace function public.lead_sold(l uuid) returns int
language sql stable security definer set search_path = public as
$$ select count(*)::int from public.lead_purchases where lead_id = l $$;

-- Open leads for the logged-in firm's trades, with sold count and whether they bought it.
create or replace view public.lead_board with (security_invoker = true) as
select l.id, l.trade, l.town, l.summary, l.price_pence, l.exclusive_price_pence, l.max_buyers,
       l.created_at, public.lead_sold(l.id) as sold,
       exists (select 1 from public.lead_purchases p where p.lead_id = l.id and p.firm_id = public.my_firm()) as mine
from public.leads l
where l.status = 'open';

alter table public.firms enable row level security;
alter table public.firm_users enable row level security;
alter table public.leads enable row level security;
alter table public.lead_contacts enable row level security;
alter table public.lead_purchases enable row level security;
alter table public.change_requests enable row level security;

drop policy if exists "own firm" on public.firms;
create policy "own firm" on public.firms for select using (id = public.my_firm());

drop policy if exists "own link" on public.firm_users;
create policy "own link" on public.firm_users for select using (user_id = auth.uid());

drop policy if exists "open leads in my trades" on public.leads;
create policy "open leads in my trades" on public.leads for select using (
  public.my_firm() is not null
  and (status = 'open' or exists (select 1 from public.lead_purchases p where p.lead_id = leads.id and p.firm_id = public.my_firm()))
  and trade = any (select unnest(trades) from public.firms where id = public.my_firm()));

drop policy if exists "contacts of leads I bought" on public.lead_contacts;
create policy "contacts of leads I bought" on public.lead_contacts for select using (
  exists (select 1 from public.lead_purchases p where p.lead_id = lead_contacts.lead_id and p.firm_id = public.my_firm()));

drop policy if exists "my purchases" on public.lead_purchases;
create policy "my purchases" on public.lead_purchases for select using (firm_id = public.my_firm());

drop policy if exists "my change requests" on public.change_requests;
create policy "my change requests" on public.change_requests for select using (firm_id = public.my_firm());
drop policy if exists "ask for a change" on public.change_requests;
create policy "ask for a change" on public.change_requests for insert with check (firm_id = public.my_firm() and status = 'pending');

-- Records a paid purchase, refusing it once a lead is full. Called only by the
-- Stripe webhook (service role). Locks the lead row so two payments at the same
-- moment can't both take the last place.
create or replace function public.record_purchase(l uuid, f uuid, excl boolean, amount int, session text)
returns boolean language plpgsql security definer set search_path = public as
$$
declare n int; cap int; st text;
begin
  select max_buyers, status into cap, st from public.leads where id = l for update;
  -- Stripe can send the same event twice: a payment already recorded is fine.
  if exists (select 1 from public.lead_purchases where stripe_session = session) then return true; end if;
  if st is distinct from 'open' then return false; end if;
  select count(*) into n from public.lead_purchases where lead_id = l;
  if excl and n > 0 then return false; end if;
  if n >= cap then return false; end if;
  insert into public.lead_purchases (lead_id, firm_id, exclusive, amount_pence, stripe_session)
  values (l, f, excl, amount, session) on conflict do nothing;
  if excl or n + 1 >= cap then update public.leads set status = 'closed' where id = l; end if;
  return true;
end $$;
revoke execute on function public.record_purchase from public, anon, authenticated;
