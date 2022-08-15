FROM python:3.10.6

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

EXPOSE 5000

ENTRYPOINT ["/bin/sh", "server-run.sh"]
