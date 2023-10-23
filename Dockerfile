FROM python:3.11-slim-buster

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

ADD . /app/

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

RUN apt-get update && \
    apt-get install -y iputils-ping dnsutils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
