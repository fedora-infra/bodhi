function remoteFormRequest(form, target, options) {
    var contents = formContents(form);
    //for (var j=0; j<contents[0].length; j++)
    //    query[contents[0][j]] = contents[1][j];
    contents[0].push("tg_random");
    contents[1].push(new Date().getTime());

    //makePOSTRequest(form.action, target, queryString(query));
    remoteRequest(form, form.action, target, contents, options);
    return true;
}

function remoteRequest(source, target_url, target_dom, data, options) {
    //before
    if (options['before']) {
        eval(options['before']);
    }
    if ((!options['confirm']) || confirm(options['confirm'])) {
        makePOSTRequest(source, target_url, getElement(target_dom), queryString(data[0], data[1]), options);
        //after
        if (options['after']) {
            eval(options['after']);
        }
    }
	return true;
}

function makePOSTRequest(source, url, target, parameters, options) {
  var http_request = false;
  if (window.XMLHttpRequest) { // Mozilla, Safari,...
     http_request = new XMLHttpRequest();
     if (http_request.overrideMimeType) {
        http_request.overrideMimeType('text/xml');
     }
  } else if (window.ActiveXObject) { // IE
     try {
        http_request = new ActiveXObject("Msxml2.XMLHTTP");
     } catch (e) {
        try {
           http_request = new ActiveXObject("Microsoft.XMLHTTP");
        } catch (e) {}
     }
  }
  if (!http_request) {
     alert('Cannot create XMLHTTP instance');
     return false;
  }

    var insertContents = function () {
        if (http_request.readyState == 4) {
            // loaded
            if (options['loaded']) {
                eval(options['loaded']);
            }
            if (http_request.status == 200) {
                if(target) {
                    target.innerHTML = http_request.responseText;
                }
                //success
                if (options['on_success']) {
                    eval(options['on_success']);
                }
            } else {
                //failure
                if (options['on_failure']) {
                    eval(options['on_failure']);
                } else {
                    alert('There was a problem with the request. Status('+http_request.status+')');
                }
            }
            //complete
            if (options['on_complete']) {
                eval(options['on_complete']);
            }
        }
    }
  
    http_request.onreadystatechange = insertContents;
    http_request.open('POST', url, true);
    http_request.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    http_request.setRequestHeader("Content-length", parameters.length);
    http_request.setRequestHeader("Connection", "close");
    http_request.send(parameters);
}
