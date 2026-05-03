from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Standardize the error response format
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

        response.data = {
            "status": "error",
            "code": response.status_code,
            "message": user_message,
            "errors": response.data if response.status_code == 400 else None
        }

    return response
