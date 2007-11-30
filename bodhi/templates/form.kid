<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>

    /*
    ** If we're flashing a broken update path error message, then display
    ** the obsolete dialog.
    */
    <script type="text/javascript">
        $(document).ready(function() {
            if( $('div.flash').text().substring(18, 0) == "Broken update path" ){
                $('#obsolete_dialog').load('/updates/obsolete_dialog?update=' + 
                                           $('#form_builds_text').val().split()[0]);
            }
        })
    </script>

    <title py:content="title" />

</head>


<body class="flora">
    <div id="obsolete_dialog" class="obsolete_dialog" />
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
