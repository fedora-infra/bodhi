<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">
<?python from bodhi import version, hostname ?>
<head>
    <meta content="text/html; charset=utf-8" http-equiv="Content-Type" py:replace="''"/>
    <title>Fedora Update System</title>
    <link media="all" href="${tg.url('/tg_widgets/turbogears.widgets/grid.css')}" type="text/css" rel="stylesheet"/>

</head>
<?python
from turbogears import config
koji_url = config.get('koji_url')
?>
<body>
    <table width="90%" align="center" valign="top">
            <tr>
                <td align="left" valign="top"><b><font size="4">Welcome to bodhi v${version}<span py:if="not tg.identity.anonymous">, ${hasattr(tg.identity.user, 'human_name') and tg.identity.user.human_name.split()[0] or tg.identity.user.display_name}</span></font></b></td>
            </tr>
            <tr>
                <td align="left">
                    <ul style="list-style:none;">
                        <li><a href="https://fedoraproject.org/wiki/QA:Update_feedback_guidelines"><img src="${tg.url('/static/images/hardhat.png')}" border="0" height="18" width="18"/> Update feedback guidelines</a></li>
                        <li><a href="https://fedoraproject.org/wiki/Bodhi"><img src="${tg.url('/static/images/info.png')}" border="0" height="18" width="18"/> Bodhi guide</a></li>
                        <li><a href="http://fedoraproject.org/wiki/PackageMaintainers/UpdatingPackageHowTo"><img src="${tg.url('/static/images/header-faq.png')}" border="0" height="18" width="18"/> Updating packages howto</a></li>
                    </ul>
                </td>
                <td align="left">
                    <ul style="list-style:none">
                        <li><a href="https://fedorahosted.org/bodhi/wiki/CLI"><img src="${tg.url('/static/images/terminal.png')}" border="0" height="18" width="18"/> Using the bodhi command-line client</a></li>
                        <li><a href="https://fedorahosted.org/bodhi/newticket"><img src="${tg.url('/static/images/header-projects.png')}" width="18" border="0" /> File a bug or feature request against bodhi</a></li>
                        <li><a href="${koji_url}/koji/"><font size="4">麹</font></a> <a href="${koji_url}/koji/">Koji buildsystem</a></li>
                    </ul>
                </td>
            </tr>
            <tr>
                <td py:if="not tg.identity.anonymous" valign="top" align="left">
                    ${now}
                </td>
            </tr>
        </table>
        <table valign="top" width="90%" align="center">
            <tr>
                <td>
                    <span py:if="updates">
                        <h3><span py:replace="tg.identity.anonymous and 'Latest' or '%s\'s' % (hasattr(tg.identity, 'user_name') and tg.identity.user_name or tg.identity.user.user_name)"></span> Updates</h3>
                        ${updates.display()}
                    </span>
                </td>
            </tr>
            <tr>
                <td>
                    <span py:if="comments">
                        <h3>Latest Comments <a href="${tg.url('/comments')}">[more]</a></h3>
                        ${comments.display()}
                    </span>
                </td>
            </tr>
        </table>

    <center>
        <a href="http://turbogears.org"><img src="${tg.url('/static/images/under_the_hood_blue.png')}" border="0" /></a>
    </center>
</body>
</html>
