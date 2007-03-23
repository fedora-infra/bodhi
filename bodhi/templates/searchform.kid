<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${action}"
    method="${method}"
    py:attrs="form_attrs" width="100%">

    <table width="100%" cellspacing="0" cellpadding="0">
        <tr>
            <td class="search-title">
                <h3>[ Package | Bug # | CVE ]:</h3>
            </td>
            <td class="search-value">
                ${display_field_for("search")}
            </td>
        </tr>
        <tr>
            <td class="search-title">
            </td>
            <td class="search-value">
                ${display_field_for("submit")}
            </td>
        </tr>
    </table>
</form>

