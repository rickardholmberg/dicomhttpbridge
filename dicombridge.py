#!/usr/bin/python
import dicom
import re
import json
import threading
import datetime
import random
import StringIO

from bottle import route, run, request, response, install

from netdicom.SOPclass import *
from dicom.UID import ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian

from netdicom.applicationentity import AE

def media_storage_sop_instance_uid():
    return conf['DICOMUIDRoot'] + '15.1'

def implementation_class_uid():
    return conf['DICOMUIDRoot'] + '15.2'

def generate_uid():
    root = conf['DICOMUIDRoot']
    suffix = datetime.datetime.isoformat(datetime.datetime.utcnow()).replace('-','').replace('T','.').replace(":","")
    while suffix.find(".0") != -1:
        suffix = suffix.replace(".0",".")
    if suffix.endswith("."):
        suffix = suffix[:-1]
    suffix += '.' + str(random.randint(0,10**(63-len(root+suffix))-1))
    return root + suffix


def add_DIMSE_tags_to_pydicom():
    # See DICOM PS3.7-2011, Table E.1-1
    DimseDicomDictionary = {
        0x00000000: ('UL', '1', "Command Group Length", ''),
        0x00000002: ('UI', '1', "Affected SOP Class UID", ''),
        0x00000003: ('UI', '1', "Requested SOP Class UID", ''),
        0x00000100: ('US', '1', "Command Field", ''),
        0x00000110: ('US', '1', "Message ID", ''),
        0x00000120: ('US', '1', "Message ID Being Responded To", ''),
        0x00000600: ('AE', '1', "Move Destination", ''),
        0x00000700: ('US', '1', "Priority", ''),
        0x00000800: ('US', '1', "Command Data Set Type", ''),
        0x00000900: ('US', '1', "Status", ''),
        0x00000901: ('AT', '1-n', "Offending Element", ''),
        0x00000902: ('LO', '1', "Error Comment", ''),
        0x00000903: ('US', '1', "Error ID", ''),
        0x00001000: ('UI', '1', "Affected SOP Instance UID", ''),
        0x00001001: ('UI', '1', "Requested SOP Instance UID", ''),
        0x00001002: ('US', '1', "Event Type ID", ''),
        0x00001005: ('AT', '1-n', "Attribute Identifier List", ''),
        0x00001008: ('US', '1', "Action Type ID", ''),
        0x00001020: ('US', '1', "Number of Remaining Sub-operations", ''),
        0x00001021: ('US', '1', "Number of Completed Sub-operations", ''),
        0x00001022: ('US', '1', "Number of Failed Sub-operations", ''),
        0x00001023: ('US', '1', "Number of Warning Sub-operations", ''),
        0x00001030: ('AE', '1', "Move Originator Application Entity Title", ''),
        0x00001031: ('US', '1', "Move Originator Message ID", ''),
        }
    
    if len(dicom._dicom_dict.DicomDictionary.values()[0]) == 5:
        # Handles pydicom < 1.0
        for k,v in DimseDicomDictionary.iteritems():
            DimseDicomDictionary[k] = (v[0], v[1], v[2], v[3], v[2].replace(" ","").replace("-",""))

    dicom._dicom_dict.DicomDictionary.update(DimseDicomDictionary)

    # TODO: Add method update_namedict() to datadict.py
    # Provide for the 'reverse' lookup. Given clean name, what is the tag?
    dicom.datadict.NameDict = {dicom.datadict.CleanName(tag): tag for tag in dicom.datadict.DicomDictionary}
    dicom.datadict.keyword_dict = dict([(dicom.datadict.dictionary_keyword(tag), tag) for tag in dicom.datadict.DicomDictionary])

add_DIMSE_tags_to_pydicom()

def DicomFileStringIO(is_implicit_VR = True, is_little_endian = True, buf=''):
    fp = dicom.filebase.DicomFileLike(StringIO.StringIO(buf))
    fp.is_implicit_VR = is_implicit_VR
    fp.is_little_endian = is_little_endian
    return fp

def strize_dict(d):
    # pynetdicom has trouble receiving unicode strings in some
    # positions, so make everything in the config strings instead of
    # unicode.
    for k,v in d.iteritems():
        if isinstance(v, unicode):
            d[k] = str(v)
        elif isinstance(v, dict):
            d[k] = strize_dict(v)
    return d

