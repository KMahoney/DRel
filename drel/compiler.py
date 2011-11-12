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
        return self._connection.ops.quote_name(s)

    def refer(self, obj):
        try:
            return self._aliases[obj]
        except KeyError:
            alias = self.q("t%d" % len(self._aliases))
            self._aliases[obj] = alias
            return alias
