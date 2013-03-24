// Dimentions and other core viz elements
var m = [20, 120, 20, 120],
w = 1000 - m[1] - m[3],
h = 600 - m[0] - m[2],
i = 0,
duration = 500,
root;

// Tree Layout
var tree = d3.layout.tree()
    .size([h,w]);

// Function for computing curved edges
var diagonal = d3.svg.diagonal()
    .projection(function(d) { return[d.y, d.x]; });

// Main Canvas
var vis = d3.select("#echotree").append('svg')
    .attr("width", w + m[1] + m[3])
    .attr("height", h + m[0] + m[2])
    .append('g')
    .attr("transform", "translate(" + m[3] + "," + m[0] + ")");


// Check for browser support:
if(typeof(WebSocket)!=="undefined") {


    // Create a WebSocket connected back to the EchoTree server 
    // where this script came from:
    //var ws = new WebSocket("ws://mono.stanford.edu:5004/subscribe_to_echo_trees");
    var ws = new WebSocket("ws://localhost:5004/subscribe_to_echo_trees");

    ws.onopen = function () {
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

function getCookie(c_name) {
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

function update(source) {
    
    // Compute new tree layout.
    var nodes = tree.nodes(root).reverse();
    
    // Compute the depth for each node.
    nodes.forEach(function(d) { d.y = d.depth * 180; });
    
    // Update the nodes.
    var node = vis.selectAll("g.node")
	.data(nodes, function(d) { return d.id || (d.id = ++i); });
    
    // New nodes enter at position of parent.
    var nodeEnter = node.enter().append('g')
	.attr('class', 'node')
	.attr('transform', function(d) { return "translate(" + source.y0 + "," + source.x0 + ")"; })

    //.on("click", toggle);
    //.addEventListener("onmousedown",handleMouseDown,false) //not def
    // Works for Chrome: .on("mousedown", handleMouseDown)
    //.onclick = function(event){handleMouseDown(event, this);};
    //if (nodeEnter.captureEvents) nodeEnter.captureEvents(Event.MOUSEDOWN);
    //****.on("singletap", toggle);
    //***.singletap(toggle).doubletap(function(e) {ws.write("small");});
    //***.on("doubletap", function(e) {ws.write("small");});
    
    // Node circles start tiny and gray.
    nodeEnter.append("circle")
	.attr("r", 1e-6)
	.style("fill", function(d) { return d.children ? "lightsteelblue": "#fff"; })
	.on("mousedown", function(event){handleMouseDown(event, this);});
    // Node text starts invisible.
    nodeEnter.append("text")
	.attr("x", function(d) { return d.children || d.followWordObjs ? -10 : 10; })
	.attr("dy", ".35em")
	.attr("text-anchor", function(d) { return d.children || d.followWordObjs ? "end" : "start";})
	.text(function(d) { return d.word; })
	.style("fill-opacity", 1e-6)
	.attr("class", "label")
	.on("mousedown", function(event){textMouseDown(event, this);})      
    // Transition nodes to new position.
    var nodeUpdate = node.transition()
	.duration(duration)
	.attr("transform", function(d) { return "translate(" + d.y + "," + d.x + ")"; });
    
    // Update node circle
    nodeUpdate.select("circle")
	.attr("r", 6)
	.style("fill", function(d) { return d.followWordObjs ? "lightsteelblue" : "#fff"; });
    
    // Update node label text
    nodeUpdate.select("text")
	.style("fill-opacity", 1);

    // Nodes exit at parent's new position.
    var nodeExit = node.exit().transition()
	.duration(duration)
	.attr("transform", function(d) { return "translate(" + source.y + "," + source.x + ")"; })
	.remove();
    
    // Shrink nodes on exit.
    nodeExit.select("circle")
	.attr("r", 1e-6);
    
    // Fade out node label at exit.
    nodeExit.select("text")
	.style("fill-opacity", 1e-6);
    
    // Update links
    var link = vis.selectAll("path.link")
	.data(tree.links(nodes), function(d) { return d.target.id; });
    
    // Enter new links at parent's previous position.
    link.enter().insert("path", "g")
	.attr("class", "link")
	.attr("d", function(d) {
	    var o = {x: source.x0, y: source.y0};
	    return diagonal({source: o, target: o});
	})
	.transition()
	.duration(duration)
	.attr("d", diagonal);
    
    // Transition links to new position.
    link.transition()
	.duration(duration)
	.attr("d", diagonal);
    
    // Exit nodes via parent's new position.
    link.exit().transition()
	.duration(duration)
	.attr("d", function(d) {
	    var o = {x: source.x, y: source.y};
	    return diagonal({source: o, target: o});
	})
	.remove();
    
    // Stash the old positions for transition.
    nodes.forEach(function(d) {
	d.x0 = d.x;
	d.y0 = d.y;
    });
}


// Take a word from the new word test field, and tell browser to make
// that word into the new root.
function sendNewRootWordFromTxtFld() {
    word = document.getElementById("newWord").value;
    sendNewRootWord(word);
}

// Given a word, tell browser to make that word into the 
// new root. We pass an array whose first val is the new
// root word. The remainder are all the player IDs to whom
// the new tree should be pushed. In this case, both players:
function sendNewRootWord(word) {
    ws.send("newRoot:" + JSON.stringify([word,thisEmail,thatEmail]);
}


// Make ENTER key submit new root word when in text field:
function handleEnterInWordFld(e) {
    if (!e) { var e = window.event; }
    // Enter is pressed?
    if (e.keyCode == 13) { sendNewRootWordFromTxtFld(); }
}


// Handle mouse down events to distinguish between
// left and middle button:
function handleMouseDown(node, el) {
    //alert("Word: " + node.word);
    //alert("Button: " + this.event.which);
    if (this.event.which == 1) // Left click
	ws.send(node.word);
    else if (this.event.which == 2) // Middle click
	toggle(node);
}


// Toggle children on node click.
function toggle(d) {
    
    if (d.children) {
	d.followWordObjs = d.children;
	d.children = null;
    } else {
	d.children = d.followWordObjs;
	d.followWordObjs = null;
    }
    update(d);
}

// Sean Code below
// Class to handle a ticker.

var ticker = function(id, tickerLength, wordDelimiter, maxChars) {
    var el = d3.select("#" + id)
	.style("width", tickerLength + "px");
    
    var t = {}, words = [],
    content = "";

    // addWord()
    // propagate: optional, defaults to true. If set to false, insertion 
    //            of a word into the ticker will not be reported to the
    //            experiment manager. Used to avoid infinite recursion.
    //            Default: true;
    // appendString: if true, the given word is appended to the ticker widget. Otherwise
    //            we assume the ticker already contains the new information (because
    //            the user typed it), and we just have to propagate to the remote
    //            server, or otherwise do bookkeeping:
    // prependDelimiter: if true, the given word is prepended with a delimiter.

    t.addWord = function(word, propagate, appendString, prependDelimiter) {
	propagate = typeof propagate !== 'undefined' ? propagate : true;
	appendString = typeof appendString !== 'undefined' ? appendString : true;
	prependDelimiter = typeof prependDelimiter !== 'undefined' ? prependDelimiter : true;

	words = document.getElementById("ticker").value = content.split();

	// Implement backspace
	if (word === "0x08") {
	    lastWord = words[words.length - 1];
	    words[words.length - 1] = lastWord.slice(0, -1);
	} else if (prependDelimiter)
	    words.push(wordDelimiter.concat(word));
	else
	    words.push(word);

	content = t.arrToContent(words);
	t.update();
	document.getElementById("ticker").value = content;
	//el.value = content;
	if (propagate)
	    expManager.onwordadded(word);
    };

    t.arrToContent = function(wordArray) {
	var newContent = "";
	wordArray.forEach(function(element, index, array) {
	    newContent = newContent.concat(element);
	});
	return newContent;
    }

    t.update = function() {
	el.attr("value", content);
    }
    t.update();
    return t;
};

var wordTicker = ticker("ticker", 500, ' ', 100);

// The color to use for selected labels.
var fillColor = "blue";

// Color the given label element.
// el should be an svg text element
function colorLabel(el, color) {
    d3.select(el)
	.style("fill", color);
}

// Color all labels.
function colorAllLabels(color) {
    d3.selectAll(".label")
	.style("fill", color);
}

// On mouse down, color label, add word to ticker.
function textMouseDown(node, el) {
    colorLabel(el, fillColor);
    if (whoami === "disabledRole")
	addToTicker(node.word);
}

// Add a word to the ticker.
function addToTicker(word, propagate, appendString, prependDelimiter) {
    propagate = typeof propagate !== 'undefined' ? propagate : true;
    appendString = typeof appendString !== 'undefined' ? appendString : true;
    prependDelimiter = typeof prependDelimiter !== 'undefined' ? prependDelimiter : true;
    wordTicker.addWord(word, propagate, appendString, prependDelimiter);
}

// Handle change event on selection widget.
// Only add word from tree to ticker if
// player is the disabled person.
function handleChange(select) {
    addToTicker(select.value);
}

// Handlers for three buttons.
function onCorrect() {
    alert("THATS CORRECT");
}

function onIncorrect() {
    alert("THATS INCORRECT");	
}   

function onRestart() {
    alert("RESTART");
}

// Get player IDs for myself and the other player:
var thisEmail   = this.getCookie("echoTreeThisEmail");
var otherEmail  = this.getCookie("echoTreeOtherEmail");
