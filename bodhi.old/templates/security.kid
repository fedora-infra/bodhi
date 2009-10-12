<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
</head>
<body>
    <b>Updates pending security approval</b>
    <br/>
    <table class="list">
        <tr class="list">
            <th class="list">
                <b>Update</b>
            </th>
            <th class="list">
                <b>Release</b>
            </th>
            <th class="list">
                <b>Status</b>
            </th>
            <th class="list">
                <b>Submitter</b>
            </th>
            <th class="list">
                <b>Age</b>
            </th>
            <th class="list">
                <b>Approve</b>
            </th>
        </tr>
        <?python row_color = "#FFFFFF" ?>
        <tr class="list" bgcolor="${row_color}" py:for="update in updates">
            <td class="list">
                <a class="list" href="${tg.url(update.get_url())}">${update.title.replace(',', ', ')}</a>
            </td>
            <td class="list">
                <a class="list" href="${tg.url('/%s' % update.release.name)}">${update.release.long_name}</a>
            </td>
            <td class="list">
                ${update.status}
            </td>
            <td class="list">
                <a href="${tg.url('/user/' + update.submitter)}">${update.submitter}</a>
            </td>
            <td class="list">
                ${update.get_submitted_age()}
            </td>
            <td class="list">
                <a class="list" href="${tg.url('/approve/%s' % update.title)}">Approve</a>
            </td>
            <?python row_color = (row_color == "#f1f1f1") and "#FFFFFF" or "#f1f1f1" ?>
        </tr>
    </table>

</body>
</html>
