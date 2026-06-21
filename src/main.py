import sys

import lex
import obj


def main():
    path = sys.argv[1]

    stream = lex.tokenize(path)
    root = obj.AstProg.parse(stream)
    root.run()



if __name__ == "__main__":
    main()

