# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: POGOProtos/Networking/Responses/DownloadSettingsResponse.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from POGOProtos.Settings import GlobalSettings_pb2 as POGOProtos_dot_Settings_dot_GlobalSettings__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='POGOProtos/Networking/Responses/DownloadSettingsResponse.proto',
  package='POGOProtos.Networking.Responses',
  syntax='proto3',
  serialized_pb=_b('\n>POGOProtos/Networking/Responses/DownloadSettingsResponse.proto\x12\x1fPOGOProtos.Networking.Responses\x1a(POGOProtos/Settings/GlobalSettings.proto\"n\n\x18\x44ownloadSettingsResponse\x12\r\n\x05\x65rror\x18\x01 \x01(\t\x12\x0c\n\x04hash\x18\x02 \x01(\t\x12\x35\n\x08settings\x18\x03 \x01(\x0b\x32#.POGOProtos.Settings.GlobalSettingsb\x06proto3')
  ,
  dependencies=[POGOProtos_dot_Settings_dot_GlobalSettings__pb2.DESCRIPTOR,])
_sym_db.RegisterFileDescriptor(DESCRIPTOR)




_DOWNLOADSETTINGSRESPONSE = _descriptor.Descriptor(
  name='DownloadSettingsResponse',
  full_name='POGOProtos.Networking.Responses.DownloadSettingsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='error', full_name='POGOProtos.Networking.Responses.DownloadSettingsResponse.error', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='hash', full_name='POGOProtos.Networking.Responses.DownloadSettingsResponse.hash', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='settings', full_name='POGOProtos.Networking.Responses.DownloadSettingsResponse.settings', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=141,
  serialized_end=251,
)

_DOWNLOADSETTINGSRESPONSE.fields_by_name['settings'].message_type = POGOProtos_dot_Settings_dot_GlobalSettings__pb2._GLOBALSETTINGS
DESCRIPTOR.message_types_by_name['DownloadSettingsResponse'] = _DOWNLOADSETTINGSRESPONSE

DownloadSettingsResponse = _reflection.GeneratedProtocolMessageType('DownloadSettingsResponse', (_message.Message,), dict(
  DESCRIPTOR = _DOWNLOADSETTINGSRESPONSE,
  __module__ = 'POGOProtos.Networking.Responses.DownloadSettingsResponse_pb2'
  # @@protoc_insertion_point(class_scope:POGOProtos.Networking.Responses.DownloadSettingsResponse)
  ))
_sym_db.RegisterMessage(DownloadSettingsResponse)


# @@protoc_insertion_point(module_scope)
