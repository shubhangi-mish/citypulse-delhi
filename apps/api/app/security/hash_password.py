"""Generate an OPERATOR_ACCOUNTS entry: uv run python -m app.security.hash_password <username>"""

import getpass
import sys

from app.security.auth import hash_password

if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else input("Operator username: ")
    pw = getpass.getpass("Password: ")
    if len(pw) < 10:
        sys.exit("Use at least 10 characters.")
    print(f"{user}:{hash_password(pw)}")
