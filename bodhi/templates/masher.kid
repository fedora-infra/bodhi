<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>

<body>
    <blockquote>
        <h1>Masher</h1>
        <b>Mash by tag:</b>
        <table><tr><td py:for="tag in tags"><a py:content="tag" href="${tg.url('/admin/mash_tags/%s' % tag)}"/></td></tr></table>
        <hr/>
        <a href="${tg.url('/admin/lastlog')}">View most recent mash log</a>
        <br/>
        <pre><div id="mashstatus"><h3>${masher_str}</h3></div></pre>
    </blockquote>
</body>
</html>
