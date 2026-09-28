#!/bin/sh
set -eu

test -s /data/server.conf
mkdir -p /run/amneziawg
amneziawg-go -f awg0 &
vpn_pid=$!
trap 'kill "$vpn_pid" 2>/dev/null || true; wait "$vpn_pid" 2>/dev/null || true' EXIT
trap 'exit 0' INT TERM

attempt=0
while [ ! -S /run/amneziawg/awg0.sock ]; do
    kill -0 "$vpn_pid" 2>/dev/null || exit 1
    attempt=$((attempt + 1))
    [ "$attempt" -lt 40 ] || exit 1
    sleep 0.25
done

awg setconf awg0 /data/server.conf
ip address add 10.8.0.1/24 dev awg0
ip -6 address add fd42:8::1/64 dev awg0
ip link set dev awg0 mtu 1280 up

# Routes and NAT are inside this container's network namespace.
iptables -P FORWARD DROP
iptables -A INPUT -i awg0 -j DROP
iptables -A FORWARD -i eth0 -o awg0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -i awg0 -o awg0 -j DROP
for network in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 127.0.0.0/8 224.0.0.0/4; do
    iptables -A FORWARD -i awg0 -d "$network" -j DROP
done
iptables -A FORWARD -i awg0 -o eth0 -s 10.8.0.0/24 -j ACCEPT
iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE
iptables -t mangle -A FORWARD -o awg0 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
ip6tables -P FORWARD DROP
ip6tables -A INPUT -i awg0 -j DROP

wait "$vpn_pid"
