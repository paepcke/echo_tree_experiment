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
import threading;
import json;
import Queue;
from threading import Event, Lock, Thread;

import tornado;
from tornado.ioloop import IOLoop;
from tornado.websocket import WebSocketHandler;
from tornado.httpserver import HTTPServer;

from echo_tree import WordExplorer;

HOST = socket.getfqdn();
ECHO_TREE_GET_PORT = 5005;

#DBPATH = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/testDb.db");
#DBPATH = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/EnronCollectionProcessed/EnronDB/enronDB.db");
scriptDir = os.path.realpath(os.path.dirname(__file__)); 
DBPATH_DMOZ_RECREATION = os.path.join(scriptDir, "Resources/dmozRecreation.db");
DBPATH_GOOGLE = os.path.join(scriptDir, "Resources/google.db");

NEW_TREE_SUBMISSION_URI_PATH = r"/submit_new_echo_tree";
ECHO_TREE_SUBSCRIBE_PATH = "r/subscribe_to_echo_trees";

# Name of script to serve on ECHO_TREE_SCRIPT_SERVER_PORT. 
# Fixed script intended to subscribe to the EchoTree event server: 
TREE_EVENT_LISTEN_SCRIPT_NAME = "wordTreeListener.html";

# -----------------------------------------  Class TreeContainer --------------------

class TreeContainer(object):
    
    # Paths to all underlying ngram DBs. Key is tree type name,
    # like 'google', or 'dmozRecreation':
    ngramPaths = {};
    
    def __init__(self, submitter, treeTypeName):
        self.treeTypeName = treeTypeName;
        self.theCurrentTree = None;
        self.theCurrentRootWord = None;
        self.treeLock = Lock();
        self.theSubscribers = [];
        self.theOwner = submitter;

    def currentRootWord(self):
        return self.theCurrentRootWord;
    
    def setCurrentRootWord(self, newWord):
        self.theCurrentRootWord = newWord;

    def currentTree(self):
        return self.theCurrentTree;
        
    def setCurrentTree(self, newTree):
        with self.treeLock:
            self.theCurrentTree = newTree;
            
    def owner(self):
        return self.theOwner;

    def addSubscriber(self, newSubscriberID):
        self.theSubscribers.append(newSubscriberID);

    def subscribers(self):
        return self.theSubscribers;

    def isSubscribed(self, subscriberID):
        try:
            self.subscribers().index(subscriberID);
            return True;
        except ValueError:
            return False;

    def treeType(self):
        return self.treeTypeName;

    @staticmethod
    def treeTypeNames():
        return TreeContainer.ngramPaths.keys();
    
    @staticmethod
    def ngramPath(treeTypeName):
        try:
            return TreeContainer.ngramPaths[treeTypeName];
        except KeyError:
            return None;

    @staticmethod
    def addTreeType(typeName, ngramPath):
        TreeContainer.ngramPaths[typeName] = ngramPath;

# -----------------------------------------  Event 'subclass' that adds event flavors --------------------

class FlavoredEvent():
    '''
    Semantically a subclass of Threading.Event, which allows events of multiple
    types controlled by a single event flag. Each set() is a
    setting of the flag for one flavor. The wait() method is
    not overridden, so the setting of any flavor will wake a
    thread that is waiting for the event instance. The method
    hotFlavors() can then be used to service all flavors, or 
    just an individual one. Method clear() clears the flag for
    just one flavor at a time.
    '''
    
    def __init__(self):
        super(FlavoredEvent, self).__init__();
        self.eventFlag = Event();
        self.flavorsLock = Lock();
        self.flavors = {}
        
    def set(self, flavor):
        '''
        Set this event flag for one flavor.
        @param flavor: Any object that can be used as a dictionary key.
        @type flavor: Object
        '''
        with self.flavorsLock:
            self.flavors[flavor] = True;
        self.eventFlag.set();
        
    def clear(self, flavor):
        '''
        Clear this event flag for the given flavor.
        @param flavor: Any object that can be used as a dictionary key.
        @type flavor: Object
        '''
        with self.flavorsLock:
            self.flavors[flavor] = False;
        self.eventFlag.clear();

    def hotFlavors(self):
        '''
        Return an array of all flavor objects that are currently True.
        @return: array of flavors that have been set via set().
        @rtype: [Object]
        '''
        hotFlavors = [];
        with self.flavorsLock:
            for flavor in self.flavors.keys():
                if self.flavors[flavor]:
                    hotFlavors.append(flavor);
        return hotFlavors;



# -----------------------------------------  Top Level Service Provider Classes --------------------

