#!/usr/bin/env python3
from gevent import monkey
monkey.patch_all()
import time
import logging
from argparse import ArgumentParser
from functools import partial
from datetime import datetime, timedelta

from redis import Redis
import gevent
from gevent.server import StreamServer

RESPONSE_CHUNK_DELAY = 1


def render_stats(sock):
    now = datetime.utcnow()
    out = []
    for delta in range(3):
        hour_key = (now - timedelta(hours=delta)).strftime('%Y-%m-%d:%H')
        out.append(b'Hour: %s' % hour_key.encode())
        rdb = Redis()
        num_hits = int(rdb.get('hr-hits-num:%s' % hour_key) or 0)
        out.append(b' * hits: %d' % num_hits)
        total_time = float(rdb.get('hr-hits-time:%s' % hour_key) or 0)
        out.append(b' * total time: %f' % total_time)
        if num_hits:
            avg_hit_time = total_time / num_hits
        else:
            avg_hit_time = 0
        out.append(b' * avg. hit time: %f' % avg_hit_time)
        out.append(b'')
    sock.sendall(
        b'HTTP/1.1 200 OK\r\n'
        b'Content-Type: text/plain\r\n'
        b'\r\n'
    )
    for item in out:
        sock.sendall(item + b'\r\n')



def render_bad_data(chunk_delay, sock):
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


def req_handler(chunk_delay, sock, addr):
    try:
        started = time.time()
        fsock = sock.makefile(mode='rb')
        is_stats = False
        try:
            with gevent.Timeout(10):
                idx = 0
                while True:
                    line = fsock.readline()
                    if idx == 0:
                        if line.startswith(b'GET /stats'):
                            is_stats = True
                    idx += 1
                    if not line.rstrip():
                        break
            if is_stats:
                render_stats(sock)
            else:
                render_bad_data(chunk_delay, sock)
        finally:
            fsock.close()
            sock.close()

            if not is_stats:
                elapsed = time.time() - started
                hour_key = datetime.utcnow().strftime('%Y-%m-%d:%H')
                # Remember statistics
                rdb = Redis()
                # increment number of visit in current hour
                rdb.incrby('hr-hits-num:%s' % hour_key, 1)
                # add this visit time to total time of visits in current hour
                rdb.incrbyfloat('hr-hits-time:%s' % hour_key, str('%.03f' % elapsed))
    except Exception as ex:
        logging.exception('')


def setup_logging():
    logging.basicConfig(level=logging.DEBUG)
    from logging.handlers import RotatingFileHandler
    hdl = RotatingFileHandler(
        'var/log/badserver.fatal', 'a',
        maxBytes=(1024 * 1024 * 10),
    )
    hdl.setLevel(logging.ERROR)
    hdl.setFormatter(logging.Formatter(
        '%(asctime)s:%(levelname)s:%(name)s:%(message)s'
    ))
    logging.getLogger().addHandler(hdl)


def run_server():
    setup_logging()
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
    logging.debug('Listening on %s:%s' % (opts.host, opts.port))
    server.serve_forever()


if __name__ == '__main__':
    run_server()
