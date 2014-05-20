# coding: utf-8
"""
From http://code.google.com/p/cherrypy-jsonrpc (LGPL)

Some modifications:
- Content-Type (application/json)
"""

import sys
import httplib
import cherrypy
import traceback
try:
    import jsonlib2 as json
    _ParseError = json.ReadError
except ImportError:
    import json
    _ParseError = ValueError

    
def _raw_body_reader():
    """
    Liest den Body ein, bevor dieser von CherryPy falsch geparst wird.
    Reads the body, before CherryPy parses it in a false kind.
    """
    if cherrypy.request.method in cherrypy.request.methods_with_bodies:
        cherrypy.request.raw_body = cherrypy.request.rfile.read()

cherrypy.tools.raw_body_reader = cherrypy.Tool("before_request_body", _raw_body_reader)


def set_content_type_json():
    """
    Setzt den Content-Type des Response auf "text/x-json"
    """
    cherrypy.response.headers["Content-Type"] = "application/json"


class SuccessfulResponse(object):
    """
    Represents a successful response.
    """

    def __init__(self, jsonrpc = None, id = None, result = None):
        """
        :param jsonrpc: JSON-RPC version string
        :param id: JSON-RPC transaction id
        :param result: Result data
        """
        self.jsonrpc = jsonrpc
        self.id = id
        self.result = result


    def to_dict(self):
        """
        Returns the response object as dictionary.
        """
        retdict = {}
        if self.jsonrpc:
            retdict["jsonrpc"] = self.jsonrpc
        if not self.id is None:
            retdict["id"] = self.id
        if not self.result is None:
            retdict["result"] = self.result
        
        return retdict


class ErrorResponse(object): 
    """
    Represents an error response object
    """
    
    code = None
    message = None
    
    
    def __init__(self, jsonrpc = None, id = None, data = None):
        """
        :param jsonrpc: JSON-RPC version string
        :param id: JSON-RPC transaction id
        :param data: Additional error informations. Can be any, to JSON
            translatable, data structure.
        """
        self.jsonrpc = jsonrpc
        self.id = id
        self.data = data
    
    
    def to_dict(self):
        """
        Returns the response object as dictionary.
        """
        retdict = {"error": {}}
        if self.jsonrpc:
            retdict["jsonrpc"] = self.jsonrpc
        retdict["id"] = self.id
        retdict["error"]["code"] = self.code
        retdict["error"]["message"] = self.message
        if self.data:
            retdict["error"]["data"] = self.data
            if isinstance(self.data, basestring):
                if self.message:
                    retdict["error"]["message"] = \
                        self.message + u" " + self.data.capitalize()
                else:
                    retdict["error"]["message"] = self.data.capitalize()
        return retdict


class ParseErrorResponse(ErrorResponse):
    code = -32700
    message = u"Invalid JSON was received by the server."


class InvalidRequestResponse(ErrorResponse):
    code = -32600
    message = u"The JSON sent is not a valid Request object."


class MethodNotFoundResponse(ErrorResponse):
    code = -32601
    message = u"The method does not exist / is not available."


class InvalidParamsResponse(ErrorResponse):
    code = -32602
    message = u"Invalid method parameter(s)."


class InternalErrorResponse(ErrorResponse):
    code = -32603
    message = u"Internal JSON-RPC error."