class EchoTreeService(WebSocketHandler):
    '''
    Handles pushing new EchoTrees to browsers who display them.
    Each instance handles one browser via a long-standing WebSocket
    connection.
    '''
    
    activeHandlers = [];
    
    # Dict mapping subscriber names to tree containers that
    # hold trees from one particular person.
    treeContainers = {};
    
    # Queue into which a newly changed TreeContainer instance 
    # will be placed after its EchoTree was updated for
    # a new root word.
    # Thread NewEchoTreeWaitThread will hang on this queue:
    newEchoTreeQueue = Queue.Queue();
        
    # Class-level dict of handler instances that are 
    # related by interest in their trees. Keys are experiment
    # participant IDs. Values are arrays of handlers that are
    # to be notified whenever the participant indicated in 
    # the key generates a new tree by submitting a new root:
    subscribingHandlers = {};
    
    # Lock to make access to activeHanlders data struct thread safe:
    activeHandlersChangeLock = Lock();
    
    # Current JSON EchoTree string:
    currentEchoTree = "";
    
    # Lock for changing the current EchoTree:
    currentEchoTreeLock = Lock();
    
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
        super(EchoTreeService, self).__init__(application, request, **kwargs);
        self.request = request;
        EchoTreeService.log("Browser at %s (%s) subscribing to EchoTrees." % (request.host, request.remote_ip));
        
        # Register this handler instance as wishing to hear
        # about new incoming EchoTrees:
        with EchoTreeService.activeHandlersChangeLock:
            EchoTreeService.activeHandlers.append(self);

        # Start thread that waits for new root words and computes the respective tree:
        EchoTreeService.log('Starting TreeComputer thread on port %d. It waits for new root words from browsers, and computes a corresponding tree.' % ECHO_TREE_NEW_ROOT_PORT);
        EchoTreeService.TreeComputer().start();
        
        # Start thread that waits for a newly computed tree,
        # and sends it to all subscribers:
        EchoTreeService.NewEchoTreeWaitThread(self).start();
    
#    def subscribeToNewTrees(self, handler):
#        with EchoTreeService.activeHandlersChangeLock:
#            EchoTreeService.activeHandlers.append(handler);
    
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
        pass
