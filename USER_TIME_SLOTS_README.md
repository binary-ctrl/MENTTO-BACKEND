# User Time Slots API

This document describes the new User Time Slots functionality that allows users to create and manage their own time slots for taking calls.

## Overview

The User Time Slots feature enables users to:
- Create individual time slots with 45-minute intervals (or custom durations)
- Create multiple time slots in bulk based on date ranges and days of the week
- Manage timezone support for global users
- Track slot status (available, booked, blocked, cancelled)
- View summaries and upcoming available slots

## Database Schema

### user_time_slots Table

```sql
CREATE TABLE user_time_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'booked', 'blocked', 'cancelled')),
    is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
    recurring_pattern VARCHAR(20) CHECK (recurring_pattern IN ('daily', 'weekly', 'monthly')),
    recurring_end_date TIMESTAMPTZ,
    duration_minutes INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## API Endpoints

All endpoints are prefixed with `/users/time-slots/` and require authentication.

### 1. Create Single Time Slot

**POST** `/users/time-slots/`

Creates a single time slot for the current user.

**Request Body:**
```json
{
    "start_time": "2024-01-15T14:00:00",
    "end_time": "2024-01-15T14:45:00",
    "timezone": "Asia/Kolkata",
    "title": "Available for calls",
    "description": "I'm available for mentoring calls during this time",
    "is_recurring": false
}
```

**Response:**
```json
{
    "id": "uuid",
    "user_id": "uuid",
    "start_time": "2024-01-15T08:30:00Z",
    "end_time": "2024-01-15T09:15:00Z",
    "timezone": "Asia/Kolkata",
    "title": "Available for calls",
    "description": "I'm available for mentoring calls during this time",
    "status": "available",
    "is_recurring": false,
    "duration_minutes": 45,
    "start_time_local": "2024-01-15T14:00:00+05:30",
    "end_time_local": "2024-01-15T14:45:00+05:30",
    "timezone_offset": "+05:30",
    "created_at": "2024-01-14T10:00:00Z",
    "updated_at": "2024-01-14T10:00:00Z"
}
```

### 2. Create Bulk Time Slots

**POST** `/users/time-slots/bulk`

Creates multiple time slots based on date range and days of the week.

**Request Body:**
```json
{
    "start_date": "2024-01-15",
    "end_date": "2024-01-21",
    "start_time": "14:00",
    "end_time": "18:00",
    "timezone": "Asia/Kolkata",
    "days_of_week": [0, 1, 2, 3, 4],
    "title": "Mentoring Hours",
    "description": "Available for mentoring calls",
    "slot_duration_minutes": 45
}
```

**Response:**
```json
{
    "success": true,
    "message": "Successfully created 20 time slots",
    "slots_created": 20,
    "slots": [...],
    "date_range": {
        "start": "2024-01-15",
        "end": "2024-01-21"
    },
    "timezone": "Asia/Kolkata"
}
```

### 3. Get Time Slots

**GET** `/users/time-slots/`

Retrieves time slots for the current user with optional filtering.

**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format
- `status` (optional): Filter by status (available, booked, blocked, cancelled)
- `limit` (optional): Number of slots to return (default: 50, max: 100)
- `offset` (optional): Number of slots to skip (default: 0)

**Example:**
```
GET /users/time-slots/?start_date=2024-01-15&status=available&limit=10
```

### 4. Get Time Slot Summary

**GET** `/users/time-slots/summary`

Returns a summary of the user's time slots.

**Response:**
```json
{
    "total_slots": 25,
    "available_slots": 20,
    "booked_slots": 3,
    "blocked_slots": 2,
    "upcoming_slots": 15,
    "next_available_slot": {...},
    "recent_slots": [...]
}
```

### 5. Get Specific Time Slot

**GET** `/users/time-slots/{slot_id}`

Retrieves a specific time slot by ID.

### 6. Update Time Slot

**PUT** `/users/time-slots/{slot_id}`

Updates a time slot.

**Request Body:**
```json
{
    "title": "Updated title",
    "description": "Updated description",
    "status": "blocked"
}
```

### 7. Delete Time Slot

**DELETE** `/users/time-slots/{slot_id}`

Deletes a time slot.

### 8. Get Upcoming Available Slots

**GET** `/users/time-slots/available/upcoming`

Gets upcoming available time slots.

**Query Parameters:**
- `limit` (optional): Number of slots to return (default: 10, max: 50)

### 9. Book Time Slot

**POST** `/users/time-slots/{slot_id}/book`

Changes a slot's status to "booked".

### 10. Block Time Slot

**POST** `/users/time-slots/{slot_id}/block`

Changes a slot's status to "blocked".

### 11. Unblock Time Slot

**POST** `/users/time-slots/{slot_id}/unblock`

Changes a slot's status to "available".

## Timezone Support

The API supports multiple timezones:

- **UTC**: Coordinated Universal Time
- **Asia/Kolkata**: India Standard Time (IST)
- **America/New_York**: Eastern Standard Time (EST)
- **America/Los_Angeles**: Pacific Standard Time (PST)
- **Europe/London**: Greenwich Mean Time (GMT)
- **Europe/Paris**: Central European Time (CET)
- **Asia/Tokyo**: Japan Standard Time (JST)
- **Australia/Sydney**: Australian Eastern Time (AEST)

All times are stored in UTC in the database and converted to the user's timezone for display.

## Validation Rules

1. **Time Validation:**
   - Start time must be before end time
   - Time slots must be in the future
   - Slot duration must be positive

2. **Date Range Validation:**
   - Bulk creation date range cannot exceed 90 days
   - Start date cannot be in the past

3. **Duration Validation:**
   - Supported durations: 15, 30, 45, 60, 90, 120 minutes
   - Default duration: 45 minutes

4. **Conflict Detection:**
   - System prevents overlapping time slots
   - Checks for conflicts before creating new slots

## Error Handling

The API returns appropriate HTTP status codes:

- **200**: Success
- **400**: Bad Request (validation errors)
- **401**: Unauthorized (missing or invalid auth token)
- **404**: Not Found (slot not found)
- **500**: Internal Server Error

Error responses include detailed error messages:

```json
{
    "detail": "Time slot must be in the future"
}
```

## Usage Examples

### Creating a Single Slot

```python
import requests

