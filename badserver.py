#!/usr/bin/env python3
from gevent import monkey
monkey.patch_all()
import time
import logging
from argparse import ArgumentParser
from functools import partial
from datetime import datetime, timedelta
import os
from random import SystemRandom

from redis import Redis
import gevent
from gevent.server import StreamServer

rand = SystemRandom()
RESPONSE_CHUNK_DELAY = 1
FUCKOFF_CHOICES = [b'slow', b'gzip']
REQUEST_MAP = {
    b'/': 'home',
    b'/stats': 'stats',
    b'/fuckoff/random': 'fuckoff_random',
    b'/fuckoff/slow': 'fuckoff_slow',
    b'/fuckoff/gzip': 'fuckoff_gzip',
    b'/home': 'home',
}



def render_stats(sock):
    now = datetime.utcnow()
    out = []
    out.append(b'----- hits -----\r\n')
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

    try:
        with open('var/socket.stat', 'rb') as inp:
            ss_out = inp.read()
    except OSError:
        ss_out = b'Could not read socket stats file'
    out.append(b'----- sockets -----\r\n')
    out.append(ss_out)

    sock.sendall(
        b'HTTP/1.1 200 OK\r\n'
        b'Content-Type: text/plain\r\n'
        b'\r\n'
    )
    for item in out:
        sock.sendall(item + b'\r\n')


def render_fuckoff_random(sock):
    target = rand.choice(FUCKOFF_CHOICES)
    sock.sendall((
        b'HTTP/1.1 302 OK\r\n'
        b'Location: /fuckoff/%s\r\n'
        b'\r\n'
        % target
    ))


def render_fuckoff_slow(chunk_delay, sock):
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


def render_fuckoff_gzip(sock):
    fname = 'data/10G.bin.gz'
    file_size = os.path.getsize(fname)
    initial_data = (
        b'HTTP/1.1 200 OK\r\n'
        b'Content-Encoding: gzip\r\n'
        b'Content-Length: %d\r\n'
        b'\r\n'
        % file_size
    )
    sock.sendall(initial_data)
    with gevent.Timeout(60 * 10):
        with open(fname, 'rb') as inp:
            sock.sendfile(inp)


def render_404(sock):
    sock.sendall((
        b'HTTP/1.1 404 OK\r\n'
        b'Content-Type: text/plain\r\n'
        b'Content-Length: 16\r\n'
        b'\r\n'
        b'Page Not Found\r\n'
    ))

def render_home(sock):
    with open('templates/home.html', 'rb') as inp:
        data = inp.read()
    sock.sendall((
        b'HTTP/1.1 200 OK\r\n'
        b'Content-Type: text/html; charset=utf-8\r\n'
        b'Content-Length: %d\r\n'
        b'\r\n'
        % len(data)
    ))
    sock.sendall(data)


def parse_req_url(line):
    sp1_pos = line.find(b' ', 0, 100)
    if 3 <= sp1_pos <= 7:
        sp2_pos = line.find(b' ', sp1_pos + 1, 100)
        if sp2_pos > -1:
            qst_pos = line.find(b'?', sp1_pos + 1, sp2_pos)
            if qst_pos > -1:
                return (
                    line[sp1_pos + 1:qst_pos],
                    line[qst_pos + 1:sp2_pos]
                )
            else:
                return (
                    line[sp1_pos + 1:sp2_pos],
                    ''
                )
    return None, None


def req_handler(chunk_delay, sock, addr):
    try:
        started = time.time()
        fsock = sock.makefile(mode='rb')
        try:
            view_id = '404'
            with gevent.Timeout(10):
                line = fsock.readline()
                req_path, req_query = parse_req_url(line)
                #print(b'PATH: %s' % (req_path or b'NA'))
                #print(b'QUERY: %s' % (req_query or b'NA'))
                logging.debug('%s:%s:%s' % (
                    addr[0], addr[1], req_path.decode('utf-8', errors='ignore')
                ))
                # Choose view ID
                for test_path, test_view_id in REQUEST_MAP.items():
                    if test_path == req_path:
                        view_id = test_view_id
                while line.rstrip():
                    line = fsock.readline()
            if view_id == 'stats':
                render_stats(sock)
            elif view_id == 'home':
                render_home(sock)
            elif view_id == 'fuckoff_random':
                render_fuckoff_random(sock)
            elif view_id == 'fuckoff_slow':
                render_fuckoff_slow(chunk_delay, sock)
            elif view_id == 'fuckoff_gzip':
                render_fuckoff_gzip(sock)
            else:
                render_404(sock)

        except gevent.Timeout:
            pass
        finally:
            fsock.close()
            sock.close()

            if view_id.startswith('fuckoff_'):
                elapsed = time.time() - started
                hour_key = datetime.utcnow().strftime('%Y-%m-%d:%H')
                # Remember statistics
                rdb = Redis()
                # increment number of visit in current hour
                rdb.incrby('hr-hits-num:%s' % hour_key, 1)
                # add this visit time to total time of visits in current hour
                rdb.incrbyfloat('hr-hits-time:%s' % hour_key, str('%.03f' % elapsed))
    except ConnectionError:
        pass
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
