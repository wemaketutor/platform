FROM caddy:2.9.1-builder AS builder

# Add rate_limit plugin
RUN xcaddy build --with github.com/mholt/caddy-ratelimit

FROM caddy:2.9.1

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
