import logging
from xmlclient import _tPartnerNS, _tSObjectNS, _tSchemaInstanceNS
from xmlclient import Client as BaseClient
from marshall import marshall
from types import TupleType, ListType
import re
import copy
from xmltramp import Namespace

_tSchemaNS = Namespace('http://www.w3.org/2001/XMLSchema')

DEFAULT_FIELD_TYPE = "string"
querytyperegx = re.compile('(?:from|FROM) (\S+)')

_logger = logging.getLogger("pyforce.{0}".format(__name__))

class QueryRecord(dict):

    def __getattr__(self, n):
        try:
            return self[n]
        except KeyError:
            return dict.__getattr__(self, n)

    def __setattr__(self, n, v):
        self[n] = v

class QueryRecordSet(list):

    def __init__(self, records, done, size, **kw):
        for r in records:
            self.append(r)
        self.done = done
        self.size = size
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def records(self):
        return self

    def __getitem__(self, n):
        if type(n) == type(''):
            try:
                return getattr(self, n)
            except AttributeError, n:
                raise KeyError
        else:
            return list.__getitem__(self, n)

class SObject(object):

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def marshall(self, fieldname, xml):
        if self.fields.has_key(fieldname):
            field = self.fields[fieldname]
        else:
            return marshall(DEFAULT_FIELD_TYPE, fieldname, xml)
        return field.marshall(xml)


