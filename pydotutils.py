def pydot_record_string(x):
    """
    FIXME Surely pydot has a function to do this? Why can't I pass
    a list to a Node to make a record?

    >>> _pydot_record_string(['a', 'b', 'lol'])
    '<f0> a|<f1> b|<f2> lol'
    """

    return ''.join(['<f%d> %s|' % (i, s) for (i, s) in enumerate(x)])[:-1]
