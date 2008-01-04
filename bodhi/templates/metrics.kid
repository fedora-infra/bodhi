<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
-    <script language="javascript" type="text/javascript" src="${tg.url('/static/js/jquery.flot.js')}"></script>
</head>
<body>
    <center>

        <h2>Fedora 7 Updates</h2>
        ${all.display()}

        <h2>Security updates per month</h2>
        ${security.display()}

        <h2>Most updates per package</h2>
        ${most_updates.display()}

        <h2>Most updates per developer</h2>
        ${active_devs.display()}

        <h2>Packages with the best karma</h2>
        ${best_karma.display()}

    </center>
</body>
</html>