class Client(BaseClient):

    cacheTypeDescriptions = False

    def __init__(self, serverUrl=None, cacheTypeDescriptions=False):
        BaseClient.__init__(self, serverUrl=serverUrl)
        self.cacheTypeDescriptions = cacheTypeDescriptions
        if self.cacheTypeDescriptions:
            self.typeDescs = {}

    def login(self, username, passwd):
        res = BaseClient.login(self, username, passwd)
        data = dict()
        data['passwordExpired'] = _bool(res[_tPartnerNS.passwordExpired])
        data['serverUrl'] = str(res[_tPartnerNS.serverUrl])
        data['sessionId'] = str(res[_tPartnerNS.sessionId])
        data['userId'] = str(res[_tPartnerNS.userId])
        data['userInfo'] = _extractUserInfo(res[_tPartnerNS.userInfo])
        return data

    def isConnected(self):
        """ First pass at a method to check if we're connected or not """
        if self.__conn and self.__conn._HTTPConnection__state == 'Idle':
            return True
        return False

    def describeGlobal(self):
        res = BaseClient.describeGlobal(self)
        data = dict()
        data['encoding'] = str(res[_tPartnerNS.encoding])
        data['maxBatchSize'] = int(str(res[_tPartnerNS.maxBatchSize]))
        sobjects = list()
        for r in res[_tPartnerNS.sobjects:]:
            d = dict()
            d['activateable'] = _bool(r[_tPartnerNS.activateable])
            d['createable'] = _bool(r[_tPartnerNS.createable])
            d['custom'] = _bool(r[_tPartnerNS.custom])
            try:
                d['customSetting'] = _bool(r[_tPartnerNS.customSetting])
            except KeyError:
                pass
            d['deletable'] = _bool(r[_tPartnerNS.deletable])
            d['deprecatedAndHidden'] = _bool(r[_tPartnerNS.deprecatedAndHidden])
            try:
                d['feedEnabled'] = _bool(r[_tPartnerNS.feedEnabled])
            except KeyError:
                pass
            d['keyPrefix'] = str(r[_tPartnerNS.keyPrefix])
            d['label'] = str(r[_tPartnerNS.label])
            d['labelPlural'] = str(r[_tPartnerNS.labelPlural])
            d['layoutable'] = _bool(r[_tPartnerNS.layoutable])
            d['mergeable'] = _bool(r[_tPartnerNS.mergeable])
            d['name'] = str(r[_tPartnerNS.name])
            d['queryable'] = _bool(r[_tPartnerNS.queryable])
            d['replicateable'] = _bool(r[_tPartnerNS.replicateable])
            d['retrieveable'] = _bool(r[_tPartnerNS.retrieveable])
            d['searchable'] = _bool(r[_tPartnerNS.searchable])
            d['triggerable'] = _bool(r[_tPartnerNS.triggerable])
            d['undeletable'] = _bool(r[_tPartnerNS.undeletable])
            d['updateable'] = _bool(r[_tPartnerNS.updateable])
            sobjects.append(SObject(**d))
        data['sobjects'] = sobjects
        data['types'] = [str(t) for t in res[_tPartnerNS.types:]]
        if not data['types']:
            # BBB for code written against API < 17.0
            data['types'] = [s.name for s in data['sobjects']]
        return data

    def describeSObjects(self, sObjectTypes):
        res = BaseClient.describeSObjects(self, sObjectTypes)
        if type(res) not in (TupleType, ListType):
            res = [res]
        data = list()
        for r in res:
            d = dict()
            d['activateable'] = _bool(r[_tPartnerNS.activateable])
            rawreldata = r[_tPartnerNS.ChildRelationships:]
            relinfo = [_extractChildRelInfo(cr) for cr in rawreldata]
            d['ChildRelationships'] = relinfo
            d['createable'] = _bool(r[_tPartnerNS.createable])
            d['custom'] = _bool(r[_tPartnerNS.custom])
            try:
                d['customSetting'] = _bool(r[_tPartnerNS.customSetting])
            except KeyError:
                pass
            d['deletable'] = _bool(r[_tPartnerNS.deletable])
            d['deprecatedAndHidden'] = _bool(r[_tPartnerNS.deprecatedAndHidden])
            try:
                d['feedEnabled'] = _bool(r[_tPartnerNS.feedEnabled])
            except KeyError:
                pass
            fields = r[_tPartnerNS.fields:]
            fields = [_extractFieldInfo(f) for f in fields]
            field_map = dict()
            for f in fields:
                field_map[f.name] = f
            d['fields'] = field_map
            d['keyPrefix'] = str(r[_tPartnerNS.keyPrefix])
            d['label'] = str(r[_tPartnerNS.label])
            d['labelPlural'] = str(r[_tPartnerNS.labelPlural])
            d['layoutable'] = _bool(r[_tPartnerNS.layoutable])
            d['mergeable'] = _bool(r[_tPartnerNS.mergeable])
            d['name'] = str(r[_tPartnerNS.name])
            d['queryable'] = _bool(r[_tPartnerNS.queryable])
            d['recordTypeInfos'] = [_extractRecordTypeInfo(rti) for rti in r[_tPartnerNS.recordTypeInfos:]]
            d['replicateable'] = _bool(r[_tPartnerNS.replicateable])
            d['retrieveable'] = _bool(r[_tPartnerNS.retrieveable])
            d['searchable'] = _bool(r[_tPartnerNS.searchable])
            try:
                d['triggerable'] = _bool(r[_tPartnerNS.triggerable])
            except KeyError:
                pass
            d['undeletable'] = _bool(r[_tPartnerNS.undeletable])
            d['updateable'] = _bool(r[_tPartnerNS.updateable])
            d['urlDetail'] = str(r[_tPartnerNS.urlDetail])
            d['urlEdit'] = str(r[_tPartnerNS.urlEdit])
            d['urlNew'] = str(r[_tPartnerNS.urlNew])
            data.append(SObject(**d))
        return data

    def create(self, sObjects):
        preparedObjects = _prepareSObjects(sObjects)
        res = BaseClient.create(self, preparedObjects)
        if type(res) not in (TupleType, ListType):
            res = [res]
        data = list()
        for r in res:
            d = dict()
            data.append(d)
            d['id'] = str(r[_tPartnerNS.id])
            d['success'] = success = _bool(r[_tPartnerNS.success])
            if not success:
                d['errors'] = [_extractError(e)
                               for e in r[_tPartnerNS.errors:]]
            else:
                d['errors'] = list()
        return data

    def convert_leads(self, lead_converts):
        preparedLeadConverts = _prepareSObjects(lead_converts)
        del preparedLeadConverts['fieldsToNull']
        res = BaseClient.convertLeads(self, preparedLeadConverts)
        if type(res) not in (TupleType, ListType):
            res = [res]
        data = list()
        for resu in res:
            d = dict()
            data.append(d)
            d['success'] = success = _bool(resu[_tPartnerNS.success])
            if not success:
                d['errors'] = [_extractError(e)
                               for e in resu[_tPartnerNS.errors:]]
            else:
                d['errors'] = list()
                d['account_id'] = str(resu[_tPartnerNS.accountId])
                d['contact_id'] = str(resu[_tPartnerNS.contactId])
                d['lead_id'] = str(resu[_tPartnerNS.leadId])
                d['opportunity_id'] = str(resu[_tPartnerNS.opportunityId])
        return data

    def sendEmail(self, emails, mass_type='SingleEmailMessage'):
        """
        Send one or more emails from Salesforce.
        
        Parameters:
            emails - a dictionary or list of dictionaries, each representing a single email as described by https://www.salesforce.com/us/developer/docs/api/Content/sforce_api_calls_sendemail.htm
            massType - 'SingleEmailMessage' or 'MassEmailMessage'. MassEmailMessage is for doing a mailmerge to up to 250 recepients in a single pass.
            
        Note:
            Newly created Salesforce Sandboxes default to System email only. In this situation, sendEmail() will fail with NO_MASS_MAIL_PERMISSION.
            
        Simple Example:
        
        >>> sendEmail([ {
            'subject': 'Test of Salesforce sendEmail()',
            'toAddresses': str(loginResult.userInfo.userEmail),
            'plainTextBody': "This is a simple test message.",
        } ])
        [{'errors': [], 'success': True}]
        
        Attachments:
        
        >>> attachment = {
            'body':'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',
            'contentType':'image/png',
            'fileName':'salesforce_logo.png',
            'inline':True
            }
        >>> message = {
            'subject': 'Test of Salesforce sendEmail()',
            'toAddresses': svc.getUserInfo()['userEmail'],
            'plainTextBody':'This is a test email message with HTML markup.\n\nYou are currently looking at the plain-text body, but the message is sent in both forms.',			'htmlBody': '<html><head><meta http-equiv="content-type" content="text/html; charset=utf-8"><body><h1>This is a test email message with HTML markup.</h1>\n\n<p>You are currently looking at the <i>HTML</i> body, but the message is sent in both forms.</p></body></html>',
            'fileAttachments': [attachment]   # Could also be a list of multiple attachments
            }
        >>> sendEmail([ message ])
        [{'errors': [], 'success': True}]
        
        Associating an email with a Salesforce object:
        
        >>> message = 
        >>> sendEmail([ {
            'subject': 'Test of Salesforce sendEmail()',
            'toAddresses': svc.getUserInfo()['userEmail'],
            'plainTextBody':'This is a test email message with HTML markup.\n\nYou are currently looking at the plain-text body, but the message is sent in both forms.',			'htmlBody': '<html><head><meta http-equiv="content-type" content="text/html; charset=utf-8"><body><h1>This is a test email message with HTML markup.</h1>\n\n<p>You are currently looking at the <i>HTML</i> body, but the message is sent in both forms.</p></body></html>',
            'targetObjectId':'003808980000GJ',  # A Contact Id
            'whatId':'500800000RuJo',  # A Case Id
            'saveAsActivity': True,
            'useSignature': True,
            'inReplyTo': '<1234567890123456789%example@example.com>',  # A previous email thread
            'references': '<1234567890123456789%example@example.com>',
            } ])
        [{'errors': [], 'success': True}]
        
        MassEmailMessage Email:
        
        >>> sendEmail([ {
            'saveAsActivity': True,
            'useSignature': True,
            'templateId': '00X80000002h4TV',
            'targetObjectIds': ['003808980000GJ'],
            'whatIds': ['500800000RuJo']}
            } ], massType='MassEmailMessage' )
        [{'errors': [], 'success': True}]
        """
        preparedEmails = _prepareSObjects(emails)
        if isinstance(preparedEmails,dict):
            # If root element is a dict, then this is a single object not an array
            del preparedEmails['fieldsToNull']
        else:
            # else this is an array, and each elelment should be prepped.
            for listitems in preparedEmails:
                del listitems['fieldsToNull']
        res = BaseClient.sendEmail(self, preparedEmails, mass_type)
        if type(res) not in (TupleType, ListType):
            res = [res]
        data = list()
        for resu in res:
            d = dict()
            data.append(d)
            d['success'] = success = _bool(resu[_tPartnerNS.success])
            if not success:
                d['errors'] = [_extractError(e)
                               for e in resu[_tPartnerNS.errors:]]
            else:
                d['errors'] = list()
        return data

    def retrieve(self, fields, sObjectType, ids):
        resultSet = BaseClient.retrieve(self, fields, sObjectType, ids)
        type_data = self.describeSObjects(sObjectType)[0]

        if type(resultSet) not in (TupleType, ListType):
            if isnil(resultSet):
                resultSet = list()
            else:
                resultSet = [resultSet]
        fields = [f.strip() for f in fields.split(',')]
        data = list()
        for result in resultSet:
            d = dict()
            data.append(d)
            for fname in fields:
                d[fname] = type_data.marshall(fname, result)
        return data

    def update(self, sObjects):
        preparedObjects = _prepareSObjects(sObjects)
        res = BaseClient.update(self, preparedObjects)
        if type(res) not in (TupleType, ListType):
            res = [res]
        data = list()
        for r in res:
            d = dict()
            data.append(d)
            d['id'] = str(r[_tPartnerNS.id])
            d['success'] = success = _bool(r[_tPartnerNS.success])
            if not success:
                d['errors'] = [_extractError(e)
                               for e in r[_tPartnerNS.errors:]]
            else:
                d['errors'] = list()
        return data

    def queryTypesDescriptions(self, types):
        """
        Given a list of types, construct a dictionary such that
        each key is a type, and each value is the corresponding sObject
        for that type.
        """
        types = list(types)
        if types:
            types_descs = self.describeSObjects(types)
        else:
            types_descs = []
        return dict(map(lambda t, d:(t, d), types, types_descs))

    def _extractRecord(self, r, typeDescs):
        record = QueryRecord()
        if r:
            row_type = str(r[_tSObjectNS.type])
            _logger.debug("row type: {0}".format(row_type))
            type_data = typeDescs[row_type]
            _logger.debug("type data: {0}".format(type_data))
            for field in r:
               fname = str(field._name[1]) 
               if isObject(field):
                   record[fname] = self._extractRecord(r[field._name:][0], typeDescs)
               elif isQueryResult(field):
                   record[fname] = QueryRecordSet(records=[self._extractRecord(rec, typeDescs) for rec in field[_tPartnerNS.records:]],
                                                  done=field[_tPartnerNS.done],
                                                  size=int(str(field[_tPartnerNS.size]))
                                                 )
               else:
                   record[fname] = type_data.marshall(fname, r)
        return record

    def query(self, *args, **kw):
        if self.cacheTypeDescriptions:
            typeDescs = self.typeDescs
        else:
            typeDescs = {}

        if len(args) == 1: # full query string
            queryString = args[0]
        elif len(args) == 2: # BBB: fields, sObjectType
            queryString = 'select %s from %s' % (args[0], args[1])
            if 'conditionalExpression' in kw: # BBB: fields, sObjectType, conditionExpression as kwarg
                queryString += ' where %s' % (kw['conditionalExpression'])
        elif len(args) == 3: # BBB: fields, sObjectType, conditionExpression as positional arg
            whereClause = args[2] and (' where %s' % args[2]) or ''
            queryString = 'select %s from %s%s' % (args[0], args[1], whereClause)
        else:
            raise RuntimeError, "Wrong number of arguments to query method."

        res = BaseClient.query(self, queryString)
        # calculate the union of the sets of record types from each record
        types = reduce(lambda a,b: a|b, [getRecordTypes(r) for r in res[_tPartnerNS.records:]], set())
        new_types = types - set(typeDescs.keys())
        if new_types:
            typeDescs.update(self.queryTypesDescriptions(new_types))
        data = QueryRecordSet(records=[self._extractRecord(r, typeDescs) for r in res[_tPartnerNS.records:]],
                              done=_bool(res[_tPartnerNS.done]),
                              size=int(str(res[_tPartnerNS.size])),
                              queryLocator = str(res[_tPartnerNS.queryLocator]))
        return data

    def queryMore(self, queryLocator):
        if self.cacheTypeDescriptions:
            typeDescs = self.typeDescs
        else:
            typeDescs = {}

        locator = queryLocator
        res = BaseClient.queryMore(self, locator)
        # calculate the union of the sets of record types from each record
        types = reduce(lambda a,b: a|b, [getRecordTypes(r) for r in res[_tPartnerNS.records:]], set())
        new_types = types - set(typeDescs.keys())
        if new_types:
            typeDescs.update(self.queryTypesDescriptions(new_types))
        data = QueryRecordSet(records=[self._extractRecord(r, typeDescs) for r in res[_tPartnerNS.records:]],
                              done=_bool(res[_tPartnerNS.done]),
                              size=int(str(res[_tPartnerNS.size])),
                              queryLocator = str(res[_tPartnerNS.queryLocator]))
        return data

    def search(self, sosl):
        if self.cacheTypeDescriptions:
            typeDescs = self.typeDescs
        else:
            typeDescs = {}
        res = BaseClient.search(self, sosl)

        # calculate the union of the sets of record types from each record
        if len(res):
            types = reduce(lambda a,b: a|b, [getRecordTypes(r) for r in res[_tPartnerNS.searchRecords]], set())
            new_types = types - set(typeDescs.keys())
            if new_types:
                typeDescs.update(self.queryTypesDescriptions(new_types))
            return [self._extractRecord(r, typeDescs) for r in res[_tPartnerNS.searchRecords]]
        else:
            return []

    def delete(self, ids):
        res = BaseClient.delete(self, ids)
        if type(res) not in (TupleType, ListType):
            res = [res]
        data = list()
        for r in res:
            d = dict()
            data.append(d)
            d['id'] = str(r[_tPartnerNS.id])
            d['success'] = success = _bool(r[_tPartnerNS.success])
            if not success:
                d['errors'] = [_extractError(e)
                               for e in r[_tPartnerNS.errors:]]
            else:
                d['errors'] = list()
        return data

    def upsert(self, externalIdName, sObjects):
        preparedObjects = _prepareSObjects(sObjects)
        res = BaseClient.upsert(self, externalIdName, preparedObjects)
        if type(res) not in (TupleType, ListType):
            res = [res]
        data = list()
        for r in res:
            d = dict()
            data.append(d)
            d['id'] = str(r[_tPartnerNS.id])
            d['success'] = success = _bool(r[_tPartnerNS.success])
            if not success:
                d['errors'] = [_extractError(e)
                               for e in r[_tPartnerNS.errors:]]
            else:
                d['errors'] = list()
            d['isCreated'] = d['created'] = _bool(r[_tPartnerNS.created])
        return data

    def getDeleted(self, sObjectType, start, end):
        res = BaseClient.getDeleted(self, sObjectType, start, end)
        res = res[_tPartnerNS.deletedRecords:]
        if type(res) not in (TupleType, ListType):
            res = [res]
        data = list()
        for r in res:
            d = dict(
                id = str(r[_tPartnerNS.id]),
                deletedDate = marshall('datetime', 'deletedDate', r,
                ns=_tPartnerNS))
            data.append(d)
        return data

    def getUpdated(self, sObjectType, start, end):
        res = BaseClient.getUpdated(self, sObjectType, start, end)
        res = res[_tPartnerNS.ids:]
        if type(res) not in (TupleType, ListType):
            res = [res]
        return [str(r) for r in res]

    def getUserInfo(self):
        res = BaseClient.getUserInfo(self)
        data = _extractUserInfo(res)
        return data

    def describeTabs(self):
        res = BaseClient.describeTabs(self)
        data = list()
        for r in res:
            tabs = [_extractTab(t) for t in r[_tPartnerNS.tabs:]]
            d = dict(
                    label = str(r[_tPartnerNS.label]),
                    logoUrl = str(r[_tPartnerNS.logoUrl]),
                    selected = _bool(r[_tPartnerNS.selected]),
                    tabs=tabs)
            data.append(d)
        return data

    def describeLayout(self, sObjectType):
        raise NotImplementedError


