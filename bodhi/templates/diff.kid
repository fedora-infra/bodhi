<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates</title>
</head>


<body>
    <blockquote>
        <h1><a href="${tg.url('/admin/repodiff')}">Repodiff</a> - ${title}</h1>
    <pre>
        <table>
            <tr py:for="line in diff.split('\n')">
                <?python
                if line.startswith('---') or line.startswith('+++'):
                    color = "#00ff00"
                elif line.startswith('+'):
                    color = "blue"
                elif line.startswith('-'):
                    color = "red"
                elif line.startswith('@@'):
                    color = "orange"
                else:
                    color = "#00000"
                ?>
                <td><font face="fixed" color="${color}">${line}</font></td>
            </tr>
        </table>
    </pre>
    </blockquote>
</body>
</html>
