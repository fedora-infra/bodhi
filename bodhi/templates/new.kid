<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${action}"
    method="${method}"
    py:attrs="form_attrs" width="100%">

    <script type="text/javascript">

    function addBuildField() {
        var oldField = $('newfield');
        var newField = oldField.cloneNode(true);
        newField.style.display = 'block';
        oldField.parentNode.insertBefore(newField, oldField);
        $('form_builds').value = $('form_build_text').value;
        $('form_build_text').value = "";
        $('form_build_text').focus();
    }

    addLoadEvent(function(e){
        $('form_build_text').focus();
    })

    </script>

    <table cellpadding="0" cellspacing="0">
        <tr>
            <td class="title">
                Package(s):
            </td>
            <td class="value">
                ${display_field_for('build')}
            </td>
        </tr>
        <tr>
            <td class="title"></td>
            <td class="value" style="padding-left: 8px">
                <div id="newfield" style="display: none">
                    ${display_field_for('builds')}
                </div>
            </td>
        </tr>
        <tr>
            <td class="title">Release:</td>
            <td class="value">${display_field_for('release')}</td>
        </tr>
        <tr>
            <td class="title">Type:</td>
            <td class="value">${display_field_for('type')}</td>
        </tr>
        <tr>
            <td class="title">Bugs:</td>
            <td class="value">${display_field_for('bugs')}</td>
        </tr>
        <tr>
            <td class="title"><a href="http://cve.mitre.org">CVEs</a>:</td>
            <td class="value">${display_field_for('cves')}</td>
        </tr>
        <tr>
            <td class="title">Notes:</td>
            <td class="value">${display_field_for('notes')}</td>
        </tr>
        <tr>
            <td class="title">${display_field_for('edited')}</td>
            <td class="value">${display_field_for('submit')}</td>
        </tr>
    </table>
</form>