class Field(object):

    def __init__(self, **kw):
        for k,v in kw.items():
            setattr(self, k, v)

    def marshall(self, xml):
        return marshall(self.type, self.name, xml)

def _doPrep(field_dict):
    """
    _doPrep is makes changes in-place.
    Do some prep work converting python types into formats that
    Salesforce will accept.
    This includes converting lists of strings to "apple;orange;pear".
    Dicts will be converted to embedded objects
    None or empty list values will be Null-ed
    """
    fieldsToNull = []
    for k,v in field_dict.items():
        if v is None:
            fieldsToNull.append(k)
            field_dict[k] = []
        if hasattr(v,'__iter__'):
            if len(v) == 0:
                fieldsToNull.append(k)
            elif isinstance(v, dict):
                innerCopy = copy.deepcopy(v)
                _doPrep(innerCopy)
                field_dict[k] = innerCopy
            else:
                field_dict[k] = ";".join(v)
    if 'fieldsToNull' in field_dict:
        raise ValueError, "fieldsToNull should be populated by the client, not the caller."
    field_dict['fieldsToNull'] = fieldsToNull

# sObjects can be 1 or a list. If values are python lists or tuples, we
# convert these to strings:
# ['one','two','three'] becomes 'one;two;three'
def _prepareSObjects(sObjects):

     sObjectsCopy = copy.deepcopy(sObjects)
     if isinstance(sObjectsCopy,dict):
        # If root element is a dict, then this is a single object not an array
         _doPrep(sObjectsCopy)
     else:
         # else this is an array, and each elelment should be prepped.
         for listitems in sObjectsCopy:
             _doPrep(listitems)
     return sObjectsCopy

