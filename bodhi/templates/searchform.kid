<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${tg.url('/search/')}"
    method="${method}"
    py:attrs="form_attrs" width="100%"
    onsubmit="$('bodhi-logo').style.display = 'none'; $('wait').style.display='block'">

    <script type="text/javascript">

    addLoadEvent(function(){
        connect($('form_search'), 'onclick', function (e) {
            $('form_search').value = "";
        });
        connect($('form_search'), 'onblur', function (e) {
            if( $('form_search').value == "" ){
                $('form_search').value = "  Package | Bug # | CVE  ";
            }
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
