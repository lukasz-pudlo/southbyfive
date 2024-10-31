from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'local.southbyfive.run']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DEV_POSTGRES_DB'),
        'USER': os.getenv('DEV_POSTGRES_USER'),
        'PASSWORD': os.getenv('DEV_POSTGRES_PASSWORD'),
        'HOST': os.getenv('DEV_POSTGRES_HOST'),
        'PORT': os.getenv('POSTGRES_PORT'),
    }
}

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# Ensure STATICFILES_STORAGE is set to the default
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
