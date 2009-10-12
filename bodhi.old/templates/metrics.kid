<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">
<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <script language="javascript" type="text/javascript" src="${tg.url('/static/js/jquery.flot.js')}"></script>
    <script language="javascript" type="text/javascript" src="${tg.url('/static/js/excanvas.js')}"></script>
</head>
<body>
  <center>
    <h1>${title}</h1><br/>
      <div py:for="metric in metrics">
        ${metric.display()}
        <br/><br/>
      </div>
    </center>
</body>
</html>
