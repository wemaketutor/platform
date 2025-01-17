# syntax=docker/dockerfile:1.3
FROM gradle:8.12.0-jdk21-alpine AS build

ENV BUILD_WORKDIR=/tmp/backend/

WORKDIR $BUILD_WORKDIR

COPY --chown=gradle:gradle ./backend/build.gradle.kts ./backend/settings.gradle.kts $BUILD_WORKDIR
COPY --chown=gradle:gradle ./backend/gradle/ $BUILD_WORKDIR/gradle/
COPY --chown=gradle:gradle ./backend/src/ $BUILD_WORKDIR/src/

RUN --mount=type=cache,target=/root/.gradle \
    gradle -q clean build bootJar -x test

FROM ibm-semeru-runtimes:open-21.0.5_11-jdk-focal AS package

ENV BUILD_WORKDIR=/tmp/backend/
ENV PACKAGE_WORKDIR=/usr/app

WORKDIR $PACKAGE_WORKDIR

COPY --from=build $BUILD_WORKDIR/build/libs/service.jar $PACKAGE_WORKDIR/service.jar

RUN jar -xvf "$PACKAGE_WORKDIR/service.jar" "$PACKAGE_WORKDIR/target/" \
  && jdeps \
  --ignore-missing-deps \
  -q \
  --multi-release 21 \
  --print-module-deps \
  --class-path "$PACKAGE_WORKDIR/target/*" \
  $PACKAGE_WORKDIR/service.jar > java.modules

RUN jlink --verbose \
  --compress 2 \
  --strip-java-debug-attributes \
  --no-header-files \
  --no-man-pages \
  --output jre \
  --add-modules $(cat java.modules),java.sql,java.transaction.xa,java.xml,java.naming,java.desktop,java.security.jgss,java.instrument,java.management

FROM debian:buster-slim

ENV DOCKERIZE_VERSION=v0.6.1 \
  TINI_VERSION=v0.19.0 \
  JAVA_HOME=/opt/jre/bin/java \
  PATH="/opt/jre/bin/:$PATH"

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
  # Cleaning cache:
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && apt-get clean -y && rm -rf /var/lib/apt/lists/*

COPY --from=package /usr/app/jre /opt/jre

WORKDIR /code

RUN groupadd -r runner && useradd -d /code -r -g runner runner \
  && chown runner:runner -R /code

COPY ./docker/backend/entrypoint.sh /docker-entrypoint.sh
COPY ./docker/backend/runner /usr/local/bin/runner
COPY --from=package /usr/app/ /code/

RUN chmod +x '/docker-entrypoint.sh' \
  && chmod +x '/usr/local/bin/runner'
#  && sed -i 's/\r$//g' '/docker-entrypoint.sh' \
#  && sed -i 's/\r$//g' '/usr/local/bin/runner' \

USER runner

ENTRYPOINT ["tini", "--", "/docker-entrypoint.sh"]
