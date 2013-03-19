#!/usr/bin/env python

'''
Module holding three servers:
   1. Web server serving a fixed html file containing JavaScript for starting an event stream to clients.
   2. Server for anyone uploading a new JSON formatted EchoTree.
   3. Server to which browser based clients subscribe as server-sent stream recipients.
      This server pushes new EchoTrees as they arrive via (2.). The subscription is initiated
      by the served JavaScript (for example.)
For ports, see constants below.
'''

import os;
import sys;
import time;
import socket;
import argparse;
import datetime;
from threading import Event, Lock, Thread;

import tornado;
from tornado.ioloop import IOLoop;
from tornado.websocket import WebSocketHandler;
from tornado.httpserver import HTTPServer;

from echo_tree import WordExplorer;

HOST = socket.getfqdn();
ECHO_TREE_EXPERIMENT_SERVICE_PORT = 5004;
ECHO_TREE_EXPERIMENT_DISABLED_PORT = 5005;
ECHO_TREE_EXPERIMENT_PARTNER_PORT = 5006;

DISABLED_PAGE_NAME = "disabled.html";
PARTNER_PAGE_NAME = "partner.html";

#DBPATH = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/testDb.db");
DBPATH = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/EnronCollectionProcessed/EnronDB/enronDB.db");

# -----------------------------------------  Top Level Service Provider Classes --------------------

class EchoTreeLogService(WebSocketHandler):
    '''
    Handles interaction with dyads of users during experiment.
    Each instance handles one browser via a long-standing WebSocket
    connection.
    '''
    
    # Class-level list of handler instances: 
    activeHandlers = [];
    # Lock to make access to activeHanlders data struct thread safe:
    activeHandlersChangeLock = Lock();
    
    # Lock for changing the current EchoTree:
    currentEchoTreeLock = Lock();
    
    # Lock for changing the current EchoTree:
#    currentEchoTreeLock = Lock();
    
    # Log FD for logging. If None, calls to log() are ignored.
    # Else log to this FD (allowed to be sys.stdout for console:
    logFD = None;
    # If true, log to console, independently of logFD. If logFD is
    # provided (and not just sys.stdout), then logging occurs to
    # that FD *and* to the console. Else just to the concole:
    logToConsole = False;
    
    def __init__(self, application, request, **kwargs):
        '''
        Invoked when browser accesses this server via ws://...
        Register this handler instance in the handler list. 
        @param application: Application object that defines the collection of handlers.
        @type application: tornado.web.Application
        @param request: a request object holding details of the incoming request
        @type request:HTTPRequest.HTTPRequest
        @param kwargs: dict of additional parameters for operating this service.
        @type kwargs: dict
        '''
        super(EchoTreeLogService, self).__init__(application, request, **kwargs);
        self.request = request;
        EchoTreeLogService.log("Browser at %s (%s) subscribing to EchoTreeLogService." % (request.host, request.remote_ip));
        
        self.selfTest = [];
        
        # Register this handler instance as being an active
        # experiment logger:
        with EchoTreeLogService.activeHandlersChangeLock:
            EchoTreeLogService.activeHandlers.append(self);
    
    def allow_draft76(self):
        '''
        Allow WebSocket connections via the old Draft-76 protocol. It has some
        security issues, and was replaced. However, Safari (i.e. e.g. iPad) 
        don't implement the new protocols yet. Overriding this method, and 
        returning True will allow those connections.
        '''
        return True
    
    def open(self): #@ReservedAssignment
        '''
        Called by WebSocket/tornado when a client connects. Method must
        be named 'open'
        '''
        with EchoTreeLogService.currentEchoTreeLock:
            # Deliver the current tree to the subscribing browser:
            try:
                self.write_message("test");
                self.selfTest.append('sentMsgToPartner');
            except Exception as e:
                EchoTreeLogService.log("Error during send of current EchoTree to %s (%s) during initial subscription: %s" % (self.request.host, self.request.remote_ip, `e`));
        
    def on_message(self, message):
        '''
        Connected browser requests a new word:
        @param message: message arriving from the browser
        @type message: string
        '''
        subjectMsg = message.encode('utf-8');
        EchoTreeLogService.log("Message from participant: '%s'." % subjectMsg);
        if (len(subjectMsg) == 0):
            return;
        msgArr = subjectMsg.split(':');
        if (msgArr[0] == 'test'):
            self.selfTest.append('partnerSubjectResponded');
            return;
        if (msgArr[0] == 'addWord'):
            if (len(msgArr) < 2):
                return;
            word = msgArr[1];
            self.notifyInterestedParties("addWord:" + word, exceptions=[self]);
    
    def on_close(self):
        '''
        Called when socket is closed. Remove this handler from
        the list of handlers.
        '''
        with EchoTreeLogService.activeHandlersChangeLock:
            try:
                EchoTreeLogService.activeHandlers.remove(self);
            except:
                pass
        EchoTreeLogService.log("Browser at %s (%s) now disconnected." % (self.request.host, self.request.remote_ip));

    @staticmethod
    def log(theStr, addTimestamp=True):
        if EchoTreeLogService.logFD is None and not EchoTreeLogService.logToConsole:
            return;
        if addTimestamp:
            timestamp = str(datetime.datetime.now());
            # Write timestamp to log file if appropriate:
            if EchoTreeLogService.logFD is not None:
                EchoTreeLogService.logFD.write(timestamp + ": ");
            # Write timestamp to console, if appropriate:
            if EchoTreeLogService.logToConsole and EchoTreeLogService.logFD != sys.stdout:
                sys.stdout.write(timestamp + ': ');
        if EchoTreeLogService.logFD is not None:
            EchoTreeLogService.logFD.write(theStr + '\n');
            EchoTreeLogService.logFD.flush();
        if EchoTreeLogService.logToConsole and EchoTreeLogService.logFD != sys.stdout:
            sys.stdout.write(theStr + '\n');
    
    @staticmethod
    def notifyInterestedParties(msg, exceptions=[]):
        '''
        Called from other threads to send the given information
        to all registered parties, but not  itself.
        '''
        with EchoTreeLogService.activeHandlersChangeLock:
            for handler in EchoTreeLogService.activeHandlers:
                if (not handler in exceptions):
                    handler.write_message(msg);
                    EchoTreeLogService.log("Message to participant: " + msg);
    
