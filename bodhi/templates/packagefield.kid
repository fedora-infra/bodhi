<div xmlns:py="http://purl.org/kid/ns#">
    <script language="JavaScript" type="text/JavaScript">
        AutoCompleteManager${field_id} = new AutoCompleteManager('${field_id}',
        '${text_field.field_id}', '${hidden_field.field_id}',
        '${search_controller}', '${search_param}', '${result_name}',${str(only_suggest).lower()},
        '${tg.widgets}/turbogears.widgets/spinner.gif', 0.2);
        addLoadEvent(AutoCompleteManager${field_id}.initialize);
    </script>
    <table cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td>
          ${text_field.display(value_for(text_field), **params_for(text_field))}
        </td>
        <td>
          <img name="autoCompleteSpinner${name}" id="autoCompleteSpinner${field_id}" src="${tg.widgets}/turbogears.widgets/spinnerstopped.png" alt="" />
        </td>
      </tr>
      <tr>
        <td>
          <div class="autoTextResults" id="autoCompleteResults${field_id}">${hidden_field.display(value_for(hidden_field), **params_for(hidden_field))}</div>
        </td>
      </tr>
      <tr>
        <td>
          <a id="addField" href="#" class="list">
            <img src="${tg.url('/static/images/plus.png')}" border="0" alt="Add another package to this update"/>
          Add another build
          </a>
        </td>
     </tr>
    </table>
</div>
