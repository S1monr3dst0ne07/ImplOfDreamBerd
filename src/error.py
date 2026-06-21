
import sys


def error(msg):
    print(f"Error: {msg}")
    sys.exit(1)

def token(token, msg):
    print(f"Error on line {token.line}: {msg}")
    sys.exit(1)
