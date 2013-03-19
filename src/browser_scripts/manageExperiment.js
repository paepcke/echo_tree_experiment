ExperimentManager = function() {

    this.wsExp;
    var DONT_PROPAGATE = false;
    var NO_WORD_SEPARATOR = false;

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
	    addToTicker(wordToAdd, DONT_PROPAGATE);
	    break;
	case "addLetter":
	    var letterToAdd = cmdArr.shift();
	    if (letterToAdd === undefined)
		return;
	    addToTicker(letterToAdd, DONT_PROPAGATE, NO_WORD_SEPARATOR);
	    break;
	}
    }

    this.onwordadded = function(word) {
	this.send("addWord:" + word);
    }

    this.ontickertyped = function(evt) {
	if (whoami === "disabledRole")
	    expManager.send("addLetter:" + String.fromCharCode(evt.keyCode));
    }			    
    document.getElementById("ticker").onkeypress = this.ontickertyped;

    this.send = function(msgStr) {
	wsExp.send(msgStr);
    }
}

expManager = new ExperimentManager();
expManager.connect();
