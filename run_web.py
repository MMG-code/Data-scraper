"""Launch the Restaurant Data Scraper web interface."""

from web.app import app

if __name__ == "__main__":
    print("\n  Restaurant Data Scraper - Web UI")
    print("  ================================")
    print("  Open your browser to: http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
