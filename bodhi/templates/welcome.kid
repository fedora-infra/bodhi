<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">
<head>
<meta content="text/html; charset=utf-8" http-equiv="Content-Type" py:replace="''"/>
<title>Fedora Update System</title>
</head>
<body>
    <blockquote>
        <h1>Welcome, ${tg.identity.user.display_name}</h1>
        <blockquote>
            <table cellpadding="5" cellspacing="5">
                <tr>
                    <td valign="middle">
                        <a href="http://fedoraproject.org/wiki/Infrastructure/UpdatesSystem/Bodhi-info-DRAFT" class="list"><img src="${tg.url('/static/images/header-faq.png')}" align="middle" border="0" />Bodhi workflow and Q&amp;A draft</a>
                    </td>
                </tr>
                <tr>
                    <td valign="middle">
                        <a href="https://hosted.fedoraproject.org/projects/bodhi/newticket" class="list"><img src="${tg.url('/static/images/header-projects.png')}" border="0" align="middle" alt="Bugs"/>File a bug or feature request</a>
                    </td>
                </tr>
                <tr>
                    <td valign="middle">
                        <a href="http://mugshot.org/group?who=yWstkV2xGz93rQ" class="list"><img src="${tg.url('/static/images/mugshot.png')}" border="0" align="middle" alt="Fedora Infrastructure Mugshot Group"/>Join the Fedora Infrastructure Mugshot group</a>
                    </td>
                </tr>

            </table>
        </blockquote>
    </blockquote>
    <center>
        <a href="http://turbogears.org"><img src="${tg.url('/static/images/under_the_hood_blue.png')}" border="0" /></a>
    </center>
</body>
</html>
