<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>

<body>
    <blockquote>
        <h1>Repodiff</h1>
        <table>
            <tr py:for="diff in diffs">
                <td>
                    <a href="${tg.url('/admin/repodiff/' + diff)}">${diff}</a>
                </td>
            </tr>
        </table>
    </blockquote>
</body>
</html>
