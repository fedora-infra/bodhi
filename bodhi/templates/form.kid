<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
</head>


<body>
    <div>
        <table cellspacing="10">
            <tr>
                <td>
                    ${form(value=values, action=action)}
                </td>
            </tr>
        </table>
    </div>

<script language="javascript">
    function newType() {
        log("newType()");
        var val = getElement("form_type").value;
        logDebug("val = " + val);
        toggle("form_embargo");
        if (val == "security") {
            logDebug("val is security");
            toggle("form_embargo");
            //showElement(getElement("form_embargo"));
            //showElement(getElement("form_embargo_trigger"));
        } else {
            hideElement(getElement("form_embargo"));
            //showElement(getElement("form_embargo_trigger"));
        }
    }

    //createLoggingPane(true);
    logDebug("done");
</script>
</body>
</html>
