<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title py:content="title" />

</head>

<body>
    <div>
        <table class="show" cellpadding="0" cellspacing="0">
            <tr>
                <td>
                    ${form(value=values, action=action)}
                </td>
            </tr>
        </table>
    </div>
</body>
</html>
