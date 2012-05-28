#!/usr/bin/python
import dicom
import re
import json
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

from netdicom.SOPclass import *
from dicom.UID import ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian

def _minihtml(title, body):
    return Response("<!DOCTYPE html><html><head><title>%s</title></head><body>%s</body></html>" % (title, body), mimetype='text/html')

from netdicom.applicationentity import AE

class QRSCUAE(AE):
    def __init__(self, calling_ae):
        super(QRSCUAE,self).__init__(calling_ae, 65500,
                                     [PatientRootFindSOPClass, VerificationSOPClass],
                                     [StorageSOPClass], [ImplicitVRLittleEndian])

    def find(self, address, port, called_ae, query_dataset):
        assoc = self.RequestAssociation({'Address': address, 'Port': port, 'AET': called_ae})
        print "DICOM Echo ... ",
        st = assoc.VerificationSOPClass.SCU(1)
        print 'done with status "%s"' % st
        print "DICOM FindSCU ... ",
        st = assoc.PatientRootFindSOPClass.SCU(query_dataset, 1)
        print 'done with status "%s"' % st
        res = [x for x in st]
        print res
        assoc.Release(0)
        return res

class DicomBridge(object):
    def __init__(self, config):
        self.url_map = Map([
            Rule('/<pacsname>/find/<qrlevel>', endpoint='qrfind'),
            ])

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, 'on_' + endpoint)(request, **values)
        except HTTPException, e:
            return e
        
    def on_qrfind(self, request, pacsname, qrlevel):
        assert qrlevel in ["patient", "study", "series", "image"]

        ds = dicom.dataset.Dataset()
        for k,v in request.args.iteritems():
            if k in dicom.datadict.NameDict:
                setattr(ds,k,v)
            elif re.match("\([0-9a-fA-F]{4},[0-9a-fA-F]{4}\)", k):
                tag = (int(k[1:5], 16), int(k[6:10], 16))
                vr = dicom.datadict.dictionaryVR(tag)
                ds.add_new(tag, vr, v)
            else:
                assert False, "Unknown tag"

        ds.QueryRetrieveLevel = qrlevel.upper()

        s = 'PacsName: %s<br/>Q/R Level: %s<br/>' % (pacsname, qrlevel)
        s += '<pre>' + str(ds) + '</pre>'

        ae = QRSCUAE("VIOLANTA")
        ae.start()
        st = ae.find("test.myhealthaccount.com", 104, "READWRITE", ds)
        s += '<pre>' + str(reduce(list.__add__, [list(x[1:]) for x in st])) + '</pre>'
        ae.Quit()
        
        return _minihtml('Logged in!', s)

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

def create_app():
    app = DicomBridge(json.load(file("dicombridge.conf")))
    return app

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    app = create_app()
    run_simple('0.0.0.0', 5000, app, use_debugger=True, use_reloader=True)

