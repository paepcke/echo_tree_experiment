#!/usr/bin/env python

'''
Module holding three servers:
   1. Web server serving a fixed html file containing JavaScript for starting an event stream to clients.
   2. Server for anyone uploading a new JSON formatted EchoTree.
   3. Server to which browser based clients subscribe as server-sent stream recipients.
      This server pushes new EchoTrees as they arrive via (2.). The subscription is initiated
      by the served JavaScript (for example.)
For ports, see constants below.

Protocol:
   Player to server:
       addWord: <wordTyped>
       goodGuessClicked:       # Only sent by disabled. Server records the click in the score, and also notifies partner 
       login: role=disabledRole disabledID=disabledEmail partnerID=partnerEmail
       parDone: <parID>        # Only sent by disabled. Server records event, and returns a new par, or "done:".
                               # <parId> is -1 one for the first call that asks for the first paragraph.  
       test:
   Server to player:
       dyadComplete:          # to both disabled and partner when both players logged in.
       done:                  # the session is finished. Sent to both disabled and partner
       goodGuessClicked:      # only to partner. Action by browser: show feedback to partner
       newPar: <parID>|<parStr> # sent only to disabled.
       newPar: <topicKeyword> # Sent to partner: topic keyword of next paragraph to work on.
       waitForPlayer: <playerID> # One player has logged in, waiting for the other, whos ID is included
'''

import os;
import sys;
import time;
import socket;
import argparse;
import urlparse;
import datetime;
import random;
from threading import Event, Lock, Thread;

import tornado;
from tornado.ioloop import IOLoop;
from tornado.websocket import WebSocketHandler;
from tornado.httpserver import HTTPServer;

from echo_tree import WordExplorer;

HOST = socket.getfqdn();

ECHO_TREE_PAGE_SERVICE_PORT = 5003
ECHO_TREE_EXPERIMENT_SERVICE_PORT = 5004;

# Number of paragraphs to communicate during one game:
NUM_OF_PARS_PER_SESSION = 10;

DISABLED_PAGE_NAME = "disabled.html";
PARTNER_PAGE_NAME = "partner.html";
DISABLED_CSS_NAME = "disabled.css";
PARTNER_CSS_NAME = "partner.css";
EXPERIMENT_MANAGEMENT_NAME = "manageExperiment.js";
ECHO_TREE_NAME = "echoTreeExperiment.js";

HTML_MIME = "text/html";
CSS_MIME  = "text/css";
JS_MIME   = "application/javascript";

SCRIPT_DIR = os.path.realpath(os.path.dirname(__file__));
#DBPATH = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/testDb.db");
#DBPATH = os.path.join(SCRIPT_DIR, "Resources/EnronCollectionProcessed/EnronDB/enronDB.db");
RECREATION_DB_PATH = os.path.join(SCRIPT_DIR, "Resources/dmozRecreation.db");
#GOOGLE_DB_PATH = os.path.join(SCRIPT_DIR, "Resources/googleNgrams.db");

PARAGRAPHS_PATH = os.path.join(SCRIPT_DIR, "Resources/paragraphs.txt");

CSV_OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "Measurements");

class Condition:
    RECREATION_NGRAMS = 0;
    GOOGLE_NGRAMS     = 1;

class Role:
    DISABLED = 'disabledRole';
    PARTNER  = 'partnerRole';

# -----------------------------------------  Classes ExperimentPair, ParagraphScore --------------------

