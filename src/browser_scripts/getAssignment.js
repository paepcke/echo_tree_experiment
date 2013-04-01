var xmlHttp = null;

function getAssignment() {
    ownEmail   = document.getElementById( "playerName1" ).value;
    otherEmail = document.getElementById( "playerName2" ).value;
    // Remember the emails to save them across the impending load
    // of the disabled.html or partner.html page (20 days expiration):
    setCookie("echoTreeOwnEmail", ownEmail, 20);
    setCookie("echoTreeOtherEmail", otherEmail, 20);
    var Url = "getAssignment?ownEmail=" + ownEmail + "&otherEmail=" + otherEmail;

    xmlHttp = new XMLHttpRequest(); 
    xmlHttp.onreadystatechange = handleAssignmentResponse;
    xmlHttp.open( "GET", Url, true );
    xmlHttp.send( null );
}

function handleAssignmentResponse() {
    if ( xmlHttp.readyState == 4 && xmlHttp.status == 200 )  {
        if (xmlHttp.responseText == "Not found" ) {
	    alert("No assignment received: Not found Web error.");
        }
        else {
	    // Response is the URL to load: disabled.html or partner.html:
	    window.location.assign(xmlHttp.responseText);
        }                    
    }
}

function setCookie(c_name,value,exdays) {
    var exdate=new Date();
    exdate.setDate(exdate.getDate() + exdays);
    var c_value=escape(value) + ((exdays==null) ? "" : "; expires="+exdate.toUTCString());
    document.cookie=c_name + "=" + c_value;
}

function getCookie(c_name)
{
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
