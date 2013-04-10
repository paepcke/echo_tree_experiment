
function setCookie(c_name,value,exdays) {
    var exdate=new Date();
    exdate.setDate(exdate.getDate() + exdays);
    var c_value=escape(value) + ((exdays==null) ? "" : "; expires="+exdate.toUTCString());
    document.cookie=c_name + "=" + c_value;
}

function ExperimentManager () {

    var that = this;

    // Class vars:
    ExperimentManager.prototype.DONT_PROPAGATE = false;
    ExperimentManager.prototype.DO_PROPAGATE = true;
    ExperimentManager.prototype.NO_APPEND = false;
    ExperimentManager.prototype.DO_APPEND = true;
    ExperimentManager.prototype.DONT_PREPEND_DELIMITER = false;
    ExperimentManager.prototype.DO_PREPEND_DELIMITER = true;

    // Instance vars:
    var wsExp = undefined;
    var ASCII_BACKSPACE = 8;
    var ASCII_SPACE = 32;
    var ASCII_Z = 90;
    var ASCII_DEL = 126;

    // Chars separating msg operators from args:
    var OP_CODE_SEPARATOR = '>';
    // Char separating multiple msg args:
    var ARGS_SEPARATOR    = '|';

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
		// Experiment server closed ws. Likely due to a
		// restart:
		window.location = "http://" + CONTACT_MACHINE + ":" + EXPERIMENT_FRONT_PAGE_PORT;
		this.showMsg("Experiment server closed our connection. Please log in again. Sorry for the inconvenience!");
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
	var cmdArr = cmdStr.split(OP_CODE_SEPARATOR);
	cmdOp = cmdArr.shift();

	switch (cmdOp) {
	case "test":
	    //alert("Got test message");
	    wsExp.send("test" + OP_CODE_SEPARATOR + " " + whoami + " got it.");

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
	    //alert("Got login prompt.");
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
	    
    	    wsExp.send("login" + OP_CODE_SEPARATOR + "role=" + whoami + 
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
		    addToTicker(wordToAdd, 
				expManager.DONT_PROPAGATE, 
				expManager.DO_APPEND, 
				expManager.DONT_PREPEND_DELIMITER);
		else
		    addToTicker(wordToAdd, 
				expManager.DONT_PROPAGATE, 
				expManager.DO_APPEND, 
				expManager.DO_PREPEND_DELIMITER);
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
		sendNewRootWord("0");
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
	case "newAssignment":
	    // Get ownEmail|otherEmail|URLToLoad|userInstructions

	    var rest = cmdArr.shift();
	    var restFrags = rest.split('|');
	    var ownEmail     = restFrags.shift();
	    var otherEmail   = restFrags.shift();
	    var URLToLoad    = restFrags.shift();
	    var instructions = restFrags.shift();
	    // Remember the emails to save them across the impending load
	    // of the disabled.html or partner.html page (20 days expiration):
	    //****?setCookie("echoTreeOwnEmail", ownEmail, 20);
	    //****?setCookie("echoTreeOtherEmail", otherEmail, 20);

	    if (whoami === 'disabledRole') {
		whoami = 'partnerRole';
	    } else {
		whoami = 'disabledRole';
	    }
	    // onunload is bound to onunload() from the
	    // previous game. Disable that function, so that
	    // loading the next page won't immediately close
	    // the WebSocket:
	    window.onunload = undefined;

	    // Show the instructions to the user:
	    this.showMsg(instructions);

	    // Cleanly disconnect:
	    wsExp.close();
	    // Load the new UI (disabled or partner page):
	    window.location.assign(URLToLoad);
	    // Next the server will send some instructions to show.
	    break;
	case "goodGuessClicked":
	    this.deliverGoodGuessFeedback();
	    break;
	case "done":
	    this.showMsg("All done. Thank you for your help!");
	    break;
	case "pleaseClose":
	    var closeReason = cmdArr.shift();
	    wsExp.close();
	    window.location = "http://" + CONTACT_MACHINE + ":" + EXPERIMENT_FRONT_PAGE_PORT;
	    if (typeof closeReason !== 'undefined')
		this.showMsg(closeReason)
	    break;
	}
    }

    this.onwordadded = function(word) {
	wsExp.send("addWord" + OP_CODE_SEPARATOR + word);
    }

    this.ontickertyped = function(evt) {
	// Function called when the Web page's ticker
	// is typed to *locally*. This method is not involved
	// when info comes over from the other player.
	
	if (document.getElementById("ticker").readonly)
	    return;
	keyCode = (evt.which || evt.keyCode);

	// Shift key pressed?
	if (evt.shiftKey)
	    try {
		charAsStr = keyCodeToCharShifted[keyCode];
	    } catch(err) {
		return;
	    }
	// No shift key: Get periods, comma, etc. correct:
	else if (keyCode == 8)
	    charAsStr = "0x08";
	else if (keyCode > 46) {
	    charAsStr = keyCodeToCharNoShift[keyCode];
	} else {
	    // The following returns single, one-char string. If the 
	    // key code is non-printable, the string will be empty:
	    charAsStr = String.fromCharCode(keyCode);
	    if (charAsStr.length == 0)
		// Throw away any other non-printables (including arrow keys):
		return;
	}

	// fromCharCode() returns all upper case letters. Convert,
	// unless shift key is pressed:
	if (charAsStr.match(/[A-Z]/) && !evt.shiftKey)
	    charAsStr = charAsStr.toLowerCase();

	// If I'm the disabled player, send letter to partner.
	// The typing already placed the letter in the text box,
	// so no appending needed.
	addToTicker(charAsStr, 
		    expManager.DO_PROPAGATE, 
		    expManager.NO_APPEND, 
		    expManager.DONT_PREPEND_DELIMITER);
    }

    this.onGoodGuessClicked = function () {
	wsExp.send("goodGuessClicked" + OP_CODE_SEPARATOR);
    }

    this.onParCompleteClicked = function () {
	wsExp.send("parDone" + OP_CODE_SEPARATOR + this.currParID);
    }

    window.onunload = function() {
	// If user hits back button or reload, the browser
	// unloads the page, and then calls this function.
	// Closing the WebSocket gets the experiment server
	// to clean up. The try/catch is relevant b/c
	// in screwy situations, unload happens before
	// wsExp was openend.
	try {
	    wsExp.close();
	} catch (e) {}
	// Used to try and put up an alert(), but that gets blocked during
	// unload.
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


// Keys passed in event.which of event objects are 
// encoded. This table must be used if event.which is
// is greater than ASCII Z (decimal 90). Note that 
// letters always come back in upper-case ASCII. You
// must check event.shiftKey to know whether to translate
// to lower case:
keyCodeToCharNoShift = {8:"Backspace",9:"Tab",13:"Enter",16:"Shift",17:"Ctrl",18:"Alt",19:"Pause/Break",20:"Caps Lock",27:"Esc",32:"Space",33:"Page Up",34:"Page Down",35:"End",36:"Home",37:"Left",38:"Up",39:"Right",40:"Down",45:"Insert",46:"Delete",48:"0",49:"1",50:"2",51:"3",52:"4",53:"5",54:"6",55:"7",56:"8",57:"9",65:"a",66:"b",67:"c",68:"d",69:"e",70:"f",71:"g",72:"h",73:"i",74:"j",75:"k",76:"l",77:"m",78:"n",79:"o",80:"p",81:"q",82:"r",83:"s",84:"t",85:"u",86:"v",87:"w",88:"x",89:"y",90:"z",91:"Windows",93:"Right Click",96:"Numpad 0",97:"Numpad 1",98:"Numpad 2",99:"Numpad 3",100:"Numpad 4",101:"Numpad 5",102:"Numpad 6",103:"Numpad 7",104:"Numpad 8",105:"Numpad 9",106:"Numpad *",107:"Numpad +",109:"Numpad -",110:"Numpad .",111:"Numpad /",112:"F1",113:"F2",114:"F3",115:"F4",116:"F5",117:"F6",118:"F7",119:"F8",120:"F9",121:"F10",122:"F11",123:"F12",144:"Num Lock",145:"Scroll Lock",182:"My Computer",183:"My Calculator",186:";",187:"=",188:",",189:"-",190:".",191:"/",192:"`",219:"[",220:"\\",221:"]",222:"'"};

keyCodeToCharShifted = {49:"!",50:"@",51:"#",52:"$",53:"%",54:"^",55:"&",56:"*",57:"(",58:")",48:")",187:"+",186:":",222:"\"",188:"<",190:">",191:"?",219:"{",221:"}",220:"|"};

for (var i=65;i<91;i++)
    keyCodeToCharShifted[i] = String.fromCharCode(i);

expManager.connect();
