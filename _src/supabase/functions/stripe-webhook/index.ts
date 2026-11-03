// Stripe calls this when a lead payment completes. It records the purchase, which
// releases the homeowner's details to that firm in the dashboard. If the lead filled
// up while the firm was paying, the payment is refunded straight away.
// Deploy with --no-verify-jwt (Stripe does not send a Supabase login).
// Secrets: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET.
import Stripe from "npm:stripe@14.25.0";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, { apiVersion: "2024-06-20" });

Deno.serve(async (req) => {
  const sig = req.headers.get("stripe-signature") ?? "";
  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(await req.text(), sig, Deno.env.get("STRIPE_WEBHOOK_SECRET")!);
  } catch {
    return new Response("bad signature", { status: 400 });
  }
  if (event.type !== "checkout.session.completed") return new Response("ignored");

  const s = event.data.object as Stripe.Checkout.Session;
  const m = s.metadata ?? {};
  if (!m.lead_id || s.payment_status !== "paid") return new Response("not a lead payment");

  const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const { data: ok, error } = await admin.rpc("record_purchase", {
    l: m.lead_id, f: m.firm_id, excl: m.exclusive === "1", amount: s.amount_total, session: s.id,
  });
  if (error) return new Response(error.message, { status: 500 }); // Stripe retries
  if (!ok) await stripe.refunds.create({ payment_intent: s.payment_intent as string, reason: "duplicate" });
  return new Response(ok ? "recorded" : "refunded");
});
