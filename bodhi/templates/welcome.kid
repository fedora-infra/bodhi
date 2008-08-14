<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">
<?python from bodhi import version, hostname ?>
<head>
    <meta content="text/html; charset=utf-8" http-equiv="Content-Type" py:replace="''"/>
    <title>Fedora Update System</title>
    <link media="all" href="${tg.url('/tg_widgets/turbogears.widgets/grid.css')}" type="text/css" rel="stylesheet"/>
    <script src="${tg.url('/static/js/jquery.dimensions.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/jquery.tooltip.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/chili-1.7.pack.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/jquery.bgiframe.js')}" type="text/javascript"></script>

    <script language="javascript">
        $(document).ready(function(){
            $('#bodhitip').Tooltip( { delay: 0, track: true, opacity: 0.85,  } );
            $('#wftip').Tooltip( { delay: 0, track: true, opacity: 0.85,  } );
            $('#clitip').Tooltip( { delay: 0, track: true, opacity: 0.85,  } );
            $('#kojitip').Tooltip( { delay: 0, track: true, opacity: 0.85,  } );
            $('#mugtip').Tooltip( { delay: 0, track: true, opacity: 0.85, } );
            $('#bugtip').Tooltip( { delay: 0, track: true, opacity: 0.85, } );
        });
    </script>

</head>
<body>
    <table width="90%" align="center" valign="top">
            <tr>
                <td align="left" valign="bottom"><b><font size="4">Welcome to bodhi v${version}<span py:if="not tg.identity.anonymous">, ${hasattr(tg.identity.user, 'human_name') and tg.identity.user.human_name.split()[0] or tg.identity.user.display_name}</span></font></b></td>
                <td align="right">
                    <table>
                        <tr>
                            <td>
                                <span id="bodhitip" title="Bodhi Project Homepage">
                                    <a href="http://fedorahosted.org/bodhi"><img src="${tg.url('/static/images/bodhi-icon-36.png')}" border="0" height="36" width="36"/></a>
                                </span>
                            </td>
                            <td>
                                <span id="wftip" title="Updating Packages HowTo">
                                    <a href="http://fedoraproject.org/wiki/PackageMaintainers/UpdatingPackageHowTo"><img src="${tg.url('/static/images/header-faq.png')}" border="0" height="36" width="36"/></a>
                                </span>
                            </td>
                            <td>
                                <span id="clitip" title="Using the bodhi command-line client">
                                    <a href="https://fedorahosted.org/bodhi/wiki/CLI"><img src="${tg.url('/static/images/terminal.png')}" border="0" height="36" width="36"/></a>
                                </span>
                            </td>
 
                            <td>
                                <span id="bugtip" title="File a bug or feature request against bodhi">
                                    <a href="https://fedorahosted.org/bodhi/newticket"><img src="${tg.url('/static/images/header-projects.png')}" border="0" /></a>
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
                <td py:if="not tg.identity.anonymous" valign="top" align="left">
                    ${now}
                </td>
            </tr>
        </table>
        <table valign="top" width="90%" align="center">
            <tr>
                <td>
                    <span py:if="updates">
                        <h3><span py:replace="tg.identity.anonymous and 'Latest' or '%s\'' % (hasattr(tg.identity, 'user_name') and tg.identity.user_name or tg.identity.user.user_name)"></span> Updates</h3>
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
