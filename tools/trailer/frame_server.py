"""Tiny local receiver for trailer frames: POST /f/<name> writes the body to <outdir>/<name>.jpg."""
import http.server, os, sys
OUT = sys.argv[1]

class H(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(n)
        name = os.path.basename(self.path.rstrip('/'))
        with open(os.path.join(OUT, name + '.jpg'), 'wb') as f:
            f.write(data)
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *a):
        pass

http.server.ThreadingHTTPServer(('127.0.0.1', 8765), H).serve_forever()
