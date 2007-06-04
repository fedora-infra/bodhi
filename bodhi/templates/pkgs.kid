<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>

<body>
    &nbsp;&nbsp;${num_pkgs} packages found
    <div class="list">
        <span py:for="page in tg.paginate.pages">
            <a py:if="page != tg.paginate.current_page"
                href="${tg.paginate.get_href(page)}">${page}</a>
            <b py:if="page == tg.paginate.current_page">${page}</b>
        </span>
        <a href="?tg_paginate_limit=${num_pkgs}">all</a>
    </div>

    <table class="list">
        <tr class="list">
            <th class="list">
                <b>Name</b>
            </th>
            <th class="list">
                <b>Updates</b>
            </th>
        </tr>
        <?python row_color = "#FFFFFF" ?>
        <tr class="list" bgcolor="${row_color}" py:for="pkg in pkgs">
            <td class="list">
                <a class="list" href="${tg.url('/%s' % pkg.name)}">${pkg.name}</a>
            </td>
            <td class="list">
                ${len(pkg.updates)}
            </td>
            <?python row_color = (row_color == "#f1f1f1") and "#FFFFFF" or "#f1f1f1" ?>
        </tr>
    </table>

</body>
</html>
