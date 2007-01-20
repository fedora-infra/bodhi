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
bzlink = '<a href="https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=%s">%s</a> '
cvelink = '<a href="http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=%s">%s</a> '

## Build our reference links
for bug in update.bugs:
    bugs += bzlink % (bug.bz_id, bug.bz_id)
    if bug.title:
        bugs += '- %s<br/>' % (bug.title)
for cve in update.cves:
    cves += cvelink % (cve.cve_id, cve.cve_id)

## Build our file list
from os.path import basename
filelist = ''
for item in update.filelist.items():
    filelist += '<b>%s</b><br/>' % item[0]
    for pkg in isinstance(item[1], list) and item[1] or [item[1]]:
        filelist += '|-- %s<br/>' % basename(pkg)
?>

<body>

    <center><table width="97%">
        <tr>
            <td><div class="show">${update.nvr}</div></td>

            <!-- update options -->
            <td align="right">
                [
                <span py:if="not update.needs_push">
                    <a href="/push/${update.nvr}">Push</a> | 
                </span>
                <span py:if="update.needs_push">
                    <a href="/revoke/${update.nvr}">Revoke Push Request</a> | 
                </span>
                <span py:if="update.pushed">
                    <a href="/unpush/${update.nvr}">Unpush</a> | 
                </span>
                <span py:if="not update.pushed">
                    <a href="/delete/${update.nvr}">Delete</a> | 
                </span>
                <a href="/edit/${update.nvr}">Edit</a>
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
            ['Pushed',        update.pushed],
            ['Needs Push',    update.needs_push],
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
        <tr><td class="show-title"></td></tr>
    </table>

</body>
</html>
