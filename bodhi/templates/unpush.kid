<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
        <title>Fedora Updates</title>
</head>

<body>

<form name="push_form" method="post" action="/admin/push/console">
    <table>
        <tr py:for="update in updates">
            <td>
                <input type="checkbox" name="updates" value="${update.nvr}" checed="True"/>
                <a href="/show/${update.nvr}">${update.nvr}</a>
            </td>
        </tr>
    </table>
    <input type="submit" name="push" value="Push" />
</form>

</body>
</html>
