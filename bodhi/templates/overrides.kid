<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Fedora Updates - ${title}</title>
</head>

<body>
    &nbsp;&nbsp;<h2>${title}</h2>
    <div style="float:left">
    &nbsp;&nbsp;<a href="${tg.url('/override/new')}"><img src="${tg.url('/static/images/plus.png')}"/>Submit a new override</a>
    </div>
    <div style="float:right">
        <div py:if="mine">
            &nbsp;&nbsp;[ <a href="${tg.url('/override/list')}">Show all</a> ]
        </div>
        <div py:if="not mine">
            &nbsp;&nbsp;[ <a href="${tg.url('/override/list?mine=True')}">Show mine</a> ]
        </div>
        <div py:if="show_expired">
            &nbsp;&nbsp;[ <a href="${tg.url('/override/list')}">Hide expired overrides</a> ]
        </div>
        <div py:if="not show_expired">
            &nbsp;&nbsp;[ <a href="${tg.url('/override/list?show_expired=True')}">Show expired overrides</a> ]
        </div>
    </div>

    <table class="list">
        <tr class="list">
            <th class="list">
                <b>Build</b>
            </th>
            <th class="list">
                <b>Notes</b>
            </th>
            <th class="list">
                <b>Submitter</b>
            </th>
            <th class="list">
                <b>Submitted</b>
            </th>
            <th class="list">
                <b>Expiration</b>
            </th>
            <th class="list">
            </th>
        </tr>
        <?python row_color = "#FFFFFF" ?>
        <tr class="list" bgcolor="${row_color}" py:for="override in overrides">
            <td class="list">
                <a href="${tg.url('/override/edit?build=' + override.build)}">${override.build}</a>
            </td>
            <td class="list">
                ${override.notes}
            </td>
            <td class="list">
                <a href="${tg.url('/user/' + override.submitter)}">${override.submitter}</a>
            </td>
            <td class="list">
                ${override.date_submitted and override.date_submitted.strftime('%m/%d/%Y') or ''}
            </td>
            <td class="list">
                ${override.expiration and override.expiration.strftime('%m/%d/%Y') or ''}
            </td>
            <td class="list">
                <div py:if="override.date_expired">
                    <b>EXPIRED</b>
                </div>
                <div py:if="not override.date_expired">
                    <div py:if="'releng' in tg.identity.groups or tg.identity.user_name == override.submitter">
                        <a href="${tg.url('/override/expire/%s' % override.build)}">Expire</a>
                    </div>
                </div>
            </td>
            <?python row_color = (row_color == "#f1f1f1") and "#FFFFFF" or "#f1f1f1" ?>
        </tr>
    </table>

    <div py:if="num_items" class="list">
        <span py:for="page in tg.paginate.pages">
            <a py:if="page != tg.paginate.current_page"
                href="${tg.paginate.get_href(page)}">${page}</a>
            <b py:if="page == tg.paginate.current_page">${page}</b>
        </span>
    </div>

</body>
</html>
