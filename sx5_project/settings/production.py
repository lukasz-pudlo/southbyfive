from .base import *
import boto3
import json
from botocore.exceptions import ClientError


DEBUG = False
ALLOWED_HOSTS = ['southbyfive.run', 'www.southbyfive.run',
                 '.southbyfive.run', 'southbyfive.eu-west-1.elasticbeanstalk.com', 'http://southbyfive-app-env.eba-vma6ktp3.eu-west-1.elasticbeanstalk.com']
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


rds_credentials = get_rds_credentials()
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': rds_credentials.get('NAME'),
        'USER': rds_credentials.get('USER'),
        'PASSWORD': rds_credentials.get('PASSWORD'),
        'HOST': rds_credentials.get('HOST'),
        'PORT': rds_credentials.get('PORT'),
    }
}

# S3 bucket configuration for deployment to AWS Elastic Beanstalk.
s3_credentials = get_s3_credentials()
AWS_ACCESS_KEY_ID = s3_credentials.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = s3_credentials.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = s3_credentials.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = s3_credentials.get("AWS_S3_REGION_NAME")
AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME

# Static files (CSS, JavaScript, images)
AWS_STATIC_LOCATION = 'static'
STATIC_URL = 'https://%s/%s/' % (AWS_S3_CUSTOM_DOMAIN, AWS_STATIC_LOCATION)
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Media files (uploads)
AWS_MEDIA_LOCATION = 'media'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
MEDIA_URL = 'https://%s/%s/' % (AWS_S3_CUSTOM_DOMAIN, AWS_MEDIA_LOCATION)