class JsonRpcMethods(object):
    """
    Erbt man von dieser Klasse, dann werden die mit *exposed* markierten
    Methoden der Klasseninstanz automatisch zu JSON-RPC-Methoden.
    """
    
    _cp_config = {
        "tools.encode.on": True,
        "tools.encode.encoding": "utf-8",
        "tools.decode.on": True,
        "tools.raw_body_reader.on": True,
    }
    
    
    def __init__(self, debug = False):
        
        self.debug = debug
        
        # Alle mit *exposed* markierten Attribute/Methoden (ausgenommen die
        # *default*-Methode) dieser Klasse werden als JSON-RPC-Methoden markiert.
        # Weiters wird deren *exposed*-Flag entfernt.
        rpc_methods = {}
        for attribute_name in dir(self):
            if (
                not attribute_name.startswith("_") and 
                attribute_name != "default"
            ):
                item = getattr(self, attribute_name)
                if hasattr(item, "exposed") and item.exposed:
                    # Es handelt sich um eine mit exposed markierte Funktion
                    rpc_methods[attribute_name] = item
                    del item.__dict__["exposed"]
        self.rpc_methods = rpc_methods

    
    def default(self, *args, **kwargs):
        """
        Nimmt die JSON-RPC-Anfrage entgegen und übergibt sie an die entsprechende
        JSON-RPC-Methode.
        """
        
        responses = []
        
        # Response content type -> JSON
        set_content_type_json()
        
        # Get data
        if cherrypy.request.method == "GET":
            data = kwargs
            if "params" in data:
                if self.debug:
                    cherrypy.log("")
                    cherrypy.log(u"params (raw): " + repr(data["params"]))
                    cherrypy.log("")
                try:
                    data["params"] = json.loads(data["params"])
                except _ParseError, err:
                    traceback_info = "".join(traceback.format_exception(*sys.exc_info())) 
                    cherrypy.log(traceback_info)
                    return json.dumps(
                        ParseErrorResponse(
                            data = unicode(err)
                        ).to_dict()
                    )
            requests = [data]
        elif cherrypy.request.method == "POST":
            if self.debug:
                cherrypy.log("")
                cherrypy.log(u"cherrypy.request.raw_body:")
                cherrypy.log(repr(cherrypy.request.raw_body))
                cherrypy.log("")
            try:
                data = json.loads(cherrypy.request.raw_body)
            except _ParseError, err:
                traceback_info = "".join(traceback.format_exception(*sys.exc_info())) 
                cherrypy.log(traceback_info)
                return json.dumps(
                    ParseErrorResponse(
                        data = unicode(err)
                    ).to_dict()
                )
            if isinstance(data, list):
                requests = data
            else:
                requests = [data]
        else:
            raise cherrypy.HTTPError(
                status = httplib.BAD_REQUEST, 
                message = "Only GET or POST allowed"
            )
        
        # Every JSON-RPC request in a batch of requests
        for request in requests:
            
            # jsonrpc
            jsonrpc = request.get("jsonrpc")
            
            # method
            method = str(request.get("method", ""))
            
            # id
            id = request.get("id")

            # split positional and named params
            positional_params = []
            named_params = {}
            params = request.get("params", [])
            if isinstance(params, list):
                positional_params = params
            elif isinstance(params, dict):
                positional_params = params.get("__args", [])
                if positional_params:
                    del params["__args"]
                named_params = params
            
            # Debug
            if self.debug:
                cherrypy.log("")
                cherrypy.log(u"jsonrpc: " + repr(jsonrpc))
                cherrypy.log(u"request: " + repr(request))
                cherrypy.log(u"positional_params: " + repr(positional_params))
                cherrypy.log(u"named_params: " + repr(named_params))
                cherrypy.log(u"method: " + repr(method))
                cherrypy.log(u"id: " + repr(id))
                cherrypy.log("")
            
            # Do we know the method name?
            if not method in self.rpc_methods:
                traceback_info = "".join(traceback.format_exception(*sys.exc_info())) 
                cherrypy.log("JSON-RPC method '%s' not found" % method)
                responses.append(
                    MethodNotFoundResponse(jsonrpc = jsonrpc, id = id).to_dict()
                )
                continue
            
            # Call the method with parameters
            try:
                rpc_function = self.rpc_methods[method]
                result = rpc_function(*positional_params, **named_params)
                # No return value is OK if we donÂ´t have an ID (=notification)
                if result is None:
                    if id:
                        cherrypy.log("No result from JSON-RPC method '%s'" % method)
                        responses.append(
                            InternalErrorResponse(
                                jsonrpc = jsonrpc,
                                id = id,
                                data = u"No result from JSON-RPC method."
                            ).to_dict()
                        )
                else:
                    # Successful response
                    responses.append(
                        SuccessfulResponse(
                            jsonrpc = jsonrpc, id = id, result = result
                        ).to_dict()
                    )
            except TypeError, err:
                traceback_info = "".join(traceback.format_exception(*sys.exc_info())) 
                cherrypy.log(traceback_info)
                if "takes exactly" in unicode(err) and "arguments" in unicode(err):
                    responses.append(
                        InvalidParamsResponse(jsonrpc = jsonrpc, id = id).to_dict()
                    )
                else:
                    responses.append(
                        InternalErrorResponse(
                            jsonrpc = jsonrpc, 
                            id = id,
                            data = unicode(err)
                        ).to_dict()
                    )
            except BaseException, err:
                traceback_info = "".join(traceback.format_exception(*sys.exc_info())) 
                cherrypy.log(traceback_info)
                if hasattr(err, "data"):
                    error_data = err.data
                else:
                    error_data = None
                responses.append(
                    InternalErrorResponse(
                        jsonrpc = jsonrpc, 
                        id = id,
                        data = error_data or unicode(err)
                    ).to_dict()
                )
        
        # Return as JSON-String (batch or normal)
        if len(requests) == 1:
            return json.dumps(responses[0])
        elif len(requests) > 1:
            return json.dumps(responses)
        else:
            return None
    
    default.exposed = True