def _bool(val):
    return str(val) == 'true'

def _extractFieldInfo(fdata):
    data = dict()
    data['autoNumber'] = _bool(fdata[_tPartnerNS.autoNumber])
    data['byteLength'] = int(str(fdata[_tPartnerNS.byteLength]))
    data['calculated'] = _bool(fdata[_tPartnerNS.calculated])
    data['createable'] = _bool(fdata[_tPartnerNS.createable])
    data['nillable'] = _bool(fdata[_tPartnerNS.nillable])
    data['custom'] = _bool(fdata[_tPartnerNS.custom])
    data['defaultedOnCreate'] = _bool(fdata[_tPartnerNS.defaultedOnCreate])
    data['digits'] = int(str(fdata[_tPartnerNS.digits]))
    data['filterable'] = _bool(fdata[_tPartnerNS.filterable])
    try:
        data['htmlFormatted'] = _bool(fdata[_tPartnerNS.htmlFormatted])
    except KeyError:
        data['htmlFormatted'] = False
    data['label']  = str(fdata[_tPartnerNS.label])
    data['length'] = int(str(fdata[_tPartnerNS.length]))
    data['name'] = str(fdata[_tPartnerNS.name])
    data['nameField'] = _bool(fdata[_tPartnerNS.nameField])
    plValues = fdata[_tPartnerNS.picklistValues:]
    data['picklistValues'] = [_extractPicklistEntry(p) for p in plValues]
    data['precision'] = int(str(fdata[_tPartnerNS.precision]))
    data['referenceTo'] = [str(r) for r in fdata[_tPartnerNS.referenceTo:]]
    data['restrictedPicklist'] = _bool(fdata[_tPartnerNS.restrictedPicklist])
    data['scale'] = int(str(fdata[_tPartnerNS.scale]))
    data['soapType'] = str(fdata[_tPartnerNS.soapType])
    data['type'] = str(fdata[_tPartnerNS.type])
    data['updateable'] = _bool(fdata[_tPartnerNS.updateable])
    try:
        data['dependentPicklist'] = _bool(fdata[_tPartnerNS.dependentPicklist])
        data['controllerName'] = str(fdata[_tPartnerNS.controllerName])
    except KeyError:
        data['dependentPicklist'] = False
        data['controllerName'] = ''
    return Field(**data)


