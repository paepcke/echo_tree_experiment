#!/usr/bin/env python

import json;
import copy;
from collections import deque;
from collections import OrderedDict;
import argparse;

from echo_tree_experiment.echo_tree import WORD_TREE_BREADTH;
from echo_tree_experiment.echo_tree import WORD_TREE_DEPTH;
from echo_tree_experiment.echo_tree import WordExplorer;

STOPWORDS =  ['a','able','about','across','after','all','almost','also','am','among','an','and','any',
              'are','as','at','be','because','been','but','by','can','cannot','could','dear','did','do',
              'does','either','else','ever','every','for','from','get','got','had','has','have','he',
              'her','hers','him','his','how','however','i','if','in','into','is','it','its','just',
              'least','let','like','likely','may','me','might','most','must','my','neither','no','nor',
              'not','of','off','often','on','only','or','other','our','own','rather','said','say','says',
              'she','should','since','so','some','than','that','the','their','them','then','there','these',
              'they','this','tis','to','too','twas','us','wants','was','we','were','what','when','where',
              'which','while','who','whom','why','will','with','would','yet','you','your',
              'subject', 'cc', 'bcc', 'nbspb', 'mr.', 'inc.', 'one', 'two', 'three', 'four', 'five', 
              'six', 'seven', 'eight', 'nine', 'ten', 'enron', 'http'];

# All of string.punctuation, except for comma, which is
# the Stanford NLP token separator:
PUNCTUATION = '!"#$%&\'()*+-./:;<=>?@[\\]^_`{|}~'

class Verbosity:
    NONE  = 0;
    LOG   = 1;
    DEBUG = 2;


class SentencePerformance(object):
    '''
    *********Stuct to hold measurement results of one sentence.
       - sentenceLen: number of words that are not stopwords.
       - failures: number of times a tree did not contain one of the words, and a new tree needed to 
                   be constructed by typing in the word.
       - outOfSeqs: number of times future word in the sentence was in an early tree.
       - depths: for each tree depth, how many of the sentence's words appeared at that depth.   
    '''
    
    def __init__(self, evaluator, tokenSequence, emailID=-1, sentenceID=None):
        self.evaluator = evaluator;
        self.emailID = emailID;
        self.sentenceID = sentenceID;
        
        self.sentenceLen = len(tokenSequence);
        self.failures    = 0;
        self.outOfSeqs   = 0;
        self.depths      = {};
    
    def addFailure(self):
        '''
        Increment counter of occasions when a word was not found
        in the currently displayed tree.
        '''
        self.failures += 1;
        
    def addOutOfSeq(self):
        '''
        Increment count of occasions when a word was not found in the
        tree that was active when the word was to being considered, but
        was contained in a tree that was displayed in service
        of an earlier word in the sentence.        
        '''
        self.outOfSeqs += 1;
        
    def addWordDepth(self, depth):
        '''
        Given the depth of a tree at which a word was found,
        count one more such occurrence.
        @param depth: depth at which word was found in displayed tree.
        @type depth: int
        '''
        try:
            self.depths[depth] += 1;
        except KeyError:
            self.depths[depth] = 1;
            
    def getNetFailure(self):
        '''
        Return the difference between all failures and outOfSeqs.
        The latter are occasions when a word was not found in the
        tree that was active when the word was to be entered, but
        it was contained in a tree that was displayed in service
        of an earlier word in the sentence.
        '''
        return self.failures - self.outOfSeqs;
    
    def getNetSuccess(self):
        '''
        Return percentage of times a word was found in a currently
        displayed tree.
        '''
        # Subtract 1 from sentence len, b/c the last word had
        # no chance to predict a word:
        return 100 - (self.getNetFailure() * 100.0 / (self.sentenceLen - 1));
    
    def getDepthWeightedSuccessSentence(self):
        '''
        Return a number between 0 and 1 that provides
        a weighted prediction success: successful predictions
        at tree level 1 earn one point. Successful predictions
        at tree level 2 earn 1/2 point; at level 3: 1/4 point, etc.
        The sum over that sentence is divided by (sentenceLength - 1)
        to normalize over that length: 
        
                   (1/2)**(depth-1) * countAtDepth
            sum(   --------------------------  ) for all words in sentence
                        (sentenceLen - 1)
        '''
        res = 0.0;
        #maxDepth = self.evaluator.getMaxDepthAllSentences();
        for depth in range(1, WORD_TREE_DEPTH):
            res += 0.5**(depth-1) * self.getDepthCount(depth);

        # Subtract 1 from sentence len, b/c the last word had
        # no chance to predict a word:
        return res/(self.sentenceLen - 1);
        
    def getDepthCount(self, depth):
        '''
        Return the number of times a word in this sentence was found
        at the given depth. Takes care of cases when given depth was 
        never the site of a found word (returns 0).
        @param depth: depth in tree whose occurrence count is requested.
        @type depth: int
        '''
        try:
            return self.depths[depth];
        except KeyError:
            return 0;
        
    def getDepths(self):
        '''
        Create array of depth counts. The array will be as
        long as the deepest depth. Depths in between that were
        never site for a found word are properly entered as zero.
        '''
        deepest = self.evaluator.getMaxDepthAllSentences();
        self.allDepths = [];
        for oneDepth in range(1,deepest + 1):
            self.allDepths.append(self.getDepthCount(oneDepth));
        return self.allDepths;
    
    def getDeepestDepth(self):
        try:
            return max(self.depths.keys());
        except ValueError:
            # No entries in depths at all:
            return 0;
    
    def toString(self):
        '''
        Return human-readable performance of this sentence.
        '''
        netFailure = self.getNetFailure();
        netSuccess = self.getNetSuccess();
        depthReport = str(self.getDepths());
        
        return "SentenceLen: %d. Failures: %d. OutofSeq: %d. NetFailure: %d. NetSuccess: %.2f%%. Depths: %s" %\
            (self.sentenceLen, self.failures, self.outOfSeqs, netFailure, netSuccess, depthReport);
                        
    def toCSV(self):
        row =        str(self.emailID);
        row += ',' + str(self.sentenceID);
        row += ',' + str(self.sentenceLen);
        row += ',' + str(self.failures);
        row += ',' + str(self.outOfSeqs);
        row += ',' + str(self.getNetFailure());
        row += ',' + '%.2f' % self.getNetSuccess();
        for depth in range(1, self.evaluator.getMaxDepthAllSentences() + 1):
            row += ',' + str(self.getDepthCount(depth));
        row += ',' + str(self.getDepthWeightedSuccessSentence());
        return row;
        

