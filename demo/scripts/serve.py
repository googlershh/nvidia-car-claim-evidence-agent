"""Serve only generated public demo files on a loopback port."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

class ShareHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        name = 'index.html' if path == '/' else path.lstrip('/')
        if name not in self.server.public_files or not (self.server.root / name).resolve().is_relative_to(self.server.root):
            self.send_error(404, 'Not found')
            return None
        self.path = '/' + name
        return super().send_head()

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('X-Robots-Tag', 'noindex, nofollow, noarchive')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self' data:; worker-src 'self' blob:; connect-src 'self' blob:; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'self'")
        super().end_headers()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--port', type=int, default=8767)
    a = p.parse_args()
    root = a.root.resolve()
    server = ThreadingHTTPServer(('127.0.0.1', a.port), partial(ShareHandler, directory=str(root)))
    server.root = root
    server.public_files = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and not p.name.startswith('.') and p.name not in {'_headers', '_redirects'}}
    print(f'Sharing {len(server.public_files)} public assets at http://127.0.0.1:{a.port}', flush=True)
    server.serve_forever()
