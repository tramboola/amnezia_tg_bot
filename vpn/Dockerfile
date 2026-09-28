FROM golang:1.25.12-alpine3.24@sha256:56961d79ea8129efddcc0b8643fd8a5416b4e6228cfd477e3fd61deb2672c587 AS go-build
ARG AWG_GO_COMMIT=b5928efb6ca19f0153958460c3d141f04abc5c2e
RUN apk add --no-cache git ca-certificates && \
    git clone https://github.com/amnezia-vpn/amneziawg-go.git /src && \
    cd /src && git checkout "$AWG_GO_COMMIT" && go mod download && go mod verify && \
    CGO_ENABLED=0 GOMAXPROCS=1 GOMEMLIMIT=384MiB go build -p 1 -trimpath -o /amneziawg-go .

FROM alpine:3.24.2@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6 AS tools-build
ARG AWG_TOOLS_COMMIT=ee0f0a9aa34ff0a0da4b3433b9512781cfe02843
RUN apk add --no-cache git build-base linux-headers && \
    git clone https://github.com/amnezia-vpn/amneziawg-tools.git /src && \
    cd /src && git checkout "$AWG_TOOLS_COMMIT" && make -C src

FROM alpine:3.24.2@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6
RUN apk add --no-cache iproute2 iptables && \
    mkdir -p /run/amneziawg
COPY --from=go-build /amneziawg-go /usr/bin/amneziawg-go
COPY --from=tools-build /src/src/wg /usr/bin/awg
COPY --chmod=755 entrypoint.sh /entrypoint.sh
ENV LOG_LEVEL=error
ENTRYPOINT ["/entrypoint.sh"]
