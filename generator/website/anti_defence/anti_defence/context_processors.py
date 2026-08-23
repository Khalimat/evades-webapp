from django.conf import settings

def base_url(request):
    return {
        "base_url": settings.BASE_URL,
        "site_root": settings.SITE_ROOT,
    }