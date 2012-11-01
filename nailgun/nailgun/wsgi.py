import os
import sys
import web
import logging
import logging.config

curdir = os.path.dirname(__file__)
sys.path.insert(0, curdir)

from nailgun.settings import settings
from nailgun.api.handlers import check_client_content_type
from nailgun.db import load_db_driver
from nailgun.urls import urls

app = web.application(urls, locals())
app.add_processor(load_db_driver)
#app.add_processor(check_client_content_type)


class FlushingLogger(object):
    def __init__(self):
        self.opened = False
        self.fd = None

    @property
    def _fd(self):
        if not self.opened:
            self.fd = open(settings.ACCESS_LOG, "a+")
            self.opened = True
        return self.fd

    def __enter__(self):
        return self._fd

    def __exit__(self, type, value, traceback):
        self._fd.close()
        self.opened = False

    def write(self, data):
        self._fd.write(data)
        self._fd.flush()

    def close(self):
        self._fd.close()
        self.opened = False


def appstart():
    from nailgun.rpc import threaded
    import eventlet
    from eventlet import wsgi
    eventlet.monkey_patch()
    q = threaded.rpc_queue
    rpc_thread = threaded.RPCThread()

    try:
        rpc_thread.start()
        wsgi.server(
            eventlet.listen(
                (
                    settings.LISTEN_ADDRESS,
                    int(settings.LISTEN_PORT)
                )
            ),
            app.wsgifunc(),
            log=FlushingLogger()
        )
    except KeyboardInterrupt:
        logger.info("Stopping RPC thread...")
        rpc_thread.running = False
        logger.info("Stopping WSGI app...")
        server.stop()
        logger.info("Done")


application = app.wsgifunc()
