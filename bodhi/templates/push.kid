<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
        <title>Fedora Update Requests</title>
</head>

<body>

<?python
## Build a few lists of updates that that outstanding requests
needmove = filter(lambda x: x.request == 'move', updates)
needpush = filter(lambda x: x.request == 'push', updates)
needunpush = filter(lambda x: x.request == 'unpush', updates)
?>

<blockquote>
    <form name="push_form" method="post" action="${tg.url('/admin/push/mash')}">
        <h1>${updates.count()} pending requests</h1>
        <span py:if="len(needpush)">
            <b>Push</b>
            <table>
                <tr py:for="update in needpush">
                    <td>
                        <input type="checkbox" name="updates" value="${update.nvr}" checked="True"/>
                    </td>
                    <td>
                        <a href="${tg.url(update.get_url())}">${update.nvr}</a>
                    </td>
                </tr>
            </table>
        </span>
        <span py:if="len(needmove)">
            <b>Move</b>
            <table>
                <tr py:for="update in needmove">
                    <td>
                        <input type="checkbox" name="updates" value="${update.nvr}" checked="True"/>
                    </td>
                    <td>
                        <a href="${tg.url(update.get_url())}">${update.nvr}</a>
                    </td>
                </tr>
            </table>
        </span>
        <span py:if="len(needunpush)">
            <b>Unpush</b>
            <table>
                <tr py:for="update in needunpush">
                    <td>
                        <input type="checkbox" name="updates" value="${update.nvr}" checked="True"/>
                    </td>
                    <td>
                        <a href="${tg.url(update.get_url())}">${update.nvr}</a>
                    </td>
                </tr>
            </table>
        </span>


        <!-- <input type="hidden" name="callback" value="${callback}" /> -->
        <input type="submit" name="push" value="Mash Repository" />
    </form>
</blockquote>

</body>
</html>
