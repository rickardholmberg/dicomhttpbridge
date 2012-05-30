#!/usr/bin/python

from bottle import route, run, request, response, install
import uuid
import glob
import os

@route("/")
def returnmultipart():
    boundary='----multipart-boundary-%s----' % (uuid.uuid1(),)
    response.content_type = 'multipart/mixed; boundary=%s' % (boundary,)
    s = ''

    for fn in glob.glob("*.dcm"):
        print fn
        s += "\r\n" + boundary + "\r\n"
        s += 'Content-Disposition: attachment; filename="%s";\r\n' % (fn,)
        s += 'Content-Type: application/dicom;\r\n'
        s += 'Content-Length: %i\r\n' % (os.stat(fn).st_size,)
        s += '\r\n'
        s += file(fn).read()

    s += '\r\n' + boundary + '\r\n'

    return s
    

run(host='localhost', port=5000)
