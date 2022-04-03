import dill as pickle
import zmq


class Dummy(object):
    def query(*args, **kwargs):
        return ""


def sync_up_reply(sync_port: int, rpc_port: int, backend: str, version: str):
    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.ROUTER)
    try:
        socket.bind(f"tcp://*:{sync_port}")
        address, _, _ = socket.recv_multipart()
        reply = {
            "rpc_port": rpc_port,
            "backend": backend,
            "version": version,
        }
        socket.send_multipart([address, b"", pickle.dumps(reply)])
    finally:
        socket.close()
    return None


def recv_compare_and_reply(
    server: zmq.Socket, expected_msg: dict, reply_msg: dict
) -> bool:
    msg = pickle.loads(server.recv())
    if "args" in msg:
        msg["args"] = tuple(msg["args"])
    identical = msg == expected_msg
    server.send(pickle.dumps(reply_msg))
    return identical