class ExperimentDyad(object):
    
    def __init__(self, theInstantiatingHandler, instantiatorRole, disabledID, partnerID):
        '''
        Creates a new ExperimentDyad.
        @param theInstantiatingHandler:
        @type theInstantiatingHandler:
        @param disabledID:
        @type disabledID:
        @param partnerID:
        @type partnerID:
        '''
        self.theDisabledID   = disabledID;
        self.thePartnerID    = partnerID;
        self.instantiatorRole = instantiatorRole;
        self.dyadLoggedIn = False;
        self.thisHandler  = theInstantiatingHandler;
        if instantiatorRole == Role.DISABLED:
            self.disabledHandler = theInstantiatingHandler;
            self.partnerHandler  = None;
        else:
            self.partnerHandler  = theInstantiatingHandler;
            self.disabledHandler = None;
        self.thatHandler  = None;
        self.condition    = None;
        
        # All ParagraphScore instances for this dyad
        self.parScores = [];
        
        # All the paragraphs used by this dyad before.
        # Keys are integers between 0 and the number of
        # paragraphs in file PARAGRAPHS_PATH. That
        # file is internalized into EchoTreeLogServices.paragraphs:
        self.parsUsed  = {};

    def currentParScore(self):
        return self.parScores[-1];
        
    def disabledID(self):
        return self.theDisabledID;
    
    def partnerID(self):
        return self.thePartnerID;
    
    def condition(self): 
        return self.condition;
    
    def setCondition(self, condition):
        self.condition = condition;
    
    def isDyadLoggedIn(self):
        return self.dyadLoggedIn;

    def setDyadLoggedIn(self):
        self.dyadLoggedIn = True;
        
    def getThisHandler(self):
        return self.thisHandler;

    def getThatHandler(self):
        return self.thatHandler;
    
    def getDisabledHandler(self):
        return self.disabledHandler;
    
    def getPartnerHandler(self):
        return self.partnerHandler;
    
    def setThatHandler(self, handler):
        self.thatHandler = handler;
        if self.disabledHandler is None:
            self.disabledHandler = handler;
        else:
            self.partnerHandler  = handler;

    def getNewParScore(self):
        '''
        Returns a random paragraph for a dyad to work on.
        Guarantees that this dyad has never seen that par.
        @return: paragraph ID
        @rtype: int
        '''
        if len(self.parsUsed) >= NUM_OF_PARS_PER_SESSION:
            return None;
        while True:
            newParID = random.randint(0,len(EchoTreeLogService.paragraphs) - 1);
            try:
                self.parsUsed[newParID];
                # If we didn't bomb out, we used this par
                # already:
                continue;
            except KeyError:
                self.parsUsed[newParID] = True;
                return newParID; 

    def saveToCSV(self, outfilePath):
        '''
        Outputs one session's outcome to CSV with this schema:
        Disabled,Partner,Condition, parID_i, StartTime_i, EndTime_i, GoodnessClicks_i, NumLettersTyped_i
        @param outfile: path to csv file that is already prepared with a header.
        @type outfile: String
        '''
        with open(outfile, 'a') as fd:
            fd.write(self.disabledID() + ',' + self.partnerID() + ',' +  self.condition() + ',');
            for i in range(len(self.parScores)):
                parScore = self.parScores[i];
                # Compute number of letters typed: each word that was
                # inserted from the tree counts only for one letter:
                numLetters = len(parScore.typedWords);
                for word in parScore.insertedWords:
                    numLetters -= len(word) - 1; # -1 is to count one of the letters.
                fd.write(str(parScore.parID) +\
                         str(parScore.startTime) + ',' +\
                         str(parScore.stopTime) + ',' +\
                         str(parScore.numGoodGuesses) + ',' +\
                         str(numLettersTyped));
        
class ParagraphScore(object):
    
    def __init__(self, condition, parID, disabled, partner):
        '''
        @param parContent: Content of the paragraph being scored
        @type parContent: String
        '''
        self.parID            = parID;
        self.disabledPlayer   = disabled;
        self.partnerPlayer    = partner;
        self.condition        = condition;
        self.startTime        = 0L;
        self.endTime          = 0L; 
        
        self.numGoodGuesses = 0;
        # Words typed by the disabled:
        self.typedWords = "";
        # Words inserted via clicking on a word in the tree:
        self.insertedWords = [];
        
    def addInsertedWord(self, word):
        self.insertedWords.append(word);
        
    def addGoodnessClick(self):
        self.numGoodGuesses += 1;
        
    def setStartTime(self):
        self.startTime = time.time();

    def setStopTime(self):
        self.stopTime = time.time();

