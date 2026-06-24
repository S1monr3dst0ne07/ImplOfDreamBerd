
import sys


def error(msg):
    print(f"Error: {msg}")
    _trace()

def internal(msg):
    print(f"INTERNAL ERROR (this is most certainly a bug): {msg}")
    _trace()

def token(token, msg):
    print(f"Error on line {token.line}: {msg}")
    _trace()

def _trace():
    #import traceback
    #traceback.print_stack()
    sys.exit(1)
