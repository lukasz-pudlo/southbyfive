FROM python:3.11-slim-buster

# Environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install dependencies early for better caching
COPY requirements.txt /app/
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Add application code
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose the application port
EXPOSE 8000

# Command to run the application using Gunicorn
CMD ["gunicorn", "sx5_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
