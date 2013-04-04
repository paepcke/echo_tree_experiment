#!/usr/bin/env python

'''
Module listens for two messages:
   1. the root word for a new echo tree to create (newRootWord)
   2. request to subscribe to a particular tree type by a particular contributor (subscribe)
   
For port, see constants below.
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

ECHO_TREE_SUBSCRIBE_PATH = "r/subscribe_to_echo_trees";

# Name of script to serve on ECHO_TREE_SCRIPT_SERVER_PORT. 
# Fixed script intended to subscribe to the EchoTree event server: 
TREE_EVENT_LISTEN_SCRIPT_NAME = "wordTreeListener.html";

class TreeTypes:
    RECREATION_NGRAMS = 'dmozRecreation';
    GOOGLE_NGRAMS     = 'googleNgrams';

# -----------------------------------------  Class TreeContainer --------------------

class TreeContainer(object):
    '''
    Container objects that hold information about one EchoTree.
    The objects contain the tree itself, the root word, the type
    of tree (i.e. underlying model that generated the tree), 
    and subscriber IDs of parties interested in notifications
    of tree changes in this container.
    '''
    
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

    def addSubscriber(self, newSubscriberID, handler):
        self.theSubscribers.append(newSubscriberID);
        with EchoTreeService.activeHandlersChangeLock:
            try:
                subscribedToHandlers =  EchoTreeService.activeHandlers[newSubscriberID];
                # Add the new handler, if it's not alreay in the array,
                # in which case we get the ValueError:
                try:
                    subscribedToHandlers.index(handler);
                except ValueError:
                    subscribedToHandlers.append(handler);
            except KeyError:
                # This subscriber is not subscribed to anything yet:
                EchoTreeService.activeHandlers[newSubscriberID] = [handler];

    def removeSubscriber(self, subscriberID):
        with EchoTreeService.activeHandlersChangeLock:
            del EchoTreeService.activeHandlers[subscriberID];

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


# -----------------------------------------  Top Level Service Provider Classes --------------------

class EchoTreeService(WebSocketHandler):
    '''
    Handles pushing new EchoTrees to browsers who display them.
    Each instance handles one browser via a long-standing WebSocket
    connection.
    '''
    
    # Keys: subscriberID, values: we sockets through which
    # to communicate to that subscriber:
    activeHandlers = {};
    
    # Dict mapping subscriber names to tree containers that
    # hold trees from one particular person.
    treeContainers = {};
    
    # Queue into which a newly changed TreeContainer instance 
    # will be placed after its EchoTree was updated for
    # a new root word.
    # Thread NewEchoTreeWaitThread will hang on this queue:
    newEchoTreeQueue = Queue.Queue();
        
    # Lock to make access to activeHanlders data struct thread safe:
    activeHandlersChangeLock = Lock();
    
    # Current JSON EchoTree string:
    currentEchoTree = "";
    
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
        self.myID = None; # Set as soon as one request comes in from this handler instantiation
        EchoTreeService.log("Browser at %s (%s) subscribing to EchoTrees." % (request.host, request.remote_ip));
        
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
            # In case we didn't know before: now we know the ID of
            # this handler's browser:
            self.myID = submitter;

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
                container.addSubscriber(submitter, self);
    
            EchoTreeService.triggerTreeComputationAndDistrib(container, newRootWord);
            EchoTreeService.log("New root word from connected browser: '%s': '%s'" % (submitter,newRootWord));
            
        elif cmd == 'subscribe':
            try:
                submitter = msgDict['submitter'];
                treeCreator = msgDict['treeCreator'];
                treeType = msgDict['treeType'];
            except KeyError:
                EchoTreeService.log("Ill-formed root word submission message from browser: " + encodedMsg);
                return;
            # In case we didn't know before: now we know the ID of
            # this handler's browser:
            self.myID = submitter;
                
            # Try to find the tree creator's TreeContainer instances:
            try:
                treeContainersForTreeCreator = EchoTreeService.treeContainers[treeCreator];
            except KeyError:
                # the creator to whom the caller is trying to subscribe
                # does not have a TreeContainer instance for any tree type.
                # Create one, with None for the current tree:
                EchoTreeService.treeContainers[treeCreator] = [TreeContainer(treeCreator, treeType)];
                treeContainersForTreeCreator = EchoTreeService.treeContainers[treeCreator];
                #EchoTreeService.log("Error: Request from %s subscribing to %s for tree type %s. But %s has no tree containers at all." % (str(submitter),str(treeCreator), str(treeType),str(treeCreator)));
                #return;
            # Found an array of tree containers for the specified treeCreator.
            # But does that creator deal with the specified tree type?
            foundIt = False;
            for container in treeContainersForTreeCreator:
                if container.treeType() == treeType:
                    foundIt = True;
                    break;
            if not foundIt:
                EchoTreeService.log("Request from %s subscribing to %s for tree type %s. But %s has no such tree type" % (str(submitter),
                                                                                                                          str(treeCreator),
                                                                                                                          str(treeType),
                                                                                                                          str(treeCreator)));
                return;
            container.addSubscriber(submitter, self);
                
        else:
            EchoTreeService.log("Unsupported command %s in request %s." % (cmd, encodedMsg));
            return;
    
    def on_close(self):
        '''
        Called when socket is closed. Update bookkeeping data structures.
        '''
        # Remove this handler from all lists of handlers.
        with EchoTreeService.activeHandlersChangeLock:
            for subscriberID, handlerArr in EchoTreeService.activeHandlers.items():
                try:
                    # Try to remove this handler from the subscriber's list of 
                    # subscribed-to handlers:
                    handlerArr.remove(self);
                    # This (closing) handler was subscribed to; remnoval succeeded.
                    # If this was the last handler this subscriber was subscribed
                    # to, remove the subscriber's entry from the dict:
                    if len(handlerArr) == 0:
                        del EchoTreeService.activeHandlers[subscriberID];
                except ValueError:
                    # that subscriber was not subscribed to this handler.
                    continue;
        if self.myID is not None:
            try:
                del EchoTreeService.treeContainers[self.myID];
            except KeyError:
                pass;
                    
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
        A TreeContainer will appear in the newEchoTreeQueue, where
        this thread retrieves it. The new tree is then sent to 
        all subscribers of that tree, as recorded in the tree container.
        Only one instance of this thread runs:
        '''
        
        singletonRunning = False;
        
        def __init__(self):
            '''
            Init thread
            @param handlerObj: instance of EchoTreeService.
            @type handlerObj: EchoTreeService.
            '''
            super(EchoTreeService.NewEchoTreeWaitThread, self).__init__();
            if EchoTreeService.NewEchoTreeWaitThread.singletonRunning:
                raise RuntimeError("Only one NewEchoTreeWaitThread instance may run per process.");
            EchoTreeService.NewEchoTreeWaitThread.singletonRunning = True;
            
            EchoTreeService.log("Starting NewEchoTreeWait thread: sends any newly computed EchoTrees to its the connected browser.");
        
        def run(self):
            while 1:
                # Hang on new-EchoTree event:
                modifiedContainer = EchoTreeService.newEchoTreeQueue.get();
                with EchoTreeService.activeHandlersChangeLock:
                    # Deliver the new tree to the browser:
                    try:
                        handler = None;
                        subscriberIDs = modifiedContainer.subscribers();
                        for subscriber in subscriberIDs:
                            try:
                                handlerArr = EchoTreeService.activeHandlers[subscriber];
                            except KeyError:
                                EchoTreeService.log("Error: no handler found in activeHandlers for subscriber %s." % subscriber);
                                continue;
                            for handler in handlerArr:
                                handler.write_message(modifiedContainer.currentTree());
                    except Exception as e:
                        if handler is not None:
                            EchoTreeService.log("Error during send of new EchoTree to %s (%s): %s" % (handler.request.host, handler.request.remote_ip, `e`));
                        else:
                            EchoTreeService.log("Error during send of new EchoTree: %s" % `e`);
                            
    
    @staticmethod
    def triggerTreeComputationAndDistrib(treeContainer, newRootWord):
