#!/usr/bin/python

from bottle import route, run, request, response, install
import uuid

@route("/")
def returnmultipart():
    boundary='----multipart-boundary-%s----' % (uuid.uuid1(),)
    response.content_type = 'multipart/mixed; boundary=%s' % (boundary,)
    s = boundary + "\n"
    s += 'Content-Disposition: attachment filename="hej"\n'
    s += '\n'
    s += '<html><head/><body>HEj!</body></html>\n'
    s += boundary + "\n"
    s += 'Content-Disposition: attachment filename="hej"\n'
    s += '\n'
    s += '<html><head/><body>HEj2!</body></html>\n'
    s += boundary + '\n'

    return s
    

run(host='localhost', port=5000)
