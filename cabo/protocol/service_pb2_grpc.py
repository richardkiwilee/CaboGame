# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
import grpc

import cabo.protocol.service_pb2 as service__pb2


class CaboRoomStub(object):
  # missing associated documentation comment in .proto file
  pass

  def __init__(self, channel):
    """Constructor.

    Args:
      channel: A grpc.Channel.
    """
    self.Register = channel.unary_unary(
        '/cabo.CaboRoom/Register',
        request_serializer=service__pb2.GeneralRequest.SerializeToString,
        response_deserializer=service__pb2.GeneralResponse.FromString,
        )
    self.Handle = channel.unary_unary(
        '/cabo.CaboRoom/Handle',
        request_serializer=service__pb2.GeneralRequest.SerializeToString,
        response_deserializer=service__pb2.GeneralResponse.FromString,
        )
    self.Subscribe = channel.unary_stream(
        '/cabo.CaboRoom/Subscribe',
        request_serializer=service__pb2.GeneralRequest.SerializeToString,
        response_deserializer=service__pb2.Broadcast.FromString,
        )


class CaboRoomServicer(object):
  # missing associated documentation comment in .proto file
  pass

  def Register(self, request, context):
    # missing associated documentation comment in .proto file
    pass
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')

  def Handle(self, request, context):
    # missing associated documentation comment in .proto file
    pass
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')

  def Subscribe(self, request, context):
    # missing associated documentation comment in .proto file
    pass
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')


def add_CaboRoomServicer_to_server(servicer, server):
  rpc_method_handlers = {
      'Register': grpc.unary_unary_rpc_method_handler(
          servicer.Register,
          request_deserializer=service__pb2.GeneralRequest.FromString,
          response_serializer=service__pb2.GeneralResponse.SerializeToString,
      ),
      'Handle': grpc.unary_unary_rpc_method_handler(
          servicer.Handle,
          request_deserializer=service__pb2.GeneralRequest.FromString,
          response_serializer=service__pb2.GeneralResponse.SerializeToString,
      ),
      'Subscribe': grpc.unary_stream_rpc_method_handler(
          servicer.Subscribe,
          request_deserializer=service__pb2.GeneralRequest.FromString,
          response_serializer=service__pb2.Broadcast.SerializeToString,
      ),
  }
  generic_handler = grpc.method_handlers_generic_handler(
      'cabo.CaboRoom', rpc_method_handlers)
  server.add_generic_rpc_handlers((generic_handler,))
