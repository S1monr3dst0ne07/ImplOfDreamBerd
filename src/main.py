import sys

import lex


def main():
    path = sys.argv[1]

    stream = lex.tokenize(path)
    print(stream)


if __name__ == "__main__":
    main()