# --------------------  Request Handler Class for browsers: serves HTML pages and javascript -------------------

class EchoTreeExperimentDisabledRequestHandler(HTTPServer):
    '''
    Web service serving an HTML page for the experiment 
    participant who plays the disabled person.
    '''

#    def _execute(self, transforms):
#        pass;

    @staticmethod
    def handle_request(request):
        '''
        Hangles the HTTP GET request.
        @param request: instance holding information about the request
        @type request: ???
        '''
        # Path to the HTML page we serve. Should probably just load that once, but
        # this request is not frequent. 
        scriptPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 
                                  "../browser_scripts/" + DISABLED_PAGE_NAME);
        # Create the response and the HTML page string:
        reply =  "HTTP/1.1 200 OK\r\n" +\
                 "Content-type, text/html\r\n" +\
                 "Content-Length:%s\r\n" % os.path.getsize(scriptPath) +\
                 "Last-Modified:%s\r\n" % time.ctime(os.path.getmtime(scriptPath)) +\
                 "\r\n";
        # Add the HTML page to the header:
        with open(scriptPath) as fileFD:
            for line in fileFD:
                reply += line;
        request.write(reply);
        request.finish();
        
        
# --------------------  Request Handler Class for browsers requesting the JavaScript that knows to open a disabled or partner connection ---------------

class EchoTreeExperimentPartnerRequestHandler(HTTPServer):
    '''
    Web service serving an HTML page for the experiment 
    participant who plays the partner person.
    '''

#    def _execute(self, transforms):
#        pass;

    @staticmethod
    def handle_request(request):
        '''
        Hangles the HTTP GET request.
        @param request: instance holding information about the request
        @type request: ???
        '''
        # Path to the HTML page we serve. Should probably just load that once, but
        # this request is not frequent. 
        scriptPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 
                                  "../browser_scripts/" + PARTNER_PAGE_NAME);
        # Create the response and the HTML page string:
        reply =  "HTTP/1.1 200 OK\r\n" +\
                 "Content-type, text/html\r\n" +\
                 "Content-Length:%s\r\n" % os.path.getsize(scriptPath) +\
                 "Last-Modified:%s\r\n" % time.ctime(os.path.getmtime(scriptPath)) +\
                 "\r\n";
        # Add the HTML page to the header:
        with open(scriptPath) as fileFD:
            for line in fileFD:
                reply += line;
        request.write(reply);
        request.finish();
        
        
# --------------------  Helper class for spawning the services in their own threads ---------------
                
