FROM python:3.12-alpine

WORKDIR /app

ENV RUN_IN_DOCKER=yes

RUN apk add --no-cache netcat-openbsd

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt --no-cache-dir

COPY . .

RUN chmod +x entrypoint.sh

ENTRYPOINT ["sh", "entrypoint.sh" ]
