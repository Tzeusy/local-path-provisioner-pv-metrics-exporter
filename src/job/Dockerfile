FROM python:3.12-alpine
WORKDIR /app
COPY requirements.txt requirements.txt
RUN apk update \
    && apk upgrade \
    && pip3 install -r requirements.txt
COPY . .
CMD [ "python3", "/app/job.py"]