#**********************
#        if newRootWord == treeContainer.currentRootWord():
#            return;
#**********************
        treeContainer.setCurrentRootWord(newRootWord);
        EchoTreeService.TreeComputer.workQueue.put(treeContainer);
        
    class TreeComputer(Thread):
        '''
        Waits for a new TreeContainer in a publicly accessible Queue
        (TreeComputer.workQueue). Creates a new EchoTree from the root word that
        Generates an EchoTree of the type specified in the tree container,
        based on the root word that is also contained in that container.
        Calls 
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
                
                # Place the new tree into the output queue for broadcasters to
                # pick up and distribute to interested parties. (
                # jsonTree has arrived, and they should push it to their clients:
                EchoTreeService.newEchoTreeQueue.put(treeContainerToProcess);
        
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
    Convenience for firing up various servers. Currently not used. 
    In its current form it knows to start the service that distributes
    a JavaScript script that subscribes to the EchoTree service (the
    main class, which inherits from WebSocketHandler. Need to start
    the script server (EchoTreeScriptRequestHandler) in main() if
    this module is used stand-alone, rather than from some browser-side
    script that already knows how to push new root words, and subscribe
    to EchoTrees.
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
    
    # Start thread that waits for new root words and computes the respective tree:
    EchoTreeService.log('Starting TreeComputer thread.');
    EchoTreeService.TreeComputer().start();
    
    # Start thread that waits for a newly computed tree,
    # and sends it to all subscribers:
    EchoTreeService.NewEchoTreeWaitThread().start();
    
    
    EchoTreeService.log("Starting EchoTree distribution server at port %s: creates, and pushes new word trees to all subscribed clients." %
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
        EchoTreeService.log("Stopping EchoTree distribution server...");
        if ioLoop.running():
            ioLoop.stop();
        EchoTreeService.NewEchoTreeWaitThread.stop();
        EchoTreeService.TreeComputer.stop();
#        treeComputerThread.stop();
        EchoTreeService.log("EchoTree distribution server stopped.");
        if EchoTreeService.logFD is not None:
            EchoTreeService.logFD.close();
        os._exit(0);
        