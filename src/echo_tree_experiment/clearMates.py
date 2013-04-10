#!/usr/bin/env python

import sys
import echo_tree_experiment_server
from echo_tree_experiment_server import EchoTreeLogService
from echo_tree_experiment_server import LoadedParticipants
from echo_tree_experiment_server import Participant

if __name__ == '__main__':
    
    if len(sys.argv) < 2:
        print("Usage clearMates <playerID1> [<playerID2>...]")
        sys.exit(1)
    
    numClearedMateLists = 0;
    with LoadedParticipants():
        for playerID in sys.argv[1:]:
            try:
                participant = EchoTreeLogService.participantDict[playerID];
                participant.setPlaymates([]);
                EchoTreeLogService.participantDict[playerID] = participant;
                numClearedMateLists += 1;
            except KeyError:
                print("Player ID '%s' does not exist. Continuing." % playerID)
    print("Cleared %d playmate lists." % numClearedMateLists);