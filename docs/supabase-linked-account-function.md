## Supabase Edge Function: `create-linked-account`

### Overview
- Proxies secure requests from Supabase to Razorpay’s `POST /v2/accounts` endpoint.
- Normalizes payload defaults (`type=route`, `tnc_accepted=true`, fallback `reference_id`).
- Validates required fields before sending to Razorpay and relays Razorpay response or errors with a `requestId` for tracing.
- Handles CORS so the function can be invoked directly from browsers or server-side code.

**File:** `supabase/functions/create-linked-account/index.ts`

### Environment variables
Set these secrets in the Supabase project (or `.env` file when running locally):

```
supabase functions secrets set RAZOR_PAY_KEY_ID=rzp_test_xxx
supabase functions secrets set RAZOR_PAY_KEY_SECERET=yyy
```

Aliases supported by the function: `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.

### Local development
```
cd /Users/vikaskamwal/Downloads/mentto-backend
supabase functions serve create-linked-account \
  --env-file supabase/.env.local \
  --no-verify-jwt
```

The `--no-verify-jwt` flag skips JWT checks locally; omit it in deployed environments so Supabase enforces auth automatically.

### Deploying
```
supabase functions deploy create-linked-account
```

### Request payload
Send a POST request with JSON body. Example:

```
curl -X POST <FUNCTION_URL> \
  -H "Authorization: Bearer <supabase_anon_or_service_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "gaurav.kumar@example.com",
    "phone": "9000090000",
    "type": "route",
    "reference_id": "124124",
    "legal_business_name": "Acme Corp",
    "business_type": "partnership",
    "contact_name": "Gaurav Kumar",
    "profile": {
      "category": "healthcare",
      "subcategory": "clinic",
      "addresses": {
        "registered": {
          "street1": "507, Koramangala 1st block",
          "street2": "MG Road",
          "city": "Bengaluru",
          "state": "KARNATAKA",
          "postal_code": "560034",
          "country": "IN"
        }
      }
    },
    "legal_info": {
      "pan": "AAACL1234C",
      "gst": "18AABCU9603R1ZM"
    }
  }'
```

### Response shape
- **Success (200):**
  ```
  {
    "success": true,
    "requestId": "...",
    "account": { ...razorpay_payload... }
  }
  ```
- **Error:** mirrors Razorpay’s error payload and HTTP status while adding `requestId` and `message`.

### Notes
- Supply `idempotency_key` in the request to control Razorpay idempotency; otherwise the function injects a UUID per call.
- Optional fields (`profile`, `legal_info`, `notes`, `metadata`, `capabilities`) may be omitted; undefined values are stripped automatically.

