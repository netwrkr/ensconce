"""
This is a helper module that effectively configures the application at import time.

This exists for cherryd to be able to simply call `import ensconce.server_autoconfig`
and have cherrypy be fully configured (with default config file paths, etc) for serving.
"""
from ensconce import config
from ensconce import server

# Module-level initialization is deliberate here.  This should only ever be imported
# by cherryd.

config.init_app()
server.configure()