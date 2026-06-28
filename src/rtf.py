
from dataclasses import dataclass as dc

# yes, this file contains a rich text parser. 
# *sighs* what am i doing with my life?


def tokenize(src) -> "iterator":
    buffer = ""
    state = None
    for char in src + '\0':
        match char:
            case '{': kind = 'bopen' #}
            case '}': kind = 'bclose'
            case '\\': kind = 'command'
            case ' ': kind = 'space'
            case '\n': kind = 'newline'
            case x if x.isalpha(): kind = 'alpha'
            case x if x.isdigit(): kind = 'digit'
            case "'": kind = 'single'
            case '\0': kind = 'terminator'
            case _: kind = 'symb'

        emit = state != kind
        override = state in ('bopen', 'bclose', 'newline')

        def _emit():
            nonlocal buffer
            #weird compounds
            if state == 'alpha'  and kind == 'digit': return
            if state == 'single' and kind == 'digit': return

            res = "".join(buffer)
            buffer = ""
            return res

        if state and (emit or override):
            res = _emit()
            if res is not None:
                yield res

        buffer += char
        state = kind




# *collars and leashes you* let's go for walkies!
# (i think i'm loosing it)
def walkies(stream):
    #some block can be ignored.
    # for example, metadata blocks
    emit = True

    buffer = []
    def _read_cmd(cmd):
        nonlocal buffer, emit
        # decide what to do with command word

        match cmd:
            #constructive command
            case 'u8220': buffer += ['"']
            case 'u8221': buffer += ['"']
            case 'par': buffer += '\n'

            # wow the fancy stuff right here
            case 'b': buffer += 'rtf_bold_'
            case 'i': buffer += 'rtf_ital_'

            #destructive command
            case 'fonttbl': emit = False
            case 'colortbl': emit = False
            case 'stylesheet': emit = False
            case '*': emit = False

    def _read_word(word):
        nonlocal buffer
        buffer.append(word)

    while True: 
        word = next(stream)
        match word:
            case '}': break
            case '\\': 
                _read_cmd(next(stream))
            case '{': #}
                buffer += walkies(stream)

            #ignore space after command word (idk why)
            case ' '  if last == '\\': continue

            #also newline can be ignored
            case '\n': pass

            # probably normal word
            case word:
                _read_word(word)

        last = word

    return buffer if emit else []

def preprocess(src):
    stream = tokenize(src)

    assert next(stream) == '{' #}
    segs = walkies(stream)
    prog = "".join(segs)
    
    print('=== rich text extracted program ===')
    print(prog)
    print('=== execution ===\n')

    return prog



