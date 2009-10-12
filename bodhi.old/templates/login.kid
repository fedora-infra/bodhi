<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
    xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8"
        http-equiv="content-type" py:replace="''"/>
    <title>Login</title>
</head>

<body onload="document.login.user_name.focus()">
    <blockquote>
        <h1 class="padded">Fedora Update System</h1>
        <p class="padded">${message}<br/>
        Hint: Use your Fedora username, not your e-mail address.</p> 
    </blockquote>
    <form action="${previous_url}" method="POST" name="login">
        <table class="login">
            <tr>
                <td class="title">
                    Username:
                </td>
                <td class="value">
                    <input type="text" size="25" name="user_name" />
                </td>
            </tr>
            <tr>
                <td class="title">
                    Password:
                </td>
                <td class="value">
                    <input type="password" size="25" name="password" />
                </td>
            </tr>
            <tr>
                <td class="title"></td>
                <td class="value">
                    <input class="button" name="login" type="submit" value="Login" />
                </td>
            </tr>
        </table>

        <input py:if="forward_url" type="hidden" name="forward_url"
            value="${forward_url}"/>

        <input py:for="name,value in original_parameters.items()"
            type="hidden" name="${name}" value="${value}"/>
    </form>
    <blockquote>
        <p class="padded">Forgot your password? Reset it in the <a href="https://admin.fedoraproject.org/accounts/user/resetpass">Fedora Accounts System</a>.</p>
    </blockquote>

</body>
</html>
