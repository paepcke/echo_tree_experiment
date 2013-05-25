#!/usr/bin/env python

import os;

import sqlite3;
import json;
from collections import OrderedDict;

'''
Module for generating word tree datastructures from an underlying
database of co-occurrence data in a collection. Provides both 
Python and JSON results.
'''

WORD_TREE_BREADTH = 5;
WORD_TREE_DEPTH   = 3;

class ARITY:
    BIGRAM  = 2;
    TRIGRAM = 3;

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

# ------------------------------- class Word Database ---------------------
class WordDatabase(object):
    '''
    Service class to wrap an underlying SQLite database file.socket
    '''
    
    def __init__(self, SQLiteDbPath):
        '''
        Open an SQLite connection to the underlying SQLite database file: 
        @param SQLiteDbPath: SQLite database file.
        @type SQLiteDbPath: string
        '''
        self.dbPath = SQLiteDbPath;
        try:
            self.conn   = sqlite3.connect(self.dbPath);
        except Exception as e:
            raise IOError(`e` + ": %s" % self.dbPath);
        
    def close(self):
        pass;
    
# ------------------------------- class Word Follower ---------------------
class WordFollower(object):
    '''
    Provides a 'with' facility for database cursors. Used by
    methods of class WordExplorer to treat db cursors as
    tuple generators that close the cursor even after
    exceptions. See Python contextmanager.
    '''

    def __init__(self, db, word, arity):
        '''
        Provides a tuple generator, given a WordDatabase instance 
        that accesses a word co-occurrence file, a root word, and the
        ngram arity. The latter is needed to select the proper table.
        @param db: WordDatabase instance that wraps an SQLite co-occurrence file.
        @type db: WordDatabase
        @param word: Root word, whose follower words are to be found.
        @type word: string
        @param arity: the 'n' in ngram. 2 for bigram, 3 for trigrams, etc.
        @type arity: ARITY
        '''
        self.db   = db;
        self.word = word;
        self.arity = arity;
        
    def __enter__(self):
        '''
        Method required by contextmanager. Create a new cursor,
        then initializes a tuple stream <followerWord><count>.
        @return: initialized database cursor.
        @rtype: sqlite3.cursor
        '''
        self.cursor = self.db.conn.cursor();
        # The *1 converts the followingCount value to an int. 
        # Necessary so that the ordering isn't alpha. This even
        # though the followingCount is declared as int:
        try:
            if self.arity == ARITY.BIGRAM:
                self.cursor.execute('SELECT word2 from Bigrams where word1="%s" ORDER BY probability*1 desc;' % self.word.encode('ascii', 'ignore'));
            elif self.arity == ARITY.TRIGRAM:
                self.cursor.execute('SELECT word2,word3 from Trigrams where word1="%s" ORDER BY probability*1 desc;' % self.word.encode('ascii', 'ignore'));
            else:
                raise ValueError("WordFollower for arity %d is not implemented." % self.arity);
        except sqlite3.OperationalError as e:
            raise ValueError("SELECT statement failed for word '%s' in database '%s': %s" % (self.word, self.db.dbPath, `e`));
            
        # Return iterator:
        return self.cursor;
    
    def __exit__(self, excType, excValue, traceback):
        '''
        Method required by contextmanager. Closes cursor. Called automatically
        when 'with' clause goes out of scope, naturally, or via an exception. 
        @param excType: Exception type if an exception occurred, or None.
        @type excType: string?
        @param excValue: Exception object if an exception occurred, or None.
        @type excValue: Exception
        @param traceback: Traceback object if an exception occurred, or None.
        @type traceback: traceback.
        '''
        if excType is not None:
            # Don't do anything special if 
            # exception occurred in the caller's with clause:
            pass;
        self.cursor.close();
        
