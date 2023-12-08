"""
Django settings for sx5_project project.

Generated by 'django-admin startproject' using Django 4.2.2.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import boto3
import json
from botocore.exceptions import ClientError

from pathlib import Path
import os

from dotenv import load_dotenv
load_dotenv()

# Fetch credentials from Secrets Manager


def get_secret(secret_name, region_name="eu-west-1"):
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name)
    except ClientError as e:
        raise e
    else:
        if 'SecretString' in get_secret_value_response:
            return json.loads(get_secret_value_response['SecretString'])


def get_rds_credentials():
    if 'RDS_DB_NAME' in os.environ:
        # Fetch RDS credentials from Secrets Manager
        secret_name = "Sx5EbRdsCredentials"
        return get_secret(secret_name)
    else:
        # Local database credentials
        return {
            'NAME': os.getenv("POSTGRES_DB"),
            'USER': os.getenv("POSTGRES_USER"),
            'PASSWORD': os.getenv("POSTGRES_PASSWORD"),
            'HOST': os.getenv("POSTGRES_HOST"),
            'PORT': os.getenv("POSTGRES_PORT"),
        }


def get_s3_credentials():
    if 'AWS_STORAGE_BUCKET_NAME' in os.environ:
        # Fetch S3 credentials from Secrets Manager
        secret_name = "Sx5S3BucketCredentials"
        return get_secret(secret_name)
    else:
        # Local S3 credentials
        return {
            'AWS_ACCESS_KEY_ID': os.getenv("AWS_ACCESS_KEY_ID"),
            'AWS_SECRET_ACCESS_KEY': os.getenv("AWS_SECRET_ACCESS_KEY"),
            'AWS_STORAGE_BUCKET_NAME': os.getenv("AWS_STORAGE_BUCKET_NAME"),
            'AWS_S3_REGION_NAME': os.getenv("AWS_S3_REGION_NAME"),
        }


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['southbyfive.run', 'www.southbyfive.run', 'localhost', '127.0.0.1',
                 '.southbyfive.run', 'southbyfive.eu-west-1.elasticbeanstalk.com', 'http://southbyfive-app-env.eba-vma6ktp3.eu-west-1.elasticbeanstalk.com', '.ngrok-free.app']


# Application definition

INSTALLED_APPS = [
    'sx5_project',
    'races',
    'race_versions',
    'classifications',
    'info',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bootstrap5',
    'django_extensions',
    'storages',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


CSRF_TRUSTED_ORIGINS = ['https://southbyfive.run']


ROOT_URLCONF = 'sx5_project.urls'
APPEND_SLASH = True

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'races.context_processors.race_list',
                'races.context_processors.race_navbar',
                'races.context_processors.race_dates_context'
            ],
        },
    },
]

WSGI_APPLICATION = 'sx5_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# Database configuration for deployment to AWS Elastic Beanstalk.
# rds_credentials = get_rds_credentials()
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': rds_credentials.get('NAME'),
#         'USER': rds_credentials.get('USER'),
#         'PASSWORD': rds_credentials.get('PASSWORD'),
#         'HOST': rds_credentials.get('HOST'),
#         'PORT': rds_credentials.get('PORT'),
#     }
# }

# Database configuration for local development, but with access to RDS database.
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('POSTGRES_DB'),
#         'USER': os.getenv('POSTGRES_USER'),
#         'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
#         'HOST': os.getenv('POSTGRES_HOST'),
#         'PORT': os.getenv('POSTGRES_PORT'),
#     }
# }

# Database configuration for local development, with local database.
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

# S3 bucket configuration for deployment to AWS Elastic Beanstalk.
# s3_credentials = get_s3_credentials()
# AWS_ACCESS_KEY_ID = s3_credentials.get("AWS_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = s3_credentials.get("AWS_SECRET_ACCESS_KEY")
# AWS_STORAGE_BUCKET_NAME = s3_credentials.get("AWS_STORAGE_BUCKET_NAME")
# AWS_S3_REGION_NAME = s3_credentials.get("AWS_S3_REGION_NAME")
# AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME

# # # Static files (CSS, JavaScript, images)
# AWS_STATIC_LOCATION = 'static'
# STATIC_URL = 'https://%s/%s/' % (AWS_S3_CUSTOM_DOMAIN, AWS_STATIC_LOCATION)
# STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# # # Media files (uploads)
# AWS_MEDIA_LOCATION = 'media'
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# MEDIA_URL = 'https://%s/%s/' % (AWS_S3_CUSTOM_DOMAIN, AWS_MEDIA_LOCATION)

# S3 bucket configuration for local development but with access to AWS S3 bucket.
# AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
# AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
# AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")
# AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME

# # Static files (CSS, JavaScript, images)
# AWS_STATIC_LOCATION = 'static'
# STATIC_URL = 'https://%s/%s/' % (AWS_S3_CUSTOM_DOMAIN, AWS_STATIC_LOCATION)
# STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# # Media files (uploads)
# AWS_MEDIA_LOCATION = 'media'
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# MEDIA_URL = 'https://%s/%s/' % (AWS_S3_CUSTOM_DOMAIN, AWS_MEDIA_LOCATION)

# Local static and media configuration for local development.
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Ensure STATICFILES_STORAGE is set to the default
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# STATIC_URL = '/static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

LOGIN_REDIRECT_URL = '/races'
