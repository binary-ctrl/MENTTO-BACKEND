# Google Calendar Credentials Sync Flow Documentation

## Overview

This document provides a detailed explanation of how the Google Calendar credentials syncing works in the Mento Backend system. The flow enables users (mentors and mentees) to connect their Google Calendar accounts, allowing the platform to access their calendar availability and schedule meetings.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [OAuth 2.0 Flow](#oauth-20-flow)
3. [Detailed Step-by-Step Flow](#detailed-step-by-step-flow)
4. [API Endpoints](#api-endpoints)
5. [Database Schema](#database-schema)
6. [Token Management](#token-management)
7. [Security Considerations](#security-considerations)
8. [Error Handling](#error-handling)
9. [Testing Endpoints](#testing-endpoints)

---

## Architecture Overview

### Key Components

| Component | File Path | Responsibility |
|-----------|-----------|----------------|
| **Calendar Routes** | `app/api/calendar/routes.py` | API endpoints for calendar operations |
| **Calendar Service** | `app/services/calendar/calendar_service.py` | Google Calendar API interaction |
| **Credentials Service** | `app/services/calendar/calendar_credentials_service.py` | Credential storage and retrieval |
| **Database** | Supabase `users` table | OAuth token persistence |

### Technology Stack

- **OAuth Provider**: Google OAuth 2.0
- **Calendar API**: Google Calendar API v3
- **Storage**: Supabase PostgreSQL
- **Authentication**: Firebase Auth + JWT
- **API Framework**: FastAPI

---

## OAuth 2.0 Flow

### Required Scopes

```python
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]
```

These scopes provide:
- Full calendar access (read/write)
- Create, read, update, and delete calendar events
- Access to free/busy information

### OAuth Configuration

Environment variables required:
```bash
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_CALENDAR_REDIRECT_URI=https://your-backend.com/api/calendar/callback
```

---

## Detailed Step-by-Step Flow

### Step 1: Initiation Phase

**Endpoint**: `GET /api/calendar/auth` or `GET /api/calendar/auth-url`

**Process**:
```
User Request 
    ↓
Validate OAuth Config (client_id, client_secret, redirect_uri)
    ↓
Check if credentials exist in database
    ↓
    ├─ If EXISTS:
    │   ├─ Attempt to sync with existing credentials
    │   ├─ If sync succeeds → Return success + sync results
    │   └─ If sync fails → Continue to re-authorization
    │
    └─ If NOT EXISTS or sync failed:
        └─ Generate Google OAuth authorization URL
```

**Code Flow**:
```python
# 1. Validate configuration
_validate_calendar_oauth_config()

# 2. Check existing credentials
has_credentials = await calendar_credentials_service.has_calendar_credentials(user_id)

# 3. Try sync if credentials exist
if has_credentials:
    credentials = await calendar_credentials_service.get_calendar_credentials(user_id)
    sync_result = await calendar_service.sync_calendar_events(user_id, credentials)
    # Update last sync time
    await calendar_credentials_service.update_last_sync(user_id)

# 4. Generate auth URL if needed
auth_url = calendar_service.get_authorization_url(user_id)
```

**Response**:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?client_id=...",
  "already_connected": false,
  "message": "Redirect user to this URL to grant calendar permissions",
  "user_id": "user123"
}
```

### Step 2: Authorization URL Generation

**Service Method**: `calendar_service.get_authorization_url(user_id)`

**Process**:
```python
flow = Flow.from_client_config(
    {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [calendar_redirect_uri]
        }
    },
    scopes=SCOPES
)

authorization_url, state = flow.authorization_url(
    access_type='offline',          # Request refresh token
    include_granted_scopes='false',  # Fresh permissions only
    prompt='consent',                # Force consent screen
    state=user_id                    # Track user through flow
)
```

**URL Parameters**:
- `client_id`: Your Google OAuth client ID
- `redirect_uri`: Where Google redirects after auth
- `scope`: Calendar access scopes
- `state`: User ID (for security and tracking)
- `access_type=offline`: Ensures refresh token is provided
- `prompt=consent`: Forces user to see permission screen

### Step 3: User Authorization

**Process**:
```
Frontend redirects user to authorization_url
    ↓
User lands on Google OAuth consent screen
    ↓
User reviews requested permissions:
    - View and manage calendars
    - Create and manage calendar events
    ↓
User clicks "Allow"
    ↓
Google redirects to: {redirect_uri}?code=AUTH_CODE&state=USER_ID
```

### Step 4: OAuth Callback

**Endpoint**: `GET /api/calendar/callback?code={code}&state={user_id}`

**Process Flow**:
```python
# 1. Receive callback parameters
code = request.query_params.get('code')
state = request.query_params.get('state')  # Contains user_id
error = request.query_params.get('error')

# 2. Handle errors
if error:
    raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

# 3. Exchange authorization code for credentials
credentials_data = calendar_service.exchange_code_for_credentials(code, user_id)

# 4. Store credentials in database
credentials_stored = await calendar_credentials_service.store_calendar_credentials(
    user_id, 
    credentials_data
)

# 5. Perform initial sync
sync_result = await calendar_service.sync_calendar_events(
    user_id=user_id,
    credentials_data=credentials_data
)

# 6. Update last sync time
await calendar_credentials_service.update_last_sync(user_id)

# 7. Get user role and redirect appropriately
user = await user_service.get_user_by_id(user_id)
if user.role == "mentor":
    redirect_url = f"{settings.frontend_url}/dashboard/mentor?tab=calls"
elif user.role == "mentee":
    redirect_url = f"{settings.frontend_url}/calls"
else:
    redirect_url = f"{settings.frontend_url}/dashboard"

return RedirectResponse(url=redirect_url)
```

### Step 5: Token Exchange

**Service Method**: `calendar_service.exchange_code_for_credentials(code, user_id)`

**Process**:
```python
flow = Flow.from_client_config(client_config, scopes=SCOPES)
flow.redirect_uri = calendar_redirect_uri

# Exchange code for tokens
flow.fetch_token(code=code)
credentials = flow.credentials

# Extract credential data
credentials_data = {
    'token': credentials.token,                    # Access token
    'refresh_token': credentials.refresh_token,    # Refresh token
    'token_uri': credentials.token_uri,            # Token refresh endpoint
    'client_id': credentials.client_id,            # OAuth client ID
    'client_secret': credentials.client_secret,    # OAuth client secret
    'scopes': credentials.scopes                   # Granted scopes
}
```

**Returned Data Structure**:
```json
{
  "token": "ya29.a0AfH6SMBx...",
  "refresh_token": "1//0gX8pN2zK...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "123456789.apps.googleusercontent.com",
  "client_secret": "your_client_secret",
  "scopes": [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events"
  ]
}
```

### Step 6: Credential Storage

**Service Method**: `calendar_credentials_service.store_calendar_credentials(user_id, credentials_data)`

**Database Operation**:
```python
# Add metadata to credentials
credentials_with_metadata = {
    **credentials_data,
    'stored_at': datetime.utcnow().isoformat(),
    'last_sync': None  # Will be updated after first sync
}

# Update database
result = supabase.table("users").update({
    "google_calendar_credentials": credentials_with_metadata
}).eq("user_id", user_id).execute()
```

**Database Storage Structure**:
```json
{
  "user_id": "user123",
  "email": "user@example.com",
  "google_calendar_credentials": {
    "token": "ya29.a0AfH6SMBx...",
    "refresh_token": "1//0gX8pN2zK...",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "123456789.apps.googleusercontent.com",
    "client_secret": "your_client_secret",
    "scopes": [
      "https://www.googleapis.com/auth/calendar",
      "https://www.googleapis.com/auth/calendar.events"
    ],
    "stored_at": "2025-10-10T12:00:00.000000",
    "last_sync": null
  }
}
```

### Step 7: Calendar Sync

**Service Method**: `calendar_service.sync_calendar_events(user_id, credentials_data)`

**Process Flow**:
```python
# 1. Build Google Calendar service
self.build_service(credentials_data)

# 2. Set date range (default: next 30 days)
start_date = datetime.utcnow()
end_date = start_date + timedelta(days=30)

# 3. Fetch events from Google Calendar
events_result = self.service.events().list(
    calendarId='primary',
    timeMin=start_date.isoformat() + 'Z',
    timeMax=end_date.isoformat() + 'Z',
    singleEvents=True,
    orderBy='startTime'
).execute()

events = events_result.get('items', [])

# 4. Process events
synced_events = []
for event in events:
    event_data = {
        'google_event_id': event.get('id'),
        'title': event.get('summary', 'No Title'),
        'description': event.get('description', ''),
        'start_time': event['start'].get('dateTime', event['start'].get('date')),
        'end_time': event['end'].get('dateTime', event['end'].get('date')),
        'attendees': [a.get('email') for a in event.get('attendees', [])],
        'location': event.get('location', ''),
        'status': event.get('status', 'confirmed'),
        'user_id': user_id
    }
    synced_events.append(event_data)

# 5. Return sync results
return {
    'success': True,
    'events_synced': len(synced_events),
    'events': synced_events,
    'last_sync': datetime.utcnow()
}
```

### Step 8: Update Last Sync Time

**Service Method**: `calendar_credentials_service.update_last_sync(user_id)`

```python
# Get current credentials
credentials = await self.get_calendar_credentials(user_id)

# Update last sync timestamp
credentials['last_sync'] = datetime.utcnow().isoformat()

# Store back to database
result = supabase.table("users").update({
    "google_calendar_credentials": credentials
}).eq("user_id", user_id).execute()
```

---

## API Endpoints

### Authentication & Authorization

#### 1. Initiate Calendar Authorization
```http
GET /api/calendar/auth
Authorization: Bearer {jwt_token}
```

**Response**:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "already_connected": false,
  "message": "Redirect user to this URL to grant calendar permissions",
  "user_id": "user123"
}
```

#### 2. Get Authorization URL (JSON Response)
```http
GET /api/calendar/auth-url
Authorization: Bearer {jwt_token}
```

**Response**: Same as above, but always returns JSON (no redirect)

#### 3. Direct Redirect to Google OAuth
```http
GET /api/calendar/auth-redirect
Authorization: Bearer {jwt_token}
```

**Response**: 302 Redirect to Google OAuth or frontend dashboard if already connected

#### 4. OAuth Callback
```http
GET /api/calendar/callback?code={code}&state={user_id}
```

**Response**: 302 Redirect to appropriate frontend page

#### 5. Force Re-authorization
```http
GET /api/calendar/auth/force
Authorization: Bearer {jwt_token}
```

Clears existing credentials and generates fresh auth URL.

### Calendar Operations

#### 6. Check Calendar Status
```http
GET /api/calendar/status
Authorization: Bearer {jwt_token}
```

**Response**:
```json
{
  "user_id": "user123",
  "calendar_connected": true,
  "last_sync": "2025-10-10T12:30:00.000000",
  "credentials_stored_at": "2025-10-10T12:00:00.000000",
  "scopes": [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events"
  ],
  "message": "Calendar connected and ready for sync"
}
```

#### 7. Manual Sync
```http
POST /api/calendar/sync
Authorization: Bearer {jwt_token}
```

**Response**:
```json
{
  "success": true,
  "message": "Calendar synced successfully",
  "user_id": "user123",
  "sync_result": {
    "success": true,
    "events_synced": 15,
    "events": [...],
    "last_sync": "2025-10-10T12:35:00.000000"
  }
}
```

#### 8. Disconnect Calendar
```http
DELETE /api/calendar/disconnect
Authorization: Bearer {jwt_token}
```

**Response**:
```json
{
  "success": true,
  "message": "Calendar disconnected successfully",
  "user_id": "user123"
}
```

#### 9. Get Calendar Events
```http
POST /api/calendar/events
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "email": "user@example.com",
  "start_date": "2025-10-10",
  "end_date": "2025-10-17",
  "include_free_slots": true,
  "include_blocked_slots": true
}
```

**Response**:
```json
{
  "email": "user@example.com",
  "total_events": 15,
  "total_free_slots": 28,
  "total_blocked_slots": 10,
  "date_range": {
    "start": "2025-10-10",
    "end": "2025-10-17"
  },
  "events": [...],
  "free_slots": [...],
  "blocked_slots": [...]
}
```

---

## Database Schema

### Users Table - `google_calendar_credentials` Column

**Type**: JSONB

**Structure**:
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    google_calendar_credentials JSONB,
    -- other fields...
);
```

**Credential Object Schema**:
```typescript
interface GoogleCalendarCredentials {
  token: string;              // Access token (expires in ~1 hour)
  refresh_token: string;      // Refresh token (long-lived)
  token_uri: string;          // Google token endpoint
  client_id: string;          // OAuth client ID
  client_secret: string;      // OAuth client secret
  scopes: string[];           // Granted scopes
  stored_at: string;          // ISO timestamp when stored
  last_sync: string | null;   // ISO timestamp of last sync
}
```

**Example Query**:
```sql
-- Get user credentials
SELECT google_calendar_credentials 
FROM users 
WHERE user_id = 'user123';

-- Check if user has credentials
SELECT 
    user_id, 
    email,
    CASE 
        WHEN google_calendar_credentials IS NOT NULL 
        THEN true 
        ELSE false 
    END as has_credentials
FROM users 
WHERE user_id = 'user123';

-- Update credentials
UPDATE users 
SET google_calendar_credentials = '{"token": "...", ...}'::jsonb
WHERE user_id = 'user123';

-- Remove credentials
UPDATE users 
SET google_calendar_credentials = NULL
WHERE user_id = 'user123';
```

---

## Token Management

### Access Token Lifecycle

1. **Token Duration**: ~1 hour
2. **Automatic Refresh**: Handled by `build_service()` method
3. **Refresh Process**:
   ```python
   credentials = Credentials.from_authorized_user_info(credentials_data, SCOPES)
   
   if not credentials.valid:
       if credentials.expired and credentials.refresh_token:
           credentials.refresh(Request())  # Auto-refresh
   ```

### Token Refresh Flow

```
User makes API request
    ↓
Retrieve stored credentials from DB
    ↓
Check token validity
    ↓
Is token valid? ──No──> Is refresh_token available?
    │                           │
    Yes                        Yes
    │                           │
    ↓                           ↓
Use existing token      Exchange refresh_token for new access_token
    │                           │
    │                           ↓
    │                   Update stored credentials in DB
    │                           │
    └───────────┬───────────────┘
                ↓
    Make Google Calendar API call
```

### Refresh Token Security

- **Storage**: Encrypted in database (JSONB column)
- **Lifetime**: Long-lived (can be years)
- **Revocation**: Can be revoked by:
  - User disconnecting calendar
  - User revoking app access in Google Account settings
  - Force re-authorization endpoint

---

## Security Considerations

### 1. State Parameter
- Contains `user_id` to track OAuth flow
- Prevents CSRF attacks
- Validated on callback

### 2. Credential Storage
- Stored in database JSONB column
- Database encryption at rest (Supabase default)
- Never exposed in API responses
- Only accessible by authenticated users

### 3. Token Exposure
```python
# ❌ BAD - Don't do this
return {
    "credentials": credentials_data  # Exposes tokens!
}

# ✅ GOOD - Safe status response
return {
    "calendar_connected": True,
    "last_sync": last_sync_time,
    "message": "Calendar connected"
}
```

### 4. Access Control
- All endpoints require authentication (`get_current_user` dependency)
- Users can only access their own calendar data
- Email verification on calendar access:
  ```python
  if request.email != current_user.email:
      raise HTTPException(status_code=403, detail="Forbidden")
  ```

### 5. Scope Limitation
- Only request necessary scopes
- Current scopes: `calendar`, `calendar.events`
- Can be restricted further if needed

---

## Error Handling

### Common Error Scenarios

#### 1. Missing OAuth Configuration
```python
HTTPException(
    status_code=500,
    detail="Google OAuth not configured for calendar"
)
```

**Solution**: Set environment variables

#### 2. No Stored Credentials
```python
HTTPException(
    status_code=400,
    detail="Calendar not connected. Please authorize calendar access first."
)
```

**Solution**: Redirect user to `/calendar/auth`

#### 3. Expired/Invalid Token
```python
# Automatically handled by token refresh
credentials.refresh(Request())
```

**Fallback**: If refresh fails, prompt re-authorization

#### 4. Google API Error
```python
except HttpError as e:
    logger.error(f"Google Calendar API error: {e}")
    raise Exception(f"Calendar sync failed: {e}")
```

**Common causes**:
- Rate limiting (429)
- Invalid credentials (401)
- Insufficient permissions (403)

#### 5. Sync Failure
```python
try:
    sync_result = await calendar_service.sync_calendar_events(...)
except Exception as sync_error:
    logger.warning(f"Failed to sync: {sync_error}")
    # Don't fail entire flow, just warn
```

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong",
  "status_code": 400
}
```

---

## Testing Endpoints

### Database Connection Test
```http
GET /api/calendar/test/database
```

### User Credentials Test
```http
GET /api/calendar/test/credentials/{email}
Authorization: Bearer {jwt_token}
```

### Calendar Data Fetching Test
```http
GET /api/calendar/test/calendar-data/{email}?start_date=2025-10-10&end_date=2025-10-17
Authorization: Bearer {jwt_token}
```

### Calendar Health Check
```http
GET /api/calendar/test/calendar-health
Authorization: Bearer {jwt_token}
```

**Response**:
```json
{
  "timestamp": "2025-10-10T12:40:00.000000",
  "user_id": "user123",
  "email": "user@example.com",
  "checks": {
    "calendar_connection": {
      "calendar_connected": true,
      "last_sync": "2025-10-10T12:35:00.000000"
    },
    "sync_status": {
      "has_credentials": true,
      "sync_age_hours": 0.08
    },
    "database_health": {
      "status": "healthy",
      "message": "Database connection working"
    }
  }
}
```

### Sync Monitoring
```http
GET /api/calendar/test/sync-monitoring
Authorization: Bearer {jwt_token}
```

---

## Flow Diagrams

### Complete OAuth Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER INITIATES CALENDAR SYNC                            │
│    GET /calendar/auth or /calendar/auth-url                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. CHECK EXISTING CREDENTIALS                               │
│    Query: users.google_calendar_credentials                 │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
    [EXISTS]              [NOT EXISTS]
         │                       │
         ▼                       │
┌──────────────────┐            │
│ Try Sync First   │            │
│ If success: Done │            │
│ If fail: Continue│            │
└────────┬─────────┘            │
         │                       │
         └───────────┬───────────┘
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. GENERATE GOOGLE OAUTH URL                                │
│    - Add scopes, state=user_id, access_type=offline        │
│    - Return authorization_url to user                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. USER REDIRECTED TO GOOGLE                                │
│    - User authenticates                                     │
│    - User grants calendar permissions                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. GOOGLE REDIRECTS BACK WITH CODE                          │
│    GET /calendar/callback?code=xxx&state=user_id            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. EXCHANGE CODE FOR TOKENS                                 │
│    - POST to Google token endpoint                          │
│    - Receive: access_token, refresh_token                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. STORE CREDENTIALS IN DATABASE                            │
│    UPDATE users SET google_calendar_credentials = {         │
│      token, refresh_token, stored_at, last_sync            │
│    } WHERE user_id = xxx                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. INITIAL SYNC                                             │
│    - Build Google Calendar service                          │
│    - Fetch events (next 30 days)                            │
│    - Update last_sync timestamp                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. REDIRECT USER TO APPROPRIATE PAGE                        │
│    - Mentor: /dashboard/mentor?tab=calls                    │
│    - Mentee: /calls                                         │
└─────────────────────────────────────────────────────────────┘
```

### Token Refresh Flow

```
┌─────────────────────────────────────────────────────────────┐
│ API REQUEST (with expired access token)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Retrieve credentials from database                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Create Credentials object                                   │
│ credentials = Credentials.from_authorized_user_info(...)    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Check: credentials.valid ?                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
           ┌─────────┴─────────┐
           │                   │
          YES                 NO
           │                   │
           │                   ▼
           │    ┌──────────────────────────────────┐
           │    │ Check: credentials.expired AND   │
           │    │        credentials.refresh_token?│
           │    └────────────┬─────────────────────┘
           │                 │
           │        ┌────────┴────────┐
           │       YES               NO
           │        │                 │
           │        ▼                 ▼
           │    ┌────────────┐   ┌─────────────┐
           │    │  Refresh   │   │ Re-auth     │
           │    │  Token     │   │ Required    │
           │    └─────┬──────┘   └─────────────┘
           │          │
           │          ▼
           │    ┌─────────────────────────────────┐
           │    │ POST to Google Token Endpoint   │
           │    │ with refresh_token              │
           │    └─────┬───────────────────────────┘
           │          │
           │          ▼
           │    ┌─────────────────────────────────┐
           │    │ Receive new access_token        │
           │    └─────┬───────────────────────────┘
           │          │
           │          ▼
           │    ┌─────────────────────────────────┐
           │    │ Update credentials in DB        │
           │    │ (optional - auto-used in memory)│
           │    └─────┬───────────────────────────┘
           │          │
           └──────────┴──────────┐
                                 │
                                 ▼
                    ┌────────────────────────────┐
                    │ Make Google Calendar API   │
                    │ call with valid token      │
                    └────────────────────────────┘
```

---

## Troubleshooting

### Issue: "Calendar not connected" Error

**Symptoms**: API returns 400 error saying calendar not connected

**Solutions**:
1. Check if user has completed OAuth flow
2. Verify credentials exist in database:
   ```sql
   SELECT google_calendar_credentials FROM users WHERE user_id = 'xxx';
   ```
3. If no credentials, redirect user to `/calendar/auth`

### Issue: Sync Fails with 401 Unauthorized

**Cause**: Token expired and refresh failed

**Solutions**:
1. Check if refresh_token is present in stored credentials
2. Use `/calendar/auth/force` to force re-authorization
3. Check Google Cloud Console for API quota issues

### Issue: "Missing state parameter" in Callback

**Cause**: OAuth flow interrupted or state not preserved

**Solution**: Ensure `state` parameter is passed through entire OAuth flow

### Issue: Events Not Syncing

**Symptoms**: Sync completes but no events returned

**Debug Steps**:
1. Check date range - may be outside event window
2. Verify calendar has events in Google Calendar UI
3. Check if events are on 'primary' calendar
4. Use test endpoint: `/calendar/test/calendar-data/{email}`

### Issue: Rate Limiting (429 Error)

**Cause**: Too many API requests to Google Calendar

**Solutions**:
1. Implement exponential backoff
2. Reduce sync frequency
3. Increase quota in Google Cloud Console
4. Cache calendar data to reduce API calls

---

## Best Practices

### 1. Token Refresh
- Always check token validity before API calls
- Implement automatic refresh
- Handle refresh failures gracefully

### 2. Error Handling
- Log all errors with context
- Don't expose sensitive data in error messages
- Provide user-friendly error messages
- Implement retry logic for transient failures

### 3. Security
- Never log or expose tokens
- Use HTTPS for all OAuth redirects
- Validate state parameter
- Implement CSRF protection
- Regular token rotation

### 4. Performance
- Cache calendar data when possible
- Implement batch operations for multiple users
- Use webhooks for real-time updates (future enhancement)
- Optimize database queries for credentials

### 5. User Experience
- Show clear connection status
- Provide easy re-authorization flow
- Display last sync time
- Handle disconnection gracefully

---

## Future Enhancements

### 1. Webhook Integration
Implement Google Calendar push notifications instead of polling:
```python
# Watch calendar for changes
watch_request = {
    'id': unique_channel_id,
    'type': 'web_hook',
    'address': 'https://backend.com/calendar/webhook'
}
service.events().watch(calendarId='primary', body=watch_request).execute()
```

### 2. Multiple Calendar Support
Currently only syncs 'primary' calendar. Could extend to:
- Secondary calendars
- Shared calendars
- Calendar-specific permissions

### 3. Enhanced Caching
- Redis cache for frequently accessed calendar data
- Invalidate cache on webhook events
- TTL-based cache expiration

### 4. Sync Optimization
- Delta sync (only fetch changed events)
- Use `syncToken` for incremental sync
- Parallel sync for multiple users

---

## Related Documentation

- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- [OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Documentation](https://supabase.com/docs)

---

## Contact & Support

For questions or issues related to calendar sync:
1. Check logs in application server
2. Review Google Cloud Console for API errors
3. Test endpoints for debugging
4. Review this documentation

---

*Last Updated: October 10, 2025*
*Version: 1.0*

