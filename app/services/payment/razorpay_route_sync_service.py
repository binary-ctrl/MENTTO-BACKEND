"""
Razorpay Route Account Sync Service
This service handles syncing bank details from the database to Razorpay Route accounts.
Designed to be used with Supabase Edge Functions.
"""

import logging
import requests
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class RazorpayRouteSyncService:
    """
    Service to sync bank details to Razorpay Route accounts
    """
    
    def __init__(self, razorpay_key_id: str, razorpay_key_secret: str):
        """
        Initialize the service with Razorpay credentials
        
        Args:
            razorpay_key_id: Razorpay API key ID
            razorpay_key_secret: Razorpay API key secret
        """
        self.key_id = razorpay_key_id
        self.key_secret = razorpay_key_secret
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
        Create a new route account in Razorpay
        
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
            Dict containing the created route account details or error info
        """
        try:
            url = f"{self.base_url}/route/accounts"
            
            # Prepare payload for Razorpay API
            payload = {
                "business_name": bank_details.get("business_name"),
                "business_type": bank_details.get("business_type", "individual"),
                "branch_ifsc_code": bank_details.get("branch_ifsc_code"),
                "account_number": bank_details.get("account_number"),
                "beneficiary_name": bank_details.get("beneficiary_name")
            }
            
            # Validate required fields
            required_fields = ["business_name", "branch_ifsc_code", "account_number", "beneficiary_name"]
            missing_fields = [field for field in required_fields if not payload.get(field)]
            
            if missing_fields:
                return {
                    "success": False,
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "error_code": "MISSING_FIELDS"
                }
            
            logger.info(f"Creating route account for business: {payload['business_name']}")
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully created route account: {result.get('id')}")
                return {
                    "success": True,
                    "data": result,
                    "message": "Route account created successfully"
                }
            else:
                error_detail = response.json() if response.content else {"error": "Unknown error"}
                logger.error(f"Failed to create route account: {response.status_code} - {error_detail}")
                return {
                    "success": False,
                    "error": error_detail.get("error", {}).get("description", "Failed to create route account"),
                    "error_code": error_detail.get("error", {}).get("code", "UNKNOWN_ERROR"),
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            logger.error("Timeout while creating route account")
            return {
                "success": False,
                "error": "Request timeout",
                "error_code": "TIMEOUT"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while creating route account: {e}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "error_code": "REQUEST_ERROR"
            }
        except Exception as e:
            logger.error(f"Unexpected error while creating route account: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_code": "UNEXPECTED_ERROR"
            }
    
    def get_route_account(self, account_id: str) -> Dict[str, Any]:
        """
        Get details of a specific route account
        
        Args:
            account_id: Razorpay route account ID
            
        Returns:
            Dict containing route account details or error info
        """
        try:
            url = f"{self.base_url}/route/accounts/{account_id}"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "data": result,
                    "message": "Route account retrieved successfully"
                }
            else:
                error_detail = response.json() if response.content else {"error": "Unknown error"}
                return {
                    "success": False,
                    "error": error_detail.get("error", {}).get("description", "Failed to get route account"),
                    "error_code": error_detail.get("error", {}).get("code", "UNKNOWN_ERROR"),
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error getting route account {account_id}: {e}")
            return {
                "success": False,
                "error": f"Error retrieving route account: {str(e)}",
                "error_code": "REQUEST_ERROR"
            }
    
    def list_route_accounts(self, limit: int = 10, skip: int = 0) -> Dict[str, Any]:
        """
        List all route accounts
        
        Args:
            limit: Number of accounts to retrieve (max 100)
            skip: Number of accounts to skip
            
        Returns:
            Dict containing list of route accounts or error info
        """
        try:
            url = f"{self.base_url}/route/accounts"
            params = {"count": min(limit, 100), "skip": skip}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "data": result,
                    "message": "Route accounts retrieved successfully"
                }
            else:
                error_detail = response.json() if response.content else {"error": "Unknown error"}
                return {
                    "success": False,
                    "error": error_detail.get("error", {}).get("description", "Failed to list route accounts"),
                    "error_code": error_detail.get("error", {}).get("code", "UNKNOWN_ERROR"),
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error listing route accounts: {e}")
            return {
                "success": False,
                "error": f"Error listing route accounts: {str(e)}",
                "error_code": "REQUEST_ERROR"
            }
    
    def sync_bank_details_to_razorpay(self, bank_details_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sync multiple bank details to Razorpay route accounts
        
        Args:
            bank_details_list: List of bank detail dictionaries
            
        Returns:
            Dict containing sync results for all accounts
        """
        results = {
            "success": True,
            "total_processed": len(bank_details_list),
            "successful": 0,
            "failed": 0,
            "results": []
        }
        
        for i, bank_details in enumerate(bank_details_list):
            logger.info(f"Processing bank details {i+1}/{len(bank_details_list)}")
            
            result = self.create_route_account(bank_details)
            results["results"].append({
                "index": i,
                "bank_details": bank_details,
                "result": result
            })
            
            if result["success"]:
                results["successful"] += 1
            else:
                results["failed"] += 1
        
        # Overall success if at least one account was created successfully
        results["success"] = results["successful"] > 0
        
        return results


# Utility functions for Supabase Edge Functions
def create_razorpay_sync_service(razorpay_key_id: str, razorpay_key_secret: str) -> RazorpayRouteSyncService:
    """
    Factory function to create RazorpayRouteSyncService instance
    Useful for Supabase Edge Functions
    """
    return RazorpayRouteSyncService(razorpay_key_id, razorpay_key_secret)


def format_response_for_edge_function(result: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """
    Format response for Supabase Edge Functions
    
    Args:
        result: Result from RazorpayRouteSyncService methods
        status_code: HTTP status code
        
    Returns:
        Formatted response for Edge Function
    """
    return {
        "statusCode": status_code,
        "body": result,
        "headers": {
            "Content-Type": "application/json"
        }
    }


# Example usage for Supabase Edge Function
def example_edge_function_handler(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example handler for Supabase Edge Function
    
    Args:
        request_data: Request data from Edge Function
        
    Returns:
        Formatted response for Edge Function
    """
    try:
        # Extract credentials and bank details from request
        razorpay_key_id = request_data.get("razorpay_key_id")
        razorpay_key_secret = request_data.get("razorpay_key_secret")
        bank_details = request_data.get("bank_details")
        
        if not all([razorpay_key_id, razorpay_key_secret, bank_details]):
            return format_response_for_edge_function({
                "success": False,
                "error": "Missing required parameters: razorpay_key_id, razorpay_key_secret, bank_details"
            }, 400)
        
        # Create service instance
        sync_service = create_razorpay_sync_service(razorpay_key_id, razorpay_key_secret)
        
        # If bank_details is a list, sync multiple accounts
        if isinstance(bank_details, list):
            result = sync_service.sync_bank_details_to_razorpay(bank_details)
        else:
            # Single account
            result = sync_service.create_route_account(bank_details)
        
        return format_response_for_edge_function(result)
        
    except Exception as e:
        logger.error(f"Error in edge function handler: {e}")
        return format_response_for_edge_function({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }, 500)
