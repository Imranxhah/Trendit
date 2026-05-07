import cloudinary
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)

    if response is None:
        # Check for infrastructure/network errors that DRF doesn't catch by default
        if isinstance(exc, (cloudinary.exceptions.Error,)):
            # Handle Cloudinary errors (often network or credential issues)
            message = str(exc)
            if "getaddrinfo failed" in message or "NameResolutionError" in message:
                user_message = "The server is having trouble connecting to the media storage service. Please check your internet connection."
            elif "Max retries exceeded" in message:
                user_message = "Connection to media storage timed out. Please try again."
            else:
                user_message = f"Media upload failed: {message}"
            
            response = Response({
                "status": "error",
                "code": 500,
                "message": user_message,
                "errors": {"media": [str(exc)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    if response is not None:
        # Print the exact error to the backend console
        print("\n--- API ERROR ---")
        print(f"Endpoint: {context.get('request').path if context.get('request') else 'Unknown'}")    
        print(f"Exception Type: {type(exc).__name__}")
        print(f"Raw Response Data: {response.data}")
        print("-----------------\n")

        # If it's a standard DRF response that hasn't been formatted yet
        if not (isinstance(response.data, dict) and 'status' in response.data):
            user_message = "Something went wrong. Please try again."

            if response.status_code == 401:
                user_message = "Your session has expired or you are not logged in."
            elif response.status_code == 403:
                user_message = "You do not have permission to perform this action."
            elif response.status_code == 404:
                user_message = "The item you are looking for was not found."
            elif response.status_code == 400:
                user_message = "Please check your input and try again."
            elif response.status_code == 429:
                user_message = "Too many requests. Please slow down."

            # If the exception provided a specific 'detail', use it as the message
            if isinstance(response.data, dict):
                if 'detail' in response.data:
                    user_message = response.data['detail']
                elif 'non_field_errors' in response.data:
                    user_message = response.data['non_field_errors'][0]
                elif response.status_code == 400:
                    # For 400 errors, try to pick the first field error as the message
                    try:
                        first_field = next(iter(response.data))
                        first_error = response.data[first_field]
                        if isinstance(first_error, list) and len(first_error) > 0:
                            user_message = f"{first_field}: {first_error[0]}"
                        elif isinstance(first_error, str):
                            user_message = f"{first_field}: {first_error}"
                    except (StopIteration, KeyError, TypeError):
                        pass

            response.data = {
                "status": "error",
                "code": response.status_code,
                "message": user_message,
                "errors": response.data if response.status_code == 400 else None
            }

    return response
