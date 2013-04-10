#!/usr/bin/env python

import sys
import echo_tree_experiment_server
from echo_tree_experiment_server import EchoTreeLogService
from echo_tree_experiment_server import LoadedParticipants
from echo_tree_experiment_server import Participant

if __name__ == '__main__':
    
    if len(sys.argv) != 2:
        print("Usage listPlaymates <playerID>")
        sys.exit(1);
        
    player = sys.argv[1]
    
    with LoadedParticipants():
        try:
            participant = EchoTreeLogService.participantDict[player];
        except KeyError:
            print("Player ID '%s' does not exist." % player)
            exit(1)
           
        playerMates = participant.getPlaymates();
    print("%s playmates: %s" % (player, str(playerMates)));
