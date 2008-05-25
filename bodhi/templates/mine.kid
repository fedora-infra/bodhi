<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>

<body>
    &nbsp;&nbsp;<b>${title}</b>
    <div py:if="num_items" class="list">
        <span py:for="page in tg.paginate.pages">
            <a py:if="page != tg.paginate.current_page"
                href="${tg.paginate.get_href(page)}">${page}</a>
            <b py:if="page == tg.paginate.current_page">${page}</b>
        </span>
        <a href="?tg_paginate_limit=${num_items}">all</a>
    </div>

    <table class="list">
        <tr class="list">
            <th class="list">
                <b>Update</b>
            </th>
            <th class="list">
                <b>Release</b>
            </th>
            <th class="list">
                <center><b>Type</b></center>
            </th>
            <th class="list">
                <b>Status</b>
            </th>
            <th class="list">
                <center><b>Request</b></center>
            </th>
            <th class="list">
                <b>Karma</b>
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
                <a class="list" href="${tg.url('/%s' % update.release.name)}">${update.release.long_name}</a>
            </td>
            <td class="list" align="center">
                <img src="${tg.url('/static/images/%s.png' % update.type)}" title="${update.type}" />
            </td>
            <td class="list">
                ${update.status}
            </td>
            <td class="list">
                <center>
                    <img src="${tg.url('/static/images/%s-large.png' % update.request)}" title="${update.request}"/> ${update.request}
                </center>
            </td>
            <td class="list">
                <center>
                    <img src="${tg.url('/static/images/karma%d.png' % update.karma)}" /> ${update.karma}
                </center>
            </td>
            <td class="list">
                ${update.date_submitted}
            </td>
            <?python row_color = (row_color == "#f1f1f1") and "#FFFFFF" or "#f1f1f1" ?>
        </tr>
    </table>

</body>
</html>
