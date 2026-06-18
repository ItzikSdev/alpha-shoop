#!/usr/bin/env python3
"""One-time script to get a Shopify offline access token via OAuth."""
import hashlib
import hmac
import http.server
import os
import secrets
import threading
import urllib.parse
import urllib.request
import json
import webbrowser

CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "0dfe5685f422a744caa5effc1b88e304")
CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")  # set in env: export SHOPIFY_CLIENT_SECRET=shpss_...
SHOP          = os.environ.get("SHOPIFY_SHOP", "kgg8n0-k0.myshopify.com")
REDIRECT_URI  = "http://localhost:3333/callback"
SCOPES        = "write_products,read_products,write_inventory,read_inventory,write_orders,read_orders,write_fulfillments,read_fulfillments,read_themes,write_themes,read_online_store_navigation,write_online_store_navigation,read_script_tags,write_script_tags,read_metaobjects,write_metaobjects,read_publications,write_publications"

state = secrets.token_hex(16)
result = {}
done = threading.Event()


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if parsed.path != "/callback" or params.get("state") != state:
            self.send_error(400, "Bad request")
            return

        code = params.get("code", "")
        data = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
        }).encode()

        req = urllib.request.Request(
            f"https://{SHOP}/admin/oauth/access_token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())

        result["token"] = body.get("access_token", "")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>Got it! You can close this tab and return to your terminal.</h2>")
        done.set()


auth_url = (
    f"https://{SHOP}/admin/oauth/authorize"
    f"?client_id={CLIENT_ID}"
    f"&scope={urllib.parse.quote(SCOPES)}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&state={state}"
    f"&grant_options[]=offline"
)

server = http.server.HTTPServer(("localhost", 3333), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

print("\n Opening Shopify authorization in your browser...")
print(f" If it doesn't open, go to:\n {auth_url}\n")
webbrowser.open(auth_url)

done.wait(timeout=120)
server.shutdown()

token = result.get("token", "")
if token:
    print(f"\n SUCCESS!\n")
    print(f" Add this to your .env file:\n")
    print(f" SHOPIFY_ACCESS_TOKEN={token}\n")

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            content = f.read()
        if "SHOPIFY_ACCESS_TOKEN=" in content:
            lines = []
            for line in content.splitlines():
                if line.startswith("SHOPIFY_ACCESS_TOKEN="):
                    lines.append(f"SHOPIFY_ACCESS_TOKEN={token}")
                else:
                    lines.append(line)
            with open(env_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            print(f" .env updated automatically!")
        else:
            print(f" (add it manually to .env)")
else:
    print("\n No token received. Try again.")
