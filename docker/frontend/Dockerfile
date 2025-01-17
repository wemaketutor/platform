# syntax=docker/dockerfile:1.3
FROM debian:buster-slim

ENV DOCKERIZE_VERSION=v0.6.1 \
  TINI_VERSION=v0.19.0 \
  NVM_VERSION=v0.40.0 \
  NODE_VERSION=v22.11.0 \
  NPM_CACHE_DIR='~/.npm' \
  NVM_DIR='/usr/local/nvm' \
  NVM_INSTALL_PATH='$NVM_DIR/versions/node/v$NODE_VERSION'

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

RUN apt-get update && apt-get upgrade -y \
  && apt-get install --no-install-recommends -y \
    ca-certificates \
    bash \
    curl \
  # Installing `dockerize` utility:
  # https://github.com/jwilder/dockerize
  && curl -sSLO "https://github.com/jwilder/dockerize/releases/download/${DOCKERIZE_VERSION}/dockerize-linux-amd64-${DOCKERIZE_VERSION}.tar.gz" \
  && tar -C /usr/local/bin -xzvf "dockerize-linux-amd64-${DOCKERIZE_VERSION}.tar.gz" \
  && rm "dockerize-linux-amd64-${DOCKERIZE_VERSION}.tar.gz" && dockerize --version \
  # Installing `tini` utility:
  # https://github.com/krallin/tini \
  && dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')" \
  && curl -o /usr/local/bin/tini -sSLO "https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-${dpkgArch}" \
  && chmod +x /usr/local/bin/tini && tini --version \
  # Installing `npm`: \
  && mkdir $NVM_DIR && curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash \
  && source "$NVM_DIR/nvm.sh" && nvm install $NODE_VERSION \
  && nvm use ${NODE_VERSION} \
  && ln -s "$NVM_DIR/versions/node/${NODE_VERSION}/bin/node" /usr/local/bin/node \
  && ln -s "$NVM_DIR/versions/node/${NODE_VERSION}/bin/npm" /usr/local/bin/npm \
  # Cleaning cache:
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && apt-get clean -y && rm -rf /var/lib/apt/lists/*

ENV NODE_PATH=$NVM_INSTALL_PATH/lib/node_modules \
  PATH=$NVM_INSTALL_PATH/bin:$PATH

WORKDIR /code

RUN groupadd -r runner && useradd -d /code -r -g runner runner \
  && chown runner:runner -R /code

COPY --chown=runner:runner ./frontend/package.json ./frontend/package-lock.json /code/

RUN --mount=type=cache,target=$NPM_CACHE_DIR npm ci

COPY ./docker/frontend/entrypoint.sh /docker-entrypoint.sh
COPY ./docker/frontend/runner /usr/local/bin/runner
COPY ./frontend /code/

RUN chmod +x '/docker-entrypoint.sh' \
  && chmod +x '/usr/local/bin/runner' \
  && chmod 777 '/code/node_modules/'
#  && sed -i 's/\r$//g' '/docker-entrypoint.sh' \
#  && sed -i 's/\r$//g' '/usr/local/bin/runner' \

USER runner

ENTRYPOINT ["tini", "--", "/docker-entrypoint.sh"]
