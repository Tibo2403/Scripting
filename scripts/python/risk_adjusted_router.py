"""Run the local risk-adjusted HTTP router."""

from http.server import ThreadingHTTPServer
from risk_router_http import Handler


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 4001), Handler)
    print("Risk-adjusted router listening on http://127.0.0.1:4001")
    server.serve_forever()



if __name__ == "__main__":
    main()
