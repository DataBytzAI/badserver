#!/usr/bin/env python3
from gevent import monkey
monkey.patch_all()
import time
import logging
from argparse import ArgumentParser
from functools import partial

import gevent
from gevent.server import StreamServer

RESPONSE_CHUNK_DELAY = 1


def req_handler(chunk_delay, sock, addr):
    fsock = sock.makefile(mode='rb')
    try:
        with gevent.Timeout(10):
            while True:
                line = fsock.readline()
                if not line.rstrip():
                    break
        initial_data = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html; charset=utf-8\r\n'
            b'Content-Length: 666\r\n'
        )
        for char in initial_data:
            sock.sendall(char.to_bytes(1, 'big'))
            time.sleep(chunk_delay)
        with gevent.Timeout(60 * 60):
            while True:
                for char in b'Fuck: Off\r\n':
                    sock.sendall(char.to_bytes(1, 'big'))
                    time.sleep(chunk_delay)
            sock.sendall(b'\r\n')
    finally:
        fsock.close()
        sock.close()


def run_server():
    parser = ArgumentParser()
    parser.add_argument('--host', type=str, default='127.0.0.1')
    parser.add_argument('-p', '--port', type=int, default=8888)
    parser.add_argument(
        '-d', '--chunk-delay', type=float,
        default=RESPONSE_CHUNK_DELAY
    )
    opts = parser.parse_args()
    server = StreamServer(
        (opts.host, opts.port),
        partial(req_handler, opts.chunk_delay)
    )
    logging.basicConfig(level=logging.DEBUG)
    logging.debug('Listening on %s:%s' % (opts.host, opts.port))
    server.serve_forever()


if __name__ == '__main__':
    run_server()