# ------------------------------- class Word Explorer ---------------------        
class WordExplorer(object):
    '''
    Main class. Provides extraction of a frequency ordered JSON
    structure, given a source word and an underlying co-occurrence database.
    Python structures are recursive, as are the corresponding JSON structures:
    WordTree := {"word" : <rootWord>,"followWordObjs" : [WordTree1, WordTree2, ...]}
    '''
    
    def __init__(self, dbPath):
        '''
        Create new WordExplorer that can be used for multiple tree creation requests.
        @param dbPath: Path to SQLite word co-occurrence file.
        @type dbPath: string
        '''
        self.cache = {};
        self.db = WordDatabase(dbPath);
        # Cache needs to be invalidated when we change arity,
        # or when we change db (see getSortedFollowers(), and setDb()):
        self.arityInCache = None

    def getSortedFollowers(self, word, arity):
        '''
        Return an array of follow-words for the given root word.
        The array is sorted by decreasing frequency. A cache
        is maintained to speed requests for root words after
        their first use, which must turn to the database. All
        After the first request, follow-ons will therefore be fast.   
        @param word: root word for the new WordTree.
        @type word: string
        @param arity: the 'n' in ngram. 2 for bigram, 3 for trigram, etc.
        @type arity: ARITY
        @raise ValueError: if language model database access fails  
        '''

        try:
            if self.arityInCache is not None:
                # Is arity in this call different than 
                # the arity with which we built the cache?
                if arity != self.arityInCache:
                    self.cache = {};
            self.arityInCache = arity;
            wordArr = self.cache[word];
        except KeyError:
            # Not cached yet:
            wordArr = []; 
            with WordFollower(self.db, word, arity) as followers:
                for followerWordPlusCount in followers:
                    wordArr.append(followerWordPlusCount);
            self.cache[word] = wordArr;
        return wordArr;


    def setDb(self, newDbPath):
        # New db invalidates our cache:
        self.cache = {};
        self.db = WordDatabase(newDbPath);
      
    def makeWordTree(self, wordArr, arity, wordTree=None, maxDepth=WORD_TREE_DEPTH, maxBranch=WORD_TREE_BREADTH):
        '''
        Return a Python WordTree structure in which the
        followWordObjs are sorted by decreasing frequency. This
        method is recursive, and is the main purpose of this class.
        @param wordArr: root word(s) for the new WordTree. For the first call,
                        which will start the recursion, this parm is a single
                        word. For all calls from recursion, this parm is an
                        array of strings: the words that follow. The array is
                        of len 1 for bigrams (only one follow-on word), 2 for
                        trigrams, etc.
        @type wordArr: {string | [string]}
        @param arity: the 'n' in ngram. 2 for bigram, 3 for trigram, etc.
        @type arity: ARITY
        @param wordTree: Dictionary to use for one 'word'/'followWordObjs.
        @type wordTree: {}
        @param maxDepth: How deep the tree should grow, that is how far along a 
                         word-follows chain the recursion should proceed.
        @type maxDepth: int
        @param maxBranch: max breadth of each branch. I.e. how many of a word's followWords are pursued.
                          The followWords chosen are by frequency with which the followWord follows
                          the respective word (content of parm word).
        @type maxBranch: int
        @return: new EchoTree Python structure
        @rtype: string
        @raise ValueError: if language model database access fails  
        '''
        # Recursion bottomed out:
        if maxDepth <= 0:
            return wordTree;
        if wordTree is None:
            # Use OrderedDict so that conversions to JSON show the 'word' key first:
            wordTree = OrderedDict();
            # First call; wordArr is allowed to be a string, rather than a strArray:
            wordTree['word'] = wordArr;
            wordArr = [wordArr]
        else:
            # We either have ('foo') or (foo,bar)
            if len(wordArr) == 1:
                flattenedFirstTerm = wordArr[0];
            else:
                flattenedFirstTerm = ' '.join(wordArr)
            wordTree['word'] = flattenedFirstTerm;
        # wordArr is a tuple, the 'list' below turns it
        # into an array, to which we can append:
        wordTree['followWordObjs'] = [];
        
        # Tree already as deep as it should be?: root word plus all the follow words:
        if 1 + len(wordTree['followWordObjs']) >= maxDepth:
            return wordTree
        # No, not deep enough. Compute another ngram from the last word:
        
        for i,followerWords in enumerate(self.getSortedFollowers(wordArr[-1], arity)):
            # followerWords is now in the form: (word1,word1.2), with
            # the number of words in each depending on the ngram arity. Bigrams: length 1,
            # trigrams, length 2, etc. for ngrams of order >2 we contract the whole ngram
            # into one string, as if it were the follower in a bigram. The next follower
            # is always computed on the last word.
            
            # Curtail the tree breadth, i.e. number of follow words we pursue:
            if i >= maxBranch:
                return wordTree;
            # Each member of the followWordOjbs array is its own tree:
            followerTree = OrderedDict();
            newSubtree = self.makeWordTree(followerWords, arity, wordTree=followerTree, maxDepth=maxDepth-1);
            # Don't enter empty dictionaries into the array:
            if len(newSubtree) > 0:
                wordTree['followWordObjs'].append(newSubtree);
                
        return wordTree;
    
    def makeJSONTree(self, wordTree):
        '''
        Given a WordTree structure created by makeWordTree, return
        an equivalent JSON tree.
        @param wordTree: Word tree structure emanating from a root word.
        @type wordTree: {}
        '''
        return json.dumps(wordTree);
      
   
    def printWordTree(self, wordTree, treeDepth, currentStr=None, currDepth=0):
        rootWord = wordTree['word'];
        followers = wordTree['followWordObjs'];
        if currentStr is None:
            # New ngram:
            currentStr = [];
        currentStr.append(rootWord);
        for wordNode in followers:
            currentStr = self.printWordTree(wordNode, treeDepth, currentStr=currentStr, currDepth=currDepth+1);
        # If we climbed out of recursion, it's time to print
        # what we collected:
        if currDepth == treeDepth:
            print ' '.join(currentStr);
        return currentStr[0:currDepth];
        
