FROM python:3.10.6

WORKDIR /app

COPY setup.py workdir/
COPY src workdir/src/
RUN cd workdir && pip install . && cd .. && rm -rf workdir

# to enable running pytest in the container...
COPY setup.py workdir/
COPY src workdir/src/
RUN cd workdir && pip install .[test] && cd .. && rm -rf workdir
COPY test ./test
COPY pyproject.toml .
# ...to enable running pytest in the container

EXPOSE 5000

COPY responses ./responses
COPY server-run.sh .
ENTRYPOINT ["/bin/sh", "server-run.sh"]
