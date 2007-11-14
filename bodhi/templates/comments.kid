<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>

<body>
    &nbsp;&nbsp;<b>Update Comments</b>
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
                <b>Update</b>
            </th>
            <th class="list">
                <b>Comment</b>
            </th>
            <th class="list">
                <center><b>Karma</b></center>
            </th>
            <th class="list">
                <b>Author</b>
            </th>
            <th class="list">
                <b>Timestamp</b>
            </th>
        </tr>
        <?python row_color = "#FFFFFF" ?>
        <tr class="list" bgcolor="${row_color}" py:for="comment in comments">
            <td class="list">
                <a href="${tg.url(comment.update.get_url())}" class="list">${comment.update.get_title(', ')}</a>
            </td>
            <td class="list">
              <span py:if="comment.text">
                ${comment.text[:50]}
              </span>
            </td>
            <td class="list" align="center">
                <img src="${tg.url('/static/images/karma%d.png' % comment.karma)}" align="top"/> <b>${comment.karma}</b>
            </td>
            <td class="list">
                ${comment.author}
            </td>
            <td class="list">
                ${comment.timestamp}
            </td>
            <?python row_color = (row_color == "#f1f1f1") and "#FFFFFF" or "#f1f1f1" ?>
        </tr>
    </table>

</body>
</html>
