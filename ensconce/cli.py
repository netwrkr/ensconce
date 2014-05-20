import sys
import optparse

from ensconce.config import init_app, config
from ensconce import server

def run_server(argv=None):
    if argv is None:
        argv = sys.argv
        
    parser = optparse.OptionParser(description='Run the ensconce cherrypy server.')
    init_app()
    
    parser.add_option('-d', '--debug',
                      default=config.get('debug', False),
                      action="store_true",
                      help='Run in debug mode?')
    
    (options, args) = parser.parse_args()
    
    config['debug'] = options.debug
    server.configure()
    server.serve_forever()