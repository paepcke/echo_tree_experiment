newRootWord = function () {
    var newWord = document.getElementById("rootWordInput").value;
    alert(newWord);
}

// Check for browser support:
if(typeof(WebSocket)!=="undefined") {


    // Create a WebSocket connected back to the EchoTree server 
    // where this script came from:
    //var ws = new WebSocket("ws://mono.stanford.edu:5004/subscribe_to_echo_trees");
    var ws = new WebSocket("ws://localhost:5004/subscribe_to_echo_trees");

    ws.onopen = function () {
	alert("About to send.");
	//ws.send(JSON.stringify(subscribeCmd));
	ws.send(JSON.stringify(newWordCmd));
    };

    ws.onerror = function () {
	alert('ERROR: ' + evt.data);
    };

    ws.onmessage = function (event) {
	try {
	    if (event.data.length == 0)
		return;
	    root = eval("(" + event.data + ")");
	} catch(err) {
	    return;
	}
	root.x0 = h / 2;
	root.y0 = 0;
	
	// As default, start with tree collapsed.
	// Obviously can change this in the future.
	function collapse(d) {
	    if (d.followWordObjs) {
		if (d.followWordObjs.length > 0) {
		    d.followWordObjs.forEach(collapse);
		    d.children = null;
		}
	    }
	}
	
	// Children are visible, followWordObjs are not.
	// Expand turns everything into children.
	function expand(d) {
	    //console.log('expanding ' + d.word);
	    if (d.followWordObjs) {
		if (d.followWordObjs.length > 0) {
		    //console.log(' * expanding fwos')
		    d.children = d.followWordObjs;
		    d.followWordObjs = null;
		    d.children.forEach(expand)
		}
	    }
	    
	    if (d.children) {
		if (d.children.length > 0) {
		    d.children.forEach(expand)
		}
	    }
	}
	
	root.followWordObjs.forEach(expand);
	toggle(root);
	update(root);
    };


} else {
    // WebSockets not supported in this browser:
    document.getElementById("userMsg").innerHTML="Whoops! Your browser doesn't support WebSockets.";
}
subscribeCmd = {'command':'subscribe','submitter':'me@google', 'subscriber':'you@google', 'treeType':'google'};
newWordCmd   = {'command':'newRootWord','submitter':'me@google', 'word':'foolish', 'treeType':'dmozRecreation'};
