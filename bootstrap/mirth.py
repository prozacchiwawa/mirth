#!/usr/bin/env python3

############################### LICENSE ###############################
# This Source Code Form is subject to the terms of the Mozilla Public #
# License, v. 2.0. If a copy of the MPL was not distributed with this #
# file, You can obtain one at http://mozilla.org/MPL/2.0/.            #
#######################################################################

import re

def exception(fn):
    r"""Get thrown exception from function and return it.
    Returns None if there is no exception.

    >>> exception(lambda: 0)
    >>> exception(lambda: 10 / 0)
    ZeroDivisionError('division by zero',)
    """
    try:
        fn()
    except Exception as e:
        return e

def assert_type(val, ty, name=None):
    '''Assert value has given type before returning value.

    >>> assert_type(1, int)
    1
    >>> assert_type('foo', str)
    'foo'
    >>> exception(lambda: assert_type([], bool))
    TypeError('expected bool got []',)
    >>> exception(lambda: assert_type(1, str, "filename"))
    TypeError('expected str got 1 for filename',)
    '''
    if not isinstance(val, ty):
        msg = 'expected %s got %r' % (ty.__name__, val)
        if name:
            raise TypeError('%s for %s' % (msg, name))
        else:
            raise TypeError(msg)
    return val

def assert_type_or_none(val, ty, name=None):
    if val is None:
        return None
    else:
        return assert_type(val, ty, name)

def unescape_str (s):
    r"""Remove escape from captured string.

    >>> unescape_str('"foo"')
    'foo'
    >>> unescape_str("'bar'")
    'bar'
    >>> exception(lambda: unescape_str("foo"))
    ValueError('Unknown string delimiter: f',)
    >>> exception(lambda: unescape_str("'foo"))
    ValueError('Unknown string delimiter: o',)
    >>> exception(lambda: unescape_str("'foo\""))
    ValueError('Mismatched string delimiters: \' and "',)
    >>> unescape_str(r'"helwo\\lorld"')
    'helwo\\lorld'
    >>> unescape_str(r'"\n\t\r\'\""')
    '\n\t\r\'"'
    >>> exception(lambda: unescape_str(r'"\l"'))
    SyntaxError('Unknown escape sequence: \\l',)
    >>> exception(lambda: unescape_str(r'"\"'))
    ValueError('Unexpected escape at end of string.',)
    """
    if s[0] not in ['"', "'"]:
        raise ValueError("Unknown string delimiter: %c" % s[0])
    if s[-1] not in ['"', "'"]:
        raise ValueError("Unknown string delimiter: %c" % s[-1])
    if s[0] != s[-1]:
        raise ValueError("Mismatched string delimiters: %c and %c"
                        % (s[0], s[-1]))

    s = s[1:-1]
    r = []
    escaped = False
    for c in s:
        if escaped:
            escaped = False
            if c in {'\\', '"', "'"}:
                r.append(c)
            elif c == 'n':
                r.append('\n')
            elif c == 't':
                r.append('\t')
            elif c == 'r':
                r.append('\r')
            else:
                raise SyntaxError("Unknown escape sequence: \\%c" % c)
        elif c == '\\':
            escaped = True
        else:
            r.append(c)
    if escaped:
        raise ValueError("Unexpected escape at end of string.")

    return ''.join(r)


# rule types
OPEN   = 'OPEN'
CLOSE  = 'CLOSE'
ATOMIC = 'ATOMIC'
IGNORE = 'IGNORE'

class Rule:
    KINDS = {OPEN, CLOSE, ATOMIC, IGNORE}

    def __init__(self, kind, name, regex, to_value=None):
        if kind not in Rule.KINDS:
            raise ValueError("%s nat a valid rule kind" % kind)
        self.kind = assert_type(kind, str, 'kind')
        self.name = assert_type(name, str, 'name')
        self.regex = re.compile(assert_type(regex, str, 'regex'))
        self.to_value = to_value if to_value else lambda x: x

