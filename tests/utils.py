import zmq
import msgpack


def recv_compare_and_reply(server: zmq.Socket,
                           expected_msg: dict,
                           reply_msg: dict) -> bool:
    msg = server.recv_serialized(msgpack.loads)
    identical = msg == expected_msg
    server.send_serialized(reply_msg, msgpack.dumps)
    return identical
