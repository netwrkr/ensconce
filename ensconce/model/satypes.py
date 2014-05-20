import binascii
import json

from sqlalchemy import TypeDecorator, Text

class Json(TypeDecorator):

    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value
        
class SimpleList(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        if value == '':
            value = None
        if value is not None:
            if isinstance(value, (tuple, list)):
                value = ','.join(value)
        return value

    def process_result_value(self, value, dialect):
        if value == '':
            value = None
        if value is not None:
            value = value.split(',')
        return value
    
    
class HexEncodedBinary(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = binascii.hexlify(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = binascii.unhexlify(value)
        return value