#!/usr/bin/env python3
"""One-time YouTube OAuth credential bootstrap (Task 8).

Prompts for the Google Cloud OAuth client_secret.json path, runs the
installed-app flow via a local loopback server, and stores the resulting
refresh token as instance/tokens/token_<label>.json with 0600 permissions.

Usage:
    python scripts/setup_youtube_oauth.py [--secret-file PATH] [--label dev]
"""
import argparse
import os
import re
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from src.services.providers import youtube_uploader  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--secret-file',
                        help='path to the Google OAuth client_secret.json')
    parser.add_argument('--label', default='dev',
                        help='token label; stored as token_<label>.json')
    args = parser.parse_args(argv)

    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', args.label):
        sys.exit('--label must match [A-Za-z0-9_-]{1,32}')

    secret = args.secret_file or input('Path to client_secret.json: ').strip()
    if not os.path.exists(secret):
        sys.exit(f'client secret not found: {secret}')
    os.environ['GOOGLE_CLIENT_SECRET_FILE'] = os.path.abspath(secret)

    flow = youtube_uploader._make_flow()
    print('Opening browser for Google consent (youtube.upload scope)...')
    flow.run_local_server(port=0, access_type='offline', prompt='consent')

    path = youtube_uploader.save_token(flow.credentials, args.label)
    print(f'Token saved: {path} (mode 0600)')


if __name__ == '__main__':
    main()
