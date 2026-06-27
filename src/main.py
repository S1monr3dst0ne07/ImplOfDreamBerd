import sys

import lex
import tree
import obj
import conf


def main():
    path = sys.argv[1]

    root = tree.AstProg.load(path)

    try:
        root.run()
    except KeyboardInterrupt: 
        pass



if __name__ == "__main__":
    main()

