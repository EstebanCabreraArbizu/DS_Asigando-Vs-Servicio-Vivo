from django.http import JsonResponse


def health(_request):
    """Health check endpoint - returns {"status": "ok"}"""
    return JsonResponse({"status": "ok"})
