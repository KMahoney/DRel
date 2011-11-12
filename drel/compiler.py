class Compiler(object):
    '''
    A class that maintains state during the compilation of SQL, as the
    AST nodes themselves are stateless and immutable.

    '''
    def __init__(self, connection):
        self._aliases = {}
        self.values = []
        self._connection = connection

    def q(self, s):
        '''Quote a name.'''
        return self._connection.ops.quote_name(s)

    def refer(self, obj):
        '''
        Return the quoted name of an object, creating a new name if it
        hasn't been referred to before.

        '''
        try:
            return self._aliases[obj]
        except KeyError:
            alias = self.q("t%d" % len(self._aliases))
            self._aliases[obj] = alias
            return alias