# ----------------------------   Testing   ----------------

if __name__ == "__main__":
    
    #dbPath = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/testDb.db");
    #dbPath = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/EnronCollectionProcessed/EnronDB/enronDB.db");
    #dbPath = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/dmozRecreation.db");
    dbPath = os.path.join(os.path.realpath(os.path.dirname(__file__)), "Resources/henryBlog.db");
    
#    db = WordDatabase(dbPath);
#    with WordFollower(db, 'ant') as followers:
#        for followerWord in followers:
#            print followerWord;
    
    explorer = WordExplorer(dbPath);
    
    #print explorer.getSortedFollowers('my');
#    jsonTree = explorer.makeJSONTree(explorer.makeWordTree('reliability', ARITY.BIGRAM));
#    print jsonTree;
    
#    explorer = WordExplorer(dbPath);    
#    wordTree = explorer.makeWordTree('reliability', ARITY.TRIGRAM);
#    print str(wordTree)
#    jsonTree = explorer.makeJSONTree(wordTree);
#    explorer.printWordTree(wordTree, 3);
#    print jsonTree;

    explorer = WordExplorer(dbPath);    
    wordTree = explorer.makeWordTree('secluded', ARITY.TRIGRAM);
    print str(wordTree)
    jsonTree = explorer.makeJSONTree(wordTree);
    explorer.printWordTree(wordTree, 3);
    print jsonTree;

    
#    explorer = WordExplorer(dbPath);
#    wordTree = explorer.makeWordTree('reliability', ARITY.BIGRAM);
#    print str(wordTree)
#    jsonTree = explorer.makeJSONTree(wordTree);
#    explorer.printWordTree(wordTree, 2);
#    print jsonTree;
    
    exit();
    
#    print explorer.getSortedFollowers('ant');
#    print explorer.getSortedFollowers('echo');
#    # Cache works? (put breakpoint in getSortedFollowers try: statement to check):
#    print explorer.getSortedFollowers('ant');
            
#    print explorer.makeWordTree('ant');
#    print explorer.makeWordTree('echo');

    jsonTree = explorer.makeJSONTree(explorer.makeWordTree('echo'));
    print jsonTree;
    