# Create a 45-minute slot for tomorrow at 2 PM IST
slot_data = {
    "start_time": "2024-01-15T14:00:00",
    "end_time": "2024-01-15T14:45:00",
    "timezone": "Asia/Kolkata",
    "title": "Available for calls"
}

response = requests.post(
    "http://localhost:8000/users/time-slots/",
    headers={"Authorization": "Bearer your_token"},
    json=slot_data
)
```

### Creating Weekly Slots

```python
# Create slots for Monday to Friday, 2 PM to 6 PM, for the next week
bulk_data = {
    "start_date": "2024-01-15",
    "end_date": "2024-01-21",
    "start_time": "14:00",
    "end_time": "18:00",
    "timezone": "Asia/Kolkata",
    "days_of_week": [0, 1, 2, 3, 4],  # Monday to Friday
    "slot_duration_minutes": 45
}

response = requests.post(
    "http://localhost:8000/users/time-slots/bulk",
    headers={"Authorization": "Bearer your_token"},
    json=bulk_data
)
```

### Getting Available Slots

```python
# Get upcoming available slots
response = requests.get(
    "http://localhost:8000/users/time-slots/available/upcoming",
    headers={"Authorization": "Bearer your_token"},
    params={"limit": 10}
)

available_slots = response.json()
```

## Database Migration

To set up the database table, run the migration script:

```bash
psql -d your_database -f database_migration_user_time_slots.sql
```

## Testing

Use the provided test script to verify the functionality:

```bash
python test_time_slots_api.py
```

Make sure to:
1. Update the `BASE_URL` and `AUTH_TOKEN` in the test script
2. Run the database migration first
3. Start your FastAPI server

## Integration with Existing Calendar System

This time slots system is separate from the existing Google Calendar integration. Users can:

1. Create their own time slots using this API
2. Sync with Google Calendar (existing functionality)
3. Use both systems together for comprehensive availability management

The time slots created through this API are stored in your database and can be used for:
- Mentoring session scheduling
- Call booking
- Availability display
- Integration with payment systems

## Future Enhancements

Potential future features:
- Recurring slot patterns (daily, weekly, monthly)
- Integration with external calendar systems
- Automated slot generation based on user preferences
- Slot templates for quick creation
- Advanced conflict resolution
- Bulk operations (delete multiple slots)
- Export/import functionality
