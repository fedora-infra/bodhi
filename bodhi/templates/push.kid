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
            <b>Push to Testing</b>
            <table class="list">
			    <th class="list" width="5%">
			    </th>
			    <th class="list" width="45%">
			        <b>Package</b>
			    </th>
			    <th class="list" width="10%">
			        <b>Karma</b>
			    </th>
			    <th class="list" width="20%">
			        <b>Release / Status</b>
			    </th>
			    <th class="list" width="20%">
			        <b>Type</b>
			    </th>
            
                <tr class="list" py:for="update in needpush">
		            <?python
		                if update.karma < 0: karma = -1
						elif update.karma > 0: karma = 1
						else: karma = 0
						karma = XML("<img src=\"%s\" align=\"top\" /> <b>%d</b>" % (tg.url('/static/images/karma%d.png' % karma), update.karma))
					?>
                    <td class="list">
                        <input type="checkbox" name="updates" value="${update.title}" checked="True"/>
                    </td>
                    <td class="list">
                        <a href="${tg.url(update.get_url())}">${update.title}</a>
                    </td>
                    <td class="list">			
                        ${karma}
                    </td>
                    <td class="list">
                        ${"%s / %s " % (update.release.name, update.status)}
                    </td>
                    <td class="list">
                        ${update.type}
                    </td>
                    
                </tr>
            </table>
        </span>
        <span py:if="len(needmove)">
            <b>Move to Stable</b>
            <table class="list">
			    <th class="list" width="5%">
			    </th>
			    <th class="list" width="45%">
			        <b>Package</b>
			    </th>
			    <th class="list" width="10%">
			        <b>Karma</b>
			    </th>
			    <th class="list" width="20%">
			        <b>Release / Status</b>
			    </th>
			    <th class="list" width="20%">
			        <b>Type</b>
			    </th>
                <tr class="list" py:for="update in needmove">
	                <?python
		                if update.karma < 0: karma = -1
						elif update.karma > 0: karma = 1
						else: karma = 0
						karma = XML("<img src=\"%s\" align=\"top\" /> <b>%d</b>" % (tg.url('/static/images/karma%d.png' % karma), update.karma))
					?>
                
                    <td class="list">
                        <input type="checkbox" name="updates" value="${update.title}" checked="True"/>
                    </td>
                    <td class="list">
                        <a href="${tg.url(update.get_url())}">${update.title}</a>
                    </td>
                    <td class="list">			
                        ${karma}
                    </td>
                    <td class="list">
                        ${"%s / %s " % (update.release.name, update.status)}
                    </td>
                    <td class="list">
                        ${update.type}
                    </td>
                    
                </tr>
            </table>
        </span>
        <span py:if="len(needunpush)">
            <b>Unpush</b>
            <table class="list">
			    <th class="list" width="5%">
			    </th>
			    <th class="list" width="45%">
			        <b>Package</b>
			    </th>
			    <th class="list" width="10%">
			        <b>Karma</b>
			    </th>
			    <th class="list" width="20%">
			        <b>Release / Status</b>
			    </th>
			    <th class="list" width="20%">
			        <b>Type</b>
			    </th>
                <tr class="list" py:for="update in needunpush">
		            <?python
		                if update.karma < 0: karma = -1
						elif update.karma > 0: karma = 1
						else: karma = 0
						karma = XML("<img src=\"%s\" align=\"top\" /> <b>%d</b>" % (tg.url('/static/images/karma%d.png' % karma), update.karma))
					?>
                    <td class="list">
                        <input type="checkbox" name="updates" value="${update.title}" checked="True"/>
                    </td>
                    <td class="list">
                        <a href="${tg.url(update.get_url())}">${update.title}</a>
                    </td>
                    <td class="list">			
                        ${karma}
                    </td>
                    <td class="list">
                        ${"%s / %s " % (update.release.name, update.status)}
                    </td>
                    <td class="list">
                        ${update.type}
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