# -----------------------------------------  Top Level Service Provider Classes --------------------

class EchoTreeLogService(WebSocketHandler):
    '''
    Handles interaction with dyads of users during experiment.
    Each instance handles one browser via a long-standing WebSocket
    connection.
    '''
    
    # Array of paragraphs to choose from:
    paragraphs = None;
    
    # Dict of dyads keyed by player. Values are ExperimentDyad
    # instances in which the keyed player participated in. Each dyad instance
    # is represented in two value lists, once in the value for each player.
    # However, the instances are the same object in both
    # cases:
    dyads = {};
    
    # Class-level list of handler instances: 
    activeHandlers = [];
    # Lock to make access to activeHanlders data struct thread safe:
    activeHandlersChangeLock = Lock();
    
    # Lock for changing the current EchoTree:
    currentEchoTreeLock = Lock();
    
    # Lock protecting access to dyads dict:
    dyadLock = Lock();
    
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

        # Read the paragraphs the disabled players have to write
        # from a file, removing \n with spaces. The pars in the 
        # file are separated by a newline:
#******         
#        with open(PARAGRAPHS_PATH, 'r') as fd:
#            pars = fd.read().split('\n\n');
#            for i,par in enumerate(pars):
#                pars[i] = pars[i].replace('\n', ' ')
#            EchoTreeLogService.paragraphs = pars; 
#
#        # Find a fresh CSV file to output to:
#        self.gameOutputFilePath = None;
#        outputFileNum = 0;
#        while True:
#            self.gameOutputFilePath = os.path.join(CSV_OUTPUT_DIR, "gameResult_" + str(outputFileNum) + ".csv")
#            if os.path.exists(self.gameOutputFilePath):
#                outputFileNum += 1;
#                continue;
#        # Add the CSV header to the output file:
#        with open(self.gameOutputFilePath, 'w') as fd:
#            fd.write("Disabled,Partner,Condition,");
#            for i in range(NUM_OF_PARS_PER_SESSION):
#                fd.write('ParID_' + str(i) + 'StartTime_' + str(i), 'EndTime_' + str(i), 'GoodnessClicks_' + str(i), 'NumLettersTyped_' + str(i));
#            fd.writeln; 


        # Register this handler instance as being an active
        # experiment logger:
        with EchoTreeLogService.activeHandlersChangeLock:
            EchoTreeLogService.activeHandlers.append(self);

        self.myDyad = None;
    
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
            self.write_message('sendLogin:')
            return;

        # Is browser reporting the players' email addresses?
        # Format: login:role=disabledRole myEmail=disabledEmail otherEmail=partnerEmail
        #    or : login:role=partnerFole myEmail=partnerEmail otherEmail=disabledEmail        
        if (msgArr[0] == 'login'):
            if (len(msgArr) < 2):
                EchoTreeLogService.log('Bad setIDs message: no arg provided.');
                return;
            self.processLogin(msgArr);
            
        # Is disabled-browser telling that it added one word
        # from the tree down into the ticker?
        if (msgArr[0] == 'addWord'):
            if (len(msgArr) < 2):
                EchoTreeLogService.log('Bad addWord message: no arg provided.');
                return;
            word = msgArr[1];
            currScore = self.myDyad.currentParScore().addInsertedWord(word);
            self.myDyad.getThatHandler().write_message("addWord:" + word);

        if (msgArr[0] == 'goodGuessClicked:'):
            self.myDyad.currentParScore().addGoodnessClick();
            # Tell partner so feedback can be given:
            self.myDyad.getThatHandler().write_message("goodGuessClicked:");
            
        # Is browser reporting that one paragraph is all done?
        # (Note this msg is also used when a disabled partner is
        # asking for its first paragraph. The arg is -1 in that case.
        if (msgArr[0] == 'parDone:'):
            self.myDyad.currentParScore().setStopTime();
            newParID = self.myDyad.getNewPar();
            if newPar is None:
                # Game done. All NUM_OF_PARS_PER_SESSION paragraphs have
                # been communicated:
                self.write_message('done:');
                self.myDyad.getThatHandler().write_message('done:');
                self.myDyad.saveToCSV(self.NUM_OF_PARS_PER_SESSION);
                self.handleGameDone();
                return;
            else:
                parContent = EchoTreeLogService.paragraphs[newParID];
                # Each paragraph starts with a topic keyword, followed by a '|'.
                # Send the topic to the partner, and the body of the paragraph to
                # the disabled:
                topicPlusContent = parContent.split('|');
                self.myDyad.getDisabledHandler().write_message('newPar:' + str(newParID) + '|' + topicPlusContent[1]);
                self.myDyad.getPartnerHandler().write_message('newPar:' + topicPlusContent[0]);
    
    def handleGameDone(self):
        #**********
        # Turn players around.
        pass
    
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


    def processLogin(self, msgArr):
        '''
        Heavy lifting of matching up dyads as they log in. Called when a 
        player ('thisPlayer') is opening a connection to this server. The
        msgArr provides information about the other player this new connection
        must be matched up with ('thatPlayer') If no existing dyad is found 
        that pair this player and thatPlayer, a new such dyad is created. 
        If such an dyad is found, the other player already logged in and the
        game is ready to go. Note that a player may play multiple games, with
        different other players. A dict keyed by player keeps track of the
        resulting multiple dyad instances.  
        @param msgArr: Argument part of the setIDs msg, which has format 
                        login:role=disabledRole myEmail=disabledEmail otherEmail=partnerEmail
                    or: login:role=partnerRole myEmail=partnerEmail otherEmail=disabledEmail        
        @type msgArr: [String]
        '''
        argArr = msgArr[1].split(' ');
        if len(argArr) != 3:
            EchoTreeLogService.log('Bad login message: not all args provided: ' + subjectMsg);
            return;
        roleSpec = argArr[0];
        
        if roleSpec.find('=') == -1:
            EchoTreeLogService.log('Bad login message: bad role spec: ' + str(roleSpec));
            return;
        role = roleSpec.split('=')[1];
        
        thisEmailSpec = argArr[1];
        if thisEmailSpec.find('=') == -1:
            EchoTreeLogService.log('Bad login message: bad thisEmail spec: ' + str(thisEmailSpec));
            return;
        disabledEmail = thisEmailSpec.split('=')[1];

        thatEmailSpec = argArr[2];
        if thatEmailSpec.find('=') == -1:
            EchoTreeLogService.log('Bad login message: bad thatEmail spec: ' + str(thatEmailSpec));
            return;
        partnerEmail = thatEmailSpec.split('=')[1];
        if role == Role.DISABLED:
            thisEmail = disabledEmail;
            thatEmail = partnerEmail
        else:
            thisEmail = partnerEmail;
            thatEmail  = disabledEmail;

        if thisEmail == thatEmail:
            # Something wrong. To recover, check whether any open
            # dyad involves this player. If so, delete that dyad:
            try:
                defectivePlayersDyads = EchoTreeLogService.dyads[thisEmail];
                if defectivePlayersDyads is not None:
                    newDyadChain = [];
                    for dyad in defectivePlayersDyads:
                        if dyad.isDyadLoggedIn():
                            newDyadChain.append(dyad);
                    EchoTreeLogService.dyads[thisEmail] = newDyadChain;
            except KeyError:
                # no diad chain needs repairing.
                pass;
                
            self.write_message("showMsg:Back here it looks as if player '%s' is trying to play with another player of the same name. " % thisEmail +\
                               "Trying to recover. Please go to the starting URL. So sorry.");
            return; 

        with EchoTreeLogService.dyadLock:
            try:
                thisPlayersDyads = EchoTreeLogService.dyads[thisEmail];
                for dyad in thisPlayersDyads:
                    dyadDisabledID = dyad.disabledID();
                    dyadPartnerID  = dyad.partnerID();
                    if (thisEmail == dyadDisabledID and thatEmail == dyadPartnerID) or \
                       (thisEmail == dyadPartnerID and thatEmail == dyadDisabledID):
                        # Found waiting dyad:
                        # The thisHandler was set when dyad was created. Now 
                        # set that of the partner:
                        dyad.setThatHandler(self);
                        if dyad.isDyadLoggedIn():
                            EchoTreeLogService.log("Player logging into an already logged-in dyad with the same partner: " + str(msgArr));
                            return;
                        dyad.setDyadLoggedIn();
                        EchoTreeLogService.log("Dyad complete: %s/%s" % (thisEmail, thatEmail));
                        self.write_message('dyadComplete:');
                        # Notify the already waiting player:
                        dyad.getThisHandler().write_message("dyadComplete:");
                        return
                    
                # Dyad chain for the player who is checking in was found,
                # but none of those dyads represented a game of this player with 
                # that other player. Create a new open dyad and link it to this
                # player's existing chain of dyads:
                newDyad = ExperimentDyad(self, role, disabledEmail, partnerEmail);
                self.myDyad = newDyad;
                # Register this new dyad under both names so that we can find it:
                EchoTreeLogService.dyads[thisEmail].append(newDyad);
                EchoTreeLogService.dyads[thatEmail].append(newDyad);
                self.write_message("waitForPlayer:" + thatEmail);
                EchoTreeLogService.log("Dyad created and waiting: %s/%s" % (thisEmail, thatEmail));
                return;
            except KeyError:
                # The other player has not logged in yet. Create
                # a new dyad with this handler as the first argument,
                # and the player ids as the rest:
                newDyad = ExperimentDyad(self, role, disabledEmail, partnerEmail);
                self.myDyad = newDyad;
                EchoTreeLogService.dyads[thisEmail] = [newDyad];
                EchoTreeLogService.dyads[thatEmail] = [newDyad];
                self.write_message("waitForPlayer:" + thatEmail);
                EchoTreeLogService.log("Dyad created and waiting: %s/%s" % (thisEmail, thatEmail));
                return;

    @staticmethod
    def decideNewPlayersRole(contactingPlayerEmail, friendEmail):
        with EchoTreeLogService.dyadLock:
            try:
                newPlayersDyads = EchoTreeLogService.dyads[contactingPlayerEmail];
            except KeyError:
                # Totally new person:
                return EchoTreeLogService.randomRole();
            for dyad in newPlayersDyads:
                if (not dyad.isDyadLoggedIn() and ((dyad.disabledID() == contactingPlayerEmail) or
                                       (dyad.partnerID()) == contactingPlayerEmail)):
                    # If an open dyad already exists for him, then he 
                    # pushed the browser back button, or reloaded. Delete that
                    # open dyad, and give him a new one:
                    del EchoTreeLogService.dyads[contactingPlayerEmail];
                    return EchoTreeLogService.randomRole();
                if (not dyad.isDyadLoggedIn() and (dyad.disabledID() == friendEmail)):
                    # Dyad was opened for a friend of the new player. So the
                    # new player must get the opposite role:
                    return Role.PARTNER;
                elif (not dyad.isDyadLoggedIn() and (dyad.partnerID() == friendEmail)):
                    return Role.DISABLED;
                    
    @staticmethod
    def randomRole():
        if random.randint(1,2) == 1:
            return Role.DISABLED;
        else:
            return Role.PARTNER;

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


