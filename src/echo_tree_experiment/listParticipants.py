#!/usr/bin/env python

import sys
import argparse
import echo_tree_experiment_server
from echo_tree_experiment_server import EchoTreeLogService
from echo_tree_experiment_server import LoadedParticipants
from echo_tree_experiment_server import Participant
from echo_tree_experiment_server import PlayContact


def listParticipantDetails(participant):
    for contact in participant.playContacts:
        print("\tGame with: %s" % str(contact.playmateID));
        print("\t\tParticipant %s had role %s." % (str(participant.getParticipantID()), str(contact.rolePlayed)));
        print("\t\tExperimental condition: %s." % str(contact.condition));

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