base_rules = [
    Rule(OPEN, 'LPAREN', r'\('),
    Rule(CLOSE,'RPAREN', r'\)'),
    Rule(OPEN, 'LSQUARE', r'\['),
    Rule(CLOSE,'RSQUARE', r'\]'),
    Rule(OPEN, 'LCURLY', r'\{'),
    Rule(CLOSE,'RCURLY', r'\}'),
    Rule(ATOMIC, 'LINE', r'\n'),
    Rule(ATOMIC, 'PRAGMA', r'#\[[^\n\[\]]*\]()\n'),
    Rule(ATOMIC, 'COMMENT', r'#([\r\n]+|[ \t\n])'),
    Rule(ATOMIC, 'COMMA', r','),
    Rule(ATOMIC, 'STR', r'"([^\\"]|\\.)*"', to_value=unescape_str),
    Rule(ATOMIC, 'STR', r"'([^\\']|\\.)*'", to_value=unescape_str),
    Rule(ATOMIC, 'INT', r'[\+\-]?\d+', to_value=int),
    Rule(ATOMIC, 'INT', r'0[xX][0-9a-zA-Z]+', to_value=lambda x: int(x,16)),
    Rule(ATOMIC, 'WORD', r'[^\s\(\)\[\]\{\},]+'),
    Rule(IGNORE, 'SPACE', r'[ \t\r\f\v]+'),
]

class Loc:
    def __init__ (self, path=None, row=1, col=1):
        self.path = assert_type_or_none(path, str, 'path')
        self.row = assert_type(row, int, 'row')
        self.col = assert_type(col, int, 'col')

    def __str__ (self):
        if self.path:
            return '%s:%d:%d' % (self.path, self.row, self.col)
        else:
            return '%d:%d' % (self.row, self.col)

    def __repr__ (self):
        return 'Loc(%r, %r, %r)' % (self.path, self.row, self.col)

    def next(self, text, **etc):
        TABSTOP = etc.get('TABSTOP', 8)
        row, col = self.row, self.col
        for c in text:
            if   c == '\n': row += 1 ; col = 1
            elif c == '\t': col += TABSTOP - col % TABSTOP
            else: col += 1
        return Loc(self.path, row, col)

    def can_dup (self):
        return True

    def can_drop (self):
        return True


class Token:
    def __init__ (self, kind, name, text, value, loc):
        self.kind = assert_type(kind, str, 'kind')
        if kind not in Rule.KINDS:
            raise ValueError("%s nat a valid rule kind" % kind)
        self.name = assert_type(name, str, 'name')
        self.text = assert_type(text, str, 'text')
        self.value = value
        self.loc = assert_type(loc, Loc, 'text')

    def __repr__ (self):
        return 'Token(%r, %r, %r, %r, %r)' % (
            self.kind, self.name, self.text, self.value, self.loc
        )


    def __len__ (self):
        return len(self.text)

    def next_loc(self, **etc):
        return self.loc.next(self.text, **etc)

    def can_dup (self):
        return can_dup(self.value)

    def can_drop (self):
        return can_drop(self.value)

# rewriting this in OO style was a mistake ...
class Lexer:
    def __init__(self, source, loc=Loc(), rules=base_rules):
        self.source = assert_type(source, str, 'source')
        self.loc    = assert_type(loc, Loc, 'loc')
        self.rules  = rules

    def can_dup(self):
        return False # contains variables, so can't duplicate

    def can_drop(self):
        return True

    def __iter__(self):
        return self

    def __next__(self):
        r'''Get the next token based on rules.
        If no rule matches / end of file, returns None.
        If multiple rules match, returns the longest match.
        If multiple rules match with the same length, returns the first such match
        (the rules are ordered).

        >>> l = Lexer(''); exception(lambda: l.__next__())
        StopIteration()
        >>> l = Lexer('123'); l.__next__()
        Token('ATOMIC', 'INT', '123', 123, Loc(None, 1, 1))
        >>> l = Lexer('0xdeadbeef', Loc(None,100)); l.__next__()
        Token('ATOMIC', 'INT', '0xdeadbeef', 3735928559, Loc(None, 100, 1))
        >>> l = Lexer('1st', Loc(None,10,20)); l.__next__()
        Token('ATOMIC', 'WORD', '1st', '1st', Loc(None, 10, 20))
        >>> l = Lexer('"\l"', Loc('jeff.txt',2,3)); exception(lambda: l.__next__())
        SyntaxError('jeff.txt:2:3: Unknown escape sequence: \\l',)
        >>> l = Lexer('foo(bar baz)'); l.__next__()
        Token('ATOMIC', 'WORD', 'foo', 'foo', Loc(None, 1, 1))
        '''
        result = None
        best_len = 0
        for rule in self.rules:
            match = rule.regex.match(self.source)
            if match:
                text = match.group()
                if len(text) > best_len:
                    best_len = len(text)
                    try:
                        value = rule.to_value(text)
                    except SyntaxError as e:
                        raise SyntaxError("%s: %s" % (self.loc, e.msg))
                    result = Token(rule.kind, rule.name, text, value, self.loc)

        if result:
            self.source = self.source[best_len:]
            self.loc = result.next_loc()
            return result
        elif len(self.source) > 0:
            short_source = (self.source if len(self.source) < 8
                                      else self.source[:5] + '...')
            raise SyntaxError("%s: expected token, got %r"
                            % (show_loc(loc), short_source))
        else:
            raise StopIteration