class SocketServerThreadStarter(Thread):
    '''
    Used to fire up the three services each in its own thread.
    '''
    
    def __init__(self, socketServerClassName, port):
        '''
        Create one thread for one of the services to run in.
        @param socketServerClassName: Name of top level server class to run.
        @type socketServerClassName: string
        @param port: port to listen on
        @type port: int
        '''
        super(SocketServerThreadStarter, self).__init__();
        self.socketServerClassName = socketServerClassName;
        self.port = port;
        self.ioLoop = None;

    def stop(self):
        self.ioLoop.stop();
       
    def run(self):
        '''
        Use the service name to instantiate the proper service, passing in the
        proper helper class.
        '''
        super(SocketServerThreadStarter, self).run();
        try:
            if  self.socketServerClassName == 'EchoTreeExperimentPartnerRequestHandler':
                EchoTreeLogService.log("Starting EchoTree page server %d: Returns page for the 'partner' participant." % self.port);
                http_server = EchoTreeExperimentPartnerRequestHandler(EchoTreeExperimentPartnerRequestHandler.handle_request);
                http_server.listen(self.port);
                self.ioLoop = IOLoop();
                self.ioLoop.start();
                self.ioLoop.close(all_fds=True);
                return;
            elif self.socketServerClassName == 'EchoTreeExperimentDisabledRequestHandler':
                EchoTreeLogService.log("Starting EchoTree page server %d: Returns page for the 'disabled' participant." % self.port);
                http_server = EchoTreeExperimentDisabledRequestHandler(EchoTreeExperimentDisabledRequestHandler.handle_request);
                http_server.listen(self.port);
                self.ioLoop = IOLoop();
                self.ioLoop.start();
                self.ioLoop.close(all_fds=True);
                return;
            else:
                raise ValueError("Service class %s is unknown." % self.socketServerClassName);
        except Exception:
            # Typically an exception is caught here that complains about 'socket in use'
            # Should avoid that by sensing busy socket and timing out:
#            if e.errno == 98:
#                print "Exception: %s. You need to try starting this service again. Socket busy condition will time out within 30 secs or so." % `e`
#            else:
#                print `e`;
            #raise e;
            pass
        finally:
            if self.ioLoop is not None and self.ioLoop.running():
                self.ioLoop.stop();
                return;


if __name__ == '__main__':

    parser = argparse.ArgumentParser(prog='echo_tree_server')
    parser.add_argument("-l", "--logFile, help=fully qualified log file name. Default: no logging.", dest='logFile');
    parser.add_argument("-v", "--verbose, help=print operational info to console.", 
                        dest='verbose',
                        action='store_true');
    
    
    args = parser.parse_args();
    if args.logFile is not None:
        try:
            EchoTreeLogService.logFD = open(args.logFile, 'w');
        except IOError, e:
            print "Cannot open log file '%s' for writing. Server not started." % args.logFile;
            sys.exit();
    
    if args.verbose:
        EchoTreeLogService.logToConsole = True;

    # Service that coordinates traffice among all active participants:                                   
    EchoTreeLogService.log("Starting EchoTree experiment server at port %s: . Interacts with participants." % "/echo_tree_experiment");
    application = tornado.web.Application([(r"/echo_tree_experiment", EchoTreeLogService),                                           
                                           ]);
    # Create the service that serves out the 'disabled' participant's Web page:
    #EchoTreeLogService.log('Starting EchoTree experiment for disabled participant page at port %d' % ECHO_TREE_EXPERIMENT_DISABLED_PORT);
    disabledServer = SocketServerThreadStarter('EchoTreeExperimentDisabledRequestHandler', ECHO_TREE_EXPERIMENT_DISABLED_PORT); 
    disabledServer.start();
                                           
    # Create the service that serves out the 'partner' participant's Web page:
    #EchoTreeLogService.log('Starting EchoTree experiment for partner participant page at port %d' % ECHO_TREE_EXPERIMENT_PARTNER_PORT);
    partnerServer = SocketServerThreadStarter('EchoTreeExperimentPartnerRequestHandler', ECHO_TREE_EXPERIMENT_PARTNER_PORT); 
    partnerServer.start();
                                           
    application.listen(ECHO_TREE_EXPERIMENT_SERVICE_PORT);
    
    try:
        ioLoop = IOLoop.instance();
        try:
            ioLoop.start()
            ioLoop.close(all_fds=True);
        except Exception, e:
            ioLoop.stop();
            if e.__class__ == KeyboardInterrupt:
                raise e;
    except KeyboardInterrupt:
        EchoTreeLogService.log("Stopping EchoTree experiment server...");
        if ioLoop.running():
            ioLoop.stop();
        disabledServer.stop();
        partnerServer.stop();
        EchoTreeLogService.log("EchoTree experiment server stopped.");
        if EchoTreeLogService.logFD is not None:
            EchoTreeLogService.logFD.close();
        os._exit(0);
        