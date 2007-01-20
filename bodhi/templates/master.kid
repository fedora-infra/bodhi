<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python import sitetemplate ?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#" py:extends="sitetemplate">

<head py:match="item.tag=='{http://www.w3.org/1999/xhtml}head'" py:attrs="item.items()">
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title py:replace="''">Your title goes here</title>
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
@import "/static/css/layout.css";
    </style>
</head>

<body py:match="item.tag=='{http://www.w3.org/1999/xhtml}body'" py:attrs="item.items()">

    <!-- header BEGIN -->
    <div id="fedora-header">
        <div id="fedora-header-logo">
            <a href="/fedora-updates/"><img src="/static/images/header-fedora_logo.png" alt="Fedora Project"/></a>
        </div>

        <div id="fedora-header-items">
            <span class="fedora-header-icon">
                <a href="https://hosted.fedoraproject.org/projects/bodhi/newticket"><img src="/static/images/header-projects.png" alt="Bugs"/>Report a Bug</a>
            </span>
        </div>
    </div>

    <div id="fedora-nav"></div>
    <!-- header END -->

   <!-- leftside BEGIN -->
    <div id="fedora-side-left" py:if="not tg.identity.anonymous">
        <div id="fedora-side-nav-label">Site Navigation:</div>
            <div py:if="'admin' in tg.identity.groups">
                <ul id="fedora-side-nav">
                    <li><a href="/admin/push">Push updates</a></li>
                    <li><a href="/admin/push/unpush">Unpush updates</a></li>
                    <li><a href="/admin/catwalk">CatWalk</a></li>
                    <li><a href="/admin/repotree">Repository Tree</a></li>
                </ul>
            </div>
            <ul id="fedora-side-nav">
                <li><a href="/new">New update</a></li>
                <li><a href="/list">Released updates</a></li>
                <li><a href="/pending">Pending updates</a></li>
                <li><a href="/mine">My updates</a></li>
                <!-- <li><a href="/search">Search</a></li> -->
                <li><a href="/logout">Logout</a></li>
            </ul>
        </div>

        <!-- leftside END -->
        <!-- content BEGIN -->

        <div py:attrs="{'id' : tg.identity.anonymous and 'fedora-middle-three' or 'fedora-middle-two'}">
            <div class="fedora-corner-tr">&nbsp;</div>
            <div class="fedora-corner-tl">&nbsp;</div>
            <div id="fedora-content">

            <div id="page-main">

                <div py:if="tg_flash" class="flash" py:content="tg_flash"></div>
                <div py:replace="[item.text]+item[:]"/>

            </div>

        </div>
        <div class="fedora-corner-br">&nbsp;</div>
        <div class="fedora-corner-bl">&nbsp;</div>
    </div>

    <!-- content END -->
    <!-- footer BEGIN -->
    <div id="fedora-footer"></div>
    <!-- footer END -->

</body>

</html>
