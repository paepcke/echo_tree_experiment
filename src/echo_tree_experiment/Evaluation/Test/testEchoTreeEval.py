import unittest;
import os;

from echo_tree_experiment.Evaluation.echo_tree_eval import Evaluator;
from echo_tree_experiment.Evaluation.echo_tree_eval import Verbosity;
from unittest.case import skip, SkipTest


class TestEchoTreeEval(unittest.TestCase):

    def setUp(self):
        currDir = os.path.dirname(os.path.realpath(__file__));
        self.dbFileName = os.path.join(currDir, "../../Resources/henryBlog.db");
        self.evaluator  = Evaluator(self.dbFileName);
        self.tokenFile  = os.path.join(currDir, "henry_Tokens.txt");
        self.testArity  = 2;

    @SkipTest
    def test_bigrams(self):
        self.testArity = 2;
        perfNum = self.evaluator.measurePerformance("/tmp/echoTreeEvalTestBigrams.csv",
                                                    self.dbFileName,
                                                    self.testArity,
                                                    [self.tokenFile],
                                                    verbosity=Verbosity.DEBUG
                                                    );  
        self.assertEqual(0.373015873015873, perfNum);

        # Check the output file:
        with open("/tmp/echoTreeEvalTestBigrams.csv") as fd:
            spreadsheet = fd.readlines();
            self.assertEquals('EmailID,SentenceID,SentenceLen,Failures,OutofSeq,InputSavings,Depth_1,Depth_2,DepthWeightedScore\n',
                              spreadsheet[0]);
            self.assertEquals('10639,0,10,4,0,25.0,2,3,0.388888888889\n',
                              spreadsheet[1]);
                              
            self.assertEquals('10639,1,15,9,0,16.6666666667,5,0,0.357142857143\n',
                              spreadsheet[2]);

    def test_trigrams(self):
        self.testArity = 3;
        perfNum = self.evaluator.measurePerformance("/tmp/echoTreeEvalTestTrigrams.csv",
                                                    self.dbFileName,
                                                    self.testArity,
                                                    [self.tokenFile],
                                                    verbosity=Verbosity.DEBUG
                                                    );  
        self.assertEqual(0.30753968253968256, perfNum);

        # Check the output file:
        with open("/tmp/echoTreeEvalTestTrigrams.csv") as fd:
            spreadsheet = fd.readlines();
            self.assertEquals('EmailID,SentenceID,SentenceLen,Failures,OutofSeq,InputSavings,Depth_1,Depth_2,DepthWeightedScore\n',
                              spreadsheet[0]);
            self.assertEquals('10639,0,10,6,0,14.2857142857,1,2,0.222222222222\n',
                              spreadsheet[1]);
                              
            self.assertEquals('10639,1,15,8,0,18.8888888889,5,1,0.392857142857\n',
                              spreadsheet[2]);
        
if __name__ == '__main__':
    unittest.main()
        
