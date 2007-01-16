<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
        <title>Fedora Updates</title>
</head>

<body>
    <blockquote>
        <h2>Push Console</h2>
        <textarea id="push_console" rows="30" cols="100" wrap="hard"></textarea>
    </blockquote>

    <script lang="javascript">
        function handler(evt){
          //logDebug("onLoad handler");
          var t = evt.target.responseText;
          var console = getElement("push_console");
          console.value += '\n' + t;
          console.scrollTop = console.scrollHeight;
        }
        //createLoggingPane(true);
        //logDebug("Creating new XMLHttpRequest");
        var req = new XMLHttpRequest();
        req.multipart = true;
        req.onload = handler;
        //req.open("GET", "/admin/push/push_updates", true);
        req.open("GET", "${callback}", true);
        req.send(null);
        //logDebug("send req" + req);
   </script>
</body>
</html>
