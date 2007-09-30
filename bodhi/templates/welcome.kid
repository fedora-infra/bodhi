<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">
<head>
    <meta content="text/html; charset=utf-8" http-equiv="Content-Type" py:replace="''"/>
    <title>Fedora Update System</title>
    <link media="all" href="${tg.url('/tg_widgets/turbogears.widgets/grid.css')}" type="text/css" rel="stylesheet"/>
    <link rel="stylesheet" href="${tg.url('/static/css/jquery.tooltip.css')}" />
    <script src="${tg.url('/static/js/jquery.dimensions.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/jquery.tooltip.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/chili-1.7.pack.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/jquery.bgiframe.js')}" type="text/javascript"></script>

    <script language="javascript">
        $(document).ready(function(){
            $('#bodhitip').Tooltip( { delay: 0 } );
            $('#wftip').Tooltip( { delay: 0 } );
            $('#kojitip').Tooltip( { delay: 0 } );
            $('#mugtip').Tooltip( { delay: 0 } );
            $('#bugtip').Tooltip( { delay: 0 } );
        });
    </script>

</head>
<body>
    <table width="90%" align="center" valign="top">
            <tr>
                <td align="left" valign="bottom"><b><font size="4">Welcome, ${tg.identity.user.display_name}</font></b></td>
                <td align="right">
                    <table>
                        <tr>
                            <td>
                                <span id="bodhitip" title="Bodhi Project Homepage">
                                    <a href="http://hosted.fedoraproject.org/projects/bodhi"><img src="${tg.url('/static/images/bodhi-icon-36.png')}" border="0" height="36" width="36"/></a>
                                </span>
                            </td>
                            <td>
                                <span id="wftip" title="Bodhi Workflow Q&amp;A draft">
                                    <a href="http://fedoraproject.org/wiki/Infrastructure/UpdatesSystem/Bodhi-info-DRAFT"><img src="${tg.url('/static/images/header-faq.png')}" border="0" height="36" width="36"/></a>
                                </span>
                            </td>
                            <td>
                                <span id="bugtip" title="File a bug or feature request">
                                    <a href="https://hosted.fedoraproject.org/projects/bodhi/newticket"><img src="${tg.url('/static/images/header-projects.png')}" border="0" /></a>
                                </span>
                            </td>
                            <td>
                                <span id="kojitip" title="Koji Buildsystem">
                                    <a href="http://koji.fedoraproject.org/koji/" class="list"><font size="6">麹</font></a>
                                </span>
                            </td>
                            <td>
                                <span id="mugtip" title="Fedora Infrastructure Mugshot Group">
                                    <a href="http://mugshot.org/group?who=yWstkV2xGz93rQ"><img src="${tg.url('/static/images/mugshot.png')}" border="0" /></a>
                                </span>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            <tr>
                <td valign="top" align="left">
                    ${now}
                </td>
            </tr>
        </table>
        <table valign="top" width="90%" align="center">
            <tr>
                <td>
                    <span py:if="mine">
                        <h3>${tg.identity.user.user_name}'s updates</h3>
                        ${mine.display()}
                    </span>
                </td>
            </tr>
            <tr>
                <td>
                    <span py:if="comments">
                        <h3>Latest Comments</h3>
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
