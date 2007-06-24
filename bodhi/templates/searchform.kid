<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${action}"
    method="${method}"
    py:attrs="form_attrs" width="100%"
    onsubmit="$('bodhi-logo').style.display = 'none'; $('wait').style.display='block'">

    <script type="text/javascript">

    addLoadEvent(function(){
        connect($('form_search'), 'onclick', function (e) {
            $('form_search').value = "";
        });
    });

    </script>

    <table cellpadding="0" cellspacing="0">
        <tr>
            <td class="value">
                ${display_field_for("search")}
            </td>
        </tr>
    </table>
</form>
