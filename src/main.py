import sys

import lex
import tree
import obj
import conf


def main():
    path = sys.argv[1]

    stream = lex.tokenize(path)
    root = tree.AstProg.parse(stream)

    try:
        root.run()
    except KeyboardInterrupt: 
        pass



if __name__ == "__main__":
    main()

