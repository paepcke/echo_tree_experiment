#!/usr/bin/env python

import sys
import argparse
import echo_tree_experiment_server
from echo_tree_experiment_server import EchoTreeLogService
from echo_tree_experiment_server import LoadedParticipants
from echo_tree_experiment_server import Participant


def listParticipantDetails(participant):
    print("\tRoles played: %s" % str(participant.getRoles()))
    print("\tConditions  : %s" % str(participant.getConditions()))
    print("\tPlaymates   : %s" % str(participant.getPlaymates()))

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(prog='listParticipants')
    parser.add_argument("-v", "--verbose, help=include details about each participant.", 
                        dest='verbose',
                        action='store_true');
    
    
    args = parser.parse_args();
    if args.verbose:
        verbose = True;
    else:
        verbose = False;
    
    if len(sys.argv) > 2:
        print("Usage listParticipants [-v | --verbose]")
        sys.exit(1)
    
    with LoadedParticipants():
        playerIDs = EchoTreeLogService.participantDict.keys();
        for playerID in playerIDs:
            try:
                participant = EchoTreeLogService.participantDict[playerID];
                print(participant.getParticipantID());
                if verbose:
                    listParticipantDetails(participant);
            except KeyError:
                print("Player ID '%s' does not exist. Continuing." % playerID)
    print("Done.")