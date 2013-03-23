var wsExp = undefined;

function ExperimentManager () {

    var that = this;
    var DONT_PROPAGATE = false;
    var DO_PROPAGATE = true;
    var NO_APPEND = false;
    var DO_APPEND = true;
    var DONT_PREPEND_DELIMITER = false;
    var DO_PREPEND_DELIMITER = true;
    var ASCII_BACKSPACE = 8;
    var ASCII_SPACE = 32;
    var ASCII_DEL = 126;

    var currParID = -1;

    this.connect = function() {
	var expManager = this;
	// Check for browser support:
	if(typeof(WebSocket)!=="undefined") {

	    wsExp = new WebSocket("ws://mono.stanford.edu:5004/echo_tree_experiment");
	    //wsExp = new WebSocket("ws://localhost:5004/echo_tree_experiment");

	    wsExp.onopen = function () {
	    };

	    wsExp.onerror = function () {
		this.logError('ERROR: ' + evt.data);
	    };

	    wsExp.onmessage = function (event) {
		if (event.data.length == 0)
		    return;
		expManager.execCmd(event.data);
	    }

	} else {
	    // WebSockets not supported in this browser:
	    document.getElementById("userMsg").innerHTML="Whoops! Your browser doesn't support WebSockets.";
	}
    }

    this.login = function() {
	// Log into server:
	//******that.wsExp.send("login:role=" + whoami + 
	wsExp.send("login:role=" + "Andreas" + 
		   " disabledID=" + "****disabled@foo.com" + 
		   " parterID=" + "****partner@bar.com");
    }


    this.execCmd = function(cmdStr) {

	if (cmdStr.length == 0)
	    return;
	var cmdArr = cmdStr.split(":");
	cmdOp = cmdArr.shift();

	switch (cmdOp) {
	case "test":
	    alert("Got test message");
	    wsExp.send("test: " + whoami + " got it.");
	    break;
	case "showMsg":
	    var msg = cmdArr.shift();
	    if (msg === undefined) {
		this.logError("No message included in showMsg.");
		return;
	    }
	    this.showMsg(msg);
	    break;
	case "waitForPlayer":
	    var missingPlayersID = cmdArr.shift();
	    if (missingPlayersID === undefined) {
		this.logError("No missing-player ID provided in waitForPlayer message.");
		return;
	    }
	    this.showMsg("Waiting for player " + missingPlayersID);
	    break;
	case "dyadComplete":
	    this.showMsg("You are both online. Ready to go?");
	    break;
	case "addWord":
	    var wordToAdd = cmdArr.shift();
	    if (wordToAdd === undefined) {
		this.logError("No word provided in addWord message.");
		return;
	    }
	    if (wordToAdd.length === 1)
		addToTicker(wordToAdd, DONT_PROPAGATE, DO_APPEND, DONT_PREPEND_DELIMITER);
	    else
		addToTicker(wordToAdd, DONT_PROPAGATE, DO_APPEND, DO_PREPEND_DELIMITER);
	    break;
	case "newPar":
            // On disabled player newPar has form <parID>|<parStr>.
            // On parnter side form is <topicKeyword>. Distinguish here:
	    var parInfo = cmdArr.shift();
	    if (parInfo === undefined) {
		this.logError("No parID or topicKeyword in newPar message.");
		return;
	    }
	    parIDAndParStr = parInfo.split('|');
	    if (parIDAndParStr.length == 1) {
		// This player is a partner, arg is topic keyword:
		this.showMsg("The next paragraph will loosely be about " + parIDAndParStr[0]);
		return;
	    }
	    currParID = parIDAndParStr[0];
	    document.getElementById("taskText").value= parIDAndParStr[1];
	    break;
	case "goodGuessClicked":
	    this.deliverGoodGuessFeedback();
	    break;
	case "done":
	    this.showMsg("All done. Thank you!");
	    break;
	}
    }

    this.onwordadded = function(word) {
	wsExp.send("addWord:" + word);
    }

    this.ontickertyped = function(evt) {
	// Function called when the Web page's ticker
	// is typed to *locally*. This method is not involved
	// when info comes over from the other player.
	
	// Ascii printable range?
	if (evt.which >= ASCII_SPACE && evt.which < ASCII_DEL) {
	    charAsStr = String.fromCharCode(evt.which);
	    if (! evt.shiftKey)
		// Oddly, chars in the event are upper-case:
		charAsStr = charAsStr.toLowerCase();
	} else if (evt.which === ASCII_BACKSPACE)
	    // If backspace, we encode it as hex 8, which
	    // gets special treatment down the call chain:
	    charAsStr = "0x08";
	else 
	    // Throw away any other non-printables (including arrow keys):
	    return;
	
	if (whoami === "disabledRole")
	    // If I'm the disabled player, send letter to partner.
	    // The typing already place the letter in the text box,
	    // so no appending needed.
	    addToTicker(charAsStr, DO_PROPAGATE, NO_APPEND, DONT_PREPEND_DELIMITER);
	else
	    // Ticker tape is that of the partner: dont' send to disabled player:
	    addToTicker(charAsStr, DONT_PROPAGATE, NO_APPEND, DONT_PREPEND_DELIMITER);
    }

    this.onGoodGuessClicked = function () {
	wsExp.send("goodGuessClicked:");
    }

    this.onParCompleteClicked = function () {
	wsExp.send("parDone:" + this.currParID);
    }

    this.showMsg = function(msg) {
	alert(msg);
    }

    this.deliverGoodGuessFeedback = function() {
	alert("Good guess, 'disabled' player will type more.");
    }

    this.logError = function(msg) {
	alert(msg);
    }

    // Bind ticker tape's keyboard presses to ontickertyped:
    document.getElementById("ticker").onkeyup = this.ontickertyped;
    document.getElementById("partialDone").onclick=this.onGoodGuessClicked;
    document.getElementById("allDone").onclick=this.onParCompleteClicked;

} // end ExperimentManager

expManager = new ExperimentManager();
expManager.connect();
