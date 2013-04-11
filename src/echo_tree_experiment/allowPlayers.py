#!/usr/bin/env python

import sys
import echo_tree_experiment_server
from echo_tree_experiment_server import EchoTreeLogService
from echo_tree_experiment_server import LoadedParticipants
from echo_tree_experiment_server import Participant
from echo_tree_experiment_server import PlayContact

if __name__ == '__main__':
    
    if len(sys.argv) != 3:
        print("Usage allowPlayers <playerID1> <playerID2>")
        sys.exit(1)
        
    player1 = sys.argv[1]
    player2 = sys.argv[2]
    
    with LoadedParticipants():
        try:
            participant1 = EchoTreeLogService.participantDict[player1];
        except KeyError:
            print("Player ID '%s' does not exist." % player1)
            sys.exit(1)
        try:
            participant2 = EchoTreeLogService.participantDict[player2];
        except KeyError:
            print("Player ID '%s' does not exist." % player2)
            sys.exit(1)
           
        delFromP1 = participant1.deleteContactsByPlaymateID(player2);
        delFromP2 = participant2.deleteContactsByPlaymateID(player1);
           
        EchoTreeLogService.participantDict[player1] = participant1;
        EchoTreeLogService.participantDict[player2] = participant2;

    print("Deleted %d occurrences of %s in %s. Deleted %d occurrences of %s in %s." %
          (delFromP1,
           player2,
           player1,
           delFromP2,
           player1,
           player2));
