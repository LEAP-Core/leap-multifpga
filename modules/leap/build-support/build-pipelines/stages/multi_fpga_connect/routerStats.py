##
## Manage generation of statistics within a module by collecting counter names
## and then providing methods to emit a statistics node.
##
class RouterStats:
    """Manage router statistics within a generated Bluespec module."""

    def __init__(self,name):
        self.name = name
        self.counters = list()

    def addCounter(self, name, tag, descr):
        """Add a new counter.  The 'name' field will be used to reference the
           counter (using stats.incr(name)).  The 'tag' and 'descr' fields are
           passed to statName()."""
        self.counters.append([ name, tag, descr ])

    def genStats(self):
        """Return the Bluespec to generate the statistics node and counters."""

        if (len(self.counters) == 0):
            return ''

        # First generate the set of IDs
        s = '\n\tSTAT_ID ' + self.name + 'statIDs[' + str(len(self.counters)) + '] = {\n'
        idx = 0
        for cnt in self.counters:
            s += '\t\tstatName("' + cnt[1] + '", "' + cnt[2] + '")'
            if ((idx + 1) != len(self.counters)):
                s += ','
            s += '\n'
            idx += 1
        s += '\t};'

        # Generate Bluespec names corresponding to the ID array
        s += '\n'
        idx = 0
        for cnt in self.counters:
            s += '\tlet ' + cnt[0] + ' = ' + str(idx) + ';\n'
            idx += 1

        # Generate the statistics node
        s += '\n\tSTAT_VECTOR#(' + str(len(self.counters)) + ') ' + self.name + 'stats <- mkStatCounter_Vector(' + self.name + 'statIDs);\n\n'

        return s

    def incrCounter(self, name):
        """Emit a string with the Bluespec code that increments a counter."""
        return  self.name + 'stats.incr_NB(' + name + ')'
