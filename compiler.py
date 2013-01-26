from secd import *
import logging

global logger
logger = logging.getLogger('pysecd_compiler')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


# Keywords of our Lisp:
IF      = 'IF'
NULL    = 'NULL'
NIL     = 'NIL'
LAMBDA  = 'LAMBDA'
LET     = 'LET'
LETREC  = 'LETREC'
LIST    = 'LIST'

def flatten1L(x):
    """
    Utility function for flattening a list of lists.

    >>> flatten1L([[1], [2, 3], [4]])
    [1, 2, 3, 4]

    Does not go more than one level deep:
    >>> flatten1L([[1], [2, 3], [4, [5, 6]]])
    [1, 2, 3, 4, [5, 6]]
    """

    return [inner for outer in x for inner in outer]

def is_atom(e):
    """
    An atom is NIL, an integer, or an identifier (a string).

    >>> is_atom(NIL)
    True

    >>> is_atom(3)
    True

    >>> is_atom('foo')
    True

    >>> is_atom([1, 2, 3])
    False
    """

    return e == NIL or type(e) == int or type(e) == str

def is_builtin(e):
    """
    A number of SECD opcodes are considered to be built-in
    functions in the language.
    """

    return e in [ADD, SUB, MUL, DIV, WRITEI, WRITEC, CAR, CDR] # FIXME Any other builtins?

def compile_builtin(args, n, c):
    """
    Compile the arguments 'args' for a built-in function with current
    name list 'n', and code suffix 'c'.

    >>> compile_builtin([1, 2], [], [ADD, STOP])
    ['LDC', 2, 'LDC', 1, 'ADD', 'STOP']

    >>> compile_builtin([1, [MUL, 3, 4]], [], [ADD, STOP])
    ['LDC', 4, 'LDC', 3, 'MUL', 'LDC', 1, 'ADD', 'STOP']

    """

    if args == []:
        return c
    else:
        return compile_builtin(args[1:], n, compile(args[0], n, c))

def compile_app(args, n, c):
    """
    Compile a lambda application.

    ((lambda (x y) (- x y)) 8 9) corresponds to:

    >>> lambda_expr = [LAMBDA, ['x', 'y'], [SUB, 'x', 'y']]
    >>> code = compile([lambda_expr, 8, 9], [], [WRITEI, STOP])
    >>> print code
    ['NIL', 'LDC', 9, 'CONS', 'LDC', 8, 'CONS', 'LDF', ['LD', [1, 2], 'LD', [1, 1], 'SUB', 'RTN'], 'AP', 'WRITEI', 'STOP']

    >>> s = SECD()
    >>> s.load_program(code)
    >>> for _ in range(12): s.execute_opcode()
    -1

    """

    if args == []:
        return c
    else:
        return compile_app(args[1:], n, compile(args[0], n, [CONS] + c))

def compile_if(test, then_code, else_code, n, c):
    """
    Compile an 'if' form. We use SEL to choose the then_code or
    else_code to execute.

    >>> code = compile([IF, 1, [WRITEI, 111], [WRITEI, 222]], [], [STOP])
    >>> print code
    ['LDC', 1, 'SEL', ['LDC', 111, 'WRITEI', 'JOIN'], ['LDC', 222, 'WRITEI', 'JOIN'], 'STOP']
    >>> s = SECD()
    >>> s.load_program(code)
    >>> for _ in range(6): s.execute_opcode()
    111
    <BLANKLINE>
    MACHINE HALTED!
    <BLANKLINE>

    >>> code = compile([IF, 0, [WRITEI, 111], [WRITEI, 222]], [], [STOP])
    >>> print code
    ['LDC', 0, 'SEL', ['LDC', 111, 'WRITEI', 'JOIN'], ['LDC', 222, 'WRITEI', 'JOIN'], 'STOP']

    >>> s = SECD()
    >>> s.load_program(code)
    >>> for _ in range(6): s.execute_opcode()
    222
    <BLANKLINE>
    MACHINE HALTED!
    <BLANKLINE>

    """

    global logger
    logger.debug('compile_if: test: %s; then_code: %s; else_code: %s, n: %s, c: %s',
                 str(test), str(then_code), str(else_code), str(n), str(c))

    return compile(test, n, [SEL] + [compile(then_code, n, [JOIN])]
                                  + [compile(else_code, n, [JOIN])]
                                  + c)


def index(e, n):
    """
    Auxilliary function for the SECD compiler. Taken from
    Figure 7-22 of K1991.

    FIXME doctest!
    """

    def indx2(e, n, j):
        if len(n) == 0:
            return []
        elif n[0] == e:
            return j
        else:
            return indx2(e, n[1:], j + 1)

    def indx(e, n, i):
        if len(n) == 0:
            return []

        j = indx2(e, n[0], 1)

        if j == []:
            return indx(e, n[1:], i + 1) # typo 2nd last line in Figure 7-22: refers to index instead of indx
        else:
            return [i, j] # FIXME typo in K1991? Should be [j, i]? Originally had this: [i, j]

    rval = indx(e, n, 1)

    if rval == []:
        return rval
    else:
        assert len(rval) == 2
        assert type(rval[0]) == int
        assert type(rval[1]) == int
        return rval

def compile_lambda(body, n, c):
    """
    Compile a lambda expression.

    >>> compile_lambda([ADD, 1, 2], [], [STOP])
    ['LDF', ['LDC', 2, 'LDC', 1, 'ADD', 'RTN'], 'STOP']

    """

    return [LDF, compile(body, n, [RTN])] + c

