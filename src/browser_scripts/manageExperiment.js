ExperimentManager = function() {

    this.wsExp;
    var DONT_PROPAGATE = false;
    var DO_PROPAGATE = true;
    var NO_APPEND = false;
    var DO_APPEND = true;
    var DONT_PREPEND_DELIMITER = false;
    var DO_PREPEND_DELIMITER = true;
    var ASCII_BACKSPACE = 8;
    var ASCII_SPACE = 32;
    var ASCII_DEL = 126;

    this.connect = function() {
	var expManager = this;
	// Check for browser support:
	if(typeof(WebSocket)!=="undefined") {

	    wsExp = new WebSocket("ws://mono.stanford.edu:5004/echo_tree_experiment");
	    //wsExp = new WebSocket("ws://localhost:5004/echo_tree_experiment");

	    wsExp.onopen = function () {
	    };

	    wsExp.onerror = function () {
		alert('ERROR: ' + evt.data);
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
	    if (msg === undefined)
		return;
	    alert(msg);
	    break;
	case "addWord":
	    var wordToAdd = cmdArr.shift();
	    if (wordToAdd === undefined)
		return;
	    if (wordToAdd.length === 1)
		addToTicker(wordToAdd, DONT_PROPAGATE, DO_APPEND, DONT_PREPEND_DELIMITER);
	    else
		addToTicker(wordToAdd, DONT_PROPAGATE, DO_APPEND, DO_PREPEND_DELIMITER);
	    break;
	case "setTaskText":
	    var textToAdd = cmdArr.shift();
	    if (textToAdd === undefined)
		return;
	    document.getElementById("taskText").value= textToAdd;
	}
    }

    this.onwordadded = function(word) {
	this.send("addWord:" + word);
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

    // Bind ticker tape's keyboard presses to ontickertyped:
    document.getElementById("ticker").onkeyup = this.ontickertyped;

    this.send = function(msgStr) {
	wsExp.send(msgStr);
    }
}

expManager = new ExperimentManager();
expManager.connect();
