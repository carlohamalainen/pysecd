#!/usr/bin/env python

"""
Toy implementation of the SECD abstract machine. Follows the
presentation by Peter M. Kogge, The Architecture of Symbolic Computers,
1991, McGraw Hill.

Author: Carlo Hamalainen <carlo.hamalainen@gmail.com>
"""

try:
    import pydot
    from pydotutils import pydot_record_string
except:
    pass

import sys

# We have a fixed amount of memory available.
MAX_ADDRESS = 1000

# Memory cells hold either an integer or a nonterminal. For simplicity we
# store an integer as the tuple (TAG_INTEGER, x) where type(x) == int, and
# a nonterminal is of the form (TAG_NONTERMINAL, car, cdr) where car and cdr
# are memory locations.

TAG_INTEGER     = 'INT'
TAG_NONTERMINAL = 'NT'

# Opcodes are stored in memory as strings. This is cheating (really we should have
# a bijection ADD <-> 100, MUL <-> 101, etc) but it simplifies debugging.

# Names to make writing code a bit more pleasant (avoids
# heaps of string quoting).
ADD     = 'ADD'
AP      = 'AP'
CAR     = 'CAR'
CDR     = 'CDR'
CONS    = 'CONS'
DIV     = 'DIV'
DUM     = 'DUM'
JOIN    = 'JOIN'
LD      = 'LD'
LDC     = 'LDC'
LDF     = 'LDF'
MUL     = 'MUL'
NIL     = 'NIL'
NULL    = 'NULL'
RAP     = 'RAP'
READC   = 'READC'
READI   = 'READI'
RTN     = 'RTN'
SEL     = 'SEL'
STOP    = 'STOP'
SUB     = 'SUB'
WRITEC  = 'WRITEC'
WRITEI  = 'WRITEI'

ZEROP   = 'ZEROP'
GT0P    = 'GT0P'
LT0P    = 'LT0P'

OP_CODES = [ADD,      # integer addition
            MUL,      # integer multiplication
            SUB,      # integer subtraction
            DIV,      # integer division

            NIL,      # push nil pointer onto the stack
            CONS,     # cons the top of the stack onto the next list
            LDC,      # push a constant argument (any S-expression) onto the stack
            LDF,      # load function
            AP,       # function application
            LD,       # load a variable
            CAR,      # value of car cell
            CDR,      # value of cdr cell

            DUM,      # setup recursive closure list
            RAP,      # recursive apply

            JOIN,     # pop a list reference from the dump stack and set C to this value
            RTN,      # return from function
            SEL,      # logical selection (used to implement an if/then/else branch)
            NULL,     # test if list is empty

            WRITEI,   # write an integer to the terminal
            WRITEC,   # write a character to the terminal, e.g. 96 -> 'a'

            READC,    # read a single character from the terminal
            READI,    # read an integer from the terminal

            STOP,     # halt the machine

            ZEROP,    # test if top of stack is zero (does not consume the element)                 [nonstandard opcode]
            GT0P,     # test if top of stack is greater than zero (does not consume the element)    [nonstandard opcode]
            LT0P,     # test if top of stack is less    than zero (does not consume the element)    [nonstandard opcode]

           ]
OP_CODES = dict([(op, True) for op in OP_CODES])


