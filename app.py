#!/usr/bin/env python3
"""
Spire Run Stats - Local web server
Run with: python3 app.py
Then open http://localhost:8080
"""
import json
import glob
import os
import collections
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history')
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8080

CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript',
    '.css':  'text/css',
    '.json': 'application/json',
}


def load_runs():
    runs = []
    for filepath in sorted(glob.glob(os.path.join(HISTORY_DIR, '*.run'))):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Extract just what the frontend needs
            character = 'UNKNOWN'
            for player in data.get('players', []):
                raw = player.get('character', 'UNKNOWN')
                # Strip "CHARACTER." prefix
                character = raw.replace('CHARACTER.', '') if raw.startswith('CHARACTER.') else raw
                break

            killed_raw = data.get('killed_by_encounter', 'NONE.NONE')
            killed_event_raw = data.get('killed_by_event', 'NONE.NONE')

            acts = data.get('acts', [])
            acts_count = len(acts)

            runs.append({
                'character': character,
                'killed_by': killed_raw,
                'killed_by_event': killed_event_raw,
                'win': bool(data.get('win', False)),
                'abandoned': bool(data.get('was_abandoned', False)),
                'ascension': int(data.get('ascension', 0)),
                'acts': acts_count,
                'start_time': data.get('start_time', 0),
                'run_time': data.get('run_time', 0),
            })
        except Exception as e:
            print(f"Warning: could not parse {filepath}: {e}")
    return runs


def load_card_stats():
    """
    Returns a list of records:
      { character, act, card, offered, picked }
    Aggregated across all run files.
    """
    # key: (character, act_name, card_id) -> {offered, picked}
    stats = collections.defaultdict(lambda: {'offered': 0, 'picked': 0})

    for filepath in sorted(glob.glob(os.path.join(HISTORY_DIR, '*.run'))):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            char = 'UNKNOWN'
            for player in data.get('players', []):
                raw = player.get('character', 'UNKNOWN')
                char = raw.replace('CHARACTER.', '') if raw.startswith('CHARACTER.') else raw
                break

            acts = data.get('acts', [])
            for act_i, act_points in enumerate(data.get('map_point_history', [])):
                act_name = acts[act_i].replace('ACT.', '') if act_i < len(acts) else f'ACT_{act_i}'
                for point in act_points:
                    for ps in point.get('player_stats', []):
                        for choice in ps.get('card_choices', []):
                            card_id = choice.get('card', {}).get('id', '')
                            if not card_id:
                                continue
                            key = (char, act_name, card_id)
                            stats[key]['offered'] += 1
                            if choice.get('was_picked'):
                                stats[key]['picked'] += 1
        except Exception as e:
            print(f"Warning: could not parse {filepath}: {e}")

    result = []
    for (char, act, card), v in stats.items():
        result.append({
            'character': char,
            'act': act,
            'card': card.replace('CARD.', ''),
            'offered': v['offered'],
            'picked': v['picked'],
        })
    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path in ('', '/'):
            self._serve_file(os.path.join(STATIC_DIR, 'index.html'))
        elif path == '/api/runs':
            runs = load_runs()
            body = json.dumps(runs).encode('utf-8')
            self._send(200, 'application/json', body)
        elif path == '/api/cards':
            cards = load_card_stats()
            body = json.dumps(cards).encode('utf-8')
            self._send(200, 'application/json', body)
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_file(self, filepath):
        if not os.path.isfile(filepath):
            self.send_response(404)
            self.end_headers()
            return
        ext = os.path.splitext(filepath)[1]
        content_type = CONTENT_TYPES.get(ext, 'application/octet-stream')
        with open(filepath, 'rb') as f:
            body = f.read()
        self._send(200, content_type, body)

    def _send(self, status, content_type, body):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Print cleaner log lines
        print(f"  {self.address_string()} {args[0]}")


if __name__ == '__main__':
    server = HTTPServer(('localhost', PORT), Handler)
    print(f"Spire Run Stats running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
