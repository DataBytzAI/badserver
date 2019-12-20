## What is this

This is HTTP web server written in Python. It can serve different kinds of data intended to slow down or break remote HTTP client.


## Installation

To create virtual environment and install all dependencies run: `make build`

To run bad server on 127.0.0.1:8090 port run: `python3 badserver.py -p 8090`

Redirect bots to `bad-server-hostname:8090/fuckoff`

# Endpoints

- `/fuckoff/slow` - respond with infinite sequence of HTTP headers making 1 second pause before sending each next byte of data
- `/fuckoff/gzip` - respond with "Content-Encoding: gzip" and serve 12MB content which is equal to 10GB bytes after unpacking
- `/fuckoff/random` - redirect to random one of fuckoff endpoints described above
- `/stats` - return stats

# Running on 80 port

To bind non-root process to 80 port you can use `sysctl -w net.ipv4.ip_unprivileged_port_start=0`. Do not forget to write it to "/etc/sysctl.conf"


## Support

Telegram chats: [grablab](https://t.me/grablab) (English) and [grablab\_ru](https://t.me/grablab_ru) (Russian)