#        with EchoTreeService.currentEchoTreeLock:
#            # Deliver the current tree to the subscribing browser:
#            try:
#                self.write_message(EchoTreeService.currentEchoTree); #***********
#            except Exception as e:
#                EchoTreeService.log("Error during send of current EchoTree to %s (%s) during initial subscription: %s" % (self.request.host, self.request.remote_ip, `e`));
        
    
    def on_message(self, message):
        '''
        Connected browser submits a request. Possible requests are:
           - push a new root word. Message will be a 
                JSON structure that decodes into dict like this: 
                {'command':'newRootWord', 'submitter':<submitterIDStr>, 'word':<wordStr>, 'treeType':<treeTypeNameStr}
           - subscribe to another player's echo trees of a particular type:
                JSON structure that decodes into dict like this: 
                {'command':'subscribe', 'submitter':<submitterIDStr>, 'subscriber':<subscriberIDOfEchoTreeCreatorStr>, 'treeType':<treeTypeNameStr}
        @param message: message arriving from the browser
        @type message: string
        '''
        encodedMsg = message.encode('utf-8');
        msgDict = json.loads(encodedMsg);
        try:
            cmd = msgDict['command'];
        except KeyError:
            EchoTreeService.log("Ill-formed request from browser: no 'command' field: '%s'." % encodedMsg);
            return;
        
        if cmd == 'newRootWord':        
            try:
                submitter = msgDict['submitter'];
                newRootWord = msgDict['word'];
                treeType = msgDict['treeType'];
            except KeyError:
                EchoTreeService.log("Ill-formed root word submission message from browser: " + encodedMsg);
                return;

            # Does this submitter already have a container for its trees
            # of this type?
            container = self.getTreeContainer(submitter, treeType);
            if container is None:
                container = TreeContainer(submitter, treeType);
                try:
                    EchoTreeService.treeContainers[submitter].append(container);
                except KeyError:
                    EchoTreeService.treeContainers[submitter] = [container];
                # Everyone is a subscriber to their own tree:
                container.addSubscriber(submitter);
    
            EchoTreeService.triggerTreeComputationAndDistrib(container, newRootWord);
            EchoTreeService.log("New root word from connected browser: '%s': '%s'" % (submitter,newRootWord));
            
        elif cmd == 'subscribe':
            try:
                submitter = msgDict['submitter'];
                treeCreator = msgDict['treeCreator'];
                treeType = msgDict['treeType'];
            except KeyError:
                EchoTreeService.log("Ill-formed root word submission message from browser: " + encodedMsg);
                
            # Try to find the tree creator's TreeContainer instances:
            try:
                treeContainersForTreeCreator = EchoTreeService.treeContainers[treeCreator];
            except KeyError:
                # the creator to whom the caller is trying to subscribe
                # does not have a TreeContainer instance for any tree type.
                EchoTreeService.log("Request from %s subscribing to %s for tree type %s. But %s has no tree containers at all." % (str(submitter),str(treeCreator), str(treeType),str(treeCreator)));
                return;
            # Found an array of tree containers for the specified treeCreator.
            # But does that creator deal with the specified tree type?
            foundIt = False;
            for container in treeContainersForTreeCreator:
                if container.treeType() == treeType:
                    foundIt = True;
                    break;
            if not foundIt:
                EchoTreeService.log("Request from %s subscribing to %s for tree type %s. But %s has no such tree type" % (str(submitter),str(treeType),str(treeCreator)));
                return;
            container.addSubscriber(submitter);
                
        else:
            EchoTreeService.log("Unsupported command %s in request %s." % (cmd, encodedMsg));
            return;
    
    def on_close(self):
        '''
        Called when socket is closed. Remove this handler from
        the list of handlers.
        '''
        with EchoTreeService.activeHandlersChangeLock:
            try:
                EchoTreeService.activeHandlers.remove(self);
            except:
                pass
        EchoTreeService.log("Browser at %s (%s) now disconnected." % (self.request.host, self.request.remote_ip));

    @staticmethod
    def log(theStr, addTimestamp=True):
        if EchoTreeService.logFD is None and not EchoTreeService.logToConsole:
            return;
        if addTimestamp:
            timestamp = str(datetime.datetime.now());
            # Write timestamp to log file if appropriate:
            if EchoTreeService.logFD is not None:
                EchoTreeService.logFD.write(timestamp + ": ");
            # Write timestamp to console, if appropriate:
            if EchoTreeService.logToConsole and EchoTreeService.logFD != sys.stdout:
                sys.stdout.write(timestamp + ': ');
        if EchoTreeService.logFD is not None:
            EchoTreeService.logFD.write(theStr + '\n');
            EchoTreeService.logFD.flush();
        if EchoTreeService.logToConsole and EchoTreeService.logFD != sys.stdout:
            sys.stdout.write(theStr + '\n');
        
    
    @staticmethod
    def notifyInterestedParties(treeContainer):
        '''
        Called from other threads to set the new-EchoTree-arrived event flags
        for all instances of EchoTreeService.  
        '''
        EchoTreeService.newEchoTreeQueue.put(treeContainer);
