<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python import sitetemplate ?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#" py:extends="sitetemplate">

<head py:match="item.tag=='{http://www.w3.org/1999/xhtml}head'" py:attrs="item.items()">
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <link rel="shortcut icon" type="image/vnd.microsoft.icon" href="${tg.url('/static/images/favicon.ico')}" /> 
    <link rel="shortcut icon" type="image/x-icon" href="${tg.url('/static/images/favicon.ico')}" /> 
    <title py:replace="''">Your title goes here</title>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/jquery.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/jquery.corner.js')}"></script>

    <meta py:replace="item[:]"/>
    <style type="text/css">
        #pageLogin
        {
            font-size: 10px;
            font-family: verdana;
            text-align: right;
        }
    </style>
    <style type="text/css" media="screen">
        @import "${tg.url('/static/css/layout-uncompressed.css')}";
    </style>
</head>

<body py:match="item.tag=='{http://www.w3.org/1999/xhtml}body'" py:attrs="item.items()">

<?python
from bodhi.model import Release, PackageUpdate, releases
from bodhi.search import search_form
from sqlobject.sqlbuilder import AND
?>

<!-- Make any form submission change the bodhi logo into a spinner -->
<script type="text/javascript">
$(document).ready(function() {
    // This kills our fedora-content border.  We'll keep using the 4 rounded
    // corner images until we can figure out how to round them with jquery and
    // maintain our 1px content border.
    //$("div[@id=fedora-content]").corner();

    $("form").submit( function() {
        $("div[@id=bodhi-logo]").hide();
        $("div[@id=wait]").show();
    } );
} );
</script>
<script type="text/javascript" py:if="not tg.identity.anonymous">
$(document).ready(function() {
    $('#release').click( function() { $('#releases').toggle('slow'); });
    $('div.flash').corner();
    $('div.flash').show("slow");
});
</script>
<script type="text/javascript" py:if="'releng' in tg.identity.groups">
$(document).ready(function() {
    $('#administration').click( function() { $('#adminlist').toggle('slow'); });
});
</script>

    <!-- header BEGIN -->
    <div id="fedora-header">
        <div id="fedora-header-logo">
            <a href="${tg.url('/')}"><img src="${tg.url('/static/images/header-fedora_logo.png')}" /></a>
        </div>

        <div id="fedora-header-items">
            <table><tr><td py:if="not tg.identity.anonymous"> ${search_form.display()} </td><td>
                <div id="bodhi-logo">
                    <a href="${tg.url('/')}"><img src="${tg.url('/static/images/bodhi-icon-48.png')}" /></a>
                </div>
                <div id="wait" style="display: none">
                    <img src="${tg.url('/static/images/wait.gif')}" height="48" width="48"/>
                </div>
            </td></tr></table>
        </div>
    </div>

    <div id="fedora-nav"></div>
    <!-- header END -->

   <!-- leftside BEGIN -->
    <div id="fedora-side-left" py:if="not tg.identity.anonymous">
        <div id="fedora-side-nav-label">Site Navigation:</div>
            <div py:if="'releng' in tg.identity.groups">
                <ul id="fedora-side-nav">
                    <li><a id="administration" href="#">Administration</a></li>
                    <div id="adminlist" style="display: none">
                        <ul>
                            <li><a href="${tg.url('/admin/push')}">Requests</a></li>
                            <li><a href="${tg.url('/admin/masher')}">Masher</a></li>
                        </ul>
                    </div>
                </ul>
            </div>
            <ul id="fedora-side-nav">
                <li><a href="${tg.url('/')}">Home</a></li>
                <li><a href="${tg.url('/mine')}">My updates</a></li>
                <li py:for="release in releases()">
                    <a id="release" href="#">${release[1]}</a>
                        <div id="releases">
                            <ul>
                                <li><a href="${tg.url('/new/%s' % release[0])}">New Update</a></li>
                                <li py:for="status in ('pending', 'testing', 'stable')">
                                <a href="${tg.url('/%s%s' % (status != 'stable' and '%s/' % status or '', release[0]))}">${status.title()} (${PackageUpdate.select(AND(PackageUpdate.q.releaseID == release[2], PackageUpdate.q.status == status)).count()})</a>
                                </li>
                            </ul>
                        </div>
                    </li>
                <li><a href="${tg.url('/pkgs')}">Packages</a></li>
                <li><a href="${tg.url('/logout')}">Logout</a></li>
            </ul>
        </div>
        <!-- leftside END -->

        <!-- content BEGIN -->
        <div py:attrs="{'id' : tg.identity.anonymous and 'fedora-middle-three' or 'fedora-middle-two'}">
            <div class="fedora-corner-tr">&nbsp;</div> 
            <div class="fedora-corner-tl">&nbsp;</div> 
            <div id="fedora-content">

            <div id="page-main">

                <center>
                    <div style="display: none;" id="flash" py:if="tg_flash" class="flash" py:content="tg_flash"></div>
                </center>
                <div py:replace="[item.text]+item[:]"/>

            </div>
        </div>
        <div class="fedora-corner-br">&nbsp;</div>
        <div class="fedora-corner-bl">&nbsp;</div>
    </div>
    <!-- content END -->

    <!-- footer BEGIN -->
    <div id="fedora-footer">Copyright © 2007 Red Hat, Inc.</div>
    <!-- footer END -->

</body>
</html>