class Evaluator(object):
    
    def __init__(self, dbPath):
        self.wordExplorer = WordExplorer(dbPath);
        self.initWordCaptureTally();
        self.verbosity = Verbosity.NONE;
        
    def getMaxDepthAllSentences(self):
        '''
        Runs through all sentences this Evaluator instance has
        measured, and returns the deepest depth of all sentences:
        '''
        maxDepth = 0;
        for sentencePerf in self.performanceTally:
            maxDepth = max(sentencePerf.getDeepestDepth(), maxDepth);
        return maxDepth;
        
    def toCSV(self, outFileFD=None):
        csv = self.getCSVHeader() + '\n';
        for sentencePerf in self.performanceTally:
            csv += sentencePerf.toCSV() + '\n';
        if outFileFD is not None:
            try:
                outFileFD.write(csv);
                outFileFD.flush();
            except IOError:
                print "Warning: could not write to outfile FD: %s" + str(outFileFD);
        return csv;
            
    def getCSVHeader(self):
        header = 'EmailID,SentenceID,SentenceLen,Failures,OutofSeq,NetFailure,NetSuccess';        
        for depthIndex in range(1,self.getMaxDepthAllSentences() + 1):
            header += ',Depth_' + str(depthIndex);
        header += ',DepthWeightedScore'
        return header;
    
    def extractWordSet(self, jsonEchoTreeStr):
        '''
        Given a JSON Echo Tree, return the root word and a flat set of
        all follow-on words.
        @param jsonEchoTreeStr: JSON EchoTree structure of any depth/breadth
        @type jsonEchoTreeStr: string
        '''
        pythonEchoTree = json.loads(jsonEchoTreeStr);
        flatTreeStr  = self.extractWordSeqsHelper(pythonEchoTree);
        lowerCaseFlatTreeList = [];
        for word in flatTreeStr.split(" "):
            lowerCaseFlatTreeList.append(word.lower());
        rootWord = lowerCaseFlatTreeList[0];
        flatSet = set(lowerCaseFlatTreeList[1:]);
        return (rootWord, flatSet);
    
    def getDepthFromWord(self, pythonEchoTree, word):
        '''
        Given a word, return its depth in the tree. Root postion is 0.
        @param pythonEchoTree: Python encoded EchoTree
        @type pythonEchoTree: Dict
        @param word: word to find in the EchoTree
        @type word: string
        @return: the depth at which the word occurs in the tree, or 0 if not present.
        @rtype: {int | None}
        '''
        #**********************
        #self.wordExplorer.printWordTree(pythonEchoTree, 2);
        #**********************
        resultDepths = []
        self.getDepthFromWordHelper(pythonEchoTree, word, resultDepths, depth=0);
        try:
            return min(resultDepths);
        except ValueError:
            return None;
    
    def getDepthFromWordHelper(self, pythonEchoTree, wordToFind, resultDepths, depth=0):
        if pythonEchoTree is None:
            return None;
        # While 'wordToFind' is always a single word, the
        # subtrees (pythonEchoTree['word']) will be 
        # two words for a trigram system, yet one word
        # for bigram systems. Check whether *any* word in the given
        # pythonEchoTree match wordToFind. 
        #****REMOVE if pythonEchoTree['word'] == wordToFind:

        if wordToFind in pythonEchoTree['word'].split():
            resultDepths.append(depth);
            return;
        # No match; recursively check the subtrees:
        for subtree in pythonEchoTree['followWordObjs']:
            newDepth = self.getDepthFromWordHelper(subtree, wordToFind, resultDepths, depth=depth+1);
            if newDepth is not None:
                resultDepths.append(newDepth);
                return;
        return None;
    
    
    def extractSentences(self, jsonEchoTreeStr):
        '''
        Print all sentences that can be made from the EchoTree.
        @param jsonEchoTreeStr:
        @type jsonEchoTreeStr:
        '''
        #sentenceStructs = self.extractWordSeqs(jsonEchoTreeStr);
        pass
        
    
    def extractWordSeqs(self, jsonEchoTreeStr):
        '''
        Given a JSON EchoTree structure, return a structure representing all
        'sentences' generated by the tree via a depth-first walk. Example:
        root  pig    truffle
                     mud
              tree   deep
                     broad
        generates: 
            deque([root, OrderedDict([(tree, deque([broad, deep]))]), 
                         OrderedDict([(pig, deque([mud, truffle]))])])
        from which one can generate:
            - root tree broad
            - root tree deep
            - root pig mud
            - root pig truffle
            
        @param jsonEchoTreeStr: JSON encoded EchoTree
        @type jsonEchoTreeStr:string
        '''
        pythonEchoTree = json.loads(jsonEchoTreeStr);
        flatTree  = self.extractWordSeqsHelper(pythonEchoTree);
        flatQueue = deque(flatTree.split());
        # Number of words: breadth ** (depth-1) + 1
        numSibPops = WORD_TREE_BREADTH ** (WORD_TREE_DEPTH - 2);
        # Root word first:
        resDictQueue = deque([flatQueue[0]]);
        for dummy in range(numSibPops):
            sibs = deque([]);
            parentDict = OrderedDict();
            resDictQueue.append(parentDict);
            for dummy in range(WORD_TREE_BREADTH):
                sibs.append(flatQueue.pop());
            parentDict[flatQueue.pop()] = sibs;
        return resDictQueue;
    
    def extractWordSeqsHelper(self, pythonEchoTreeDict):
        '''
        Too-long example (it's what I had on hand:
        {u'word': u'reliability', 
         u'followWordObjs': [
                {u'word': u'new', 
                 u'followWordObjs': [
                     {u'word': u'power', 
                      u'followWordObjs': []}, 
                     {u'word': u'generation', 
                      u'followWordObjs': []}, 
                     {u'word': u'business', 
                      u'followWordObjs': []}, 
                     {u'word': u'product', 
                      u'followWordObjs': []}, 
                     {u'word': u'company', 
                      u'followWordObjs': []}]}, 
                {u'word': u'issues', 
                 u'followWordObjs': [
                     {u'word': u'related', 
                      u'followWordObjs': []}, 
                     {u'word': u'need', 
                      u'followWordObjs': []}, 
                     {u'word': u'raised', 
                      u'followWordObjs': []}, 
                     {u'word': u'such', 
                      u'followWordObjs': []}, 
                     {u'word': u'addressed', 
                      u'followWordObjs': []}]}, 
                {u'word': u'legislation', 
                 u'followWordObjs': [
                     {u'word': u'passed', 
                      u'followWordObjs': []}, 
                     {u'word': u'allow', 
                      u'followWordObjs': []}, 
                     {u'word': u'introduced', 
                      u'followWordObjs': []}, 
                     {u'word': u'require', 
                      u'followWordObjs': []}, 
                     {u'word': u'provide', 
                      u'followWordObjs': []}]}, 
                {u'word': u'standards', 
                 u'followWordObjs': [
                     {u'word': u'conduct', 
                      u'followWordObjs': []}, 
                     {u'word': u'set', 
                      u'followWordObjs': []}, 
                     {u'word': u'needed', 
                      u'followWordObjs': []}, 
                     {u'word': u'facilitate', 
                      u'followWordObjs': []}, 
                     {u'word': u'required', 
                      u'followWordObjs': []}]}, 
                {u'word': u'problems', 
                 u'followWordObjs': [
                     {u'word': u'please', 
                      u'followWordObjs': []}, 
                     {u'word': u'California', 
                      u'followWordObjs': []}, 
                     {u'word': u'accessing', 
                      u'followWordObjs': []}, 
                     {u'word': u'arise', 
                      u'followWordObjs': []}, 
                     {u'word': u'occur', 
                     u'followWordObjs': []}]}]}        
        
        @param pythonEchoTreeDict:
        @type pythonEchoTreeDict: dict
        '''
        res = '';
        word = pythonEchoTreeDict['word'];
        res += ' ' + word;
        if len(pythonEchoTreeDict['followWordObjs']) == 0:
            return res;
        for subtree in pythonEchoTreeDict['followWordObjs']:
            res += self.extractWordSeqsHelper(subtree);
        return res;
            
    def initWordCaptureTally(self):
        self.performanceTally = [];
        
    def tallyWordCapture(self, sentenceTokens, emailID=-1, sentenceID=None, removeStopwords=False):
        '''
        Measures overlap of each sentence token with trees created
        by this evaluator's database. Stopwords are removed here. Measures:
        
           - sentenceLen: number of words that are not stopwords.
           - failures: number of times a tree did not contain one of the words, and a new tree needed to 
                       be constructed by typing in the word.
           - outOfSeqs: number of times future word in the sentence was in an early tree.
           - depths: for each tree depth, how many of the sentence's words appeared at that depth.
           
       Creates a SentencePerformance instance that stores the result measures. Adds
       that instance to this evaluator's performanceTally array.
                     
        @param sentenceTokens: tokens that make up the sentence.
        @type sentenceTokens: [string]
        @param emailID: optional ID to identify from which email the given sentence was taken.
        @type emailID: <any>
        @param sentenceID: optional ID to identify the given sentence within its email.
        @type sentenceID: <any>
        @param removeStopwords: whether or not to remove stopwords.
        @type removeStopwords: boolean
        '''
        # We'll modify sentenceTokens in the loop
        # below, so get a shallow copy for the loop:
        tokenCopy = copy.copy(sentenceTokens);
        for word in tokenCopy:
            if len(word) == 0:
                sentenceTokens.remove(word);
                continue;
            if removeStopwords and (word.lower() in STOPWORDS):
                sentenceTokens.remove(word);
        
        if self.verbosity == Verbosity.DEBUG:
            print("Sentence %d tokens after cleanup: %s" % (sentenceID,str(sentenceTokens)));        
                
        # Make a new SentencePerformance instance, passing this evaluator,
        # the array of stopword-free tokens, and the index in the self.performanceTally
        # array at which this new SentencePerformance instance will reside:
        if sentenceID is None:
            sentenceID = len(self.performanceTally);
        sentencePerf = SentencePerformance(self, sentenceTokens, emailID=emailID, sentenceID=sentenceID);
        
        # Start for real:
        tree = self.wordExplorer.makeWordTree(sentenceTokens[0], self.arity);
        treeWords = self.extractWordSet(self.wordExplorer.makeJSONTree(tree));
        prevWord = sentenceTokens[0];
        for wordPos, word in enumerate(sentenceTokens[1:]):
            #word = word.lower();
            wordDepth = self.getDepthFromWord(tree, word);
            if self.verbosity == Verbosity.DEBUG:
                print("   Word %s score:\t\t%f  %f" % (prevWord,
                                                       1.0 if wordDepth == 1 else 0.0, 
                                                       0.5 if wordDepth == 2 else 0.0))
            if wordDepth is None:
                # wanted word is not in tree anywhere:
                sentencePerf.addFailure();
                # Is any of the future sentence words in the tree's word set?
                if wordDepth < len(sentenceTokens) - 1:
                    for futureWord in sentenceTokens[wordPos+1:]:
                        if futureWord in treeWords:
                            sentencePerf.addOutOfSeq();
            else:
                # Found word in tree:
                sentencePerf.addWordDepth(wordDepth);
            # Build a new tree from the (virtually) typed in current word
            tree =  self.wordExplorer.makeWordTree(word, self.arity);
            treeWords = self.extractWordSet(self.wordExplorer.makeJSONTree(tree));
            prevWord = word;
        
        # Finished looking at every toking in the sentence.
        self.performanceTally.append(sentencePerf);
        if self.verbosity == Verbosity.DEBUG:
            totalDepthWeightedScore = 0.0
            totalDepth1Score = 0;
            totalDepth2Score = 0;
            performance = self.performanceTally[-1]
            totalDepthWeightedScore += performance.getDepthWeightedSuccessSentence();
            totalDepth1Score        += performance.getDepthCount(1);
            totalDepth2Score        += performance.getDepthCount(2);
                
            print("\t\t\tTotal: \t%f  %f  %f" % (totalDepth1Score,
                                                 totalDepth2Score * 0.5,
                                                 totalDepthWeightedScore));
            print("\t\t\t       \t-------------------------------");
    def readSentence(self, fd):
        sentenceOpener = '['
        sentenceCloser= ']'
        res = '';
        # Find start of next sentence:
        while 1:
            try:
                letter = fd.read(1);
                if letter == sentenceOpener:
                    # Found start of sentence
                    break;
                if len(letter) == 0:
                    # Gone through the whole file:
                    return None;
            except IOError:
                return None
        while 1:
            try:
                letter = fd.read(1);
                # Reached end of file before closing bracket:
                if len(letter) == 0:
                    raise IOError;
            except IOError:
                print "Warning: ignoring unfinished sentence: %s." % res;
                return None
            if letter == sentenceCloser:
                return res;
            if letter == " " or letter in PUNCTUATION:
                continue;
            res += letter;
            
    def checksum(self, theStr):
        '''
        Returns the sum of all the given string's ASCCII values.
        @param theStr: string to be checksummed.
        @type theStr: string
        @return: sum of ASCII values as checksum
        @rtype: int
        '''
        return reduce(lambda x,y:x+y, map(ord, theStr))
            
            
    def measurePerformance(self, csvFilePath, dbFilePath, arity, tokenFilePaths, verbosity=Verbosity.NONE, removeStopwords=False):
        '''
        Token files must hold a string as produced by the Stanford NLP core 
        tokenizer/sentence segmenter. Ex: "[foo, bar, fum]". Notice the ',<space>'
        after each token. That is the token separator.
        
        Assumed that db file is accessible for reading, that csv file can be
        opened/created for output, and that the token file paths are accessible
        for reading.
        
        @param csvFilePath: path to which to write the sentence-by-sentence CSV lines
        @type csvFilePath: string
        @param dbFilePath: path to the Bigram/Trigram probabilities table Sqlite3 db to use
        @type dbFilePath: sting
        @param arity: arity of ngrams to use in the trees
        @type arity: int
        @param tokenFilePaths: fully qualified paths to each token file.
        @type tokenFilePaths: string
        @param verbosity: if Verbosity.NONE: silent; if Verbosity.LOG: msg every 10 sentences. For debugging: Verbosity.DEBUG
        @type verbose: Verbosity
        @param removeStopwords: whether or not to remove ngrams with stopwords from the echo trees
        @type  removeStopwords: boolean
        @return: Average of depth-weighted performance of all sentences
        @rtype: float.
        '''
        if verbosity > 0:
            numSentencesDone = 0;
            reportEvery = 10; # progress every 10 sentences
            # Be debug level verbose:
            if verbosity > 1:
                self.verbosity = verbosity;
            
        self.arity = arity;
        
        self.initWordCaptureTally();
        for tokenFilePath in tokenFilePaths:
            msgID = self.checksum(tokenFilePath);
            sentenceID = 0;
            with open(tokenFilePath, 'r') as tokenFD:
                while 1:
                    pythonSentenceTokens = self.readSentence(tokenFD);
                    if self.verbosity == Verbosity.DEBUG:
                        print("Sentence %d tokens: %s" % (numSentencesDone,str(pythonSentenceTokens)));
                    if pythonSentenceTokens is None:
                        # Done with one file.
                        break;
                    self.tallyWordCapture(pythonSentenceTokens.split(','), emailID=msgID, sentenceID=sentenceID, removeStopwords=removeStopwords);
                    sentenceID += 1;
                    if self.verbosity != Verbosity.NONE:
                        numSentencesDone += 1;
                        if numSentencesDone % reportEvery == 0:
                            print "At file %s. Done %d sentences." % (os.path.basename(tokenFilePath), numSentencesDone);
                            
        with open(csvFilePath,'w') as CsvFd:
            csvAll = self.toCSV(outFileFD=CsvFd);
        if self.verbosity == Verbosity.DEBUG:
            print csvAll;
        # Compute mean sentence performance:
        totalPerfDbAndArity = 0.0;
        sentenceID = 0;
        for sentencePerformance in self.performanceTally:
            totalPerfDbAndArity += sentencePerformance.getDepthWeightedSuccessSentence();
            if self.verbosity == Verbosity.DEBUG:
                print("Sentence %d tally: %f" % (sentenceID, sentencePerformance.getDepthWeightedSuccessSentence()));
                sentenceID += 1;
        if self.verbosity == Verbosity.DEBUG:
            print("Total score (sumSentenceScores/numSentences): %f / %d = %f" % (totalPerfDbAndArity, 
                                                                                  len(self.performanceTally), 
                                                                                  totalPerfDbAndArity/len(self.performanceTally)));
        return totalPerfDbAndArity/len(self.performanceTally)