class EchoTreeExperimentPageRequestHandler(HTTPServer):
    '''
    Web service serving HTML pages for the experiment 
    participants, and javascript.
    '''

#    def _execute(self, transforms):
#        pass;

    @staticmethod
    def handle_request(request):
        '''
        Handles the HTTP GET request. the request.path property holds
        /disabled.html, or /partner.css, or manageExperiment.js, etc.
        @param request: instance holding information about the request
        @type request: tornado.httpserver.HTTPRequest
        '''
        # Path to the directory with all the material we serve.
        #Should probably just load that once, but this request is not frequent.
        scriptDir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                  "../browser_scripts/");
        isGetAssignment = False;                                  
        if (request.path == "/"):
            scriptPath = os.path.join(scriptDir, "index.html");
        elif (os.path.split(request.path)[1] == 'getAssignment'):
            # Requested 'file' ended in getAssignment, so it's the initial form submission:
            isGetAssignment = True;
        else:
            scriptPath = os.path.join(scriptDir, request.path[1:]);

        mimeType = HTML_MIME;
        if (request.path == "/disabled.css" or request.path == "/partner.css"):
            mimeType = CSS_MIME;
            #self.set_header("Content-Type", "text/css; charset=UTF-8");

        elif (request.path == "/echoTreeExperiment.js" or request.path == "/manageExperiment.js"):
            mimeType = JS_MIME;
            #self.set_header("Content-Type", "application/x-javascript; charset=UTF-8");

        if (isGetAssignment):
            requestURL = request.full_url();
            urlFragTuple = urlparse.urlsplit(requestURL);
            urlRoot = urlFragTuple.scheme + "://" + urlFragTuple.netloc + '/';
            # Query part of URL is like this: 'ownEmail=me@google&otherEmail=you@google'
            urlQuery = urlFragTuple.query;
            # Get this type of struct: dict: {'ownEmail': ['me@google.com'], 'otherEmail': ['you@google.com']}
            emailInfoDict = urlparse.parse_qs(urlQuery);
            try:
                roleToAssign = EchoTreeLogService.decideNewPlayersRole(emailInfoDict['ownEmail'][0], emailInfoDict['otherEmail'][0]);
            except KeyError:
                EchoTreeLogService.log("Initial contact does not provide emails. Dict is: %s" % str(emailInfoDict));
                return;
            if roleToAssign == Role.DISABLED:
                assignedScriptURL = urlRoot + 'disabled.html';
            else:
                assignedScriptURL = urlRoot + 'partner.html';
            
            contentLen = len(assignedScriptURL);
            lastModTime = time.time();
        else:
            if not os.path.exists(scriptPath):
                EchoTreeLogService.log("Non-existing script path requested by some browser: %s" + str(scriptPath));
                return;
            contentLen  = os.path.getsize(scriptPath);
            lastModTime = time.ctime(os.path.getmtime(scriptPath));
        

        # Create the response and the HTML page string:
        reply =  "HTTP/1.1 200 OK\r\n" +\
                 "Content-Type, " + mimeType + "\r\n" +\
                 "Content-Length:%s\r\n" % contentLen +\
                 "Last-Modified:%s\r\n" % lastModTime +\
                 "\r\n";

        if (isGetAssignment):
            # Add the URL of the page the assignment-requesting user is to load:
            reply += assignedScriptURL;
        else:
            # Add the HTML page to the header:
            with open(scriptPath) as fileFD:
                for line in fileFD:
                    reply += line;
        request.write(reply);
        #self.set_header("Content-Type", mimeType);
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
            if  self.socketServerClassName == 'EchoTreeExperimentPageRequestHandler':
                EchoTreeLogService.log("Starting EchoTree page server %d: Returns Web pages and JavaScript for experiment." % self.port);
                http_server = EchoTreeExperimentPageRequestHandler(EchoTreeExperimentPageRequestHandler.handle_request);
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
    EchoTreeLogService.log("Starting EchoTree experiment server at port %s: . Interacts with participants." % (str(ECHO_TREE_EXPERIMENT_SERVICE_PORT) + ":/echo_tree_experiment"));
    application = tornado.web.Application([(r"/echo_tree_experiment", EchoTreeLogService),                                           
                                           ]);
    # Create the service that serves out the Web pages and JS:
    pageAndJSServer = SocketServerThreadStarter('EchoTreeExperimentPageRequestHandler', ECHO_TREE_PAGE_SERVICE_PORT); 
    pageAndJSServer.start();
                                           
                                           
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
        pageAndJSServer.stop();
        EchoTreeLogService.log("EchoTree experiment server stopped.");
        if EchoTreeLogService.logFD is not None:
            EchoTreeLogService.logFD.close();
        os._exit(0);
        