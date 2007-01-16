<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>

<body>

    <div class="list">
        <span py:for="page in tg.paginate.pages">
            <a py:if="page != tg.paginate.current_page"
                href="${tg.paginate.get_href(page)}">${page}</a>
            <b py:if="page == tg.paginate.current_page">${page}</b>
        </span>
    </div>

    <table class="list">
        <tr class="list">
            <th class="list">
                <b>ID</b>
            </th>
            <th class="list" width="30%">
                <b>Package</b>
            </th>
            <th class="list" width="15%">
                <b>Release</b>
            </th>
            <th class="list" width="5%">
                <center><b>Type</b></center>
            </th>
            <th class="list" width="10%">
                <center><b>Status</b></center>
            </th>
            <th class="list" width="40%">
                <b>Submitted</b>
            </th>
        </tr>
        <?python row_color = "#FFFFFF" ?>
        <tr class="list" bgcolor="${row_color}" py:for="update in updates">
            <td class="list">
                ${update.update_id}
            </td>
            <?python
            testing = update.testing and 'Testing' or 'Final'
            ?>
            <td class="list">
                <a class="list" href="/show/${update.nvr}">${update.nvr}</a>
            </td>
            <td class="list">
                ${update.release.long_name}
            </td>
            <td class="list" align="center">
                <img src="/static/images/${update.type}.png"/>
            </td>
            <td class="list" align="center">
                ${testing}
            </td>
            <td class="list">
                ${update.date_submitted}
            </td>
            <?python row_color = (row_color == "#f1f1f1") and "#FFFFFF" or "#f1f1f1" ?>
        </tr>
    </table>

</body>
</html>
