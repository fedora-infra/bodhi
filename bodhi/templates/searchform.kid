<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${tg.url('/search/')}"
    method="${method}"
    py:attrs="form_attrs" width="100%">

    <script type="text/javascript">
        $(document).ready(function() {
            $('#form_search').click( function() { $(this).val(""); } );
            $('#form_search').blur( function() {
                if ( $(this).val() == "" )
                    $(this).val("  Package | Bug # | CVE  ");
            } );
        } );
    </script>

    <table cellpadding="0" cellspacing="0">
        <tr>
            <td class="value">
                ${display_field_for("search")}
            </td>
        </tr>
    </table>
</form>