# ---------------------------------- Running and Testing ------------------------------------

if __name__ == '__main__':
    
    import os;
    import sys;
#    from subprocess import call;

    parser = argparse.ArgumentParser(prog='echo_tree_evaluator');
    
    
    parser.add_argument("-v", "--verbose, help=print operational info to console.", 
                        dest='verbose',
                        action='store_true');
    
    parser.add_argument("-r", "--removeStopwords, help=if present, will remove stopwords from input text.", 
                        dest='remStopwords',
                        action='store_true');
        
    parser.add_argument('csvFilePath', 
                        type=argparse.FileType('w'),
                        default=sys.stdout,
                        help="fully qualified name of target csv file."
                        )

    parser.add_argument('dbFilePath', 
                        type=argparse.FileType('r'),
                        help="fully qualified name of SQLite db file to use."
                        )
    
    parser.add_argument('arity', 
                        type=int,
                        help="Arity of ngrams to use (2 or 3)."
                        )
    
    parser.add_argument('tokenFilePaths', 
                        nargs='+', 
                        type=argparse.FileType('r'),
                        help="List of tokenfiles to use for measurements.",
                        );
    
    args = parser.parse_args();
    # The parser opens all the files, which is great, because that
    # tests whether files are accessible. But the Evaluator class is written
    # to do the opening itself. So, close everything, now that we know all
    # is good:
    args.csvFilePath.close();
    args.dbFilePath.close();
    tokenFilePaths = [];
    for fd in args.tokenFilePaths:
        fd.close();
        tokenFilePaths.append(fd.name);
    
    if (args.arity != 2) and (args.arity != 3):
        print("Error: Ngram arity must currently be either 2 or 3.");
        sys.exit();
    
    if args.verbose:
        verbosity = Verbosity.LOG;
    else:
        verbosity = Verbosity.NONE;
        
    evaluator = Evaluator(args.dbFilePath.name);
    evaluator.measurePerformance(args.csvFilePath.name, 
                                 args.dbFilePath.name, 
                                 args.arity,
                                 tokenFilePaths,
                                 verbosity=verbosity,
                                 removeStopwords=args.remStopwords
                                 );  
    
    sys.exit();
        
        
    dbPath = os.path.join(os.path.realpath(os.path.dirname(__file__)), "../Resources/EnronCollectionProcessed/EnronDB/enronDB.db");
    evaluator = Evaluator(dbPath);
    thisFileDir = os.path.realpath(os.path.dirname(__file__));
    try:
        stacksPos = thisFileDir.index("stacks")
    except ValueError:
        print "The 'stacks' directory not found above this file (that you're running). Assuming source tree of echo_tree_sentence_seg to be under stacks.";
        sys.exit();

    stacksDir = thisFileDir[0:stacksPos + len('stacks')];
    emailTokenizerDir = stacksDir + "/echo_tree_sentence_seg/src/EchoTreeTextProcessingJava/target";  
    tokensTargetDir = stacksDir + '/echo_tree/src/echo_tree/Resources/EmailEchoTreeOverlapTests/EmailMsgTokens/';
    emailsSourceDir = stacksDir + '/echo_tree/src/echo_tree/Resources/EmailEchoTreeOverlapTests/EmailMsgs/';
    fullPathEmailFileList = []; 
    for fileName in os.listdir(emailsSourceDir):
        fullPathEmailFileList.append(os.path.join(emailsSourceDir, fileName));
    
    # To run, rather than test, uncomment from here...
    evaluator.initWordCaptureTally();
    tokens = "this, demonstrates, a, couple, things, ;, it, appears, to, be, disruptive, technology, -LRB-, but, i, need, to, demo, it, to, be, sure, -RRB-, ;, it, shows, how, products, for, the, disabled, can, lead, t0, commercial, products, for, the, general, population, ;, it, really, stresses, how, technology, is, an, anti, dote, for, depression, among, the, disabled, ;, it, does, not, require, HEAD, movement, ,, only, EYE, some, draw, backs, ;, it, only, works, with, Windows, -LRB-, UGH, -RRB-, it, still, requires, a, computer, screen, 18, '', in, front, of, your, face, i, doubt, it, is, faster, than, my, current, headtracker, or, more, precise, -LRB-, but, i, need, to, play, with, one, to, be, sure, -RRB-".split(', '); 
    #tokens = ['this','demonstrates','a','couple','things'];
    evaluator.tallyWordCapture(tokens);
    print evaluator.performanceTally[0].toString();
    print evaluator.toCSV(); 
    
    # ... to here (running for real, rather than tests.)

    
