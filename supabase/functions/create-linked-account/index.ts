import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

const baseCorsHeaders = {
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-idempotency-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const REQUIRED_FIELDS: (keyof CreateLinkedAccountRequest)[] = [
  "email",
  "phone",
  "legal_business_name",
  "business_type",
  "contact_name",
];

type Address = {
  street1?: string;
  street2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
};

type Addresses = {
  registered?: Address;
  correspondence?: Address;
};

type Profile = {
  category?: string;
  subcategory?: string;
  description?: string;
  addresses?: Addresses;
};

type LegalInfo = {
  pan?: string;
  gst?: string;
  cin?: string;
  tan?: string;
};

type CreateLinkedAccountRequest = {
  email: string;
  phone: string;
  type?: string;
  reference_id?: string;
  legal_business_name: string;
  business_name?: string;
  business_type: string;
  contact_name: string;
  contact_email?: string;
  contact_phone?: string;
  profile?: Profile;
  addresses?: Addresses;
  legal_info?: LegalInfo;
  notes?: Record<string, string>;
  metadata?: Record<string, string>;
  capabilities?: Record<string, unknown>;
  tnc_accepted?: boolean;
  idempotency_key?: string;
};

type RazorpayError = {
  error?: {
    code?: string;
    description?: string;
    field?: string;
    source?: string;
    step?: string;
    reason?: string;
    metadata?: Record<string, unknown>;
  };
  [key: string]: unknown;
};

const withCors = (req: Request) => {
  const origin = req.headers.get("Origin") ?? "*";
  return {
    ...baseCorsHeaders,
    "Access-Control-Allow-Origin": origin,
    "Vary": "Origin",
  };
};

const pruneUndefined = (value: unknown): unknown => {
  if (value === null || value === undefined) {
    return undefined;
  }

  if (Array.isArray(value)) {
    const pruned = value
      .map(pruneUndefined)
      .filter((item) => item !== undefined);
    return pruned.length ? pruned : undefined;
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .map(([key, val]) => [key, pruneUndefined(val)] as const)
      .filter(([, val]) => val !== undefined);

    if (!entries.length) {
      return undefined;
    }

    return Object.fromEntries(entries);
  }

  return value;
};

const buildPayload = (
  input: CreateLinkedAccountRequest,
  fallbackReferenceId: string,
): Record<string, unknown> => {
  const profile = pruneUndefined({
    ...input.profile,
    addresses: input.profile?.addresses ?? input.addresses,
  });

  return pruneUndefined({
    type: input.type ?? "route",
    reference_id: input.reference_id ?? fallbackReferenceId,
    email: input.email,
    phone: input.phone,
    legal_business_name: input.legal_business_name,
    business_name: input.business_name ?? input.legal_business_name,
    business_type: input.business_type,
    contact_name: input.contact_name,
    contact_email: input.contact_email ?? input.email,
    contact_phone: input.contact_phone ?? input.phone,
    profile,
    legal_info: input.legal_info,
    notes: input.notes,
    metadata: input.metadata,
    capabilities: input.capabilities,
    tnc_accepted: input.tnc_accepted ?? true,
  }) as Record<string, unknown>;
};

serve(async (req) => {
  const corsHeaders = withCors(req);

  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response(
      JSON.stringify({
        success: false,
        message: "Only POST is allowed",
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 405,
      },
    );
  }

  const requestId = crypto.randomUUID();

  let body: CreateLinkedAccountRequest;
  try {
    body = await req.json();
  } catch (error) {
    console.error(`[${requestId}] Invalid JSON body`, error);
    return new Response(
      JSON.stringify({
        success: false,
        requestId,
        message: "Invalid JSON body",
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 400,
      },
    );
  }

  const missingFields = REQUIRED_FIELDS.filter((field) => {
    const value = body[field];
    return value === undefined || value === null || value === "";
  });

  if (missingFields.length) {
    return new Response(
      JSON.stringify({
        success: false,
        requestId,
        message: "Missing required fields",
        missingFields,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 400,
      },
    );
  }

  const keyId = Deno.env.get("RAZOR_PAY_KEY_ID") ??
    Deno.env.get("RAZORPAY_KEY_ID");
  const keySecret = Deno.env.get("RAZOR_PAY_KEY_SECERET") ??
    Deno.env.get("RAZORPAY_KEY_SECRET");

  if (!keyId || !keySecret) {
    console.error(`[${requestId}] Razorpay credentials are not configured`);
    return new Response(
      JSON.stringify({
        success: false,
        requestId,
        message: "Razorpay credentials are not configured",
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 500,
      },
    );
  }

  const payload = buildPayload(
    body,
    body.reference_id ?? `supabase_${requestId}`,
  );
  const idempotencyKey = body.idempotency_key ?? requestId;

  let razorpayResponse: Response;
  try {
    razorpayResponse = await fetch("https://api.razorpay.com/v2/accounts", {
      method: "POST",
      headers: {
        "Authorization": `Basic ${btoa(`${keyId}:${keySecret}`)}`,
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    console.error(`[${requestId}] Network error`, error);
    return new Response(
      JSON.stringify({
        success: false,
        requestId,
        message: "Unable to reach Razorpay",
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 502,
      },
    );
  }

  let responseBody: unknown;
  try {
    responseBody = await razorpayResponse.json();
  } catch {
    responseBody = await razorpayResponse.text();
  }

  if (!razorpayResponse.ok) {
    console.error(
      `[${requestId}] Razorpay error`,
      responseBody,
    );
    const errorPayload: RazorpayError = typeof responseBody === "object"
      ? (responseBody as RazorpayError)
      : { error: { description: String(responseBody) } };

    return new Response(
      JSON.stringify({
        success: false,
        requestId,
        message: "Razorpay returned an error",
        status: razorpayResponse.status,
        error: errorPayload.error ?? errorPayload,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: razorpayResponse.status,
      },
    );
  }

  return new Response(
    JSON.stringify({
      success: true,
      requestId,
      account: responseBody,
    }),
    {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 200,
    },
  );
});

