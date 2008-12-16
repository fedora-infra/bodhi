<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<?python
from bodhi.model import Release, PackageUpdate, Releases
?>
<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <!-- copy&pasted from master.kid with username added -->
    <link py:for="release_name in [release['name'] for release in Releases().data]" py:strip="True">
    <link py:for="status in ('pending', 'testing', 'stable')" href="${tg.url('/rss/rss2.0?release=%s&amp;status=%s&amp;submitter=%s' % (release_name, status, username))}" rel="alternate" type="application/rss+xml" title="${'%s %s updates submitted by %s' % (release_name, status, username)}" />
    </link>
    <!-- Feed for all updates by one user -->
    <link href="${tg.url('/rss/rss2.0?submitter=%s' % (username))}" rel="alternate" type="application/rss+xml" title="${'All updates submitted by %s' % (username)}" />
    <title>Fedora Updates</title>
</head>

<body>
    &nbsp;&nbsp;<b>${"%s's %d updates" % (username, num_items)}</b>
    <div py:if="num_items" class="list">
        <span py:for="page in tg.paginate.pages">
            <a py:if="page != tg.paginate.current_page"
                href="${tg.paginate.get_href(page)}">${page}</a>
            <b py:if="page == tg.paginate.current_page">${page}</b>
        </span>
    </div>

    <table class="list">
        <tr class="list">
            <th class="list">
                <b>Update</b>
            </th>
            <th class="list">
                <b>Type</b>
            </th>
            <th class="list">
                <b>Submitter</b>
            </th>
            <th class="list">
                <b>Date Submitted</b>
            </th>
        </tr>
        <?python row_color = "#FFFFFF" ?>
        <tr class="list" bgcolor="${row_color}" py:for="update in updates">
            <td class="list" width="35%">
                <a class="list" href="${tg.url(update.get_url())}">${update.title.replace(',', ', ')}</a>
            </td>
            <td class="list">
                <img src="${tg.url('/static/images/%s.png' % update.type)}" title="${update.type}" /> ${update.type}
            </td>
            <td class="list">
                <a href="${tg.url('/user/%s' % update.submitter)}">${update.submitter}</a>
            </td>
            <td class="list">
                ${update.date_submitted}
            </td>
            <?python row_color = (row_color == "#f1f1f1") and "#FFFFFF" or "#f1f1f1" ?>
        </tr>
    </table>

</body>
</html>
