#!/bin/bash

# Use Stanford tokenizer to tokenize one or more text files.
# Can ask for tokenization of a single txt file, or a directory
# of .txt files. Optionally: provide output directory. By default
# results are stored in the input directory. All files will have
# '_tokens' appended to their basename.

USAGE="Usage: tokenizeText.sh {textDir | textFile} [targetDir]"

if [ $# -lt 1 ]
then
    echo $USAGE
    exit
fi
 

if [ ! -e $1 ]
then
    echo "No file or directory named '$1' exists."
    exit
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -d $1 ]
then
    # We are to tokenize a whole directory:
    srcFiles=$1/*.txt
    outDir=$1
else
    # Just do an individual file:
    srcFiles=$1
    outDir=$(dirname $1)
fi

if [ $# == 2 ]
then
    outDir=$2
    if [ ! -d $2 ]
    then
	mkdir $2
    fi
fi

#echo "Source: $srcFiles"
#echo "Dest: $outDir"

java -jar $SCRIPT_DIR/emailTokenizer.jar com.willowgarage.echo_tree.EmailTokenizer $outDir $srcFiles
