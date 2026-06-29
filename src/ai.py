

import conf


# this preprocessing is line-based
#  because otherwise it would be impossible
#  to determine where a statement/string should end.
#  this also means multiline strings are impossible.
#  ai can be turned up in the config for this reason.


def preprocess(src):
    out = ""


    quotes = {
        "'" : 1,
        '"' : 2,
    }

    for line in src.split('\n'):
        
        quote_size = 0
        quote_depth = 0

        paren_depth = 0
        
        last = None 
        for char in line + '\0':
            match char:
                case '(': paren_depth += 1
                case ')': paren_depth -= 1
                case x if x in quotes:
                    quote_size += quotes[char]

            if last in quotes and char not in quotes:
                #done building
                if quote_depth == 0:
                    #start of string
                    quote_depth = quote_size
                    quote_size = 0
                elif quote_size == quote_depth:
                    #end of string
                    quote_depth = 0

            last = char

        out += line 
        out += ('"' * (quote_depth >> 1)) + ("'" if quote_depth & 1 else "")
        out += ')' * (paren_depth if paren_depth > 0 else 0)
        
        if line.strip() != "" and "!" not in line:
            out += '!'

        out += '\n'
        
    return out                    

    