def _extractPicklistEntry(pldata):
    data = dict()
    data['active'] = _bool(pldata[_tPartnerNS.active])
    data['validFor'] = [str(v) for v in pldata[_tPartnerNS.validFor:]]
    data['defaultValue'] = _bool(pldata[_tPartnerNS.defaultValue])
    data['label'] = str(pldata[_tPartnerNS.label])
    data['value'] = str(pldata[_tPartnerNS.value])
    return data


def _extractChildRelInfo(crdata):
    data = dict()
    data['cascadeDelete'] = _bool(crdata[_tPartnerNS.cascadeDelete])
    data['childSObject'] = str(crdata[_tPartnerNS.childSObject])
    data['field'] = str(crdata[_tPartnerNS.field])
    return data

def _extractRecordTypeInfo(rtidata):
    data = dict()
    data['available'] = _bool(rtidata[_tPartnerNS.available])
    data['defaultRecordTypeMapping'] = _bool(rtidata[_tPartnerNS.defaultRecordTypeMapping])
    data['name'] = str(rtidata[_tPartnerNS.name])
    data['recordTypeId'] = str(rtidata[_tPartnerNS.recordTypeId])
    return data

def _extractError(edata):
    data = dict()
    data['statusCode'] = str(edata[_tPartnerNS.statusCode])
    data['message'] = str(edata[_tPartnerNS.message])
    data['fields'] = [str(f) for f in edata[_tPartnerNS.fields:]]
    return data

