<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type"
            py:replace="''"/>
        <title>${update.nvr}</title>
</head>

<?python
bugs = ''
cves = ''
bzlink = '<a href="https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=%d">%d</a> '
cvelink = '<a href="http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=%s">%s</a> '

## Build our reference links
for bug in update.bugs:
    bugs += bzlink % (bug.bz_id, bug.bz_id)
    if bug.title:
        bugs += '- %s<br/>' % (bug.title)
bugs = bugs.replace('&', '&amp;')
for cve in update.cves:
    cves += cvelink % (cve.cve_id, cve.cve_id)

## Build our file list
from os.path import basename
filelist = '<div id="showfiles"><a href="#" onClick="MochiKit.Visual.toggle($(\'filelist\'))">Toggle filelist</a></div><div id="filelist" style="display: none">'
for arch in update.filelist.keys():
    if len(update.filelist[arch]):
        filelist += '<b>%s</b><br/>' % arch
        for pkg in update.filelist[arch]:
            filelist += '|-- %s<br/>' % basename(pkg)
filelist += "</div>"

comments = ''
for comment in update.comments:
    comments += "<b>%s</b> - %s<br/>%s<br/>" % (comment.author,
                                                comment.timestamp,
                                                comment.text)

from bodhi.util import get_nvr
nvr = get_nvr(update.nvr)
title = XML("<a href=\"" + tg.url('/%s' % nvr[0]) + "\">" + nvr[0] + "</a>-" + '-'.join(nvr[-2:]))
?>

<body>

    <center><table width="97%">
        <tr>
            <td><div class="show">${title}</div></td>

            <!-- update options -->
            <td align="right">
                [
                <span py:if="not update.pushed">
                    <span py:if="update.request == None">
                        <a href="${tg.url('/push/%s' % update.nvr)}">Push</a> | 
                        <a href="${tg.url('/delete/%s' % update.nvr)}">Delete</a> | 
                    </span>
                    <span py:if="update.request in ('push', 'move')">
                        <a href="${tg.url('/revoke/%s' % update.nvr)}">
                            Revoke ${update.request} request</a> | 
                    </span>
                </span>
                <span py:if="update.pushed">
                    <a href="${tg.url('/unpush/%s' % update.nvr)}">Unpush</a> | 
                    <span py:if="update.testing">
                        <a href="${tg.url('/move/%s' % update.nvr)}">Mark as Stable</a> | 
                    </span>
                </span>
                <a href="${tg.url('/edit/%s' % update.nvr)}">Edit</a>
                ]
            </td>
        </tr>
    </table></center>

    <table class="show">
        <tr py:for="field in (
            ['Release',       update.release.long_name],
            ['Update ID',     update.update_id],
            ['Status',        update.testing and 'Testing' or 'Final'],
            ['Type',          update.type],
            ['Bugs',          (bugs) and XML(bugs) or ''],
            ['CVEs',          (cves) and XML(cves) or ''],
            ['Embargo',       update.type == 'security' and update.embargo or ''],
            ['Requested',     update.request],
            ['Pushed',        update.pushed],
            ['Date Pushed',   update.date_pushed],
            ['Mail Sent',     update.mail_sent],
            ['Submitter',     update.submitter],
            ['Submitted',     update.date_submitted],
            ['Modified',      update.date_modified],
            ['Archived Mail', update.archived_mail],
            ['Notes',         update.notes],
            ['Files',         XML(filelist)]
        )">
                <span py:if="field[1] != None and field[1] != ''">
                    <td class="show-title"><b>${field[0]}:</b></td>
                    <td class="show-value">${field[1]}</td>
                </span>
        </tr>
        <tr>
            <td class="show-title"><b>Comments:</b></td>
            <td class="show-value">
                ${XML(comments)}
            </td>
        </tr>
        <tr>
            <td class="show-title"></td>
            <td class="show-value">
                ${comment_form.display(value=values)}
            </td>
        </tr>
        <tr><td class="show-title"></td></tr>
    </table>

</body>
</html>