def compile(e, n, c):
    """
    Compile an expression 'e', given a namelist 'n', and an
    accumulating parameter 'c'.

    This function is an almost direct copy of Figure 7-21 of K1991.

    >>> compile(NIL, [], [STOP])
    ['NIL', 'STOP']

    >>> compile(3, [], [STOP])
    ['LDC', 3, 'STOP']

    FIXME doctest where we use index(e, n) in the is_atom(e) branch.

    >>> compile([ADD, 1, 2], [], [STOP])
    ['LDC', 2, 'LDC', 1, 'ADD', 'STOP']

    FIXME doctest LAMBDA

    >>> compile([IF, 1, 2, 3], [], [STOP])
    ['LDC', 1, 'SEL', ['LDC', 2, 'JOIN'], ['LDC', 3, 'JOIN'], 'STOP']

    >>> code = compile([LET, ['x', 'y'], [5, 7], [SUB, 'x', 'y']], [], [STOP])
    >>> s = SECD()
    >>> s.load_program(code)
    >>> for _ in range(12): s.execute_opcode()
    <BLANKLINE>
    MACHINE HALTED!
    <BLANKLINE>

    >>> s.dump_registers()
    S: address = 67 value: [-2]
    E: address = 3 value: []
    C: address = 45 value: 45
    D: address = 4 value: []

    >>> c = compile([LIST, 1, 2, 3], [], [STOP])
    >>> print c
    ['NIL', 'LDC', 3, 'CONS', 'LDC', 2, 'CONS', 'LDC', 1, 'CONS', 'STOP']
    >>> s = SECD()
    >>> s.load_program(c)
    >>> for _ in range(7): s.execute_opcode()
    >>> s.dump_registers()
    S: address = 29 value: [[1, 2, 3]]
    E: address = 3 value: []
    C: address = 25 value: 25
    D: address = 4 value: []

    >>> c = compile([LET, ['x'], [[LIST, 1, 2, 3]], [CAR, 'x']], [], [WRITEI, STOP])
    >>> print c
    ['NIL', 'NIL', 'LDC', 3, 'CONS', 'LDC', 2, 'CONS', 'LDC', 1, 'CONS', 'CONS', 'LDF', ['LD', [1, 1], 'CAR', 'RTN'], 'AP', 'WRITEI', 'STOP']
    >>> s = SECD()
    >>> s.load_program(c)
    >>> for _ in range(15): s.execute_opcode()
    1

    FIXME doctest letrec

    FIXME doctest 'fcn must be a variable'

    >>> compile([LAMBDA, ['x', 'y'], [ADD, 'x', 'y']], [], [STOP])
    ['LDF', ['LD', [1, 2], 'LD', [1, 1], 'ADD', 'RTN'], 'STOP']

    >>> compile([[LAMBDA, ['x', 'y'], [ADD, 'x', 'y']], 8, 9], [], [STOP])
    ['NIL', 'LDC', 9, 'CONS', 'LDC', 8, 'CONS', 'LDF', ['LD', [1, 2], 'LD', [1, 1], 'ADD', 'RTN'], 'AP', 'STOP']

    """

    global logger

    logger.debug('compile: e: %s; n: %s, c: %s', str(e), str(n), str(c))

    if is_atom(e):
        logger.debug('compile: decided that <%s> is an atom', str(e))
        if e == NIL:
            return [NIL] + c
        else:
            ij = index(e, n)
            if ij == []:
                return [LDC] + [e] + c
            else:
                return [LD]  + [ij]  + c
    else:
        fcn  = e[0]
        args = e[1:]
        logger.debug('compile: othewise, <%s> is a function <%s> with args <%s>', str(e), str(fcn), str(args))

        if is_atom(fcn): # builtin, lambda, or special form
            if is_builtin(fcn):
                logger.debug('compile: fcn is a built-in')
                return compile_builtin(args, n, [fcn] + c)
            elif fcn == LIST:
                # My own convenient built-in for making lists. Sample use:
                # [LIST, 1, 2, 3] => [1, 2, 3].
                #
                # FIXME Not sure how this would behave on examples other than
                # a simple list of ints, variable names, etc.
                list_body = flatten1L([compile(list_item, n, [CONS]) for list_item in args][::-1])
                return [NIL] + list_body + c
            elif fcn == LAMBDA:
                logger.debug('compile: fcn is a LAMBDA')
                assert len(args) == 2 # [name list, body]
                return compile_lambda(args[1], [args[0]] + n, c)
            elif fcn == IF:
                logger.debug('compile: fcn is an IF')
                return compile_if(args[0], args[1], args[2], n, c)
            elif fcn == LET or fcn == LETREC:
                newn   = [args[0]] + n
                values = args[1]
                body   = args[2]

                if fcn == LET:
                    logger.debug('compile: fcn is LET')
                    return [NIL]      + compile_app(values, n,    compile_lambda(body, newn, [AP] + c)) # another typo in Figure 7-21: cons(AP, C) -> cons(AP, c)
                elif fcn == LETREC:
                    logger.debug('compile: fcn is LETREC')
                    return [DUM, NIL] + compile_app(values, newn, compile_lambda(body, newn, [RAP] + c))
            else: # fcn must be a variable FIXME is this comment correct?
                logger.debug('compile: fcn is a variable? FIXME')
                return [NIL] + compile_app(args, n, [LD] + index(fcn, n) + [AP] + c)

        else: # an application with nested function
            return [NIL] + compile_app(args, n, compile(fcn, n, [AP] + c))

if __name__ == '__main__':
    print 'boo'