#    # The automatic invocation of the Java based tokenizer isn't working. Get mangling of file names.
#    # Instead, run the following in a terminal:
#    #     java -jar emailTokenizer.jar foo ~/fuerte/stacks/echo_tree/src/echo_tree/Resources/EmailEchoTreeOverlapTests/EmailMsgTokens/ 
#    #                                      ~/fuerte/stacks/echo_tree/src/echo_tree/Resources/EmailEchoTreeOverlapTests/EmailMsgs/*.txt
#    # That will take files in Resource's EmailEchoTreeOverlapTests/EmailMsgs, tokenize them, and deposit token files
#    # in  ~/fuerte/stacks/echo_tree/src/echo_tree/Resources/EmailEchoTreeOverlapTests/EmailTokens with _Tokens added to
#    # the basename.
     
#    # The Java arg, and the jar name:
#    sysCallArgs = ['java', '-jar', emailTokenizerDir + '/emailTokenizer.jar'];
#    sysCallArgs.append(tokensTargetDir);
#    sysCallArgs.extend(fullPathEmailFileList);
#    
#    print str(sysCallArgs);
#    
#    call(sysCallArgs);
    
    # Unit tests:

#    from unittest import TestCase;
#    import unittest;
#    
#    class Tests(TestCase):
#        
#        def testSentenceRead(self):
#            # Test sentence reader:
#            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)),
#                                    '../Resources/tokenReaderTest.txt'))  as fd:
#                sentence = evaluator.readSentence(fd);
#                self.assertEqual(sentence, '[here,and,there]', "Sentence getting failed. Is %s" % sentence);
#                
#                sentence = evaluator.readSentence(fd);
#                self.assertEqual(sentence, '[,,,]', "Sentence getting failed. Is %s" % sentence);
#        
#                sentence = evaluator.readSentence(fd);
#                self.assertEqual(sentence, '[foo]', "Sentence getting failed. Is %s" % sentence);
#
#                sentence = evaluator.readSentence(fd);
#                self.assertEqual(sentence, '[]', "Sentence getting failed. Is %s" % sentence);
#
#                sentence = evaluator.readSentence(fd);
#                self.assertEqual(sentence, '[bar]', "Sentence getting failed. Is %s" % sentence);