def tokenize(source, loc=Loc(), rules=base_rules):
    r'''Tokenize source all at once according to rules. This ignores
    lexer macros. As such, it is not suitable for modules that
    introduce or import lexer macros (if such a thing is to exist).

    >>> tokenize('')
    []
    >>> tokenize('foo')
    [Token('ATOMIC', 'WORD', 'foo', 'foo', Loc(None, 1, 1))]
    >>> tokenize('foo bar')
    [Token('ATOMIC', 'WORD', 'foo', 'foo', Loc(None, 1, 1)), Token('ATOMIC', 'WORD', 'bar', 'bar', Loc(None, 1, 5))]
    >>> tokenize('foo(1 2 \n +)')
    [Token('ATOMIC', 'WORD', 'foo', 'foo', Loc(None, 1, 1)), Token('OPEN', 'LPAREN', '(', '(', Loc(None, 1, 4)), Token('ATOMIC', 'INT', '1', 1, Loc(None, 1, 5)), Token('ATOMIC', 'INT', '2', 2, Loc(None, 1, 7)), Token('ATOMIC', 'LINE', '\n', '\n', Loc(None, 1, 9)), Token('ATOMIC', 'WORD', '+', '+', Loc(None, 2, 2)), Token('CLOSE', 'RPAREN', ')', ')', Loc(None, 2, 3))]
    '''
    return [t for t in Lexer(source, loc, rules) if t.kind != IGNORE]

def can_drop(x):
    '''Is x safely droppable, i.e. can x be dropped without dropping
    some connection to the world, such as a file handle.

    >>> can_drop(1)
    True
    >>> can_drop([''])
    True
    >>> can_drop({'zero': 1})
    True
    >>> import sys
    >>> can_drop(sys.stdin)
    False
    >>> can_drop([sys.stdin])
    False
    '''

    if hasattr(x, 'can_drop'):
        return x.can_drop()
    if any(isinstance(x,t) for t in (list, tuple, set)):
        return all(can_drop(y) for y in x)
    if isinstance(x,dict):
        return (all(can_drop(y) for y in x.values())
            and all(can_drop(y) for y in x))
    return any(isinstance(x,ty) for ty in (int, bool, str, type(None)))

def can_dup(x):
    '''Is x safely duplicable, i.e. can x be duplicated without duplicating a
    mutable reference?

    >>> can_dup(10)
    True
    >>> can_dup("hello, world!")
    True
    >>> can_dup(True)
    True
    >>> can_dup(None)
    True
    >>> can_dup((1,2,3))
    True
    >>> can_dup((1,[2],3))
    False
    >>> can_dup([1,2,3])
    False
    >>> can_dup({1,2,3})
    False
    >>> can_dup({'a': 'b'})
    False
    '''
    if hasattr(x, 'can_dup'):
        return x.can_dup()
    if isinstance(x, tuple):
        return all(can_dup(y) for y in x)
    return any(isinstance(x,ty) for ty in (int, bool, str, type(None)))


# word creators / combinators

def const_word(x):
    def f(vs, rs, ps):
        vs.append(x)
    return f


# built-in words

def dup(vs, rs, ps):
    x = vs.pop()
    if duppable(x):
        vs.append(x)
        vs.append(x)
    else:
        raise ValueError("runtime error: can't duplicate value")

def drop(vs, rs, ps):
    vs.pop()

def swap(vs, rs, ps):
    x = vs.pop()
    y = vs.pop()
    vs.append(x)
    vs.append(y)

def dip(vs, rs, ps):
    x = vs.pop()
    rs.append(const_word(x))
    rs.append(ps[0])


# built-in forms

def define_word(vs, rs, word, code):

    # usage: define_word(trip,    dup dup)
    #        define_word(dip2(f), dip(dip(f)))

    print(word, code)


# modes
WORD = 'WORD'
FORM = 'FORM'

loaded_modules = {
    'Prelude.Primitive':
        { 'dup'         : (WORD, 0, dup)
        , 'drop'        : (WORD, 0, drop)
        , 'swap'        : (WORD, 0, swap)
        , 'dip'         : (WORD, 1, dip)
        , 'define_word' : (FORM, 2, define_word)
        },
}

if __name__ == '__main__':
    import doctest
    doctest.testmod()
