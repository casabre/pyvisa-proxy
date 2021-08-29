import argparse
import sys
import logging
from .PyVisaRemoteServer import PyVisaRemoteServer

LOGGER = logging.getLogger(__name__)


def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int,
                        dest='port',
                        default=5000,
                        help='Port for zmq localhost binding')
    return parser.parse_args(args)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s: %(message)s')
    args = parse_args(sys.argv[1:])
    with PyVisaRemoteServer(args.port) as server:
        server.run()
