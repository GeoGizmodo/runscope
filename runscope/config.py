"""
runscope.config -- configuration placeholders for the (optional, future) cloud tier.

The free client is 100% LOCAL and needs none of this. These settings only matter for
the upcoming RunScope Pro cloud sync (cross-machine history, alerts). Everything is
read from ENVIRONMENT VARIABLES at runtime -- never hardcode credentials, and never
commit a .env file. There are intentionally NO secret values in this repo.

Environment variables (all optional; unset = local-only, the default):
  RUNSCOPE_API_URL     Base URL of the RunScope cloud API (Pro).      e.g. https://api.runscope.dev
  RUNSCOPE_TOKEN       Your personal API token for the cloud API.     (obtain from your account)
  RUNSCOPE_LICENSE     License key for paid features after the free period.
  RUNSCOPE_HOME        Where local history/config live.               default: ~/.runscope
  RUNSCOPE_NO_TELEMETRY Set to 1 to disable any future anonymous usage ping (opt-out).

Nothing here transmits your code or data. Cloud sync, when it ships, will be
opt-in and clearly disclosed.
"""
import os

# --- cloud (Pro) -- all default to None/off; the client works fully without them ---
API_URL = os.environ.get("RUNSCOPE_API_URL")          # e.g. "https://api.runscope.dev"
TOKEN = os.environ.get("RUNSCOPE_TOKEN")              # personal API token (never hardcode)
LICENSE_KEY = os.environ.get("RUNSCOPE_LICENSE")      # paid features after free period

# --- local ---
HOME = os.environ.get("RUNSCOPE_HOME") or os.path.join(
    os.path.expanduser("~"), ".runscope")

# --- telemetry (not implemented yet; will be opt-in + disclosed when it is) ---
TELEMETRY_DISABLED = os.environ.get("RUNSCOPE_NO_TELEMETRY") == "1"


def cloud_enabled():
    """True only if the user has configured cloud sync (Pro). Off by default."""
    return bool(API_URL and TOKEN)
