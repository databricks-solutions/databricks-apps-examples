#!/usr/bin/env python
"""Runner script for the Dash Coles RO application."""

from src.excel_like_dash.app import app

if __name__ == "__main__":
    app.run(debug=True)