def _extractTab(tdata):
    data = dict(
            custom = _bool(tdata[_tPartnerNS.custom]),
            label = str(tdata[_tPartnerNS.label]),
            sObjectName = str(tdata[_tPartnerNS.sobjectName]),
            url = str(tdata[_tPartnerNS.url]))
    return data

def _extractUserInfo(res):
    data = dict(
            accessibilityMode = _bool(res[_tPartnerNS.accessibilityMode]),
            currencySymbol = str(res[_tPartnerNS.currencySymbol]),
            organizationId = str(res[_tPartnerNS.organizationId]),
            organizationMultiCurrency = _bool(
                    res[_tPartnerNS.organizationMultiCurrency]),
            organizationName = str(res[_tPartnerNS.organizationName]),
            userDefaultCurrencyIsoCode = str(
                    res[_tPartnerNS.userDefaultCurrencyIsoCode]),
            userEmail = str(res[_tPartnerNS.userEmail]),
            userFullName = str(res[_tPartnerNS.userFullName]),
            userId = str(res[_tPartnerNS.userId]),
            userLanguage = str(res[_tPartnerNS.userLanguage]),
            userLocale = str(res[_tPartnerNS.userLocale]),
            userTimeZone = str(res[_tPartnerNS.userTimeZone]),
            userUiSkin = str(res[_tPartnerNS.userUiSkin]))
    return data

def isObject(xml):
    try:
        if xml(_tSchemaInstanceNS.type) == 'sf:sObject':
            return True
        else:
            return False
    except KeyError:
        return False

def isQueryResult(xml):
    try:
        if xml(_tSchemaInstanceNS.type) == 'QueryResult':
            return True
        else:
            return False
    except KeyError:
        return False

def isnil(xml):
    try:
        if xml(_tSchemaInstanceNS.nil) == 'true':
            return True
        else:
            return False
    except KeyError:
        return False

def getRecordTypes(xml):
    record_types = set() 
    if xml:
        record_types.add(str(xml[_tSObjectNS.type]))
        for field in xml:
            if isObject(field):
                record_types.update(getRecordTypes(field))
            elif isQueryResult(field):
                record_types.update(reduce(lambda x, y: x|y, [getRecordTypes(r) for r in field[_tPartnerNS.records:]]))
    return record_types
