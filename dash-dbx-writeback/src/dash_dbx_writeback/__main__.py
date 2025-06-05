"""
Entry point for running the Dash AG-Grid Writeback application as a module.
"""

from .app import app

if __name__ == "__main__":
    app.run(debug=True)
