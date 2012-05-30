class CatIO(object):
    def __init__(self):
        self._bufs = []
        self._curbuf = None
        self._curpos = 0

    def __iadd__(self, x):
        self._bufs.append(x)
        return self

    def read(self, size = None):
        if self._curbuf == None:
            if len(self._bufs) == 0:
                return ''
            self._curbuf = 0
        if size == None:
            r = self._bufs[self._curbuf].read()
        else:
            r = self._bufs[self._curbuf].read(size)
        self._curpos += len(r)
        if size != None and len(r) >= size:
            return r
        if self._curbuf >= len(self._bufs)-1:
            return r
        self._curbuf += 1
        return r + self.read(size - len(r))

    def tell(self):
        return self._curpos
        
        
