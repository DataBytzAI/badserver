## What is this

This is bad HTTP server. It responds with infinite sequence of HTTP headers delaying each byte with 1 second.


## Installation

To create virtual environment and install all dependencies run: `make build`

To run bad server on 127.0.0.1:8090 port run: `python3 badserver.py -p 8090`

Redirect bots to `bad-server-hostname:8090/fuckoff`

# Running on 80 port

To bind non-root process to 80 port you can use `sysctl -w net.ipv4.ip_unprivileged_port_start=0`. Do not forget to write it to "/etc/sysctl.conf"


## Support

Telegram chats: [grablab](https://t.me/grablab) (English) and [grablab\_ru](https://t.me/grablab_ru) (Russian)
