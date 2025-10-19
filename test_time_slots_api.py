"""
Test script for User Time Slots API
This script demonstrates how to use the new time slots functionality
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust this to your API base URL
AUTH_TOKEN = "your_auth_token_here"  # Replace with actual auth token

def get_headers() -> Dict[str, str]:
    """Get headers with authentication"""
    return {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }

def test_create_single_time_slot():
    """Test creating a single time slot"""
    print("Testing single time slot creation...")
    
    # Create a time slot for tomorrow at 2 PM (45 minutes)
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=45)
    
    slot_data = {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "timezone": "Asia/Kolkata",
        "title": "Available for calls",
        "description": "I'm available for mentoring calls during this time"
    }
    
    response = requests.post(
        f"{BASE_URL}/users/time-slots/",
        headers=get_headers(),
        json=slot_data
    )
    
    if response.status_code == 200:
        print("✅ Single time slot created successfully!")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()["id"]
    else:
        print(f"❌ Failed to create single time slot: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def test_create_bulk_time_slots():
    """Test creating multiple time slots"""
    print("\nTesting bulk time slot creation...")
    
    # Create slots for the next 7 days, Monday to Friday, 2 PM to 6 PM, 45-minute slots
    bulk_data = {
        "start_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "end_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "start_time": "14:00",
        "end_time": "18:00",
        "timezone": "Asia/Kolkata",
        "days_of_week": [0, 1, 2, 3, 4],  # Monday to Friday
        "title": "Mentoring Hours",
        "description": "Available for mentoring calls",
        "slot_duration_minutes": 45
    }
    
    response = requests.post(
        f"{BASE_URL}/users/time-slots/bulk",
        headers=get_headers(),
        json=bulk_data
    )
    
    if response.status_code == 200:
        print("✅ Bulk time slots created successfully!")
        result = response.json()
        print(f"Created {result['slots_created']} slots")
        print(f"Date range: {result['date_range']['start']} to {result['date_range']['end']}")
        return result["slots"]
    else:
        print(f"❌ Failed to create bulk time slots: {response.status_code}")
        print(f"Error: {response.text}")
        return []

def test_get_time_slots():
    """Test getting time slots"""
    print("\nTesting get time slots...")
    
    response = requests.get(
        f"{BASE_URL}/users/time-slots/",
        headers=get_headers(),
        params={"limit": 10}
    )
    
    if response.status_code == 200:
        print("✅ Time slots retrieved successfully!")
        slots = response.json()
        print(f"Found {len(slots)} time slots")
        for slot in slots[:3]:  # Show first 3 slots
            print(f"- {slot['title']}: {slot['start_time_local']} to {slot['end_time_local']} ({slot['status']})")
        return slots
    else:
        print(f"❌ Failed to get time slots: {response.status_code}")
        print(f"Error: {response.text}")
        return []

def test_get_time_slot_summary():
    """Test getting time slot summary"""
    print("\nTesting time slot summary...")
    
    response = requests.get(
        f"{BASE_URL}/users/time-slots/summary",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        print("✅ Time slot summary retrieved successfully!")
        summary = response.json()
        print(f"Total slots: {summary['total_slots']}")
        print(f"Available: {summary['available_slots']}")
        print(f"Booked: {summary['booked_slots']}")
        print(f"Blocked: {summary['blocked_slots']}")
        print(f"Upcoming: {summary['upcoming_slots']}")
        return summary
    else:
        print(f"❌ Failed to get time slot summary: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def test_update_time_slot(slot_id: str):
    """Test updating a time slot"""
    print(f"\nTesting update time slot {slot_id}...")
    
    update_data = {
        "title": "Updated: Available for calls",
        "description": "Updated description for this time slot"
    }
    
    response = requests.put(
        f"{BASE_URL}/users/time-slots/{slot_id}",
        headers=get_headers(),
        json=update_data
    )
    
    if response.status_code == 200:
        print("✅ Time slot updated successfully!")
        updated_slot = response.json()
        print(f"New title: {updated_slot['title']}")
        return updated_slot
    else:
        print(f"❌ Failed to update time slot: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def test_book_time_slot(slot_id: str):
    """Test booking a time slot"""
    print(f"\nTesting booking time slot {slot_id}...")
    
    response = requests.post(
        f"{BASE_URL}/users/time-slots/{slot_id}/book",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        print("✅ Time slot booked successfully!")
        result = response.json()
        print(f"Status: {result['slot']['status']}")
        return result["slot"]
    else:
        print(f"❌ Failed to book time slot: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def test_get_upcoming_available_slots():
    """Test getting upcoming available slots"""
    print("\nTesting get upcoming available slots...")
    
    response = requests.get(
        f"{BASE_URL}/users/time-slots/available/upcoming",
        headers=get_headers(),
        params={"limit": 5}
    )
    
    if response.status_code == 200:
        print("✅ Upcoming available slots retrieved successfully!")
        slots = response.json()
        print(f"Found {len(slots)} upcoming available slots")
        for slot in slots:
            print(f"- {slot['title']}: {slot['start_time_local']} ({slot['timezone']})")
        return slots
    else:
        print(f"❌ Failed to get upcoming available slots: {response.status_code}")
        print(f"Error: {response.text}")
        return []

def main():
    """Run all tests"""
    print("🚀 Starting User Time Slots API Tests")
    print("=" * 50)
    
    # Test 1: Create single time slot
    slot_id = test_create_single_time_slot()
    
    # Test 2: Create bulk time slots
    bulk_slots = test_create_bulk_time_slots()
    
    # Test 3: Get time slots
    all_slots = test_get_time_slots()
    
    # Test 4: Get time slot summary
    summary = test_get_time_slot_summary()
    
    # Test 5: Update time slot (if we have one)
    if slot_id:
        test_update_time_slot(slot_id)
    
    # Test 6: Book time slot (if we have one)
    if slot_id:
        test_book_time_slot(slot_id)
    
    # Test 7: Get upcoming available slots
    test_get_upcoming_available_slots()
    
    print("\n" + "=" * 50)
    print("✅ All tests completed!")
    print("\nTo use this API in your application:")
    print("1. Run the database migration: database_migration_user_time_slots.sql")
    print("2. Start your FastAPI server")
    print("3. Use the endpoints at /users/time-slots/")
    print("4. Make sure to include proper authentication headers")

if __name__ == "__main__":
    main()