def dicom_to_plain(x):
    if isinstance(x, dicom.dataset.Dataset):
        return [{'tag':"(%04x,%04x)" % (k.group, k.elem),
                 'value': dicom_to_plain(v),
                 'VR': v.VR,
                 'name': dicom.datadict.DicomDictionary.get(k.group << 16 | k.elem, ('','','N/A'))[2]}
                for k,v in x.iteritems()]
    if isinstance(x, dicom.dataelem.RawDataElement) or isinstance(x, dicom.dataelem.DataElement):
        return dicom_to_plain(x.value)
    if isinstance(x, dicom.sequence.Sequence):
        return [dicom_to_plain(y) for y in x]
    if isinstance(x, dicom.valuerep.DS):
        return float(x)
    if isinstance(x, dicom.valuerep.IS):
        return int(x)
    if isinstance(x, list):
        return [dicom_to_plain(v) for v in x]
    return x

class QRSCUAE(AE):
    def __init__(self, calling_ae):
        super(QRSCUAE,self).__init__(calling_ae, 
                                     [PatientRootFindSOPClass, VerificationSOPClass],
                                     [StorageSOPClass], [ImplicitVRLittleEndian])

    def find(self, address, port, called_ae, query_dataset):
        print "find(%s, %s, %s)" % (address, port ,called_ae)
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

class MoveSCUAE(AE):
    def __init__(self, calling_ae):
        super(MoveSCUAE,self).__init__(calling_ae, 
                                       [PatientRootFindSOPClass,
                                        PatientRootMoveSOPClass,
                                        VerificationSOPClass],
                                       [StorageSOPClass], [ImplicitVRLittleEndian])

    def move(self, address, port, called_ae, query_dataset):
        # TODO other Q/R level and frame range keys
        assoc = self.RequestAssociation({'Address': address, 'Port': port, 'AET': called_ae})
        print "DICOM Echo ... ",
        st = assoc.VerificationSOPClass.SCU(1)
        print 'done with status "%s"' % st
        print "DICOM MoveSCU ... ",
        st = assoc.PatientRootMoveSOPClass.SCU(query_dataset, conf['LocalAETitle'], 1)
        st = [x for x in st]
        print 'move status "%s"' % st

        assoc.Release(0)
        return st

class StoreSCPAE(AE):
    @staticmethod
    def OnAssociateRequest(association):
        print "Associate request: %s" % (association,)

    @staticmethod
    def OnAssociateResponse(association):
        print "Association response received"

    @staticmethod
    def OnReceiveEcho(verificationServiceClass):
        print "Echo received: %s" % (verificationServiceClass,)

    @staticmethod
    def OnReceiveStore(SOPClass, DS):
        print "Received C-STORE"

        if DS.SOPInstanceUID not in receivedSOPInstanceEvents:
            print "Received unexpected SOP Instance %s! Discarding." % (DS.SOPInstanceUID,)
        else:
            print "Received SOP Instance %s. Waking client." % (DS.SOPInstanceUID,)
            evt = receivedSOPInstanceEvents[DS.SOPInstanceUID]
            receivedSOPInstances[DS.SOPInstanceUID] = DS
            evt.set()

        # must return appropriate status
        return SOPClass.Success

def write_file(dataset):
    """Store the Dataset specified and return it as a string.
    
    If there is no Transfer Syntax tag in the dataset,
       Set dataset.is_implicit_VR, and .is_little_endian
       to determine the transfer syntax used to write the file.
    """

    # Decide whether to write DICOM preamble. Should always do so unless trying to mimic the original file read in
    preamble = "\0"*128
    
    file_meta = dataset.file_meta
    if file_meta is None:
        file_meta = Dataset()
    if 'TransferSyntaxUID' not in file_meta:
        if dataset.is_little_endian and dataset.is_implicit_VR:
            file_meta.add_new((2, 0x10), 'UI', ImplicitVRLittleEndian)
        elif dataset.is_little_endian and not dataset.is_implicit_VR:
            file_meta.add_new((2, 0x10), 'UI', ExplicitVRLittleEndian)
        elif dataset.is_big_endian and not dataset.is_implicit_VR:
            file_meta.add_new((2, 0x10), 'UI', ExplicitVRBigEndian)
        else:
            raise NotImplementedError, "pydicom has not been verified for Big Endian with Implicit VR"
        
    fp = DicomFileStringIO(is_implicit_VR = dataset.is_implicit_VR, is_little_endian = dataset.is_little_endian)
    try:
        fp.write(preamble)  # blank 128 byte preamble
        dicom.filewriter._write_file_meta_info(fp, file_meta) 
        
        # Set file VR, endian. MUST BE AFTER writing META INFO (which changes to Explict LittleEndian)
        fp.is_implicit_VR = dataset.is_implicit_VR
        fp.is_little_endian = dataset.is_little_endian
        
        dicom.filewriter.write_dataset(fp, dataset)
        return fp.parent.getvalue()
    finally:
        fp.close()
    return None


