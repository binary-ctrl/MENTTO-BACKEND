# Mentor Payout System - Curl Commands

## 🎯 **Complete Flow: Mentee pays → 70% goes to Mentor after 7 days**

---

## 📋 **Step 1: Mentor Onboarding**

### **Setup Mentor Account**
```bash
curl --location 'http://localhost:8000/mentors/{mentor_user_id}/setup' \
--header 'Authorization: Bearer YOUR_JWT_TOKEN' \
--header 'Content-Type: application/json' \
--data-raw '{
    "business_name": "John Doe Consulting",
    "business_type": "individual",
    "business_registration_number": null,
    "business_pan": "ABCDE1234F",
    "business_gst": null,
    "contact_name": "John Doe",
    "contact_email": "john.doe@example.com",
    "contact_mobile": "+919876543210",
    "address": {
        "street": "123 Main Street",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postal_code": "400001",
        "country": "IN"
    }
}'
```

**✅ Response:**
```json
{
  "success": true,
  "message": "Mentor setup completed successfully",
  "data": {
    "id": "uuid-here",
    "user_id": "mentor-user-id",
    "razorpay_account_id": "acc_XXXX",
    "is_payout_ready": true,
    "kyc_status": "pending",
    "created_at": "2025-01-19T10:30:00Z",
    "updated_at": "2025-01-19T10:30:00Z"
  }
}
```

### **Check Mentor Status**
```bash
curl --location 'http://localhost:8000/mentors/{mentor_user_id}/status' \
--header 'Authorization: Bearer YOUR_JWT_TOKEN'
```

---

## 📋 **Step 2: Create Session & Payment**

### **Create Session (Mentee creates session with Mentor)**
```bash
curl --location 'http://localhost:8000/mentors/sessions' \
--header 'Authorization: Bearer YOUR_JWT_TOKEN' \
--header 'Content-Type: application/json' \
--data-raw '{
    "mentor_id": "mentor-user-id",
    "title": "Career Guidance Session",
    "description": "One-on-one career guidance session",
    "scheduled_at": "2025-01-25T14:00:00Z",
    "duration_minutes": 60,
    "amount": 1000.00
}'
```

### **Create Payment Order**
```bash
curl --location 'http://localhost:8000/mentors/sessions/{session_id}/pay' \
--header 'Authorization: Bearer YOUR_JWT_TOKEN' \
--header 'Content-Type: application/json'
```

**✅ Response:**
```json
{
  "success": true,
  "message": "Payment order created successfully",
  "data": {
    "session_id": "session-uuid",
    "razorpay_order_id": "order_XXXX",
    "amount": 1000.00,
    "currency": "INR",
    "key_id": "rzp_test_RHZoSdShUSqco6"
  }
}
```

---

## 📋 **Step 3: Frontend Payment**

Use the response data to open Razorpay Checkout:
```javascript
const options = {
  key: "rzp_test_RHZoSdShUSqco6",
  amount: 100000, // 1000.00 * 100 (in paise)
  currency: "INR",
  name: "Mentto",
  description: "Career Guidance Session",
  order_id: "order_XXXX",
  handler: function (response) {
    // Payment successful
    console.log(response);
  }
};

const rzp = new Razorpay(options);
rzp.open();
```

---

## 📋 **Step 4: Automatic Processing**

### **What Happens Automatically:**
1. ✅ **Payment Success** → Razorpay webhook calls your backend
2. ✅ **Payment Captured** → Status updated to "captured"
3. ✅ **Transfer Scheduled** → 70% (₹700) scheduled for 7 days later
4. ✅ **After 7 Days** → Transfer processed to mentor's account

### **Manual Transfer (if needed)**
```bash
curl --location 'http://localhost:8000/mentors/transfers/{payment_id}' \
--header 'Authorization: Bearer YOUR_JWT_TOKEN' \
--header 'Content-Type: application/json'
```

---

## 🎯 **Complete Flow Summary:**

### **For Mentors:**
1. **Setup Account** → `POST /mentors/{id}/setup`
2. **Wait for KYC** → Razorpay verifies account
3. **Receive Payouts** → 70% after 7 days

### **For Mentees:**
1. **Create Session** → `POST /mentors/sessions`
2. **Pay for Session** → `POST /mentors/sessions/{id}/pay`
3. **Complete Payment** → Frontend Razorpay Checkout

### **For Platform:**
1. **Receive Payment** → 100% goes to your account
2. **Hold for 7 Days** → Risk management
3. **Send 70% to Mentor** → Automatic transfer
4. **Keep 30%** → Platform fee

---

## 🚨 **Important Notes:**

### **Razorpay Setup Required:**
1. **Linked Accounts** → Enable in Razorpay Dashboard
2. **Webhooks** → Configure payment.captured events
3. **Transfers** → Enable in your Razorpay account

### **Database Tables:**
- `mentors` → Mentor accounts and Razorpay IDs
- `sessions` → Session details
- `session_payments` → Payment records
- `transfers` → Payout tracking

### **Security:**
- All endpoints require JWT authentication
- Users can only access their own data
- Transfers are processed automatically after 7 days

---

## 🔧 **Testing Flow:**

1. **Setup Mentor** → Create mentor account
2. **Create Session** → Mentee books session
3. **Make Payment** → Use test card: `4111 1111 1111 1111`
4. **Check Status** → Verify payment captured
5. **Wait 7 Days** → Transfer automatically processed

**Your 70:30 revenue split is now fully automated!** 🎉
