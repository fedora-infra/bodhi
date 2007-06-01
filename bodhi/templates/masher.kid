<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>

<body>

<?python
from bodhi.masher import get_masher
masher = get_masher()
mashlinks = '['
for tag in ('f7-updates', 'f7-updates-testing'):
    mashlinks += ' <a href="' + tg.url('/admin/mash/%s' % tag) + '">%s</a> |' % tag
mashlinks = mashlinks[:-1] + ']'
?>

    <blockquote>
        <h1>Masher</h1>
        <b>Mash Tag:</b> ${XML(mashlinks)}<br/>
        <a href="${tg.url('/admin/masher/lastlog')}">View most recent mash log</a>
        <br/>
        <pre><h3>${masher}</h3></pre>
    </blockquote>
</body>
</html>
