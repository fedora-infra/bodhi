<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>

<body>
    &nbsp;&nbsp;${num_items} updates found
    <div class="list">
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
                <b>ID</b>
            </th>
            <th class="list">
                <b>Package</b>
            </th>
            <th class="list">
                <b>Release</b>
            </th>
            <th class="list">
                <center><b>Type</b></center>
            </th>
            <th class="list">
                <center><b>Status</b></center>
            </th>
            <th class="list">
                <b>Date Pushed</b>
            </th>
        </tr>
        <?python row_color = "#FFFFFF" ?>
        <tr class="list" bgcolor="${row_color}" py:for="update in updates">
            <td class="list">
                ${update.update_id}
            </td>
            <td class="list">
                <a class="list" href="${tg.url(update.get_url())}">${update.nvr}</a>
            </td>
            <td class="list">
                <a class="list" href="${tg.url('/%s%s' % (update.status=='testing' and 'testing/' or '', update.release.name))}">${"%s%s" % (update.release.long_name, update.status=='testing' and ' Testing' or '')}</a>
            </td>
            <td class="list" align="center">
                <img src="${tg.url('/static/images/%s.png' % update.type)}" title="${update.type}" />
            </td>
            <td class="list" align="center">
                ${update.status}
            </td>
            <td class="list">
                ${update.date_pushed}
            </td>
            <?python row_color = (row_color == "#f1f1f1") and "#FFFFFF" or "#f1f1f1" ?>
        </tr>
    </table>

</body>
</html>
