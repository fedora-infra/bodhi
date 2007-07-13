<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">
<head>
    <meta content="text/html; charset=utf-8" http-equiv="Content-Type" py:replace="''"/>
    <title>Fedora Update System</title>
    <link media="all" href="${tg.url('/tg_widgets/turbogears.widgets/grid.css')}" type="text/css" rel="stylesheet"/>
</head>
<body>

<?python
from bodhi.model import PackageUpdate
?>

    <blockquote>
        <h1>Welcome, ${tg.identity.user.display_name}</h1>
        ${now}
        <table cellpadding="5" cellspacing="5">
            <tr>
                <td>
                    <table width="100%">
                        <tr>
                            <td align="right">
                                <img src="${tg.url('/static/images/bodhi-icon-36.png')}" height="36" width="36"/>
                            </td>
                            <td align="left">
                                <a href="http://hosted.fedoraproject.org/projects/bodhi" class="list">Bodhi Project Homepage</a>
                            </td>
                        </tr>
                        <tr>
                            <td align="right">
                                <img src="${tg.url('/static/images/header-faq.png')}" align="middle" border="0" />
                            </td>
                            <td align="left">
                                <a href="http://fedoraproject.org/wiki/Infrastructure/UpdatesSystem/Bodhi-info-DRAFT" class="list">Bodhi workflow and Q&amp;A draft</a>
                            </td>
                        </tr>
                        <tr>
                            <td align="right">
                                <img src="${tg.url('/static/images/header-projects.png')}" border="0" align="middle" alt="Bugs"/>
                            </td>
                            <td align="left">
                                <a href="https://hosted.fedoraproject.org/projects/bodhi/newticket" class="list">File a bug or feature request</a>
                            </td>
                        </tr>
                        <tr>
                            <td align="right">
                                <font size="6">麹</font>
                            </td>
                            <td align="left">
                                <a href="http://koji.fedoraproject.org/koji/" class="list">Koji Buildsystem</a>
                            </td>
                        </tr>
                        <tr>
                            <td align="right">
                                <img src="${tg.url('/static/images/mugshot.png')}" border="0" align="middle" alt="Fedora Infrastructure Mugshot Group"/>
                            </td>
                            <td align="left">
                                <a href="http://mugshot.org/group?who=yWstkV2xGz93rQ" class="list">Join the Fedora Infrastructure Mugshot group</a>
                            </td>
                        </tr>
                        </table>
                    </td>
                    <td valign="top">
                        <div class="tabber">
                            <div class="tabbertab" py:for="title, value in grids.items()">
                                <h2>${title}</h2>
                                <span py:if="value[2]">
                                    ${value[2].display()}
                                </span>
                            </div>
                        </div>
                    </td>
                </tr>
        </table>
    </blockquote>
    <center>
        <a href="http://turbogears.org"><img src="${tg.url('/static/images/under_the_hood_blue.png')}" border="0" /></a>
    </center>
</body>
</html>
