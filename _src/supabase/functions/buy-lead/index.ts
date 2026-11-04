// Starts a Stripe Checkout payment for a lead. Called from the firm dashboard.
// Body: { lead_id, exclusive }. The firm comes from the logged-in user, never the body.
// Secrets (set in Supabase > Edge Functions > Secrets): STRIPE_SECRET_KEY, SITE_URL.
import Stripe from "npm:stripe@14.25.0";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, { apiVersion: "2024-06-20" });
const SITE = Deno.env.get("SITE_URL") ?? "https://toptradesnearme.co.uk";
const cors = {
  "Access-Control-Allow-Origin": SITE,
  "Access-Control-Allow-Headers": "authorization, content-type, apikey, x-client-info",
};
const reply = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const token = (req.headers.get("Authorization") ?? "").replace("Bearer ", "");
  const { data: { user } } = await admin.auth.getUser(token);
  if (!user) return reply(401, { error: "Please log in again." });

  const { lead_id, exclusive } = await req.json();
  const { data: link } = await admin.from("firm_users").select("firm_id, firms(name, trades)").eq("user_id", user.id).single();
  if (!link) return reply(403, { error: "This login is not linked to a firm yet. Email listings@toptradesnearme.co.uk." });

  const { data: lead } = await admin.from("leads").select("*").eq("id", lead_id).single();
  if (!lead || lead.status !== "open") return reply(409, { error: "Sorry, this lead has just sold out." });
  if (!(link.firms as { trades: string[] }).trades.includes(lead.trade)) return reply(403, { error: "This lead is for another trade." });

  const { count } = await admin.from("lead_purchases").select("*", { count: "exact", head: true }).eq("lead_id", lead_id);
  const { count: mine } = await admin.from("lead_purchases").select("*", { count: "exact", head: true }).eq("lead_id", lead_id).eq("firm_id", link.firm_id);
  if (mine) return reply(409, { error: "You already have this lead." });
  if ((count ?? 0) >= lead.max_buyers) return reply(409, { error: "Sorry, this lead has just sold out." });
  if (exclusive && ((count ?? 0) > 0 || !lead.exclusive_price_pence)) return reply(409, { error: "This lead can no longer be bought exclusively." });

  const amount = exclusive ? lead.exclusive_price_pence : lead.price_pence;
  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    customer_email: user.email,
    line_items: [{
      quantity: 1,
      price_data: {
        currency: "gbp",
        unit_amount: amount,
        product_data: { name: `${exclusive ? "Exclusive" : "Shared"} ${lead.trade} lead, ${lead.town}` },
      },
    }],
    metadata: { lead_id, firm_id: link.firm_id, exclusive: exclusive ? "1" : "0" },
    payment_intent_data: { metadata: { lead_id, firm_id: link.firm_id } },
    success_url: `${SITE}/dashboard/?bought=${lead_id}`,
    cancel_url: `${SITE}/dashboard/?tab=board`,
  });
  return reply(200, { url: session.url });
});
