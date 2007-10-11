<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type"
            py:replace="''"/>
        <title>${update.title}</title>
</head>

<?python
from cgi import escape
from bodhi import util
from turbogears import identity

## Build our reference links
bugs = ''
for bug in update.bugs:
    bugs += '<a href="%s">%d</a> ' % (bug.get_url(), bug.bz_id)
    if bug.title:
        bugs += '- %s<br/>' % (escape(bug.title))
bugs = bugs.replace('&', '&amp;')
cves = ''
for cve in update.cves:
    cves += '<a href="%s">%s</a><br/>'% (cve.get_url(), cve.cve_id)

## Link to build info and logs
buildinfo = ''
for build in update.builds:
    nvr = util.get_nvr(build.nvr)
    buildinfo += '<a href="http://koji.fedoraproject.org/koji/search?terms=%s&amp;type=build&amp;match=glob">%s</a> <b>[</b> <a href="http://koji.fedoraproject.org/packages/%s/%s/%s/data/logs">logs</a> <b>]</b><br/>' % (build.nvr, build.nvr, nvr[0], nvr[1], nvr[2])

## Make the package name linkable in the n-v-r
title = ''
for build in update.builds:
    nvr = util.get_nvr(build.nvr)
    title += "<a href=\"" + tg.url('/%s' % nvr[0]) + "\">" + nvr[0] + "</a>-" + '-'.join(nvr[-2:]) + ", "
title = title[:-2]

release = '<a href="%s">%s</a>' % (tg.url('/%s' % update.release.name),
                                   update.release.long_name)

notes = escape(update.notes).replace('\r\n', '<br/>')

if update.karma < 0: karma = -1
elif update.karma > 0: karma = 1
else: karma = 0
karma = "<img src=\"%s\" align=\"top\" /> <b>%d</b>" % (tg.url('/static/images/karma%d.png' % karma), update.karma)
?>

<body>
<center>
<table width="97%">
    <tr>
        <td>
            <div class="show">${XML(title)}</div>
        </td>

        <!-- update options -->
        <span py:if="util.authorized_user(update, identity)">
            <td align="right" width="50%" valign="bottom">
                <table cellspacing="7">
                    <tr>
                        <span py:if="not update.pushed">
                            <span py:if="update.request == None">
                                <td>
                                    <a href="${tg.url('/request/testing/%s' % update.title)}" class="list">
                                        <img src="${tg.url('/static/images/testing.png')}" border="0"/>
                                        Push to Testing
                                    </a>
                                </td>
                                <td>
                                    <a href="${tg.url('/request/stable/%s' % update.title)}" class="list">
                                        <img src="${tg.url('/static/images/submit.png')}" border="0"/>
                                        Push to Stable
                                    </a>
                                </td>
                                <td>
                                    <a href="${tg.url('/confirm_delete?nvr=%s' % update.title)}" class="list">
                                        <img src="${tg.url('/static/images/trash.png')}" border="0"/>
                                        Delete
                                    </a>
                                </td>
                            </span>
                            <td>
                                <a href="${tg.url('/edit/%s' % update.title)}" class="list">
                                    <img src="${tg.url('/static/images/edit.png')}" border="0"/>
                                    Edit
                                </a>
                            </td>
                        </span>
                        <span py:if="update.pushed">
                            <td>
                                <a href="${tg.url('/request/unpush/%s' % update.title)}" class="list">
                                    <img src="${tg.url('/static/images/revoke.png')}" border="0"/>
                                    Unpush
                                </a>
                            </td>
                            <span py:if="update.status == 'testing'">
                                <span py:if="update.request == None">
                                    <td>
                                        <a href="${tg.url('/request/stable/%s' % update.title)}" class="list">
                                            <img src="${tg.url('/static/images/submit.png')}" border="0"/>
                                            Mark as Stable
                                        </a>
                                    </td>
                            </span>
                            <td>
                                <a href="${tg.url('/edit/%s' % update.title)}" class="list">
                                    <img src="${tg.url('/static/images/edit.png')}" border="0"/>
                                    Edit
                                </a>
                            </td>
                        </span>
                    </span>
                    <span py:if="update.request != None">
                        <td>
                            <a href="${tg.url('/revoke/%s' % update.title)}" class="list">
                                <img src="${tg.url('/static/images/revoke.png')}" border="0"/>
                                Revoke request
                            </a>
                        </td>
                    </span>
                </tr>
            </table>
        </td>
      </span>
    </tr>
</table>
</center>

<table class="show">
    <tr py:for="field in (
        ['Release',       XML(release)],
        ['Update ID',     update.update_id],
        ['Status',        update.status],
        ['Type',          update.type],
        ['Bugs',          (bugs) and XML(bugs) or ''],
        ['CVEs',          (cves) and XML(cves) or ''],
        ['Karma',         XML(karma)],
        ['Requested',     update.request],
        ['Pushed',        update.pushed],
        ['Date Pushed',   update.date_pushed],
        ['Submitter',     update.submitter],
        ['Submitted',     update.date_submitted],
        ['Modified',      update.date_modified],
        ['Koji Build(s)',    XML(buildinfo)],
    )">
            <span py:if="field[1] != None and field[1] != ''">
                <td class="title"><b>${field[0]}:</b></td>
                <td class="value">${field[1]}</td>
            </span>
    </tr>
    <tr>
        <span py:if="update.notes">
            <td class="title"><b>Notes:</b></td>
            <td class="value">${XML(notes)}</td>
        </span>
    </tr>
    <tr>
        <span py:if="update.comments">
            <td class="title"><b>Comments:</b></td>
            <td class="value">
                <div py:for="comment in update.comments">
                    <img py:attrs="{'src' : tg.url('/static/images/comment-%d.png' % comment.karma)}" hspace="3"/><b>${comment.author}</b> - ${comment.timestamp}<br/>
                    <div py:replace="comment.text">Comment</div>
                </div>
            </td>
        </span>
    </tr>
    <tr>
        <td class="title"></td>
        <td class="value">
            ${comment_form.display(value=values)}
        </td>
    </tr>
    <tr><td class="title"></td></tr>
</table>

</body>
</html>
