pysecd
======

Python interpreter for the SECD abstract machine defined by Peter Landin.

I followed the presentation of the SECD machine given by Peter M. Kogge in his book *The Architecture of Symbolic Computers* (1991, McGraw Hill). I wrote this interpreter as a learning exercise, so the code should not be taken as a definitive statement on how the SECD machine operates. The trickiest opcodes to implement were DUM and RAP, for defining recursive closures.

To aid debugging I wrote a small wrapper for pydot, so that the memory structures can be visualised. For example the list [1, 2, 3] is stored as:

![small list](https://github.com/carlohamalainen/pysecd/raw/master/list_1_2_3.png)

A nonterminal cell has three parts: its address, the car value, and the cdr value. Nonterminal cells have two parts: the address and the integer value. For convenience opcodes (ADD, LD, LDF, etc) are stored as strings so that when we draw the graph we can see opcodes instead of integers. For examle the program

    [LDC, [3, 4], LDF, [LD, [1, 2], LD, [1, 1], ADD, RTN], AP, WRITEI, STOP,]

corresponds to the following graph in memory:

![sample program](https://github.com/carlohamalainen/pysecd/raw/master/program_in_memory.png)

On Debian-like systems, install pydot with this command:

    sudo apt-get install python-pydot

Further reading
======

I only read Kogge's presentation of the SECD machine, so I really ought to invest some time in getting through these:

* The original 1964 paper by Peter Landin: http://comjnl.oxfordjournals.org/content/6/4/308.full.pdf+html
* Notes on the RAP instruction: http://lambda-the-ultimate.org/node/4368
* Implementing an SECD machine in Common Lisp: http://netzhansa.blogspot.com/2008/09/revisiting-secd-and-power-of-lisp-while.html
* Lecture notes on the SECD machine: http://webdocs.cs.ualberta.ca/~you/courses/325/Mynotes/Fun/SECD-slides.html
* An SECD implementation (in what I assume is Common Lisp?): http://ugweb.cs.ualberta.ca/~c325/secd.lsp
* An SECD implementation in C (part of LispKit): http://vaxbusters.org/lispkit/LKIT-2/lispkit-debug.c
* SECD Mania: http://skelet.ludost.net/sec/

TODO
======

* Test pysecd against one of the other implementations listed above.
* Complete the Lisp to SECD compiler (Chapter 7 of Kogge's book); use the compiler to further test the SECD interpreter.
* Implement garbage collection (Chapter 8 of Kogge's book).

