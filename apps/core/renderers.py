from rest_framework.renderers import JSONRenderer

class StandardizedJSONRenderer(JSONRenderer):
    """
    Custom renderer to ensure a consistent response format for successes.
    """
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context['response']
        status_code = response.status_code

        # If data is already in our standard 'error' or 'success' format, don't wrap it again
        if isinstance(data, dict) and 'status' in data and data['status'] in ['success', 'error']:
            return super().render(data, accepted_media_type, renderer_context)

        # Handle Success Responses (2xx)
        if 200 <= status_code < 300:
            message = "Action completed successfully."
            
            # If the view passed a custom message in the data, extract it
            if isinstance(data, dict) and 'message' in data:
                message = data.pop('message')

            data = {
                "status": "success",
                "code": status_code,
                "message": message,
                "data": data
            }

        return super().render(data, accepted_media_type, renderer_context)