#        with EchoTreeService.activeHandlersChangeLock:
#            for handler in EchoTreeService.activeHandlers: #************
#                handler.newEchoTreeEvent.set();

    def getTreeContainer(self, submitterID, treeType):
        try:
            containerArr = EchoTreeService.treeContainers[submitterID];
        except KeyError:
            return None;

        for container in containerArr:
            if container.treeType() == treeType:
                return container;
        return None;

    class NewEchoTreeWaitThread(Thread):
        '''
        Thread that waits for a new EchoTree to have been created.
        It then sends that tree to the browser to which it is dedicated.
        The handler that communicates with that browser is passed into
        the init method. A new thread is started for each EchoTreeService
        connection that is made from some browser:
        '''
        
        def __init__(self, handlerObj):
            '''
            Init thread
            @param handlerObj: instance of EchoTreeService.
            @type handlerObj: EchoTreeService.
            '''
            super(EchoTreeService.NewEchoTreeWaitThread, self).__init__();
            self.handlerObj = handlerObj
            EchoTreeService.log("Starting NewEchoTreeWait thread: sends any newly computed EchoTrees to its the connected browser.");
        
        def run(self):
            while 1:
                # Hang on new-EchoTree event:
                modifiedContainer = EchoTreeService.newEchoTreeQueue.get();
                with EchoTreeService.currentEchoTreeLock:
                    # Deliver the new tree to the browser:
                    try:
                        #***************** Must only send if self is subscribed!
                        self.handlerObj.write_message(modifiedContainer.currentTree());
                    except Exception as e:
                        EchoTreeService.log("Error during send of new EchoTree to %s (%s): %s" % (self.handlerObj.request.host, self.handlerObj.request.remote_ip, `e`));
    
    @staticmethod
    def triggerTreeComputationAndDistrib(treeContainer, newRootWord):
        if newRootWord == treeContainer.currentRootWord():
            return;
        treeContainer.setCurrentRootWord(newRootWord);
        EchoTreeService.TreeComputer.workQueue.put(treeContainer);
        
    class TreeComputer(Thread):
        '''
        Waits for newWordEvent. Creates a new EchoTree from the root word that
        it EchoTreeService.TreeComputer. Calls notifyInterestedParties
        to distribute the new tree to relevant connected browsers.
        '''
        
        rootWord = None;
        keepRunning = True;
        singletonRunning = False;
        wordExplorers = {};
        # Tree containers with new root words waiting to have
        # their tree re-computed:
        workQueue = Queue.Queue();
        
        def __init__(self):
            super(EchoTreeService.TreeComputer, self).__init__();
            if EchoTreeService.TreeComputer.singletonRunning:
                raise RuntimeError("Only one TreeComputer instance may run per process.");
            EchoTreeService.TreeComputer.singletonRunning = True;
        
        def stop(self):
            EchoTreeService.TreeComputer.keepRunning = False;
        
        def run(self):
            # Make one tree manufacturer for each tree type (i.e. for each
            # ngram database):
            for treeType in TreeContainer.treeTypeNames():
                EchoTreeService.TreeComputer.wordExplorers[treeType] = WordExplorer(TreeContainer.ngramPath(treeType));

            while EchoTreeService.TreeComputer.keepRunning:
                treeContainerToProcess = EchoTreeService.TreeComputer.workQueue.get();
                
                try:
                    properWordExplorer = EchoTreeService.TreeComputer.wordExplorers[treeContainerToProcess.treeType()];
                except KeyError:
                    # Non-existing tree type passed in the container:
                    EchoTreeService.log("Non-existent tree type passed TreeComputer thread: " + str(treeContainerToProcess.treeType()));
                    continue;
                newJSONEchoTreeStr = properWordExplorer.makeJSONTree(properWordExplorer.makeWordTree(treeContainerToProcess.currentRootWord()));
                treeContainerToProcess.setCurrentTree(newJSONEchoTreeStr);
                
                # Signal to the new-tree-arrived event pushers that a new
                # jsonTree has arrived, and they should push it to their clients:
                EchoTreeService.notifyInterestedParties(treeContainerToProcess);
                #EchoTreeService.log(RootWordSubmissionService.TreeComputer.rootWord);
                #EchoTreeService.log(newJSONEchoTreeStr);
        
# --------------------  Request Handler Class for browsers requesting the JavaScript that knows to open an EchoTreeService connection ---------------

class EchoTreeScriptRequestHandler(HTTPServer):
    '''
    Web service serving a single JavaScript containing HTML page.
    That page contains instructions for requesting an event stream for
    new EchoTree instances from this server.
    '''

#    def _execute(self, transforms):
#        pass;

    @staticmethod
    def handle_request(request):
        '''
        Handles the HTTP GET request.
        @param request: instance holding information about the request
        @type request: ???
        '''
        # Path to the HTML page we serve. Should probably just load that once, but
        # this request is not frequent. 
        scriptPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../browser_scripts/" + TREE_EVENT_LISTEN_SCRIPT_NAME);
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
            if self.socketServerClassName == 'EchoTreeScriptRequestHandler':
                EchoTreeService.log("Starting EchoTree script server %d: Returns one script that listens to the new-tree events in the browser." % self.port);
                http_server = EchoTreeScriptRequestHandler(EchoTreeScriptRequestHandler.handle_request);
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
            EchoTreeService.logFD = open(args.logFile, 'w');
        except IOError, e:
            print "Cannot open log file '%s' for writing. Server not started." % args.logFile;
            sys.exit();
    
    if args.verbose:
        EchoTreeService.logToConsole = True;

    # Create the different types of EchoTrees, each based on a different
    # underlying ngram collection:
    TreeContainer.addTreeType("dmozRecreation", DBPATH_DMOZ_RECREATION);
    TreeContainer.addTreeType("google", DBPATH_GOOGLE);
    
    EchoTreeService.log("Starting EchoTree server at port %s: pushes new word trees to all connecting clients." %
                         (str(ECHO_TREE_GET_PORT) + ":/subscribe_to_echo_trees"));
    application = tornado.web.Application([(r"/subscribe_to_echo_trees", EchoTreeService),
                                           ]);
                                           
    application.listen(ECHO_TREE_GET_PORT);
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
        EchoTreeService.log("Stopping EchoTree servers...");
        if ioLoop.running():
            ioLoop.stop();
        EchoTreeService.NewEchoTreeWaitThread.stop();
        EchoTreeService.TreeComputer.stop();
#        treeComputerThread.stop();
        EchoTreeService.log("EchoTree servers stopped.");
        if EchoTreeService.logFD is not None:
            EchoTreeService.logFD.close();
        os._exit(0);
        