#    testJson = '{"word": "reliability", "followWordObjs": [{"word": "new", "followWordObjs": [{"word": "power", "followWordObjs": []}, {"word": "generation", "followWordObjs": []}, {"word": "business", "followWordObjs": []}, {"word": "product", "followWordObjs": []}, {"word": "company", "followWordObjs": []}]}, {"word": "issues", "followWordObjs": [{"word": "related", "followWordObjs": []}, {"word": "need", "followWordObjs": []}, {"word": "raised", "followWordObjs": []}, {"word": "such", "followWordObjs": []}, {"word": "addressed", "followWordObjs": []}]}, {"word": "legislation", "followWordObjs": [{"word": "passed", "followWordObjs": []}, {"word": "allow", "followWordObjs": []}, {"word": "introduced", "followWordObjs": []}, {"word": "require", "followWordObjs": []}, {"word": "provide", "followWordObjs": []}]}, {"word": "standards", "followWordObjs": [{"word": "conduct", "followWordObjs": []}, {"word": "set", "followWordObjs": []}, {"word": "needed", "followWordObjs": []}, {"word": "facilitate", "followWordObjs": []}, {"word": "required", "followWordObjs": []}]}, {"word": "problems", "followWordObjs": [{"word": "please", "followWordObjs": []}, {"word": "California", "followWordObjs": []}, {"word": "accessing", "followWordObjs": []}, {"word": "arise", "followWordObjs": []}, {"word": "occur", "followWordObjs": []}]}]}';
    
