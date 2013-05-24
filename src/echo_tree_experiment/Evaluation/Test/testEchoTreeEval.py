import unittest;
import os;

from echo_tree_experiment.Evaluation.echo_tree_eval import Evaluator;
from echo_tree_experiment.Evaluation.echo_tree_eval import Verbosity;


class TestEchoTreeEval(unittest.TestCase):

    def setUp(self):
        currDir = os.path.dirname(os.path.realpath(__file__));
        self.dbFileName = os.path.join(currDir, "../../Resources/henryBlog.db");
        self.evaluator  = Evaluator(self.dbFileName);
        self.tokenFile  = os.path.join(currDir, "henry_Tokens.txt");
        self.testArity  = 2;

    @unittest.skip("debugging trigrams now")
    def test_bigrams(self):
        self.testArity = 2;
        perfNum = self.evaluator.measurePerformance("/tmp/echoTreeEvalTest.csv",
                                                    self.dbFileName,
                                                    self.testArity,
                                                    [self.tokenFile],
                                                    verbosity=Verbosity.DEBUG
                                                    );  
        self.assertEqual(0.373015873015873, perfNum);

    def test_trigrams(self):
        self.testArity = 3;
        perfNum = self.evaluator.measurePerformance("/tmp/echoTreeEvalTest.csv",
                                                    self.dbFileName,
                                                    self.testArity,
                                                    [self.tokenFile],
                                                    verbosity=Verbosity.DEBUG
                                                    );  
        self.assertEqual(0.373015873015873, perfNum);


        
if __name__ == '__main__':
    unittest.main()
        
