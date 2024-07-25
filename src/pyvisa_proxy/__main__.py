"""Run PyVISA-proxy server as service.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""

import logging
import sys

from ._main import main, parse_arguments

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s"
    )
    args = parse_arguments(sys.argv[1:])
    main(args.port, args.rpc_port, args.backend)