class SECD:
    def __init__(self):
        # Memory of the machine. A 'None' indicates an unused cell. Note that
        # 0 is never used because that corresponds to nil.
        self.memory = [None] + [None]*MAX_ADDRESS
        self.max_used_address = 1

        # By default WRITEI and WRITEC write to stdout.
        self.output_stream = sys.stdout
        self.input_stream  = sys.stdin

        self.debug = False

        # Registers:
        self.registers = {}

        # The main stack:
        self.registers['S'] = self.get_new_address()
        self.set_nonterminal(self.registers['S'], 0, 0)

        # The program counter; points to a memory location:
        self.registers['C'] = -1 # initialised later

        # The environment stack:
        self.registers['E'] = self.get_new_address()
        self.set_nonterminal(self.registers['E'], 0, 0)

        # The dump stack:
        self.registers['D'] = self.get_new_address()
        self.set_nonterminal(self.registers['D'], 0, 0)

        assert self.max_used_address < MAX_ADDRESS

    def dump_registers(self):
        """
        Dump to stdout the address of the registers S, E and D,
        and the values of each. The register C (the program counter)
        always stores an integer.

        >>> m = SECD()
        >>> m.dump_registers()
        S: address = 2 value: []
        E: address = 3 value: []
        C: address = -1 value: -1
        D: address = 4 value: []

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.push_stack('S', new_cell)
        >>> m.dump_registers()
        S: address = 6 value: [123]
        E: address = 3 value: []
        C: address = -1 value: -1
        D: address = 4 value: []
        """

        print 'S: address =', self.registers['S'], 'value:', self.get_value(self.registers['S'])
        print 'E: address =', self.registers['E'], 'value:', self.get_value(self.registers['E'])
        print 'C: address =', self.registers['C'], 'value:', self.registers['C']
        print 'D: address =', self.registers['D'], 'value:', self.get_value(self.registers['D'])

    def dump_memory(self):
        """
        Dump to stdout each cell of the machine's memory, ignoring
        cells that have not been used yet. Each line has two items:
        the memory address (an integer) and the contents of the
        cell, a tuple indicating the type (integer or nonterminal)
        and the contents.

        >>> m = SECD()
        >>> m.dump_memory()
        2 ('NT', 0, 0)
        3 ('NT', 0, 0)
        4 ('NT', 0, 0)

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.push_stack('S', new_cell)
        >>> m.dump_memory()
        2 ('NT', 0, 0)
        3 ('NT', 0, 0)
        4 ('NT', 0, 0)
        5 ('INT', 123)
        6 ('NT', 5, 2)

        """

        for a in range(1, len(self.memory)):
            if self.memory[a] is None: continue
            print a, self.memory[a]

    def get_new_address(self):
        """
        Return the address of an unused memory cell.

        >>> m = SECD()
        >>> m.get_new_address()
        5
        >>> m.get_new_address()
        6
        """

        self.max_used_address += 1
        assert self.max_used_address < MAX_ADDRESS, 'Error, out of memory.'
        return self.max_used_address

    def tag(self, address):
        """
        All memory cells have a tag, indicating if the cell stores
        an integers (TAG_INTEGER) or nonterminal (TAG_NONTERMINAL).

        >>> m = SECD()

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.tag(new_cell)
        'INT'

        >>> new_cell = m.get_new_address()
        >>> m.set_nonterminal(new_cell, 0, 0) # two nil pointers
        >>> m.tag(new_cell)
        'NT'
        """

        return self.memory[address][0]

    def push_stack(self, stack_name, new_cell):
        """
        Push a cell onto the top of the given stack.

        >>> m = SECD()
        >>> m.get_value(m.registers['S'])
        []

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.push_stack('S', new_cell)
        >>> m.get_value(m.registers['S'])
        [123]

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 456)
        >>> m.push_stack('S', new_cell)
        >>> m.get_value(m.registers['S'])
        [456, 123]
        """

        new_head = self.get_new_address()
        self.set_nonterminal(new_head, new_cell, self.registers[stack_name])
        self.registers[stack_name] = new_head

    def pop_stack(self, stack_name):
        """
        Pop the top element off the stack.

        >>> m = SECD()

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.push_stack('S', new_cell)

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 456)
        >>> m.push_stack('S', new_cell)

        >>> m.get_value(m.registers['S'])
        [456, 123]

        >>> m.pop_stack('S')
        >>> m.get_value(m.registers['S'])
        [123]

        >>> m.pop_stack('S')
        >>> m.get_value(m.registers['S'])
        []
        """

        assert self.tag(self.registers[stack_name]) == TAG_NONTERMINAL
        self.registers[stack_name] = self.cdr(self.registers[stack_name])

    def car(self, address):
        """
        Address register value of a nonterminal cell.

        >>> m = SECD()

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.push_stack('S', new_cell)

        >>> m.car(m.registers['S'])
        5

        >>> m.get_value(5)
        123
        """

        assert self.memory[address][0] == TAG_NONTERMINAL
        return self.memory[address][1]

    def cdr(self, address):
        """
        Data register value of a nonterminal cell.

        >>> m = SECD()

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.push_stack('S', new_cell)

        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 456)
        >>> m.push_stack('S', new_cell)

        >>> m.get_value(m.registers['S'])
        [456, 123]

        >>> m.car(m.registers['S'])
        7
        >>> m.get_value(7)
        456

        >>> m.car(m.cdr(m.registers['S']))
        5
        >>> m.get_value(5)
        123
        """

        assert self.memory[address][0] == TAG_NONTERMINAL
        return self.memory[address][2]

    def set_int(self, address, x):
        """
        Set a memory cell to store an integer. We cheat a little here
        and allow a string to be stored in an integer cell as long
        as it refers to an opcode.

        >>> m = SECD()
        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.memory[new_cell]
        ('INT', 123)

        """

        assert type(x) == int or (type(x) == str and x in OP_CODES)
        self.memory[address] = (TAG_INTEGER, x)

    def get_int(self, address):
        """
        Get the integer value of a memory cell.

        >>> m = SECD()
        >>> new_cell = m.get_new_address()
        >>> m.set_int(new_cell, 123)
        >>> m.get_int(new_cell)
        123
        """

        assert self.memory[address][0] == TAG_INTEGER
        return self.memory[address][1]

    def set_nonterminal(self, address, car_value, cdr_value):
        """
        Set a nonterminal node.

        >>> m = SECD()
        >>> new_cell = m.get_new_address()
        >>> m.set_nonterminal(new_cell, 100, 200)
        >>> m.memory[new_cell]
        ('NT', 100, 200)
        """

        self.memory[address] = (TAG_NONTERMINAL, car_value, cdr_value)

    def store_py_list(self, address, x):
        """
        Given the Python list x, store it in the machine's memory
        at 'address' as a linked list. This function uses a basic
        recursive definition so it will fail if x is too large (we
        will hit Python's recursion limit).

        >>> m = SECD()
        >>> new_cell = m.get_new_address()

        >>> m.store_py_list(new_cell, [])
        >>> m.get_value(new_cell)
        []

        >>> m.store_py_list(new_cell, [1])
        >>> m.get_value(new_cell)
        [1]

        >>> m.store_py_list(new_cell, [1, 2, 3])
        >>> m.get_value(new_cell)
        [1, 2, 3]

        >>> m.store_py_list(new_cell, [1, 2, []])
        >>> m.get_value(new_cell)
        [1, 2, []]

        >>> m.store_py_list(new_cell, [[1, 2], [3], [[[4]]], 5])
        >>> m.get_value(new_cell)
        [[1, 2], [3], [[[4]]], 5]

        >>> m.store_py_list(new_cell, [[], [[], []], [[[[ [], [], [[]] ]]]]])
        >>> m.get_value(new_cell)
        [[], [[], []], [[[[[], [], [[]]]]]]]

        """

        if x == []:
            self.memory[address] = (TAG_NONTERMINAL, 0, 0)
        elif type(x[0]) == int or (type(x[0]) == str and x[0] in OP_CODES):
            car_address = self.get_new_address()
            cdr_address = self.get_new_address()

            self.set_int(car_address, x[0])
            self.store_py_list(cdr_address, x[1:])

            self.set_nonterminal(address, car_address, cdr_address)
        elif type(x[0]) == list:
            car_address = self.get_new_address()
            cdr_address = self.get_new_address()

            self.store_py_list(car_address, x[0])
            self.store_py_list(cdr_address, x[1:])

            self.set_nonterminal(address, car_address, cdr_address)
        else:
            assert False, 'Unknown element type: %s' % (str(type(x[0])))

    def get_value(self, address):
        """
        Return a Python object representing the data stored at
        'address'. We will either return an integer or a list. For
        examples see store_py_list().

        Note: this function is not the inverse of store_py_list()
        due to the possible existence of cycles as created by the
        DUM/RAP opcodes (note the case where '*** RECURSIVE LOOP ***'
        is printed). Also, the nil pointer created by DUM will be
        printed as 'NIL_PTR0', which is not handled by store_py_list().

        >>> m = SECD()
        >>> new_cell = m.get_new_address()

        >>> m.set_int(new_cell, 33)
        >>> m.get_value(new_cell)
        33

        >>> m.store_py_list(new_cell, [1, 2, 3])
        >>> m.get_value(new_cell)
        [1, 2, 3]

        """

        # To avoid infinite loops we maintain a list of
        # visited addresses.
        self.seen_by_get_value = {}
        return self._get_value(address)

    def _get_value(self, address):

        if address in self.seen_by_get_value:
            return ['*** RECURSIVE LOOP ***']

        self.seen_by_get_value[address] = True

        if self.tag(address) == TAG_INTEGER:
            return self.get_int(address)
        elif self.tag(address) == TAG_NONTERMINAL:
            if self.car(address) == 0 and self.cdr(address) == 0:
                return []
            elif self.car(address) == 0 and self.cdr(address) != 0:
                # Special case constructed by DUM.
                return ['NIL_PTR0'] + self._get_value(self.cdr(address))
            else:
                assert self.car(address) != 0
                assert self.cdr(address) != 0
                return [self._get_value(self.car(address))] + self._get_value(self.cdr(address))
        else:
            assert False, 'Unknown tag: %s' % self.tag(address)

    def graph_at_address(self, address):
        """
        Produce a dotty (graphviz) graph representing the linked structure at
        'address'. See draw_graphs() for some examples and associated PNG plots.

        >>> m = SECD()
        >>> new_cell = m.get_new_address()

        >>> m.store_py_list(new_cell, [])
        >>> m.graph_at_address(new_cell).to_string().replace('\\n', '')
        'digraph graphname {rankdir=LR;node5 [shape=record, label="<f0> 5|<f1> nil|<f2> nil"];}'

        >>> m.store_py_list(new_cell, [1])
        >>> m.graph_at_address(new_cell).to_string().replace('\\n', '')
        'digraph graphname {rankdir=LR;node5 [shape=record, label="<f0> 5|<f1> car 6|<f2> cdr 7"];node5:f1 -> node6:f0;node5:f2 -> node7:f0;node6 [shape=record, label="<f0> 6|<f1> 1"];node7 [shape=record, label="<f0> 7|<f1> nil|<f2> nil"];}'


        >>> m.store_py_list(new_cell, [1, 2, 3])
        >>> m.graph_at_address(new_cell).to_string().replace('\\n', '')
        'digraph graphname {rankdir=LR;node5 [shape=record, label="<f0> 5|<f1> car 8|<f2> cdr 9"];node5:f1 -> node8:f0;node5:f2 -> node9:f0;node8 [shape=record, label="<f0> 8|<f1> 1"];node9 [shape=record, label="<f0> 9|<f1> car 10|<f2> cdr 11"];node9:f1 -> node10:f0;node9:f2 -> node11:f0;node10 [shape=record, label="<f0> 10|<f1> 2"];node11 [shape=record, label="<f0> 11|<f1> car 12|<f2> cdr 13"];node11:f1 -> node12:f0;node11:f2 -> node13:f0;node12 [shape=record, label="<f0> 12|<f1> 3"];node13 [shape=record, label="<f0> 13|<f1> nil|<f2> nil"];}'


        >>> m.store_py_list(new_cell, [1, 2, []])
        >>> m.graph_at_address(new_cell).to_string().replace('\\n', '')
        'digraph graphname {rankdir=LR;node5 [shape=record, label="<f0> 5|<f1> car 14|<f2> cdr 15"];node5:f1 -> node14:f0;node5:f2 -> node15:f0;node14 [shape=record, label="<f0> 14|<f1> 1"];node15 [shape=record, label="<f0> 15|<f1> car 16|<f2> cdr 17"];node15:f1 -> node16:f0;node15:f2 -> node17:f0;node16 [shape=record, label="<f0> 16|<f1> 2"];node17 [shape=record, label="<f0> 17|<f1> car 18|<f2> cdr 19"];node17:f1 -> node18:f0;node17:f2 -> node19:f0;node18 [shape=record, label="<f0> 18|<f1> nil|<f2> nil"];node19 [shape=record, label="<f0> 19|<f1> nil|<f2> nil"];}'


        >>> m.store_py_list(new_cell, [[1, 2], [3], [[[4]]], 5])
        >>> m.graph_at_address(new_cell).to_string().replace('\\n', '')
        'digraph graphname {rankdir=LR;node5 [shape=record, label="<f0> 5|<f1> car 20|<f2> cdr 21"];node5:f1 -> node20:f0;node5:f2 -> node21:f0;node20 [shape=record, label="<f0> 20|<f1> car 22|<f2> cdr 23"];node20:f1 -> node22:f0;node20:f2 -> node23:f0;node22 [shape=record, label="<f0> 22|<f1> 1"];node23 [shape=record, label="<f0> 23|<f1> car 24|<f2> cdr 25"];node23:f1 -> node24:f0;node23:f2 -> node25:f0;node24 [shape=record, label="<f0> 24|<f1> 2"];node25 [shape=record, label="<f0> 25|<f1> nil|<f2> nil"];node21 [shape=record, label="<f0> 21|<f1> car 26|<f2> cdr 27"];node21:f1 -> node26:f0;node21:f2 -> node27:f0;node26 [shape=record, label="<f0> 26|<f1> car 28|<f2> cdr 29"];node26:f1 -> node28:f0;node26:f2 -> node29:f0;node28 [shape=record, label="<f0> 28|<f1> 3"];node29 [shape=record, label="<f0> 29|<f1> nil|<f2> nil"];node27 [shape=record, label="<f0> 27|<f1> car 30|<f2> cdr 31"];node27:f1 -> node30:f0;node27:f2 -> node31:f0;node30 [shape=record, label="<f0> 30|<f1> car 32|<f2> cdr 33"];node30:f1 -> node32:f0;node30:f2 -> node33:f0;node32 [shape=record, label="<f0> 32|<f1> car 34|<f2> cdr 35"];node32:f1 -> node34:f0;node32:f2 -> node35:f0;node34 [shape=record, label="<f0> 34|<f1> car 36|<f2> cdr 37"];node34:f1 -> node36:f0;node34:f2 -> node37:f0;node36 [shape=record, label="<f0> 36|<f1> 4"];node37 [shape=record, label="<f0> 37|<f1> nil|<f2> nil"];node35 [shape=record, label="<f0> 35|<f1> nil|<f2> nil"];node33 [shape=record, label="<f0> 33|<f1> nil|<f2> nil"];node31 [shape=record, label="<f0> 31|<f1> car 38|<f2> cdr 39"];node31:f1 -> node38:f0;node31:f2 -> node39:f0;node38 [shape=record, label="<f0> 38|<f1> 5"];node39 [shape=record, label="<f0> 39|<f1> nil|<f2> nil"];}'


        """

        self.seen_by_graph_at_address = {} # avoid infinite loops
        graph = pydot.Dot('graphname', graph_type='digraph', rankdir='LR')
        self._graph_at_address(address, graph)
        return graph

    def _graph_at_address(self, address, graph):
        if address in self.seen_by_graph_at_address:
            return
        else:
            self.seen_by_graph_at_address[address] = True

        if self.tag(address) == TAG_INTEGER:
            graph.add_node(pydot.Node(name='node' + str(address),
                                      label=pydot_record_string([str(address), str(self.get_int(address))]),
                                      shape='record'))
        elif self.tag(address) == TAG_NONTERMINAL:
            if self.car(address) == 0 and self.cdr(address) == 0:
                graph.add_node(pydot.Node(name='node' + str(address),
                                          label=pydot_record_string([str(address), 'nil', 'nil']),
                                          shape='record'))
            else:
                if self.car(address) == 0:
                    graph.add_node(pydot.Node(name='node' + str(address),
                                              label=pydot_record_string([str(address), 'nil', str(self.cdr(address))]),
                                              shape='record'))
                    graph.add_edge(pydot.Edge('node%d:f2' % address, 'node%d:f0' % self.cdr(address)))
                    self._graph_at_address(self.cdr(address), graph)
                else:
                    graph.add_node(pydot.Node(name='node' + str(address),
                                              label=pydot_record_string([str(address), ('car %d' % self.car(address)),
                                                                                       ('cdr %d' % self.cdr(address))]),
                                              shape='record'))

                    assert self.car(address) != 0
                    assert self.cdr(address) != 0

                    graph.add_edge(pydot.Edge('node%d:f1' % address, 'node%d:f0' % self.car(address)))
                    graph.add_edge(pydot.Edge('node%d:f2' % address, 'node%d:f0' % self.cdr(address)))

                    self._graph_at_address(self.car(address), graph)
                    self._graph_at_address(self.cdr(address), graph)
        else:
            assert False, 'Unknown tag: %s' % self.tag(address)

    def load_program(self, code, stack=[]):
        """
        Initialise the C register with 'code' and the stack S with 'stack'.

        >>> s = SECD()
        >>> s.load_program([ADD], [100, 42])
        >>> s.get_value(s.registers['C'])
        ['ADD']
        >>> s.get_value(s.registers['S'])
        [100, 42]
        """

        program = self.get_new_address()
        self.store_py_list(program, code)
        self.registers['C'] = program

        self.store_py_list(self.registers['S'], stack)
        self.running = True

    def opcode_ADD(self):
        """
        Integer addition; arguments are taken from the stack.

        >>> s = SECD()
        >>> s.load_program([ADD], [100, 42])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [142]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []
        """

        assert self.get_int(self.car(self.registers['C'])) == ADD

        val1 = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        val2 = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        result = self.get_new_address()
        self.set_int(result, val1 + val2)
        self.push_stack('S', result)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_SUB(self):
        """
        Integer subtraction; arguments are taken from the stack.

        >>> s = SECD()
        >>> s.load_program([SUB], [100, 42])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [58]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []
        """

        assert self.get_int(self.car(self.registers['C'])) == SUB

        val1 = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        val2 = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        result = self.get_new_address()
        self.set_int(result, val1 - val2)
        self.push_stack('S', result)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_MUL(self):
        """
        Integer multiplication; arguments are taken from the stack.

        >>> s = SECD()
        >>> s.load_program([MUL], [100, 42])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [4200]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []
        """

        assert self.get_int(self.car(self.registers['C'])) == MUL

        val1 = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        val2 = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        result = self.get_new_address()
        self.set_int(result, val1*val2)
        self.push_stack('S', result)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_DIV(self):
        """
        Integer division; arguments are taken from the stack.

        >>> s = SECD()
        >>> s.load_program([DIV], [18, 3])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [6]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []
        """

        assert self.get_int(self.car(self.registers['C'])) == DIV

        val1 = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        val2 = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        result = self.get_new_address()
        self.set_int(result, val1/val2)
        self.push_stack('S', result)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_NIL(self):
        """
        Push an empty list (nil) onto the stack. See also CONS.

        >>> s = SECD()
        >>> s.load_program([NIL], [18, 19])
        >>> s.get_value(s.registers['S'])
        [18, 19]
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [[], 18, 19]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []
        """

        assert self.get_int(self.car(self.registers['C'])) == NIL

        new_cell = self.get_new_address()
        self.set_nonterminal(new_cell, 0, 0)
        self.push_stack('S', new_cell)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_LDC(self):
        """
        Load a constant onto the stack. The constant expression
        is whatever follows LDC in C, so it may be an arbitrary
        s-expression.

        >>> s = SECD()
        >>> s.load_program([LDC, 3], [18, 19])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 14 value: [3, 18, 19]
        E: address = 3 value: []
        C: address = 9 value: 9
        D: address = 4 value: []

        >>> s = SECD()
        >>> s.load_program([LDC, [3, 4, [18]]], [1])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 20 value: [[3, 4, [18]], 1]
        E: address = 3 value: []
        C: address = 9 value: 9
        D: address = 4 value: []
        """

        assert self.get_int(self.car(self.registers['C'])) == LDC

        self.push_stack('S', self.car(self.cdr(self.registers['C'])))

        self.registers['C'] = self.cdr(self.registers['C']) # skip LDC
        self.registers['C'] = self.cdr(self.registers['C']) # skip the constant expression

    def opcode_LDF(self):
        """
        Builds a closure for the code immediately after LDF. The
        function's parameters are to be found on the top of the
        stack. Note that LDF doesn't start the execution of the
        function - this happens when an appropriate AP opcode is
        executed.

        >>> s = SECD()
        >>> s.load_program([LDC, [3, 4], LDF, [LD, [1, 2], LD, [1, 1], ADD, RTN], AP, WRITEI, STOP,], [500])
        >>> s.store_py_list(s.registers['E'], [[99, 999]]) # pretend that this is the enclosing environment
        >>> s.dump_registers()
        S: address = 2 value: [500]
        E: address = 3 value: [[99, 999]]
        C: address = 5 value: 5
        D: address = 4 value: []

        Push [3, 4] onto the stack (these are the function's parameters):

        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 52 value: [[3, 4], 500]
        E: address = 3 value: [[99, 999]]
        C: address = 9 value: 9
        D: address = 4 value: []

        Run LDF, which pushes the code portion onto the stack and
        moves C to the code after the function:

        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 53 value: [[['LD', [1, 2], 'LD', [1, 1], 'ADD', 'RTN'], [[99, 999]]], [3, 4], 500]
        E: address = 3 value: [[99, 999]]
        C: address = 17 value: 17
        D: address = 4 value: []

        >>> s.get_value(s.registers['C'])
        ['AP', 'WRITEI', 'STOP']

        Execute AP, which saves a copy of the program counter, environment, and stack:

        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 60 value: []
        E: address = 61 value: [[3, 4], [99, 999]]
        C: address = 16 value: 16
        D: address = 59 value: [['WRITEI', 'STOP'], [[99, 999]], [500]]

        Now we can execute the function itself:

        >>> s.get_value(s.registers['C'])
        ['LD', [1, 2], 'LD', [1, 1], 'ADD', 'RTN']

        >>> s.execute_opcode() # LD
        >>> s.execute_opcode() # LD
        >>> s.execute_opcode() # ADD
        >>> s.execute_opcode() # RTN

        >>> s.execute_opcode() # WRITEI
        7

        Now an example of a nested call. Evaluates (9*5) + (3+4) with the
        multiplication happening during the LDF for the addition.

        >>> mul_5_9 = [LDC, [5, 9], LDF, [LD, [1, 2], LD, [1, 1], MUL, RTN], AP]
        >>> add_3_4 = [LDC, [3, 4], LDF, [LD, [1, 2], LD, [1, 1], ADD] + mul_5_9 + [ADD, RTN], AP, WRITEI, STOP]
        >>> s = SECD()
        >>> s.load_program(add_3_4, [500])
        >>> s.store_py_list(s.registers['E'], [[99, 999]]) # pretend that this is the enclosing environment

        Registers before the LDFs are executed:
        >>> s.dump_registers()
        S: address = 2 value: [500]
        E: address = 3 value: [[99, 999]]
        C: address = 5 value: 5
        D: address = 4 value: []

        >>> for _ in range(17): s.execute_opcode()
        52
        <BLANKLINE>
        MACHINE HALTED!
        <BLANKLINE>

        Note that the original registers are preserved after the calls:

        >>> s.dump_registers()
        S: address = 2 value: [500]
        E: address = 3 value: [[99, 999]]
        C: address = 77 value: 77
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == LDF

        # Make a note of the start of the original E list:
        E_head = self.registers['E']

        # The code after the LDF (the function itself):
        code = self.car(self.cdr(self.registers['C']))

        # The closure consists of code and E_head:
        new_cell_0 = self.get_new_address()
        new_cell_1 = self.get_new_address()
        new_cell_2 = self.get_new_address()
        new_cell_3 = self.get_new_address()

        # Push the closure onto the stack:
        self.set_nonterminal(new_cell_0, new_cell_1, self.registers['S'])
        self.set_nonterminal(new_cell_1, code,       new_cell_2)
        self.set_nonterminal(new_cell_2, E_head,     new_cell_3)
        self.set_nonterminal(new_cell_3, 0, 0)
        self.registers['S'] = new_cell_0

        self.registers['C'] = self.cdr(self.registers['C']) # skip LDF
        self.registers['C'] = self.cdr(self.registers['C']) # skip the code

    def opcode_AP(self):
        """
        Apply a function that has been loaded onto the stack using LDF.

        First we save a copy of certain parts of S, E, and C on
        the dump.  We then clear S, set C to the start of the code
        in the closure, and set E to the cons of the second element
        on the original S (this will be the function parameters) and
        the rest of E (which contains the environment that earlier
        code may have set up).

        For a full example and doctests, see opcode_LDF().
        """

        assert self.get_int(self.car(self.registers['C'])) == AP

        # We must save a copy of certain parts of S, E, and C on the dump
        # before running the function's code.

        # The cddr of S contains the stack after the closure and the function
        # parameters. We save this on the dump.
        if self.debug: print 'opcode_AP: saving this part of S: ', self.get_value(self.cdr(self.cdr(self.registers['S'])))
        self.push_stack('D', self.cdr(self.cdr(self.registers['S'])))

        # The environment E contains variable values specified by earlier
        # code; after the function executes we want this to be restored to its
        # original value.
        if self.debug: print 'opcode_AP: saving E: ', self.get_value(self.registers['E'])
        self.push_stack('D', self.registers['E'])

        # The cdr of C is the instruction immediately after the AP, and we
        # want to continue at that point after executing the function.
        if self.debug: print 'opcode_AP: part of C to save: ', self.get_value(self.cdr(self.registers['C']))
        self.push_stack('D', self.cdr(self.registers['C']))

        closure_code        = self.car(self.car(self.registers['S']))
        closure_environment = self.car(self.cdr(self.car(self.registers['S'])))
        second_element_of_S = self.car(self.cdr(self.registers['S']))

        if self.debug:
            print 'opcode_AP: closure_code:', self.get_value(closure_code)
            print 'opcode_AP: closure_env: ', self.get_value(closure_environment)
            print 'opcode_AP: 2nd element of S:', self.get_value(second_element_of_S)

        # clear S:
        self.registers['S'] = self.get_new_address()
        self.store_py_list(self.registers['S'], [])

        # set C to the code in the closure:
        self.registers['C'] = closure_code

        # set E to the cons of the second element in the original stack
        # and the closure_environment
        new_cell = self.get_new_address()
        self.set_nonterminal(new_cell, second_element_of_S, closure_environment)
        self.registers['E'] = new_cell

    def opcode_JOIN(self):
        """
        Return to a location specified by the top element of the
        dump. Typically used in conjunction with SEL. For a longer
        example see opcode_SEL().

        >>> s = SECD()
        >>> s.load_program([JOIN], [])
        >>> new_cell = s.get_new_address()
        >>> s.set_int(new_cell, 100)
        >>> s.push_stack('D', new_cell)
        >>> s.dump_registers()
        S: address = 2 value: []
        E: address = 3 value: []
        C: address = 5 value: 5
        D: address = 9 value: [100]

        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 2 value: []
        E: address = 3 value: []
        C: address = 100 value: 100
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == JOIN

        # Pop a value off the dump stack (a pointer):
        assert self.car(self.registers['D']) != 0
        new_C = self.get_int(self.car(self.registers['D']))
        self.registers['D'] = self.cdr(self.registers['D'])

        # Set the program counter to this new location
        self.registers['C'] = new_C


    def opcode_RTN(self):
        """
        Return after a function application initiated using AP. We
        recover the original S, E, and C registers from the dump,
        and leave the function's result on the top of S.

        >>> s = SECD()
        >>> s.load_program([LDC, [3, 4], LDF, [LD, [1, 2], LD, [1, 1], ADD, RTN], AP, WRITEI, STOP,], [500])
        >>> for _ in range(8): s.execute_opcode()
        7
        >>> s.dump_registers()
        S: address = 2 value: [500]
        E: address = 3 value: []
        C: address = 41 value: 41
        D: address = 4 value: []

        Note that if the function puts more than one item onto the
        stack S, only the top-most item is kept when the RTN is
        executed. In this example we add 3 to 4 to get 7, then push
        [9, 8, 7] onto the stack, and only the list [9, 8, 7] is
        preserved after the RTN:

        >>> s = SECD()
        >>> s.load_program([LDC, [3, 4], LDF, [LD, [1, 2], LD, [1, 1], ADD, LDC, [9, 8, 7], RTN], AP, STOP,], [500])
        >>> for _ in range(9): s.execute_opcode()
        <BLANKLINE>
        MACHINE HALTED!
        <BLANKLINE>

        >>> s.dump_registers()
        S: address = 69 value: [[9, 8, 7], 500]
        E: address = 3 value: []
        C: address = 49 value: 49
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == RTN

        # We pushed S, E, and C onto the dump, so they'll come off
        # in the reverse order:

        old_C = self.car(self.registers['D'])
        if self.debug:
            print 'opcode_RTN: old_C:', self.get_value(old_C)

        old_E = self.car(self.cdr(self.registers['D']))
        if self.debug:
            print 'opcode_RTN: cur_E:', self.get_value(self.registers['E'])
            print 'opcode_RTN: old_E:', self.get_value(old_E)

        old_S = self.car(self.cdr(self.cdr(self.registers['D'])))
        if self.debug:
            print 'opcode_RTN: old_S:', self.get_value(old_S)

        # The result of the previous AP will be on the top of the current stack,
        # so we cons this onto the front of the old stack. We take JUST ONE
        # element off the top of the stack.
        new_S = self.get_new_address()
        self.set_nonterminal(new_S, self.car(self.registers['S']), old_S)
        self.registers['S'] = new_S
        if self.debug:
            print 'opcode_RTN: S is now:', self.get_value(self.registers['S'])

        # restore E and C directly:
        self.registers['E'] = old_E
        self.registers['C'] = old_C

        if self.debug:
            print 'opcode_RTN: restored E:', self.get_value(self.registers['E'])
            print 'opcode_RTN: restored C:', self.get_value(self.registers['C'])

        # Pop the dump
        self.pop_stack('D') # C
        self.pop_stack('D') # E
        self.pop_stack('D') # S

    def opcode_SEL(self):
        """
        Boolean selection based on the element on the top of the stack
        (an integer). We follow Python's convention for truthiness, so
        zero is false and anything else is true.

        In this example with a 1 on the top of the stack, we follow
        the WRITEI path and print an integer 97, then jump to the last WRITEI:

        >>> s = SECD()
        >>> s.load_program([SEL, [WRITEI, JOIN], [WRITEC, JOIN], WRITEI], [1, 97, 1000])
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        97
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        1000

        With a 0 on the top of the stack, we follow the WRITEC path and print an
        'a', then jump to the last WRITEI:

        >>> s = SECD()
        >>> s.load_program([SEL, [WRITEI, JOIN], [WRITEC, JOIN], WRITEI], [0, 97, 1000])
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        a
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        1000
        """

        assert self.get_int(self.car(self.registers['C'])) == SEL

        value = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        # Code point after the two branches for the SEL opcode:
        after_sel_address = self.get_new_address()
        self.set_int(after_sel_address, self.cdr(self.cdr(self.cdr(self.registers['C']))))

        # Push this address onto the dump:
        self.push_stack('D', after_sel_address)

        # Follow the if or the else branch:
        if value:
            self.registers['C'] = self.car(self.cdr(self.registers['C']))
        else:
            self.registers['C'] = self.car(self.cdr(self.cdr(self.registers['C'])))

    def opcode_NULL(self):
        """
        Test if the list on the stack is empty. We do not pop the
        list off the stack and the result is pushed onto the stack.

        >>> s = SECD()
        >>> s.load_program([NULL], [[], 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [1, [], 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []


        >>> s = SECD()
        >>> s.load_program([NULL], [[1, 2, 3], 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 19 value: [0, [1, 2, 3], 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []
        """

        assert self.get_int(self.car(self.registers['C'])) == NULL

        value = self.memory[self.car(self.registers['S'])]
        assert value[0] == TAG_NONTERMINAL

        result = self.get_new_address()
        self.set_int(result, int(value[1] == 0 and value[2] == 0))
        self.push_stack('S', result)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_ZEROP(self):
        """
        Test if the number on the stack is zero. We do not pop the
        number off the stack, and the result is pushed onto the stack.

        >>> s = SECD()
        >>> s.load_program([ZEROP], [0, 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [1, 0, 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        >>> s = SECD()
        >>> s.load_program([ZEROP], [2, 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [0, 2, 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == ZEROP

        value = self.memory[self.car(self.registers['S'])]
        assert value[0] == TAG_INTEGER

        result = self.get_new_address()
        self.set_int(result, int(value[1] == 0))
        self.push_stack('S', result)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_GT0P(self):
        """
        Test if the number on the stack is greater than zero. We do
        not pop the number off the stack, and the result is pushed
        onto the stack.

        >>> s = SECD()
        >>> s.load_program([GT0P], [-5, 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [0, -5, 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        >>> s = SECD()
        >>> s.load_program([GT0P], [0, 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [0, 0, 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        >>> s = SECD()
        >>> s.load_program([GT0P], [2, 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [1, 2, 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == GT0P

        value = self.memory[self.car(self.registers['S'])]
        assert value[0] == TAG_INTEGER

        result = self.get_new_address()
        self.set_int(result, int(value[1] > 0))
        self.push_stack('S', result)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_LT0P(self):
        """
        Test if the number on the stack is less than zero. We do not
        pop the number off the stack, and the result is pushed onto
        the stack.

        >>> s = SECD()
        >>> s.load_program([LT0P], [-3, 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [1, -3, 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        >>> s = SECD()
        >>> s.load_program([LT0P], [2, 999])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 13 value: [0, 2, 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == LT0P

        value = self.memory[self.car(self.registers['S'])]
        assert value[0] == TAG_INTEGER

        result = self.get_new_address()
        self.set_int(result, int(value[1] < 0))
        self.push_stack('S', result)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_WRITEI(self):
        """
        Write an integer to the console. Takes its argument from the stack.

        >>> s = SECD()
        >>> s.load_program([WRITEI], [1234])
        >>> s.execute_opcode()
        1234
        """

        value = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        self.output_stream.write(str(value) + '\n')

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_WRITEC(self):
        """
        Write a character to the console. Takes its argument (an integer)
        from the stack and prints chr() of the value.

        >>> s = SECD()
        >>> s.load_program([WRITEC], [97])
        >>> s.execute_opcode()
        a
        """

        value = self.get_int(self.car(self.registers['S']))
        self.pop_stack('S')

        self.output_stream.write(chr(value) + '\n')

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_READI(self):
        """
        Read an integer from the console.

        This doctest relies on stdin being '42'. Note the trailing
        whitespace after the '?' as well (it is part of the prompt).

        >>> s = SECD()
        >>> s.load_program([READI, WRITEI], [97])
        >>> s.execute_opcode()
        ? 
        >>> s.execute_opcode()
        42
        """

        i = int(raw_input('? '))

        new_cell = self.get_new_address()
        self.set_int(new_cell, i)
        self.push_stack('S', new_cell)

        self.registers['C'] = self.cdr(self.registers['C'])


    def opcode_STOP(self):
        """
        Half the machine. Any future call to execute_opcode() results
        in an error.
        """

        self.running = False

        print
        print 'MACHINE HALTED!'
        print

    def opcode_CAR(self):
        """
        Take the car of the list on the stack.

        >>> s = SECD()
        >>> s.load_program([CAR], [[1, 2, 3]])
        >>> s.dump_registers()
        S: address = 2 value: [[1, 2, 3]]
        E: address = 3 value: []
        C: address = 5 value: 5
        D: address = 4 value: []

        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 16 value: [1]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        >>> s = SECD()
        >>> s.load_program([CDR, CAR], [[1, 2, 3]])
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 18 value: [2]
        E: address = 3 value: []
        C: address = 9 value: 9
        D: address = 4 value: []

        >>> s = SECD()
        >>> s.load_program([CDR, CDR, CAR], [[1, 2, 3]])
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 20 value: [3]
        E: address = 3 value: []
        C: address = 11 value: 11
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == CAR

        car_value = self.car(self.car(self.registers['S']))
        self.pop_stack('S')
        self.push_stack('S', car_value)

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_CDR(self):
        """
        Take the cdr of the list on the stack.

        >>> s = SECD()
        >>> s.load_program([CDR, CDR, CDR], [[1, 2, 3]])
        >>> s.dump_registers()
        S: address = 2 value: [[1, 2, 3]]
        E: address = 3 value: []
        C: address = 5 value: 5
        D: address = 4 value: []

        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 2 value: [[2, 3]]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 2 value: [[3]]
        E: address = 3 value: []
        C: address = 9 value: 9
        D: address = 4 value: []

        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 2 value: [[]]
        E: address = 3 value: []
        C: address = 11 value: 11
        D: address = 4 value: []
        """

        assert self.get_int(self.car(self.registers['C'])) == CDR

        head_address = self.car(self.registers['S'])

        self.set_nonterminal(head_address, self.car(self.cdr(head_address)),
                                           self.cdr(self.cdr(head_address)))

        assert self.get_int(self.car(self.registers['C'])) == CDR

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_CONS(self):
        """
        Cons of the first element of the stack with the list in the
        second element.

        >>> s = SECD()
        >>> s.load_program([NIL, LDC, 3, CONS, LDC, 2, CONS, LDC, 1, CONS,], [999])
        >>> s.dump_registers()
        S: address = 2 value: [999]
        E: address = 3 value: []
        C: address = 5 value: 5
        D: address = 4 value: []

        # Push nil onto the stack:
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 29 value: [[], 999]
        E: address = 3 value: []
        C: address = 7 value: 7
        D: address = 4 value: []

        # Push 3 onto the stack:
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 30 value: [3, [], 999]
        E: address = 3 value: []
        C: address = 11 value: 11
        D: address = 4 value: []

        # Cons the 3:
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 29 value: [[3], 999]
        E: address = 3 value: []
        C: address = 13 value: 13
        D: address = 4 value: []

        # Push the 2 onto the stack:
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 32 value: [2, [3], 999]
        E: address = 3 value: []
        C: address = 17 value: 17
        D: address = 4 value: []

        # Cons the 2:
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 29 value: [[2, 3], 999]
        E: address = 3 value: []
        C: address = 19 value: 19
        D: address = 4 value: []

        Another example:

        >>> s = SECD()
        >>> s.load_program([NIL, LDC, [1, 2, 3, 4], CONS, LDC, 9, CONS], [999])
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 31 value: [[9, [1, 2, 3, 4]], 999]
        E: address = 3 value: []
        C: address = 27 value: 27
        D: address = 4 value: []

        """
        assert self.get_int(self.car(self.registers['C'])) == CONS

        cell0 = self.registers['S']
        cell1 = self.car(cell0)
        cell2 = self.cdr(cell0)
        cell3 = self.car(cell2)
        cell4 = self.cdr(cell2)

        cellx = self.get_new_address()

        self.set_nonterminal(cell2, cellx, cell4)
        self.set_nonterminal(cellx, cell1, cell3)
        self.registers['S'] = cell2

        self.registers['C'] = self.cdr(self.registers['C'])

    def locate(self, ij, vlist):
        """
        Find the j-th element of the i-th sublist of vlist. Typically
        ij will be a parameter to a function and vlist will be the
        environment register E, containing a list of sublists.

        K1991 p. 149. There is a typo in the first line: replace
        each occurence of 'x' with 'ij'.

        ij    = dotted pair, e.g. 1.3 = [1, 3]
        vlist = memory location of environment list

        >>> s = SECD()
        >>> vlist = s.get_new_address()
        >>> s.store_py_list(vlist, [[8,], [4, [2, 2]], [1, 2, 3],])

        for (i, j) in [(3, 3)]: # [(1, 1), (2, 1), (2, 2), (3, 1), (3, 2), (3, 3),]:

        >>> ij = s.get_new_address()
        >>> s.store_py_list(ij, [1, 1])
        >>> s.get_value(s.locate(ij, vlist))
        8

        >>> ij = s.get_new_address()
        >>> s.store_py_list(ij, [2, 1])
        >>> s.get_value(s.locate(ij, vlist))
        4

        >>> ij = s.get_new_address()
        >>> s.store_py_list(ij, [2, 2])
        >>> s.get_value(s.locate(ij, vlist))
        [2, 2]

        >>> ij = s.get_new_address()
        >>> s.store_py_list(ij, [3, 1])
        >>> s.get_value(s.locate(ij, vlist))
        1

        >>> ij = s.get_new_address()
        >>> s.store_py_list(ij, [3, 2])
        >>> s.get_value(s.locate(ij, vlist))
        2

        >>> ij = s.get_new_address()
        >>> s.store_py_list(ij, [3, 3])
        >>> s.get_value(s.locate(ij, vlist))
        3

        """

        def loc(s, y, z):
            assert type(y) == int
            assert y >= 1

            if y == 1:
                return s.car(z)
            else:
                return loc(s, y - 1, s.cdr(z))

        return loc(self, self.get_int(self.car(self.cdr(ij))), loc(self, self.get_int(self.car(ij)), vlist))

    def opcode_LD(self):
        """
        Load the value of a variable onto the stack. The cdr of C is a
        pair [i, j] which specifies that we want the j-th element of
        the i-th sublist of the environment E. For further examples
        see opcode_LDF().

        >>> s = SECD()
        >>> s.store_py_list(s.registers['E'], [[8,], [4, [2, 2]], [1, 2, 3],])
        >>> s.load_program([LD, [1, 1], LD, [2, 1], LD, [2, 2], LD, [3, 1], LD, [3, 2], LD, [3, 3],], [])
        >>> s.dump_registers()
        S: address = 2 value: []
        E: address = 3 value: [[8], [4, [2, 2]], [1, 2, 3]]
        C: address = 27 value: 27
        D: address = 4 value: []

        >>> s.execute_opcode()
        >>> s.get_value(s.registers['S'])
        [8]

        >>> s.execute_opcode()
        >>> s.get_value(s.registers['S'])
        [4, 8]

        >>> s.execute_opcode()
        >>> s.get_value(s.registers['S'])
        [[2, 2], 4, 8]

        >>> s.execute_opcode()
        >>> s.get_value(s.registers['S'])
        [1, [2, 2], 4, 8]

        >>> s.execute_opcode()
        >>> s.get_value(s.registers['S'])
        [2, 1, [2, 2], 4, 8]

        >>> s.execute_opcode()
        >>> s.get_value(s.registers['S'])
        [3, 2, 1, [2, 2], 4, 8]

        """

        assert self.get_int(self.car(self.registers['C'])) == LD

        ij = self.car(self.cdr(self.registers['C']))

        self.push_stack('S', self.locate(ij, self.registers['E']))

        self.registers['C'] = self.cdr(self.registers['C']) # LD
        self.registers['C'] = self.cdr(self.registers['C']) # ij

    def opcode_DUM(self):
        """
        Refer to K1991 p. 160.

        Cons onto the front of the environment register a cell
        with car = nil. Later the car of the new cell will be
        reset by RAP to point to the list of closures.

        >>> s = SECD()
        >>> s.load_program([DUM], [])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 2 value: []
        E: address = 8 value: ['NIL_PTR0']
        C: address = 7 value: 7
        D: address = 4 value: []

        >>> s = SECD()
        >>> s.load_program([DUM], [])
        >>> s.store_py_list(s.registers['E'], [[99, 999]])
        >>> s.execute_opcode()
        >>> s.dump_registers()
        S: address = 2 value: []
        E: address = 14 value: ['NIL_PTR0', [99, 999]]
        C: address = 7 value: 7
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == DUM

        new_cell = self.get_new_address()
        self.set_nonterminal(new_cell, 0, self.registers['E'])
        self.registers['E'] = new_cell

        self.registers['C'] = self.cdr(self.registers['C'])

    def opcode_RAP(self):
        """
        Apply a function that was set up in conjunction with DUM
        and LDF.

        The example below is taken from K1991 p. 164 and corresponds
        to the code:

            (LETREC (f) ((LAMBDA (x m) (IF (NULL x) m
                                           (f (CDR x) (+ m 1)))))
                (f (1 2 3) 0))

        which computes the length of the list x using the supplied
        accumulator m.

        There appear to be two typos on p. 164:

        1. Replace "LDL 0" with "LDC 0"  (there is no LDL instruction).

        2. Replace "CONS (1.1) AP RTN" with "CONS LD (1.1) AP RTN", otherwise the
           following AP will not load the first recursively defined
           function. See also p. 161:

                Within the code called by the RAP, any required
                calls to the i-th recursively defined function fi
                are initiated by a LD(1,i) followed by an AP. The
                LD fetches the closure for the function from the
                environment, and AP unpacks it as before.

        >>> s = SECD()
        >>> len_program = [DUM,
        ...                NIL,
        ...                LDF, [LD, [1, 1], NULL, SEL,
        ...                                              [LD, [1, 2], JOIN,],
        ...                                              [NIL, LDC, 1, LD, [1, 2], ADD, CONS, LD, [1, 1], CDR, CONS, LD, [2, 1], AP, JOIN,],
        ...                                              RTN,],
        ...                CONS,
        ...                LDF, [NIL, LDC, 0, CONS, LDC, [1, 2, 3], CONS, LD, [1, 1], AP, RTN,], # missing LD before [1, 1] in text
        ...                RAP,
        ...                STOP,]
        >>> s.load_program(len_program, [500])
        >>> s.store_py_list(s.registers['E'], [[99, 999]]) # pretend that this is the enclosing environment
        >>> while s.running: s.execute_opcode()
        <BLANKLINE>
        MACHINE HALTED!
        <BLANKLINE>

        The answer is 3, as left on the top of the stack:

        >>> s.dump_registers()
        S: address = 232 value: [3, 500]
        E: address = 3 value: [[99, 999]]
        C: address = 123 value: 123
        D: address = 4 value: []

        The same example as before, but with the accumulator set to
        100 so the final answer is 103:

        >>> s = SECD()
        >>> len_program = [DUM,
        ...                NIL,
        ...                LDF, [LD, [1, 1], NULL, SEL,
        ...                                              [LD, [1, 2], JOIN,],
        ...                                              [NIL, LDC, 1, LD, [1, 2], ADD, CONS, LD, [1, 1], CDR, CONS, LD, [2, 1], AP, JOIN,],
        ...                                              RTN,],
        ...                CONS,
        ...                LDF, [NIL, LDC, 100, CONS, LDC, [1, 2, 3], CONS, LD, [1, 1], AP, RTN,],
        ...                RAP,
        ...                STOP,]
        >>> s.load_program(len_program, [500])
        >>> s.store_py_list(s.registers['E'], [[99, 999]]) # pretend that this is the enclosing environment
        >>> while s.running: s.execute_opcode()
        <BLANKLINE>
        MACHINE HALTED!
        <BLANKLINE>

        The answer is 103, as left on the top of the stack:

        >>> s.dump_registers()
        S: address = 232 value: [103, 500]
        E: address = 3 value: [[99, 999]]
        C: address = 123 value: 123
        D: address = 4 value: []

        Here is a longer example where we define f1 and f2, each of which
        call themselves.

        Call f2 and ignore f1:

        >>> s = SECD()
        >>> len_program = [DUM,
        ...               NIL,
        ...
        ...               # f2: length of list
        ...               LDF, [LD, [1, 1], NULL, SEL,
        ...                                             [LD, [1, 2], JOIN,],
        ...                                             [NIL, LDC, 1, LD, [1, 2], ADD, CONS, LD, [1, 1], CDR, CONS, LD, [2, 2], AP, JOIN,],
        ...                                             RTN,],
        ...               CONS,
        ...
        ...               #f1: length of list * 11
        ...               LDF, [LD, [1, 1], NULL, SEL,
        ...                                             [LD, [1, 2], JOIN,],
        ...                                             [NIL, LDC, 11, LD, [1, 2], ADD, CONS, LD, [1, 1], CDR, CONS, LD, [2, 1], AP, JOIN,],
        ...                                             RTN,],
        ...               CONS,
        ...               LDF, [NIL, LDC, 0, CONS, LDC, [1, 2, 3], CONS, LD, [1, 2], AP, RTN,], # LD [1, 2] refers to f2
        ...               RAP,
        ...               STOP,]
        >>> s.load_program(len_program, [500])
        >>> s.store_py_list(s.registers['E'], [[99, 999]]) # pretend that this is the enclosing environment
        >>> while s.running: s.execute_opcode()
        <BLANKLINE>
        MACHINE HALTED!
        <BLANKLINE>

        The answer is 33, as left on the top of the stack:

        >>> s.dump_registers()
        S: address = 313 value: [3, 500]
        E: address = 3 value: [[99, 999]]
        C: address = 199 value: 199
        D: address = 4 value: []

        Call f1 and ignore f2:

        >>> s = SECD()
        >>> len_program = [DUM,
        ...               NIL,
        ...
        ...               # f2: length of list
        ...               LDF, [LD, [1, 1], NULL, SEL,
        ...                                             [LD, [1, 2], JOIN,],
        ...                                             [NIL, LDC, 1, LD, [1, 2], ADD, CONS, LD, [1, 1], CDR, CONS, LD, [2, 2], AP, JOIN,],
        ...                                             RTN,],
        ...               CONS,
        ...
        ...               #f1: length of list * 11
        ...               LDF, [LD, [1, 1], NULL, SEL,
        ...                                             [LD, [1, 2], JOIN,],
        ...                                             [NIL, LDC, 11, LD, [1, 2], ADD, CONS, LD, [1, 1], CDR, CONS, LD, [2, 1], AP, JOIN,],
        ...                                             RTN,],
        ...               CONS,
        ...               LDF, [NIL, LDC, 0, CONS, LDC, [1, 2, 3], CONS, LD, [1, 1], AP, RTN,], # call f1
        ...               RAP,
        ...               STOP,]
        >>> s.load_program(len_program, [500])
        >>> s.store_py_list(s.registers['E'], [[99, 999]]) # pretend that this is the enclosing environment
        >>> while s.running: s.execute_opcode()
        <BLANKLINE>
        MACHINE HALTED!
        <BLANKLINE>

        The answer is 33, as left on the top of the stack:

        >>> s.dump_registers()
        S: address = 313 value: [33, 500]
        E: address = 3 value: [[99, 999]]
        C: address = 199 value: 199
        D: address = 4 value: []

        Finally, here we intertwine f1 and f2, to check that the
        recursively defined functions can call each other.

        >>> s = SECD()
        >>> len_program = [DUM,
        ...               NIL,
        ...
        ...               # f2: length of list
        ...               LDF, [LD, [1, 1], NULL, SEL,
        ...                                             [LD, [1, 2], JOIN,],
        ...                                             [NIL, LDC, 1, LD, [1, 2], ADD, CONS, LD, [1, 1], CDR, CONS, LD, [2, 1], AP, JOIN,], # LD [2, 1] calls f1
        ...                                             RTN,],
        ...               CONS,
        ...
        ...               #f1: length of list * 11
        ...               LDF, [LD, [1, 1], NULL, SEL,
        ...                                             [LD, [1, 2], JOIN,],
        ...                                             [NIL, LDC, 11, LD, [1, 2], ADD, CONS, LD, [1, 1], CDR, CONS, LD, [2, 2], AP, JOIN,], # LD [2, 2] calls f2
        ...                                             RTN,],
        ...               CONS,
        ...               LDF, [NIL, LDC, 0, CONS, LDC, [1, 2, 3], CONS, LD, [1, 1], AP, RTN,], # LD [1, 1] refers to f1
        ...               RAP,
        ...               STOP,]
        >>> s.load_program(len_program, [500])
        >>> s.store_py_list(s.registers['E'], [[99, 999]]) # pretend that this is the enclosing environment
        >>> while s.running: s.execute_opcode()
        <BLANKLINE>
        MACHINE HALTED!
        <BLANKLINE>

        So we first enter f1, adding 11, then go into f2, adding 1,
        and finally enter f1 again, adding 11, which totals 23,
        as left on the top of the stack:

        >>> s.dump_registers()
        S: address = 313 value: [23, 500]
        E: address = 3 value: [[99, 999]]
        C: address = 199 value: 199
        D: address = 4 value: []

        """

        assert self.get_int(self.car(self.registers['C'])) == RAP

        if self.debug:
            # The stack should be in a similar state as when an AP is used.

            # The first element on the stack should be the closure for E; in
            # our example this will be roughly (f (1 2 3) 0):
            print 'closure for expression E:', self.get_value(self.registers['S'])[0]

            # The second element is the list of closures for f1..fn:
            print 'list of closures for f1..fn:', self.get_value(self.registers['S'])[1]
            py_list_of_closures = self.get_value(self.registers['S'])[1]
            for i in range(len(py_list_of_closures)):
                print 'closure for f%d:' % (i + 1,)
                print '      code:', py_list_of_closures[i][0]
                print '      env: ', py_list_of_closures[i][1]

        # We must save a copy of certain parts of S, E, and C on the dump
        # before running the function's code.

        # The cddr of S contains the stack after the closure and the function
        # parameters. We save this on the dump.
        if self.debug: print 'opcode_RAP: saving this part of S: ', self.get_value(self.cdr(self.cdr(self.registers['S'])))
        self.push_stack('D', self.cdr(self.cdr(self.registers['S'])))

        # The environment E contains variable values specified by earlier
        # code; after the function executes we want this to be restored to its
        # original value. Unlike the case for AP, the first cell of E will currently
        # contain a nil pointer (created by DUM), so the stuff that we actually want
        # to save is in the cdr of E.
        if self.debug: print 'opcode_RAP: saving cdr of E: ', self.get_value(self.cdr(self.registers['E']))
        assert self.memory[self.registers['E']][0] == TAG_NONTERMINAL
        assert self.memory[self.registers['E']][1] == 0 # this is the nil ptr
        self.push_stack('D', self.cdr(self.registers['E']))

        # The cdr of C is the instruction immediately after the AP, and we
        # want to continue at that point after executing the function.
        if self.debug: print 'opcode_RAP: part of C to save: ', self.get_value(self.cdr(self.registers['C']))
        self.push_stack('D', self.cdr(self.registers['C']))

        closure_code        = self.car(self.car(self.registers['S']))
        closure_environment = self.car(self.cdr(self.car(self.registers['S'])))
        second_element_of_S = self.car(self.cdr(self.registers['S']))

        if self.debug:
            print 'opcode_RAP: closure_code:', self.get_value(closure_code)
            print 'opcode_RAP: closure_env: ', self.get_value(closure_environment)
            print 'opcode_RAP: 2nd element of S:', self.get_value(second_element_of_S)

        # To create the circular list, we set the nil pointer of E to the second
        # element of S:
        assert self.memory[self.registers['E']][0] == TAG_NONTERMINAL
        assert self.memory[self.registers['E']][1] == 0
        self.set_nonterminal(self.registers['E'], second_element_of_S, self.cdr(self.registers['E']))

        # clear S:
        self.registers['S'] = self.get_new_address()
        self.store_py_list(self.registers['S'], [])

        # set C to the code in the closure:
        self.registers['C'] = closure_code

    def execute_opcode(self):
        """
        Execute a single opcode by calling the appropriate
        self.opcode_XXX() method.
        """

        assert self.running

        op_code = self.get_int(self.car(self.registers['C']))
        assert op_code in OP_CODES

        if self.debug:
            print 'execute_opcode:', op_code

        op = {ADD:    self.opcode_ADD,
              MUL:    self.opcode_MUL,
              SUB:    self.opcode_SUB,
              DIV:    self.opcode_DIV,

              CAR:    self.opcode_CAR,
              CDR:    self.opcode_CDR,
              NIL:    self.opcode_NIL,
              NULL:   self.opcode_NULL,
              CONS:   self.opcode_CONS,
              LDC:    self.opcode_LDC,
              LDF:    self.opcode_LDF,
              AP:     self.opcode_AP,
              LD:     self.opcode_LD,

              DUM:    self.opcode_DUM,
              RAP:    self.opcode_RAP,

              JOIN:   self.opcode_JOIN,
              RTN:    self.opcode_RTN,
              SEL:    self.opcode_SEL,

              WRITEI: self.opcode_WRITEI,
              WRITEC: self.opcode_WRITEC,

              READC:  None, # not implemented
              READI:  self.opcode_READI,

              STOP:   self.opcode_STOP,

              ZEROP:  self.opcode_ZEROP,
              GT0P:   self.opcode_GT0P,
              LT0P:   self.opcode_LT0P,

             }[op_code]

        op()

def draw_sample_graphs():
    """
    Draw some sample graphs of the memory structure corresponding to
    various lists.
    """

    m = SECD()
    new_cell = m.get_new_address()

    m.store_py_list(new_cell, [])
    m.graph_at_address(new_cell).write_png('empty_list.png')

    m.store_py_list(new_cell, [1])
    m.graph_at_address(new_cell).write_png('list_len_1.png')

    m.store_py_list(new_cell, [1, 2, 3])
    m.graph_at_address(new_cell).write_png('list_len_3.png')

    m.store_py_list(new_cell, [1, 2, []])
    m.graph_at_address(new_cell).write_png('list_len_3_with_empty.png')

    m.store_py_list(new_cell, [[1, 2], [3], [[[4]]], 5])
    m.graph_at_address(new_cell).write_png('list_len_4_with_nested.png')

    m.store_py_list(new_cell, [[], [[], []], [[[[ [], [], [[]] ]]]]])
    m.graph_at_address(new_cell).write_png('list_len_3_deeply_nested_empty_lists.png')

    s = SECD()
    s.load_program([LDC, [3, 4], LDF, [LD, [1, 2], LD, [1, 1], ADD, RTN], AP, WRITEI, STOP,], [500])
    s.graph_at_address(new_cell).write_png('program_in_memory.png')

