#!/usr/bin/python

from bottle import route, run, request, response, install
import uuid
import glob

@route("/")
def returnmultipart():
    boundary='----multipart-boundary-%s----' % (uuid.uuid1(),)
    response.content_type = 'multipart/mixed; boundary=%s' % (boundary,)
    s = ''

    for fn in glob.glob("*.dcm"):
        print fn
        s += "\n" + boundary + "\n"
        s += 'Content-Disposition: attachment; filename="%s";\n' % (fn,)
        s += 'Content-Type: application/dicom;\n'
        q = file(fn).read()
        s += 'Content-Length: %i\n' % (len(q),)
        s += '\n'
        s += q

    s += '\n' + boundary + '\n'

    return s
    

run(host='localhost', port=5000)
