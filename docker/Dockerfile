# The Dockerfile can be used to create two variants
# by using "--build-arg INSTALL_EVERYTHING=[true|false]":
# - "true": with mecab and dictionary, mandarin parser (800+ MB)
# - "false": without (230 MB)
#
# e.g.  docker build --build-arg INSTALL_EVERYTHING=true -t lute3 .

# Official python base image.
FROM python:3.11-slim-bookworm

# Install base.
COPY pyproject.toml .
COPY README_PyPi.md .
COPY lute/__init__.py /lute/__init__.py
ENV PIP_ROOT_USER_ACTION=ignore
ENV FLIT_ROOT_INSTALL=1
RUN pip install flit
RUN flit install --only-deps --deps=production
COPY docker/Dockerfile_scripts/install_everything.sh /lute/install_all.sh
RUN chmod +x /lute/install_all.sh

ARG INSTALL_EVERYTHING=false
RUN if [ "$INSTALL_EVERYTHING" = "true" ]; then /lute/install_all.sh; fi

COPY lute /lute
COPY lute/config/config.yml.docker /lute/config/config.yml

EXPOSE 5001

# Start script.
COPY docker/Dockerfile_scripts/start.sh /lute/start.sh
RUN chmod +x /lute/start.sh
ENTRYPOINT ["/lute/start.sh"]
