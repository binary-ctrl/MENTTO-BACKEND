#!/usr/bin/env python3
"""
Razorpay Route API Integration
This script shows how to automatically add bank accounts to Razorpay Route
"""

import requests
import base64
import json
from typing import Dict, Any

class RazorpayRouteAPI:
    def __init__(self, key_id: str, key_secret: str):
        self.key_id = key_id
        self.key_secret = key_secret
        self.base_url = "https://api.razorpay.com/v1"
        
        # Create basic auth header
        credentials = f"{key_id}:{key_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
    
    def create_route_account(self, bank_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a route account in Razorpay
        
        Args:
            bank_details: Dictionary containing bank account details
                {
                    "business_name": "State Bank of India",
                    "business_type": "individual",
                    "branch_ifsc_code": "SBIN0001234",
                    "account_number": "1234567890",
                    "beneficiary_name": "John Doe"
                }
        
        Returns:
            Dict containing the created route account details
        """
        url = f"{self.base_url}/route/accounts"
        
        payload = {
            "business_name": bank_details["business_name"],
            "business_type": bank_details["business_type"],
            "branch_ifsc_code": bank_details["branch_ifsc_code"],
            "account_number": bank_details["account_number"],
            "beneficiary_name": bank_details["beneficiary_name"]
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating route account: {e}")
            return None
    
    def get_route_accounts(self) -> Dict[str, Any]:
        """Get all route accounts"""
        url = f"{self.base_url}/route/accounts"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching route accounts: {e}")
            return None
    
    def get_route_account(self, account_id: str) -> Dict[str, Any]:
        """Get specific route account by ID"""
        url = f"{self.base_url}/route/accounts/{account_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching route account: {e}")
            return None

# Example usage
if __name__ == "__main__":
    # Initialize with your Razorpay credentials
    route_api = RazorpayRouteAPI(
        key_id="rzp_test_RHZoSdShUSqco6",  # Your key ID
        key_secret="j9SqysyX5huFDKOpaSvrNig0"  # Your key secret
    )
    
    # Example bank details from your database
    bank_details = {
        "business_name": "State Bank of India",
        "business_type": "individual",
        "branch_ifsc_code": "SBIN0001234",
        "account_number": "1234567890",
        "beneficiary_name": "John Doe"
    }
    
    # Create route account
    result = route_api.create_route_account(bank_details)
    if result:
        print("Route account created successfully:")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to create route account")
