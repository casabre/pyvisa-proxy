import cbor2 as cbor
import zmq


def recv_compare_and_reply(
    server: zmq.Socket, expected_msg: dict, reply_msg: dict
) -> bool:
    msg = cbor.loads(server.recv())
    if "args" in msg:
        msg["args"] = tuple(msg["args"])
    identical = msg == expected_msg
    server.send(cbor.dumps(reply_msg))
    return identical
