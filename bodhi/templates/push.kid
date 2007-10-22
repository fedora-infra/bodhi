<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
        <title>Fedora Update Requests</title>
        <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/jquery.checkboxes.js')}"></script>
</head>

<body>

<?python
## Build a few lists of updates that that outstanding requests
stable = filter(lambda x: x.request == 'stable', updates)
testing = filter(lambda x: x.request == 'testing', updates)
obsolete = filter(lambda x: x.request == 'obsolete', updates)
?>

<blockquote>

    <form id="push_form" name="push_form" method="post" action="${tg.url('/admin/push/mash')}">
        <h1>${len(updates)} pending requests</h1>
        <span py:if="len(testing)">
            <b>Push to Testing</b>
            <table class="list">
                <th class="list" width="5%">
                </th>
                <th class="list" width="45%">
                    <b>Package</b>
                </th>
                <th class="list" width="10%">
                    <b>Karma</b>
                </th>
                <th class="list" width="20%">
                    <b>Release / Status</b>
                </th>
                <th class="list" width="20%">
                    <b>Type</b>
                </th>

                <tr class="list" py:for="update in testing">
                    <?python
                        if update.karma < 0: karma = -1
                        elif update.karma > 0: karma = 1
                        else: karma = 0
                        karma = XML("<img src=\"%s\" align=\"top\" /> <b>%d</b>" % (tg.url('/static/images/karma%d.png' % karma), update.karma))
                    ?>
                    <td class="list">
                        <input type="checkbox" name="updates" value="${update.title}" checked="True"/>
                    </td>
                    <td class="list">
                        <a href="${tg.url(update.get_url())}">${update.get_title()}</a>
                    </td>
                    <td class="list">
                        ${karma}
                    </td>
                    <td class="list">
                        ${"%s / %s " % (update.release.name, update.status)}
                    </td>
                    <td class="list">
                        ${update.type}
                    </td>

                </tr>
            </table>
        </span>
        <span py:if="len(stable)">
            <b>Push to Stable</b>
            <table class="list">
                <th class="list" width="5%">
                </th>
                <th class="list" width="45%">
                    <b>Package</b>
                </th>
                <th class="list" width="10%">
                    <b>Karma</b>
                </th>
                <th class="list" width="20%">
                    <b>Release / Status</b>
                </th>
                <th class="list" width="20%">
                    <b>Type</b>
                </th>
                <tr class="list" py:for="update in stable">
                    <?python
                        if update.karma < 0: karma = -1
                        elif update.karma > 0: karma = 1
                        else: karma = 0
                        karma = XML("<img src=\"%s\" align=\"top\" /> <b>%d</b>" % (tg.url('/static/images/karma%d.png' % karma), update.karma))
                    ?>

                    <td class="list">
                        <input type="checkbox" name="updates" value="${update.title}" checked="True"/>
                    </td>
                    <td class="list">
                        <a href="${tg.url(update.get_url())}">${update.get_title()}</a>
                    </td>
                    <td class="list">
                        ${karma}
                    </td>
                    <td class="list">
                        ${"%s / %s " % (update.release.name, update.status)}
                    </td>
                    <?python color=update.get_pushed_color() ?>
                    <td class="list" bgcolor='${color}'>
                        ${update.type}
                    </td>

                </tr>
            </table>
        </span>
        <span py:if="len(obsolete)">
            <b>Obsolete</b>
            <table class="list">
                <th class="list" width="5%">
                </th>
                <th class="list" width="45%">
                    <b>Package</b>
                </th>
                <th class="list" width="10%">
                    <b>Karma</b>
                </th>
                <th class="list" width="20%">
                    <b>Release / Status</b>
                </th>
                <th class="list" width="20%">
                    <b>Type</b>
                </th>
                <tr class="list" py:for="update in obsolete">
                    <?python
                        if update.karma < 0: karma = -1
                        elif update.karma > 0: karma = 1
                        else: karma = 0
                        karma = XML("<img src=\"%s\" align=\"top\" /> <b>%d</b>" % (tg.url('/static/images/karma%d.png' % karma), update.karma))
                    ?>
                    <td class="list">
                        <input type="checkbox" name="updates" value="${update.title}" checked="True"/>
                    </td>
                    <td class="list">
                        <a href="${tg.url(update.get_url())}">${update.get_title()}</a>
                    </td>
                    <td class="list">			
                        ${karma}
                    </td>
                    <td class="list">
                        ${"%s / %s " % (update.release.name, update.status)}
                    </td>
                    <td class="list">
                        ${update.type}
                    </td>
                </tr>
            </table>
        </span>

        <!-- <input type="hidden" name="callback" value="${callback}" /> -->
        <input type="submit" name="push" value="Mash Repository" />

        <input type="button" name="checkall" value="Toggle checkboxes"
                onClick="$('#push_form').toggleCheckboxes();" />
    </form>
</blockquote>

</body>
</html>
