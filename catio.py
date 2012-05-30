import StringIO

class CatIO(object):
    def __init__(self):
        self._bufs = []
        self._curbuf = 0
        self._curpos = 0
        self._closed = False
        self.softspace = 0

    def __iadd__(self, x):
        if isinstance(x, basestring):
            return self.__iadd__(StringIO.StringIO(x))
        self._bufs.append(x)
        return self

    def flush(self):
        return

    def next(self):
        raise NotImplementedError()

    def readline(self, size = None):
        raise NotImplementedError()
    def readlines(self, sizehint = None):
        raise NotImplementedError()
    @property
    def closed(self):
        return self._closed
    @property
    def newlines(self):
        return None

    def read(self, size = None):
        if self._closed:
            raise ValueError()
        if len(self._bufs) == 0:
            return ''
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
        if self._curbuf < len(self._bufs):
            self._bufs[self._curbuf].seek(0)
        if size == None:
            return r + self.read()
        else:
            return r + self.read(size - len(r))

    def tell(self):
        if self._closed:
            raise ValueError()
        return self._curpos

    def write(self, *args, **kwargs):
        if self._closed:
            raise ValueError()
        raise IOError('File not open for writing',)
        
    def seek(self, offset, whence=0):
        if self._closed:
            raise ValueError()
        if len(self._bufs) == 0:
            return
        if whence == 0:
            self._curbuf = 0
            self._curpos = 0
            if offset < 0:
                offset = 0
            while True:
                self._bufs[self._curbuf].seek(0, 2)
                curlen = self._bufs[self._curbuf].tell()
                if offset <= self._curpos + curlen:
                    self._bufs[self._curbuf].seek(offset - self._curpos, 0)
                    self._curpos = offset
                    return
                else:
                    self._curpos += curlen
                    if self._curbuf < len(self._bufs)-1:
                        self._curbuf += 1
                    else:
                        break
        elif whence == 1:
            return self.seek(self._curpos + offset)
        elif whence == 2:
            curbufpos = self._bufs[self._curbuf].tell()
            self._bufs[self._curbuf].seek(0)
            self._curpos -= curbufpos
            while self._curbuf < len(self._bufs):
                self._bufs[self._curbuf].seek(0,2)
                self._curpos += self._bufs[self._curbuf].tell()
                self._curbuf += 1
            self._curbuf -= 1
            return self.seek(offset, 1)
        else:
            raise IOError(22, 'Invalid argument')