receivedSOPInstances = {}
receivedSOPInstanceEvents = {}

@route("/<pacsname>/find/<qrlevel>")
def qrfind(pacsname, qrlevel):
    assert qrlevel in ["patient", "study", "series", "image"]

    ds = dicom.dataset.Dataset()
    for k,v in request.query.iteritems():
        if k in dicom.datadict.NameDict:
            setattr(ds,k,v)
        elif re.match("\([0-9a-fA-F]{4},[0-9a-fA-F]{4}\)", k):
            tag = (int(k[1:5], 16), int(k[6:10], 16))
            vr = dicom.datadict.dictionaryVR(tag)
            ds.add_new(tag, vr, v)
        else:
            assert False, "Unknown tag"

    ds.QueryRetrieveLevel = qrlevel.upper()

    print 'PacsName: %s\n>Q/R Level: %s' % (pacsname, qrlevel)
    print ds
    
    ae = QRSCUAE(conf['LocalAETitle'])
    pacs = conf['RemoteAEs'][pacsname]
    print pacs
    st = ae.find(address=pacs['Address'], port=pacs['Port'], called_ae=pacs['AETitle'], query_dataset=ds)
    print reduce(list.__add__, [list(x[1:]) for x in st], [])
    ae.Quit()
    
    return {'status': 'Success',
            'datasets': dicom_to_plain(reduce(list.__add__, [list(x[1:]) for x in st if x[0].Type != 'Success'], []))}

@route("/<pacsname>/get/<qrlevel>")
def get(pacsname, qrlevel):
    assert qrlevel in 'image'
    ae = MoveSCUAE(conf['LocalAETitle'])

    ds = dicom.dataset.Dataset()
    for k,v in request.query.iteritems():
        if k in dicom.datadict.NameDict:
            setattr(ds,k,v)
        elif re.match("\([0-9a-fA-F]{4},[0-9a-fA-F]{4}\)", k):
            tag = (int(k[1:5], 16), int(k[6:10], 16))
            vr = dicom.datadict.dictionaryVR(tag)
            ds.add_new(tag, vr, v)
        else:
            assert False, "Unknown tag"

    ds.QueryRetrieveLevel = qrlevel.upper()

    receivedSOPInstanceEvents[ds.SOPInstanceUID] = threading.Event()

    pacs = conf['RemoteAEs'][pacsname]
    print ae.move(address=pacs['Address'], port=pacs['Port'], called_ae=pacs['AETitle'], query_dataset = ds)
    ae.Quit()

    del receivedSOPInstanceEvents[ds.SOPInstanceUID]
    retrievedDS = receivedSOPInstances[ds.SOPInstanceUID]
    del receivedSOPInstances[ds.SOPInstanceUID]
    file_meta = dicom.dataset.Dataset()
    file_meta.MediaStorageSOPClassUID = retrievedDS.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = media_storage_sop_instance_uid()
    file_meta.ImplementationClassUID = implementation_class_uid()

    fds = dicom.dataset.FileDataset(None, {}, file_meta=file_meta, preamble="\0" * 128)
    fds.update(retrievedDS)
    fds.is_little_endian = True
    fds.is_implicit_VR = True

    response.content_type = 'application/dicom'
    response.headers['Content-Disposition'] = 'attachment; filename="%s_%s.dcm"' % (fds.Modality, fds.SOPInstanceUID,)

    return write_file(fds)

conf = strize_dict(json.load(file("dicombridge.conf")))

if __name__ == '__main__':

    storescpae = StoreSCPAE(AET=conf['LocalAETitle'], port=conf['LocalPort'],
                            SOPSCU=[],
                            SOPSCP=[MRImageStorageSOPClass,
                                    CTImageStorageSOPClass,
                                    RTImageStorageSOPClass,
                                    RTPlanStorageSOPClass,
                                    PositronEmissionTomographyImageStorageSOPClass, VerificationSOPClass])
    storescpae.start()

    run(host='localhost', port=5000)
    storescpae.Quit()