#    # Sentences
#    sentences = evaluator.extractWordSeqs(testJson);
#    # Root word:
#    print sentences.popleft();
#    indents=[1,2,3,4];
#    for i,wordDict in enumerate(reversed(sentences)):
#        indent = indents[0];
#        parentWord =  wordDict.keys()[0];
#        print '\t'*indent + parentWord;
#        for word in reversed(wordDict[parentWord]):
#            indent = indents[1];
#            print '\t'*indent + word;
#            
#    # Sentence generation:
#    sentences = evaluator.extractWordSeqs(testJson);
#    print str(sentences);
#    print str(evaluator.extractWordSet(testJson));
#   
#    # Different-sized trees: 
#    from echo_tree.echo_tree import WordExplorer; 
#    wordExplorer = WordExplorer(dbPath);
#    deepTree = wordExplorer.makeWordTree('reliability', maxDepth=4);
#    deepJson = wordExplorer.makeJSONTree(deepTree);
#    deepSentences = evaluator.extractWordSeqs(deepJson);
#    print str(deepSentences);
#    
#    broadTree = wordExplorer.makeWordTree('reliability', maxBranch=6);
#    broadJson = wordExplorer.makeJSONTree(broadTree);
#    broadSentences = evaluator.extractWordSeqs(broadJson);
#    print str(broadSentences);
    
    # Depth measures for words:
#    pythonTree = json.loads(testJson);
#    print (str(pythonTree)); 
#    depth = evaluator.getDepthFromWord(pythonTree, 'reliability');
#    print str(depth) # 0
#    depth = evaluator.getDepthFromWord(pythonTree, 'new');
#    print str(depth); # 1
#    depth = evaluator.getDepthFromWord(pythonTree, 'product');
#    print str(depth); # 2
#    depth = evaluator.getDepthFromWord(pythonTree, 'issues');
#    print str(depth); # 1
#    depth = evaluator.getDepthFromWord(pythonTree, 'occur');
#    print str(depth); # 2
#    depth = evaluator.getDepthFromWord(pythonTree, 'foo');
#    print str(depth); # None
#
#unittest.main();