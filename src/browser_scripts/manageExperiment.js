
function ExperimentManager () {

    var that = this;
    var wsExp = undefined;
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
    var myID    = undefined;
    var otherID = undefined;

    this.connect = function() {
	myExpManager = this;
	// Check for browser support:
	if(typeof(WebSocket)!=="undefined") {

	    // CONTACT_MACHINE and EXPERIMENT_CONTACT_PORT are set in echoTreeExperiment.js:
	    wsExp = new WebSocket("ws://" + CONTACT_MACHINE + ":" + EXPERIMENT_CONTACT_PORT + "/echo_tree_experiment");

	    wsExp.onopen = function () {
	    };

	    wsExp.onerror = function (evt) {
		alert('ERROR (evt.data): ' + evt.data);
	    };

	    wsExp.onmessage = function (event) {
		if (event.data.length == 0)
		    return;
		myExpManager.execCmd(event.data);
	    }

	    wsExp.onclose = function(event) {
		//**************
		alert("Experiment server closed ws.");
	    }

	} else {
	    // WebSockets not supported in this browser:
	    document.getElementById("userMsg").innerHTML="Whoops! Your browser doesn't support WebSockets.";
	}
    }

    this.getCookie = function (c_name) {
	var i,x,y,ARRcookies=document.cookie.split(";");
	for (i=0;i<ARRcookies.length;i++)
	{
	    x=ARRcookies[i].substr(0,ARRcookies[i].indexOf("="));
	    y=ARRcookies[i].substr(ARRcookies[i].indexOf("=")+1);
	    x=x.replace(/^\s+|\s+$/g,"");
	    if (x==c_name)
	    {
		return unescape(y);
	    }
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
	    if (msg === undefined) {
		this.logError("No message included in showMsg.");
		return;
	    }
	    this.showMsg(msg);
	    break;
	case "sendLogin":
	    alert("Got login prompt.");
	    var disabledID;
	    var partnerID;
	    if (whoami == 'disabledRole') {
		disabledID = this.getCookie("echoTreeOwnEmail");
		partnerID  = this.getCookie("echoTreeOtherEmail");
		myID       = disabledID;
		otherID    = partnerID;
	    } else {
		disabledID = this.getCookie("echoTreeOtherEmail");
		partnerID  = this.getCookie("echoTreeOwnEmail");
		myID       = partnerID;
		otherID    = disabledID;
		// Partner's ticker tape is readonly:
		document.getElementById('ticker').readOnly=true;
	    }
	    
    	    wsExp.send("login:role=" + whoami + 
    		       " disabledID=" + disabledID + 
    		       " partnerID=" + partnerID);
	    break;
	case "subscribeToTree":
	    // Server wants this browser to subscribe to someone else's tree.
	    // Incoming msg's format: 
	    //   "subscribeToTree:treeCreatorsID|treeType"
	    // If we are not logged into the server, then we don't
	    // know yet what our own ID is. Punt if so:
	    if (myID === undefined) {
		this.logError("Received subscribeToTree before my own ID was known: " + cmdStr);
		return;
	    }
	    // Get the part after the colon:
	    var treeCreatorAndTreeType = cmdArr.shift();
	    treeCreatorTreeTypeArr = treeCreatorAndTreeType.split("|");
	    treeCreator = treeCreatorTreeTypeArr[0];
	    treeType    = treeCreatorTreeTypeArr[1];
	    subscribeToTree(myID, treeCreator, treeType);
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
	    try {
		// The partner ticker tape is readonly, except for
		// chars transmitted from disabled player for echoing
		// at the partner. Temporarily disable readonly:
		if (whoami == 'partnerRole')
		    document.getElementById('ticker').readOnly=false;
		if (wordToAdd.length === 1)
		    addToTicker(wordToAdd, DONT_PROPAGATE, DO_APPEND, DONT_PREPEND_DELIMITER);
		else
		    addToTicker(wordToAdd, DONT_PROPAGATE, DO_APPEND, DO_PREPEND_DELIMITER);
	    } catch (e) {
	    } finally {
		if (whoami == 'partnerRole') {
		    document.getElementById('ticker').readOnly=true;
		}
	    }
	    break;
	case "newPar":
            // On disabled player newPar has form <parID>|<parStr>.
            // On parnter side form is <topicKeyword>. Distinguish here:
	    var parInfo = cmdArr.shift();
	    if (parInfo === undefined) {
		this.logError("No parID or topicKeyword in newPar message.");
		return;
	    }
	    clearTicker();
	    // Collapse the root of the current tree as a poor-man's 
	    // clearing of the tree (I don't have time to figure out how
	    // to clear the tree completely. If no new-root-word message was
	    // ever received, collapse is not yet defined, catch that condition:
	    try {
		collapse(root);
	    } catch(err) {
	    }

	    parIDAndParStr = parInfo.split('|');
	    if (parIDAndParStr.length == 1) {
		// This player is a partner, arg is topic keyword:
		this.showMsg("The next paragraph will loosely be about " + parIDAndParStr[0]);
		return;
	    }
	    // This player plays the disabled party:
	    this.currParID = parIDAndParStr[0];
	    // Show the new text to be entered:
	    document.getElementById("taskText").value= parIDAndParStr[1];
	    this.showMsg("Please start on the new sentence in the top orange box.");
	    break;
	case "goodGuessClicked":
	    this.deliverGoodGuessFeedback();
	    break;
	case "done":
	    this.showMsg("All done. Thank you!");
	    break;
	case "pleaseClose":
	    var closeReason = cmdArr.shift();
	    this.wsExp.close();
	    window.location = "http://" + CONTACT_MACHINE + ":" + EXPERIMENT_FRONT_PAGE_PORT;
	    this.showMsg(closeReason);
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
	
	if (document.getElementById("ticker").readonly)
	    return;

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
	
	// If I'm the disabled player, send letter to partner.
	// The typing already placed the letter in the text box,
	// so no appending needed.
	addToTicker(charAsStr, DO_PROPAGATE, NO_APPEND, DONT_PREPEND_DELIMITER);
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

} // end ExperimentManager

expManager = new ExperimentManager();
// Bind ticker tape's keyboard presses to ontickertyped:
tickerObj = document.getElementById("ticker");
tickerObj.onkeyup=expManager.ontickertyped;
if (whoami === 'disabledRole') {
    document.getElementById("partialDone").onclick=expManager.onGoodGuessClicked;
    document.getElementById("allDone").onclick=expManager.onParCompleteClicked;
} else {
    // Partner's ticker is readonly. This property will
    // be briefly unset when chars from the disabled player
    // arrive, and are to be displayed in the ticker:
    tickerObj.readonly = true;
}

expManager.connect();
